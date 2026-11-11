"""Live reply streaming: a thinking timer while the model reasons, then the answer as it is written.

Finished markdown blocks (split at blank lines outside code fences) are printed for good; only the block being written
is redrawn, so long answers scroll normally and code fences render once they close.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

from app.ui.render import format_tokens, thinking_done

OPEN, CLOSE = "<think>", "</think>"


class ThinkSplitter:
    """Splits streamed text into ("think", text) and ("say", text) parts; tags may arrive cut across chunks."""

    def __init__(self) -> None:
        self.inside = False
        self._buf = ""

    def feed(self, text: str) -> list[tuple[str, str]]:
        self._buf += text
        out: list[tuple[str, str]] = []
        while self._buf:
            tag = CLOSE if self.inside else OPEN
            idx = self._buf.find(tag)
            if idx >= 0:
                if idx:
                    out.append(("think" if self.inside else "say", self._buf[:idx]))
                self._buf = self._buf[idx + len(tag):]
                self.inside = not self.inside
                continue
            # keep back a possible partial tag at the end
            keep = 0
            for k in range(min(len(tag) - 1, len(self._buf)), 0, -1):
                if tag.startswith(self._buf[-k:]):
                    keep = k
                    break
            emit = self._buf[: len(self._buf) - keep]
            if emit:
                out.append(("think" if self.inside else "say", emit))
            self._buf = self._buf[len(self._buf) - keep:]
            break
        return out

    def flush(self) -> list[tuple[str, str]]:
        rest, self._buf = self._buf, ""
        return [("think" if self.inside else "say", rest)] if rest else []


def split_blocks(text: str) -> tuple[list[str], str]:
    """Return (finished blocks, the block still being written). A block ends at a blank line outside a code fence."""
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    lines = text.split("\n")
    for i, line in enumerate(lines):
        last = i == len(lines) - 1
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not line.strip() and not in_fence and not last:
            if any(c.strip() for c in current):
                blocks.append("\n".join(current))
            current = []
            continue
        current.append(line)
    return blocks, "\n".join(current)


def _fence_open_at(lines: list[str], i: int) -> str | None:
    """The code fence line (```lang) still open just before line i, or None."""
    head = None
    for line in lines[:i]:
        if line.strip().startswith("```"):
            head = None if head is not None else line.strip()
    return head


def block_part(block: str, start: int, end: int | None = None) -> str:
    """Lines start..end of a markdown block, renderable on its own: a code fence open at a cut is reopened at the
    start and closed at the end."""
    lines = block.split("\n")
    end = len(lines) if end is None else end
    head = _fence_open_at(lines, start)
    text = "\n".join(([head] if head else []) + lines[start:end])
    if end < len(lines) and _fence_open_at(lines, end):
        text += "\n```"
    return text


def overflow_cut(block: str, start: int, max_lines: int) -> int | None:
    """The block being written is taller than the live area can show (live 2026-11-11: long lists and tables
    vanished while they were written, the live area is cropped to the screen): the line to print it up to, keeping
    only the line being written live. None while it fits."""
    lines = block.split("\n")
    if len(lines) - start <= max_lines:
        return None
    cut = len(lines) - 1
    if lines[cut - 1].strip().startswith("```") and _fence_open_at(lines, cut):
        cut -= 1  # do not leave an empty code block behind: keep its opening line with the live part
    return cut if cut > start else None


@dataclass
class StreamResult:
    message: object = None          # merged AIMessageChunk (has .tool_calls, .usage_metadata)
    text: str = ""                  # visible answer, without <think>
    thinking: str = ""
    thinking_tokens: int = 0
    seconds: float = 0.0
    first_s: float | None = None    # time to the first answer word or tool call (not thinking)
    printed: bool = False           # answer text was shown on screen
    stopped: bool = False           # the user pressed esc
    chunks: list = field(default_factory=list)


class _Thinking:
    """Spinner line whose timer is recomputed on every Live refresh."""

    def __init__(self, started: float, clock: Callable[[], float], label: str = "Thinking") -> None:
        self.started, self.clock, self.label, self.tokens = started, clock, label, 0
        self.spinner = Spinner("dots", style="m.accent")

    def __rich__(self):
        t = Text(f"{self.label}… {self.clock() - self.started:.0f}s", style="m.accent")
        if self.tokens:
            t.append(f" · {format_tokens(self.tokens)} tokens", style="m.dim")
        t.append("  esc to stop", style="m.faint")
        self.spinner.text = t
        return self.spinner


def stream_reply(
    console: Console,
    chunks: Iterable,
    *,
    show_reasoning: bool = False,
    clock: Callable[[], float] = time.monotonic,
    label: str = "Thinking",
    stop=None,
    folded=None,
    thinking_line: bool = True,
    footer: Callable | None = None,
) -> StreamResult:
    """Consume model chunks, drawing the thinking timer and the answer live. Returns the merged message.
    `footer(live_speed, writing)`: a line under the live part while Mitra works (this machine, the speed);
    `writing` is True once the answer (not the thinking timer) is on screen."""
    res = StreamResult()
    start = clock()
    splitter = ThinkSplitter()
    thinking = _Thinking(start, clock, label)
    say = ""
    printed_blocks = 0
    cur_start = 0           # lines of the block being written that are already printed for good
    think_shown = False
    state = {"view": thinking}
    pace = {"first": None, "n": 0}  # chunks since the first one: the live speed in the footer

    def live_speed() -> float | None:
        if pace["first"] is None:
            return None
        dt = clock() - pace["first"]
        return pace["n"] / dt if dt >= 1.0 else None

    class _View:
        def __rich__(self_inner):
            if footer is None:
                return state["view"]
            return Group(state["view"], footer(live_speed(), state["view"] is not thinking))

    def max_lines() -> int:
        return max(8, console.size.height - 6)

    def show_thinking_line(live: Live) -> None:
        nonlocal think_shown
        if think_shown or not (res.thinking.strip() or res.thinking_tokens):
            think_shown = True
            return
        think_shown = True
        if folded is not None and not show_reasoning:
            folded.remember("Thinking", res.thinking)
        if show_reasoning and res.thinking.strip():
            live.console.print(thinking_done(clock() - start, res.thinking_tokens, hint=False))
            live.console.print(Text(res.thinking.strip()[:4000], style="m.faint italic"))
            live.console.print()
        elif thinking_line:  # the chat turns this off: the live timer already showed it (user feedback 2026-11-06)
            live.console.print(thinking_done(clock() - start, res.thinking_tokens, hint=not show_reasoning))
            live.console.print()

    def handle(parts: list[tuple[str, str]], live: Live) -> None:
        nonlocal say, printed_blocks, cur_start
        for kind, piece in parts:
            if kind == "think":
                res.thinking += piece
                res.thinking_tokens += 1
                thinking.tokens = res.thinking_tokens
                continue
            if not say.strip() and not piece.strip():
                continue
            if res.first_s is None and piece.strip():
                res.first_s = round(clock() - start, 2)
            if not say:
                piece = piece.lstrip("\n")
                show_thinking_line(live)
            say += piece
            done, current = split_blocks(say)
            for block in done[printed_blocks:]:
                part = block_part(block, cur_start)
                if part.strip():
                    live.console.print(Markdown(part))
                    live.console.print()
                cur_start = 0  # only the first new block was partly printed
            printed_blocks = len(done)
            cut = overflow_cut(current, cur_start, max_lines())
            if cut is not None:  # taller than the screen: print it for good, keep the last line live
                live.console.print(Markdown(block_part(current, cur_start, cut)))
                cur_start = cut
            rest = block_part(current, cur_start)
            state["view"] = Markdown(rest) if rest.strip() else Text("")

    live = Live(_View(), console=console, refresh_per_second=10, transient=True)
    live.start()
    try:
        for chunk in chunks:
            if stop is not None and stop.is_set():
                res.stopped = True
                break
            res.chunks.append(chunk)
            pace["n"] += 1
            if pace["first"] is None:
                pace["first"] = clock()
            try:
                res.message = chunk if res.message is None else res.message + chunk
            except Exception:
                res.message = chunk
            reasoning = (getattr(chunk, "additional_kwargs", None) or {}).get("reasoning_content") or ""
            if reasoning:
                handle([("think", reasoning)], live)
            content = getattr(chunk, "content", "") or ""
            if isinstance(content, str) and content:
                handle(splitter.feed(content), live)
            if getattr(chunk, "tool_call_chunks", None) and res.first_s is None:
                res.first_s = round(clock() - start, 2)
            if getattr(chunk, "tool_call_chunks", None) and not say:
                thinking.label = "Choosing a tool"
        if res.stopped:
            close = getattr(chunks, "close", None)
            if callable(close):
                try:
                    close()   # closes the HTTP stream, so Ollama stops generating
                except Exception:
                    pass
        handle(splitter.flush(), live)
        show_thinking_line(live)
        done, current = split_blocks(say)
        for block in done[printed_blocks:]:
            part = block_part(block, cur_start)
            if part.strip():
                live.console.print(Markdown(part))
                live.console.print()
            cur_start = 0
        rest = block_part(current, cur_start)
        if rest.strip():
            live.console.print(Markdown(rest))
            live.console.print()
        state["view"] = Text("")
    finally:
        live.stop()
    if res.stopped:
        from app.ui.render import tool_line
        console.print(tool_line("Stopped", detail="you pressed esc; the partial answer is kept", ok=False))
    res.text = say.strip()
    res.printed = bool(res.text)
    res.seconds = clock() - start
    return res
