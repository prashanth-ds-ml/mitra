"""Tests for app/agents/reviewer.py."""

from types import SimpleNamespace

from app.agents import reviewer


class TestReviewerAgent:
    def test_run_returns_summary(self):
        class FakeLLM:
            def invoke(self, messages):
                return SimpleNamespace(content="No material issues found.")

        response = reviewer.run(
            FakeLLM(),
            "Review current changes",
            "diff --git a/app.py b/app.py",
            source="current git diff",
        )

        assert response.source == "current git diff"
        assert response.summary == "No material issues found."

    def test_render_returns_panel(self):
        response = reviewer.ReviewResponse(
            request="Review current changes",
            source="last CodeMitra change set",
            summary="Potential regression in app.py.",
        )
        assert "Potential regression in app.py." in _text_of(reviewer.render(response))


def _text_of(renderable) -> str:
    from rich.console import Console
    from app import ui
    c = ui.apply(Console(record=True, width=100, color_system=None))
    c.print(renderable)
    return c.export_text()
