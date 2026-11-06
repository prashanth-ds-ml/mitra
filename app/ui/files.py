"""How file changes are shown for approval (user feedback 2026-11-06: diffs of new files were a wall of `+` lines).

    file_card:  a new file as a compact card: header (path · language · lines), syntax colours, line numbers,
                the first lines only and a "… N more lines (ctrl+o)" fold
    edit_view:  an edit as numbered hunks with 2 lines of context; header shows +added −removed and the lines touched
"""
from __future__ import annotations

import difflib
from pathlib import PurePosixPath

from rich.box import ROUNDED
from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

LANGUAGES = {
    ".py": ("python", "Python"), ".js": ("javascript", "JavaScript"), ".ts": ("typescript", "TypeScript"),
    ".html": ("html", "HTML"), ".css": ("css", "CSS"), ".json": ("json", "JSON"), ".toml": ("toml", "TOML"),
    ".md": ("markdown", "Markdown"), ".yml": ("yaml", "YAML"), ".yaml": ("yaml", "YAML"), ".sh": ("bash", "Shell"),
    ".ps1": ("powershell", "PowerShell"), ".sql": ("sql", "SQL"), ".txt": ("text", "Text"), ".cfg": ("ini", "Config"),
    ".ini": ("ini", "Config"), ".rs": ("rust", "Rust"), ".go": ("go", "Go"), ".java": ("java", "Java"),
}
CARD_LINES = 20
EDIT_LINES = 40


def language(path: str) -> tuple[str, str]:
    return LANGUAGES.get(PurePosixPath(path.replace("\\", "/")).suffix.lower(), ("text", "Text"))


def _header(verb: str, path: str, detail: str) -> Text:
    t = Text("● ", style="m.accent")
    t.append(verb, style="m.tool")
    t.append(" " + path, style="m.text")
    t.append("   " + detail, style="m.dim")
    return t


def file_card(path: str, text: str, *, verb: str = "Create", max_lines: int = CARD_LINES) -> tuple[Group, int]:
    """A new file. Returns (renderable, lines not shown)."""
    lexer, lang = language(path)
    lines = text.splitlines()
    shown = "\n".join(lines[:max_lines]) or " "
    hidden = max(0, len(lines) - max_lines)
    body = Syntax(shown, lexer, theme="ansi_dark", line_numbers=True, word_wrap=False,
                  background_color="default", code_width=None)
    parts: list = [body]
    if hidden:
        parts.append(Text(f"     … {hidden} more lines · ctrl+o to see all", style="m.faint"))
    card = Panel(Group(*parts), box=ROUNDED, border_style="m.faint", padding=(0, 1), expand=False)
    return Group(_header(verb, path, f"{lang} · {len(lines)} lines"), card), hidden


def _hunks(old: list[str], new: list[str], context: int):
    return difflib.SequenceMatcher(None, old, new, autojunk=False).get_grouped_opcodes(context)


def edit_view(path: str, old_text: str, new_text: str, *, context: int = 2,
              max_lines: int = EDIT_LINES) -> tuple[Group, int]:
    """An edit as numbered hunks. Returns (renderable, diff lines not shown)."""
    old, new = old_text.splitlines(), new_text.splitlines()
    added = removed = 0
    first = last = None
    rows: list[Text] = []
    for group in _hunks(old, new, context):
        if rows:
            rows.append(Text("     ⋮", style="m.faint"))
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for k in range(i2 - i1):
                    rows.append(Text(f"  {j1 + k + 1:4}   {new[j1 + k]}", style="m.dim"))
                continue
            first = (j1 + 1) if first is None else first
            last = max(last or 0, j2 or j1 + 1)
            for k in range(i1, i2):
                removed += 1
                rows.append(Text(f"  {k + 1:4} - {old[k]}", style="m.del"))
            for k in range(j1, j2):
                added += 1
                rows.append(Text(f"  {k + 1:4} + {new[k]}", style="m.add"))
    hidden = max(0, len(rows) - max_lines)
    rows = rows[:max_lines]
    if hidden:
        rows.append(Text(f"     … {hidden} more diff lines · ctrl+o to see all", style="m.faint"))
    span = f" · lines {first}–{last}" if first else ""
    if not added and not removed:
        rows = [Text("  (no change)", style="m.dim")]
    return Group(_header("Edit", path, f"+{added} −{removed}{span}"), *rows), hidden


def change_view(path: str, old_text: str | None, new_text: str) -> tuple[Group, int]:
    """Card for a new file, numbered hunks for an existing one."""
    if old_text is None:
        return file_card(path, new_text)
    return edit_view(path, old_text, new_text)
