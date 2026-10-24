import pathlib
import sys
from types import SimpleNamespace

from typer.testing import CliRunner

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import memory
from app.main import cli


runner = CliRunner()


def test_build_idea_llm_prefers_best_local_model(monkeypatch):
    captured = {}

    monkeypatch.setattr("app.main.config.get_local_model_inventory", lambda: ["inventory"])
    monkeypatch.setattr("app.main.config.get_gpu_vram_gib", lambda: 8.0)
    monkeypatch.setattr("app.main.config.get_total_system_memory_gib", lambda: 24.0)
    monkeypatch.setattr("app.main.model_advisor.get_best_local_model", lambda inventory, vram_gib, ram_gib: "qwen3.5:latest")

    def fake_get_local_llm(model, temperature, base_url=None, num_ctx=None, num_gpu=None, num_predict=None):
        captured.update(
            model=model,
            temperature=temperature,
            base_url=base_url,
            num_ctx=num_ctx,
            num_gpu=num_gpu,
            num_predict=num_predict,
        )
        return object()

    monkeypatch.setattr("app.main.get_local_llm", fake_get_local_llm)

    from app.main import _build_idea_llm

    llm = _build_idea_llm({"temperature": 0.1, "num_ctx": 4096, "ollama_local_base_url": "http://localhost:11434"})

    assert llm is not None
    assert captured["model"] == "qwen3.5:latest"
    assert captured["temperature"] == 0.1
    assert captured["base_url"] == "http://localhost:11434"
    assert captured["num_ctx"] == 4096


def test_understand_command_saves_notes(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())
    monkeypatch.setattr("app.main.understand_agent.run", lambda llm, idea, console, project_context="": "# Understand\n\n## Idea\n" + idea + "\n")

    result = runner.invoke(cli, ["understand", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    saved = memory.load_understand(str(tmp_path))
    assert saved is not None
    assert "Build a snake game" in saved


def test_understand_command_passes_workspace_context(monkeypatch, tmp_path):
    (tmp_path / ".codemitra").mkdir()
    (tmp_path / ".codemitra" / "context.md").write_text("# Context\nProject summary\n", encoding="utf-8")
    (tmp_path / ".codemitra" / "brainstorm.md").write_text("# Brainstorm\nIdeas\n", encoding="utf-8")
    (tmp_path / ".codemitra" / "understand.md").write_text("# Understand\nKnown notes\n", encoding="utf-8")
    (tmp_path / "PRD.md").write_text("# Existing PRD\n", encoding="utf-8")
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())

    captured = {}

    def fake_run(llm, idea, console, project_context=""):
        captured["project_context"] = project_context
        return "# Understand\n\n## Idea\n" + idea + "\n"

    monkeypatch.setattr("app.main.understand_agent.run", fake_run)

    result = runner.invoke(cli, ["understand", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Project summary" in captured["project_context"]
    assert "Ideas" in captured["project_context"]
    assert "Known notes" in captured["project_context"]
    assert "Existing PRD" in captured["project_context"]


def test_prd_command_writes_workspace_prd(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())
    monkeypatch.setattr(
        "app.main.prd_flow.generate_markdown",
        lambda llm, **kwargs: "# Snake Game\n\n## Problem\nBuild a snake game.\n",
    )

    result = runner.invoke(cli, ["prd", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    root_prd = tmp_path / "PRD.md"
    memory_prd = tmp_path / ".codemitra" / "prd.md"
    assert root_prd.exists()
    assert memory_prd.exists()
    assert "Build a snake game" in root_prd.read_text(encoding="utf-8")


def test_understand_command_updates_context_memory(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())
    monkeypatch.setattr("app.main.understand_agent.run", lambda llm, idea, console, project_context="": "# Understand\n\n## Idea\n" + idea + "\n")

    result = runner.invoke(cli, ["understand", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    context = (tmp_path / ".codemitra" / "context.md").read_text(encoding="utf-8")
    assert "### Understand" in context
    assert "Build a snake game" in context


def test_prd_command_updates_context_memory(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())
    monkeypatch.setattr(
        "app.main.prd_flow.generate_markdown",
        lambda llm, **kwargs: "# Snake Game\n\n## Problem\nBuild a snake game.\n",
    )

    result = runner.invoke(cli, ["prd", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    context = (tmp_path / ".codemitra" / "context.md").read_text(encoding="utf-8")
    assert "### PRD" in context
    assert "Snake Game" in context


def test_prd_command_includes_workspace_context_in_understanding(monkeypatch, tmp_path):
    (tmp_path / ".codemitra").mkdir()
    (tmp_path / ".codemitra" / "context.md").write_text("# Context\nShared context\n", encoding="utf-8")
    (tmp_path / ".codemitra" / "brainstorm.md").write_text("# Brainstorm\nSaved ideas\n", encoding="utf-8")
    (tmp_path / ".codemitra" / "understand.md").write_text("# Understand\nKnown notes\n", encoding="utf-8")
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())

    captured = {}

    def fake_generate_markdown(llm, **kwargs):
        captured["understanding"] = kwargs["understanding"]
        return "# Snake Game\n\n## Problem\nBuild a snake game.\n"

    monkeypatch.setattr("app.main.prd_flow.generate_markdown", fake_generate_markdown)

    result = runner.invoke(cli, ["prd", "Build a snake game", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "Known notes" in captured["understanding"]
    assert "Shared context" in captured["understanding"]
    assert "Saved ideas" in captured["understanding"]


def test_prd_command_supports_update_request(monkeypatch, tmp_path):
    (tmp_path / ".codemitra").mkdir()
    (tmp_path / ".codemitra" / "understand.md").write_text("# Understand\n\n## Idea\nSnake game\n", encoding="utf-8")
    (tmp_path / ".codemitra" / "prd.md").write_text("# Snake Game\n\n## Problem\nOld content\n", encoding="utf-8")
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())

    captured = {}

    def fake_generate_markdown(llm, **kwargs):
        captured["update_request"] = kwargs.get("update_request")
        return "# Snake Game\n\n## Problem\nUpdated content\n"

    monkeypatch.setattr("app.main.prd_flow.generate_markdown", fake_generate_markdown)

    result = runner.invoke(cli, ["prd", "update shorten the scope", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert captured["update_request"] == "update shorten the scope"
    assert "Updated content" in (tmp_path / "PRD.md").read_text(encoding="utf-8")


def test_slash_aliases_work(monkeypatch, tmp_path):
    monkeypatch.setattr("app.main._build_idea_llm", lambda cfg: SimpleNamespace())
    monkeypatch.setattr("app.main.understand_agent.run", lambda llm, idea, console, project_context="": "# Understand\n\n## Idea\n" + idea + "\n")
    monkeypatch.setattr("app.main.prd_flow.generate_markdown", lambda llm, **kwargs: "# Snake Game\n\n## Problem\nBuild a snake game.\n")

    understand_result = runner.invoke(cli, ["/understand", "Build a snake game", "--cwd", str(tmp_path)])
    prd_result = runner.invoke(cli, ["/prd", "Build a snake game", "--cwd", str(tmp_path)])

    assert understand_result.exit_code == 0
    assert prd_result.exit_code == 0


def test_prd_command_reads_root_prd_first(monkeypatch, tmp_path):
    (tmp_path / ".codemitra").mkdir()
    (tmp_path / "PRD.md").write_text("# Root PRD\n", encoding="utf-8")
    (tmp_path / ".codemitra" / "prd.md").write_text("# Mirror PRD\n", encoding="utf-8")

    assert memory.load_prd(str(tmp_path)) == "# Root PRD\n"
