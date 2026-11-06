"""The input box and keys (D-035), driven through a real prompt_toolkit session with simulated key presses."""
import pathlib
import sys
import threading

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessageChunk
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from app import ui
from app.ui import input as uin
from app.ui.keys import KeyWatcher

ENTER, ALT_ENTER, ESC = "\r", "\x1b\r", "\x1b"
CTRL_C, SHIFT_TAB, CTRL_J = "\x03", "\x1b[Z", "\n"
PASTE_START, PASTE_END = "\x1b[200~", "\x1b[201~"


def run_prompt(keys: str, tmp_path, state=None, default: str = ""):
    state = state or uin.UiState()
    with create_pipe_input() as inp:
        inp.send_text(keys)
        with create_app_session(input=inp, output=DummyOutput()):
            box = uin.InputBox(workspace=str(tmp_path), commands=[("/help", "Show help")], state=state,
                               message="› ", toolbar=None, history_file=tmp_path / "hist.txt",
                               input=inp, output=DummyOutput())
            return box.prompt(default=default), state


def test_enter_sends(tmp_path):
    text, _ = run_prompt("hello" + ENTER, tmp_path)
    assert text == "hello"


@pytest.mark.parametrize("newline", [ALT_ENTER, CTRL_J])
def test_new_line_keys_insert_a_line_instead_of_sending(tmp_path, newline):
    text, _ = run_prompt("line one" + newline + "line two" + ENTER, tmp_path)
    assert text == "line one\nline two"


def test_esc_esc_clears_the_input(tmp_path):
    text, state = run_prompt("draft" + ESC + ESC + "kept" + ENTER, tmp_path)
    assert text == "kept"


def test_ctrl_c_clears_then_twice_on_empty_quits(tmp_path):
    with pytest.raises(EOFError):
        run_prompt("typed" + CTRL_C + CTRL_C + CTRL_C, tmp_path)   # clear, then twice on empty


def test_shift_tab_cycles_ask_auto_edit_plan(tmp_path):
    _, state = run_prompt(SHIFT_TAB + "x" + ENTER, tmp_path, uin.UiState(mode="approve"))
    assert state.mode == "auto"
    _, state = run_prompt(SHIFT_TAB + SHIFT_TAB + "x" + ENTER, tmp_path, uin.UiState(mode="approve"))
    assert state.mode == "plan"
    assert [uin.mode_label(m) for m in uin.MODES] == ["ask", "auto-edit", "plan"]
    assert uin.next_mode("plan") == "approve" and uin.next_mode("read-only") == "approve"


def test_history_is_saved_between_sessions(tmp_path):
    run_prompt("first prompt" + ENTER, tmp_path)
    # A new session reads the same file (prompt_toolkit loads it in the background, so read it directly).
    from prompt_toolkit.history import FileHistory
    assert "first prompt" in list(FileHistory(str(tmp_path / "hist.txt")).load_history_strings())
    assert uin.history_path(str(tmp_path)).name.endswith(".txt")


def test_short_paste_is_inserted_and_long_paste_is_folded_then_expanded(tmp_path):
    text, _ = run_prompt(PASTE_START + "a\nb" + PASTE_END + ENTER, tmp_path)
    assert text == "a\nb"
    big = "\n".join(f"line {i}" for i in range(40))
    state = uin.UiState()
    shown = uin.fold_paste(state, big)
    assert shown == "[pasted text #1: 40 lines]"
    assert uin.expand_pastes(state, f"fix this: {shown}") == f"fix this: {big}"
    text, _ = run_prompt(PASTE_START + big + PASTE_END + ENTER, tmp_path)
    assert text == big


def test_typed_ahead_text_prefills_the_next_prompt(tmp_path):
    text, _ = run_prompt(" more" + ENTER, tmp_path, default="typed while waiting")
    assert text == "typed while waiting more"


def test_windows_reader_turns_shift_enter_into_a_new_line():
    if sys.platform != "win32":
        pytest.skip("Windows console only")
    from prompt_toolkit.keys import Keys
    inp = uin.make_input()
    if inp is None:
        pytest.skip("no console")
    reader = inp.console_input_reader
    from prompt_toolkit.win32_types import KEY_EVENT_RECORD

    def ev(char, vk, state):
        rec = KEY_EVENT_RECORD()
        rec.KeyDown, rec.RepeatCount, rec.VirtualKeyCode, rec.ControlKeyState = 1, 1, vk, state
        rec.uChar.UnicodeChar = char
        return rec
    shift_enter = reader._event_to_key_presses(ev("\r", 0x0D, reader.SHIFT_PRESSED))
    plain_enter = reader._event_to_key_presses(ev("\r", 0x0D, 0))
    ctrl_back = reader._event_to_key_presses(ev("\x7f", 0x08, reader.LEFT_CTRL_PRESSED))
    assert [k.key for k in shift_enter] == [Keys.Escape, Keys.ControlM]
    assert [k.key for k in plain_enter] == [Keys.ControlM]
    assert [k.key for k in ctrl_back] == [Keys.ControlW]


# ── esc stops the model; type-ahead ─────────────────────────────────────────

def fake_keys(seq):
    buf = list(seq)
    return dict(getch=lambda: buf.pop(0), kbhit=lambda: bool(buf))


def test_key_watcher_sets_stop_on_esc_and_keeps_typed_text(monkeypatch):
    monkeypatch.setattr("app.ui.keys._is_console", lambda: True)
    w = KeyWatcher(poll=0.01, **fake_keys("ab\x08c\x1b"))
    with w:
        assert w.stop.wait(2)
    assert w.take_typed() == "ac"


def test_stream_stops_when_asked_and_keeps_the_partial_answer():
    c = ui.apply(Console(record=True, width=100, color_system=None))
    stop = threading.Event()

    def chunks():
        yield AIMessageChunk(content="Partial answer")
        stop.set()
        yield AIMessageChunk(content=" never shown")

    res = ui.stream_reply(c, chunks(), stop=stop)
    out = c.export_text()
    assert res.stopped and res.text == "Partial answer"
    assert "Partial answer" in out and "never shown" not in out and "Stopped" in out


def test_hidden_thinking_is_folded_for_ctrl_o():
    c = ui.apply(Console(record=True, width=100, color_system=None))
    folded = uin.Folded()
    ui.stream_reply(c, iter([AIMessageChunk(content="<think>plan</think>Answer")]), folded=folded)
    assert folded.title == "Thinking" and folded.text == "plan"


def test_long_command_output_is_folded(tmp_path):
    from app.agents import shell
    shell.configure(workspace=str(tmp_path), allowed_roots=[str(tmp_path)])
    c = ui.apply(Console(record=True, width=100, color_system=None))
    script = "import sys\nfor i in range(25): print('line', i)"
    (tmp_path / "many.py").write_text(script)
    run = "& " if sys.platform == "win32" else ""   # PowerShell needs & to run a quoted path
    r = shell.execute(f'{run}"{sys.executable}" many.py', cwd=str(tmp_path), console=c, typed_by_user=True)
    out = c.export_text()
    assert "line 9" in out and "line 10" not in out
    assert r.hidden_lines == 15 and len(r.output_lines) == 25
    assert "+15 lines (ctrl+o)" in ui.shell_done(r).plain


# ── notifications ───────────────────────────────────────────────────────────

def test_notify_rings_only_after_a_long_turn(monkeypatch):
    calls = []
    monkeypatch.setattr(ui.notify, "bell", lambda console: calls.append("bell"))
    monkeypatch.setattr(ui.notify, "set_title", lambda console, t: calls.append(t))
    ui.notify.done(None, 5)
    ui.notify.done(None, 45)
    ui.notify.waiting(None)
    assert calls == ["Mitra · ready", "✓ Mitra · done", "bell", "❓ Mitra · waiting for you", "bell"]
