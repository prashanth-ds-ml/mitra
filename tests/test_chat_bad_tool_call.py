"""E-044: Ollama could not parse a long Qwen3.5 tool call ('XML syntax error ... unexpected EOF'); the turn crashed."""
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C


class ResponseError(Exception):  # same name as ollama._types.ResponseError
    pass


class Model:
    def __init__(self, failures):
        self.failures, self.calls, self.seen = failures, 0, []

    def bind_tools(self, specs):
        return self

    def stream(self, messages):
        self.calls += 1
        self.seen.append(list(messages))
        if self.calls <= self.failures:
            raise ResponseError("XML syntax error on line 173: unexpected EOF (status code: -1)")
        return iter([AIMessage(content="Report done.")])


def _session(tmp_path, model, shown):
    hooks = C.Hooks(stream=lambda chunks, step=1: SimpleNamespace(message=next(iter(chunks)), text="Report done.",
                                                                   stopped=False, printed=True),
                    show=lambda *a: shown.append(a), confirm=lambda *a: True, run_shell=lambda c: ("", True),
                    web_search=lambda q: "", fetch_url=lambda u: "", mcp_find=lambda q: "", mcp_call=lambda *a: "")
    return C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks)


def test_a_cut_off_tool_call_is_retried_with_a_note(tmp_path):
    model, shown = Model(failures=1), []
    res = _session(tmp_path, model, shown).turn([SystemMessage(content="s"), HumanMessage(content="write a report")])
    assert res.text == "Report done." and model.calls == 2
    note = model.seen[1][-1]
    assert isinstance(note, HumanMessage) and "smaller parts" in note.content and "XML syntax error" in note.content
    assert shown and shown[0][0] == "retry" and shown[0][3] is False
    rows = [json.loads(x) for f in (tmp_path / ".mitra" / "runs").glob("chat-*.jsonl")
            for x in f.read_text(encoding="utf-8").splitlines()]
    assert any(r["kind"] == "bad_tool_call" for r in rows)


def test_it_gives_up_after_two_retries(tmp_path):
    model = Model(failures=5)
    with pytest.raises(ResponseError):
        _session(tmp_path, model, []).turn([SystemMessage(content="s"), HumanMessage(content="go")])
    assert model.calls == C.MAX_BAD_TOOL_CALLS + 1


def test_other_errors_are_not_swallowed():
    assert C.is_tool_call_parse_error(ResponseError("XML syntax error on line 1: unexpected EOF"))
    assert not C.is_tool_call_parse_error(ResponseError("model requires more system memory"))
    assert not C.is_tool_call_parse_error(ValueError("XML syntax error"))


def test_the_retry_line_renders_in_the_chat_ui():
    from app import ui
    line = ui.step_line("retry", {}, "tool call cut off (XML syntax error); asking for smaller parts", False)
    assert line is not None
