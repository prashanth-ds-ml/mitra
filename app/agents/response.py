from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    tool: str
    args: dict
    output: str

    @property
    def ok(self) -> bool:
        output = (self.output or "").strip()
        if not output:
            return False
        return not output.startswith("✗")

    @property
    def label(self) -> str:
        return _extract_label(self.tool, self.args)

    @property
    def action(self) -> str:
        return _extract_action(self.tool)


@dataclass
class AgentResponse:
    request: str
    steps: list[ToolResult] = field(default_factory=list)
    summary: str = ""
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def ok_count(self) -> int:
        return sum(1 for s in self.steps if s.ok)

    @property
    def err_count(self) -> int:
        return sum(1 for s in self.steps if not s.ok)


# ─── Label extractor ──────────────────────────────────────────────────────────

def _extract_label(tool: str, args: dict) -> str:
    match tool:
        case "move_file":
            return f"{args.get('src', '')}  →  {args.get('dest', '')}"
        case "create_venv":
            return args.get("project_path", "")
        case "install_packages":
            path = args.get("project_path", "")
            pkgs = args.get("packages")
            suffix = f"[{', '.join(pkgs)}]" if pkgs else "[from requirements.txt]"
            return f"{path}  {suffix}"
        case "run_command":
            cmd = args.get("command", "")
            cwd = args.get("cwd", "")
            return f"{cmd}  (in {cwd})" if cwd and cwd != "." else cmd
        case _:
            return args.get("path", args.get("project_path", ""))


def _extract_action(tool: str) -> str:
    actions = {
        "list_directory": "Search",
        "read_file": "Read",
        "create_file": "Edit",
        "move_file": "Move",
        "delete_file": "Delete",
        "delete_folder": "Delete",
        "create_folder": "Create",
        "create_venv": "Setup",
        "install_packages": "Install",
        "run_command": "Run",
        "git_status": "Status",
        "git_diff": "Diff",
        "git_commit": "Commit",
    }
    return actions.get(tool, tool.replace("_", " ").title())


# ─── Panel title ──────────────────────────────────────────────────────────────

def _panel_title(response: AgentResponse) -> str:
    """Derive a context-aware title from the dominant tool called."""
    tools_used = {s.tool for s in response.steps}
    if tools_used & {"git_status", "git_diff", "git_commit"}:
        return "Git"
    if tools_used & {"install_packages", "create_venv"}:
        return "Installing packages"
    if tools_used & {"delete_file", "delete_folder"}:
        return "Removing files"
    if tools_used & {"move_file"}:
        return "Moving files"
    if tools_used & {"create_file", "create_folder"}:
        return "Creating files"
    if tools_used & {"read_file", "list_directory"}:
        return "Reading project"
    return "Setup Agent"


# ─── Renderer ─────────────────────────────────────────────────────────────────

def render(response: AgentResponse):
    """Steps as one line each, then the summary (no panel, D-031)."""
    from rich.markdown import Markdown
    from app.ui import agent_steps

    parts: list = []
    if response.steps:
        parts.append(agent_steps(response.steps))
    if response.summary:
        parts.append(Text(""))
        parts.append(Markdown(response.summary))
    return Group(*parts)
