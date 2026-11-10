"""Sorting a request before any model call (D-065 P3): resume | question | small | big.

Rules, not a model: cheap, instant, predictable. `/plan <task>` and `/do <task>` override them.
- resume:   "where did we stop?" → answered from the resume brief, no model call
- question: asks about something, no change verb → a normal turn (outlines keep it small)
- small:    one clear change → a normal turn, as before
- big:      several changes, or a whole feature / app / refactor → plan first
"""
from __future__ import annotations

import re

from app.core.resume import is_resume_question

CHANGE_VERBS = {"add", "fix", "implement", "build", "create", "make", "write", "refactor", "rename", "remove",
                "delete", "update", "change", "move", "convert", "migrate", "integrate", "setup", "improve",
                "optimize", "optimise", "rewrite", "extend", "replace", "redesign", "develop", "port", "upgrade"}
BIG_WORDS = {"app", "application", "game", "feature", "features", "system", "module", "modules", "api", "website",
             "page", "pages", "refactor", "redesign", "rewrite", "whole", "entire", "full", "complete", "project",
             "end-to-end", "pipeline", "dashboard", "backend", "frontend", "migrate", "migration"}
QUESTION_START = ("what", "why", "how", "where", "when", "which", "who", "explain", "show me", "tell me", "describe",
                  "is ", "are ", "does ", "do ", "did ", "summarize", "summarise", "list ", "compare")
_WORD = re.compile(r"[a-z][a-z\-]*")


def classify(text: str) -> str:
    raw = (text or "").strip()
    low = " ".join(raw.lower().split())
    if not low:
        return "question"
    if is_resume_question(low):
        return "resume"
    prose = " ".join(t for t in low.split() if not any(c in t for c in "/\\._`"))  # not file names
    words = _WORD.findall(prose)
    verbs = [w for w in words if w in CHANGE_VERBS]
    if not verbs:
        return "question"
    asks = low.startswith(QUESTION_START) and not low.startswith(("how about", "can you", "could you"))
    if asks and not re.search(r"\b(please|can you|could you|let's|lets)\b", low) and len(set(verbs)) == 1 \
            and low.endswith("?"):
        return "question"  # "what does the fix in X change?" asks; "add a test" does
    big = (len(set(verbs)) >= 2 or len(words) > 35 or raw.count("\n") >= 2
           or any(w in BIG_WORDS for w in words))
    return "big" if big else "small"
