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
from pathlib import Path

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
                 "wish", "wishes", "greeting", "paragraph", "sentence", "prd", "spec", "blog", "article", "essay",
                 "story", "poem", "cv", "sop"}
WRITING_VERBS = {"draft", "compose", "proofread", "rephrase", "paraphrase", "translate", "summarise", "summarize",
                 "polish", "reword", "shorten", "tldr"}
REFINE = re.compile(r"^(make it|now make it|can you make it|a bit|slightly|more|less|shorter|longer|simpler|"
                    r"too long|too short|too formal|too casual|add (a|the|my)|remove (the|my)|change the tone|"
                    r"in hindi|in telugu|in english|sign it|without)\b")
DAILY = re.compile(r"^(plan my|help me plan|make (a|my) (to-?do|todo|schedule|checklist)|prioriti[sz]e (my|these))\b")
# ideas: general when they name nothing in the project; "brainstorm ways to make the game harder" is about it
IDEAS = re.compile(r"^(give me (ideas|names|a list|suggestions)|brainstorm|suggest|any ideas|ideas (for|to|on))\b")
# talking an idea through, not building it yet (live 2026-11-11: "build a web app ... can we brainstrom on this" and
# "i feel ... once we get a base model i want to setup a web app ..." were planned as features)
DISCUSS = re.compile(r"\b(brainst(or|ro)m(ing)?|discuss|discussion|think (deep|deeply|through|about|it through|this through)|"
                     r"what do you think|your thoughts|thoughts on|pros and cons|trade-?offs?)\b")
MUSING = re.compile(r"^(so )?(i feel|i think|i guess|i might|i was thinking|i want to|i'?d like to|maybe|what if|"
                    r"once we|we can|we could|imagine|suppose|ok lets say|lets say|let'?s say)\b")
BUILD_NOW = re.compile(r"\b(build it|build this|start building|go ahead|implement it|implement this|let'?s build|"
                       r"lets build|create it|do it|start coding|write the code)\b")
# folder names that are also everyday words: "a web app" in a discussion does not mean the web/ folder
GENERIC_NAMES = frozenset({"web", "app", "api", "data", "model", "models", "src", "docs", "static", "templates",
                           "scripts", "config", "server", "client", "main", "utils", "frontend", "backend", "database"})
# deep dive 2026-11-11: follow-ups keep the working turn's tools ("still not working" after a fix was answered with
# no tools at all; "why?" after a code question was answered without reading the code)
FOLLOW_UP = re.compile(r"^(no\b|nope\b|not that|still\b|try again|again\b|i meant|that'?s (wrong|not)|wrong\b|"
                       r"it (still|doesn'?t|does not|didn'?t|is still)|same (error|issue|problem)|use\b|instead\b|"
                       r"and\b|also\b|what about|why\b|how come|but\b|so\b|then\b|ok,? but|okay,? but)")
# something is broken: the working loop (it can run things), not the read-only explainer
FAILING = re.compile(r"\b(fail(s|ing|ed)?|broken|not working|doesn'?t work|does not work|crash(es|ed|ing)?|"
                     r"traceback|exception)\b")
HOW_TO = ("how do i", "how can i", "how to", "how should i", "how would i", "how do we", "how can we")
NEED = re.compile(r"^(i|we) (need|want) (a|an|you to|to (build|make|write|create|add|have|get))\b")
SMALL_VERBS = {"rename", "remove", "delete", "move", "run", "commit", "revert", "install", "push"}
# picking one of the options Mitra just gave ("go with option 2", "the first idea", "let's do 3")
PICK = re.compile(r"\b(option|idea|approach|choice|number|no\.?) ?#?\d\b|\b(first|second|third|fourth|fifth|last) "
                  r"(one|idea|option|approach)\b|^(go with|let'?s do|lets do|do|pick|take|choose|use) \S+$|"
                  r"^(go with|let'?s (do|go with)|lets (do|go with)|pick|take|choose) (option |idea |#)?\d\b")
# the plan and the docs are edited in place (a small change), not planned first (D-068 step 2b)
DOC_TARGET = re.compile(r"\b(the|our|my|this) (plan|roadmap|todo list|to-?do|readme|docs|notes)\b|"
                        r"\b(plan|readme|notes|todo|tasks|roadmap|changelog)\.md\b")
# a question that names these is about the project (explainer / chat loop), not general knowledge
PROJECT_WORDS = {"this", "our", "code", "codebase", "project", "repo", "repository", "file", "files", "function",
                 "functions", "class", "classes", "method", "test", "tests", "bug", "error", "errors", "module",
                 "script", "here", "mitra", "folder", "game", "app", "commit", "branch", "diff", "logic",
                 "variable", "import", "config", "readme", "traceback", "exception", "fails",
                 "failing", "crash", "crashes", "build", "setup", "kaggle", "we",
                 # "where is the score stored?" asks where in this code, not general knowledge
                 "defined", "implemented", "stored", "handled", "configured", "declared", "initialized",
                 "initialised", "changed", "changes"}


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
        if re.search(r"\b(mail|email|message|reply|response|note|summary)s? (function|endpoint|class|test|tests|api|"
                     r"script|module|file|handler|parser|template|model|field|table)\b", low):
            return False  # "add a reply endpoint": code
        if ws & {"prd", "spec", "blog", "article", "essay", "poem", "cv", "sop", "proposal", "memo"}:
            return True  # "write a prd for a chat app": a document about an app, not the app
        # "a mail to my manager ... for a family function" is a mail; "send an email when the test fails" is code
        to_person = re.search(r"\bto (my|the|our|a|an) (manager|team|boss|client|customer|hr|friend|colleagues?|"
                              r"lead|teacher|landlord|professor|recruiter|vendor)\b", low)
        return bool(to_person) or not (ws & {"function", "endpoint", "class", "test", "tests", "api", "script",
                                             "module", "file", "app", "application", "website", "tool", "bot",
                                             "generator", "cli", "service"})
    return False


def project_words(root: Path) -> frozenset:
    """Names in the workspace (files, folders, stems; two levels): a question naming one is about the project."""
    out: set[str] = set()
    try:
        for p in list(Path(root).iterdir())[:200]:
            if p.name.startswith(".") or p.name in ("node_modules", "__pycache__", "venv"):
                continue
            out.update({p.name.lower(), p.stem.lower()})
            if p.is_dir():
                for q in list(p.iterdir())[:100]:
                    out.update({q.name.lower(), q.stem.lower()})
    except OSError:
        pass
    return frozenset(w for w in out if len(w) > 2)


CLI_COMMANDS = ("score", "kaggle", "report", "dashboard", "solve", "night", "harness", "improve", "coach", "cases", "practice", "init",
                "status", "config", "models", "test", "mcp", "logs", "remote")


def terminal_command(text: str) -> str:
    """'mitra score --remote' typed in the chat: a terminal command (the CLI), not a request. Returns it, or ''."""
    t = " ".join((text or "").strip().strip("`").split())
    m = re.match(r"^\$?\s*mitra\s+(" + "|".join(CLI_COMMANDS) + r")\b[^\n]{0,80}$", t, re.I)
    return t if m else ""


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
    if previous in ("small", "big") and len(short) <= 15 and FOLLOW_UP.match(low):
        return "small"  # "still not working", "try again", "no, use pytest": keep working on it, with tools
    if previous == "question" and len(short) <= 12 and FOLLOW_UP.match(low) and not CHANGE_VERBS & set(short):
        return "question"  # "why?", "and where is the score kept?": the explainer, building on what it read
    if previous in ("question", "small", "big") and len(short) <= 8 and PICK.search(low) and not low.endswith("?"):
        return "small"  # "go with option 2" after Mitra's ideas: build the one you picked, with tools
    if DAILY.match(low):
        return "general"
    named = set(re.findall(r"[a-z0-9_\-]+", low)) & {w.lower() for w in project_words}
    about = bool(any(c in raw for c in "/\\`") or "." in "".join(t for t in low.split() if not t.endswith("."))
                 or set(words) & PROJECT_WORDS or named)
    if IDEAS.match(low):
        return "question" if about else "general"  # ideas about the project: look at it first (explainer)
    if previous == "general" and BUILD_NOW.search(low) and len(short) <= 12:
        return "big"  # "ok lets build it" after talking an idea through: plan it first (with the discussion)
    starts_with_change = bool(words) and words[0] in CHANGE_VERBS
    # "can you fix the crash? think it through" asks for a change, not a discussion
    asks_change = re.search(r"\b(please|can you|could you|and|then)\s+(also\s+)?(" + "|".join(CHANGE_VERBS) + r")\b",
                            low)
    if not BUILD_NOW.search(low) and not starts_with_change and not asks_change and (
            DISCUSS.search(low) or (previous in ("general", "question") and MUSING.match(low))):
        # a new idea is talked through in one answer; only one that names the code reads it first (explainer)
        code = bool(any(c in raw for c in "/\\`") or named - GENERIC_NAMES
                    or set(words) & {"code", "codebase", "repo", "repository", "project", "file", "files",
                                     "function", "module", "class", "tests", "test"})
        return "question" if code else "general"  # "build it" then plans it
    if previous == "writing" and REFINE.match(low):
        return "writing"
    if _writing(words, low, raw):
        return "writing"
    if low.startswith(HOW_TO):
        return "question" if about else "general"  # asks how; "fix it" then does it
    if FAILING.search(low) and not low.startswith(QUESTION_START):
        return "small"  # "the tests are failing, can you check": the loop can run them, the explainer cannot
    verbs = [w for w in words if w in CHANGE_VERBS | SMALL_VERBS] + (["make"] if NEED.match(low) else [])
    if not verbs:  # a follow-up that points back ("what is option 2 exactly?", "why that?") stays on the project
        back = previous == "question" and re.search(r"\b(option|idea|approach|it|that|those|these|them|one)\b", low)
        return "question" if about or back else "general"
    asks = low.startswith(QUESTION_START) and not low.startswith(("how about", "can you", "could you"))
    if asks and not re.search(r"\b(please|can you|could you|let's|lets)\b", low) and len(set(verbs)) == 1 \
            and low.endswith("?"):
        return "question"  # "what does the fix in X change?" asks; "add a test" does
    if DOC_TARGET.search(low) and len(set(verbs)) == 1 and not set(verbs) & {"build", "implement", "develop"}:
        return "small"  # "update the plan with a level system": edit plan.md, do not plan a new feature
    if len(set(verbs)) == 1 and verbs[0] in SMALL_VERBS:
        return "small"  # "rename paddle to player in the game", "run the tests", "commit the changes"
    big = (len(set(verbs)) >= 2 or len(words) > 35 or raw.count("\n") >= 2
           or any(w in BIG_WORDS for w in words))
    return "big" if big else "small"
