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


def test_a_full_harness_stays_under_budget():
    """Learned rules and tool texts are added to the fixed prompt: the most the harness allows must still fit."""
    from app.core import chat, loop, tools
    from app.core import harness as H

    h = H.Harness(rules=["x" * H.MAX_RULE_CHARS] * H.MAX_RULES)
    for name, specs, prompt in [("chat", chat.tool_specs("approve"), chat.CHAT_PROMPT),
                                ("solve", tools.TOOL_SPECS, loop.SYSTEM_PROMPT)]:
        h.tools = {s["name"]: "y" * H.MAX_TOOL_CHARS for s in specs}
        h = H._clean(h)
        total = (model_view.estimate_tokens(H.apply_prompt(prompt, h))
                 + model_view.estimate_tokens(model_view._specs_text(H.apply_tools(specs, h))))
        assert total <= model_view.BUDGET_TOKENS, f"{name}: {total} tokens with a full harness"
