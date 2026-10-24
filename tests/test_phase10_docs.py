"""Tests for the Phase 10 demo pack documentation."""

from __future__ import annotations

import pathlib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# local-codex's own docs moved to docs/archive/local-codex when the code was imported into Mitra
UPSTREAM_DOCS = REPO_ROOT / "docs" / "archive" / "local-codex"
DEMO_ROOT = UPSTREAM_DOCS / "demo_flows"


def test_phase10_demo_packs_exist():
    packs = {
        "snake_game_react",
        "fastapi_ollama_rag",
        "pomodoro_react",
    }
    expected_files = {
        "PRD.md",
        "IMPLEMENTATION_ORDER.md",
        "README.md",
        "session_log.md",
        "decision_journal.md",
    }

    assert DEMO_ROOT.is_dir()
    assert {path.name for path in DEMO_ROOT.iterdir() if path.is_dir()} >= packs
    for pack in packs:
        pack_dir = DEMO_ROOT / pack
        assert pack_dir.is_dir()
        assert {path.name for path in pack_dir.iterdir() if path.is_file()} >= expected_files


def test_phase10_rollout_marks_demo_polish_complete():
    rollout = (UPSTREAM_DOCS / "Phased Rollout.md").read_text(encoding="utf-8")

    assert "Phase 10 (complete)" in rollout
    assert "docs/demo_flows/" in rollout
    assert "Phase 10 close-out rule" in rollout

