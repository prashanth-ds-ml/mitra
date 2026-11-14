"""D-071 phased: decide first (talk, or pick look / change / plan, with no real tools), then act in that phase with
only its tools. The A/B showed why: with every tool from the first step a 9B built an app from "either X or Y"."""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app import main
from app.core import chat as C
from tests.test_backend_chat import Inputs, harness  # noqa: F401 - the driven chat fixture
from tests.test_chat_core import Model, fake_hooks, tc


class Seen(Model):
    """Scripted model that keeps the tool names offered on each call."""

    def __init__(self, *replies):
        super().__init__(*replies)
        self.offered = []

    def bind_tools(self, specs):
        self.offered.append([s["name"] for s in specs])
        return super().bind_tools(specs)


def _session(tmp_path, m):
    (tmp_path / "game.py").write_text("def step(s):\n    return s + 1\n", encoding="utf-8")
    return C.ChatSession(workspace=tmp_path, llm=m, hooks=fake_hooks()[0])


def _rows(s):
    return [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _msgs(text):
    return [SystemMessage(content=C.PHASED_PROMPT), HumanMessage(content=text)]


def test_talk_is_one_call_with_only_the_phase_switches(tmp_path):
    m = Seen(AIMessage(content="Both are good. What matters more this week: finishing or starting?"))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("either the game or a web app, or a new idea"))
    assert res.text.startswith("Both are good") and m.calls == 1 and res.steps == 1
    assert m.offered == [["look_at_code", "look_up", "make_change", "propose_plan"]]       # no file tools to misuse
    assert [r["path"] for r in _rows(s) if r["kind"] == "turn_start"] == ["phased"]
    assert s.allowed_tools is None and not s.deciding


def test_look_gets_only_read_tools_and_answers_with_the_file(tmp_path):
    m = Seen(AIMessage(content="", tool_calls=[tc("look_at_code", 1, what="how step works")]),
             AIMessage(content="", tool_calls=[tc("read_file", 2, path="game.py")]),
             AIMessage(content="It adds one (game.py:2)."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("how does step work?"))
    assert res.text == "It adds one (game.py:2)." and res.steps == 3
    assert set(m.offered[1]) == {"list_files", "read_file", "search", "run_tests"}
    assert [r["name"] for r in _rows(s) if r["kind"] == "phase"] == ["look_at_code"]


def test_change_gets_the_tools_and_changes_the_file(tmp_path):
    m = Seen(AIMessage(content="", tool_calls=[tc("make_change", 1, what="add two")]),
             AIMessage(content="", tool_calls=[tc("read_file", 2, path="game.py")]),
             AIMessage(content="", tool_calls=[tc("edit_file", 3, path="game.py", old="s + 1", new="s + 2")]),
             AIMessage(content="Changed game.py:2 to add two."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("make step add two"))
    assert "s + 2" in (tmp_path / "game.py").read_text(encoding="utf-8") and res.text.startswith("Changed")
    assert "edit_file" in m.offered[1] and "look_at_code" not in m.offered[1]


def test_plan_is_text_only_and_asks(tmp_path):
    m = Seen(AIMessage(content="", tool_calls=[tc("propose_plan", 1, goal="feedback app")]),
             AIMessage(content="Goal: a feedback app.\n1. db.py ...\nShall I build it?"))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("build the feedback app we discussed"))
    assert res.text.endswith("Shall I build it?") and m.calls == 2 and len(m.offered) == 1  # no tools in the plan


def test_an_empty_answer_after_tools_is_asked_for_once(tmp_path):
    m = Seen(AIMessage(content="", tool_calls=[tc("look_at_code", 1, what="x")]),
             AIMessage(content="", tool_calls=[tc("read_file", 2, path="game.py")]),
             AIMessage(content=""),
             AIMessage(content="It adds one (game.py:2)."))
    s = _session(tmp_path, m)
    messages = _msgs("what does step do?")
    res = s.phased(messages)
    assert res.text == "It adds one (game.py:2)." and any(r["kind"] == "empty_answer" for r in _rows(s))
    assert C.EMPTY_ANSWER_NOTE not in [x.content for x in messages]                # taken out after


def test_a_real_tool_name_in_the_decide_step_picks_its_phase(tmp_path):
    m = Seen(AIMessage(content="", tool_calls=[tc("read_file", 1, path="game.py")]),
             AIMessage(content="It adds one (game.py:2)."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("what does step do?"))
    assert res.text.startswith("It adds one") and "read_file" in m.offered[1]


def test_phased_in_the_real_chat_loop(harness):  # noqa: F811
    state, ws = harness
    (ws / "codemitra.toml").write_text('architecture = "phased"\n', encoding="utf-8")
    Inputs.script = ["hi mitra", "where did we stop", "exit"]
    main._chat()
    rows = [json.loads(x) for f in (ws / ".codemitra" / "runs").glob("chat-*.jsonl")
            for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r["path"] for r in rows if r["kind"] == "turn_start"] == ["phased", "resume_brief"]


class Heard(Seen):
    """Also keeps the messages each call received (what the model actually saw)."""

    def __init__(self, *replies):
        super().__init__(*replies)
        self.heard = []

    def stream(self, messages):
        self.heard.append([m.content for m in messages])
        return super().stream(messages)


def test_the_decide_call_gets_the_talk_reminder_next_to_the_message_and_it_is_taken_out(tmp_path):
    """E-101 (B2, B3): the small-talk and ask-back rules only in the system prompt were forgotten by a 9B."""
    m = Heard(AIMessage(content="Doing well, thanks! Anything on your mind?"))
    s = _session(tmp_path, m)
    messages = _msgs("good what about you")
    s.phased(messages)
    assert m.heard[0][-2:] == [C.DECIDE_NOTE, "good what about you"]         # right before the message
    assert C.DECIDE_NOTE not in [x.content for x in messages]                # not kept in the history


def test_the_act_phase_does_not_get_the_talk_reminder(tmp_path):
    m = Heard(AIMessage(content="", tool_calls=[tc("look_at_code", 1, what="step")]),
              AIMessage(content="It adds one (game.py:2)."))
    s = _session(tmp_path, m)
    s.phased(_msgs("what does step do?"))
    assert C.DECIDE_NOTE in m.heard[0] and C.DECIDE_NOTE not in m.heard[1]


def test_ideas_about_the_project_code_are_sent_to_look_first():
    """E-101 (I1): 'brainstorming is conversation' made it brainstorm about the snake game without reading it."""
    assert "ideas or opinions about\nthis project's code" in C.PHASED_PROMPT
    assert "Asked for ideas: 3-5 options" in C.PHASES["look_at_code"]["note"]
    assert "keeps every name, number and date" in C.PHASED_PROMPT
