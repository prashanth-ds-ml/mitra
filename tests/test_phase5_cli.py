import pathlib
import sys
from types import SimpleNamespace

from typer.testing import CliRunner

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import memory
from app.main import cli


runner = CliRunner()


def _write_simple_game_playbook(tmp_path):
    playbook = tmp_path / "playbooks" / "simple-game" / "PLAYBOOK.md"
    playbook.parent.mkdir(parents=True)
    playbook.write_text(
        """---
name: simple-game
description: Start a small game project with one core mechanic.
target_stack: React or browser game
starter_steps: ["Pick the simplest playable mechanic", "Build the game loop", "Verify the game is playable"]
---
# Simple Game
""",
        encoding="utf-8",
    )


def test_test_command_defaults_to_pytest(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.main.shell_agent.execute",
        lambda command, cwd, console=None: SimpleNamespace(output="12 passed", ok=True),
    )
    monkeypatch.setattr("app.main.shell_agent.render", lambda result: result.output)

    result = runner.invoke(cli, ["test", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "12 passed" in result.stdout


def test_logs_command_shows_summary(tmp_path):
    memory.init_memory(str(tmp_path))

    result = runner.invoke(cli, ["logs", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Logs" in result.stdout
    assert "execution_trace.jsonl" in result.stdout


def test_logs_command_can_show_history_artifact(tmp_path):
    memory.init_memory(str(tmp_path))
    memory.append_activity(str(tmp_path), "first ask", "first reply")

    result = runner.invoke(cli, ["logs", "history", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "activity.md" in result.stdout
    assert "first ask" in result.stdout
