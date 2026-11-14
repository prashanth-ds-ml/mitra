"""Dashboard step 1 (D-041): full traces of every model call, rebuildable, scrubbed, mirrored."""
import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.core import chat as C
from app.core import loop as L
from app.core import store as S


def _rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_a_growing_history_is_stored_as_deltas_and_rebuilt_exactly(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".codemitra" / "runs" / "chat-1.jsonl")
    tools = [{"name": "read_file", "description": "Read a file."}]
    msgs = [SystemMessage(content="You are CodeMitra." * 200), HumanMessage(content="read a.py")]
    r1 = AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"path": "a.py"}, "id": "c1"}],
                   additional_kwargs={"reasoning_content": "I should read the file first."})
    rec.trace(list(msgs), r1, tools=tools, model="qwen3.5:latest", num_ctx=262144, step=1)
    msgs += [r1, ToolMessage(content="x = 1\n" * 1000, tool_call_id="c1")]
    r2 = AIMessage(content="a.py sets x to 1.")
    rec.trace(list(msgs), r2, tools=tools, model="qwen3.5:latest", num_ctx=262144, step=2)

    rows = _rows(rec.trace_path)
    assert [r["kind"] for r in rows] == ["prompt", "call", "call"]  # the long prompt is saved once
    assert rows[2]["base"] == 1 and len(rows[2]["new"]) == 1  # only the tool result is new (reply is in history)
    calls = L.rebuild_calls(rows)
    assert [m["role"] for m in calls[1]["messages"]] == ["system", "user", "assistant", "tool"]
    assert calls[1]["messages"][0]["content"] == "You are CodeMitra." * 200
    assert calls[1]["messages"][3]["content"] == "x = 1\n" * 1000  # nothing cut
    assert calls[0]["reply"]["thinking"] == "I should read the file first."
    assert calls[1]["reply"]["content"] == "a.py sets x to 1." and calls[1]["tools"] == tools
    assert calls[0]["model"] == "qwen3.5:latest" and calls[0]["num_ctx"] == 262144


def test_a_rewritten_history_is_stored_in_full(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".codemitra" / "runs" / "r.jsonl")
    rec.trace([SystemMessage(content="s"), HumanMessage(content="one")], AIMessage(content="1"))
    rec.trace([SystemMessage(content="s"), HumanMessage(content="summary of before")], AIMessage(content="2"))
    rows = [r for r in _rows(rec.trace_path) if r["kind"] == "call"]
    assert rows[1]["base"] is None and len(rows[1]["new"]) == 2
    assert L.rebuild_calls(_rows(rec.trace_path))[1]["messages"][1]["content"] == "summary of before"


def test_secrets_never_reach_a_trace(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".codemitra" / "runs" / "r.jsonl")
    secret = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    rec.trace([SystemMessage(content="s"), HumanMessage(content=f"token is {secret}")], AIMessage(content="ok"))
    assert secret not in rec.trace_path.read_text(encoding="utf-8")


def test_traces_are_mirrored_but_not_counted_as_run_records(tmp_path):
    from app.core import analyze as A
    rec = L.Recorder(tmp_path / "p" / ".codemitra" / "runs" / "r.jsonl")
    rec.write("start", task="t")
    rec.trace([SystemMessage(content="s"), HumanMessage(content="u")], AIMessage(content="a"))
    assert S.stored_files("traces") and len(S.stored_files()) == 1
    assert all("traces" not in f.parts for f in A.find_run_files([tmp_path]))


def test_traces_off_writes_none(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".codemitra" / "runs" / "r.jsonl", traces=False)
    rec.trace([HumanMessage(content="u")], AIMessage(content="a"))
    assert rec.trace_path is None and not (tmp_path / "p" / ".codemitra" / "runs" / "traces").exists()


def test_a_failing_trace_never_breaks_the_run(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".codemitra" / "runs" / "r.jsonl")
    rec.trace([object()], object())  # garbage in: swallowed


class _Model:
    model = "qwen3.5:4b"

    def __init__(self, replies):
        self.replies = list(replies)

    def bind_tools(self, specs):
        return self

    def stream(self, messages):
        return iter([self.replies.pop(0)])


def _session(tmp_path, model):
    hooks = C.Hooks(stream=lambda chunks, step=1: (lambda m: SimpleNamespace(
                        message=m, text=m.content, stopped=False, printed=True, seconds=0.5,
                        thinking="thought about it"))(next(iter(chunks))),
                    show=lambda *a: None, confirm=lambda *a: True, run_shell=lambda c: ("", True),
                    web_search=lambda q: "", fetch_url=lambda u: "", mcp_find=lambda q: "", mcp_call=lambda *a: "")
    return C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks)


def test_a_chat_turn_writes_a_trace_and_an_outcome(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    model = _Model([AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"path": "a.py"}, "id": "c1"}]),
                    AIMessage(content="x is 1.")])
    session = _session(tmp_path, model)
    session.turn([SystemMessage(content="sys"), HumanMessage(content="what is x")])
    runs = tmp_path / ".codemitra" / "runs"
    trace = next((runs / "traces").glob("chat-*.jsonl"))
    calls = L.rebuild_calls(_rows(trace))
    assert len(calls) == 2 and calls[0]["model"] == "qwen3.5:4b" and calls[0]["turn"] == 1
    assert calls[0]["reply"]["thinking"] == "thought about it"
    assert calls[1]["messages"][-1]["role"] == "tool" and "x = 1" in calls[1]["messages"][-1]["content"]
    end = [r for r in _rows(next(runs.glob("chat-*.jsonl"))) if r["kind"] == "turn_end"]
    assert end[0]["outcome"] == "answered"


def test_turn_outcome_labels():
    R = SimpleNamespace
    assert C.turn_outcome(R(stopped=True, stop_reason="stopped by you (esc)", tests_run=0)) == "stopped_by_user"
    assert C.turn_outcome(R(stopped=True, stop_reason="step limit (30 model calls)", tests_run=0)) == "stopped"
    assert C.turn_outcome(R(stopped=False, stop_reason="", tests_run=2, last_test_ok=True)) == "tests_passed"
    assert C.turn_outcome(R(stopped=False, stop_reason="", tests_run=1, last_test_ok=False)) == "tests_failed"
    assert C.turn_outcome(R(stopped=False, stop_reason="", tests_run=0)) == "answered"
