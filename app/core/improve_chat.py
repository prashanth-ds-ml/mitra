"""`mitra improve --chat` (Phase B, first part; SELF_IMPROVEMENT.md section 12): learn one conversation rule from
what went wrong, and keep it only if `mitra score` says so.

    evidence -> the failed cases of the last score on this model and architecture, and your signals in the run
                records (/bad with its note, rephrase, interrupt, undo), each with what you said and what Mitra said
    propose  -> the chat model proposes ONE general rule (JSON, read by improve.parse_change; rules only)
    judge    -> the model categories of the quick score (behaviour, writing, explain, ideas), once with the current
                harness and once with the candidate: same model, same machine, same context
    decide   -> keep only if the candidate passes at least `min_gain` more cases and no category drops; a kept rule
                becomes the next harness version (`mitra harness revert <v>` undoes it)

Every attempt is logged in ~/.mitra/harness/attempts.jsonl (kind "chat"); the judge's score rows go to that round's
folder, not results/scores.jsonl. Local models only (D-025); nothing from Claude goes into the harness (D-022).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app.core import harness as H
from app.core import improve as I
from app.core import score as S

JUDGE_CATEGORIES = ("behaviour", "writing", "explain", "ideas")
MIN_GAIN = 2            # one run per arm is noisy (A/B 2026-11-11: the same setup moved by 1-3 cases)
MAX_FAILURES = 12
MAX_SIGNALS = 12
EVIDENCE_SIGNALS = ("rephrase", "interrupt", "undo")

PROPOSER_PROMPT = """You improve a local assistant's conversation behaviour by adding ONE short rule to its
instructions, never by changing its code. You get its instructions, cases it failed (what the user said and why the
answer failed) and signs the user was unhappy (marked an answer bad, asked again, stopped it, undid it).
Find the most common cause and propose one rule that would fix it. Answer with JSON only:
{"kind": "rule", "text": "<one instruction, under 200 characters>", "why": "<which failures it fixes, one line>"}
The rule must be general: never name a file, project, person or example from the evidence, and never repeat
something the instructions already say. Prefer the form "When the user ..., ...". """


# ── evidence ────────────────────────────────────────────────────────────────────────────────────────────────────

def case_texts() -> dict[str, str]:
    """What the user typed in each scored case, by id."""
    out = {}
    for name, key in (("behaviour.toml", "text"), ("writing.toml", "request"), ("explain.toml", "question")):
        try:
            for c in S._toml(name).get("case", []):
                out[c["id"]] = " ".join(str(c.get(key, "")).split())
        except (OSError, ValueError):
            continue
    return out


def last_score_row(rows: list[dict], *, model: str, arch: str) -> dict | None:
    """The newest full score row (no --only) on this model and architecture that has a model category."""
    for row in reversed(rows):
        if (row.get("model") == model and row.get("arch", "router") == arch and not row.get("only")
                and set(JUDGE_CATEGORIES) & set(row.get("categories", []))):
            return row
    return None


def score_failures(row: dict | None) -> list[dict]:
    if not row:
        return []
    texts = case_texts()
    return [{"id": c["id"], "category": c["category"], "why": c.get("why", ""), "asked": texts.get(c["id"], "")}
            for c in row.get("cases", []) if not c.get("passed") and c.get("category") != "sorting"][:MAX_FAILURES]


def _rows(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for x in lines:
        try:
            out.append(json.loads(x))
        except json.JSONDecodeError:
            continue
    return out


def conversation_signals(files: list[Path], limit: int = MAX_SIGNALS) -> list[dict]:
    """Your /bad marks and quiet signals, newest first, each with the turn it was about: what you said, what Mitra
    answered, your note, and (for a rephrase) what you said next."""
    found = []
    for f in files:
        rows = _rows(f)
        said = {r.get("turn"): str(r.get("user", "")) for r in rows if r.get("kind") == "turn_start"}
        answered = {r.get("turn"): str(r.get("text", "")) for r in rows if r.get("kind") == "turn_end"}
        for r in rows:
            kind = r.get("kind")
            if kind == "feedback" and r.get("verdict") == "bad":
                name = "bad"
            elif kind == "signal" and r.get("signal") in EVIDENCE_SIGNALS:
                name = r["signal"]
            else:
                continue
            turn = r.get("of_turn")
            you = said.get(turn, "")
            if not you or you.startswith("/"):
                continue
            found.append({"t": float(r.get("t") or 0), "signal": name, "you": you[:300],
                          "mitra": answered.get(turn, "")[:300], "note": str(r.get("note", ""))[:300],
                          "next": said.get(turn + 1, "")[:300] if isinstance(turn, int) and name == "rephrase"
                          else ""})
    found.sort(key=lambda x: -x["t"])
    return found[:limit]


def evidence_text(failures: list[dict], signals: list[dict]) -> str:
    parts = []
    if failures:
        parts.append("Cases it failed in the test set:")
        parts += [f"- [{f['category']}] the user said: \"{f['asked'][:240]}\" -> failed: {f['why']}" for f in failures]
    if signals:
        parts.append("\nSigns from real conversations:")
        for s in signals:
            line = f"- {s['signal']}: the user said \"{s['you']}\"; it answered \"{s['mitra'][:200]}\""
            if s["note"]:
                line += f"; the user's note: \"{s['note']}\""
            if s["next"]:
                line += f"; then the user said \"{s['next']}\""
            parts.append(line)
    return "\n".join(parts)


# ── propose ─────────────────────────────────────────────────────────────────────────────────────────────────────

def banned_words() -> set[str]:
    """Words a general rule may not contain: the score's project names and case ids (no learning the test set)."""
    words = {p.name.lower() for p in (S.SET / "projects").iterdir() if p.is_dir()} if (S.SET / "projects").is_dir() \
        else set()
    return words | {k.lower() for k in case_texts()}


def check_rule(text: str, banned: set[str]) -> str:
    low = text.lower()
    hit = sorted(w for w in banned if re.search(rf"\b{re.escape(w)}\b", low))
    return f"the rule names the test set ({', '.join(hit)}): it must be general" if hit else ""


def tried_rules() -> list[str]:
    """Rules a chat round already tried and dropped: not proposed again."""
    out = []
    for a in I.attempts():
        if a.get("kind") == "chat" and a.get("result") == "dropped" and str(a.get("change", "")).startswith("rule: "):
            out.append(a["change"][len("rule: "):])
    return out[-10:]


def propose_rule(evidence: str, h: H.Harness, llm, instructions: str, tries: int = 2,
                 tried: list[str] | None = None):
    """-> (Change | None, why not)."""
    banned = banned_words()
    tried = tried or []
    user = (f"Its instructions today:\n<<<\n{instructions}\n>>>\n\n{evidence}\n\n"
            f"Rules it has already learned: {json.dumps(h.rules) if h.rules else 'none'}"
            + (f"\nRules already tried that did not help (propose something different): {json.dumps(tried)}"
               if tried else ""))
    messages = [SystemMessage(content=PROPOSER_PROMPT), HumanMessage(content=user)]
    why = "no answer"
    for _ in range(tries):
        reply = llm.invoke(messages)
        change, why = I.parse_change(str(reply.content), h, tool_names=set())
        if change and change.kind != "rule":
            change, why = None, "only a rule can be proposed here"
        if change and change.text.lower() in {t.lower() for t in tried}:
            change, why = None, "that rule was already tried and did not help"
        if change:
            why = check_rule(change.text, banned)
            if not why:
                return change, ""
            change = None
        messages += [reply, HumanMessage(content=f"That was not usable ({why}). Answer with one valid JSON rule.")]
    return None, why


# ── judge and decide ────────────────────────────────────────────────────────────────────────────────────────────

def decide(base: dict, cand: dict, min_gain: int = MIN_GAIN) -> tuple[bool, str]:
    """base / cand: score rows' "score" ({category: [passed, total]})."""
    b, c = sum(p for p, _ in base.values()), sum(p for p, _ in cand.values())
    n = sum(t for _, t in base.values())
    dropped = [f"{k} {cand.get(k, [0, t])[0]}/{t} (was {p}/{t})" for k, (p, t) in base.items()
               if cand.get(k, [0, t])[0] < p]
    if dropped:
        return False, f"{c}/{n} (was {b}/{n}) but a category dropped: " + ", ".join(dropped)
    if c - b < min_gain:
        return False, f"{c}/{n} passed, needs at least {b + min_gain}/{n} (was {b}/{n})"
    return True, f"{c}/{n} passed (was {b}/{n})"


def _broken(row: dict) -> str:
    """Every model case failed with an error: the model or Ollama broke, the A/B would mean nothing."""
    cases = [c for c in row.get("cases", []) if c.get("category") != "sorting"]
    if cases and all(not c["passed"] and re.match(r"^[A-Z]\w*(Error|Exception)\b", c.get("why", "")) for c in cases):
        return cases[0]["why"][:300]
    return ""


def improve_chat(*, proposer, make_runner: Callable[[H.Harness, Path], S.Runner], model: str, arch: str,
                 score_row: dict | None, files: list[Path], instructions: Callable[[H.Harness], str],
                 min_gain: int = MIN_GAIN, dry_run: bool = False, cwd: Path | None = None, run_score=S.run,
                 say=print) -> dict:
    """One round. Returns the logged entry; entry["next_row"] is the judge row of the harness now active (the
    evidence for a next round)."""
    current = H.load()
    failures, signals = score_failures(score_row), conversation_signals(files)
    entry = {"date": time.strftime("%Y-%m-%d %H:%M"), "kind": "chat", "harness_version": current.version,
             "builder": model, "proposer": getattr(proposer, "model", "") or model, "arch": arch,
             "evidence": {"score": (score_row or {}).get("date", ""), "failed_cases": len(failures),
                          "signals": len(signals)}}
    if not failures and not signals:
        entry.update(result="skipped", reason="no failed cases and no signals: nothing to learn from")
        say("Nothing to learn from: no failed score cases and no /bad or rephrase signals. Run `mitra score --quick` "
            "first, or mark wrong answers with /bad <why> in the chat.")
        return entry
    say(f"Evidence: {len(failures)} failed case(s) from the score of {entry['evidence']['score'] or '-'}, "
        f"{len(signals)} signal(s) from your conversations. Asking {entry['proposer']} for a rule ...")
    change, why = propose_rule(evidence_text(failures, signals), current, proposer, instructions(current),
                               tried=tried_rules())
    if not change:
        entry.update(result="no_proposal", reason=why)
        I.log_attempt(entry)
        say(f"No usable proposal: {why}")
        return entry
    entry.update(change=change.describe(), why=change.why)
    say(f"Proposal: {change.describe()}\n  why: {change.why}")
    if dry_run:
        entry.update(result="dry_run")
        return entry
    runs = H.home() / "harness" / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-chat")
    results = runs / "scores.jsonl"

    def line(label):
        return lambda c: say(f"  {label} {'✓' if c.passed else '✗'} {c.id:16} {c.why}")

    cand_h = change.apply(current)
    cand_run = cand_h.copy()
    cand_run.version = current.version + 1
    say(f"Score with the current rules ({', '.join(JUDGE_CATEGORIES)}):")
    base = run_score(JUDGE_CATEGORIES, runner=make_runner(current, runs / "base"), model=model, cwd=cwd,
                     on_case=line("current "), results=results)
    if _broken(base):
        entry.update(result="bench_error", reason=_broken(base), base=base["score"], records=str(runs))
        I.log_attempt(entry)
        say(f"The model broke on every case, nothing changed: {_broken(base)}")
        return entry
    say("Score with the proposed rule:")
    cand = run_score(JUDGE_CATEGORIES, runner=make_runner(cand_run, runs / "candidate"), model=model, cwd=cwd,
                     on_case=line("proposal"), results=results)
    keep, reason = decide(base["score"], cand["score"], min_gain)
    entry.update(base=base["score"], candidate=cand["score"], result="kept" if keep else "dropped", reason=reason,
                 records=str(runs))
    if keep:
        H.save(cand_h, f"{change.describe()} ({reason}; mitra improve --chat)")
        entry["new_version"] = current.version + 1
    I.log_attempt(entry)
    say(f"{'Kept' if keep else 'Dropped'}: {reason}")
    if keep:
        say(f"  undo: mitra harness revert {current.version}")
    entry["next_row"] = cand if keep else base
    return entry
