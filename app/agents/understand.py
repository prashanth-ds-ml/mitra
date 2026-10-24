"""Lightweight idea-understanding loop for the PRD workflow."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

from app.prompts import UNDERSTAND_SYSTEM_PROMPT as _SYSTEM_PROMPT

_MAX_ROUNDS = 4


def run(llm, idea: str, console: Console, *, project_context: str = "") -> str:
    """Run a small clarification loop and return a markdown-ready transcript."""
    transcript: list[str] = [f"# Understand\n\n## Idea\n{idea.strip() or 'Untitled idea'}\n"]
    if project_context.strip():
        transcript.append(f"## Workspace Context\n{project_context.strip()}\n")
    messages: list[HumanMessage | SystemMessage] = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content="\n\n".join(
                part
                for part in [
                    f"Idea:\n{idea.strip() or 'Untitled idea'}",
                    f"Workspace context:\n{project_context.strip()}" if project_context.strip() else "",
                ]
                if part
            )
        ),
    ]

    for _ in range(_MAX_ROUNDS):
        response = llm.invoke(messages)
        text = getattr(response, "content", str(response)).strip()
        if not text:
            break

        transcript.append(f"## Assistant\n{text}\n")
        messages.append(response)

        if "READY_TO_DRAFT" in text:
            break

        console.print(text)
        user_reply = console.input("[bold cyan]Follow-up answer:[/bold cyan] ").strip()
        transcript.append(f"## User\n{user_reply or '(no response)'}\n")
        messages.append(HumanMessage(content=user_reply or "(no response)"))

    return "\n".join(transcript).strip() + "\n"
