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
    assert task.index("CodeMitra's last answer") > task.index("roman telugu") and "HF Space" in task
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


def test_planned_and_resume_turns_are_not_empty_answers(tmp_path):
    """Deep dive 2026-11-11: `codemitra report` counted plan-first and "where did we stop" turns (no answer text by
    design) and esc stops as the model's empty answers, which the coach would read as failures."""
    import json as _json

    from app.core import analyze

    runs = tmp_path / "proj" / ".codemitra" / "runs"
    runs.mkdir(parents=True)
    rows = [{"kind": "turn_start", "turn": 1, "path": "plan_first"}, {"kind": "turn_end", "turn": 1, "text": "",
                                                                        "outcome": "plan_cancelled"},
            {"kind": "turn_start", "turn": 2, "path": "resume_brief"}, {"kind": "turn_end", "turn": 2, "text": "",
                                                                          "outcome": "answered"},
            {"kind": "turn_start", "turn": 3, "path": "loop"}, {"kind": "turn_end", "turn": 3, "text": "",
                                                                  "outcome": "stopped_by_user"},
            {"kind": "turn_start", "turn": 4, "path": "loop"}, {"kind": "turn_end", "turn": 4, "text": "",
                                                                  "outcome": "answered"},
            {"kind": "turn_start", "turn": 5}]
    f = runs / "chat-20261111.jsonl"
    f.write_text("\n".join(_json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    rep = analyze.analyze([f])
    empty = rep.pattern("empty_answer")
    assert empty.count == 1 and "turn 4" in empty.examples[0]


def test_a_workspace_in_the_temp_folder_is_never_mirrored_to_your_store(tmp_path, monkeypatch):
    """Deep dive 2026-11-11: dev checks and a leaked test thread put 10 temp workspaces into ~/.codemitra/data."""
    import tempfile as _tf
    from pathlib import Path as _P

    from app.core import harness as _H
    from app.core import store

    home = _P(_tf.gettempdir()).parent / "not-temp-home-for-test"   # a real home outside the temp folder
    monkeypatch.setattr(_H, "home", lambda: home)
    rec = _P(_tf.gettempdir()) / "codemitra-score-x" / "snake" / ".codemitra" / "runs" / "chat-20261111.jsonl"
    assert store.mirror_path(rec) is None
    project = _P("C:/Users/someone/projects/game/.codemitra/runs/chat-20261111.jsonl")
    assert store.mirror_path(project) is not None


def test_your_mitra_toml_thinking_wins_over_the_role_table():
    """Review 2026-11-11: with every role set to on/off, `thinking = "on"` in codemitra.toml changed nothing."""
    from app.core import roles

    assert roles.thinking_for("chat") is False and roles.thinking_for("planner") is True
    assert roles.thinking_for("chat", {"thinking": "on"}) is True
    assert roles.thinking_for("planner", {"thinking": "off"}) is False
    assert roles.thinking_for("builder", {"thinking": "auto"}) is False      # auto = the table


SWEEP = [  # deep dive 2026-11-11: realistic follow-ups and requests that went to the wrong path
    ("small", "still not working", "small"), ("small", "no, use pytest not unittest", "small"),
    ("small", "try again", "small"), ("question", "why?", "question"),
    ("question", "and where is the score kept?", "question"), ("question", "and fix it", "small"),
    ("", "run the tests", "small"), ("", "commit the changes", "small"),
    ("", "the tests are failing, can you check", "small"), ("", "why is the test failing?", "question"),
    ("", "rename paddle to player in the game", "small"),
    ("", "rewrite this paragraph to sound more professional: we done the work", "writing"),
    ("", "help me write a prd for a roman telugu chat app", "writing"),
    ("", "write a story generator app with flask", "big"),
    ("", "i need a script that downloads hf datasets and saves them as parquet", "small"),
    ("", "what changed since yesterday", "question"), ("small", "thanks, that worked", "chat"),
]


def test_the_sweep_of_everyday_follow_ups_is_sorted_right():
    pw = {"brick-breaker", "plan", "tests", "game", "paddle", "ball", "readme", "src", "app", "main", "api"}
    got = [(p, t, classify(t, previous=p, project_words=pw)) for p, t, _ in SWEEP]
    assert got == [(p, t, w) for p, t, w in SWEEP]


def test_a_mitra_command_typed_in_the_chat_is_recognised():
    """Live 2026-11-11: the user typed `codemitra score` in the chat; it was explained as a question about the project."""
    from app.core.intent import terminal_command

    assert terminal_command("codemitra score") == "codemitra score"
    assert terminal_command("  `codemitra score --remote` ") == "codemitra score --remote"
    assert terminal_command("$ codemitra kaggle stop") == "$ codemitra kaggle stop"
    assert terminal_command("how does codemitra score the tasks?") == ""
    assert terminal_command("mitra, explain the score module") == ""
    assert terminal_command("mitra") == ""


def test_the_chat_answers_a_terminal_command_with_a_hint(harness, capsys):  # noqa: F811
    from app import main
    from tests.test_backend_chat import Inputs

    state, ws = harness
    Inputs.script = ["codemitra score", "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert "is a terminal command" in out and "another terminal" in out and "codemitra score --remote" in out
    import json as _json
    rows = [_json.loads(x) for f in (ws / ".codemitra" / "runs").glob("chat-*.jsonl")
            for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    starts = [r for r in rows if r["kind"] == "turn_start"]
    assert [(r["path"], r["request_kind"]) for r in starts] == [("cli_hint", "terminal_command")]
    assert not [r for r in rows if r["kind"] == "model"]           # answered without the model


from tests.test_backend_chat import harness  # noqa: E402,F401 - the driven chat fixture
