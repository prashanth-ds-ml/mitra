"""Review batch B regressions: E-053 (night time limit), E-056 (night marks), E-058 (training per session),
E-059 (crash_hint on Windows stdlib frames), E-060 (append_file checks the whole file)."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.core import dashboard as D
from app.core import insights as I
from app.core import night as N
from app.core import tools as T


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd,
                          capture_output=True, text=True, timeout=30)


def _repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "game.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "start")
    return tmp_path


# ── E-053: the time limit kills the whole tree and keeps the cut-off task's work ──────────────────────────────

def test_e053_report_never_claims_a_rollback_at_the_time_limit(tmp_path):
    def rep(cut_off):
        return N.report(tmp_path, tmp_path / "plan.md", "m", 1, 0, 3600, None, True, tmp_path / "x.log", cut_off=cut_off)
    assert "rolled back" not in rep("stash") and "git stash" in rep("stash")
    assert "left in the folder (no git)" in rep("no git")
    assert "no unfinished changes" in rep("nothing")
    assert "git stash failed" in rep("left: You do not have the initial commit yet")


def test_e053_cut_off_work_is_stashed_and_codemitra_logs_stay(tmp_path):
    ws = _repo(tmp_path)
    (ws / "game.py").write_text("x = 2  # half done\n", encoding="utf-8")
    (ws / "new.py").write_text("y = 1\n", encoding="utf-8")
    (ws / ".codemitra").mkdir()
    (ws / ".codemitra" / "night-1.log").write_text("log\n", encoding="utf-8")
    assert N.save_cut_off(ws) == "stash"
    assert N.STASH_MESSAGE in _git(ws, "stash", "list").stdout
    assert (ws / "game.py").read_text(encoding="utf-8") == "x = 1\n" and not (ws / "new.py").exists()
    assert (ws / ".codemitra" / "night-1.log").exists()
    assert N.save_cut_off(ws) == "nothing"


def test_e053_no_git_leaves_the_work_in_place(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert N.save_cut_off(plain) == "no git" and (plain / "a.py").exists()


def test_e053_time_limit_kills_grandchildren_and_stashes(tmp_path, monkeypatch):
    psutil = pytest.importorskip("psutil")
    (tmp_path / "proj").mkdir()
    ws = _repo(tmp_path / "proj")
    (ws / "plan.md").write_text("### T1: x\n- Done when: `python -c 1` passes\n", encoding="utf-8")
    _git(ws, "add", "-A")
    _git(ws, "commit", "-q", "-m", "plan")
    pid_file = tmp_path / "grandchild.pid"
    script = (
        "import subprocess, sys, time, pathlib\n"
        f"pathlib.Path(r'{ws}', 'game.py').write_text('x = 2  # cut off\\n')\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        f"pathlib.Path(r'{pid_file}').write_text(str(g.pid))\n"
        "time.sleep(120)\n")
    monkeypatch.setattr(N, "solve_command", lambda *a: [sys.executable, "-c", script])
    monkeypatch.setattr(N, "keep_awake", lambda on: True)
    gpid = None
    try:
        code = N.run("plan.md", workspace=str(ws), hours=4 / 3600, echo=lambda s: None)
        gpid = int(pid_file.read_text())
        for _ in range(20):  # taskkill returns once it has asked; give the OS a moment
            if not psutil.pid_exists(gpid) or psutil.Process(gpid).status() == "zombie":
                break
            time.sleep(0.25)
        alive = psutil.pid_exists(gpid) and psutil.Process(gpid).status() != "zombie"
        assert not alive, "the solve run's own child (pytest / the app) survived the time limit"
        md = (ws / "NIGHT_REPORT.md").read_text(encoding="utf-8")
        assert code == 1 and "Stopped at the time limit" in md and "git stash" in md and "rolled back" not in md
        assert (ws / "game.py").read_text(encoding="utf-8") == "x = 1\n"
    finally:
        if gpid and psutil.pid_exists(gpid):
            try:
                psutil.Process(gpid).kill()
            except psutil.Error:
                pass


# ── E-056: your /good /bad on a night run is kept and shown ───────────────────────────────────────────────────

def _write_rows(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_e056_night_marks_reach_the_session_and_the_dashboard(tmp_path):
    now = time.time()
    rec = _write_rows(tmp_path / "proj" / ".codemitra" / "runs" / "chat-20261109.jsonl", [
        {"kind": "session", "t": now - 100, "model": "m"},
        {"kind": "turn_start", "t": now - 90, "turn": 1, "user": "start the night"},
        {"kind": "turn_end", "t": now - 80, "turn": 1, "outcome": "answered"},
        {"kind": "feedback", "t": now - 10, "of_turn": None, "of_night": str(tmp_path / "proj" / "plan.md"),
         "night_started": now - 70, "verdict": "bad", "note": "tests never ran", "author": "user"},
    ])
    sess = I.sessions([rec])
    assert [m["verdict"] for m in sess[0].night_marks] == ["bad"]
    assert sess[0].turns[0].verdict == ""  # not pinned on the turn
    html = D.render_more(sess, [], [], I.improvement(sess), I.training([rec]), days=I.trends(sess))
    assert "night run plan.md" in html and "tests never ran" in html
    assert "0 / 1" in html  # counted in the 👍 / 👎 headline


# ── E-058: training data per session, not per turn number across a daily file ─────────────────────────────────

def test_e058_two_sessions_in_one_file_keep_their_own_trajectories(tmp_path):
    rec = _write_rows(tmp_path / "proj" / ".codemitra" / "runs" / "chat-20261109.jsonl", [
        {"kind": "session", "t": 100.0},
        {"kind": "turn_start", "t": 101.0, "turn": 1, "user": "A"},
        {"kind": "turn_end", "t": 105.0, "turn": 1, "outcome": "tests_passed"},
        {"kind": "session", "t": 200.0},
        {"kind": "turn_start", "t": 201.0, "turn": 1, "user": "B"},
        {"kind": "turn_end", "t": 205.0, "turn": 1, "outcome": "tests_passed"},
    ])
    _write_rows(I.trace_file(rec), [
        {"kind": "call", "t": 103.0, "id": 1, "base": None, "turn": 1, "model": "m",
         "new": [{"role": "user", "content": "A"}], "reply": {"role": "assistant", "content": "did A"}},
        {"kind": "call", "t": 203.0, "id": 2, "base": None, "turn": 1, "model": "m",
         "new": [{"role": "user", "content": "B"}], "reply": {"role": "assistant", "content": "did B"}},
    ])
    out = tmp_path / "train.jsonl"
    assert I.export_training([rec], out) == 2
    firsts = sorted(json.loads(x)["messages"][0]["content"] for x in out.read_text(encoding="utf-8").splitlines())
    assert firsts == ["A", "B"]
    tr = I.training([rec])
    assert tr.usable == 2


def test_e058_a_session_without_traces_does_not_borrow_another_sessions_calls(tmp_path):
    rec = _write_rows(tmp_path / "proj" / ".codemitra" / "runs" / "chat-20261109.jsonl", [
        {"kind": "session", "t": 100.0},
        {"kind": "turn_start", "t": 101.0, "turn": 1, "user": "A"},
        {"kind": "turn_end", "t": 105.0, "turn": 1, "outcome": "tests_passed"},
        {"kind": "session", "t": 200.0},
        {"kind": "turn_start", "t": 201.0, "turn": 1, "user": "B (traces off)"},
        {"kind": "turn_end", "t": 205.0, "turn": 1, "outcome": "tests_passed"},
    ])
    _write_rows(I.trace_file(rec), [
        {"kind": "call", "t": 103.0, "id": 1, "base": None, "turn": 1, "model": "m",
         "new": [{"role": "user", "content": "A"}], "reply": {"role": "assistant", "content": "did A"}},
    ])
    tr = I.training([rec])
    assert tr.usable == 1 and any("no trace" in w for w in tr.reasons)


# ── E-059: crash_hint skips the standard library on Windows ──────────────────────────────────────────────────

def _tb(*frames):
    body = "".join(f'  File "{f}", line {n}, in x\n    pass\n' for f, n in frames)
    return "Traceback (most recent call last):\n" + body + "json.decoder.JSONDecodeError: Expecting value\n"


@pytest.mark.parametrize("stdlib", [
    r"C:\Users\prash\AppData\Local\Programs\Python\Python312\Lib\json\decoder.py",
    r"C:\Users\prash\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\json\decoder.py",
    "/usr/lib/python3.12/json/decoder.py",
    r"C:\proj\.venv\Lib\site-packages\pygame\x.py",
    "<frozen runpy>",
])
def test_e059_crash_hint_points_at_the_project_frame(stdlib):
    hint = T.crash_hint(_tb((r"C:\proj\breakout\game.py", 10), (stdlib, 355)))
    assert "game.py line 10" in hint


def test_e059_a_projects_own_lib_folder_still_counts():
    hint = T.crash_hint(_tb((r"C:\proj\game.py", 3), (r"C:\proj\lib\foo.py", 7)))
    assert "foo.py line 7" in hint


# ── E-060: append_file checks the whole file like write_file ──────────────────────────────────────────────────

def test_e060_append_file_warns_about_python_errors_in_the_finished_file(tmp_path):
    ws = T.Workspace(tmp_path, read_only=())
    T.write_file(ws, "game.py", "def run():\n    return 1\n")
    out = T.append_file(ws, "game.py", "def main():\n    return speed * 2\n")
    assert "will likely fail" in out and "speed" in out
    out = T.append_file(ws, "game.py", "def broken(:\n")
    assert "not valid Python" in out


def test_e060_append_file_still_checks_plans(tmp_path):
    ws = T.Workspace(tmp_path, read_only=())
    T.write_file(ws, "plan.md", "# Feature\n")
    out = T.append_file(ws, "plan.md", "### T1: a\n- Done when: `python -m pytest -q tests/test_a.py` passes\n")
    assert "runnable with /run" in out
