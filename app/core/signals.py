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
        return True
    if len(cur.split()) < 4 or cur == prev and len(cur.split()) < 4:
        return False
    return difflib.SequenceMatcher(None, prev, cur).ratio() >= REPHRASE_RATIO
