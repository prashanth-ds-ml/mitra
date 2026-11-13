"""E-125 (live 2026-11-13, mitra-try): the user pasted a Neon Chomp PRD. Mitra answered with a build outline and
"Should I create all the initial files now?"; the user said yes six times and every decide call asked the same
question again, word for word. Nothing was built."""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C
from app.core import intent
from tests.test_chat_core import tc
from tests.test_phased import Heard

ASKED = ("Alright, let's get this neon game running. I'm scaffolding the folder structure and starting with the maze "
         "module to lock in the layout and reachability logic first. Should I create all the initial files now?")
LIVE_YES = ["yes", "ok start and go ahead", "yes to all go to auto mode", "yes go ahead", "then start mitra"]


def _session(tmp_path, m):
    return C.ChatSession(workspace=tmp_path, llm=m, hooks=__import__("tests.test_chat_core", fromlist=["x"])
                         .fake_hooks()[0])


def _rows(s):
    return [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _msgs(answer, user):
    return [SystemMessage(content=C.PHASED_PROMPT), HumanMessage(content="# Neon Chomp PRD ..."),
            AIMessage(content=answer), HumanMessage(content=user)]


def test_the_live_yes_messages_are_go_aheads():
    assert all(C.is_go_ahead(t) for t in LIVE_YES)
    for t in ("yes but use pytest", "no", "why?", "wait", "not yet", "ok, first explain the maze", "maybe tomorrow",
              "yes, what files?", ""):
        assert not C.is_go_ahead(t), t


def test_the_offer_and_its_phase_are_read_from_the_answer():
    assert C.offered_phase(ASKED)[0] == "make_change"
    assert C.offered_phase("Would you like me to search the web for the latest version?")[0] == "look_up"
    assert C.offered_phase("Want me to read game.py and check how scoring works?")[0] == "look_at_code"
    assert C.offered_phase("Shall I write a short plan first?")[0] == "propose_plan"
    assert C.offered_phase("Goal: ...\n1. maze.py\n2. game.py\nShall I build it?")[0] == "make_change"
    assert C.offered_phase("What do you think: the game or the web app?") is None
    assert C.offered_phase("Done: the maze loads. Tests pass.") is None


def test_yes_after_an_offer_starts_the_work_with_no_decide_call(tmp_path):
    """Fails without the fix: the decide call talks and asks again."""
    m = Heard(AIMessage(content="", tool_calls=[tc("write_file", 1, path="maze.py", content="GRID = []\n")]),
              AIMessage(content="Created maze.py (maze.py:1). Untested: there are no tests yet."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs(ASKED, "yes to all go to auto mode"))
    assert (tmp_path / "maze.py").exists()
    assert "write_file" in m.offered[0] and "make_change" not in m.offered[0]  # straight into the change phase
    assert "yes to what you offered" in m.heard[0][-1] and C.DECIDE_NOTE not in m.heard[0]
    assert [r for r in _rows(s) if r["kind"] == "phase"][0]["go_ahead"] is True
    assert res.text.startswith("Created maze.py")


def test_a_repeated_answer_gets_one_more_decide_call_told_the_users_answer(tmp_path):
    m = Heard(AIMessage(content=ASKED),
              AIMessage(content="No rush. When you are ready, tell me and I'll start with the maze."))
    s = _session(tmp_path, m)
    messages = _msgs(ASKED, "maybe tomorrow")
    res = s.phased(messages)
    assert m.calls == 2 and "maybe tomorrow" in m.heard[1][-1] and "repeated" in m.heard[1][-1]
    assert res.text.startswith("No rush") and not [r for r in _rows(s) if r["kind"] == "phase"]  # no work on a "maybe"
    assert not any("you just repeated" in str(x.content) for x in messages)       # the note is not kept
    assert any(r["kind"] == "repeat" for r in _rows(s))


def test_a_new_answer_is_not_a_repeat(tmp_path):
    m = Heard(AIMessage(content="Sure: the maze is a 21 x 22 grid. Anything else?"))
    s = _session(tmp_path, m)
    s.phased(_msgs(ASKED, "tell me about the maze size"))
    assert m.calls == 1


def test_a_pasted_spec_is_sorted_as_a_build_not_writing():
    prd = "# Neon Chomp: Product Requirements Document\n" + "\n".join(
        f"## Part {i}\n- rule {i}\n- detail {i}" for i in range(1, 8))
    assert intent.classify(prd) == "big"
    assert intent.classify("summarise this:\n" + prd) == "writing"
    assert intent.classify("write a prd for a chat app") == "writing"


def test_the_prompt_says_a_spec_is_planned_and_a_yes_is_acted_on():
    assert "pasted a spec, PRD" in C.PHASED_PROMPT and "Never ask the same question" in C.PHASED_PROMPT
