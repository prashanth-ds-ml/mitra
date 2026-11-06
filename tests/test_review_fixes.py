"""Regression tests for the original local-codex review findings E-001, E-002, E-003 (fixed 2026-11-06)."""
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage

from app import langgraph_workflows
from app.agents import filesystem, reader, shell, web
from app.agents.limits import MAX_AGENT_STEPS
from app.agents.response import AgentResponse, ToolResult


# ── E-001: an edit-only repair counts as a code change ──────────────────────

def test_edit_file_counts_as_a_code_change():
    resp = AgentResponse(request="fix", steps=[ToolResult(tool="edit_file", args={"path": "a.py"}, output="✓ Updated")])
    assert langgraph_workflows._response_has_code_changes(resp) is True


def test_reads_alone_are_not_a_code_change():
    resp = AgentResponse(request="look", steps=[ToolResult(tool="read_file", args={"path": "a.py"}, output="x")])
    assert langgraph_workflows._response_has_code_changes(resp) is False


# ── E-002: agent loops stop at the step limit ───────────────────────────────

class AlwaysCallsATool:
    """A model that never gives a final answer: every reply asks for another tool call."""

    def __init__(self, tool_name: str, args: dict):
        self.tool_name, self.args, self.calls = tool_name, args, 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(content="", tool_calls=[{"name": self.tool_name, "args": self.args, "id": f"c{self.calls}"}])


def test_file_agent_stops_at_the_step_limit(tmp_path):
    filesystem.configure(workspace=str(tmp_path), confirm_fn=None)
    try:
        llm = AlwaysCallsATool("list_directory", {"path": "."})
        resp = filesystem.run(llm, "keep listing")
        assert llm.calls == MAX_AGENT_STEPS
        assert "step limit" in resp.summary
    finally:
        filesystem.configure(workspace=None, confirm_fn=None)


def test_reader_agent_stops_at_the_step_limit(tmp_path):
    reader.configure(workspace=str(tmp_path), allowed_roots=[])
    llm = AlwaysCallsATool("get_file_tree", {"path": "."})
    resp = reader.run(llm, "keep reading")
    assert llm.calls == MAX_AGENT_STEPS and "step limit" in resp.summary


def test_web_agent_stops_at_the_step_limit(monkeypatch):
    tool = next(t for t in web._ALL_TOOLS if t.name != "fetch_url")
    monkeypatch.setattr(web, "_run_tool_with_status", lambda fn, args, console, label: "result")
    llm = AlwaysCallsATool(tool.name, {"query": "x"})
    resp = web.run(llm, "keep searching")
    assert llm.calls == MAX_AGENT_STEPS and "step limit" in resp.summary


def test_shell_agent_stops_at_the_step_limit(monkeypatch):
    monkeypatch.setattr(shell, "execute", lambda **kw: shell.ShellResult(command="x", cwd=".", exit_code=0, output_lines=[]))
    llm = AlwaysCallsATool("run_shell", {"command": "echo hi"})
    summary = shell.run_agent(llm, "keep running")
    assert llm.calls == MAX_AGENT_STEPS and "step limit" in summary


# ── E-003: fail closed; inline code needs approval ──────────────────────────

def test_shell_without_a_workspace_refuses(tmp_path):
    shell.configure(workspace=None, allowed_roots=[])
    try:
        r = shell.execute("pytest -q", cwd=str(tmp_path))
        assert not r.ok and "no workspace is set" in r.output
    finally:
        shell.configure(workspace=None, allowed_roots=[])


def test_inline_code_from_the_model_is_refused_without_approval(tmp_path):
    shell.configure(workspace=str(tmp_path), allowed_roots=[str(tmp_path)], confirm_fn=None)
    try:
        r = shell.execute('python -c "print(42)"', cwd=str(tmp_path))
        assert not r.ok and "inline code" in r.output and "42" not in r.output
    finally:
        shell.configure(workspace=None, allowed_roots=[])


def test_inline_code_runs_when_the_user_approves(tmp_path):
    asked = []
    shell.configure(workspace=str(tmp_path), allowed_roots=[str(tmp_path)],
                    confirm_fn=lambda command, cwd: asked.append(command) or command)
    try:
        r = shell.execute(f'"{sys.executable}" -c "print(42)"', cwd=str(tmp_path))
        assert asked and "42" in r.output
    finally:
        shell.configure(workspace=None, allowed_roots=[], confirm_fn=None)


def test_inline_code_detection():
    assert shell.runs_inline_code('python -c "x"') and shell.runs_inline_code("node -e x")
    assert shell.runs_inline_code("pwsh -Command ls")
    assert not shell.runs_inline_code("python main.py") and not shell.runs_inline_code("pytest -q")
    assert not shell.runs_inline_code("pip install -r requirements.txt")


# ── E-021: Windows command splitting keeps quotes ───────────────────────────

def test_split_command_strips_outer_quotes_on_windows(monkeypatch):
    monkeypatch.setattr(shell.platform, "system", lambda: "Windows")
    assert shell._split_command('python -c "print(42)"') == ["python", "-c", "print(42)"]
    assert shell._split_command('"C:/x y/python.exe" -m pytest') == ["C:/x y/python.exe", "-m", "pytest"]
    assert shell._split_command(r"pytest tests\test_a.py") == ["pytest", r"tests\test_a.py"]


# ── E-005: paths work on Windows and Linux ──────────────────────────────────

def test_ps_path_is_consistent_on_every_os():
    from app.main import _ps_path
    assert _ps_path("src/snake_agent/cli.py") == r".\src\snake_agent\cli.py"
    assert _ps_path(pathlib.PurePosixPath("a/b.py")) == r".\a\b.py"
    assert _ps_path(r".\already.py") == r".\already.py"


def test_skill_paths_written_on_windows_are_read_anywhere(tmp_path):
    from app import skills
    (tmp_path / "skills" / "rag").mkdir(parents=True)
    (tmp_path / "skills" / "rag" / "SKILL.md").write_text("body", encoding="utf-8")
    skill = skills.Skill("rag", "RAG.", r"skills\rag\SKILL.md")
    assert skills.read_body(str(tmp_path), skill) == "body"
    assert skills.find([skill], "rag") is skill


def test_status_line_folder_from_windows_or_posix_path():
    from app.ui.status import status_line
    for cwd in (r"C:\dev\snake_game", "/home/me/snake_game", "/home/me/snake_game/"):
        text = "".join(t for _, t in status_line(model="m", mode="ask", total_tokens=0, context_limit=1, cwd=cwd, branch=""))
        assert "· snake_game" in text, cwd
