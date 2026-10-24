import pathlib
import sys
from types import SimpleNamespace

from typer.testing import CliRunner

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import cli


runner = CliRunner()


def test_status_command_supports_canonical_name(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = "qwen3:8b"\n', encoding="utf-8")
    monkeypatch.setattr("app.main.probe_ollama", lambda *_args, **_kwargs: (True, "Connected: 1 local model detected"))

    result = runner.invoke(cli, ["status", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "CodeMitra Status" in result.stdout
    assert "qwen3:8b" in result.stdout


def test_status_command_supports_slash_alias(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = "qwen3:8b"\n', encoding="utf-8")
    monkeypatch.setattr("app.main.probe_ollama", lambda *_args, **_kwargs: (True, "Connected: 1 local model detected"))

    result = runner.invoke(cli, ["/status", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "CodeMitra Status" in result.stdout
    assert "qwen3:8b" in result.stdout


def test_config_command_shows_layers(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('session_mode = "approve"\n', encoding="utf-8")
    result = runner.invoke(cli, ["config", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Config Layers" in result.stdout
    assert "Resolved Settings" in result.stdout


def test_config_command_supports_slash_alias(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('session_mode = "approve"\n', encoding="utf-8")
    result = runner.invoke(cli, ["/config", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Config Layers" in result.stdout
    assert "Resolved Settings" in result.stdout


def test_models_command_supports_slash_alias(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main.probe_ollama", lambda *_args, **_kwargs: (True, "Connected"))
    monkeypatch.setattr(
        "app.main.config.get_local_model_inventory",
        lambda: [SimpleNamespace(name="qwen2.5-coder:14b", size_text="9 GB", placement="gpu", recommended=True)],
    )

    result = runner.invoke(cli, ["/models", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Local Models" in result.stdout
    assert "qwen2.5-coder:14b" in result.stdout


def test_models_command_lists_inventory(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main.probe_ollama", lambda *_args, **_kwargs: (True, "Connected"))
    monkeypatch.setattr(
        "app.main.config.get_local_model_inventory",
        lambda: [SimpleNamespace(name="qwen2.5-coder:14b", size_text="9 GB", placement="gpu", recommended=True)],
    )

    result = runner.invoke(cli, ["models", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Local Models" in result.stdout
    assert "qwen2.5-coder:14b" in result.stdout


def test_status_command_creates_phase0_log(monkeypatch, tmp_path):
    (tmp_path / "codemitra.toml").write_text('local_model = "qwen3:8b"\n', encoding="utf-8")
    monkeypatch.setattr("app.main.probe_ollama", lambda *_args, **_kwargs: (True, "Connected: 1 local model detected"))

    result = runner.invoke(cli, ["status", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    log_path = tmp_path / ".codemitra" / "codemitra.log"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "status command" in log_text
