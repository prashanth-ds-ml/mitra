"""Phosphor colour scheme (D-031): green on black, like an old CRT terminal.

The terminal's own background stays whatever the user's terminal uses; these are the text colours.
"""
from __future__ import annotations

from prompt_toolkit.styles import Style
from rich.console import Console
from rich.theme import Theme

PHOSPHOR = {
    "bg": "#050a06",
    "panel": "#08110a",
    "edge": "#1a3320",
    "text": "#b8f0c0",
    "dim": "#5f9a68",
    "faint": "#356040",
    "accent": "#5cff7a",
    "ok": "#5cff7a",
    "err": "#ff6b5c",
    "info": "#9ef0d0",
    "add_bg": "#0f3318",
    "del_bg": "#33140f",
}

P = PHOSPHOR

THEME = Theme({
    "m.text": P["text"],
    "m.dim": P["dim"],
    "m.faint": P["faint"],
    "m.accent": P["accent"],
    "m.accent.b": f"bold {P['accent']}",
    "m.ok": P["ok"],
    "m.err": P["err"],
    "m.info": P["info"],
    "m.tool": f"bold {P['text']}",
    "m.add": f"{P['ok']} on {P['add_bg']}",
    "m.del": f"{P['err']} on {P['del_bg']}",
    # rich Markdown elements, so replies follow the scheme
    "markdown.h1": f"bold {P['accent']}",
    "markdown.h2": f"bold {P['accent']}",
    "markdown.h3": f"bold {P['text']}",
    "markdown.code": P["info"],
    "markdown.link": P["info"],
    "markdown.link_url": P["dim"],
    "markdown.item.bullet": P["accent"],
    "markdown.item.number": P["accent"],
    "markdown.block_quote": P["dim"],
    "markdown.hr": P["faint"],
    "status.spinner": P["accent"],
})


def apply(console: Console) -> Console:
    """Push the Mitra theme onto an existing console (keeps every caller's Console object)."""
    console.push_theme(THEME)
    return console


def prompt_style() -> Style:
    """prompt_toolkit style for the input line and the status line under it."""
    return Style.from_dict({
        "prompt": f"bold {P['accent']}",
        "bottom-toolbar": f"noreverse {P['dim']}",
        "bottom-toolbar.text": f"noreverse {P['dim']}",
        "status": f"noreverse {P['dim']}",
        "status.accent": f"noreverse {P['accent']}",
        "status.warn": f"noreverse {P['err']}",
        "status.rule": f"noreverse {P['faint']}",
        "completion-menu": f"bg:{P['panel']} {P['text']}",
        "completion-menu.completion.current": f"bg:{P['add_bg']} {P['accent']}",
    })
