"""The input box (D-035): multi-line editing, saved history, `/` and `@` menus, paste folding, mode switching.

Keys
    enter               send (or pick the highlighted menu item)
    shift+enter         new line (also alt+enter, ctrl+enter, ctrl+j)
    ↑ ↓                 move between lines; at the first/last line, earlier prompts
    ctrl+← ctrl+→       jump a word        ctrl+backspace / ctrl+w   delete a word
    ctrl+r              search earlier prompts
    esc esc             clear the input    ctrl+c   clear, or (on an empty line, twice) quit
    shift+tab           next mode: ask → auto-edit → plan
    ctrl+o              show the last folded output or thinking
    ctrl+l              clear the screen (the conversation is kept)
    ctrl+g              open the input in your editor
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.named_commands import get_by_name
from prompt_toolkit.keys import Keys

from app.ui.theme import prompt_style

# Mitra's session modes, in shift+tab order, with the names the user sees.
MODES = ("approve", "auto", "plan")
MODE_LABELS = {"approve": "ask", "auto": "auto-edit", "plan": "plan", "read-only": "plan"}

RATE_GOOD, RATE_BAD = "\x00rate:good", "\x00rate:bad"  # what prompt() returns for the + / - key (never typed text)
PASTE_FOLD_LINES = 12
PASTE_FOLD_CHARS = 1500
_PASTE_TOKEN = re.compile(r"\[pasted text #(\d+): \d+ lines\]")

_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mitra", ".pytest_cache", "dist", "build",
              ".mypy_cache", ".ruff_cache", ".idea", ".vscode", ".tox", ".next", "target"}


def _is_secret_file(name: str) -> bool:
    """Never offer secrets in the `@` menu."""
    low = name.lower()
    return (low.startswith(".env") or low.endswith((".pem", ".key", ".p12", ".pfx"))
            or low in {"id_rsa", "id_ed25519", ".npmrc", ".pypirc", ".netrc"})


def mode_label(mode: str) -> str:
    return MODE_LABELS.get(mode, mode)


def next_mode(mode: str) -> str:
    mode = "plan" if mode == "read-only" else mode
    return MODES[(MODES.index(mode) + 1) % len(MODES)] if mode in MODES else MODES[0]


@dataclass
class Folded:
    """The last thing shown folded (long command output, hidden thinking); ctrl+o prints it in full."""
    title: str = ""
    text: str = ""

    def remember(self, title: str, text: str) -> None:
        if text and text.strip():
            self.title, self.text = title, text


@dataclass
class UiState:
    """Per-session interface state (the chat loop owns one)."""
    mode: str = "approve"
    notice: str = ""
    notice_until: float = 0.0
    last_ctrl_c: float = 0.0
    folded: Folded = field(default_factory=Folded)
    pastes: dict[int, str] = field(default_factory=dict)
    can_rate: bool = False  # D-079: right after an answer, + / - on the empty prompt rates it (one key, no Enter)

    def say(self, text: str, seconds: float = 3.0) -> None:
        self.notice, self.notice_until = text, time.monotonic() + seconds

    def current_notice(self) -> str:
        return self.notice if time.monotonic() < self.notice_until else ""


# ── completion ───────────────────────────────────────────────────────────────

class FileIndex:
    """Workspace files for `@` completion, refreshed at most every few seconds."""

    def __init__(self, root: str, *, ttl: float = 15.0, limit: int = 20000) -> None:
        self.root, self.ttl, self.limit = root, ttl, limit
        self._files: list[str] = []
        self._at = -1e9

    def files(self) -> list[str]:
        if time.monotonic() - self._at < self.ttl:
            return self._files
        out: list[str] = []
        try:
            for dirpath, dirnames, filenames in os.walk(self.root):
                dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.endswith(".egg-info"))
                rel = os.path.relpath(dirpath, self.root)
                for name in sorted(filenames):
                    if _is_secret_file(name):
                        continue
                    out.append(name if rel == "." else f"{rel}/{name}".replace("\\", "/"))
                    if len(out) >= self.limit:
                        raise StopIteration
        except StopIteration:
            pass
        except OSError:
            pass
        self._files, self._at = out, time.monotonic()
        return out

    def search(self, query: str, n: int = 15) -> list[str]:
        q = query.lower().replace("\\", "/")
        scored = []
        for path in self.files():
            low = path.lower()
            base = low.rsplit("/", 1)[-1]
            if not q:
                score = 3
            elif base.startswith(q):
                score = 0
            elif q in base:
                score = 1
            elif q in low:
                score = 2
            else:
                continue
            scored.append((score, len(path), path))
        return [p for _, _, p in sorted(scored)[:n]]


class MitraCompleter(Completer):
    """`/` commands with a description; `@` file paths from the workspace."""

    def __init__(self, commands: list[tuple[str, str]], files: FileIndex | None) -> None:
        self.commands, self.files = commands, files

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/") and " " not in text and "\n" not in text:
            for name, desc in self.commands:
                if name.startswith(text):
                    yield Completion(name, start_position=-len(text), display=name, display_meta=desc)
            return
        m = re.search(r"(?:^|\s)@([^\s@]*)$", text)
        if m and self.files is not None:
            query = m.group(1)
            for path in self.files.search(query):
                yield Completion("@" + path, start_position=-len(query) - 1, display=path)


# ── Windows: tell shift+enter apart from enter ───────────────────────────────

def make_input():
    """On Windows, read raw key events so shift+enter and ctrl+backspace can be told apart.

    Windows Terminal sends the same byte for enter and shift+enter in VT mode; the console's own key events carry the
    shift state. Returns None (prompt_toolkit's default input) elsewhere or when there is no real console.
    """
    if sys.platform != "win32":
        return None
    try:
        from prompt_toolkit.input.win32 import ConsoleInputReader, Win32Input
        from prompt_toolkit.key_binding.key_processor import KeyPress

        class _Reader(ConsoleInputReader):
            def _event_to_key_presses(self, ev):
                presses = super()._event_to_key_presses(ev)
                state = ev.ControlKeyState
                ctrl = state & (self.LEFT_CTRL_PRESSED | self.RIGHT_CTRL_PRESSED)
                if state & self.SHIFT_PRESSED and len(presses) == 1 and presses[0].key == Keys.ControlM:
                    return [KeyPress(Keys.Escape, ""), presses[0]]      # shift+enter = alt+enter = new line
                if ctrl and ev.VirtualKeyCode == 0x08:                    # ctrl+backspace = delete a word
                    return [KeyPress(Keys.ControlW, "")]
                return presses

        inp = Win32Input()
        inp.console_input_reader = _Reader()
        inp._use_virtual_terminal_input = False
        return inp
    except Exception:
        return None


# ── paste folding ────────────────────────────────────────────────────────────

def fold_paste(state: UiState, text: str) -> str:
    """Text to insert for a paste: the paste itself, or a short placeholder when it is long."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.count("\n") + 1
    if lines < PASTE_FOLD_LINES and len(text) < PASTE_FOLD_CHARS:
        return text
    n = len(state.pastes) + 1
    state.pastes[n] = text
    return f"[pasted text #{n}: {lines} lines]"


def expand_pastes(state: UiState, text: str) -> str:
    return _PASTE_TOKEN.sub(lambda m: state.pastes.get(int(m.group(1)), m.group(0)), text)


# ── the input box ────────────────────────────────────────────────────────────

def history_path(workspace: str) -> pathlib.Path:
    home = pathlib.Path(os.environ.get("MITRA_HOME") or pathlib.Path.home() / ".mitra")
    key = hashlib.sha1(str(pathlib.Path(workspace).resolve()).lower().encode("utf-8")).hexdigest()[:12]
    return home / "history" / f"{key}.txt"


def make_key_bindings(state: UiState, *, print_folded: Callable[[], None] | None = None) -> KeyBindings:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        buf = event.current_buffer
        if buf.complete_state and buf.complete_state.current_completion:
            buf.apply_completion(buf.complete_state.current_completion)
            return
        buf.validate_and_handle()

    @kb.add("escape", "enter")   # alt+enter, and shift+enter via make_input()
    @kb.add("escape", "c-j")     # ctrl+enter on Windows
    @kb.add("c-j")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", "escape")
    def _(event):
        event.current_buffer.reset()
        state.say("input cleared")

    @kb.add("c-c")
    def _(event):
        buf = event.current_buffer
        if buf.text:
            buf.reset()
            return
        now = time.monotonic()
        if now - state.last_ctrl_c < 2.0:
            event.app.exit(exception=EOFError())
            return
        state.last_ctrl_c = now
        state.say("press ctrl+c again to quit", 2.0)

    @kb.add("s-tab")
    def _(event):
        state.mode = next_mode(state.mode)
        state.say(f"mode: {mode_label(state.mode)}")

    @kb.add("c-o")
    def _(event):
        if not state.folded.text:
            state.say("nothing folded yet")
            return
        if print_folded is not None:
            from prompt_toolkit.application import run_in_terminal
            run_in_terminal(print_folded)

    @kb.add("c-l")
    def _(event):
        event.app.renderer.clear()

    @kb.add("c-left")
    def _(event):
        get_by_name("backward-word").call(event)

    @kb.add("c-right")
    def _(event):
        get_by_name("forward-word").call(event)

    @kb.add("c-g")
    def _(event):
        event.current_buffer.open_in_editor()

    @kb.add(Keys.BracketedPaste)
    def _(event):
        event.current_buffer.insert_text(fold_paste(state, event.data))

    # D-079: one key rates the last answer, only on an empty prompt right after it; anything else types as usual
    from prompt_toolkit.filters import Condition

    rate_now = Condition(lambda: state.can_rate and not get_app().current_buffer.text)

    @kb.add("+", filter=rate_now)
    def _(event):
        state.can_rate = False
        event.app.exit(result=RATE_GOOD)

    @kb.add("-", filter=rate_now)
    def _(event):
        state.can_rate = False
        event.app.exit(result=RATE_BAD)

    return kb


class InputBox:
    def __init__(
        self,
        *,
        workspace: str,
        commands: list[tuple[str, str]],
        state: UiState,
        message: Callable,
        toolbar: Callable,
        print_folded: Callable[[], None] | None = None,
        history_file: pathlib.Path | None = None,
        input=None,
        output=None,
    ) -> None:
        self.state = state
        history = InMemoryHistory()
        path = history_file if history_file is not None else history_path(workspace)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            history = FileHistory(str(path))
        except OSError:
            pass
        kwargs = {}
        inp = input if input is not None else make_input()
        if inp is not None:
            kwargs["input"] = inp
        if output is not None:
            kwargs["output"] = output
        self.session = PromptSession(
            message=message,
            multiline=True,
            prompt_continuation=lambda width, line_number, wrap_count: "  ",
            history=history,
            completer=MitraCompleter(commands, FileIndex(workspace)),
            complete_while_typing=True,
            reserve_space_for_menu=0,  # no empty block under the input; the menu still opens (E-047)
            key_bindings=make_key_bindings(state, print_folded=print_folded),
            style=prompt_style(),
            bottom_toolbar=toolbar,
            refresh_interval=0.5,
            **kwargs,
        )

    def prompt(self, default: str = "") -> str:
        """The next message, with folded pastes expanded. Raises EOFError when the user quits."""
        text = self.session.prompt(default=default)
        out = expand_pastes(self.state, text)
        self.state.pastes.clear()
        return out
