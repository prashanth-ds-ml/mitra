"""D-068 step 2: questions about the project's code. Read-only tools, a budget of 6 steps, the last step without
tools so there is always an answer; recorded with the steps used, budget hit, files read and files cited."""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app import main
from app.core import chat as C
from app.core import harness as H
from tests.test_backend_chat import Inputs, harness  # noqa: F401 - the driven chat fixture
from tests.test_chat_core import Model, fake_hooks, tc


class Watching(Model):
    """Scripted model that also keeps what each call was sent."""

    def __init__(self, *replies):
        super().__init__(*replies)
        self.sent = []

    def stream(self, messages):
        self.sent.append(list(messages))
        return super().stream(messages)


def _project(tmp_path):
    (tmp_path / "game.py").write_text("def step(state):\n    # move the ball\n    return state.ball + 1\n",
                                      encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "paddle.py").write_text("SPEED = 3\n", encoding="utf-8")
    return tmp_path


def _rows(s, kind):
    return [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if f'"{kind}"' in x]


def test_explain_reads_then_answers_with_references_and_no_write_tools(tmp_path):
    ws = _project(tmp_path)
    m = Watching(AIMessage(content="", tool_calls=[tc("search", 1, pattern="def step")]),
                 AIMessage(content="", tool_calls=[tc("read_file", 2, path="game.py")]),
                 AIMessage(content="The game moves the ball one step each tick (game.py:3)."))
    s = C.ChatSession(workspace=ws, llm=m, hooks=fake_hooks()[0])
    messages = [SystemMessage(content="sys"), HumanMessage(content="explain the game logic")]
    res = s.explain(messages, notes="## About the user (me.md)\nName: P")
    assert res.text.endswith("(game.py:3).") and res.steps == 3 and not res.stopped
    assert set(m.tool_names) == set(C.EXPLAIN_TOOLS)                       # nothing that writes was offered
    assert "You have 6 steps" in " ".join(str(x.content) for x in m.sent[0])
    # the instruction is gone from the history; what was read stays for a follow-up
    assert not any(isinstance(x, SystemMessage) and "You have 6 steps" in x.content for x in messages)
    assert sum(1 for x in messages if x.__class__.__name__ == "ToolMessage") == 2
    assert s.allowed_tools is None and s.path == "loop" and not s.answer_on_last_step and s.end_info == {}
    start, end = _rows(s, "turn_start")[0], _rows(s, "turn_end")[0]
    assert start["path"] == "explain" and start["request_kind"] == "question"
    assert end["budget"] == 6 and end["budget_hit"] is False and end["steps"] == 3
    assert end["files_read"] == ["game.py"] and end["files_cited"] == ["game.py"] and end["asked"] is False


def test_the_last_step_has_no_tools_so_it_always_answers(tmp_path):
    ws = _project(tmp_path)
    wander = [AIMessage(content="", tool_calls=[tc("search", n, pattern=f"x{n}")]) for n in range(1, 6)]
    m = Watching(*wander, AIMessage(content="I could not find all of it; the loop is in game.py:1.",
                                    tool_calls=[tc("search", 9, pattern="more")]))
    s = C.ChatSession(workspace=ws, llm=m, hooks=fake_hooks()[0])
    messages = [SystemMessage(content="sys"), HumanMessage(content="how does the game loop work?")]
    res = s.explain(messages)
    assert res.steps == 6 and m.calls == 6 and res.text.startswith("I could not find all")
    assert C.LAST_STEP_NOTE in [x.content for x in m.sent[-1]]                # told on the last step
    assert C.LAST_STEP_NOTE not in [x.content for x in messages]              # and taken out after
    assert not getattr(messages[-1], "tool_calls", None)                      # the extra tool call was not run
    end = _rows(s, "turn_end")[0]
    assert end["budget_hit"] is True and end["files_cited"] == ["game.py"]


def test_a_write_is_refused_even_if_the_model_asks(tmp_path):
    ws = _project(tmp_path)
    m = Watching(AIMessage(content="", tool_calls=[tc("edit_file", 1, path="game.py", old="+ 1", new="+ 2")]),
                 AIMessage(content="It adds one (game.py:3)."))
    hooks, shown = fake_hooks()
    s = C.ChatSession(workspace=ws, llm=m, hooks=hooks)
    s.explain([SystemMessage(content="sys"), HumanMessage(content="what does step do?")])
    assert "+ 1" in (ws / "game.py").read_text(encoding="utf-8")
    assert shown[0][0] == "edit_file" and shown[0][1] is False


def test_a_vague_question_may_be_answered_with_a_question(tmp_path):
    m = Watching(AIMessage(content="Which part do you mean: the ball, or the paddle?"))
    s = C.ChatSession(workspace=_project(tmp_path), llm=m, hooks=fake_hooks()[0])
    res = s.explain([SystemMessage(content="sys"), HumanMessage(content="explain it")])
    assert res.steps == 1 and _rows(s, "turn_end")[0]["asked"] is True


def test_cited_files_keeps_only_files_that_exist(tmp_path):
    ws = _project(tmp_path)
    text = "See game.py:3, pkg/paddle.py:1, paddle.py:1 again, ./game.py:2 and missing.py:9 or v1.2:3."
    assert C.cited_files(text, ws) == ["game.py", "pkg/paddle.py"]
    # live 2026-11-10: answers name files without a line too ("**Board** (`snake/game.py`)"); code is not a file
    assert C.cited_files("Board (`pkg/paddle.py`), see `state.ball` and self.step().", ws) == ["pkg/paddle.py"]
    (ws / ".venv").mkdir()
    (ws / ".venv" / "other.py").write_text("", encoding="utf-8")
    assert C.cited_files("other.py", ws) == []


def test_a_follow_up_records_only_its_own_reads(tmp_path):
    """Live 2026-11-10: the second question's record listed every file the first one had read."""
    ws = _project(tmp_path)
    m = Watching(AIMessage(content="", tool_calls=[tc("read_file", 1, path="game.py")]),
                 AIMessage(content="It steps the ball."),
                 AIMessage(content="", tool_calls=[tc("read_file", 2, path="pkg/paddle.py")]),
                 AIMessage(content="SPEED is 3 (pkg/paddle.py:1)."))
    s = C.ChatSession(workspace=ws, llm=m, hooks=fake_hooks()[0])
    messages = [SystemMessage(content="sys"), HumanMessage(content="what does game.py do?")]
    s.explain(messages)
    messages.append(HumanMessage(content="and the paddle speed?"))
    s.explain(messages)
    first, second = _rows(s, "turn_end")
    assert first["files_read"] == ["game.py"] and first["line_refs"] is False
    assert second["files_read"] == ["pkg/paddle.py"] and second["line_refs"] is True


def test_ideas_reviews_and_plan_edits_about_the_project_are_sorted_right():
    """Step 2b (user, 2026-11-10): brainstorming, reviews and plan updates on the project must work, not only
    "how does it work". Before: project ideas went to the no-tools path and "update the plan" planned a feature."""
    from app.core.intent import classify
    pw = {"game", "paddle", "ball", "snake", "api"}
    cases = {
        "brainstorm ideas to make the game harder": "question", "suggest some improvements for the api": "question",
        "any ideas to speed up our tests?": "question", "what could we add to the snake game next?": "question",
        "review the code in game.py": "question", "is this a good way to structure the game loop?": "question",
        "pros and cons of moving to fastapi for this project": "question",
        "update the plan with a level system": "small", "add a task to plan.md for sound": "small",
        "update the plan and implement the level system": "big",
        # not about the project: still the quick everyday answer
        "brainstorm names for my startup": "general", "give me ideas for a weekend trip": "general",
        "plan my day: gym, kaggle run, review PRs": "general",
    }
    assert {t: classify(t, project_words=pw) for t in cases} == cases
    picks = {"go with option 2": "small", "lets do option 3": "small", "yes, the first idea": "small",
             "build the second one": "small", "what is option 2 exactly?": "question"}
    assert {t: classify(t, previous="question", project_words=pw) for t in picks} == picks
    assert classify("go with option 2") == "general"          # nothing was offered before


def test_the_explainer_note_covers_reviews_and_ideas():
    note = C.EXPLAIN_NOTE.format(steps=6)
    assert "Review or opinion" in note and "Ideas: 3-5 options" in note and "Do not change" in note


def test_the_budget_is_a_harness_limit():
    assert H.Harness().limit("explain_max_steps") == 6


# ── end to end: the real chat loop ───────────────────────────────────────────

def test_a_code_question_goes_to_the_explainer_end_to_end(harness, monkeypatch):  # noqa: F811
    state, ws = harness
    (ws / "game.py").write_text("def step(s):\n    return s\n", encoding="utf-8")
    made = []
    orig = main.get_local_llm

    def tracking(*a, **k):
        m = orig(*a, **k)
        made.append(m)
        return m

    monkeypatch.setattr(main, "get_local_llm", tracking)
    Inputs.script = ["explain the game logic", "fix the failing test in test_x.py", "exit"]
    main._chat()
    rows = [json.loads(x) for f in (ws / ".mitra" / "runs").glob("chat-*.jsonl")
            for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    starts = [(r["path"], r["request_kind"]) for r in rows if r["kind"] == "turn_start"]
    assert starts == [("explain", "question"), ("loop", "small")]
    ends = [r for r in rows if r["kind"] == "turn_end"]
    assert ends[0]["budget"] == 6 and "budget_hit" in ends[0] and "budget" not in ends[1]
