"""D-062 end to end: the real chat loop with scripted input, a fake model and a Kaggle that is up or down.

Start on Kaggle → plan mode moves read work to the laptop → back to auto mode moves write work to Kaggle →
Kaggle dies → laptop + report + the message goes back to the input box.
"""
import pathlib

import pytest
from langchain_core.messages import AIMessage

from app import config, fit, main, remote
from app.core import roles
from app.core import chat as C_chat
from tests.test_chat_core import Model

KAGGLE_URL = "https://k.trycloudflare.com/tok"


class Inputs:
    """Stand-in for the prompt_toolkit input box: scripted lines; records the text put back in the box."""

    script: list = []
    defaults: list = []

    def __init__(self, *a, **k):
        self.toolbar = k.get("toolbar")

    def prompt(self, default=""):
        Inputs.defaults.append(default)
        if self.toolbar:
            Inputs.toolbars.append("".join(t for _, t in self.toolbar()))
        step = Inputs.script.pop(0) if Inputs.script else "exit"
        if callable(step):
            return step()
        return step


@pytest.fixture
def harness(tmp_path, monkeypatch):
    ws = tmp_path / "proj"
    ws.mkdir()
    (ws / ".git").mkdir()
    monkeypatch.chdir(ws)
    state = {"up": True, "llms": []}

    def fake_llm(model, temperature=0.2, *, base_url=None, num_ctx=None, **kw):
        state["llms"].append((model, base_url, num_ctx))
        m = Model(*[AIMessage(content=f"answer {i}") for i in range(20)])
        m.base_url, m.model = base_url, model
        return m

    inventory = [config.LocalModelInfo(name="mimo-v2.6:9b", context=262144),
                 config.LocalModelInfo(name="qwen3.5:4b", context=262144)]
    monkeypatch.setattr(main, "get_local_llm", fake_llm)
    monkeypatch.setattr(main, "show_banner", lambda: None)
    monkeypatch.setattr(main, "_print_memory_fit", lambda *a, **k: None)
    monkeypatch.setattr(main, "_rebuild_dashboard", lambda quiet=False: None)
    monkeypatch.setattr(main, "probe_ollama", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(main.ui, "InputBox", Inputs)
    monkeypatch.setattr(main.ui.notify, "ready", lambda c: None)
    monkeypatch.setattr(config, "get_local_model_inventory", lambda **k: list(inventory))
    monkeypatch.setattr(config, "get_gpu_memory_info", lambda: None)
    monkeypatch.setattr(config, "get_gpu_vram_gib", lambda: 8.0)
    monkeypatch.setattr(config, "get_model_facts", lambda name: {"context": 262144, "parameters": 9e9,
                                                                 "capabilities": ("completion", "tools")})
    monkeypatch.setattr(roles, "installed", lambda: {"mimo-v2.6:9b", "qwen3.5:4b"})
    monkeypatch.setattr(fit, "check", lambda m, c, **k: fit.Fit("remote" if remote.active() and not k.get("local")
                                                                  else "ok", m, c, 1.0, 1.0, 10.0, 9.0))
    monkeypatch.setattr(remote, "probe", lambda url, timeout=20: ([{"name": "mimo-v2.6:9b"}], "")
                        if state["up"] else ([], "getaddrinfo failed"))
    monkeypatch.setattr(main.mcp_registry, "discover", lambda *a, **k: [], raising=False)
    from app import kaggle
    monkeypatch.setattr(kaggle, "quota", lambda api: {"used_h": 2.0, "total_h": 30.0, "left_h": 28.0,
                                                      "refresh": None})
    monkeypatch.setattr(kaggle, "client", lambda: object())
    from app import backend
    backend.save_prefs(onboarded=True, kaggle_use="never")  # each test sets what it needs
    nokey = tmp_path / "nokey"
    monkeypatch.setattr(kaggle, "key_path", lambda: nokey / "kaggle.json")
    monkeypatch.setattr(kaggle, "token_path", lambda: nokey / "access_token")
    for var in ("KAGGLE_API_TOKEN", "KAGGLE_KEY", "KAGGLE_USERNAME"):
        monkeypatch.delenv(var, raising=False)
    config.save_last_model("mimo-v2.6:9b")
    Inputs.defaults, Inputs.toolbars = [], []
    yield state, ws
    remote.clear()


def test_switching_between_kaggle_and_the_laptop(harness, capsys):
    state, ws = harness
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")

    def kaggle_dies():
        state["up"] = False
        return "change the code"

    Inputs.script = ["/mode plan", "explain the code", "/mode auto", "/do write the feature", kaggle_dies, "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())  # the terminal wraps long lines
    # read work went to the laptop, write work back to Kaggle
    assert "plan mode: read work on the laptop → laptop" in out
    assert "write work on the remote GPU → kaggle" in out
    bases = [b for _, b, _ in state["llms"]]
    assert KAGGLE_URL in bases and "http://localhost:11434" in bases
    # Kaggle died: laptop, report, the message back in the input box
    assert "the Kaggle GPU stopped answering" in out and "Kaggle ended ·" in out
    reports = list((ws / ".codemitra" / "reports").glob("kaggle-ended-*.md"))
    assert len(reports) == 1 and "explain the code" in reports[0].read_text(encoding="utf-8")
    assert Inputs.defaults[-1] == "change the code"
    assert remote.active() is None  # a dead Kaggle address is forgotten
    assert any("☁ kaggle" in t for t in Inputs.toolbars) and any("💻 laptop" in t for t in Inputs.toolbars)


def test_kaggle_dead_at_start_reports_on_the_last_session(harness, capsys):
    state, ws = harness
    runs = ws / ".codemitra" / "runs"
    runs.mkdir(parents=True)
    (runs / "chat-20261110.jsonl").write_text(
        '{"kind": "session"}\n{"kind": "turn_start", "turn": 1, "user": "build the paddle"}\n'
        '{"kind": "turn_end", "turn": 1, "outcome": "tests_passed", "changed": []}\n', encoding="utf-8")
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")
    state["up"] = False
    Inputs.script = ["exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    # E-107: one line at start-up; the full report (with the turns) only in its file
    assert "Kaggle ended while CodeMitra was closed" in out and "1 turn, no files changed" in out
    assert "build the paddle" not in out and "is not answering" not in out and "What you asked" not in out
    reports = list((ws / ".codemitra" / "reports").glob("kaggle-ended-*.md"))
    assert reports and "build the paddle" in reports[0].read_text(encoding="utf-8")


def test_write_work_without_kaggle_asks_once_per_session(harness, monkeypatch, tmp_path):
    state, ws = harness
    from app import backend, kaggle
    key = tmp_path / "kaggle.json"
    key.write_text('{"username": "u", "key": "k"}', encoding="utf-8")
    monkeypatch.setattr(kaggle, "key_path", lambda: key)
    backend._prefs_file().unlink()
    backend.save_prefs(later_day=__import__("time").strftime("%Y-%m-%d"))  # not decided; already asked today
    asked = []
    monkeypatch.setattr(main.ui.menu, "choose", lambda console, q, opts, default=None: asked.append(q) or "no")
    _working_model(monkeypatch)  # D-074: Kaggle is offered after a turn that works, never for talk
    Inputs.script = ["write a test", "write another", "/mode plan", "explain it", "exit"]
    main._chat()
    assert len(asked) == 1 and "Kaggle GPU" in asked[0]


def _working_model(monkeypatch):
    """Every message is work: the decide call picks make_change, then the change phase answers."""
    from tests.test_chat_core import tc

    def fake(model, temperature=0.2, *, base_url=None, num_ctx=None, **kw):
        replies = []
        for i in range(10):
            replies += [AIMessage(content="", tool_calls=[tc("make_change", i, what="x")]),
                        AIMessage(content=f"done {i}")]
        m = Model(*replies)
        m.base_url, m.model = base_url, model
        return m

    monkeypatch.setattr(main, "get_local_llm", fake)


def _menu(monkeypatch, answer):
    asked = []
    monkeypatch.setattr(main.ui.menu, "choose", lambda console, q, opts, default=None: asked.append(
        (q, [k for k, _ in opts], default)) or answer)
    monkeypatch.setattr(main.sys.stdin, "isatty", lambda: True, raising=False)
    return asked


def _undecided():
    from app import backend
    backend._prefs_file().unlink()


def test_case1_no_key_asks_once_and_remembers_never(harness, monkeypatch):
    _undecided()
    asked = _menu(monkeypatch, "never")
    Inputs.script = ["exit"]
    main._chat()
    assert len(asked) == 1 and "free Kaggle GPU" in asked[0][0] and asked[0][1] == ["yes", "later", "never"]
    from app import backend
    assert backend.kaggle_use() == "never"
    asked.clear()
    Inputs.script = ["exit"]
    main._chat()
    assert asked == []


def test_case1_later_asks_again_only_on_another_day(harness, monkeypatch):
    _undecided()
    asked = _menu(monkeypatch, "later")
    for _ in range(2):
        Inputs.script = ["exit"]
        main._chat()
    assert len(asked) == 1


def _key_ready(monkeypatch, tmp_path, problem=""):
    from app import kaggle
    key = tmp_path / "k.json"
    key.write_text('{"username": "friend", "key": "k"}', encoding="utf-8")
    monkeypatch.setattr(kaggle, "key_path", lambda: key)
    monkeypatch.setattr(kaggle, "readiness", lambda **k: {"key": True, "ok": not problem, "user": "friend",
                                                          "left_h": 28.1, "total_h": 30.0, "refresh": None,
                                                          "problem": problem})
    started = []
    monkeypatch.setattr(kaggle, "start", lambda *a, **k: started.append(a))
    return started


def test_case2_key_works_asks_when_with_when_needed_first(harness, monkeypatch, tmp_path, capsys):
    _undecided()
    _key_ready(monkeypatch, tmp_path)
    asked = _menu(monkeypatch, "when-needed")
    Inputs.script = ["exit"]
    main._chat()
    q, keys, default = asked[0]
    assert "set up for friend" in q and "28.1 h left" in q
    assert keys == ["when-needed", "now", "later", "never"] and default == "when-needed"
    from app import backend
    assert backend.kaggle_use() == "when-needed"
    asked.clear()
    Inputs.script = ["exit"]
    main._chat()  # case 3: said yes: one line, no question
    out = " ".join(capsys.readouterr().out.split())
    assert asked == [] and "Kaggle ready · 28.1 h left · starts when you ask for work" in out


def test_case3_now_starts_in_the_background_at_start(harness, monkeypatch, tmp_path):
    from app import backend
    backend.save_prefs(kaggle_use="now")
    started = _key_ready(monkeypatch, tmp_path)
    Inputs.script = ["exit"]
    main._chat()
    import time as _t
    for _ in range(50):
        if started:
            break
        _t.sleep(0.05)
    assert started


def test_case4_a_problem_is_one_line_with_the_fix(harness, monkeypatch, tmp_path, capsys):
    from app import backend
    backend.save_prefs(kaggle_use="when-needed")
    _key_ready(monkeypatch, tmp_path, problem="Kaggle shows 0 GPU hours: verify your phone on kaggle.com → Settings")
    asked = _menu(monkeypatch, "now")
    Inputs.script = ["exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert asked == [] and "verify your phone" in out


def test_when_needed_starts_kaggle_on_write_work_without_asking(harness, monkeypatch, tmp_path):
    from app import backend
    backend.save_prefs(kaggle_use="when-needed")
    started = _key_ready(monkeypatch, tmp_path)
    asked = _menu(monkeypatch, "no")
    _working_model(monkeypatch)
    Inputs.script = ["/mode plan", "explain it", "/mode auto", "write a test", "exit"]
    main._chat()
    import time as _t
    for _ in range(50):
        if started:
            break
        _t.sleep(0.05)
    assert asked == [] and len(started) == 1


def test_ram_short_quietly_takes_the_smaller_laptop_model(harness, monkeypatch, capsys):
    state, ws = harness
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")
    monkeypatch.setattr(fit, "check", lambda m, c, **k: fit.Fit(
        "remote" if remote.active() and not k.get("local") else ("ok" if m == "qwen3.5:4b" else "no"),
        m, c, 1.0, 1.0, 3.0, -2.0))

    def kaggle_dies():
        state["up"] = False
        return "go on"

    Inputs.script = [kaggle_dies, "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert "→ laptop · qwen3.5:4b" in out and "RAM is short" in out
    assert state["llms"][-1][0] == "qwen3.5:4b"


def test_a_long_chat_is_compacted_before_moving_to_the_smaller_laptop_context(harness, monkeypatch, capsys):
    state, ws = harness
    config.save_context_choice("mimo-v2.6:9b", 131072)  # the laptop runs mimo at 128K (D-058)
    remote.set_remote(KAGGLE_URL, 262144, "kaggle")
    big = AIMessage(content="long answer", usage_metadata={"input_tokens": 200_000, "output_tokens": 50,
                                                           "total_tokens": 200_050})

    def fake_llm(model, temperature=0.2, *, base_url=None, num_ctx=None, **kw):
        state["llms"].append((model, base_url, num_ctx))
        m = Model(*([big] * 5))
        m.base_url, m.model = base_url, model
        return m

    monkeypatch.setattr(main, "get_local_llm", fake_llm)
    compacted = []
    monkeypatch.setattr(main, "_compact", lambda llm, msgs, *a, **k: compacted.append(k.get("reason")) or msgs[:1])

    def plan_mode_with_kaggle_up():
        return "/mode plan"

    Inputs.script = ["/do write a big feature", plan_mode_with_kaggle_up, "explain it", "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert compacted[:1] == ["backend"] and "too long for 128K" in out


# ── D-065 P3-P5 in the real chat loop ─────────────────────────────────────────

PLAN = """# Feature: score counter

## Goal
Count points.

## Tasks

### T1: score class
- Files: `tests/test_score.py`, `score.py`
- Do: test first, then the class.
- Done when: `python -m pytest -q tests/test_score.py` passes
- Needs: -
"""


def _planning_llm(state, monkeypatch):
    def fake_llm(model, temperature=0.2, *, base_url=None, num_ctx=None, **kw):
        state["llms"].append((model, base_url, num_ctx))
        m = Model(*[AIMessage(content=f"answer {i}") for i in range(20)])
        m.base_url, m.model = base_url, model
        m.invoke = lambda messages: AIMessage(content=PLAN)
        chat_stream = m.stream

        def stream(messages):  # the planner streams (F-078); the chat gets its scripted answers
            from app.core.planner import PLANNER_PROMPT
            if messages and str(messages[0].content).startswith(PLANNER_PROMPT[:60]):
                return iter([AIMessage(content=PLAN)])
            return chat_stream(messages)

        m.stream = stream
        return m

    monkeypatch.setattr(main, "get_local_llm", fake_llm)


def _fake_runner(monkeypatch, calls):
    from app.core import loop

    def run_plan(text, ws, llm, **kw):
        calls.append({"text": text, "git": kw.get("git")})
        return {"tasks": {"T1": {"status": "passed", "tests": "2 passed", "summary": "done"}}, "passed_tasks": 1,
                "total_tasks": 1, "final_tests": "2 passed", "final_tests_passed": True}

    monkeypatch.setattr(loop, "run_plan", run_plan)


def test_where_did_we_stop_is_answered_from_the_records_without_the_model(harness, monkeypatch, capsys):
    state, ws = harness
    runs = ws / ".codemitra" / "runs"
    runs.mkdir(parents=True)
    (runs / "chat-20261109.jsonl").write_text(
        '{"kind": "session"}\n{"kind": "turn_start", "turn": 1, "t": 1, "user": "add the score counter please"}\n'
        '{"kind": "turn_end", "turn": 1, "outcome": "tests_passed", "changed": []}\n', encoding="utf-8")
    monkeypatch.setattr(C_chat.ChatSession, "turn", lambda *a, **k: pytest.fail("the model was called"))
    Inputs.script = ["hi mitra where did we last stop", "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert "Where we stopped last time" in out and "add the score counter please" in out
    assert "no model call" in out


def test_a_big_request_is_planned_then_built_after_go(harness, monkeypatch, capsys):
    state, ws = harness
    (ws / "codemitra.toml").write_text('architecture = "router"\n', encoding="utf-8")  # D-071: router paths
    _planning_llm(state, monkeypatch)
    runs = []
    _fake_runner(monkeypatch, runs)
    asked = _menu(monkeypatch, "go")
    monkeypatch.setattr(C_chat.ChatSession, "turn", lambda *a, **k: pytest.fail("no plain turn for a big request"))
    Inputs.script = ["build a score system for the game with a high score file and a menu", "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    assert "planning it first" in out and "Feature: score counter" in out
    assert asked and asked[-1][0] == "Build this plan?" and asked[-1][2] == "go"
    assert runs and runs[0]["git"] is False and "### T1: score class" in runs[0]["text"]
    resume_note = (ws / ".codemitra" / "resume.md").read_text(encoding="utf-8")
    assert "T1 ✓ score class: 2 passed" in resume_note and "all tasks passed" in resume_note
    assert list(ws.glob("*.plan.md"))


def test_plan_command_and_save_for_a_night(harness, monkeypatch, capsys):
    state, ws = harness
    _planning_llm(state, monkeypatch)
    runs = []
    _fake_runner(monkeypatch, runs)
    _menu(monkeypatch, "save")
    Inputs.script = ["/plan add a score counter", "exit"]
    main._chat()
    out = " ".join(capsys.readouterr().out.split())
    saved = list(ws.glob("*.plan.md"))
    assert runs == [] and saved and f"/run {saved[0].name} 4" in out


def test_do_skips_planning(harness, monkeypatch):
    state, ws = harness
    _planning_llm(state, monkeypatch)
    turns = []
    real_turn = C_chat.ChatSession.turn
    monkeypatch.setattr(C_chat.ChatSession, "turn", lambda self, m, **k: turns.append(m[-1].content) or real_turn(self, m, **k))
    monkeypatch.setattr(main.ui.menu, "choose", lambda *a, **k: pytest.fail("no plan menu for /do"))
    Inputs.script = ["/do build a score system for the game with a high score file and a menu", "exit"]
    main._chat()
    assert turns == ["build a score system for the game with a high score file and a menu"]


def test_when_needed_does_not_start_kaggle_for_talk(harness, monkeypatch, tmp_path):
    """D-074: "hi mitra" is talk (the laptop answers): Kaggle hours are only spent once a turn does work."""
    from app import backend
    backend.save_prefs(kaggle_use="when-needed")
    started = _key_ready(monkeypatch, tmp_path)
    asked = _menu(monkeypatch, "no")
    Inputs.script = ["hi mitra", "good what about you", "exit"]   # the default model only talks
    main._chat()
    assert asked == [] and started == []
