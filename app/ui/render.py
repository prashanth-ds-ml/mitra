"""One-line tool steps and small status lines, in place of the old panels.

    ● Read snake/game.py
      ⎿  84 lines
"""
from __future__ import annotations

from rich.console import Group
from rich.text import Text

MARK = "●"
ELBOW = "⎿"

# tool name -> the verb shown to the user
_ACTIONS = {
    "read_file": "Read", "read_document": "Read", "get_file_tree": "List", "list_directory": "List",
    "search_text": "Search", "search_in_files": "Search", "grep_symbol": "Search", "find_definition": "Search",
    "create_file": "Write", "create_markdown_file": "Write", "edit_file": "Edit", "update_markdown_file": "Edit",
    "create_folder": "Create", "move_file": "Move", "delete_file": "Delete", "delete_folder": "Delete",
    "create_venv": "Setup", "install_packages": "Install", "run_command": "Bash",
    "git_status": "Git", "git_diff": "Git", "git_commit": "Commit",
    "mcp_find": "MCP", "mcp_call": "MCP", "write_file": "Write", "run_tests": "Tests", "search": "Search",
    "list_files": "List",
}


def action_for(tool: str) -> str:
    return _ACTIONS.get(tool, tool.replace("_", " ").title())


def format_tokens(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def tool_line(action: str, target: str = "", *, ok: bool = True, detail: str = "",
              added: int | None = None, removed: int | None = None) -> Text:
    """`● Action target  +a −r` with an optional `⎿ detail` line under it."""
    line = Text()
    line.append(MARK + " ", style="m.accent" if ok else "m.err")
    line.append(action, style="m.tool")
    if target:
        line.append(" " + target, style="m.dim")
    if added is not None or removed is not None:
        line.append("  ")
        line.append(f"+{added or 0}", style="m.ok")
        line.append(" ")
        line.append(f"−{removed or 0}", style="m.err")
    if detail:
        line.append(f"\n  {ELBOW}  ", style="m.faint")
        line.append(detail, style="m.dim" if ok else "m.err")
    return line


def _short(text: str, n: int = 100) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _target(tool: str, args: dict) -> str:
    if tool == "move_file":
        return f"{args.get('src', '')} → {args.get('dest', '')}"
    if tool == "run_command":
        return _short(args.get("command", ""), 80)
    if tool in ("search_text", "search_in_files"):
        return f'"{_short(str(args.get("pattern") or args.get("query") or ""), 40)}"'
    if tool in ("grep_symbol", "find_definition"):
        return str(args.get("symbol") or args.get("name") or "")
    if tool == "mcp_call":
        return f"{args.get('server', '')} / {args.get('tool', '')}"
    if tool == "mcp_find":
        return f'"{_short(str(args.get("query", "")), 40)}"'
    if tool == "git_commit":
        return _short(str(args.get("message", "")), 60)
    return str(args.get("path") or args.get("project_path") or "")


def _detail(tool: str, output: str, ok: bool) -> str:
    out = (output or "").strip()
    if not ok:
        first = out.lstrip("✗").strip().splitlines()
        return _short(first[0] if first else "failed", 120)
    lines = out.splitlines()
    if tool in ("read_file", "read_document"):
        return f"{len(lines)} lines"
    if tool in ("list_directory", "get_file_tree"):
        return f"{len(lines)} entries"
    if tool in ("search_text", "search_in_files", "grep_symbol", "find_definition"):
        hits = [ln for ln in lines if ln.strip()]
        return "no matches" if not hits or "no match" in out.lower() else f"{len(hits)} matches"
    return ""


def step_line(tool: str, args: dict, output: str, ok: bool) -> Text:
    """One tool step from a tool name, its args and its output."""
    return tool_line(action_for(tool), _target(tool, args or {}), ok=ok, detail=_detail(tool, output, ok))


def agent_steps(steps) -> Group:
    """All steps of an AgentResponse (objects with .tool, .args, .output, .ok)."""
    return Group(*(step_line(s.tool, s.args, s.output, s.ok) for s in steps))


def shell_start(command: str) -> Text:
    return tool_line("Bash", _short(command, 90))


def shell_done(result) -> Text:
    """The `⎿` line after a command's live output."""
    t = Text("  " + ELBOW + "  ", style="m.faint")
    if getattr(result, "denied", False):
        t.append("skipped: you declined", style="m.dim")
    elif getattr(result, "timed_out", False):
        t.append("timed out", style="m.err")
    elif result.exit_code == 0:
        n = len(result.output_lines)
        t.append("done" + (f" · {n} lines of output" if n else ""), style="m.ok")
    else:
        t.append(f"failed · exit {result.exit_code}", style="m.err")
        last = next((ln.strip() for ln in reversed(getattr(result, "output_lines", []) or []) if ln.strip()), "")
        if last:  # say why, not only "failed" (2026-11-06: 30 failures with no visible reason)
            t.append(f" · {last[:120]}", style="m.err")
    hidden = getattr(result, "hidden_lines", 0) or 0
    if hidden:
        t.append(f"  … +{hidden} lines (ctrl+o)", style="m.faint")
    return t


def thinking_done(seconds: float, tokens: int, *, hint: bool = True) -> Text:
    t = Text(f"✻ Thought for {seconds:.0f}s", style="m.dim")
    if tokens:
        t.append(f" · {format_tokens(tokens)} tokens", style="m.dim")
    if hint:
        t.append("  (ctrl+o to show)", style="m.faint")
    return t


def turn_footer(seconds: float, tokens_in: int, tokens_out: int) -> Text:
    return Text(
        f"  {seconds:.0f}s · ↑ {format_tokens(tokens_in)} ↓ {format_tokens(tokens_out)} tokens",
        style="m.faint",
    )


def detail_block(text: str, *, indent: str = "    ", max_lines: int = 80) -> Text:
    """Indented detail under a tool line; unified-diff lines are coloured (+ green, - red, @@ mint)."""
    out = Text()
    lines = (text or "").rstrip().splitlines()
    for n, line in enumerate(lines[:max_lines]):
        if n:
            out.append("\n")
        if line.startswith("+") and not line.startswith("+++"):
            style = "m.add"
        elif line.startswith("-") and not line.startswith("---"):
            style = "m.del"
        elif line.startswith("@@"):
            style = "m.info"
        elif line.startswith(("+++", "---")):
            style = "m.faint"
        else:
            style = "m.text"
        out.append(indent + line, style=style)
    if len(lines) > max_lines:
        out.append(f"\n{indent}… {len(lines) - max_lines} more lines", style="m.faint")
    return out


def turn_summary(*, seconds: float, steps: int, files: int, tests_run: int, last_test_ok, tokens_in: int,
                 tokens_out: int) -> Text:
    """One line at the end of a turn: what happened, at a glance."""
    mins, secs = divmod(int(seconds), 60)
    took = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
    parts = [f"{steps} step{'s' if steps != 1 else ''}"]
    if files:
        parts.append(f"{files} file{'s' if files != 1 else ''} changed")
    if tests_run:
        state = "passed" if last_test_ok else "failing"
        parts.append(f"tests run {tests_run}× (last {state})")
    parts += [took, f"↑ {format_tokens(tokens_in)} ↓ {format_tokens(tokens_out)} tokens"]
    t = Text("  ✓ " if last_test_ok is not False else "  ✗ ", style="m.ok" if last_test_ok is not False else "m.err")
    t.append(" · ".join(parts), style="m.faint")
    return t
