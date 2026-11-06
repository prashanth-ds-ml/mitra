"""The chat on the core loop (M1 stage 2), with a scripted model and fake terminal hooks."""
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.core import chat as C

TEST = "def test_add():\n    from calc import add\n    assert add(2, 3) == 5\n"


class Model:
    """Scripted model: .stream() yields one AIMessage per call from the script (also used for the wrap-up)."""

    def __init__(self, *replies):
        self.replies, self.calls, self.tool_names = list(replies), 0, None

    def bind_tools(self, specs):
        self.tool_names = [s["name"] for s in specs]
        return self

    def stream(self, messages):
        self.calls += 1
        reply = self.replies.pop(0) if self.replies else AIMessage(content="All done.")
        yield reply


def fake_hooks(confirm=True, shown=None):
    shown = shown if shown is not None else []

    def stream(chunks):
        msg = None
        for c in chunks:
            msg = c
        return SimpleNamespace(message=msg, text=(msg.content if msg else ""), stopped=False, printed=True)

    return C.Hooks(
        stream=stream,
        show=lambda name, args, out, ok: shown.append((name, ok, out)),
        confirm=lambda title, detail, question: confirm,
        run_shell=lambda cmd: (f"ran {cmd}", True),
        web_search=lambda q: f"# Web results for '{q}'",
        fetch_url=lambda u: f"# page {u}",
        mcp_find=lambda q: "no tools",
        mcp_call=lambda s, t, a: "ok",
    ), shown


def tc(name, n, **args):
    return {"name": name, "args": args, "id": f"c{n}"}


def call(*calls, text=""):
    return AIMessage(content=text, tool_calls=list(calls))


def project(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(TEST, encoding="utf-8")
    return tmp_path


def msgs(text):
    return [SystemMessage(content=C.CHAT_PROMPT), HumanMessage(content=text)]


def test_a_question_is_answered_without_tools(tmp_path):
    hooks, shown = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=Model(AIMessage(content="Snake is a game.")), hooks=hooks)
    res = session.turn(msgs("what is snake?"))
    assert res.text == "Snake is a game." and res.steps == 1 and shown == [] and not res.stopped


def test_it_keeps_working_until_it_answers(tmp_path):
    """The user's 'implement, test, fix, repeat' in one message: several tool rounds, then an answer."""
    project(tmp_path)
    model = Model(
        call(tc("read_file", 1, path="tests/test_calc.py")),
        call(tc("write_file", 2, path="calc.py", content="def add(a, b):\n    return a - b\n")),
        call(tc("run_tests", 3)),
        call(tc("read_file", 4, path="calc.py")),
        call(tc("edit_file", 5, path="calc.py", old="return a - b", new="return a + b")),
        call(tc("run_tests", 6)),
        AIMessage(content="Added calc.add; the test passes."),
    )
    hooks, shown = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="auto")
    res = session.turn(msgs("make the tests pass"))
    assert res.text == "Added calc.add; the test passes." and res.steps == 7
    tests = [ok for name, ok, _ in shown if name == "run_tests"]
    assert tests == [False, True]                       # failed, fixed, passed
    assert (tmp_path / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert [e["path"].endswith("calc.py") for e in res.journal] == [True, True]   # /undo entries


def test_ask_mode_declined_edit_is_not_written(tmp_path):
    model = Model(call(tc("write_file", 1, path="calc.py", content="x = 1\n")), AIMessage(content="ok, not changed"))
    hooks, shown = fake_hooks(confirm=False)
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="approve")
    res = session.turn(msgs("create calc.py"))
    assert not (tmp_path / "calc.py").exists()
    assert shown[0][1] is False and "declined" in shown[0][2]
    assert res.text == "ok, not changed"


def test_plan_mode_has_read_only_tools_and_refuses_writes(tmp_path):
    model = Model(call(tc("write_file", 1, path="calc.py", content="x\n")), AIMessage(content="Here is the plan."))
    hooks, shown = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="plan")
    session.turn(msgs("plan it"))
    assert set(model.tool_names) <= C.READ_ONLY_TOOLS
    assert "plan mode" in shown[0][2] and not (tmp_path / "calc.py").exists()


def test_step_limit_still_gives_an_answer(tmp_path):
    model = Model(*[call(tc("search", n, pattern=f"p{n}")) for n in range(3)])  # then "All done." for the wrap-up
    hooks, _ = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks)
    res = session.turn(msgs("x"), max_steps=3)
    assert res.stopped and "step limit" in res.stop_reason
    assert res.text == "All done." and model.calls == 4    # 3 steps + the wrap-up answer


def test_interrupted_history_is_repaired():
    m = [SystemMessage(content="s"), HumanMessage(content="u"),
         AIMessage(content="", tool_calls=[{"name": "read_file", "args": {}, "id": "a"},
                                           {"name": "search", "args": {}, "id": "b"}]),
         ToolMessage(content="done", tool_call_id="a")]
    assert C.repair_history(m) == 1
    assert [x.tool_call_id for x in m if isinstance(x, ToolMessage)] == ["a", "b"]


def test_run_plan_from_the_chat(tmp_path, monkeypatch):
    project(tmp_path)
    (tmp_path / "plan.md").write_text(
        "# Feature: calc\n\n## Tasks\n\n### T1: add\n- Do: add\n"
        "- Done when: `python -m pytest -q tests/test_calc.py` passes\n- Needs: -\n", encoding="utf-8")
    called = {}

    def fake_run_plan(text, ws, llm, **kw):
        called["tests"] = kw["full_test_command"]
        return {"tasks": {"T1": {"status": "passed", "tests": "1 passed", "summary": "ok"}}, "passed_tasks": 1,
                "total_tasks": 1, "final_tests_passed": True, "final_tests": "1 passed"}

    monkeypatch.setattr(C.core_loop, "run_plan", fake_run_plan)
    model = Model(call(tc("run_plan", 1, plan_path="plan.md")), AIMessage(content="Plan built: 1/1 tasks."))
    hooks, shown = fake_hooks(confirm=True)
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="approve")
    res = session.turn(msgs("follow plan.md and complete it"))
    assert called["tests"] == "python -m pytest -q"
    assert shown[0][0] == "run_plan" and shown[0][1] is True and "1/1 tasks passed" in shown[0][2]
    assert res.text == "Plan built: 1/1 tasks."
