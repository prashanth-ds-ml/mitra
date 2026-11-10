"""D-065 P1 (resume brief) and P2 (outlines instead of whole large files)."""
import json
import subprocess

from app.core import resume
from app.core import tools as T


# ── P1 ────────────────────────────────────────────────────────────────────────

def _records(ws, rows, name="chat-20261110.jsonl"):
    runs = ws / ".mitra" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / name).write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_the_brief_shows_recent_work_not_chit_chat(tmp_path):
    _records(tmp_path, [
        {"kind": "session"},
        {"kind": "turn_start", "turn": 1, "t": 1, "user": "add a score counter to the game"},
        {"kind": "turn_end", "turn": 1, "outcome": "tests_passed", "changed": ["C:/p/game/score.py"]},
        {"kind": "session"},
        {"kind": "turn_start", "turn": 1, "t": 2, "user": "hi mitra"},
        {"kind": "turn_end", "turn": 1, "outcome": "answered"},
        {"kind": "turn_start", "turn": 2, "t": 3, "user": "where did we last stop"},
        {"kind": "turn_end", "turn": 2, "outcome": "interrupted"},
        {"kind": "turn_start", "turn": 3, "t": 4, "user": "fix the paddle bounce please"},
        {"kind": "turn_end", "turn": 3, "outcome": "interrupted", "changed": []},
    ])
    text = resume.brief(tmp_path)
    assert text.startswith("## Where we stopped last time")
    assert "add a score counter to the game → ✓ tests passed (score.py)" in text
    assert "hi mitra" not in text and "where did we last stop" not in text and "paddle bounce" not in text


def test_the_brief_includes_plan_night_report_and_git(tmp_path):
    (tmp_path / ".mitra").mkdir()
    (tmp_path / ".mitra" / "resume.md").write_text("# Plan: brick breaker\n- T1 ✓ paddle\n- T2 ✗ ball: next\n",
                                                   encoding="utf-8")
    (tmp_path / "game").mkdir()
    (tmp_path / "game" / "NIGHT_REPORT.md").write_text("# Night report\n\n## Tasks: 2/5 passed\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m",
                    "start the game"], cwd=tmp_path, check=True)
    (tmp_path / "loose.py").write_text("x = 1\n", encoding="utf-8")
    text = resume.brief(tmp_path)
    for needed in ("**Last plan**", "T2 ✗ ball: next", "game/NIGHT_REPORT.md", "Tasks: 2/5 passed",
                   "start the game", "**Uncommitted:**", "loose.py"):
        assert needed in text, needed


def test_a_new_project_has_no_brief(tmp_path):
    assert resume.brief(tmp_path) == ""


def test_resume_questions_are_recognised():
    for q in ("hi mitra where did we last stop", "Where were we?", "can we pick up where we left off"):
        assert resume.is_resume_question(q), q
    assert not resume.is_resume_question("add a test for the paddle")


# ── P2 ────────────────────────────────────────────────────────────────────────

def _big_py(n_funcs=40):
    body = ['"""A big module."""', "import os", ""]
    for i in range(n_funcs):
        body += [f"def f{i}(a, b=1):", f"    return a + b + {i}", "", ""]
    body += ["class Game:", "    def update(self, dt):", "        pass", ""]
    return "\n".join(body) + "\n"


def test_a_large_file_gives_its_outline_first(tmp_path):
    (tmp_path / "big.py").write_text(_big_py(), encoding="utf-8")
    ws = T.Workspace(tmp_path)
    out = T.read_file(ws, "big.py")
    assert "large, so its outline first" in out and "Outline (line : definition):" in out
    assert "   4 : def f0(a, b=1)" in out and ": class Game" in out and ":     def update(self, dt)" in out
    assert "return a + b + 30" not in out  # the bodies are not sent
    part = T.read_file(ws, "big.py", start=4, end=6)
    assert "def f0(a, b=1):" in part and "return a + b + 0" in part
    assert "big.py" in ws.seen  # edits after an outline read are allowed


def test_small_files_and_markdown(tmp_path):
    (tmp_path / "small.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "plan.md").write_text("# Plan\n" + "\n".join(f"line {i}" for i in range(200)) + "\n## Tasks\n",
                                      encoding="utf-8")
    ws = T.Workspace(tmp_path)
    assert "   1 | x = 1" in T.read_file(ws, "small.py")
    md = T.read_file(ws, "plan.md")
    assert "   1 : # Plan" in md and ": ## Tasks" in md
