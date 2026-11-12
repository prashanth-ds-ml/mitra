"""Your /bad becomes a score case (D-078 Phase 2, step 6; must-have 10: an exam that grows from your real failures).

    find    -> every /bad in your recorded conversations not drafted yet: what you said, the turns before it, what
               Mitra answered, your note (sessions are split, since turn numbers restart in each one)
    draft   -> the coach (Claude, `claude -p`, no tools) writes the case when it can; otherwise a template from your
               note (search/web -> lookup, files/code -> look, else talk). A small model never writes the case: the
               research says a 9B judges itself poorly
    review  -> you keep, edit or drop each draft; kept cases go to ~/.mitra/score/real.toml

The "real" category is private (your words stay on this machine, never in the repo) and held out: `mitra score` runs
it, `mitra improve` never learns from it, so a learned rule cannot be fitted to it."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from app.core import harness as H

EXPECTS = ("talk", "look", "lookup", "change")
FIELDS = {"id", "text", "history", "expect", "max_words", "ask_back", "must_not", "facts", "cite", "note"}
HISTORY_TURNS = 2
MAX_TEXT = 1500

CASE_PROMPT = """You turn one conversation turn the user marked /bad into a test case for Mitra, a local coding
assistant. The case is replayed later: Mitra gets the same message (and the turns before it) and must now do the
right thing. Write ONLY one TOML [[case]] table, no prose, using only these keys:
  id        "R_<short_snake_case_name>"
  text      the user's message, exactly as below
  history   [[you, mitra], ...] the turns before it, as below (may be [])
  expect    "talk" (answer without tools), "look" (read the project's files first), "lookup" (search the web first)
            or "change" (change the project's files)
  max_words a number, for talk answers that should stay short (optional)
  ask_back  true when the answer should end with a question (optional)
  must_not  list of regexes the answer must NOT match, e.g. '(?i)would you like me to search' (optional)
  facts     list of regexes the answer MUST match (optional; only facts that are certain)
  note      the user's note, as below
Pick expect and the checks from the user's note: it says what should have happened.

The turn:
"""


def home() -> Path:
    return H.home() / "cases"


def real_path() -> Path:
    return H.home() / "score" / "real.toml"


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


def _sessions(rows: list[dict]) -> list[list[dict]]:
    """Rows split at each `session` row: turn numbers restart in every session."""
    out: list[list[dict]] = [[]]
    for r in rows:
        if r.get("kind") == "session" and out[-1]:
            out.append([])
        out[-1].append(r)
    return [s for s in out if s]


def bad_turns(files: list[Path]) -> list[dict]:
    """Every /bad in your chat records: {key, t, project, you, mitra, note, history}, oldest first."""
    found = []
    for f in files:
        if not f.name.startswith("chat-"):
            continue
        for sess in _sessions(_rows(f)):
            starts = {r.get("turn"): r for r in sess if r.get("kind") == "turn_start"}
            ends = {r.get("turn"): r for r in sess if r.get("kind") == "turn_end"}
            for r in sess:
                if r.get("kind") != "feedback" or r.get("verdict") != "bad":
                    continue
                n = r.get("of_turn")
                start, end = starts.get(n), ends.get(n, {})
                if not start or str(start.get("user", "")).startswith("/"):
                    continue
                before = [k for k in sorted(x for x in starts if isinstance(x, int)) if k < n][-HISTORY_TURNS:]
                history = [[str(starts[k].get("user", ""))[:MAX_TEXT], str(ends.get(k, {}).get("text", ""))[:MAX_TEXT]]
                           for k in before]
                found.append({"key": f"{f.parent.name}/{f.name}/{start.get('t')}", "t": float(start.get("t") or 0),
                              "project": f.parent.name.rsplit("-", 1)[0], "you": str(start.get("user", ""))[:MAX_TEXT],
                              "mitra": str(end.get("text", ""))[:MAX_TEXT], "note": str(r.get("note") or ""),
                              "history": history})
    return sorted(found, key=lambda x: x["t"])


def _state() -> dict:
    try:
        return json.loads((home() / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"drafted": []}


def _save_state(state: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    (home() / "state.json").write_text(json.dumps(state, indent=1), encoding="utf-8")


def new_bad_turns(files: list[Path]) -> list[dict]:
    done = set(_state().get("drafted", []))
    return [t for t in bad_turns(files) if t["key"] not in done]


def _slug(text: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", text.lower())[:4]) or "case"


def guess_expect(turn: dict) -> str:
    """The template's guess from your note (and the message): the coach does this better."""
    said = f"{turn.get('note', '')} {turn.get('you', '')}".lower()
    if re.search(r"web ?search|search|look ?up|internet|online|deep dive|sources", said):
        return "lookup"
    if re.search(r"\b(change|fix|edit|add|implement|build)\b", said) and not re.search(r"\babout\b", said):
        return "change"
    if re.search(r"\b(file|files|code|read)\b", said):
        return "look"
    return "talk"


def template_case(turn: dict) -> dict:
    case = {"id": f"R_{_slug(turn['you'])}", "text": turn["you"], "history": turn["history"],
            "expect": guess_expect(turn), "note": turn["note"] or "(no note)"}
    if case["expect"] == "talk":
        case["max_words"] = 250
    return case


def to_toml(case: dict) -> str:
    """One [[case]] table; strings in TOML basic strings (json.dumps escapes the same way for our text)."""
    lines = ["[[case]]"]
    for k in ("id", "text", "history", "expect", "max_words", "ask_back", "must_not", "facts", "cite", "note"):
        if k not in case:
            continue
        v = case[k]
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k} = {v}")
        else:
            lines.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def parse_case(text: str) -> dict:
    """A drafted [[case]] (from the coach or an edited file), checked: raises ValueError with the reason."""
    m = re.search(r"```(?:toml)?\s*\n(.*?)```", text or "", flags=re.S)
    body = m.group(1) if m else (text or "")
    try:
        data = tomllib.loads(body)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"not valid TOML: {exc}") from exc
    cases = data.get("case") or []
    if len(cases) != 1:
        raise ValueError(f"want exactly one [[case]], got {len(cases)}")
    case = cases[0]
    extra = set(case) - FIELDS
    if extra:
        raise ValueError(f"unknown keys: {', '.join(sorted(extra))}")
    if not str(case.get("text", "")).strip() or case.get("expect") not in EXPECTS:
        raise ValueError("needs text and expect (talk, look, lookup or change)")
    for pat in list(case.get("must_not", [])) + list(case.get("facts", [])):
        re.compile(pat)
    return case


def draft(turn: dict, run_claude=None) -> tuple[dict, str]:
    """(case, who drafted it: "coach" or "template"). The coach's case keeps your exact message and history."""
    if run_claude is not None:
        try:
            case = parse_case(run_claude(CASE_PROMPT + json.dumps(
                {"text": turn["you"], "history": turn["history"], "mitra_answered": turn["mitra"][:800],
                 "note": turn["note"]}, ensure_ascii=False, indent=1)))
            case.update(text=turn["you"], history=turn["history"], note=turn["note"] or "(no note)")
            case["id"] = case.get("id") if str(case.get("id", "")).startswith("R_") else f"R_{_slug(turn['you'])}"
            return case, "coach"
        except Exception:  # noqa: BLE001 - offline, no Claude, or a bad draft: the template still works
            pass
    return template_case(turn), "template"


def write_drafts(files: list[Path], run_claude=None, say=lambda t: None) -> list[Path]:
    """Draft every new /bad into ~/.mitra/cases/drafts/<id>.toml (a comment says what happened)."""
    state, written = _state(), []
    d = home() / "drafts"
    d.mkdir(parents=True, exist_ok=True)
    for turn in new_bad_turns(files):
        case, who = draft(turn, run_claude)
        path = d / f"{case['id']}.toml"
        n = 2
        while path.exists():
            path = d / f"{case['id']}_{n}.toml"
            n += 1
        case["id"] = path.stem
        head = (f"# /bad from {turn['project']} · drafted by the {who}\n# Mitra answered: "
                + " ".join(turn["mitra"].split())[:300] + "\n# Edit the checks if needed, then `mitra cases review`.\n")
        path.write_text(head + to_toml(case), encoding="utf-8")
        state.setdefault("drafted", []).append(turn["key"])
        written.append(path)
        say(f"  drafted {path.name} ({who}): expect {case['expect']}")
    _save_state(state)
    return written


def drafts() -> list[Path]:
    return sorted((home() / "drafts").glob("*.toml"))


def kept_ids() -> set[str]:
    try:
        return {c["id"] for c in tomllib.loads(real_path().read_text(encoding="utf-8")).get("case", [])}
    except (OSError, tomllib.TOMLDecodeError):
        return set()


def held_out_texts() -> set[str]:
    """The messages of the kept real cases (whitespace folded): `mitra improve` leaves these turns out."""
    try:
        data = tomllib.loads(real_path().read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set()
    return {" ".join(str(c.get("text", "")).split()) for c in data.get("case", [])}


def keep(path: Path) -> dict:
    """Check the draft and add it to ~/.mitra/score/real.toml; the draft file is removed."""
    case = parse_case(path.read_text(encoding="utf-8"))
    if case["id"] in kept_ids():
        raise ValueError(f"{case['id']} is already in real.toml")
    real = real_path()
    real.parent.mkdir(parents=True, exist_ok=True)
    if not real.exists():
        real.write_text('# Your real failures (D-078 step 6): private, held out from `mitra improve`.\n'
                        'project = "snake"\n\n', encoding="utf-8")
    with real.open("a", encoding="utf-8") as f:
        f.write("\n" + to_toml(case))
    path.unlink()
    return case


def drop(path: Path) -> None:
    path.unlink(missing_ok=True)
