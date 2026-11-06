"""E-033: model commands like `cd X && python -m pytest`, Git Bash paths, and a guard that sees shell failures."""
import pathlib
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import ui
from app.agents import shell
from app.agents.limits import RepeatGuard


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "game" / "tests").mkdir(parents=True)
    (tmp_path / "game" / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    shell.configure(workspace=str(tmp_path), allowed_roots=[str(tmp_path)], stream_to_console=False, confirm_fn=None,
                    session_mode="auto")
    yield tmp_path
    shell.configure(workspace=None, allowed_roots=[])


def test_split_chain():
    assert shell.split_chain("pytest -q") is None
    assert shell.split_chain("cd game && python -m pytest -q") == ["cd game", "python -m pytest -q"]
    assert shell.split_chain("cd game") is None          # the built-in cd, which also moves the session folder


@pytest.mark.skipif(sys.platform != "win32", reason="Git Bash paths are a Windows thing")
def test_git_bash_paths_become_windows_paths():
    assert shell.unix_to_windows_path("/c/Users/prash/x") == "C:/Users/prash/x"
    assert shell.unix_to_windows_path("/tmp") == "/tmp"


def test_cd_and_then_the_command_runs_in_that_folder(ws, monkeypatch):
    """The user's session: `cd .../brick-breaker && python -m pytest ...` failed 30+ times."""
    monkeypatch.setattr("app.core.tools.project_python", lambda root: sys.executable)
    r = shell.execute("cd game && python -m pytest -q tests", cwd=str(ws))
    assert r.ok, r.output
    assert "1 passed" in r.output and pathlib.Path(r.cwd) == (ws / "game").resolve()


@pytest.mark.skipif(sys.platform != "win32", reason="Git Bash paths are a Windows thing")
def test_cd_with_a_git_bash_absolute_path(ws, monkeypatch):
    monkeypatch.setattr("app.core.tools.project_python", lambda root: sys.executable)
    p = str((ws / "game").resolve()).replace("\\", "/")
    bash_style = "/" + p[0].lower() + p[2:]
    r = shell.execute(f"cd {bash_style} && python -m pytest -q tests", cwd=str(ws))
    assert r.ok, r.output


def test_cd_outside_the_workspace_is_refused(ws):
    r = shell.execute("cd .. && python --version", cwd=str(ws))
    assert not r.ok and r.output.startswith("✗")


def test_pipes_are_refused_with_a_reason(ws):
    r = shell.execute("python -m pytest | findstr passed", cwd=str(ws))
    assert not r.ok and "Pipes and redirects" in r.output


def test_failed_command_shows_why():
    r = SimpleNamespace(exit_code=1, output_lines=["collected 0 items", "ERROR: file or directory not found: tests/x"],
                        denied=False, timed_out=False, hidden_lines=0)
    assert "file or directory not found: tests/x" in ui.shell_done(r).plain


def test_the_same_failing_command_is_stopped():
    g = RepeatGuard(max_repeats=2, max_failures=4)
    cmd = {"command": "cd x && python -m pytest"}
    outcomes = []
    for _ in range(6):  # 2 failures, then refused repeats; the 4th refusal stops the turn
        refused = g.before("run_command", cmd)
        out = refused or "Command: ... [FAILED]"
        outcomes.append(g.after("run_command", out, ok=False if not refused else None))
    assert refused and "already called" in refused                       # 3rd identical run refused
    assert any(o and "Stopped" in o for o in outcomes)


def test_shell_failures_count_even_without_a_cross():
    g = RepeatGuard(max_repeats=9, max_failures=3)
    results = [g.after("run_command", f"Command: try {i}\n[FAILED]", ok=False) for i in range(3)]
    assert results[-1] and "failed 3 times in a row" in results[-1]


def test_a_command_may_repeat_after_a_file_changed():
    g = RepeatGuard(max_repeats=1)
    assert g.before("run_command", {"command": "pytest"}) is None
    assert g.before("run_command", {"command": "pytest"}) is not None
    g.after("edit_file", "Edited a.py.", ok=True)
    assert g.before("run_command", {"command": "pytest"}) is None
