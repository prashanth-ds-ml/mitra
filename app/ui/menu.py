"""Inline arrow-key menu for approvals (D-031): no full-screen dialog.

      Apply this edit to snake/game.py?
    ❯ 1. Yes
      2. Yes, and don't ask again
      3. No
      ↑↓ to move · enter to pick · esc to cancel
"""
from __future__ import annotations

from typing import Callable

from rich.text import Text

from app.ui.theme import prompt_style


def menu_lines(options: list[str], selected: int) -> list[tuple[str, str]]:
    """prompt_toolkit formatted text for the options with the cursor on `selected`."""
    out: list[tuple[str, str]] = []
    for i, label in enumerate(options):
        if i == selected:
            out.append(("class:menu.selected", f"  ❯ {i + 1}. {label}\n"))
        else:
            out.append(("class:menu.option", f"    {i + 1}. {label}\n"))
    out.append(("class:menu.hint", "    ↑↓ to move · enter to pick · esc to cancel"))
    return out


def _run_inline(options: list[str], default: int) -> int | None:
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style, merge_styles

    from app.ui.theme import P

    state = {"i": default}
    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _(event):
        state["i"] = (state["i"] - 1) % len(options)

    @kb.add("down")
    @kb.add("j")
    @kb.add("tab")
    def _(event):
        state["i"] = (state["i"] + 1) % len(options)

    @kb.add("enter")
    def _(event):
        event.app.exit(result=state["i"])

    @kb.add("escape")
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=None)

    for n in range(1, min(len(options), 9) + 1):
        @kb.add(str(n))
        def _(event, n=n):
            event.app.exit(result=n - 1)

    control = FormattedTextControl(lambda: menu_lines(options, state["i"]), show_cursor=False)
    style = merge_styles([prompt_style(), Style.from_dict({
        "menu.selected": f"bold {P['accent']} bg:{P['add_bg']}",
        "menu.option": P["text"],
        "menu.hint": P["faint"],
    })])
    app = Application(layout=Layout(HSplit([Window(control, height=len(options) + 1)])),
                      key_bindings=kb, style=style, full_screen=False, erase_when_done=True)
    return app.run()


def choose(
    console,
    question: str,
    options: list[tuple[str, str]],
    *,
    default: str | None = None,
    runner: Callable[[list[str], int], int | None] | None = None,
) -> str | None:
    """Ask with an inline menu; returns the chosen key, or None if cancelled.

    `options` is [(key, label)]. Falls back to a typed number when the terminal cannot run the menu.
    """
    keys = [k for k, _ in options]
    labels = [label for _, label in options]
    start = keys.index(default) if default in keys else 0
    console.print()
    console.print(Text("  " + question, style="m.tool"))
    try:
        picked = (runner or _run_inline)(labels, start)
    except Exception:
        for i, label in enumerate(labels, 1):
            console.print(Text(f"    {i}. {label}", style="m.text"))
        try:
            answer = console.input("[m.accent]  ›[/m.accent] ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not answer:
            return default
        picked = int(answer) - 1 if answer.isdigit() and 0 < int(answer) <= len(keys) else None
    if picked is None:
        console.print(Text("    cancelled", style="m.faint"))
        return None
    console.print(Text(f"    ❯ {labels[picked]}", style="m.accent"))
    return keys[picked]
