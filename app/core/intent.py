"""Sorting a request before any model call (D-065 P3, D-068 step 1): resume | chat | writing | general | question |
small | big.

Rules, not a model: cheap, instant, predictable. `/plan <task>` and `/do <task>` override them.
- resume:   "where did we stop?" → answered from the resume brief, no model call
- chat:     small talk ("hi", "thanks") → one call, no tools (D-068 step 1)
- writing:  a mail, message, summary, rewrite, translation (and "make it shorter" after one) → one call, no tools
- general:  a question that names nothing in the project ("difference between LoRA and QLoRA") → one call, no tools
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


# D-068 step 1: everyday requests take the one-call reply path (no tools, thinking off)
EVERYDAY = ("chat", "writing", "general")
SMALL_TALK = {"hi", "hello", "hey", "hii", "yo", "thanks", "thank", "thx", "ok", "okay", "cool", "great", "nice",
              "good", "morning", "afternoon", "evening", "night", "bye", "cheers", "mitra", "there", "you", "how",
              "are", "doing", "what's", "whats", "up", "sup", "awesome", "perfect", "done", "fine", "welcome",
              "namaste", "yes", "no", "sure", "alright", "much", "a", "lot", "it", "is", "that", "works", "worked",
              "very", "so", "and", "again", "all", "the", "for", "help", "your"}
WRITING_NOUNS = {"mail", "email", "e-mail", "mails", "emails", "message", "messages", "letter", "post", "tweet",
                 "announcement", "invite", "invitation", "memo", "note", "reply", "response", "bio", "caption",
                 "slack", "whatsapp", "linkedin", "cover", "proposal", "summary", "minutes", "agenda", "apology",
                 "wish", "wishes", "greeting"}
WRITING_VERBS = {"draft", "compose", "proofread", "rephrase", "paraphrase", "translate", "summarise", "summarize",
                 "polish", "reword", "shorten", "tldr"}
REFINE = re.compile(r"^(make it|now make it|can you make it|a bit|slightly|more|less|shorter|longer|simpler|"
                    r"too long|too short|too formal|too casual|add (a|the|my)|remove (the|my)|change the tone|"
                    r"in hindi|in telugu|in english|sign it|without)\b")
DAILY = re.compile(r"^(plan my|help me plan|make (a|my) (to-?do|todo|schedule|checklist)|give me (ideas|names|a list|"
                   r"suggestions)|brainstorm|suggest (some|a few)|prioriti[sz]e (my|these))\b")
# a question that names these is about the project (explainer / chat loop), not general knowledge
PROJECT_WORDS = {"this", "our", "code", "codebase", "project", "repo", "repository", "file", "files", "function",
                 "functions", "class", "classes", "method", "test", "tests", "bug", "error", "errors", "module",
                 "script", "here", "mitra", "folder", "game", "app", "commit", "branch", "diff", "logic",
                 "variable", "import", "config", "readme", "traceback", "exception", "fails",
                 "failing", "crash", "crashes", "build", "setup", "kaggle", "we"}


# "ok", "yes", "go" right after a working turn answer Mitra's question ("shall I run the tests?"): not small talk
ANSWERS = {"yes", "no", "sure", "ok", "okay", "alright", "go", "do", "please", "proceed", "fine", "done", "ahead",
           "continue", "carry", "on", "start", "now", "let's", "lets", "with", "yep", "yeah", "nope"}


def _small_talk(words: list[str], previous: str) -> bool:
    if not (0 < len(words) <= 6 and all(w in SMALL_TALK for w in words)):
        return False
    working = previous not in ("", "resume") + EVERYDAY
    return not (working and set(words) & ANSWERS)


def _writing(words: list[str], low: str, raw: str) -> bool:
    ws = set(words)
    if ws & WRITING_VERBS:
        # "summarise this module" asks about code; summarising pasted text or a mail is writing
        return not (ws & {"module", "function", "class", "file", "code", "repo", "project", "codebase"}) \
            or "\n" in raw.strip()
    if ws & WRITING_NOUNS and (ws & {"write", "draft", "compose", "send", "reply", "respond", "prepare", "make",
                                     "create", "give", "need", "help", "turn", "convert", "rewrite"}
                              or low.startswith(("a ", "an ", "mail ", "email ", "reply "))):
        return not (ws & {"function", "endpoint", "class", "test", "tests", "api", "script", "module", "file"})
    return False


def classify(text: str, previous: str = "", project_words: frozenset | set = frozenset()) -> str:
    """`previous`: the kind of the last request (a "make it shorter" after a mail is writing). `project_words`: names
    in the workspace (files, folders), so a question that names one is about the project."""
    raw = (text or "").strip()
    low = " ".join(raw.lower().split())
    if not low:
        return "question"
    if is_resume_question(low):
        return "resume"
    prose = " ".join(t for t in low.split() if not any(c in t for c in "/\\._`"))  # not file names
    words = _WORD.findall(prose)
    short = re.findall(r"[a-z']+", low)
    if _small_talk(short, previous):
        return "chat"
    if previous not in ("", "resume") + EVERYDAY and 0 < len(short) <= 6 and set(short) <= SMALL_TALK | ANSWERS:
        return "small"  # "ok" / "yes go ahead" answers the working turn's question: continue it with its tools
    if DAILY.match(low):
        return "general"
    if previous == "writing" and REFINE.match(low):
        return "writing"
    if _writing(words, low, raw):
        return "writing"
    verbs = [w for w in words if w in CHANGE_VERBS]
    if not verbs:
        named = set(re.findall(r"[a-z0-9_\-]+", low)) & {w.lower() for w in project_words}
        if any(c in raw for c in "/\\`") or "." in "".join(t for t in low.split() if not t.endswith(".")) \
                or set(words) & PROJECT_WORDS or named:
            return "question"
        return "general"
    asks = low.startswith(QUESTION_START) and not low.startswith(("how about", "can you", "could you"))
    if asks and not re.search(r"\b(please|can you|could you|let's|lets)\b", low) and len(set(verbs)) == 1 \
            and low.endswith("?"):
        return "question"  # "what does the fix in X change?" asks; "add a test" does
    big = (len(set(verbs)) >= 2 or len(words) > 35 or raw.count("\n") >= 2
           or any(w in BIG_WORDS for w in words))
    return "big" if big else "small"
