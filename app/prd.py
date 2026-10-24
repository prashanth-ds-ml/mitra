"""Minimal PRD drafting helpers for the understand -> prd flow."""

from __future__ import annotations

from textwrap import dedent

from langchain_core.messages import HumanMessage, SystemMessage

from app.builder import extract_content
from app.prompts import PRD_SYSTEM_PROMPT


_DEFAULT_TITLE = "Product Requirements Document"


def _prompt(idea: str, understanding: str, existing_prd: str | None = None, update_request: str | None = None) -> str:
    parts = [
        "You are CodeMitra's PRD writer.",
        "Write a concise, practical markdown PRD for the user's project.",
        "Use these sections exactly: Problem, Goals, Non-goals, Users, Requirements, Success Criteria, Risks.",
        "Keep it specific to the idea and the understanding notes.",
        "If the user asks for an update, revise the existing PRD rather than starting over.",
        "",
        f"Idea:\n{idea.strip() or 'Untitled idea'}",
        "",
        f"Understanding notes:\n{understanding.strip() or 'None'}",
    ]
    if existing_prd:
        parts.extend(["", f"Existing PRD:\n{existing_prd.strip()}"])
    if update_request:
        parts.extend(["", f"Update request:\n{update_request.strip()}"])
    parts.extend([
        "",
        "Return only markdown. Do not wrap the result in commentary or code fences unless needed.",
    ])
    return "\n".join(parts)


def _fallback_markdown(idea: str, understanding: str, existing_prd: str | None = None, update_request: str | None = None) -> str:
    title = idea.strip() or _DEFAULT_TITLE
    return dedent(
        f"""\
        # {title}

        ## Problem
        {idea.strip() or 'Describe the problem the project solves.'}

        ## Goals
        - Define the smallest useful version of the project.
        - Keep the scope simple enough to build and test quickly.

        ## Non-goals
        - No unnecessary feature creep.
        - No architecture decisions that are not needed for the first version.

        ## Users
        - Primary user: the project owner.
        - Secondary user: anyone who will review or test the result.

        ## Requirements
        - Capture the core idea clearly.
        - Include the must-have features from the understanding notes.
        - Keep the implementation path simple and testable.

        ## Success Criteria
        - The PRD is easy to review.
        - The next implementation step is obvious.
        - The scope is small enough to start building immediately.

        ## Risks
        - The scope may expand before the first version is validated.
        - Missing constraints may surface during implementation.
        """
    ).strip() + "\n"


def generate_markdown(llm, *, idea: str, understanding: str, existing_prd: str | None = None, update_request: str | None = None) -> str:
    """Generate a markdown PRD, with a deterministic fallback."""
    messages = [
        SystemMessage(content=PRD_SYSTEM_PROMPT),
        HumanMessage(content=_prompt(idea, understanding, existing_prd, update_request)),
    ]
    try:
        response = llm.invoke(messages)
        text = getattr(response, "content", str(response)).strip()
        content = extract_content(text)
        if content:
            return content if content.endswith("\n") else content + "\n"
    except Exception:
        pass
    return _fallback_markdown(idea, understanding, existing_prd, update_request)
