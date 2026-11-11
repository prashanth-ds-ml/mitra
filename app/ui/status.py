"""The status line under the input: model · mode · ctx % · folder (branch), and on the right this machine:
speed of the last answer · CPU · RAM free · GPU (user, 2026-11-11: only what you can act on)."""
from __future__ import annotations

import re
import shutil
import subprocess
import time


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
    backend: str = "",
    backend_level: str = "ok",
    right: list[tuple[str, str]] | None = None,
    right_compact: list[tuple[str, str]] | None = None,
    width: int | None = None,
) -> list[tuple[str, str]]:
    """prompt_toolkit formatted text for the bottom toolbar. `backend` (D-062 B1), e.g. '☁ kaggle · qwen3.5 256K ·
    28.1 h left', replaces the model name: where the model runs, and the hours left."""
    pct = min(100, int(total_tokens / max(context_limit, 1) * 100))
    folder = re.split(r"[\\\\/]", str(cwd).rstrip("\\\\/"))[-1] or str(cwd)  # Windows or POSIX path
    branch = git_branch(cwd) if branch is None else branch
    ctx_style = "class:status.warn" if pct >= 80 else "class:status"
    head = [("class:status", f"  {model} · ")]
    if backend:
        style = {"warn": "class:status.warn", "err": "class:status.warn", "info": "class:status.accent"}.get(
            backend_level, "class:status")
        head = [("class:status", "  "), (style, backend), ("class:status", " · ")]
    parts: list[tuple[str, str]] = head + [
        ("class:status.accent", mode),
        ("class:status", " · "),
        (ctx_style, f"ctx {pct}%"),
        ("class:status", f" · {folder}"),
    ]
    if branch:
        parts.append(("class:status", f" ({branch})"))
    if background_tasks:
        parts.append(("class:status", f" · {background_tasks} running"))
    if pct >= 80:
        parts.append(("class:status.warn", "  /compact soon"))
    if notice:
        parts.append(("class:status.accent", f"   {notice}"))
    elif not right:
        parts.append(("class:status.rule", "   shift+tab mode · /help"))
    return parts + _right_aligned(parts, right, right_compact, width)


def _text_len(parts: list[tuple[str, str]]) -> int:
    return sum(len(t) for _, t in parts)


def _right_aligned(left, right, compact, width) -> list[tuple[str, str]]:
    """The machine block at the right edge; the compact one if the full one does not fit; none if neither does."""
    width = width or shutil.get_terminal_size((100, 24)).columns
    used = _text_len(left)
    for block in (right, compact):
        if block and used + 3 + _text_len(block) <= width - 1:
            return [("class:status", " " * (width - 1 - used - _text_len(block)))] + list(block)
    return []


def _rule() -> str:
    width = shutil.get_terminal_size((100, 24)).columns
    return "─" * max(20, width - 1)


def prompt_message() -> list[tuple[str, str]]:
    """The input line, framed like the mock: a rule above, then `› `."""
    return [("", "\n"), ("class:status.rule", _rule() + "\n"), ("class:prompt", "› ")]


def framed_status(**kwargs) -> list[tuple[str, str]]:
    """A rule under the input, then the status line."""
    return [("class:status.rule", _rule() + "\n")] + status_line(**kwargs)
