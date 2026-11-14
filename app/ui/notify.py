"""Tell the user when CodeMitra needs them or has finished (D-035): window title + terminal bell.

The bell flashes the taskbar in Windows Terminal, so a long task can run while the user works elsewhere.
"""
from __future__ import annotations

LONG_TURN_SECONDS = 20.0


def set_title(console, text: str) -> None:
    try:
        if console.is_terminal:
            console.set_window_title(text)
    except Exception:
        pass


def bell(console) -> None:
    try:
        if console.is_terminal:
            console.file.write("\a")
            console.file.flush()
    except Exception:
        pass


def ready(console) -> None:
    set_title(console, "CodeMitra · ready")


def working(console) -> None:
    set_title(console, "⏳ CodeMitra · working")


def waiting(console) -> None:
    set_title(console, "❓ CodeMitra · waiting for you")
    bell(console)


def done(console, seconds: float) -> None:
    """After a turn: ring when it took long enough that the user may have looked away."""
    if seconds >= LONG_TURN_SECONDS:
        set_title(console, "✓ CodeMitra · done")
        bell(console)
    else:
        ready(console)
