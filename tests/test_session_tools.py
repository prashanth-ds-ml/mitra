"""A1 append_file, A2 check_code (+ automatic after .py writes), A3 run_tests(path/keyword), E4 crash hint."""
import pytest

from app.core import loop as L
from app.core import tools as T


def _ws(tmp_path, **kw):
    return T.Workspace(tmp_path, read_only=(), **kw)


def test_append_file_adds_to_a_written_file_and_needs_a_read_first(tmp_path):
    ws = _ws(tmp_path)
    T.write_file(ws, "game.py", "a = 1\n")
    assert T.append_file(ws, "game.py", "b = 2\nc = 3\n").startswith("Appended 2 lines to game.py (now 3 lines)")
    assert (tmp_path / "game.py").read_text(encoding="utf-8") == "a = 1\nb = 2\nc = 3\n"
    (tmp_path / "other.py").write_text("x = 1", encoding="utf-8")
    with pytest.raises(T.ToolError, match="Read"):
        T.append_file(ws, "other.py", "y = 2")
    with pytest.raises(T.ToolError, match="does not exist"):
        T.append_file(ws, "missing.py", "z")


def test_append_file_respects_read_only_tests_and_undo_journal(tmp_path):
    ws = T.Workspace(tmp_path, read_only=("tests",))
    ws.journal = []
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("x", encoding="utf-8")
    T.read_file(ws, "tests/test_a.py")
    with pytest.raises(T.ToolError, match="read-only"):
        T.append_file(ws, "tests/test_a.py", "y")
    T.write_file(ws, "a.py", "1\n")
    T.append_file(ws, "a.py", "2\n")
    assert ws.journal[-1]["before"] == "1\n" and T.rollback(ws.journal[-1:]) == 1
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "1\n"


def test_writing_python_with_an_undefined_name_warns_at_once(tmp_path):
    ws = _ws(tmp_path)
    out = T.write_file(ws, "g.py", "def draw():\n    for b in bricks:\n        print(b)\n")
    assert "will likely fail when it runs" in out and "line 2: undefined name 'bricks'" in out
    clean = T.write_file(ws, "h.py", "import os\nprint(os.name)\n")
    assert "⚠" not in clean  # unused imports and style are not reported: only run-time errors


def test_check_code_finds_unbound_locals_across_files_and_skips_venvs(tmp_path):
    ws = _ws(tmp_path)
    (tmp_path / "a.py").write_text("score = 0\ndef hit():\n    score += 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("print(undefined_thing)\n", encoding="utf-8")
    out = T.check_code(ws, ".")
    assert "a.py: line 3" in out and "score" in out and "junk.py" not in out
    assert T.check_code(ws, "b.py").startswith("✓ No run-time errors")


def test_crash_hint_names_the_project_line_and_error():
    out = ('Traceback (most recent call last):\n  File "C:\\\\venv\\\\Lib\\\\site-packages\\\\pygame\\\\x.py", line 9, in f\n'
           '  File "C:\\\\proj\\\\brick_breaker.py", line 185, in update\n    lives -= 1\n'
           "UnboundLocalError: local variable 'lives' referenced before assignment\n")
    hint = T.crash_hint(out)
    assert "brick_breaker.py line 185" in hint and "UnboundLocalError" in hint and "check_code" in hint
    assert T.crash_hint("exit code 1, no traceback") == ""


def test_run_tests_can_target_a_file_and_keyword(tmp_path):
    ws = _ws(tmp_path, test_command="python -m pytest -q")
    (tmp_path / "test_a.py").write_text("def test_one():\n    assert True\ndef test_two():\n    assert False\n",
                                        encoding="utf-8")
    (tmp_path / "test_b.py").write_text("def test_b():\n    assert False\n", encoding="utf-8")
    out, run = L.run_tool(ws, "run_tests", {"path": "test_a.py", "keyword": "one"})
    assert run.passed and out.startswith("PASSED (test_a.py -k one)")
    out, run = L.run_tool(ws, "run_tests", {"path": "test_a.py", "first_failure": True})
    assert not run.passed and "-x --tb=long" in out
    out, _ = L.run_tool(ws, "run_tests", {"path": "../outside.py"})
    assert out.startswith("✗") and "outside" in out


def test_new_tools_are_dispatched_and_listed():
    names = {s["name"] for s in T.TOOL_SPECS}
    assert {"append_file", "check_code"} <= names
    run_spec = next(s for s in T.TOOL_SPECS if s["name"] == "run_tests")
    assert set(run_spec["parameters"]["properties"]) == {"path", "keyword", "first_failure"}
