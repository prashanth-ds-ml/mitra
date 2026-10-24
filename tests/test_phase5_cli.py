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


def test_start_command_creates_plan_without_model(tmp_path):
    result = runner.invoke(cli, ["start", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Created a plan for: Build a snake game" in result.stdout
    saved = memory.load_plan(str(tmp_path))
    assert saved is not None
    assert "Build a snake game" in saved


def test_start_command_supports_slash_alias(tmp_path):
    result = runner.invoke(cli, ["/start", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Created a plan for: Build a snake game" in result.stdout


def test_start_command_uses_configured_work_mode(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('work_mode = "mentor"\n', encoding="utf-8")

    captured = {}

    def fake_cmd_start(goal, workspace, llm=None, **kwargs):
        captured["mode"] = kwargs["work_mode"]
        return f"mode={kwargs['work_mode']} goal={goal}"

    monkeypatch.setattr("app.main._cmd_start", fake_cmd_start)

    result = runner.invoke(cli, ["start", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["mode"] == "mentor"
    assert "mode=mentor goal=Build a snake game" in result.stdout


def test_start_command_mode_option_overrides_config(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('work_mode = "builder"\n', encoding="utf-8")

    captured = {}

    def fake_cmd_start(goal, workspace, llm=None, **kwargs):
        captured["mode"] = kwargs["work_mode"]
        return f"mode={kwargs['work_mode']} goal={goal}"

    monkeypatch.setattr("app.main._cmd_start", fake_cmd_start)

    result = runner.invoke(cli, ["start", "--mode", "reviewer", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["mode"] == "reviewer"
    assert "mode=reviewer goal=Build a snake game" in result.stdout


def test_start_command_supports_playbook_option(tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = ""\n', encoding="utf-8")
    _write_simple_game_playbook(tmp_path)

    result = runner.invoke(cli, ["start", "--playbook", "simple-game", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Using playbook: simple-game" in result.stdout
    assert "Created a plan for: Build a snake game" in result.stdout


def test_start_command_supports_slash_alias_with_playbook(tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = ""\n', encoding="utf-8")
    _write_simple_game_playbook(tmp_path)

    result = runner.invoke(cli, ["/start", "--playbook", "simple-game", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Using playbook: simple-game" in result.stdout


def test_playbooks_command_lists_project_playbooks(tmp_path):
    (tmp_path / "codemitra.toml").write_text("work_mode = \"builder\"\n", encoding="utf-8")
    _write_simple_game_playbook(tmp_path)

    result = runner.invoke(cli, ["playbooks", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "simple-game" in result.stdout
    assert "React or browser game" in result.stdout


def test_next_command_uses_command_layer(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = "qwen3:8b"\n', encoding="utf-8")
    captured = {}

    def fake_cmd_next(workspace, llm, **kwargs):
        captured["mode"] = kwargs["work_mode"]
        return "Executed next step."

    monkeypatch.setattr("app.main._cmd_next", fake_cmd_next)
    monkeypatch.setattr("app.main.get_local_llm", lambda *args, **kwargs: SimpleNamespace())

    result = runner.invoke(cli, ["next", "--mode", "architect", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["mode"] == "architect"
    assert "Executed next step." in result.stdout


def test_build_command_uses_command_layer(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = "qwen3:8b"\n', encoding="utf-8")
    captured = {}

    def fake_cmd_build(workspace, llm, **kwargs):
        captured["mode"] = kwargs["work_mode"]
        return "Executed remaining steps."

    monkeypatch.setattr("app.main._cmd_build", fake_cmd_build)
    monkeypatch.setattr("app.main.get_local_llm", lambda *args, **kwargs: SimpleNamespace())

    result = runner.invoke(cli, ["build", "--mode", "product", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["mode"] == "product"
    assert "Executed remaining steps." in result.stdout


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
