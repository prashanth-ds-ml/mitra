"""`mitra coach` (self-improvement layer 2, D-075): Claude reviews Mitra's own records and writes a coach report.

    digest  -> from the run records since the last review (no model): every turn in short (what you said, what
               Mitra answered, path, phase, machine, time, tools) with the turns that need a look first (your /bad,
               corrections, empty or slow answers, tool errors, answers about the code or the web without looking)
    review  -> `claude -p` (your Claude Code, no tools) reads the digest and writes the report: findings, rules to
               test, code fixes, new score cases
    queue   -> the report's rules go to layer 1's queue (improve_chat): `mitra score` decides each one, as for
               Mitra's own rules; nothing from Claude enters Mitra untested (D-022)

Report: ~/.mitra/coach/<date>.md (with the digest beside it). The chat header reminds you after REMIND_DAYS days or
REMIND_TURNS new turns.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from app.core import harness as H

REMIND_DAYS = 7
REMIND_TURNS = 40
DIGEST_MAX_CHARS = 60_000
CLAUDE_TIMEOUT_S = 900
SLOW_S = 60
WORK_PHASES = ("look_at_code", "look_up", "make_change", "propose_plan")

COACH_PROMPT = """You are the coach of Mitra, a local coding assistant that runs small models (qwen3.5 9B) on the
user's laptop or a Kaggle GPU. Below is a digest of Mitra's recorded conversations since the last review. Find where
Mitra did worse than a good assistant would: wrong or invented answers, answering from memory when it should have
read the code or searched the web, ignoring what the user asked, too long answers, slow or empty
turns, tool errors, missed signals. Quote the turn for each finding.

Write the report in Markdown with exactly these sections:
## Findings
Numbered, most important first: what happened (quote), why it matters, the likely cause.
## Rules to test
Short general instructions that would fix a finding by prompt alone, in a fenced block marked `rules`, one JSON
object per line: {"text": "<under 200 characters, general: never names a file, project or person>", "why": "<finding
number and one line>"}. Only rules a small model can follow; none when a finding needs code.
## Code fixes
What needs a code change in Mitra (a missing phase, tool, check or setting), one line each with the finding number.
## New score cases
Messages worth adding to `mitra score` so the problem stays measured: the message, what a good answer does.
Be concrete and short. Do not invent turns that are not in the digest."""


def home() -> Path:
    return H.home() / "coach"


def _state() -> dict:
    try:
        return json.loads((home() / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    (home() / "state.json").write_text(json.dumps(state), encoding="utf-8")


def last_review_t() -> float:
    return float(_state().get("last_t") or 0)


# ── reading the records ─────────────────────────────────────────────────────────────────────────────────────────

def _rows(path: Path) -> list[dict]:
    out = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for x in lines:
        try:
            out.append(json.loads(x))
        except json.JSONDecodeError:
            continue
    return out


def _project(f: Path) -> str:
    """The store keeps records in runs/<project>-<6 hex>/: 'mitra-try-54b64f' -> 'mitra-try'."""
    name = f.parent.name
    if name in (".mitra", "runs"):  # a record still in its project: <project>/.mitra/runs/chat-*.jsonl
        name = f.parent.parent.parent.name if name == "runs" else f.parent.parent.name
    return re.sub(r"-[0-9a-f]{6}$", "", name)


def turns_since(files: list[Path], since_t: float) -> list[dict]:
    """Every chat turn after `since_t`, oldest first: {t, project, you, mitra, path, phase, backend, seconds, tools,
    tool_errors, flags}. /commands are left out."""
    turns = []
    for f in files:
        if not f.name.startswith("chat-"):  # only your conversations: not plan tasks, score or improve runs
            continue
        rows = _rows(f)
        by_turn: dict = {}
        for r in rows:
            n = r.get("turn") if r.get("kind") in ("turn_start", "turn_end", "phase", "talk_route", "grounding") else (
                r.get("of_turn") if r.get("kind") in ("signal", "feedback") else None)
            if r.get("kind") == "tool":
                n = r.get("turn")
            if n is None:
                continue
            by_turn.setdefault(n, []).append(r)
        for n, rs in by_turn.items():
            start = next((r for r in rs if r.get("kind") == "turn_start"), None)
            if not start or float(start.get("t") or 0) <= since_t:
                continue
            you = str(start.get("user", ""))
            if not you or you.startswith("/"):
                continue
            end = next((r for r in rs if r.get("kind") == "turn_end"), {})
            tools = [str(r.get("name")) for r in rs if r.get("kind") == "tool"]
            errors = [str(r.get("name")) for r in rs if r.get("kind") == "tool" and r.get("ok") is False]
            phase = next((str(r.get("name")) for r in rs if r.get("kind") == "phase"), "")
            talk = next((r for r in rs if r.get("kind") == "talk_route"), None)
            flags = []
            for r in rs:
                if r.get("kind") == "feedback" and r.get("verdict") == "bad":
                    flags.append("you marked it /bad" + (f": {r.get('note')}" if r.get("note") else ""))
                elif r.get("kind") == "signal" and r.get("signal") in ("rephrase", "interrupt", "undo"):
                    flags.append(f"signal: {r.get('signal')}")
                elif r.get("kind") == "grounding":  # E-110: claimed a check no tool result backed
                    flags.append("unverified claim: " + "; ".join(str(c)[:120] for c in (r.get("claims") or [])[:2]))
            text = str(end.get("text", "") or "")
            seconds = float(end.get("seconds") or 0)
            if not text.strip():
                flags.append("empty answer")
            if seconds >= SLOW_S:
                flags.append(f"slow: {seconds:.0f} s")
            if errors:
                flags.append("tool errors: " + ", ".join(errors[:4]))
            turns.append({"t": float(start.get("t") or 0), "project": _project(f), "you": you, "mitra": text,
                          "path": start.get("path", ""),
                          "phase": phase or ("talk" if start.get("path") == "phased" else ""),
                          "backend": "laptop" if talk else start.get("backend", ""), "seconds": seconds,
                          "tools": tools, "flags": flags})
    turns.sort(key=lambda x: x["t"])
    return turns


def reminder(files: list[Path], now: float | None = None) -> str:
    """The header line when a review is due, else ''."""
    now = now or time.time()
    since = last_review_t()
    n = len(turns_since(files, since))
    days = (now - since) / 86400 if since else None
    if n >= REMIND_TURNS or (days is not None and days >= REMIND_DAYS and n >= 1):
        when = f"last review {days:.0f} days ago" if days is not None else "no review yet"
        return f"coach: {when}, {n} new turns · `mitra coach`"
    return ""


# ── the digest ──────────────────────────────────────────────────────────────────────────────────────────────────

def _turn_text(t: dict, you_chars: int, mitra_chars: int) -> str:
    when = time.strftime("%m-%d %H:%M", time.localtime(t["t"]))
    head = f"[{when} · {t['project']} · {t['phase'] or t['path'] or '-'} · {t['backend'] or '-'} · {t['seconds']:.0f}s"
    if t["tools"]:
        head += " · tools: " + ", ".join(dict.fromkeys(t["tools"]))
    head += "]"
    lines = [head, f"YOU: {' '.join(t['you'].split())[:you_chars]}",
             f"MITRA: {' '.join(t['mitra'].split())[:mitra_chars]}"]
    if t["flags"]:
        lines.append("FLAGS: " + "; ".join(t["flags"]))
    return "\n".join(lines)


def digest(turns: list[dict], *, score_row: dict | None = None, harness: H.Harness | None = None,
           max_chars: int = DIGEST_MAX_CHARS) -> str:
    """Flagged turns in full first, then every turn in short, within `max_chars`."""
    h = harness or H.load()
    parts = [f"# Mitra records: {len(turns)} turns"
             + (f" from {time.strftime('%Y-%m-%d', time.localtime(turns[0]['t']))}" if turns else ""),
             f"Learned rules now (harness v{h.version}): " + (json.dumps(h.rules) if h.rules else "none")]
    if score_row:
        failed = [f"{c['id']}: {c.get('why', '')}" for c in score_row.get("cases", []) if not c.get("passed")]
        parts.append(f"Last `mitra score` ({score_row.get('date', '')}): "
                     + " · ".join(f"{k} {p}/{n}" for k, (p, n) in score_row.get("score", {}).items())
                     + ("\nFailed: " + "; ".join(failed[:15]) if failed else ""))
    flagged = [t for t in turns if t["flags"]]
    if flagged:
        parts.append(f"\n## Turns that need a look ({len(flagged)})")
        parts += [_turn_text(t, 600, 1500) for t in flagged]
    parts.append(f"\n## Every turn, in short ({len(turns)})")
    body = "\n\n".join(parts)
    rest = []
    for t in turns:
        block = _turn_text(t, 240, 400)
        if len(body) + sum(len(x) + 2 for x in rest) + len(block) > max_chars:
            rest.append(f"(… {len(turns) - len(rest)} more turns left out: the digest is full)")
            break
        rest.append(block)
    return body + "\n\n" + "\n\n".join(rest)


# ── the review ──────────────────────────────────────────────────────────────────────────────────────────────────

def claude_path() -> str | None:
    return shutil.which("claude")


def run_claude(text: str, timeout_s: float = CLAUDE_TIMEOUT_S, claude: str | None = None) -> str:
    """`claude -p` with the prompt on stdin, plain text out, no tools. Raises RuntimeError with the reason."""
    exe = claude or claude_path()
    if not exe:
        raise RuntimeError("Claude Code (`claude`) is not installed or not on PATH")
    try:
        p = subprocess.run([exe, "-p", "--output-format", "text", "--disallowed-tools", "Bash", "Edit", "Write",
                            "NotebookEdit", "WebFetch", "WebSearch"],
                           input=text, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude -p did not answer in {timeout_s / 60:.0f} min")
    if p.returncode != 0 or not p.stdout.strip():
        raise RuntimeError(f"claude -p failed ({p.returncode}): {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout.strip()


def parse_rules(report: str) -> list[dict]:
    """The ```rules block: one JSON object per line -> [{text, why}]."""
    m = re.search(r"```rules\s*\n(.*?)```", report or "", flags=re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = " ".join(str(d.get("text", "")).split())
        if text and len(text) <= H.MAX_RULE_CHARS:
            out.append({"text": text, "why": str(d.get("why", ""))[:200]})
    return out


def coach(files: list[Path], *, score_row: dict | None = None, ask=run_claude, now: float | None = None,
          say=print) -> dict:
    """One review. Returns {result, report, turns, findings_rules, queued}."""
    from app.core import improve_chat as IC
    now = now or time.time()
    turns = turns_since(files, last_review_t())
    if not turns:
        say("No new turns since the last review: nothing to coach.")
        return {"result": "skipped", "turns": 0}
    text = digest(turns, score_row=score_row)
    stamp = time.strftime("%Y-%m-%d-%H%M", time.localtime(now))
    home().mkdir(parents=True, exist_ok=True)
    (home() / f"{stamp}-digest.md").write_text(text, encoding="utf-8")
    flagged = sum(1 for t in turns if t["flags"])
    say(f"Digest: {len(turns)} turns ({flagged} flagged), {len(text):,} characters. Asking Claude (claude -p) …")
    try:
        report = ask(COACH_PROMPT + "\n\n---\n\n" + text)
    except RuntimeError as exc:
        say(f"The review did not run: {exc}")
        return {"result": "error", "reason": str(exc), "turns": len(turns)}
    path = home() / f"{stamp}.md"
    path.write_text(f"# Coach report · {time.strftime('%Y-%m-%d %H:%M', time.localtime(now))}\n\n"
                    f"{len(turns)} turns reviewed ({flagged} flagged) · digest: {stamp}-digest.md\n\n{report}\n",
                    encoding="utf-8")
    rules = parse_rules(report)
    queued = IC.queue_rules(rules, source="coach")
    _save_state({"last_t": max(t["t"] for t in turns), "last_report": str(path), "date": stamp})
    say(f"Report: {path}")
    say(f"{len(rules)} rule(s) suggested, {queued} queued for `mitra improve --chat` (the score decides each one)")
    return {"result": "done", "report": str(path), "turns": len(turns), "rules": len(rules), "queued": queued}
