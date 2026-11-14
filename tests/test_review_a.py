"""Deep-dive review 2026-11-09, batch A: E-054, E-055, E-057, E-061, E-062, E-063, E-064."""
import io

from langchain_core.messages import AIMessage

from app import config
from app.core import chat as C
from app.core import plans
from app.core import roles
from app.main import _utf8_streams
from tests.test_chat_core import GOOD_PLAN, Model, call, fake_hooks, msgs, tc


def test_a_plan_in_a_subfolder_shares_the_turn_journal(tmp_path, monkeypatch):
    """E-064: the plan's own Workspace had its own journal, so /undo and the corrections check missed its changes."""
    (tmp_path / "game").mkdir()
    (tmp_path / "game" / "plan.md").write_text(GOOD_PLAN, encoding="utf-8")

    def fake_run_plan(text, ws, llm, **kw):
        ws.journal.append({"kind": "create_file", "path": str(ws.root / "calc.py"), "existed": False})
        return {"tasks": {}, "passed_tasks": 1, "total_tasks": 1, "final_tests_passed": True, "final_tests": "ok"}

    monkeypatch.setattr(C.core_loop, "run_plan", fake_run_plan)
    model = Model(call(tc("run_plan", 1, plan_path="game/plan.md")), AIMessage(content="done"))
    hooks, _ = fake_hooks()
    res = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="auto").turn(msgs("run it"))
    assert [e["path"] for e in res.journal] == [str((tmp_path / "game").resolve() / "calc.py")]


def test_a_role_cannot_run_a_tool_outside_its_set(tmp_path):
    """E-055: the role's tools were only hidden from the model; a call it named anyway still ran."""
    model = Model(call(tc("write_file", 1, path="x.py", content="x = 1\n")), AIMessage(content="ok"))
    hooks, shown = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="auto")
    session.apply_route(roles.route("reviewer", {}, have=set()))
    session.turn(msgs("write x.py"))
    assert not (tmp_path / "x.py").exists()
    assert shown[0][1] is False and "not available to the reviewer role" in shown[0][2]


def test_model_use_beats_local_model_in_codemitra_toml():
    """E-054: `/model use X` saved the last model, but codemitra.toml local_model (and an older chat choice) won."""
    cfg = {"local_model": "qwen3.5:4b"}
    have = {"qwen3.5:4b", "deepseek-r1:8b", "mimo-v2.6:9b"}
    roles.save_choice("chat", "mimo-v2.6:9b")
    roles.use_for_chat("deepseek-r1:8b")
    assert roles.resolve("chat", cfg, have)[0] == "deepseek-r1:8b"
    assert config.load_last_model() == "deepseek-r1:8b"


def test_context_auto_gives_the_same_size_as_a_restart(monkeypatch):
    """E-061: `/context auto` gave the measured 128K now but the model's 256K maximum after a restart."""
    facts = {"context": 262_144, "parameters": 4_000_000_000, "capabilities": ["completion", "tools"]}
    monkeypatch.setattr(config, "get_model_facts", lambda name: facts)
    config.save_context_choice("qwen3.5:4b", 131_072)
    now, err = roles.choose_context("qwen3.5:4b", "auto", {})
    assert err == "" and now == roles.route("chat", {"local_model": "qwen3.5:4b"}, have=set())["num_ctx"] == 262_144
    assert roles.choose_context("qwen3.5:4b", "128k", {}) == (131_072, "")
    assert roles.choose_context("qwen3.5:4b", "1m", {})[1]


def test_files_a_night_will_change_are_not_counted_as_your_corrections(tmp_path):
    """E-057: a /run night rewrote a file CodeMitra had left; the next turn recorded it as the user's correction."""
    (tmp_path / "game").mkdir()
    game, other = tmp_path / "game" / "game.py", tmp_path / "notes.py"
    for f in (game, other):
        f.write_text("old\n", encoding="utf-8")
    hooks, _ = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=Model(AIMessage(content="hi")), hooks=hooks, mode="auto")
    session._remember_left([{"path": str(game)}, {"path": str(other)}])
    session.night_started(tmp_path / "game" / "plan.md", 1.0)
    game.write_text("night wrote this\n", encoding="utf-8")
    other.write_text("you wrote this\n", encoding="utf-8")
    assert session._check_corrections(of_turn=1) == 1 and session.noticed == ["notes.py"]
    assert session.last_night["plan"].endswith("plan.md")


def test_redirected_output_takes_any_character():
    """E-062: `codemitra night ... > night.log` crashed on the first ✗ (cp1252 file output on Windows)."""
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    _utf8_streams([stream])
    stream.write("✗ The plan cannot run ✓")
    stream.flush()
    assert raw.getvalue().decode("utf-8") == "✗ The plan cannot run ✓"


def test_the_same_plan_problem_is_named_once_with_its_tasks():
    """E-063: one folder-prefix mistake in 5 tasks gave 5 copies of the message (and hid others past the 5th)."""
    tasks = "".join(f"### T{i}: t{i}\n- Done when: `python -m pytest -q game/tests/test_{i}.py` passes\n- Needs: -\n\n"
                    for i in range(1, 7))
    n, problem = plans.check_text("# Feature: x\n\n## Tasks\n\n" + tasks + "### T7: t7\n- Done when: `pytest -q` passes\n"
                                  "- Needs: T7\n", "game")
    assert n == 7
    assert problem.count("paths are relative") == 1 and "T1, T2, T3, T4, T5, T6: paths" in problem
    assert "T7: write `python -m pytest" in problem and "T7 needs itself" in problem and "more" not in problem
