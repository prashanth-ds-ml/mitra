"""Core loop upgrades: text tool calls, call timeout, fresh rounds, rollback, plan runner on git, replay, thinking."""
import json
import pathlib
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage

from app.core import loop as L
from app.core import tools as T
from app.core.parse import text_tool_calls
from app.core.replay import ReplayModel
from app.llm import thinking_setting

KNOWN = {s["name"] for s in T.TOOL_SPECS}
GOOD = "def add(a, b):\n    return a + b\n"
BAD = "def add(a, b):\n    return a - b\n"


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(
        "def test_add():\n    from calc import add\n    assert add(2, 3) == 5\n", encoding="utf-8")
    w = T.Workspace(tmp_path, test_command="python -m pytest -q tests")
    return w


class Scripted:
    def __init__(self, *replies, delay=0.0):
        self.replies, self.calls, self.seen, self.delay = list(replies), 0, [], delay

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        self.seen.append(list(messages))
        if self.delay:
            time.sleep(self.delay)
        return self.replies.pop(0) if self.replies else AIMessage(content="")


def tc(name, n, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{n}"}])


# ── tool calls written as text ──────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    '{"name": "run_tests", "arguments": {}}',
    'I will run them now.\n<tool_call>{"name": "run_tests", "arguments": {}}</tool_call>',
    '```json\n{"tool": "run_tests", "parameters": {}}\n```',
    '{"function": {"name": "run_tests", "arguments": "{}"}}',
])
def test_text_tool_calls_are_found(text):
    calls, err = text_tool_calls(text, KNOWN)
    assert [c["name"] for c in calls] == ["run_tests"] and err == ""


def test_prose_and_unknown_tools_are_not_calls():
    assert text_tool_calls("The dict {a: 1} is fine.", KNOWN) == ([], "")
    assert text_tool_calls('{"name": "rm_rf", "arguments": {}}', KNOWN) == ([], "")


def test_broken_text_call_gets_an_error_back():
    calls, err = text_tool_calls('<tool_call>{"name": "read_file", "arguments": {path: x}}</tool_call>', KNOWN)
    assert calls == [] and "not valid JSON" in err


def test_loop_runs_a_call_written_as_text(ws):
    model = Scripted(
        AIMessage(content='{"name": "write_file", "arguments": {"path": "calc.py", "content": %s}}' % json.dumps(GOOD)),
        AIMessage(content='<tool_call>{"name": "run_tests", "arguments": {}}</tool_call>'),
    )
    res = L.solve("make add work", ws, model)
    assert res.status == "passed" and res.steps == 2


def test_loop_tells_the_model_its_text_call_was_broken(ws):
    model = Scripted(AIMessage(content='<tool_call>{"name": "run_tests", "arguments": {oops}}</tool_call>'),
                     tc("write_file", 2, path="calc.py", content=GOOD), tc("run_tests", 3))
    res = L.solve("x", ws, model)
    assert res.status == "passed"
    assert "not valid JSON" in model.seen[1][-1].content


# ── a stalled model ─────────────────────────────────────────────────────────

def test_a_stalled_model_call_times_out(ws):
    model = Scripted(delay=3)
    t0 = time.monotonic()
    res = L.solve("x", ws, model, call_timeout=0.3)
    assert res.status == "error" and model.calls == 2
    assert time.monotonic() - t0 < 6


# ── fresh round with a handoff note ─────────────────────────────────────────

def test_fresh_round_after_repeated_failures_keeps_files_and_hands_off(ws):
    model = Scripted(
        tc("write_file", 1, path="calc.py", content=BAD),
        tc("run_tests", 2), tc("search", 3, pattern="add"), tc("run_tests", 4), tc("list_files", 5),
        tc("run_tests", 6),                       # 3rd failing run -> fresh round
        tc("read_file", 7, path="calc.py"),
        tc("edit_file", 8, path="calc.py", old="return a - b", new="return a + b"),
        tc("run_tests", 9),
    )
    events = []
    res = L.solve("make add work", ws, model, on_event=events.append, fresh_round_after=3)
    assert res.status == "passed"
    assert any(e.kind == "note" and "fresh round 2" in e.data["text"] for e in events)
    first_of_round_2 = model.seen[6]
    assert len(first_of_round_2) == 2 and "round 2" in first_of_round_2[1].content
    assert "calc.py" in first_of_round_2[1].content and "1 failed" in first_of_round_2[1].content


def test_rounds_run_out(ws):
    model = Scripted(tc("write_file", 1, path="calc.py", content=BAD),
                     *[tc("run_tests", n) if n % 2 else tc("search", n, pattern=f"p{n}") for n in range(2, 30)])
    res = L.solve("x", ws, model, fresh_round_after=2, max_rounds=2)
    assert res.status == "failed" and "after 2 rounds" in res.summary


# ── rollback ────────────────────────────────────────────────────────────────

def test_rollback_restores_files_when_the_task_fails(ws):
    (ws.root / "keep.py").write_text("original\n", encoding="utf-8")
    model = Scripted(tc("read_file", 1, path="keep.py"), tc("write_file", 2, path="keep.py", content="changed\n"),
                     tc("write_file", 3, path="calc.py", content=BAD),
                     *[tc("finish", n, summary="done") for n in range(4, 8)])
    res = L.solve("x", ws, model, rollback=True)
    assert res.status == "failed" and "Rolled back 2" in res.summary
    assert (ws.root / "keep.py").read_text() == "original\n" and not (ws.root / "calc.py").exists()


# ── plan runner: branch, commits, needs-help, report ────────────────────────

PLAN = """# Feature: calc

## Design notes
- `calc.py` has `add` and `sub`.

## Tasks

### T1: add
- Do: add(a, b)
- Done when: `python -m pytest -q tests/test_calc.py` passes
- Needs: -

### T2: sub
- Do: sub(a, b)
- Done when: `python -m pytest -q tests/test_sub.py` passes
- Needs: -
"""


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_plan_runs_on_a_branch_commits_each_task_and_writes_needs_help(ws, tmp_path):
    (ws.root / "tests" / "test_sub.py").write_text(
        "def test_sub():\n    from calc import sub\n    assert sub(5, 3) == 2\n", encoding="utf-8")
    git(ws.root, "init", "-q", "-b", "main")
    git(ws.root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(ws.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "start")
    git(ws.root, "config", "user.email", "t@t")
    git(ws.root, "config", "user.name", "t")
    model = Scripted(
        tc("write_file", 1, path="calc.py", content=GOOD), tc("run_tests", 2),            # T1 passes
        tc("read_file", 3, path="calc.py"),
        tc("edit_file", 4, path="calc.py", old="return a + b", new="return a + b\n\n\ndef sub(a, b):\n    return a + b"),
        *[tc("finish", n, summary="done") for n in range(5, 9)],                           # T2 fails
    )
    out = L.run_plan(PLAN, ws, model, full_test_command="python -m pytest -q tests", record_dir=tmp_path / "runs")
    assert out["branch"].startswith("codemitra/plan-") and git(ws.root, "branch", "--show-current") == out["branch"]
    assert out["tasks"]["T1"]["status"] == "passed" and out["tasks"]["T2"]["status"] == "failed"
    assert out["commits"]["T1"] and "mitra: T1 add" in git(ws.root, "log", "-1", "--format=%s")
    assert "def sub" not in (ws.root / "calc.py").read_text()          # T2's edit was rolled back
    assert "T2: sub: needs help" in out["needs_help"][0]
    assert (tmp_path / "runs" / "report.json").exists() and (tmp_path / "runs" / "needs-help.md").exists()
    assert git(ws.root, "log", "main", "-1", "--format=%s") == "start"   # main untouched


def test_plan_without_git_still_runs(ws):
    model = Scripted(tc("write_file", 1, path="calc.py", content=GOOD), tc("run_tests", 2))
    out = L.run_plan(PLAN.split("### T2")[0], ws, model, full_test_command="python -m pytest -q tests/test_calc.py")
    assert out["branch"] == "" and out["passed_tasks"] == 1 and out["final_tests_passed"]


# ── record / replay ─────────────────────────────────────────────────────────

def test_a_recorded_run_replays_without_ollama(ws, tmp_path):
    rec = tmp_path / "run.jsonl"
    live = Scripted(tc("list_files", 1), tc("write_file", 2, path="calc.py", content=GOOD), tc("run_tests", 3))
    first = L.solve("make add work", ws, live, record_path=rec)
    (ws.root / "calc.py").unlink()
    ws.seen.clear()
    replayed = L.solve("make add work", ws, ReplayModel(rec))
    assert first.status == replayed.status == "passed" and replayed.steps == first.steps


# ── thinking setting ────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [("on", True), ("off", False), ("auto", "auto"), (None, "auto")])
def test_thinking_setting(value, expected):
    assert thinking_setting(value) == expected


def test_repeat_guard_allows_rerunning_tests_and_rereading_after_an_edit():
    """E-026: run_tests is always called with {} and was refused on its 3rd run; re-reading an edited file too."""
    from app.agents.limits import RepeatGuard
    g = RepeatGuard(max_repeats=1)
    assert all(g.before("run_tests", {}) is None for _ in range(5))
    assert g.before("read_file", {"path": "a.py"}) is None
    assert g.before("read_file", {"path": "a.py"}) is not None          # a real repeat
    g.after("edit_file", "Edited a.py.")
    assert g.before("read_file", {"path": "a.py"}) is None              # the file changed


def test_run_records_are_scrubbed(ws, tmp_path):
    """D-022: a secret the model reads or writes never lands in .codemitra/runs."""
    token = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    (ws.root / "config.txt").write_text(f"GITHUB_TOKEN={token}\n", encoding="utf-8")
    model = Scripted(tc("read_file", 1, path="config.txt"), tc("write_file", 2, path="calc.py", content=GOOD),
                     tc("run_tests", 3))
    rec = tmp_path / "run.jsonl"
    L.solve("x", ws, model, record_path=rec)
    text = rec.read_text(encoding="utf-8")
    assert token not in text and "***" in text


def test_tests_run_with_the_projects_python(tmp_path, monkeypatch):
    """E-028: installed as a command, CodeMitra's own Python had no pytest; prefer the project's venv, then PATH."""
    venv_py = tmp_path / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("", encoding="utf-8")
    assert T.project_python(tmp_path) == str(venv_py)
    other = tmp_path / "plain"
    other.mkdir()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/python-with-pytest" if name == "python" else None)
    monkeypatch.setattr(T, "_has_pytest", lambda p: True)
    assert T.project_python(other) == "/usr/bin/python-with-pytest"
    monkeypatch.setattr(T, "_has_pytest", lambda p: False)
    assert T.project_python(other) == sys.executable
