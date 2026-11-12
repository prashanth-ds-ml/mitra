"""D-078 #2 (must-have 5): after a step that changes code, Mitra runs the project's tests itself and the model sees
the result; on failure it gets the failures and a round count, and after `auto_test_rounds` failing rounds it is told
to stop and say what still fails. A project without tests: "untested, say so"."""
import json

from langchain_core.messages import AIMessage, HumanMessage

from app.core import chat as C
from app.core import tools as T
from tests.test_chat_core import fake_hooks, tc
from tests.test_phased import _msgs
from tests.test_trust_d077 import Spy


def _project(tmp_path, body="def add(a, b):\n    return a - b\n"):
    (tmp_path / "calc.py").write_text(body, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(
        "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parents[1]))\nfrom calc import add\n\n\n"
        "def test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")


def _session(tmp_path, m):
    return C.ChatSession(workspace=tmp_path, llm=m, hooks=fake_hooks()[0])


def _notes(m):
    return [x.content for x in m.seen[-1] if isinstance(x, HumanMessage) and "tests ran after your change" in x.content
            or isinstance(x, HumanMessage) and "has no tests" in x.content]


def test_the_tests_run_after_a_fix_and_the_model_sees_they_pass(tmp_path):
    _project(tmp_path)
    m = Spy(AIMessage(content="", tool_calls=[tc("make_change", 1, what="fix add")]),
            AIMessage(content="", tool_calls=[tc("read_file", 2, path="calc.py")]),
            AIMessage(content="", tool_calls=[tc("edit_file", 3, path="calc.py", old="a - b", new="a + b")]),
            AIMessage(content="Fixed add in calc.py:2; all tests pass."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("fix add in calc.py, it subtracts"))
    assert any("passed" in n for n in _notes(m))
    assert res.tests_run == 1 and res.last_test_ok is True
    assert res.unverified == []                                     # "all tests pass" is backed by the run
    rows = [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r for r in rows if r["kind"] == "tool" and r["name"] == "run_tests"][0]["after_change"] is True


def test_a_failing_change_gets_the_failures_and_a_round_count(tmp_path):
    _project(tmp_path)
    m = Spy(AIMessage(content="", tool_calls=[tc("make_change", 1, what="change add")]),
            AIMessage(content="", tool_calls=[tc("read_file", 2, path="calc.py")]),
            AIMessage(content="", tool_calls=[tc("edit_file", 3, path="calc.py", old="a - b", new="a * b")]),
            AIMessage(content="I changed add; the test still fails."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("change add in calc.py"))
    note = [n for n in _notes(m) if "failed" in n][0]
    assert "Round 1 of 3" in note and "test_add" in note
    assert res.last_test_ok is False


def test_after_the_last_failing_round_it_is_told_to_stop(tmp_path):
    _project(tmp_path)
    s = _session(tmp_path, Spy())
    s._run = lambda name, args, plan: ("1 failed in 0.1s", False)
    res = C.TurnResult()
    notes = [s._test_after_change(res, 1) for _ in range(3)]
    assert "Round 1 of 3" in notes[0] and "Round 2 of 3" in notes[1]
    assert "Stop changing code" in notes[2] and res.tests_run == 3


def test_a_project_without_tests_is_called_untested_once(tmp_path):
    (tmp_path / "calc.py").write_text("x = 1\n", encoding="utf-8")
    s = _session(tmp_path, Spy())
    assert "has no tests" in s._test_after_change(C.TurnResult(), 1)
    assert s._test_after_change(C.TurnResult(), 1) == ""            # said once per turn


def test_notes_and_docs_do_not_trigger_a_test_run(tmp_path):
    _project(tmp_path)
    (tmp_path / "notes.md").write_text("old\n", encoding="utf-8")
    m = Spy(AIMessage(content="", tool_calls=[tc("make_change", 1, what="note")]),
            AIMessage(content="", tool_calls=[tc("read_file", 2, path="notes.md")]),
            AIMessage(content="", tool_calls=[tc("edit_file", 3, path="notes.md", old="old", new="new")]),
            AIMessage(content="Updated notes.md."))
    res = _session(tmp_path, m).phased(_msgs("update notes.md"))
    assert res.tests_run == 0


def test_the_switch_turns_it_off(tmp_path):
    _project(tmp_path)
    s = _session(tmp_path, Spy())
    s.harness.limits["auto_test_rounds"] = 1
    assert s._test_after_change(C.TurnResult(), 1) == ""


def test_has_tests_finds_pytest_files_and_skips_venvs(tmp_path):
    assert not T.has_tests(tmp_path)
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "test_x.py").write_text("", encoding="utf-8")
    assert not T.has_tests(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "thing_test.py").write_text("", encoding="utf-8")
    assert T.has_tests(tmp_path)


# ── D-078 #3: no "done" without a passing test ─────────────────────────────────────────────────────────────────

def test_done_after_a_change_needs_a_passing_test_in_the_turn():
    from app.core import grounding as G
    assert G.unbacked("Done! I fixed the bug.", [], changed=True)
    assert G.unbacked("Done! I fixed the bug.", [("run_tests", False, "1 failed")], changed=True)
    assert G.unbacked("Done! I fixed the bug.", [("run_tests", True, "3 passed")], changed=True) == []
    assert G.unbacked("Done, but it is untested: this project has no tests.", [], changed=True) == []
    assert G.unbacked("Done! Anything else?", [], changed=False) == []          # talk: nothing was changed


def test_a_fix_that_still_fails_but_says_fixed_is_flagged(tmp_path):
    _project(tmp_path)
    m = Spy(AIMessage(content="", tool_calls=[tc("make_change", 1, what="change add")]),
            AIMessage(content="", tool_calls=[tc("read_file", 2, path="calc.py")]),
            AIMessage(content="", tool_calls=[tc("edit_file", 3, path="calc.py", old="a - b", new="a * b")]),
            AIMessage(content="Fixed: add works now."))
    res = _session(tmp_path, m).phased(_msgs("fix add in calc.py"))
    assert res.unverified and "Fixed" in res.unverified[0]


# ── D-078 #4: no accidental whole-file overwrite ───────────────────────────────────────────────────────────────

def test_write_file_refuses_to_shrink_a_big_file_to_a_fragment(tmp_path):
    import pytest
    ws = T.Workspace(tmp_path)
    big = "".join(f"line {i}\n" for i in range(40))
    (tmp_path / "game.py").write_text(big, encoding="utf-8")
    T.read_file(ws, "game.py")
    with pytest.raises(T.ToolError, match="edit_file"):
        T.write_file(ws, "game.py", "def main():\n    pass\n")
    assert (tmp_path / "game.py").read_text(encoding="utf-8") == big          # nothing lost
    T.write_file(ws, "game.py", big + "line 40\n")                             # a full rewrite is still allowed
    (tmp_path / "small.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    T.read_file(ws, "small.py")
    T.write_file(ws, "small.py", "x = 3\n")                                    # small files: fine


# ── E-114: a look phase hands over to the change phase ─────────────────────────────────────────────────────────

def test_looking_first_then_changing_works_in_one_turn(tmp_path):
    """Phase 1 score, B9: "make the snake start 4 cells long" -> look_at_code, found line 13, called make_change
    inside the look phase, was told it is not available, and answered "I can't directly edit files"."""
    _project(tmp_path)
    m = Spy(AIMessage(content="", tool_calls=[tc("look_at_code", 1, what="where add is")]),
            AIMessage(content="", tool_calls=[tc("read_file", 2, path="calc.py")]),
            AIMessage(content="", tool_calls=[tc("make_change", 3, what="add, not subtract")]),
            AIMessage(content="", tool_calls=[tc("edit_file", 4, path="calc.py", old="a - b", new="a + b")]),
            AIMessage(content="Changed calc.py:2 to add; the test passes."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("make add in calc.py add instead of subtract"))
    assert (tmp_path / "calc.py").read_text(encoding="utf-8").endswith("return a + b\n")
    assert res.tests_run == 1 and res.last_test_ok is True and res.unverified == []
    assert res.text.startswith("Changed calc.py:2") and s.last_phase == "make_change"
    rows = [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r["name"] for r in rows if r["kind"] == "phase"] == ["look_at_code", "make_change"]
    assert res.steps == 5


def test_a_phase_cannot_switch_to_one_that_is_not_next(tmp_path):
    _project(tmp_path)
    m = Spy(AIMessage(content="", tool_calls=[tc("look_up", 1, what="x")]),
            AIMessage(content="", tool_calls=[tc("propose_plan", 2, goal="x")]),
            AIMessage(content="Here is what I found."))
    s = _session(tmp_path, m)
    s.phased(_msgs("look up x"))
    assert s.last_phase == "look_up"                       # look_up -> propose_plan is not a hand-over
