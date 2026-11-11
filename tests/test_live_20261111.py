"""The user's live session on 2026-11-11 (mitra-try, Kaggle): talking an idea through went to plan-first, the
planner was cut by Cloudflare after 120 s on the tunnel (524), and the Kaggle-ended report named an old night run
with "4176 min of up to 4.0 h"."""
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import handoff, planner
from app.core.intent import classify

IDEA = ("i want you to build a simple web application that will help in paraphase or write a small story using the "
        "inputs we give , and for llm i will provide with an openrouter or any free llm api from any provider\n"
        "can we brainstrom on this")
MUSE = ("i feel i might be week in roman telugu , so once we get a base model i want to setup a web application and "
        "host it in hugging face to people to use mostly in roman telugu so i can collect lots of different user "
        "feedback they can ask anything just like a casual chat and collect feedback")


def test_talking_an_idea_through_is_not_planned_as_a_build():
    assert classify(IDEA) == "general"
    assert classify(MUSE, previous="general") == "general"
    assert classify("we can think deep i feel, where we can use or design a database", previous="general") == "general"
    assert classify("can we discuss how the game module handles collisions", project_words={"game"}) == "question"


def test_build_it_after_the_discussion_plans_it():
    assert classify("ok lets build it", previous="general") == "big"
    assert classify("build the web app we discussed", previous="general") == "big"
    assert classify("ok do it", previous="question") == "small"          # after a code question: just do it
    assert classify("i think the test is wrong, fix it") == "small"       # a change, not a musing
    assert classify("refactor the api and discuss the trade-offs") == "big"


def test_the_planner_gets_the_discussion_not_just_build_it():
    messages = [SystemMessage(content="sys"), HumanMessage(content=IDEA), AIMessage(content="Components: a DB ..."),
                HumanMessage(content=MUSE), AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
                AIMessage(content="Plan: FastAPI + SQLite, a rating table, a HF Space.")]
    task = planner.with_discussion("ok lets build it", messages)
    assert task.startswith("ok lets build it") and "brainstrom" in task and "roman telugu" in task
    assert task.index("Mitra's last answer") > task.index("roman telugu") and "HF Space" in task
    assert len(planner.with_discussion("go", [HumanMessage(content="x" * 50_000)])) < 5000
    assert planner.with_discussion("go", [SystemMessage(content="sys")]) == "go"


def test_the_planner_streams_so_the_tunnel_never_waits_120_s_for_a_first_byte():
    class Streams:
        def invoke(self, messages):
            raise AssertionError("one long invoke is cut by Cloudflare after 120 s (524)")

        def stream(self, messages):
            yield AIMessage(content="## Tasks\n")
            yield AIMessage(content="### T1: a\n")

    assert planner._invoke(Streams(), [HumanMessage(content="plan")]) == "## Tasks\n### T1: a\n"


def test_the_kaggle_report_names_only_a_night_from_this_session():
    now = time.time()
    old = {"running": False, "started": now - 4176 * 60, "plan": "C:/x/plan.md", "elapsed_min": 4176, "hours": 4.0}
    assert handoff.night_for_report(old, kaggle_started=now - 135 * 60) is None
    assert handoff.night_for_report(None, kaggle_started=now) is None
    fresh = {**old, "started": now - 60 * 60, "elapsed_min": 60}
    assert handoff.night_for_report(fresh, kaggle_started=now - 135 * 60) == {
        "state": "finished", "plan": "plan.md", "detail": "up to 4.0 h"}
    running = {**old, "running": True}
    assert handoff.night_for_report(running, kaggle_started=now)["detail"] == "4176 min so far, up to 4.0 h"
