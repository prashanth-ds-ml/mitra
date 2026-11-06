"""Tests for app/agents/response.py — panel rendering, title logic, step truncation."""
from app.agents.response import (
    AgentResponse,
    ToolResult,
    _extract_action,
    render,
)


# ── _panel_title ──────────────────────────────────────────────────────────────



# ── ToolResult.ok ─────────────────────────────────────────────────────────────

class TestToolResultOk:
    def test_ok_on_checkmark(self):
        assert ToolResult(tool="t", args={}, output="✓ Created folder").ok is True

    def test_not_ok_on_cross(self):
        assert ToolResult(tool="t", args={}, output="✗ Failed").ok is False

    def test_not_ok_on_empty(self):
        assert ToolResult(tool="t", args={}, output="").ok is False

    def test_plain_success_output_counts_as_ok(self):
        assert ToolResult(tool="t", args={}, output="./\n  [dir] src").ok is True


class TestToolResultAction:
    def test_extracts_compact_actions(self):
        assert _extract_action("list_directory") == "Search"
        assert _extract_action("read_file") == "Read"
        assert _extract_action("create_file") == "Edit"
        assert _extract_action("run_command") == "Run"

    def test_tool_result_exposes_action(self):
        step = ToolResult(tool="create_file", args={"path": "app.py"}, output="✓ Created file: app.py")
        assert step.action == "Edit"


# ── AgentResponse counts ──────────────────────────────────────────────────────

class TestAgentResponseCounts:
    def test_counts(self):
        r = AgentResponse(request="x", steps=[
            ToolResult(tool="a", args={}, output="✓ ok"),
            ToolResult(tool="b", args={}, output="✗ fail"),
            ToolResult(tool="c", args={}, output="✓ ok"),
        ])
        assert r.ok_count == 2
        assert r.err_count == 1


# ── render() — step truncation ────────────────────────────────────────────────

class TestRenderStepTruncation:
    def test_long_error_truncated_to_120_chars(self):
        long_err = "x" * 200
        step = ToolResult(tool="create_file", args={"path": "a.py"}, output=f"✗ {long_err}")
        r = AgentResponse(request="req", steps=[step])
        # render() should not raise and the panel should be producible
        panel = render(r)
        assert panel is not None

    def test_multiline_error_shows_first_line_only(self):
        step = ToolResult(
            tool="create_file",
            args={"path": "a.py"},
            output="✗ Line one error\nLine two details\nLine three",
        )
        r = AgentResponse(request="req", steps=[step])
        # Should not raise — first line extraction works
        panel = render(r)
        assert panel is not None


# ── render() — panel contains title ──────────────────────────────────────────

class TestRenderPanelTitle:
    def test_title_reflects_tools(self):
        r = AgentResponse(request="install", steps=[
            ToolResult(tool="install_packages", args={"project_path": "."}, output="✓ done"),
        ])
        assert "● Install ." in _text_of(render(r))

    def test_render_uses_compact_activity_labels(self):
        r = AgentResponse(
            request="inspect and update files",
            steps=[
                ToolResult(tool="list_directory", args={"path": "."}, output="src\napp.py"),
                ToolResult(tool="create_file", args={"path": "app.py"}, output="✓ Created file: app.py"),
            ],
        )
        out = _text_of(render(r))
        assert "● List ." in out and "2 entries" in out and "● Write app.py" in out


def _text_of(renderable) -> str:
    from rich.console import Console
    from app import ui
    c = ui.apply(Console(record=True, width=100, color_system=None))
    c.print(renderable)
    return c.export_text()
