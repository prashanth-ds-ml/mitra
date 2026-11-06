"""Keys while the model is writing (D-035): esc stops it; anything typed is kept for the next prompt.

Windows only (msvcrt); elsewhere the watcher does nothing and ctrl+c still stops the model.
"""
from __future__ import annotations

import sys
import threading
import time


class KeyWatcher:
    """Context manager: polls the console while the model streams.

    `stop` is set when esc is pressed; `typed` collects printable keys so they are not lost (type-ahead).
    """

    def __init__(self, *, poll: float = 0.05, getch=None, kbhit=None) -> None:
        self.stop = threading.Event()
        self.typed: list[str] = []
        self._poll = poll
        self._done = threading.Event()
        self._thread: threading.Thread | None = None
        if getch is None and sys.platform == "win32":
            import msvcrt
            getch, kbhit = msvcrt.getwch, msvcrt.kbhit
        self._getch, self._kbhit = getch, kbhit

    def _run(self) -> None:
        while not self._done.is_set():
            try:
                while self._kbhit():
                    ch = self._getch()
                    if ch in ("\x00", "\xe0"):      # arrow / function key: second code follows
                        self._getch()
                        continue
                    if ch == "\x1b":
                        self.stop.set()
                    elif ch == "\x08":
                        if self.typed:
                            self.typed.pop()
                    elif ch == "\r":
                        self.typed.append("\n")
                    elif ch.isprintable():
                        self.typed.append(ch)
            except Exception:
                return
            time.sleep(self._poll)

    def __enter__(self) -> "KeyWatcher":
        if self._getch is not None and self._kbhit is not None and sys.stdin is not None and _is_console():
            self._thread = threading.Thread(target=self._run, name="mitra-keys", daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._done.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def take_typed(self) -> str:
        text = "".join(self.typed).rstrip("\n")
        self.typed.clear()
        return text


def _is_console() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False
