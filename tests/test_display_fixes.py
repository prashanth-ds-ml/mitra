"""Fixes from the brick-breaker session (2026-11-06): file display, approvals, activity, folders, syntax, shell."""
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from rich.console import Console

from app import ui
from app.core import chat as C
from app.core import tools as T


def render(renderable, width=100) -> str:
    c = ui.apply(Console(record=True, width=width, color_system=None))
    c.print(renderable)
    return c.export_text()


# ── file display ────────────────────────────────────────────────────────────

def test_new_file_card_has_header_numbers_and_an_honest_fold():
    text = "\n".join(f"line_{i} = {i}" for i in range(1, 155))   # 154 lines, like game.py
    view, hidden = ui.files.file_card("brick-breaker/reference/game.py", text)
    out = render(view)
    assert "● Create brick-breaker/reference/game.py" in out and "Python · 154 lines" in out
    assert "line_1 = 1" in out and "line_20 = 20" in out and "line_21 = 21" not in out
    assert hidden == 134 and "… 134 more lines · ctrl+o to see all" in out     # was "… 1 more lines"
    assert "+++" not in out and "@@" not in out


def test_edit_view_shows_numbered_change_with_context():
    old = "\n".join(["a", "b", "c", "d", "e", "f", "g"])
    new = "\n".join(["a", "b", "c", "D", "D2", "e", "f", "g"])
    view, hidden = ui.files.edit_view("game.py", old, new)
    out = render(view)
    assert "● Edit game.py" in out and "+2 −1 · lines 4–5" in out
    assert "4 - d" in out and "4 + D" in out and "5 + D2" in out
    assert "2   b" in out and "a" not in out.split("\n")[1]          # 2 lines of context, not the whole file
    assert hidden == 0


def test_language_names():
    assert ui.files.language("level.toml") == ("toml", "TOML")
    assert ui.files.language("README") == ("text", "Text")


# ── approvals: yes / yes to all / no with a reason ──────────────────────────

class Model:
    def __init__(self, *replies):
        self.replies = list(replies)

    def bind_tools(self, specs):
        return self

    def stream(self, messages):
        yield self.replies.pop(0) if self.replies else AIMessage(content="done")


def hooks(answers, shown, steps=None):
    def stream(chunks, step=1):
        if steps is not None:
            steps.append(step)
        msg = None
        for c in chunks:
            msg = c
        return SimpleNamespace(message=msg, text=msg.content if msg else "", stopped=False, printed=True)

    asked = []

    def confirm_write(rel, old, new):
        asked.append(rel)
        return answers.pop(0)

    h = C.Hooks(stream=stream, show=lambda n, a, o, ok: shown.append((n, ok, o)), confirm=lambda *a: True,
                run_shell=lambda c: ("", True), web_search=lambda q: "", fetch_url=lambda u: "",
                mcp_find=lambda q: "", mcp_call=lambda s, t, a: "", confirm_write=confirm_write)
    return h, asked


def tc(name, n, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{n}"}])


def msgs():
    return [SystemMessage(content="s"), HumanMessage(content="make files")]


def test_yes_to_all_covers_the_rest_of_the_turn_only(tmp_path):
    shown, steps = [], []
    h, asked = hooks(["all"], shown, steps)
    model = Model(tc("write_file", 1, path="a.py", content="x = 1\n"), tc("write_file", 2, path="b.py", content="y = 2\n"),
                  AIMessage(content="done"))
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=h, mode="approve")
    session.turn(msgs())
    assert asked == ["a.py"] and (tmp_path / "b.py").exists()           # asked once, both written
    assert steps == [1, 2, 3]                                              # step number reaches the spinner
    model.replies = [tc("write_file", 3, path="c.py", content="z = 3\n"), AIMessage(content="ok")]
    h2_answers = ["yes"]
    session.hooks.confirm_write = lambda rel, old, new: h2_answers.pop(0)
    session.turn(msgs())
    assert h2_answers == []                                                # the next turn asks again


def test_no_with_a_reason_reaches_the_model(tmp_path):
    shown = []
    h, _ = hooks(["no: use a dataclass instead"], shown)
    model = Model(tc("write_file", 1, path="a.py", content="x = 1\n"), AIMessage(content="ok"))
    C.ChatSession(workspace=tmp_path, llm=model, hooks=h, mode="approve").turn(msgs())
    assert not (tmp_path / "a.py").exists()
    assert "Their reason: use a dataclass instead" in shown[0][2]


# ── tools: folders, syntax warnings ─────────────────────────────────────────

def test_make_dir_creates_folders_inside_the_workspace(tmp_path):
    ws = T.Workspace(tmp_path)
    assert T.make_dir(ws, "brick-breaker/tests").startswith("Created folder")
    assert (tmp_path / "brick-breaker" / "tests").is_dir()
    assert "already exists" in T.make_dir(ws, "brick-breaker")


def test_written_files_that_do_not_parse_get_a_warning(tmp_path):
    ws = T.Workspace(tmp_path)
    out = T.write_file(ws, "level.toml", "## Grid\n- rows = 5\n")                 # what Mitra wrote
    assert "not valid TOML" in out
    assert "not valid Python" in T.write_file(ws, "game.py", "def f(:\n")
    assert "not valid JSON" in T.write_file(ws, "c.json", "{a: 1}")
    assert "⚠" not in T.write_file(ws, "ok.toml", "rows = 5\n")


# ── activity: test counts and the turn summary ──────────────────────────────

def test_turn_counts_test_runs(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    shown = []
    h, _ = hooks([], shown)
    res = C.ChatSession(workspace=tmp_path, llm=Model(tc("run_tests", 1), AIMessage(content="ok")), hooks=h,
                        mode="auto").turn(msgs())
    assert res.tests_run == 1 and res.last_test_ok is True


def test_turn_summary_line():
    t = ui.turn_summary(seconds=220, steps=9, files=6, tests_run=2, last_test_ok=True, tokens_in=30200, tokens_out=1700)
    assert t.plain == "  ✓ 9 steps · 6 files changed · tests run 2× (last passed) · 3m 40s · ↑ 30.2K ↓ 1.7K tokens"
    assert ui.turn_summary(seconds=5, steps=1, files=0, tests_run=0, last_test_ok=None, tokens_in=1, tokens_out=1).plain.startswith("  ✓ 1 step · 5s")


# ── shell: project python; inline code never "trusted" ──────────────────────

def test_model_python_command_uses_the_projects_python(tmp_path, monkeypatch):
    from app.agents import shell
    monkeypatch.setattr("app.core.tools.project_python", lambda root: "/proj/.venv/python")
    shell.configure(workspace=str(tmp_path), allowed_roots=[str(tmp_path)])
    try:
        assert shell._model_command_args("python -m pytest -q", str(tmp_path))[0] == "/proj/.venv/python"
        assert shell._model_command_args("git status", str(tmp_path))[0] == "git"
    finally:
        shell.configure(workspace=None, allowed_roots=[])


def test_inline_code_asks_even_when_the_program_is_trusted(tmp_path, monkeypatch):
    import app.main as m
    asked = []
    monkeypatch.setattr(m.memory, "is_shell_command_trusted", lambda *a: True)
    monkeypatch.setattr(m, "_choose_approval_option", lambda *a, **k: asked.append(a[0]) or "deny")
    monkeypatch.setattr(m, "_print_approval_result", lambda *a, **k: None)
    assert m._confirm_shell("python -m pytest", str(tmp_path)) == "python -m pytest"         # trusted: runs
    assert m._confirm_shell('python -c "import os"', str(tmp_path)) is None                   # inline: asked
    assert asked == ["Run shell command"]
