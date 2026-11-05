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


def test_prd_command_reads_root_prd_first(monkeypatch, tmp_path):
    (tmp_path / ".mitra").mkdir()
    (tmp_path / "PRD.md").write_text("# Root PRD\n", encoding="utf-8")
    (tmp_path / ".mitra" / "prd.md").write_text("# Mirror PRD\n", encoding="utf-8")

    assert memory.load_prd(str(tmp_path)) == "# Root PRD\n"
