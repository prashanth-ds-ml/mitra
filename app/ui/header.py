"""Startup screen (D-031): a one-line title, a compact model picker, then a small header box with tips."""
from __future__ import annotations

from rich.box import ROUNDED
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_PLACEMENT = {"gpu": ("GPU", "m.ok"), "split": ("GPU+CPU", "m.info"), "cpu": ("CPU, slow", "m.err")}


def title_line() -> Text:
    t = Text("✻ Mitra", style="m.accent.b")
    t.append("  local coding assistant · runs on your machine", style="m.dim")
    return t


def hardware_line(*, vram_gib=None, vram_free_gib=None, ram_free_gib=None, ram_total_gib=None) -> Text:
    parts = []
    if vram_gib is not None:
        parts.append(f"GPU {vram_gib:.1f} GB" + (f" ({vram_free_gib:.1f} free)" if vram_free_gib is not None else ""))
    if ram_total_gib is not None:
        parts.append(f"RAM {ram_total_gib:.0f} GB" + (f" ({ram_free_gib:.1f} free)" if ram_free_gib is not None else ""))
    return Text("  " + " · ".join(parts), style="m.faint") if parts else Text("")


def model_table(models) -> Table:
    """Numbered list of models (objects with .name, .size_text, .placement)."""
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="m.accent")
    table.add_column(style="m.text")
    table.add_column(justify="right", style="m.dim")
    table.add_column(justify="right", style="m.text")
    table.add_column()
    for i, m in enumerate(models, 1):
        label, style = _PLACEMENT.get(getattr(m, "placement", ""), ("", "m.dim"))
        ctx = getattr(m, "context", 0) or 0
        table.add_row(f"  {i}", m.name, getattr(m, "size_text", "") or "",
                      f"{ctx // 1024}K context" if ctx else "", Text(label, style=style))
    return table


def header(*, model: str, folder: str, context: int | None = None, placement: str = "",
           mcp_servers: list[str] | None = None, loaded: list[str] | None = None, version: str = "") -> Panel:
    rows = Table.grid(padding=(0, 2))
    rows.add_column(style="m.dim")
    rows.add_column(style="m.text")
    where, style = _PLACEMENT.get(placement, ("", "m.dim"))
    model_text = Text(model, style="m.text")
    extra = ", ".join(p for p in (f"{context // 1024}K context" if context else "", f"on {where}" if where else "") if p)
    if extra:
        model_text.append(f"  ({extra})", style="m.dim")
    rows.add_row("model", model_text)
    rows.add_row("folder", folder)
    if mcp_servers:
        mcp = Text()
        for i, name in enumerate(mcp_servers):
            if i:
                mcp.append("  ")
            mcp.append("● ", style="m.accent")
            mcp.append(name, style="m.text")
        rows.add_row("mcp", mcp)
    if loaded:
        rows.add_row("loaded", Text(" · ".join(loaded), style="m.dim"))
    title = Text("✻ Mitra", style="m.accent.b")
    if version:
        title.append(f" {version}", style="m.dim")
    return Panel(Group(rows), title=title, title_align="left", box=ROUNDED, border_style="m.accent",
                 padding=(0, 2), expand=False)


def tips() -> Text:
    t = Text("  ", style="m.dim")
    for i, (key, what) in enumerate((("/", "commands"), ("!", "shell command"), ("/doctor", "check"),
                                     ("ctrl+c", "stop"), ("exit", "quit"))):
        if i:
            t.append("  ·  ", style="m.faint")
        t.append(key, style="m.text")
        t.append(" " + what, style="m.dim")
    return t
