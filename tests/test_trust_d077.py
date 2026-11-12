"""D-077 Next #1 (make it trustworthy): E-109 the decide step's own query is run, never dropped; E-110 a "confirmed"
or "tests pass" no tool result of the turn backs is flagged; offline is said plainly. From the user's live session
2026-11-11 (BYOP critic: "Confirmed that India's DPDP Rules require compliance by May 2027" after a search that
never ran)."""
import json

from langchain_core.messages import AIMessage, ToolMessage

from app.agents import web
from app.core import chat as C
from app.core import grounding as G
from tests.test_chat_core import Model, fake_hooks, tc
from tests.test_phased import _msgs


class Spy(Model):
    """Scripted model that keeps a copy of the messages it was sent on each call."""

    def __init__(self, *replies):
        super().__init__(*replies)
        self.seen = []

    def stream(self, messages):
        self.seen.append(list(messages))
        yield from super().stream(messages)


def _rows(s):
    return [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _session(tmp_path, m, searched):
    hooks = fake_hooks()[0]
    hooks.web_search = lambda q: (searched.append(q), f"# Web results for '{q}'\n1. DPDP Rules 2025: comply by "
                                                      "13 May 2027")[1]
    return C.ChatSession(workspace=tmp_path, llm=m, hooks=hooks)


# ── E-109 ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_search_asked_for_in_the_decide_step_is_run(tmp_path):
    searched = []
    m = Spy(AIMessage(content="", tool_calls=[tc("web_search", 1, query="DPDP SME compliance deadline")]),
            AIMessage(content="The DPDP Rules give until 13 May 2027 (web results)."))
    s = _session(tmp_path, m, searched)
    res = s.phased(_msgs("do the look_up and then rescore"))
    assert searched == ["DPDP SME compliance deadline"]                       # it ran (it was dropped)
    answer_call = m.seen[-1]
    result = [x for x in answer_call if isinstance(x, ToolMessage) and x.tool_call_id == "c1"][0]
    assert "13 May 2027" in result.content and not result.content.startswith("ok")
    assert [r for r in _rows(s) if r["kind"] == "tool"][0]["from_decide"] is True
    assert res.unverified == []                                               # backed by the search it ran


def test_a_tool_that_changes_files_is_never_run_by_the_switch(tmp_path):
    m = Spy(AIMessage(content="", tool_calls=[tc("edit_file", 1, path="x.py", old="a", new="b")]),
            AIMessage(content="I need to read x.py first."))
    s = _session(tmp_path, m, [])
    s.phased(_msgs("change a to b in x.py"))
    placeholder = [x for x in m.seen[-1] if isinstance(x, ToolMessage) and x.tool_call_id == "c1"][0]
    assert placeholder.content.startswith("Not run yet")                      # never a false "ok"
    assert not [r for r in _rows(s) if r["kind"] == "tool"]


# ── E-110 ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_live_confirmed_claims_are_flagged():
    tools = [("web_search", True, "# Web results for 'Indian tourism market size 2025'\n1. Economy of India ..."),
             ("web_search", True, "# Web results for 'ScrapUncle Recykal'\n1. [arXiv] Anomaly Object Segmentation")]
    answer = ("### What I Could Verify:\n1. **DPDP Act Compliance Deadline**: Confirmed that India's DPDP Rules "
              "require compliance by May 2027.\n5. **Scrap Recycling**: Found that ScrapUncle and Recykal are "
              "established players.")
    claims = G.unbacked(answer, tools)
    assert len(claims) == 2 and "2027" in claims[0] and "ScrapUncle" in claims[1]


def test_a_backed_claim_and_an_honest_nothing_found_are_not_flagged():
    tools = [("web_search", True, "1. DPDP Rules 2025 notified; full compliance by May 2027 for data fiduciaries")]
    assert G.unbacked("I confirmed the DPDP deadline is May 2027.", tools) == []
    assert G.unbacked("I searched but could not confirm the market size.", tools) == []
    assert G.unbacked("I found nothing useful on ScrapUncle.", tools) == []
    assert G.unbacked("Hello! How is your day going?", []) == []


def test_tests_pass_needs_a_passing_run_in_the_turn():
    assert G.unbacked("Done: all tests pass.", []) == ["Done: all tests pass."]
    assert G.unbacked("Done: all tests pass.", [("run_tests", False, "1 failed")]) == ["Done: all tests pass."]
    assert G.unbacked("Done: all tests pass.", [("run_tests", True, "3 passed")]) == []
    assert G.unbacked("2 tests still fail.", []) == []


def test_an_unbacked_claim_is_recorded_and_returned(tmp_path):
    m = Spy(AIMessage(content="Confirmed: the DPDP deadline is May 2027."))
    s = _session(tmp_path, m, [])
    res = s.phased(_msgs("is the deadline May 2027?"))
    assert res.unverified and "2027" in res.unverified[0]
    row = [r for r in _rows(s) if r["kind"] == "grounding"][0]
    assert row["claims"] and row["tools"] == []
    assert "Treat as unverified" in G.warning(res.unverified)


def test_the_coach_sees_an_unverified_claim(tmp_path):
    from app.core import coach
    f = tmp_path / "chat-20261112.jsonl"
    rows = [{"t": 10, "kind": "turn_start", "turn": 1, "user": "rescore with research", "path": "phased"},
            {"t": 11, "kind": "grounding", "turn": 1, "claims": ["Confirmed that the deadline is May 2027."]},
            {"t": 12, "kind": "turn_end", "turn": 1, "text": "Confirmed ...", "seconds": 5}]
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    turn = coach.turns_since([f], 0)[0]
    assert any(fl.startswith("unverified claim: Confirmed") for fl in turn["flags"])


# ── offline ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_offline_web_tools_say_so_at_once(monkeypatch):
    monkeypatch.setattr(web, "is_online", lambda timeout=1.5: False)
    for out in (web.search_web.invoke({"query": "qwen3.5"}), web.fetch_url.invoke({"url": "example.com"})):
        assert out == web.OFFLINE and "offline" in out and "not checked" in out


def test_the_online_check_is_remembered_for_a_while(monkeypatch):
    import socket
    calls = []

    def boom(addr, timeout):
        calls.append(addr)
        raise OSError("no route")

    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(web, "_online_cache", {"t": -1e9, "ok": True})
    assert web.is_online() is False and web.is_online() is False
    assert len(calls) == len(web._PROBES)                                    # asked once, then remembered
