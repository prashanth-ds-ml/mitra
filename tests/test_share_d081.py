"""D-081: share your sessions (light + scrubbed), push them to a logs repo, and pull everyone's into the store where
CodeMitra's own learning round (and, only when needed, the coach) reads them."""
import json
import subprocess
from pathlib import Path

import pytest

from app.core import share as SH
from app.core import store


def _record(ws: Path, rows: list[dict]) -> Path:
    path = store.runs_root() / "mitra-try-54b64f" / "chat-20261113.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


WS = "C:\\Users\\ravi\\projects\\mitra-try"
ROWS = [
    {"t": 1.0, "kind": "session", "workspace": WS, "model": "qwen3.5:latest", "num_ctx": 262144, "code_version": "abc"},
    {"t": 2.0, "kind": "turn_start", "turn": 1, "user": "fix the maze, my token is ghp_" + "a" * 36 + " mail ravi@x.com",
     "author": "mitra"},
    {"t": 3.0, "kind": "tool", "turn": 1, "step": 1, "name": "read_file", "ok": True,
     "args": {"path": WS + "\\neon_chomp\\maze.py"}, "output": "SECRET FILE CONTENT line 1\nline 2"},
    {"t": 4.0, "kind": "tool", "turn": 1, "step": 2, "name": "edit_file", "ok": True,
     "args": {"path": "neon_chomp/maze.py", "old": "PELLETS = 215", "new": "PELLETS = 214"}, "output": "Edited."},
    {"t": 5.0, "kind": "tool", "turn": 1, "step": 3, "name": "run_tests", "ok": False, "args": {"folder": "neon_chomp"},
     "output": "FAILED (in neon_chomp/): x\n\n=== 1 failed, 4 passed in 0.5s ==="},
    {"t": 6.0, "kind": "turn_end", "turn": 1, "text": "Fixed C:\\Users\\ravi\\projects\\mitra-try\\neon_chomp\\maze.py",
     "outcome": "tests_failed", "changed": [WS + "\\neon_chomp\\maze.py"], "seconds": 30},
    {"t": 7.0, "kind": "turn_start", "turn": 2, "user": "why dont you run it", "author": "mitra"},
    {"t": 8.0, "kind": "signal", "of_turn": 1, "signal": "unhappy", "why": "why dont", "auto": True},
    {"t": 9.0, "kind": "turn_end", "turn": 2, "text": "Sorry.", "outcome": "answered"},
    {"t": 10.0, "kind": "session_rating", "stars": 2, "turns": 2},
]


@pytest.fixture
def scrub():
    return SH.scrubber(user="ravi", home="C:\\Users\\ravi")


def test_scrubbing_removes_tokens_emails_home_and_user(scrub):
    s = scrub("ghp_" + "a" * 36 + " sk-abcdefghijklmnopqrst ravi@x.com C:\\Users\\ravi\\x and /c/users/ravi/y by ravi "
              "password=hunter2 KGAT_0123456789abcd")
    for leaked in ("ghp_", "sk-abc", "ravi@", "C:\\Users", "/c/users", " ravi", "hunter2", "KGAT_"):
        assert leaked not in s, leaked
    assert "[secret]" in s and "[email]" in s and "~" in s and "[user]" in s


def test_the_light_copy_has_no_file_contents_or_paths(tmp_path, scrub):
    _record(tmp_path, ROWS)
    sess = SH.sessions(store.stored_files())
    assert len(sess) == 1 and sess[0]["turns"] == 2 and sess[0]["labels"] == 2
    rows = SH.light(sess[0]["rows"], scrub, "p-abc123", "ravi")
    text = json.dumps(rows)
    for leaked in ("SECRET FILE CONTENT", "PELLETS = 215", "PELLETS = 214", "C:\\\\Users", "ghp_", "ravi@x.com",
                   "\"workspace\""):
        assert leaked not in text, leaked
    tools = [r for r in rows if r["kind"] == "tool"]
    assert tools[0]["args"] == {"path": "neon_chomp/maze.py"} and "output" not in tools[0]     # a read: no content
    assert tools[2]["output"] == "1 failed, 4 passed in 0.5s"                                 # tests: the summary
    end = [r for r in rows if r["kind"] == "turn_end"][0]
    assert end["changed"] == ["neon_chomp/maze.py"]
    assert {r["kind"] for r in rows} >= {"session", "turn_start", "turn_end", "tool", "signal", "session_rating"}
    assert all(r["shared_by"] == "ravi" for r in rows)


def test_a_session_is_shared_once(tmp_path):
    _record(tmp_path, ROWS)
    todo = SH.unshared(store.stored_files())
    ok, msg, files = SH.share(todo, do_push=False, friend="ravi")
    assert ok and files[0].is_file() and files[0].name.startswith("chat-")
    assert SH.unshared(store.stored_files()) == []


def _git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _logs_repo(tmp_path) -> Path:
    """A bare repo standing in for prashanth-ds-ml/codemitra-logs."""
    bare = tmp_path / "codemitra-logs.git"
    _git("init", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    _git("clone", str(bare), str(seed))
    (seed / "README.md").write_text("# logs\n", encoding="utf-8")
    _git("-c", "user.email=t@t", "-c", "user.name=t", "add", ".", cwd=seed)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init", cwd=seed)
    _git("push", "origin", "HEAD:main", cwd=seed)
    return bare


def test_push_then_pull_brings_a_friends_session_into_the_store(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t"), monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@t")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t"), monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@t")
    bare = _logs_repo(tmp_path)
    SH.save_settings(repo=str(bare), name="Ravi K", at_exit="ask")
    _record(tmp_path, ROWS)
    ok, msg, files = SH.share(SH.unshared(store.stored_files()), do_push=True)
    assert ok, msg
    assert "people/ravi-k/" in msg
    listed = subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main"],
                            capture_output=True, text=True).stdout
    assert f"people/ravi-k/{files[0].name}" in listed
    # the maintainer's side (here: same store, fresh checkout)
    SH.rmtree(SH.folder() / "repo")
    n, msg = SH.pull()
    assert n == 1 and "1 people" in msg
    got = store.runs_root() / "shared-ravi-k" / files[0].name
    assert got.is_file()
    assert SH.pull()[0] == 0                                         # once only
    assert SH.unshared(store.stored_files()) == []                   # a friend's session is never re-shared


def test_shared_sessions_feed_codemitras_own_learning(tmp_path, monkeypatch):
    """D-082 (user): CodeMitra learns by itself first; a friend's unhappy turn is evidence for its own round."""
    from app.core import improve_chat as IC
    dest = store.runs_root() / "shared-ravi" / "chat-20261113-1200-p-abc123-x.jsonl"
    dest.parent.mkdir(parents=True)
    rows = SH.light(ROWS, SH.scrubber(user="ravi", home="C:\\Users\\ravi"), "p-abc123", "ravi")
    dest.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    found = IC.conversation_signals([dest])
    assert found and found[0]["signal"] == "unhappy" and found[0]["next"] == "why dont you run it"


def test_the_coach_reviews_a_shared_session_from_its_arrival(tmp_path):
    from app.core import coach as coach_mod
    dest = store.runs_root() / "shared-ravi" / "chat-old.jsonl"
    dest.parent.mkdir(parents=True)
    rows = SH.light(ROWS, SH.scrubber(user="ravi", home="C:\\Users\\ravi"), "p-abc123", "ravi")
    dest.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    # said long ago (t=2), arrived now: still new for a review done yesterday
    import time
    assert coach_mod.turns_since([dest], time.time() - 86400)
    assert not coach_mod.turns_since([dest], time.time() + 60)


def test_no_access_says_what_to_do(tmp_path):
    ok, err = SH.push([], repo=str(tmp_path / "nope.git"), friend="ravi")
    assert not ok and "could not clone" in err and "share --setup" in err
