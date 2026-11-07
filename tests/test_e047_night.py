"""E-047 (the user's 2026-11-08 session) and the night launcher."""
import inspect
import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C
from app.core import night as N
from app.core import tools as T


def test_model_command_is_not_caught_by_mode():
    from app import main
    src = inspect.getsource(main._chat)
    assert 'if cmd == "/mode" or cmd.startswith("/mode "):' in src
    assert 'if cmd.startswith("/mode"):' not in src


def test_test_summary_is_pytests_result_line_not_a_trailing_warning():
    out = ("..F.\nFAILED tests/test_game.py::test_paddle - assert 1 == 2\n"
           "=================== 1 failed, 3 passed in 0.21s ===================\n"
           "  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))\n")
    assert T.test_summary(out) == "1 failed, 3 passed in 0.21s"
    assert T.test_summary("no tests ran in 0.01s") == "no tests ran in 0.01s"
    assert T.test_summary("weird tool output\nlast line") == "last line"


def test_connection_errors_are_recognised():
    assert C.is_connection_error(ConnectionResetError(10054, "An existing connection was forcibly closed"))
    assert C.is_connection_error(Exception("[WinError 10054] An existing connection was forcibly closed"))
    assert not C.is_connection_error(ValueError("XML syntax error"))


def test_a_lost_ollama_is_waited_for_and_the_step_retried(tmp_path, monkeypatch):
    calls = {"n": 0}

    class Model:
        model = "x"

        def bind_tools(self, specs):
            return self

        def stream(self, messages):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionResetError(10054, "An existing connection was forcibly closed by the remote host")
            return iter([AIMessage(content="back again")])

    monkeypatch.setattr(C, "wait_for_ollama", lambda base_url=None: True)
    shown = []
    hooks = C.Hooks(stream=lambda chunks, step=1: (lambda m: SimpleNamespace(
                        message=m, text=m.content, stopped=False, printed=True, seconds=0.1, thinking=""))(
                        next(iter(chunks))),
                    show=lambda *a: shown.append(a), confirm=lambda *a: True, run_shell=lambda c: ("", True),
                    web_search=lambda q: "", fetch_url=lambda u: "", mcp_find=lambda q: "", mcp_call=lambda *a: "")
    s = C.ChatSession(workspace=tmp_path, llm=Model(), hooks=hooks)
    res = s.turn([SystemMessage(content="s"), HumanMessage(content="hi")])
    assert res.text == "back again" and calls["n"] == 2 and shown[0][0] == "retry"


def test_input_box_reserves_no_empty_space():
    from app.ui import input as inp
    assert "reserve_space_for_menu=0" in inspect.getsource(inp)


def test_night_builds_the_solve_command_with_write_tests():
    cmd = N.solve_command(N.Path("plan.md"), N.Path("C:/proj"), "qwen3.5:latest", True)
    assert cmd[1:4] == ["-m", "app.main", "solve"] and "--write-tests" in cmd and "--json" in cmd
    assert cmd[cmd.index("--model") + 1] == "qwen3.5:latest"
    assert "--write-tests" not in N.solve_command(N.Path("p.md"), N.Path("."), "", False)


def test_night_report_lists_tasks_branch_and_how_to_play(tmp_path):
    (tmp_path / "breakout").mkdir()
    result = {"passed_tasks": 2, "total_tasks": 3, "final_tests": "5 passed", "final_tests_passed": False,
              "tasks": {"T1": {"status": "passed", "tests": "3 passed", "summary": "state"},
                        "T2": {"status": "failed", "tests": "1 failed", "summary": "paddle"}},
              "needs_help": ["T2: paddle edge"]}
    md = N.report(tmp_path, tmp_path / "plan.md", "qwen3.5:latest", 4, 0, 3600, result, False, tmp_path / "x.log")
    assert "Tasks: 2/3 passed" in md and "✓ T1" in md and "✗ T2" in md and "Needs help" in md
    assert "python -m breakout.app" in md and "/good" in md
    cut = N.report(tmp_path, tmp_path / "plan.md", "m", 1, 0, 3600, None, True, tmp_path / "x.log")
    assert "Stopped at the time limit" in cut


def test_night_run_with_a_fake_solve_writes_the_report(tmp_path, monkeypatch):
    (tmp_path / "plan.md").write_text("### T1: x\n- Done when: `python -c 1` passes\n", encoding="utf-8")
    fake = {"passed_tasks": 1, "total_tasks": 1, "final_tests": "1 passed", "final_tests_passed": True,
            "tasks": {"T1": {"status": "passed", "tests": "1 passed", "summary": "ok"}}, "needs_help": []}
    monkeypatch.setattr(N, "solve_command", lambda *a: ["python", "-c", f"print({json.dumps(json.dumps(fake))})"])
    monkeypatch.setattr(N, "keep_awake", lambda on: True)
    out = []
    code = N.run("plan.md", workspace=str(tmp_path), hours=0.01, echo=out.append)
    assert code == 0 and (tmp_path / "NIGHT_REPORT.md").exists()
    assert "Tasks: 1/1 passed" in (tmp_path / "NIGHT_REPORT.md").read_text(encoding="utf-8")


def test_run_command_is_wired_in_the_chat():
    from app import main
    src = inspect.getsource(main._chat)
    assert '"night", str(plan_path)' in src and "CREATE_NEW_CONSOLE" in src
