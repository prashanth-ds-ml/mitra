"""Phosphor colour scheme (D-031): green on black, like an old CRT terminal.

The terminal's own background stays whatever the user's terminal uses; these are the text colours.
"""
from __future__ import annotations

from prompt_toolkit.styles import Style
from pygments.style import Style as PygmentsStyle
from pygments.token import Comment, Error, Generic, Keyword, Name, Number, Operator, Punctuation, String, Token
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import PygmentsSyntaxTheme
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
    "you": "#ffb84d",   # D-076: your messages in amber, the other classic phosphor colour
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
    "markdown.strong": f"bold {P['accent']}",
    "markdown.em": f"italic {P['text']}",
    "markdown.table.header": f"bold {P['accent']}",
    "markdown.table.border": P["edge"],
    "m.you": P["you"],
    "status.spinner": P["accent"],
})


class _PhosphorCode(PygmentsStyle):
    """Code blocks in CodeMitra's colours (D-076): Rich's default (monokai) is pink and yellow on grey."""
    background_color = P["panel"]
    styles = {
        Token: P["text"],
        Comment: f"italic {P['dim']}",
        Keyword: f"bold {P['accent']}",
        Name.Function: P["info"],
        Name.Class: f"bold {P['info']}",
        Name.Builtin: P["info"],
        Name.Decorator: P["you"],
        String: P["you"],
        Number: P["you"],
        Operator: P["dim"],
        Punctuation: P["dim"],
        Generic.Deleted: P["err"],
        Generic.Inserted: P["ok"],
        Error: P["err"],
    }


CODE_THEME = PygmentsSyntaxTheme(_PhosphorCode)


def md(text: str) -> Markdown:
    """Markdown as CodeMitra shows it: the theme's styles and Phosphor code blocks. Use this, not Markdown()."""
    return Markdown(text or "", code_theme=CODE_THEME)


def apply(console: Console) -> Console:
    """Push the CodeMitra theme onto an existing console (keeps every caller's Console object)."""
    console.push_theme(THEME)
    return console


def prompt_style() -> Style:
    """prompt_toolkit style for the input line and the status line under it."""
    return Style.from_dict({
        "": P["you"],  # D-076: what you type (and what stays on screen after enter) is amber
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
