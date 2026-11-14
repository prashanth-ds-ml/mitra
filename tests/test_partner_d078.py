"""D-078 Phase 1: 1b partner basics (must-have 13) and 1c honest self-description (must-have 7). From the user's live
session 2026-11-12: "You're absolutely right!" opened 5 of 10 answers; a "deep dive" was 1 search and 2 pages
("you are still missing some"); asked what it can do, CodeMitra said "I validate changes with tests before applying
them", which is not built yet."""
from langchain_core.messages import AIMessage, ToolMessage

from app.core import chat as C
from app.core import harness as H
from tests.test_chat_core import fake_hooks, tc
from tests.test_phased import _msgs
from tests.test_trust_d077 import Spy


def _session(tmp_path, m):
    return C.ChatSession(workspace=tmp_path, llm=m, hooks=fake_hooks()[0])


# ── 1b: honest, no flattery ────────────────────────────────────────────────────────────────────────────────────

def test_the_prompts_forbid_opening_praise_and_ask_for_its_own_view():
    for prompt in (C.PHASED_PROMPT, C.ONE_PROMPT):
        assert "You're absolutely right" in prompt and "Never open with praise" in prompt
        assert "your own view" in prompt


# ── 1b: a deep dive digs ───────────────────────────────────────────────────────────────────────────────────────

def test_deep_dive_words_are_recognised():
    for said in ("can you do a deep dive into web", "dig deep on this", "do proper research", "go deeper please",
                 "pull all the sources you can", "research this thoroughly"):
        assert C.is_deep(said), said
    for said in ("look up the ollama version", "what is qwen3.5", "hi mitra"):
        assert not C.is_deep(said), said


def test_a_deep_dive_is_told_how_far_it_is_until_it_has_searched_enough(tmp_path):
    m = Spy(AIMessage(content="", tool_calls=[tc("look_up", 1, what="coding assistants")]),
            AIMessage(content="", tool_calls=[tc("web_search", 2, query="ai coding assistant features")]),
            AIMessage(content="", tool_calls=[tc("web_search", 3, query="local coding agent github")]),
            AIMessage(content="", tool_calls=[tc("web_search", 4, query="self improving agent arxiv")]),
            AIMessage(content="Here is what the three searches showed."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("can you do a deep dive into web on must-have features"))
    results = [x.content for x in m.seen[-1] if isinstance(x, ToolMessage) and x.tool_call_id in ("c2", "c3", "c4")]
    assert "1 of 3 searches" in results[0] and "2 of 3 searches" in results[1]
    assert "of 3 searches" not in results[2]                                # enough: no more nudging
    assert res.text.startswith("Here is")


def test_a_deep_dive_gets_the_bigger_budget_and_a_plain_look_up_does_not(tmp_path):
    s = _session(tmp_path, Spy(AIMessage(content="", tool_calls=[tc("look_up", 1, what="x")])))
    s.phased(_msgs("dig deep into local coding agents"))
    assert s.look_budget == H.DEFAULT_LIMITS["deep_max_steps"] > H.DEFAULT_LIMITS["explain_max_steps"]
    s2 = _session(tmp_path, Spy(AIMessage(content="", tool_calls=[tc("look_up", 1, what="x")])))
    s2.phased(_msgs("look up the latest ollama version"))
    assert s2.look_budget == H.DEFAULT_LIMITS["explain_max_steps"]


def test_the_deep_dive_nudge_can_be_switched_off_in_the_harness(tmp_path):
    m = Spy(AIMessage(content="", tool_calls=[tc("look_up", 1, what="x")]),
            AIMessage(content="", tool_calls=[tc("web_search", 2, query="a")]),
            AIMessage(content="Done."))
    s = _session(tmp_path, m)
    s.harness.limits["deep_min_searches"] = 1                               # 1 = off
    s.phased(_msgs("deep dive on a"))
    result = [x.content for x in m.seen[-1] if isinstance(x, ToolMessage) and x.tool_call_id == "c2"][0]
    assert "searches done" not in result


# ── 1c: knows what it cannot do yet ────────────────────────────────────────────────────────────────────────────

def test_about_codemitra_says_what_is_not_built_yet():
    about = C.ABOUT_CODEMITRA
    assert "tests run by themselves" in about.split("Not built yet")[0]        # built (D-078 #2): an ability now
    for gap in ("Wikipedia, GitHub, arXiv, Hugging Face",
                "outside this project folder", "not straight away"):
        assert gap in about, gap
    assert "never claim" in about
