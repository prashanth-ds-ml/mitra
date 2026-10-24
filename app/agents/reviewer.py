"""Review Agent — reviews current changes and surfaces actionable issues."""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from rich.markdown import Markdown
from rich.panel import Panel

from app.prompts import REVIEWER_SYSTEM_PROMPT as _SYSTEM_PROMPT


@dataclass
class ReviewResponse:
    request: str
    source: str
    summary: str
    tokens_in: int = 0
    tokens_out: int = 0


def run(llm, request: str, review_input: str, *, source: str = "current changes") -> ReviewResponse:
    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Review source: {source}\n\n"
                f"User request: {request}\n\n"
                f"Changes to review:\n{review_input}"
            )
        ),
    ])
    meta = getattr(response, "usage_metadata", None) or {}
    summary = (response.content or "").strip() or "No material issues found."
    return ReviewResponse(
        request=request,
        source=source,
        summary=summary,
        tokens_in=meta.get("input_tokens", 0),
        tokens_out=meta.get("output_tokens", 0),
    )


def render(response: ReviewResponse) -> Panel:
    return Panel(
        Markdown(response.summary),
        title="[bold cyan]Review[/bold cyan]",
        border_style="cyan",
    )
