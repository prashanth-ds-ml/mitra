"""Core loop (M1): tools, the loop and the plan runner, with a scripted fake model (no Ollama)."""
import json
import pathlib
import sys
import textwrap

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage

from app.core import loop as L
from app.core import tools as T

PASSING_TEST = "def test_add():\n    from calc import add\n    assert add(2, 3) == 5\n"


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(PASSING_TEST, encoding="utf-8")
    w = T.Workspace(tmp_path, test_command="python -m pytest -q tests")
    w.spill_dir = tmp_path / ".mitra" / "out"
    return w


def call(name, n, **args):
    return {"name": name, "args": args, "id": f"c{n}"}


class Scripted:
    """A fake model that replies from a script: AIMessage, or an Exception to raise."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        if not self.replies:
            return AIMessage(content="")
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def tool_msg(*calls, text=""):
    return AIMessage(content=text, tool_calls=list(calls))


# ── tools ────────────────────────────────────────────────────────────────────

def test_paths_stay_inside_the_workspace(ws):
    with pytest.raises(T.ToolError, match="outside"):
        T.read_file(ws, "../secret.txt")
    with pytest.raises(T.ToolError, match="relative"):
        T.read_file(ws, str(ws.root / "x.py"))


def test_repeated_workspace_name_is_not_nested(ws):
    T.write_file(ws, f"{ws.root.name}/calc.py", "x = 1\n")
    assert (ws.root / "calc.py").exists()


def test_tests_are_read_only(ws):
    with pytest.raises(T.ToolError, match="read-only"):
        T.write_file(ws, "tests/test_calc.py", "")


def test_edit_needs_a_read_first_and_an_unchanged_file(ws):
    T.write_file(ws, "calc.py", "def add(a, b):\n    return a - b\n")
    ws.seen.clear()
    with pytest.raises(T.ToolError, match="before editing"):
        T.edit_file(ws, "calc.py", "a - b", "a + b")
    T.read_file(ws, "calc.py")
    (ws.root / "calc.py").write_text("changed by someone\n", encoding="utf-8")
    import os
    os.utime(ws.root / "calc.py", (1, 1))
    with pytest.raises(T.ToolError, match="changed since"):
        T.edit_file(ws, "calc.py", "x", "y")


def test_edit_is_forgiving_about_indentation(ws):
    T.write_file(ws, "calc.py", "def add(a, b):\n    return a - b\n")
    T.read_file(ws, "calc.py")
    T.edit_file(ws, "calc.py", "return a - b", "return a + b")
    assert "return a + b" in (ws.root / "calc.py").read_text()
    T.edit_file(ws, "calc.py", "def add(a, b):\nreturn a + b", "def add(a, b):\n    return b + a")
    assert (ws.root / "calc.py").read_text() == "def add(a, b):\n    return b + a\n"


def test_existing_file_is_not_overwritten_unread(ws):
    (ws.root / "calc.py").write_text("keep\n", encoding="utf-8")
    with pytest.raises(T.ToolError, match="Read it first"):
        T.write_file(ws, "calc.py", "lost\n")


def test_run_tests_reports_and_spills(ws):
    run = T.run_tests(ws)
    assert not run.passed and pathlib.Path(run.full_path).exists()
    T.write_file(ws, "calc.py", "def add(a, b):\n    return a + b\n")
    assert T.run_tests(ws).passed


# ── the loop ─────────────────────────────────────────────────────────────────

def test_loop_passes_when_the_tests_pass(ws, tmp_path):
    model = Scripted(
        tool_msg(call("list_files", 1)),
        tool_msg(call("write_file", 2, path="calc.py", content="def add(a, b):\n    return a + b\n")),
        tool_msg(call("run_tests", 3)),
    )
    events = []
    res = L.solve("make add work", ws, model, on_event=events.append, record_path=tmp_path / "run.jsonl")
    assert res.status == "passed" and res.steps == 3 and res.changed == ["calc.py"]
    assert res.tests.passed
    kinds = [e.kind for e in events]
    assert "result" in kinds and kinds[-1] == "done"
    rows = [json.loads(line) for line in (tmp_path / "run.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["kind"] == "start" and rows[-1]["kind"] == "end" and rows[-1]["status"] == "passed"
    assert all(r["author"] == "mitra" for r in rows)


def test_finish_with_failing_tests_is_refused_then_fails(ws):
    model = Scripted(*[tool_msg(call("finish", n, summary="done")) for n in range(5)])
    res = L.solve("make add work", ws, model, max_failed_finishes=3)
    assert res.status == "failed" and "finish 3 times" in res.summary and model.calls == 3


def test_tool_mistakes_go_back_to_the_model(ws):
    model = Scripted(
        tool_msg(call("edit_file", 1, path="calc.py", old="x", new="y")),       # file does not exist
        tool_msg(call("write_file", 2, path="tests/test_calc.py", content="")), # tests are read-only
        tool_msg(call("write_file", 3, path="calc.py", content="def add(a, b):\n    return a + b\n")),
        tool_msg(call("run_tests", 4)),
    )
    events = []
    res = L.solve("x", ws, model, on_event=events.append)
    fails = [e.data["output"] for e in events if e.kind == "result" and not e.data["ok"]]
    assert res.status == "passed" and len(fails) == 2 and all(f.startswith("✗") for f in fails)


def test_replies_without_tools_are_nudged_then_stopped(ws):
    model = Scripted(AIMessage(content="I would add the function."), AIMessage(content=""), AIMessage(content="ok"))
    res = L.solve("x", ws, model)
    assert res.status == "stopped" and "stopped using tools" in res.summary and model.calls == 3


def test_repeated_calls_are_stopped(ws):
    model = Scripted(*[tool_msg(call("read_file", n, path="tests/test_calc.py")) for n in range(10)])
    res = L.solve("x", ws, model)
    assert res.status == "stopped" and "kept repeating" in res.summary


def test_model_error_is_retried_once_then_reported(ws):
    model = Scripted(ConnectionError("ollama down"), ConnectionError("still down"))
    res = L.solve("x", ws, model)
    assert res.status == "error" and "Ollama" in res.summary and model.calls == 2


def test_step_limit(ws):
    model = Scripted(*[tool_msg(call("search", n, pattern=f"p{n}")) for n in range(10)])
    res = L.solve("x", ws, model, max_steps=4)
    assert res.status == "stopped" and "Step limit" in res.summary and model.calls == 4


def test_old_tool_output_is_dropped_when_context_fills():
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    msgs = [SystemMessage(content="s"), HumanMessage(content="u")]
    for i in range(12):
        msgs += [AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": f"i{i}"}]),
                 ToolMessage(content="big output " * 100, tool_call_id=f"i{i}")]
    dropped = L._compact(msgs)
    assert dropped == 8 and msgs[-1].content.startswith("big output")


# ── the plan runner ──────────────────────────────────────────────────────────

PLAN = textwrap.dedent("""\
    # Feature: calc

    ## Goal
    A calculator.

    ## Design notes
    - `calc.py` has `add(a, b)`.

    ## Tasks

    ### T1: add
    - Files: `calc.py`
    - Do: write add
    - Done when: `python -m pytest -q tests/test_calc.py` passes
    - Needs: -

    ### T2: sub
    - Files: `calc.py`
    - Do: write sub
    - Done when: `python -m pytest -q tests/test_sub.py` passes
    - Needs: T1
    """)


def test_parse_plan():
    header, tasks = L.parse_plan(PLAN)
    assert [t.id for t in tasks] == ["T1", "T2"]
    assert tasks[0].test_command == "python -m pytest -q tests/test_calc.py" and tasks[1].needs == ["T1"]
    assert "Design notes" in header and "### T1" not in header


def test_plan_runner_does_tasks_in_order_and_skips_when_a_need_failed(ws):
    model = Scripted(
        tool_msg(call("write_file", 1, path="calc.py", content="def add(a, b):\n    return a - b\n")),
        *[tool_msg(call("finish", n, summary="done")) for n in range(2, 6)],
    )
    events = []
    out = L.run_plan(PLAN, ws, model, full_test_command="python -m pytest -q tests", on_event=events.append)
    assert out["tasks"]["T1"]["status"] == "failed" and "T2" not in out["tasks"]
    assert any(e.kind == "note" and "T2 skipped" in e.data["text"] for e in events)
    assert out["final_tests_passed"] is False
