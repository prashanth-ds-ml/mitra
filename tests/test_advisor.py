"""Tests for app.advisor — model recommendation engine."""
from __future__ import annotations

import pathlib
import types

import pytest

from app import advisor


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_model(name: str, size_gib: float, placement: str = "gpu"):
    m = types.SimpleNamespace()
    m.name = name
    m.size_gib = size_gib
    m.size_text = f"{size_gib:.1f}G"
    m.placement = placement
    return m


INVENTORY = [
    _make_model("qwen3:8b",           4.9, "gpu"),
    _make_model("deepseek-r1:8b",     4.9, "gpu"),
    _make_model("qwen2.5-coder:7b",   4.7, "gpu"),
    _make_model("qwen2.5-coder:14b",  9.0, "split"),
    _make_model("llama3.2:3b",        2.0, "gpu"),
]


# ── recommend_models ──────────────────────────────────────────────────────────

class TestRecommendModels:
    def test_returns_recommendations(self):
        recs = advisor.recommend_models(INVENTORY, vram_gib=8.0, ram_gib=24.0)
        assert recs is not None
        assert recs.hardware.vram_gib == 8.0

    def test_chat_pick_is_high_quality(self):
        recs = advisor.recommend_models(INVENTORY, vram_gib=8.0, ram_gib=24.0)
        assert recs.chat is not None
        # qwen3:8b has the highest chat score (9.5) with gpu placement
        assert recs.chat.model.name == "qwen3:8b"

    def test_code_pick_is_coder_model(self):
        recs = advisor.recommend_models(INVENTORY, vram_gib=8.0, ram_gib=24.0)
        assert recs.code is not None
        # qwen2.5-coder:14b has highest code score (9.5) even after split penalty (×0.90 = 8.55)
        # vs qwen2.5-coder:7b gpu (8.5 × 1.0 = 8.5) — so 14b wins
        assert "coder" in recs.code.model.name

    def test_runner_up_different_from_top(self):
        recs = advisor.recommend_models(INVENTORY, vram_gib=8.0, ram_gib=24.0)
        ru = recs.runner_up.get("chat")
        assert ru is None or ru.model.name != recs.chat.model.name

    def test_all_scores_populated(self):
        recs = advisor.recommend_models(INVENTORY, vram_gib=8.0, ram_gib=24.0)
        for role in ("chat", "code", "agent"):
            assert len(recs.all_scores[role]) == len(INVENTORY)

    def test_empty_inventory(self):
        recs = advisor.recommend_models([], vram_gib=8.0, ram_gib=24.0)
        assert recs.chat is None
        assert recs.code is None

    def test_no_gpu_cpu_placement_penalised(self):
        cpu_inventory = [_make_model("qwen3:8b", 4.9, "cpu")]
        recs = advisor.recommend_models(cpu_inventory, vram_gib=None, ram_gib=24.0)
        assert recs.chat is not None
        # CPU multiplier for chat is 0.45, so final should be 9.5 * 0.45 = 4.275
        assert recs.chat.final == pytest.approx(9.5 * 0.45, abs=0.01)


# ── format_recommendations ────────────────────────────────────────────────────

class TestFormatRecommendations:
    def setup_method(self):
        self.recs = advisor.recommend_models(INVENTORY, vram_gib=8.0, ram_gib=24.0, gpu_name="RTX 5050")

    def test_contains_hardware_section(self):
        out = advisor.format_recommendations(self.recs)
        assert "Hardware analysis" in out
        assert "RTX 5050" in out

    def test_contains_recommended_config(self):
        out = advisor.format_recommendations(self.recs)
        assert "Recommended config" in out

    def test_star_emoji_on_top_model(self):
        out = advisor.format_recommendations(self.recs)
        assert "⭐" in out

    def test_already_set_badge(self):
        chat_name = self.recs.chat.model.name
        out = advisor.format_recommendations(self.recs, current_local=chat_name)
        assert "(already set)" in out

    def test_ranked_table_present(self):
        out = advisor.format_recommendations(self.recs)
        assert "Full ranking" in out


# ── apply_to_toml (manual fallback) ──────────────────────────────────────────

class TestApplyToToml:
    def test_creates_new_toml(self, tmp_path):
        ok, msg = advisor.apply_to_toml(str(tmp_path), "qwen3:8b", "qwen2.5-coder:14b")
        assert ok
        content = (tmp_path / "codemitra.toml").read_text()
        assert "qwen3:8b" in content

    def test_updates_existing_local_model(self, tmp_path):
        toml = tmp_path / "codemitra.toml"
        toml.write_text('local_model = "old-model"\n')
        ok, msg = advisor.apply_to_toml(str(tmp_path), "qwen3:8b")
        assert ok
        assert "qwen3:8b" in toml.read_text()
        assert "old-model" not in toml.read_text()

    def test_preserves_other_keys(self, tmp_path):
        toml = tmp_path / "codemitra.toml"
        toml.write_text('workspace = "/my/project"\nlocal_model = "old"\n')
        ok, _ = advisor.apply_to_toml(str(tmp_path), "qwen3:8b")
        assert ok
        content = toml.read_text()
        assert "workspace" in content


# ── get_best_local_model ──────────────────────────────────────────────────────

class TestGetBestLocalModel:
    def test_returns_string(self):
        result = advisor.get_best_local_model(INVENTORY, vram_gib=8.0, ram_gib=24.0)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_returns_none(self):
        result = advisor.get_best_local_model([], vram_gib=8.0, ram_gib=24.0)
        assert result is None
