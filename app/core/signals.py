"""What the records need for self-improvement (D-068 step 0): the version of your notes, and quiet signs of what you
thought of a turn (you asked again, stopped it, undid it, copied it). Pure functions, no model calls."""
from __future__ import annotations

import difflib
import hashlib
import re
from pathlib import Path

from app.core import harness as H

# rows of kind "signal": signal = one of these
SIGNALS = ("rephrase", "interrupt", "undo", "copy", "unhappy", "happy")

# D-079 (feedback every turn, no extra work): your next message is the verdict on the last answer. Live 2026-11-13
# (Neon Chomp): "i thought neon chomp...???", "why dont you do that", "did you do that fix" and a pasted traceback
# after "running successfully" were all verdicts; none was recorded
_UNHAPPY = re.compile(
    # "...???" alone is the user's emphasis, also in plain questions ("can we add these features...???"): not a verdict
    r"^\s*i thought\b|\bwhy (dont|don'?t|didn'?t|did not|can'?t|cant|won'?t|aren'?t|are you not|"
    r"is it not)\b|\bdid you (really )?(do|fix|make|change|add|run|test|check) (that|it|this|the|those|them)\b|"
    r"\byou (said|told me)\b.*\bbut\b|"
    r"\b(still|again) (not|broken|failing|wrong|the same)\b|\b(not|isn'?t|doesn'?t|does not|don'?t) (working|work)\b|"
    r"\b(unable|cant|can'?t|cannot) (to )?(move|play|run|start|open|launch|see|use|find)\b|\bnothing (happens|changed)\b|"
    r"\b(that'?s|this is|it'?s) (wrong|not right|incorrect|broken)\b|\bwe are talking about\b",
    re.IGNORECASE)
_PASTED_ERROR = re.compile(r"Traceback \(most recent call last\)|^\w*(Error|Exception): |\bexit code [1-9]",
                           re.MULTILINE)
_HAPPY = re.compile(
    r"^\W*(thanks|thank you|thx|great|perfect|nice|awesome|cool|excellent|good job|well done|works|it works|"
    r"working now|looks good|lgtm|love it|that'?s it|exactly|correct|super|brilliant)\b",
    re.IGNORECASE)

# the user says the last answer was not what they wanted
_AGAIN = re.compile(r"^\s*(no\b|nope\b|not (that|this|what)|i meant\b|i mean\b|that'?s (wrong|not)|wrong\b|"
                    r"try again\b|again\b|still (wrong|not|failing|broken)|it (still )?(doesn'?t|does not|didn'?t) work)",
                    re.IGNORECASE)
# E-104 (live 2026-11-11): "i said you to pick and tell me with a reason right why are not following that mitra" was
# not a signal: you correcting Mitra for not doing what you asked
_CORRECTED = re.compile(
    r"^\s*(i (already |just )?(said|told you|asked you)\b|you (didn'?t|did not|are not|aren'?t|forgot|ignored|missed)\b"
    r"|(that'?s|this is|it'?s) not what i (asked|said|wanted|meant))"
    r"|\bwhy (are|aren'?t|did|didn'?t|do|don'?t|is|isn'?t)( you| it)? (not |n'?t )?(follow|listen)",
    re.IGNORECASE)
REPHRASE_RATIO = 0.6  # this similar to the previous message = the same request asked again


def notes_files(workspace: Path) -> list[Path]:
    """Your notes Mitra reads every turn (D-068 step 1): ~/.mitra/me.md and the project's .mitra/notes.md."""
    return [H.home() / "me.md", Path(workspace) / ".mitra" / "notes.md"]


def notes_version(workspace: Path) -> str:
    """8 hex of the notes' contents, "none" when there are none: which notes a turn ran with."""
    h, found = hashlib.sha1(), False
    for f in notes_files(workspace):
        try:
            data = f.read_bytes()
        except OSError:
            continue
        found = True
        h.update(f.name.encode("utf-8") + b"\0" + data + b"\0")
    return h.hexdigest()[:8] if found else "none"


def _words(text: str) -> str:
    return " ".join(str(text).lower().split())


def is_rephrase(previous: str, now: str) -> bool:
    """The user asked again: says the answer was wrong, or sent nearly the same message (not a short "ok")."""
    prev, cur = _words(previous), _words(now)
    if not prev or not cur:
        return False
    if _AGAIN.match(cur):
        # a bare "no" answers Mitra's question ("shall I add tests too?"); "no, I meant ..." asks again
        return not re.fullmatch(r"(no|nope)\W*(thanks?|thank you)?\W*", cur)
    if _CORRECTED.search(cur):
        return True
    if len(cur.split()) < 4:
        return False
    return difflib.SequenceMatcher(None, prev, cur).ratio() >= REPHRASE_RATIO


def implicit_label(previous_answer: str, now: str, did_work: bool = False) -> tuple[str, str] | None:
    """D-079: what your next message says about the last answer -> ("unhappy" | "happy", why), or None when it does
    not say (most messages: a new task, a follow-up). Never a guess: only clear words, or an error pasted right
    after a turn that worked on files. A rephrase is recorded on its own (is_rephrase), not here too."""
    cur = (now or "").strip()
    if not cur or cur.startswith("/") or not (previous_answer or "").strip():
        return None
    if _PASTED_ERROR.search(cur):  # live turn 14: the traceback came right after "I've fixed all the issues"
        return "unhappy", "pasted an error after the change" if did_work else "pasted an error"
    m = _UNHAPPY.search(cur)
    if m:
        return "unhappy", m.group(0).strip()[:40]
    m = _HAPPY.search(cur)
    if m and not re.search(r"\bbut\b", cur, re.IGNORECASE):
        return "happy", m.group(0).strip(" .!,")[:40]
    return None


# ── your notes, read every turn (D-068 step 1) ──────────────────────────────────

NOTES_MAX_CHARS = 2000  # both files together, so a long notes file never crowds out the task
ME_TEMPLATE = """# About me (Mitra reads this every turn; edit it any time)

Name:
Role:
Mail signature:
    Regards,
    <your name>

Tone: concise, friendly, plain English; no filler
Stack:
Habits:
"""


def ensure_me() -> Path | None:
    """Create ~/.mitra/me.md from the template the first time; returns its path when it was just created."""
    f = H.home() / "me.md"
    if f.exists():
        return None
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(ME_TEMPLATE, encoding="utf-8")
        return f
    except OSError:
        return None


def notes_text(workspace: Path, max_chars: int = NOTES_MAX_CHARS) -> str:
    """Your notes for the prompt: me.md, then the project's notes; template lines left empty are dropped."""
    parts = []
    for f, title in zip(notes_files(workspace), ("About the user (me.md)", "Project notes (.mitra/notes.md)")):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        raw = [ln.rstrip() for ln in text.splitlines() if ln.strip() and "<your name>" not in ln]
        lines = []
        for i, ln in enumerate(raw):
            if ln.lstrip().startswith("#"):
                continue
            nxt = raw[i + 1] if i + 1 < len(raw) else ""
            if re.fullmatch(r"\s*[\w ]+:\s*", ln) and not nxt.startswith((" ", "\t")):
                continue  # a template field left empty ("Stack:"), not a heading for indented lines below
            lines.append(ln)
        if len(lines) == 1 and lines[0].strip().endswith(":"):
            lines = []
        if lines:
            parts.append(f"## {title}\n" + "\n".join(lines))
    out = "\n\n".join(parts)
    return out if len(out) <= max_chars else out[:max_chars - 1] + "…"
