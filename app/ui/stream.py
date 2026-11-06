"""Live reply streaming: a thinking timer while the model reasons, then the answer as it is written.

Finished markdown blocks (split at blank lines outside code fences) are printed for good; only the block being written
is redrawn, so long answers scroll normally and code fences render once they close.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

from rich.console import Console
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


@dataclass
class StreamResult:
    message: object = None          # merged AIMessageChunk (has .tool_calls, .usage_metadata)
    text: str = ""                  # visible answer, without <think>
    thinking: str = ""
    thinking_tokens: int = 0
    seconds: float = 0.0
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
) -> StreamResult:
    """Consume model chunks, drawing the thinking timer and the answer live. Returns the merged message."""
    res = StreamResult()
    start = clock()
    splitter = ThinkSplitter()
    thinking = _Thinking(start, clock, label)
    say = ""
    printed_blocks = 0
    think_shown = False
    state = {"view": thinking}

    class _View:
        def __rich__(self_inner):
            return state["view"]

    def show_thinking_line(live: Live) -> None:
        nonlocal think_shown
        if think_shown or not (res.thinking.strip() or res.thinking_tokens):
            think_shown = True
            return
        think_shown = True
        live.console.print(thinking_done(clock() - start, res.thinking_tokens, hint=not show_reasoning))
        if folded is not None and not show_reasoning:
            folded.remember("Thinking", res.thinking)
        if show_reasoning and res.thinking.strip():
            live.console.print(Text(res.thinking.strip()[:4000], style="m.faint italic"))
        live.console.print()

    def handle(parts: list[tuple[str, str]], live: Live) -> None:
        nonlocal say, printed_blocks
        for kind, piece in parts:
            if kind == "think":
                res.thinking += piece
                res.thinking_tokens += 1
                thinking.tokens = res.thinking_tokens
                continue
            if not say.strip() and not piece.strip():
                continue
            if not say:
                piece = piece.lstrip("\n")
                show_thinking_line(live)
            say += piece
            done, current = split_blocks(say)
            for block in done[printed_blocks:]:
                live.console.print(Markdown(block))
                live.console.print()
            printed_blocks = len(done)
            state["view"] = Markdown(current) if current.strip() else Text("")

    live = Live(_View(), console=console, refresh_per_second=10, transient=True)
    live.start()
    try:
        for chunk in chunks:
            if stop is not None and stop.is_set():
                res.stopped = True
                break
            res.chunks.append(chunk)
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
            live.console.print(Markdown(block))
            live.console.print()
        if current.strip():
            live.console.print(Markdown(current))
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
