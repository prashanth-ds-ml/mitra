"""The status line under the input: model · mode · ctx % · tokens · folder (branch)."""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import time

from app.ui.render import format_tokens

_branch_cache: dict[str, tuple[float, str]] = {}


def git_branch(cwd: str, *, ttl: float = 5.0) -> str:
    """Current branch, cached for a few seconds (the status line is redrawn on every key press)."""
    now = time.monotonic()
    hit = _branch_cache.get(cwd)
    if hit and now - hit[0] < ttl:
        return hit[1]
    branch = ""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            branch = out.stdout.strip()
    except Exception:
        branch = ""
    _branch_cache[cwd] = (now, branch)
    return branch


def status_line(
    *,
    model: str,
    mode: str,
    total_tokens: int,
    context_limit: int,
    cwd: str,
    background_tasks: int = 0,
    branch: str | None = None,
    notice: str = "",
) -> list[tuple[str, str]]:
    """prompt_toolkit formatted text for the bottom toolbar."""
    pct = min(100, int(total_tokens / max(context_limit, 1) * 100))
    folder = pathlib.Path(cwd).name or cwd
    branch = git_branch(cwd) if branch is None else branch
    ctx_style = "class:status.warn" if pct >= 80 else "class:status"
    parts: list[tuple[str, str]] = [
        ("class:status", f"  {model} · "),
        ("class:status.accent", mode),
        ("class:status", " · "),
        (ctx_style, f"ctx {pct}%"),
        ("class:status", f" · {format_tokens(total_tokens)} tokens · {folder}"),
    ]
    if branch:
        parts.append(("class:status", f" ({branch})"))
    if background_tasks:
        parts.append(("class:status", f" · {background_tasks} running"))
    if pct >= 80:
        parts.append(("class:status.warn", "  /compact soon"))
    if notice:
        parts.append(("class:status.accent", f"   {notice}"))
    else:
        parts.append(("class:status.rule", "   shift+tab mode · /help"))
    return parts


def _rule() -> str:
    width = shutil.get_terminal_size((100, 24)).columns
    return "─" * max(20, width - 1)


def prompt_message() -> list[tuple[str, str]]:
    """The input line, framed like the mock: a rule above, then `› `."""
    return [("", "\n"), ("class:status.rule", _rule() + "\n"), ("class:prompt", "› ")]


def framed_status(**kwargs) -> list[tuple[str, str]]:
    """A rule under the input, then the status line."""
    return [("class:status.rule", _rule() + "\n")] + status_line(**kwargs)
