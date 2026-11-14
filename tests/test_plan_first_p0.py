"""D-065 P0: the fixes from the 2026-11-10 "where did we last stop" session."""
import pytest

from app import memory
from app.agents.shell import WarningFold
from app.core import tools as T


def test_commands_are_not_stored_or_loaded_as_topics(tmp_path):
    ws = str(tmp_path)
    memory.update_context(ws, "build the brick breaker")
    memory.update_context(ws, "/logs")
    memory.update_context(ws, "!dir")
    text = memory.load_context(ws)
    assert "build the brick breaker" in text and "/logs" not in text and "!dir" not in text
    path = tmp_path / ".codemitra" / "context.md"  # a topic stored by an older CodeMitra is ignored when loaded
    path.write_text(path.read_text(encoding="utf-8") + "- `2026-11-08 01:28` /logs\n", encoding="utf-8")
    assert "/logs" not in memory.load_context(ws)


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "brick-breaker" / "tests").mkdir(parents=True)
    (tmp_path / "brick-breaker" / "plan.md").write_text("# plan\n", encoding="utf-8")
    (tmp_path / "brick-breaker" / "tests" / "test_game.py").write_text("def test_x(): pass\n", encoding="utf-8")
    return T.Workspace(tmp_path)


def test_a_made_up_rooted_path_points_to_the_real_file(ws):
    with pytest.raises(T.ToolError) as err:
        T.read_file(ws, "/logs/brick-breaker/plan.md")
    assert "Did you mean 'brick-breaker/plan.md'?" in str(err.value)
    with pytest.raises(T.ToolError) as err:
        T.read_file(ws, "/logs/brick-breaker/brick-breaker/tests/test_game.py")
    assert "brick-breaker/tests/test_game.py" in str(err.value)


def test_a_wrong_relative_path_finds_the_file_by_name(ws):
    with pytest.raises(T.ToolError) as err:
        T.read_file(ws, "tests/test_game.py")
    assert "brick-breaker/tests/test_game.py" in str(err.value)
    with pytest.raises(T.ToolError) as err:
        T.list_files(ws, "nothing/here")
    assert "list_files" in str(err.value)


def test_an_absolute_path_inside_the_workspace_just_works(ws):
    assert "1 lines" in T.read_file(ws, str(ws.root / "brick-breaker" / "plan.md"))


def test_python_warning_blocks_are_folded_on_screen():
    raw = [
        "C:\\site-packages\\pytest_asyncio\\plugin.py:208: PytestDeprecationWarning: The configuration option "
        "\"asyncio_default_fixture_loop_scope\" is unset.",
        "The event loop scope for asynchronous fixtures will default to the fixture caching scope.",
        "",
        "  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))",
        "============================= test session starts =============================",
        "collected 37 items",
    ]
    fold = WarningFold()
    shown = [s for s in (fold.feed(line) for line in raw) if s is not None]
    assert shown == ["(PytestDeprecationWarning folded · ctrl+o shows it)",
                     "============================= test session starts =============================",
                     "collected 37 items"]


def test_run_command_says_its_rules_up_front():
    from app.core import chat
    spec = next(s for s in chat.TOOL_SPECS if s["name"] == "run_command") if hasattr(chat, "TOOL_SPECS") else None
    if spec is None:
        spec = next(s for s in chat.tool_specs("approve") if s["name"] == "run_command")
    assert "No pipes" in spec["description"] and "python -m pytest" in spec["description"]
