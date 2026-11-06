"""CI check: the fixed prompt + tool specs stay under ~3K tokens (SCOPE.md)."""

import importlib.util
import pathlib

_PATH = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "model_view.py"
_spec = importlib.util.spec_from_file_location("model_view", _PATH)
model_view = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(model_view)


def test_estimate_rounds_up():
    assert model_view.estimate_tokens("") == 0
    assert model_view.estimate_tokens("a") == 1
    assert model_view.estimate_tokens("a" * 7) == 2
    assert model_view.estimate_tokens("a" * 8) == 3


def test_views_cover_chat_and_solve():
    totals = model_view.totals()
    assert len(totals) == 2
    assert all(total > 0 for total in totals.values())


def test_chat_and_solve_under_budget():
    totals = model_view.totals()
    over = {name: total for name, total in totals.items() if total > model_view.BUDGET_TOKENS}
    assert not over, f"over the {model_view.BUDGET_TOKENS:,}-token budget: {over}"


def test_render_lists_every_part():
    text = model_view.render()
    assert "estimate" in text.lower()
    for parts in model_view.views().values():
        for part, _ in parts:
            assert part in text
