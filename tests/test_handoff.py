"""D-062 B3: Kaggle ended → laptop, report, stop. The report and the mid-turn detection."""
import json
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.core import chat as C
from app.core import handoff as H
from tests.test_chat_core import Model, call, fake_hooks, msgs, tc


def test_the_report_holds_the_facts_and_the_summary(tmp_path):
    turns = [{"no": 1, "user": "add a score counter", "outcome": "tests_passed",
              "files": [str(tmp_path / "game" / "score.py")]},
             {"no": 2, "user": "now the level screen", "outcome": "kaggle_ended", "files": []}]
    text = H.build(reason="the Kaggle GPU stopped answering", workspace=tmp_path, turns=turns,
                   laptop="qwen3.5:4b at 64K (RAM is short)", summary="- score done\n- level screen half done",
                   last_tests="3 passed", night={"state": "running", "plan": "plan.md", "detail": "40 min of up to 4 h"},
                   kaggle={"session_min": 52, "left_h": 27.3}, now=time.mktime((2026, 11, 10, 15, 4, 0, 0, 0, -1)))
    for needed in ("# Kaggle ended · 2026-11-10 15:04", "the Kaggle GPU stopped answering", "qwen3.5:4b at 64K",
                   "used 52 min", "27.3 h left", "- 1 · add a score counter → ✓ tests passed",
                   "- 2 · now the level screen → cut off: Kaggle ended", "`game/score.py`", "/undo",
                   "**Last test run:** 3 passed", "**Night run:** running · plan.md", "- level screen half done",
                   "/kaggle start"):
        assert needed in text, needed
    path = H.write(tmp_path, text)
    assert path.parent == tmp_path / ".codemitra" / "reports" and path.name.startswith("kaggle-ended-")


def test_no_summary_still_gives_a_complete_report(tmp_path):
    text = H.build(reason="r", workspace=tmp_path, turns=[], laptop="m")
    assert "(no turns recorded)" in text and "the facts above are complete" in text


def test_last_sessions_turns_are_read_from_the_record(tmp_path):
    rec = tmp_path / "chat-20261110.jsonl"
    rows = [{"kind": "session"}, {"kind": "turn_start", "turn": 1, "user": "old session"},
            {"kind": "session"}, {"kind": "turn_start", "turn": 1, "user": "fix the paddle"},
            {"kind": "turn_end", "turn": 1, "outcome": "tests_failed", "changed": ["C:/p/paddle.py"]},
            {"kind": "turn_start", "turn": 2, "user": "try again"}]
    rec.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert H.turns_from_record(rec) == [
        {"no": 1, "user": "fix the paddle", "outcome": "tests_failed", "files": ["C:/p/paddle.py"]},
        {"no": 2, "user": "try again", "outcome": "", "files": []}]


def test_summary_uses_the_transcript_and_survives_a_failure():
    class Echo:
        def invoke(self, prompt):
            assert "USER: make it faster" in prompt[1].content and "CODEMITRA used: edit_file" in prompt[1].content
            return AIMessage(content="- sped up the loop")

    history = [SystemMessage(content="s"), HumanMessage(content="make it faster"),
               AIMessage(content="", tool_calls=[{"name": "edit_file", "args": {}, "id": "1"}]),
               ToolMessage(content="ok", tool_call_id="1")]
    assert H.summarize(Echo(), history) == "- sped up the loop"

    class Broken:
        def invoke(self, prompt):
            raise ConnectionError("no model")

    assert H.summarize(Broken(), history) == ""


class Dropping(Model):
    """A remote model whose connection drops after the first call."""

    def __init__(self, *replies, drop_after=1):
        super().__init__(*replies)
        self.drop_after = drop_after

    def stream(self, messages):
        self.calls += 1
        if self.calls > self.drop_after:
            raise ConnectionError("[WinError 10054] An existing connection was forcibly closed")
        yield self.replies.pop(0)


def test_a_remote_that_drops_mid_turn_ends_the_turn_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(C.time, "sleep", lambda s: None)
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    model = Dropping(call(tc("read_file", 1, path="a.py")))
    hooks, shown = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="auto")
    session.backend_kind = "remote"
    history = msgs("change a.py")
    res = session.turn(history)
    assert res.remote_gone and res.stopped and "stopped answering" in res.stop_reason
    assert model.calls == 3  # the call, then one quick retry, then give up
    assert session.turn_log[-1]["outcome"] == "kaggle_ended"
    assert isinstance(history[-1], ToolMessage)  # the chat history stays valid for the laptop model
    rows = [json.loads(line) for f in (tmp_path / ".codemitra" / "runs").glob("chat-*.jsonl")
            for line in f.read_text(encoding="utf-8").splitlines()]
    assert any(r.get("kind") == "turn_end" and r.get("outcome") == "kaggle_ended" for r in rows)


def test_cloudflare_errors_count_as_the_remote_gone():
    class ResponseError(Exception):
        status_code = 530

    assert C.is_remote_down(ResponseError("error code: 1033"))
    assert C.is_remote_down(OSError("getaddrinfo failed"))
    assert not C.is_remote_down(ValueError("XML syntax error"))


def test_every_turn_is_logged_for_the_report(tmp_path):
    hooks, _ = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=Model(AIMessage(content="hi")), hooks=hooks)
    session.turn(msgs("hello there"))
    assert session.turn_log == [{"no": 1, "user": "hello there", "outcome": "answered", "files": []}]
