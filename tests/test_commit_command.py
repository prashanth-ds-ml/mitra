"""/commit: drafts a message, asks, commits only staged changes, never pushes (E-026)."""

import subprocess
from types import SimpleNamespace

import pytest

from app import main


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "start")
    return tmp_path


@pytest.fixture
def commands(monkeypatch):
    """Record every subprocess command while still running it."""
    seen: list[list[str]] = []
    real_run = subprocess.run

    def run(args, *a, **kw):
        seen.append([str(x) for x in args] if isinstance(args, (list, tuple)) else [str(args)])
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", run)
    return seen


class FakeLLM:
    def __init__(self, reply="feat: change a"):
        self.reply = reply
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages[-1].content)
        return SimpleNamespace(content=self.reply)


def _choose(monkeypatch, answer):
    asked = []

    def choose(console, question, options, **kw):
        asked.append((question, options))
        return answer

    monkeypatch.setattr(main.ui.menu, "choose", choose)
    return asked


def _log(repo):
    return _git(repo, "log", "--format=%s").splitlines()


def _committed_files(repo):
    return _git(repo, "show", "--name-only", "--format=", "HEAD").split()


def _stage_change(repo):
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "a.txt")


def test_generate_yes_uses_drafted_message_and_commits_only_staged(repo, commands, monkeypatch):
    _stage_change(repo)
    (repo / "b.txt").write_text("not staged\n", encoding="utf-8")  # untracked
    asked = _choose(monkeypatch, "yes")
    llm = FakeLLM("feat: change a")

    out = main._cmd_commit(str(repo), llm, generate=True)

    assert _log(repo)[0] == "feat: change a"
    assert _committed_files(repo) == ["a.txt"]
    assert "b.txt" in _git(repo, "status", "--short")  # still untracked
    assert asked and asked[0][1] == [("yes", "Yes"), ("edit", "No, I'll type my own")]
    assert "two" in llm.prompts[0]  # the staged diff was drafted from
    assert "feat: change a" in out


def test_never_pushes_and_never_stages(repo, commands, monkeypatch):
    _stage_change(repo)
    (repo / "b.txt").write_text("untracked\n", encoding="utf-8")
    _choose(monkeypatch, "yes")
    commands.clear()  # only what /commit runs counts
    main._cmd_commit(str(repo), FakeLLM(), generate=True)
    main._cmd_commit(str(repo), FakeLLM(), message="manual message")
    git_cmds = [c for c in commands if c and c[0] == "git"]
    assert git_cmds, "expected git to be called"
    assert not any("push" in c for c in git_cmds)
    assert not any(c[1:2] == ["add"] for c in git_cmds)


def test_plain_message_with_unstaged_changes_refuses(repo, commands):
    (repo / "a.txt").write_text("unstaged edit\n", encoding="utf-8")
    (repo / "c.txt").write_text("new\n", encoding="utf-8")

    out = main._cmd_commit(str(repo), FakeLLM(), message="should not commit")

    assert "staged" in out.lower()
    assert _log(repo) == ["start"]
    assert not any(c[:2] == ["git", "commit"] for c in commands)


def test_generate_with_nothing_staged_does_not_ask_the_model(repo, commands, monkeypatch):
    (repo / "a.txt").write_text("unstaged edit\n", encoding="utf-8")
    asked = _choose(monkeypatch, "yes")
    llm = FakeLLM()

    out = main._cmd_commit(str(repo), llm, generate=True)

    assert "staged" in out.lower()
    assert llm.prompts == []
    assert asked == []
    assert _log(repo) == ["start"]


def test_type_my_own_message(repo, monkeypatch):
    _stage_change(repo)
    _choose(monkeypatch, "edit")
    monkeypatch.setattr(main.console, "input", lambda prompt="": "fix: my words")
    main._cmd_commit(str(repo), FakeLLM("feat: drafted"), generate=True)
    assert _log(repo)[0] == "fix: my words"


def test_cancelled_menu_does_not_commit(repo, monkeypatch):
    _stage_change(repo)
    _choose(monkeypatch, None)
    monkeypatch.setattr(main.console, "input", lambda prompt="": pytest.fail("should not ask for a message"))
    out = main._cmd_commit(str(repo), FakeLLM(), generate=True)
    assert "cancel" in out.lower()
    assert _log(repo) == ["start"]


def test_empty_typed_message_does_not_commit(repo, monkeypatch):
    _stage_change(repo)
    _choose(monkeypatch, "edit")
    monkeypatch.setattr(main.console, "input", lambda prompt="": "  ")
    out = main._cmd_commit(str(repo), FakeLLM(), generate=True)
    assert _log(repo) == ["start"]
    assert "cancel" in out.lower() or "usage" in out.lower()


def test_not_a_git_repo(tmp_path):
    assert main._cmd_commit(str(tmp_path), FakeLLM(), message="x") == "Not a git repository."


def test_git_calls_have_timeouts(repo, monkeypatch):
    _stage_change(repo)
    _choose(monkeypatch, "yes")
    timeouts = []
    real_run = subprocess.run

    def run(args, *a, **kw):
        if isinstance(args, (list, tuple)) and args and args[0] == "git" and args[1] in ("commit", "diff"):
            timeouts.append(kw.get("timeout"))
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", run)
    main._cmd_commit(str(repo), FakeLLM(), generate=True)
    assert timeouts and all(t for t in timeouts)
