"""D-071 one CodeMitra: one conversational loop decides whether to talk, look or change (behind `architecture = "one"`).
Fixed rules stay only for /commands, `mitra ...` typed in the chat and "where did we stop"."""
import json

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from app import main, memory
from app.core import chat as C
from app.core import score as S
from tests.test_backend_chat import Inputs, harness  # noqa: F401 - the driven chat fixture
from tests.test_chat_core import Model, fake_hooks, tc


def _rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_converse_offers_every_tool_and_just_talks_when_the_model_talks(tmp_path):
    m = Model(AIMessage(content="Sounds good. What's on your mind?"))
    s = C.ChatSession(workspace=tmp_path, llm=m, hooks=fake_hooks()[0])
    messages = [SystemMessage(content=C.ONE_PROMPT), HumanMessage(content="i am thinking mitra")]
    res = s.converse(messages)
    assert res.text.startswith("Sounds good") and res.steps == 1 and m.calls == 1
    assert {"read_file", "edit_file", "run_tests"} <= set(m.tool_names)         # the model decides, not a sorter
    start = [r for r in _rows(s.rec.path) if r["kind"] == "turn_start"][0]
    assert start["path"] == "one" and s.path == "loop" and not s.answer_on_last_step


def test_converse_looks_when_the_model_needs_the_code_and_always_ends_with_an_answer(tmp_path):
    (tmp_path / "game.py").write_text("def step():\n    return 1\n", encoding="utf-8")
    calls = [AIMessage(content="", tool_calls=[tc("search", n, pattern=f"p{n}")]) for n in range(1, 4)]
    m = Model(*calls, AIMessage(content="It returns 1 (game.py:2); I could not check the rest."))
    s = C.ChatSession(workspace=tmp_path, llm=m, hooks=fake_hooks()[0])
    s.harness.limits["chat_max_steps"] = 4
    messages = [SystemMessage(content=C.ONE_PROMPT), HumanMessage(content="what does step do?")]
    res = s.converse(messages)
    assert res.steps == 4 and m.calls == 4 and res.text                        # the 4th step had no tools
    assert C.ONE_LAST_STEP_NOTE not in [x.content for x in messages]           # the note is taken out again


def test_your_notes_reach_a_turn_only_when_changed_and_leave_no_trace(tmp_path):
    seen = []

    class Watch(Model):
        def stream(self, messages):
            seen.append([str(x.content) for x in messages])
            return super().stream(messages)

    s = C.ChatSession(workspace=tmp_path, llm=Watch(AIMessage(content="ok")), hooks=fake_hooks()[0])
    messages = [SystemMessage(content="sys"), HumanMessage(content="hi")]
    s.converse(messages, notes="## About the user (me.md)\nName: P")
    assert "Name: P" in " ".join(seen[0]) and len(messages) == 3              # sys, you, CodeMitra: no note left


def test_context_notes_keeps_what_you_wrote_not_the_topic_list():
    ctx = ("# Project Context\n## Recent topics\n- `2026-11-11` hi mitra\n- `2026-11-10` brick breaker\n\n"
           "## Notes\n<!-- Add anything -->\nUse uv.\n\n## Auto\nx\n")
    assert memory.context_notes(ctx) == "## Notes\nUse uv."
    assert memory.context_notes("## Notes\n<!-- Add anything -->\n") is None and memory.context_notes(None) is None


def test_the_score_runs_one_mitra_through_converse(tmp_path):
    from app.core import store
    m = Model(AIMessage(content="Hi Prashanth! What are we working on today?"))
    r = S.Runner(llm=m, harness=C.H.Harness(), num_ctx=8192, records=store.root() / "score-runs" / "one",
                 arch="one")
    out = S.run_behaviour(r, only={"B1_hello"})
    assert [(c.id, c.passed) for c in out] == [("B1_hello", True)]
    assert m.tool_names                                                          # tools offered, none used
    assert r.system().content.startswith("You are CodeMitra, the user's thinking partner")


def test_one_mitra_in_the_real_chat_loop(harness, capsys):  # noqa: F811
    state, ws = harness
    (ws / "codemitra.toml").write_text('architecture = "one"\n', encoding="utf-8")
    Inputs.script = ["hi mitra", "build a score system for the game with a high score file and a menu",
                     "where did we stop", "codemitra score", "exit"]
    main._chat()
    rows = [json.loads(x) for f in (ws / ".codemitra" / "runs").glob("chat-*.jsonl")
            for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    paths = [r["path"] for r in rows if r["kind"] == "turn_start"]
    assert paths == ["one", "one", "resume_brief", "cli_hint"]                 # no sorter, no plan-first guess
    out = " ".join(capsys.readouterr().out.split())
    assert "planning it first" not in out


def test_every_model_call_has_an_output_cap():
    """E-099: a looping model generated 18,400 tokens for 36 minutes; every later request queued behind it."""
    from app import llm as L
    m = L.get_local_llm("mimo-v2.6:9b", num_ctx=8192, reasoning=False)
    assert m.num_predict == L.MAX_OUTPUT_TOKENS == 8192
    assert L.get_local_llm("mimo-v2.6:9b", num_predict=100, reasoning=False).num_predict == 100


def test_a_cancelled_case_closes_its_model_stream():
    closed = []

    def endless():
        try:
            n = 0
            while True:
                n += 1
                yield AIMessageChunk(content="x")
        finally:
            closed.append(True)

    calls = {"n": 0}

    def cancelled():
        calls["n"] += 1
        return calls["n"] > 5

    res = S._stream(endless(), 1, cancelled)
    assert res.stopped and closed == [True] and res.text == "xxxxx"


class _Runaway(Model):
    """First call: endless invisible output (thinking with thinking off, E-100); then a real answer."""

    def __init__(self, answer):
        super().__init__()
        self.answer, self.closed = answer, 0

    def stream(self, messages):
        self.calls += 1
        if self.calls == 1:
            def endless():
                try:
                    while True:
                        yield AIMessageChunk(content="")
                finally:
                    self.closed += 1
            return endless()
        return iter([AIMessageChunk(content=self.answer)])


def test_a_hidden_runaway_is_stopped_nudged_and_answered(tmp_path):
    m = _Runaway("Sounds good: who would rate first?")
    s = C.ChatSession(workspace=tmp_path, llm=m, hooks=fake_hooks()[0])
    s.thinking = False
    messages = [SystemMessage(content=C.ONE_PROMPT), HumanMessage(content="lets think deep about ratings")]
    res = s.converse(messages)
    assert res.text == "Sounds good: who would rate first?" and m.calls == 2 and m.closed == 1
    assert any(r["kind"] == "runaway" for r in _rows(s.rec.path))
    assert C.RUNAWAY_NOTE in [x.content for x in messages]


def test_with_thinking_on_long_reasoning_is_not_cut():
    chunks = [AIMessageChunk(content="", additional_kwargs={"reasoning_content": "x"})] * 2000 + [
        AIMessageChunk(content="done")]
    assert len(list(C.guard_runaway(iter(chunks), limit=10**9))) == 2001     # the chat skips the guard then
    try:
        list(C.guard_runaway(iter(chunks), limit=1500))
        raise AssertionError("expected a runaway")
    except C.Runaway:
        pass


def test_project_outline_lists_the_folder(tmp_path):
    (tmp_path / "snake").mkdir()
    (tmp_path / "snake" / "game.py").write_text("x", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("x", encoding="utf-8")
    (tmp_path / "serve.py").write_text("x", encoding="utf-8")
    out = C.project_outline(tmp_path)
    assert out.endswith("Files: serve.py, snake/game.py") and ".git" not in out
