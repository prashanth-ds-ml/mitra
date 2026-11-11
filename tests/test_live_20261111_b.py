"""The user's live session 2026-11-11 evening (feature list with Mitra): E-102 look-up phase, E-103 Mitra knows
itself, E-104 a correction is a signal, E-105 no false "could not write a summary"."""
from langchain_core.messages import AIMessage

from app.core import chat as C
from app.core import handoff as HO
from app.core import score as S
from app.core import signals as SIG
from tests.test_chat_core import tc
from tests.test_phased import Seen, _msgs, _session


def test_pulling_information_goes_to_the_web_with_only_the_web_tools(tmp_path):
    """E-102: "pull information on self improving coding agents" was answered from memory: no phase had the web."""
    m = Seen(AIMessage(content="", tool_calls=[tc("look_up", 1, what="self-improving coding agents")]),
             AIMessage(content="", tool_calls=[tc("web_search", 2, query="self-improving coding agents")]),
             AIMessage(content="I found Harness² (tunes its harness from runs)."))
    s = _session(tmp_path, m)
    res = s.phased(_msgs("can you pull information on self improving coding agents"))
    assert res.text.startswith("I found") and set(m.offered[1]) == {"web_search", "fetch_url"}
    assert "look_up" in C.PHASED_PROMPT and "look_up" in [p["name"] for p in C.PHASE_SPECS]


def test_a_web_tool_named_in_the_decide_step_picks_the_look_up_phase(tmp_path):
    m = Seen(AIMessage(content="", tool_calls=[tc("web_search", 1, query="x")]), AIMessage(content="Found it."))
    s = _session(tmp_path, m)
    s.phased(_msgs("look up the latest ollama version"))
    assert set(m.offered[1]) == {"web_search", "fetch_url"}


def test_mitra_knows_what_it_already_can_do():
    """E-103: "do you know about you?" -> "no fixed identity"; it proposed features it already has."""
    for prompt in (C.PHASED_PROMPT, C.ONE_PROMPT):
        assert C.ABOUT_MITRA in prompt
    for fact in ("Kaggle", "run the tests", "MCP servers", "skills", "mitra improve", "say which ones you already have"):
        assert fact in C.ABOUT_MITRA


def test_being_corrected_for_not_following_is_a_signal():
    """E-104: the user's own words, which were not caught."""
    prev = "lets continue this upto 15 list ... you need to think as tell me whats your pick with as clean reason"
    assert SIG.is_rephrase(prev, "i said you to pick and tell me with a reason right why are not following that mitra")
    assert SIG.is_rephrase(prev, "you didn't add your pick")
    assert SIG.is_rephrase(prev, "that's not what i asked")
    assert SIG.is_rephrase(prev, "why aren't you following the plan")
    # not corrections
    assert not SIG.is_rephrase(prev, "great add that")
    assert not SIG.is_rephrase(prev, "why are you using pygame for this")


def test_a_report_written_at_start_up_has_no_summary_part(tmp_path):
    """E-105: every start-up report said "the laptop model could not write a summary" although none was tried."""
    text = HO.build(reason="the Kaggle GPU ended while Mitra was closed", workspace=tmp_path, turns=[], laptop="m",
                    summary=None)
    assert "could not write" not in text and "## Summary" not in text
    tried = HO.build(reason="r", workspace=tmp_path, turns=[], laptop="m", summary="")
    assert "could not write a summary" in tried                       # tried and failed: still said


def test_the_lookup_check_needs_a_web_tool(tmp_path):
    case = {"expect": "lookup"}
    assert S.check_behaviour(case, "Self-improving agents learn from RL.", tmp_path, tools=[], changed=[]) \
        == "answered from memory without looking it up"
    assert S.check_behaviour(case, "I found Harness².", tmp_path, tools=["web_search"], changed=[]) == ""


# ── D-074: talk on the laptop, the work on Kaggle ─────────────────────────────────────────────────────────────────

def test_talk_goes_to_the_laptop_only_when_the_whole_conversation_fits():
    from app import backend as B
    assert B.talk_on_laptop(B.REMOTE, "phased", ctx_used=5_200, laptop_ctx=65_536)
    assert not B.talk_on_laptop(B.REMOTE, "phased", ctx_used=60_000, laptop_ctx=65_536)   # grown on Kaggle: stays
    assert not B.talk_on_laptop(B.LAPTOP, "phased", ctx_used=0, laptop_ctx=65_536)        # already on the laptop
    assert not B.talk_on_laptop(B.REMOTE, "one", ctx_used=0, laptop_ctx=65_536)           # only phased decides first


def test_the_decide_call_runs_on_the_laptop_and_the_work_on_the_remote(tmp_path):
    work = Seen(AIMessage(content="", tool_calls=[tc("read_file", 2, path="game.py")]),
                AIMessage(content="It adds one (game.py:2)."))
    talk = Seen(AIMessage(content="", tool_calls=[tc("look_at_code", 1, what="step")]))
    s = _session(tmp_path, work)
    s.backend_kind = "remote"
    res = s.phased(_msgs("what does step do?"), talk_llm=talk, talk_ctx=65_536)
    assert talk.calls == 1 and work.calls == 2 and res.text.startswith("It adds one")
    assert s.llm is work and s.backend_kind == "remote" and s._talk is None              # restored after the turn
    import json
    rows = [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r for r in rows if r["kind"] == "talk_route"][0]["backend"] == "laptop"


def test_plain_talk_never_touches_the_remote(tmp_path):
    work, talk = Seen(), Seen(AIMessage(content="Doing well, thanks! What's on your mind?"))
    s = _session(tmp_path, work)
    s.backend_kind = "remote"
    s.phased(_msgs("good what about you"), talk_llm=talk, talk_ctx=65_536)
    assert talk.calls == 1 and work.calls == 0


def test_the_laptop_talk_model_can_stay_loaded():
    from app.llm import get_local_llm
    assert get_local_llm("qwen3.5:latest", keep_alive="30m", reasoning=False).keep_alive == "30m"
