"""E-126 (live 2026-11-13 20:38-23:11, mitra-try, 22 turns building Neon Chomp on d7f9bc1). Every case here is a
real turn of that session: change requests landed in the read-only look phase and Mitra told the user to edit by
hand (5 turns); brick-breaker's tests stood in for neon_chomp's ("37 passed"); "fixed" / "running successfully"
with nothing changed or tests failing; drift to brick-breaker; a 524 ended the turn as "Kaggle ended"; and the
E-125 go-ahead never fired because the questions were in bold."""
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C
from app.core import grounding as G
from app.core import tools as T
from tests.test_chat_core import fake_hooks, tc
from tests.test_phased import Heard

TEST_OK = "def test_ok():\n    assert True\n"


def _two_projects(tmp_path):
    """mitra-try's shape: brick-breaker/ has tests, neon_chomp/ is new."""
    (tmp_path / "brick-breaker" / "tests").mkdir(parents=True)
    (tmp_path / "brick-breaker" / "tests" / "test_game.py").write_text(TEST_OK, encoding="utf-8")
    (tmp_path / "neon_chomp").mkdir()
    (tmp_path / "neon_chomp" / "maze.py").write_text("PELLETS = 215\n", encoding="utf-8")
    return tmp_path


def _session(ws, m):
    return C.ChatSession(workspace=ws, llm=m, hooks=fake_hooks()[0])


def _rows(s):
    return [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _msgs(*turns):
    out = [SystemMessage(content=C.PHASED_PROMPT)]
    for i, t in enumerate(turns):
        out.append((HumanMessage if i % 2 == 0 else AIMessage)(content=t))
    return out


# ── 4. the E-125 go-ahead: the live answers' last lines ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("tail, phase", [
    ("acceptance criteria\n\n---\n\n**Should I start building now?** If yes, I'll create the initial project structure "
     "and begin with the maze loader.", "make_change"),                                                    # turn 4
    ("I should fix the remaining issues.\n\n**Should I continue with Phase 2 (AI & Game Logic) now?**", "make_change"),
    ("4. **Tune difficulty values** and polish\n\n**Should I continue with visuals and audio next?**", "make_change"),
    ("2. **Run tests**\n3. **Launch game**\n\n---\n\n**Shall I proceed with this plan?**", "make_change"),   # turn 20
    ("Shall I write a short plan first?", "propose_plan"),
    ("Would you like me to continue debugging and fixing these issues, or would you prefer to take a break and "
     "review the code together?", None),                                                                   # turn 8
    ("**Would you like me to help fix the test file issues next, or should we focus on getting brick-breaker "
     "launched first?**", None),                                                                           # turn 12
    ("Let me run the tests again to see if they all pass now:", None),                                      # turn 9
])
def test_the_live_offers_are_read_through_the_bold(tail, phase):
    got = C.offered_phase(tail)
    assert (got[0] if got else None) == phase


def test_yes_after_a_bold_offer_starts_the_work(tmp_path):
    """Fails without the fix: '**Should I start building now?** If yes, ...' was not seen as an offer."""
    m = Heard(AIMessage(content="", tool_calls=[tc("write_file", 1, path="maze.py", content="GRID = []\n")]),
              AIMessage(content="Created maze.py. Untested: no tests yet."))
    s = _session(tmp_path, m)
    s.phased(_msgs("check this and plan first", "## Build Plan\n1. maze\n\n**Should I start building now?** If yes, "
                   "I'll create the initial project structure.", "yes"))
    assert (tmp_path / "maze.py").exists() and "write_file" in m.offered[0]


# ── 1. a change request stays a change ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, change", [
    ("go a head and complete all the required things", True),                                              # turn 9
    ("review this neon chomp code and fix the issues and bugs", True),                                     # turn 10
    ("you check and fix test and tell me how to launch the game ", True),                                  # turn 11
    ("yes please do so i can launch the game ", True),                                                     # turn 12
    ("why dont you do that", True),                                                                        # turn 16
    ("write the plan , write test and do the final fix", True),                                            # turn 19
    ("why dont you do proper code review and first tell me where we are having issues", False),            # turn 18
    ("last time we launched we were unable to play the game", False),                                      # turn 17
    ("we are talking about neon chomp game right...???", False),                                           # turn 22
])
def test_which_live_messages_ask_for_a_change(text, change):
    assert C.asks_change(text) is change


def test_a_fix_that_starts_by_reading_gets_the_change_tools(tmp_path):
    """Live turn 10: the decide step called read_file, the look phase refused every edit. Fails without the fix."""
    ws = _two_projects(tmp_path)
    m = Heard(AIMessage(content="", tool_calls=[tc("read_file", 1, path="neon_chomp/maze.py")]),
              AIMessage(content="", tool_calls=[tc("edit_file", 2, path="neon_chomp/maze.py", old="215", new="214")]),
              AIMessage(content="Changed neon_chomp/maze.py:1 to 214. Untested: neon_chomp has no tests."))
    s = _session(ws, m)
    s.phased(_msgs("review this neon chomp code and fix the issues and bugs"))
    assert "214" in (ws / "neon_chomp" / "maze.py").read_text(encoding="utf-8")
    assert "edit_file" in m.offered[1] and s.last_phase == "make_change"     # the change tools, not the look's


def test_an_edit_inside_a_look_switches_to_the_change_phase(tmp_path):
    """Live turns 8/13/18: look_at_code, then edit_file -> "not available to the chat role" -> "apply it manually"."""
    ws = _two_projects(tmp_path)
    m = Heard(AIMessage(content="", tool_calls=[tc("look_at_code", 1, what="the pellet bug")]),
              AIMessage(content="", tool_calls=[tc("read_file", 2, path="neon_chomp/maze.py")]),
              AIMessage(content="", tool_calls=[tc("edit_file", 3, path="neon_chomp/maze.py", old="215", new="214")]),
              AIMessage(content="", tool_calls=[tc("edit_file", 4, path="neon_chomp/maze.py", old="215", new="214")]),
              AIMessage(content="Changed neon_chomp/maze.py:1. Untested: no tests for neon_chomp."))
    s = _session(ws, m)
    s.phased(_msgs("go a head and complete all the required things"))
    assert "214" in (ws / "neon_chomp" / "maze.py").read_text(encoding="utf-8")
    assert "make_change" in m.offered[1] and "edit_file" in m.offered[-1]   # offered in the look, then used
    assert [r.get("name") for r in _rows(s) if r["kind"] == "phase"][-1] == "make_change"


def test_a_question_keeps_the_look_phase_and_the_refusal_never_says_role(tmp_path):
    ws = _two_projects(tmp_path)
    m = Heard(AIMessage(content="", tool_calls=[tc("look_at_code", 1, what="where the issues are")]),
              AIMessage(content="", tool_calls=[tc("edit_file", 2, path="neon_chomp/maze.py", old="215", new="214")]),
              AIMessage(content="The pellet count is off by one (neon_chomp/maze.py:1)."))
    s = _session(ws, m)
    s.phased(_msgs("why dont you do proper code review and first tell me where we are having issues"))
    assert "215" in (ws / "neon_chomp" / "maze.py").read_text(encoding="utf-8")     # looked, changed nothing
    refused = [r["output"] for r in _rows(s) if r["kind"] == "tool" and r["name"] == "edit_file"][0]
    assert "role" not in refused and "never tell the user you cannot change files" in refused


# ── 2. the tests of the project that changed ─────────────────────────────────────────────────────────────────────

def test_project_dir_in_a_folder_of_projects(tmp_path):
    ws = _two_projects(tmp_path)
    assert T.is_multi_project(ws)
    assert T.project_dir(ws, "neon_chomp/maze.py") == "neon_chomp"
    assert T.project_dir(ws, "brick-breaker/tests/test_game.py") == "brick-breaker"
    single = tmp_path / "snake"
    (single / "snake").mkdir(parents=True)
    (single / "web").mkdir()
    assert not T.is_multi_project(single) and T.project_dir(single, "snake/game.py") == ""    # one project, parts
    (single / "tests").mkdir()
    assert T.project_dir(single, "snake/game.py") == ""


def test_a_change_in_a_new_project_never_reports_another_projects_tests(tmp_path):
    """Live turns 4-6: neon_chomp files written, brick-breaker's '37 passed' came back. Fails without the fix."""
    ws = _two_projects(tmp_path)
    m = Heard(AIMessage(content="", tool_calls=[tc("make_change", 1, what="maze")]),
              AIMessage(content="", tool_calls=[tc("write_file", 2, path="neon_chomp/entities.py",
                                                   content="class Player:\n    pass\n")]),
              AIMessage(content="Wrote neon_chomp/entities.py. Untested: neon_chomp has no tests yet."))
    s = _session(ws, m)
    s.phased(_msgs("build the entities"))
    rows = _rows(s)
    assert not [r for r in rows if r["kind"] == "tool" and r["name"] == "run_tests"]      # brick-breaker's: not run
    assert any("this project (neon_chomp/) has no tests" in str(x) for x in m.heard[2])
    assert s.focus == "neon_chomp"


def test_the_tests_run_inside_the_project_folder(tmp_path):
    ws = _two_projects(tmp_path)
    (ws / "neon_chomp" / "tests").mkdir()
    (ws / "neon_chomp" / "tests" / "test_maze.py").write_text(
        "from maze import PELLETS\n\ndef test_count():\n    assert PELLETS == 214\n", encoding="utf-8")
    (ws / "neon_chomp" / "conftest.py").write_text("", encoding="utf-8")
    m = Heard(AIMessage(content="", tool_calls=[tc("make_change", 1, what="fix the count")]),
              AIMessage(content="", tool_calls=[tc("read_file", 2, path="neon_chomp/maze.py")]),
              AIMessage(content="", tool_calls=[tc("edit_file", 3, path="neon_chomp/maze.py", old="215", new="214")]),
              AIMessage(content="Fixed neon_chomp/maze.py:1; the neon_chomp tests pass."))
    s = _session(ws, m)
    s.turn_no = 0
    s.phased(_msgs("fix the pellet count in neon chomp"))
    runs = [r for r in _rows(s) if r["kind"] == "tool" and r["name"] == "run_tests"]
    assert runs and runs[-1]["ok"] and "1 passed" in runs[-1]["output"]       # neon_chomp's test, not brick's
    assert runs[-1]["args"] == {"folder": "neon_chomp"}


def test_the_model_s_own_run_tests_stays_in_the_project(tmp_path):
    ws = _two_projects(tmp_path)
    m = Heard(AIMessage(content="", tool_calls=[tc("run_tests", 1)]),
              AIMessage(content="No tests ran in neon_chomp."))
    s = _session(ws, m)
    s.focus = "neon_chomp"
    s.phased(_msgs("run the neon chomp tests"))
    run = [r for r in _rows(s) if r["kind"] == "tool" and r["name"] == "run_tests"][0]
    assert run["args"]["folder"] == "neon_chomp" and "1 passed" not in run["output"]


# ── 5. the project in focus ──────────────────────────────────────────────────────────────────────────────────────

def test_the_focus_follows_the_user_and_the_changes(tmp_path):
    ws = _two_projects(tmp_path)
    m = Heard(AIMessage(content="Yes: Neon Chomp. What should I check first?"))
    s = _session(ws, m)
    s.phased(_msgs("we are talking about neon chomp game right...???"))
    assert s.focus == "neon_chomp"
    assert "we are working on neon_chomp/" in m.heard[0][-2] and "brick-breaker/ are other projects" in m.heard[0][-2]
    s._touch_project("read_file", {"path": "brick-breaker/tests/test_game.py"})
    assert s.focus == "neon_chomp"                              # a stray read does not move it (live turn 21)
    s._touch_project("write_file", {"path": "brick-breaker/x.py"})
    assert s.focus == "brick-breaker"                           # a change does


def test_no_focus_line_in_a_single_project(tmp_path):
    (tmp_path / "game.py").write_text("x = 1\n", encoding="utf-8")
    m = Heard(AIMessage(content="Hi! What are we working on?"))
    s = _session(tmp_path, m)
    s.phased(_msgs("hi mitra"))
    assert m.heard[0][-2] == C.DECIDE_NOTE


# ── 3. claims that a turn's tools do not back ────────────────────────────────────────────────────────────────────

REFUSED = [("read_file", True, "neon_chomp/maze.py"), ("edit_file", False, "✗ edit_file is not available")]
FAILED = [("edit_file", True, "Edited"), ("run_tests", False, "FAILED: 4 failed, 11 passed in 0.5s")]


@pytest.mark.parametrize("text, tools, changed", [
    ("Great news! I found and fixed the bug in **Neon Chomp**.", REFUSED, False),                         # turn 8
    ("I've identified and fixed all the issues in **Neon Chomp**.", REFUSED, False),                      # turn 13
    ("- ✅ Fixed the drone targeting issue (player not initialized yet)", [], False),                      # turn 17
    ("I've already fixed the issues in the brick-breaker project.", [], False),                           # turn 12
    ("All 36 tests are now passing", [], False),                                                          # turn 12
    ("🎉 **Neon Chomp is now running successfully!**", FAILED, True),                                      # turn 20
    ("The game has launched without any crashes or errors.", FAILED, True),                               # turn 20
])
def test_the_live_false_claims_are_caught(text, tools, changed):
    assert G.unbacked(text, tools, changed=changed), text


@pytest.mark.parametrize("text, tools, changed", [
    ("I'll fix maze.py next. Should I add the check?", [], False),
    ("The fix needs to be applied to maze.py:94.", [], False),
    ("Fixed neon_chomp/maze.py:94; the tests pass.", [("edit_file", True, "Edited"), ("run_tests", True, "PASSED")],
     True),
    ("Once it is running, press Enter.", FAILED, True),
    ("I could not change maze.py: the edit did not apply.", REFUSED, False),
])
def test_honest_answers_are_not_claims(text, tools, changed):
    assert not G.unbacked(text, tools, changed=changed), text


def test_a_false_claim_is_corrected_in_the_history(tmp_path):
    """Live turn 15: "did you do that fix" built on turn 13's false "I've fixed all the issues"."""
    ws = _two_projects(tmp_path)
    m = Heard(AIMessage(content="I've identified and fixed all the issues in Neon Chomp."))
    s = _session(ws, m)
    messages = _msgs("did you fix it")
    s.phased(messages)
    note = messages[-1].content
    assert isinstance(messages[-1], HumanMessage) and "do not back it" in note and "changed no files" in note


# ── 6. a 524 is one slow call, not Kaggle ending ─────────────────────────────────────────────────────────────────

class Slow524(Heard):
    def __init__(self, *replies, fails=1):
        super().__init__(*replies)
        self.fails = fails

    def stream(self, messages):
        self.heard.append([m.content for m in messages])
        if self.fails:
            self.fails -= 1
            raise RuntimeError('{"title":"Error 524: A timeout occurred","status":524,"detail":"The origin web server '
                               'did not return a complete response within the 120-second Proxy Read Timeout window."}')
        self.calls += 1
        yield self.replies.pop(0) if self.replies else AIMessage(content="All done.")


def test_a_524_retries_with_smaller_steps_and_never_ends_kaggle(tmp_path):
    """Live turn 5: two 524s and the turn ended as "kaggle_ended" while Kaggle was fine. Fails without the fix."""
    m = Slow524(AIMessage(content="", tool_calls=[tc("write_file", 1, path="a.py", content="x = 1\n")]),
                AIMessage(content="Wrote a.py. Untested: no tests."))
    s = _session(tmp_path, m)
    s.backend_kind = "remote"
    res = s.turn(_msgs("write a.py"))
    assert not res.remote_gone and (tmp_path / "a.py").exists()
    assert C.SLOW_NOTE in m.heard[1]
    ends = [r for r in _rows(s) if r["kind"] == "turn_end"]
    assert ends[-1]["outcome"] != "kaggle_ended"


def test_two_524s_stop_the_turn_honestly(tmp_path):
    m = Slow524(AIMessage(content="I was cut off twice; I wrote nothing yet."), fails=2)
    s = _session(tmp_path, m)
    s.backend_kind = "remote"
    res = s.turn(_msgs("write a.py"))
    assert not res.remote_gone and res.stopped and "Kaggle itself is still running" in res.stop_reason


def test_a_real_tunnel_loss_is_still_remote_gone():
    assert C.is_remote_down(RuntimeError("getaddrinfo failed for x.trycloudflare.com"))
    assert not C.is_remote_slow(RuntimeError("getaddrinfo failed"))
    assert C.is_remote_slow(RuntimeError("Error 524: A timeout occurred"))


def test_a_true_count_from_a_failed_run_is_not_a_claim():
    out = "FAILED: 4 failed, 11 passed, 1 warning in 0.49s"
    assert not G.unbacked("What's working (11 tests passing):", [("run_tests", False, out)])
    assert G.unbacked("What's working (15 tests passing):", [("run_tests", False, out)])
