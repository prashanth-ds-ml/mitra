"""What the records need for self-improvement (D-068 step 0): the version of your notes, and quiet signs of what you
thought of a turn (you asked again, stopped it, undid it, copied it). Pure functions, no model calls."""
from __future__ import annotations

import difflib
import hashlib
import re
from pathlib import Path

from app.core import harness as H

# rows of kind "signal": signal = one of these
SIGNALS = ("rephrase", "interrupt", "undo", "copy")

# the user says the last answer was not what they wanted
_AGAIN = re.compile(r"^\s*(no\b|nope\b|not (that|this|what)|i meant\b|i mean\b|that'?s (wrong|not)|wrong\b|"
                    r"try again\b|again\b|still (wrong|not|failing|broken)|it (still )?(doesn'?t|does not|didn'?t) work)",
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
    if len(cur.split()) < 4:
        return False
    return difflib.SequenceMatcher(None, prev, cur).ratio() >= REPHRASE_RATIO


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
