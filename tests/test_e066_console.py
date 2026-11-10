"""E-066: without a real terminal the chat printed a 60-line prompt_toolkit traceback; now one line."""
import pytest
import typer

from app import main


def test_no_terminal_gives_one_line(monkeypatch, capsys):
    class NoConsoleScreenBufferError(Exception):
        pass

    def chat():
        raise NoConsoleScreenBufferError("Found xterm-256color, while expecting a Windows console")

    monkeypatch.setattr(main, "_chat", chat)
    ctx = type("Ctx", (), {"invoked_subcommand": None})()
    with pytest.raises(typer.Exit):
        main.main(ctx, show_version=False)
    assert "needs a terminal window" in capsys.readouterr().out


def test_other_errors_still_raise(monkeypatch):
    monkeypatch.setattr(main, "_chat", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    ctx = type("Ctx", (), {"invoked_subcommand": None})()
    with pytest.raises(RuntimeError):
        main.main(ctx, show_version=False)
