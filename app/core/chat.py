"""The chat on the core loop (M1 stage 2): every message runs one agent loop until the model answers.

Replaces the keyword router and the agent hand-offs (planner / file / shell / reader / web agents). The model gets
the core tools plus shell, web, MCP and the plan runner, and keeps calling them until it gives an answer.

Modes (shift+tab):  ask = approve every edit and command · auto-edit = edits without asking · plan = read-only tools
"""
from __future__ import annotations

import difflib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.limits import RepeatGuard
from app.core import harness as H
from app.core import loop as core_loop
from app.core import signals as SIG
from app.core import tools as T
from app.core.parse import text_tool_calls

CHAT_PROMPT = """You are Mitra, a local coding assistant working in the user's project folder.

Answer questions directly when you can. For work on the project, use the tools and keep going until it is done:
look first (list_files, read_file, search), make small changes (edit_file, write_file), check them (run_tests or
run_command), and fix what fails. Read a file before you edit it. For a plan file with tasks (plan.md), use run_plan:
it builds the tasks one at a time and runs each task's tests. Use web_search / fetch_url for facts you do not know;
a question about this project (its status, what exists) is answered from its files, not the web.

Run the tests right after you write code, before writing more files. Create folders with make_dir.
A plan.md for /run has tasks `### T1: title`, each with `- Done when: `<test command>` passes`.
A new project gets its code, its tests and a plan.md; folders like reference/ or tests/hidden/ are only for test
levels, so do not copy them unless the user asks for a level.

When the work is done, or you need the user, reply in a few short lines: what you did, what is left. Do not describe
changes you did not make."""

# D-071 one Mitra: one conversational loop; the model decides whether to talk, look or change (all tools offered)
ONE_PROMPT = """You are Mitra, the user's thinking partner and coder, running on their own machine, in their project
folder (its files are listed below).

Talk like a person, not a report. Most messages are conversation: greetings, thinking out loud, ideas, choices,
opinions, questions. Answer those directly in a few sentences of plain words and react to what the user actually
said. In conversation never use headings or bold section titles, even when you explain a concept: write short
paragraphs, and at most one short list when steps or options really need it. When the user is deciding or an idea
is still open, end with one short question that helps them decide. In small talk, do not bring up the project.

A message that names something in this project (a file, a folder, or a part such as the game, the API, the tests)
is about this project, even if the words could mean something else in general: look at the code before you answer.
Use tools only when the answer needs them:
- About this project's code, files, tests or status: look first (search, list_files, read_file; read only the part
  you need), then answer with path:line references. Never state a number you did not check; run_tests when the
  question is whether tests pass.
- A change: read the file, make small changes (edit_file, write_file), run the tests, fix what fails, stop when it
  works, then say in a few lines what you changed. Run the tests right after you write code. Create folders with
  make_dir. Never describe changes you did not make.
- A bigger feature (several files): propose a short plan in a few lines and ask before building it; a plan.md with
  `### T1:` tasks is built with run_plan.
- A fact you do not know: web_search / fetch_url.
If it is unclear what to look at or change, ask one short question instead of searching.

A mail or message the user wants drafted: you write it FOR the user, as the user, never as Mitra. A mail has a
'Subject:' line, then the body, then the user's mail signature copied exactly from their notes, word for word,
with no other closing (no signature in the notes: end with [your name]). Use only facts the user gave or that are
in this conversation; write [placeholder] for anything missing. Output only the text itself."""
OUTLINE_MAX_FILES = 60
_OUTLINE_SKIP = {".git", ".mitra", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build",
                 ".idea", ".vscode"}


def project_outline(root: Path, max_files: int = OUTLINE_MAX_FILES) -> str:
    """'## This project folder: snake' and its files (two levels), so one Mitra knows what 'the snake' or 'the API'
    refers to (A/B 2026-11-11: asked how the snake grows, it explained real snakes)."""
    import os

    root = Path(root)
    files: list[str] = []
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in _OUTLINE_SKIP and not x.startswith("."))
        rel = Path(d).relative_to(root)
        if len(rel.parts) > 2:
            dirs[:] = []
            continue
        files += [(rel / n).as_posix() for n in sorted(names) if not n.startswith(".")]
        if len(files) > max_files:
            break
    if not files:
        return ""
    more = f" (+ more)" if len(files) > max_files else ""
    return f"## This project folder: {root.name}\nFiles: " + ", ".join(files[:max_files]) + more


# D-071 phased (decide, then act): the first call has no real tools, only these three phase switches; the model
# answers in text (talk) or picks a phase, and only then gets that phase's tools (A/B 2026-11-11: with every tool
# from the first step, a 9B built a whole app from "either the snake game or a web app").
PHASED_PROMPT = """You are Mitra, the user's thinking partner and coder, running on their own machine, in their project
folder (its files are listed below).

Talk like a person, not a report. Most messages are conversation: greetings, thinking out loud, ideas, choices,
opinions, general questions. Answer those yourself, directly, in a few sentences of plain words, and react to what
the user actually said. Never use headings or bold section titles; at most one short list when steps or options
really need it. When the user is deciding or an idea is still open, end with one short question that helps them
decide. In small talk, do not bring up the project.

You have no file tools until you choose a phase. Choose one only when the message needs it:
- look_at_code: the message asks about this project's code, files, tests or status (it names something in the
  project: a file, a folder, a part such as the game, the API, the tests). Never answer those from memory.
- make_change: the user asked you to change, fix, add or build something small and clear in this project.
- propose_plan: the user asked to build something bigger (several files) or said "build it" after a discussion.
Deciding between options, brainstorming, opinions and ideas are conversation: answer them yourself.

A mail or message the user wants drafted: you write it FOR the user, as the user, never as Mitra. A mail has a
'Subject:' line, then the body, then the user's mail signature copied exactly from their notes, word for word,
with no other closing (no signature in the notes: end with [your name]). Use only facts the user gave or that are
in this conversation; write [placeholder] for anything missing. Output only the text itself, with no preamble."""

PHASE_SPECS = [
    {"name": "look_at_code", "description": "Start looking at this project's files to answer a question about them.",
     "parameters": {"type": "object", "properties": {"what": {"type": "string", "description": "what to find out"}},
                    "required": ["what"]}},
    {"name": "make_change", "description": "Start changing this project's files: a change the user asked for.",
     "parameters": {"type": "object", "properties": {"what": {"type": "string", "description": "the change"}},
                    "required": ["what"]}},
    {"name": "propose_plan", "description": "Write a short plan for a bigger build and ask the user before building.",
     "parameters": {"type": "object", "properties": {"goal": {"type": "string"}}, "required": ["goal"]}},
]
PHASES = {
    "look_at_code": dict(tools=("list_files", "read_file", "search", "run_tests"), budget="explain_max_steps",
                         note="[Mitra: look phase. Find what answers the question: search for a name or list_files, "
                              "read only the part you need, run_tests if the question is whether tests pass. Then "
                              "answer in a few plain sentences, citing each point as path:line with the file path "
                              "(for example snake/game.py:40). Never state a number you did not check. Change "
                              "nothing.]"),
    "make_change": dict(tools=None, budget="chat_max_steps",
                        note="[Mitra: change phase. Read the file before you edit it, make small changes, run the "
                             "tests right after, fix what fails, stop when it works. Then tell the user in two or "
                             "three lines what you changed (path:line) and the test result.]"),
    "propose_plan": dict(tools=(), budget=None,
                         note="[Mitra: plan phase. Write a short plan: the goal in one line, then 3-6 steps, each with "
                              "the files it touches and how it is checked. End by asking the user whether to build "
                              "it. Do not build anything yet.]"),
}
EMPTY_ANSWER_NOTE = ("[Mitra: you have not said anything to the user. Tell them now, in a few plain sentences, what "
                     "you found or changed. Do not call tools.]")

ONE_LAST_STEP_NOTE = ("[Mitra: this is your last step. Answer the user now from what you have; say what you could not "
                      "finish or check. Do not call tools.]")

# D-068 step 1: the one-call reply path (small talk, writing, general questions): no tools, thinking off
REPLY_NOTES = {
    "chat": "This is small talk. Reply in one or two friendly sentences. If it is the start of the conversation and "
            "the 'where we stopped' brief above has something, add one short line on it. Do not call tools.",
    "writing": "This is a writing task (a mail, message, summary, rewrite or translation). You are drafting it FOR "
               "the user, as the user: write in their voice and tone from their notes, and never sign as Mitra. "
               "For a mail: a 'Subject:' line, then the body, then the user's mail signature copied exactly from "
               "their notes (no signature in the notes: end with [your name]). Use only facts the user gave or that "
               "are in this conversation: do not add claims, offers, numbers or advice they did not mention; write "
               "[placeholder] for anything missing. Output only the text itself: no preamble, no notes after it. "
               "Do not call tools.",
    "general": "This is a general question or everyday task, not about the project's files. Answer directly and "
               "briefly, with a short list or example when it helps. Do not call tools.",
}

# D-068 step 2: questions about the project's code: read only, a small budget, always an answer
EXPLAIN_TOOLS = ("list_files", "read_file", "search")
EXPLAIN_NOTE = (
    "This is a question, review or brainstorm about the project. You may only look: list_files, search, read_file "
    "(read the part you need, not whole big files). You have {steps} steps. Find the right files first (search for "
    "a name, or list_files), read only what you need, then answer with path:line references. How or why: short and "
    "plain. Review or opinion: what is good, what is risky, what you would change, and why. Ideas: 3-5 options that "
    "fit this code, each with its cost and trade-off, then your pick; the user says which one to build. Do not change "
    "anything. Only if the question is too vague to start, ask at most 2 short questions instead of searching.")
LAST_STEP_NOTE = ("[Mitra: this is your last step. Answer the question now from what you have read, with path:line "
                  "references; say what you could not check. Do not call tools.]")
_CITE = re.compile(r"(?<![\w/.\\-])([\w./\\-]*[A-Za-z_][\w-]*\.[A-Za-z]\w*)(?![\w(])")
_LINE_REF = re.compile(r"\.[A-Za-z]\w*:\d+|\blines? \d+")


_SKIP_DIRS = {".git", ".mitra", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}


def _project_files(root: Path, cap: int = 20_000) -> list[str]:
    import os
    out: list[str] = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in _SKIP_DIRS]
        rel = Path(d).relative_to(root).as_posix()
        out += [f if rel == "." else f"{rel}/{f}" for f in files]
        if len(out) >= cap:
            break
    return out


def cited_files(text: str, root: Path) -> list[str]:
    """Files an answer names (with or without :line) that exist in the workspace; a bare name matches anywhere."""
    # only a leading "./" goes: lstrip("./") also ate the dot of ".github/..." and ".env.example"
    names = [re.sub(r"^(\./)+", "", n.replace("\\", "/")) for n in _CITE.findall(text or "")]
    if not names:
        return []
    files: list[str] | None = None  # walked only when a name is not a path from the root
    out: list[str] = []
    for rel in names:
        if not set(Path(rel).parts) & (_SKIP_DIRS | {".."}) and (Path(root) / rel).is_file():
            hit = rel
        else:
            files = _project_files(root) if files is None else files
            hit = rel if rel in files else next((f for f in files if f.endswith("/" + rel)), None)
        if hit and hit not in out:
            out.append(hit)
    return out


READ_ONLY_TOOLS = {"list_files", "read_file", "search", "web_search", "fetch_url", "mcp_find"}  # plan mode

# E-100 (A/B 2026-11-11): with thinking off, mimo sometimes "thinks" anyway, invisibly, until the output cap (8,192
# tokens, ~6 minutes on the laptop) and answers nothing. A reply that shows nothing for this many chunks is stopped,
# the model is told to answer now, and it gets one more try.
RUNAWAY_HIDDEN_CHUNKS = 1500
RUNAWAY_NOTE = ("[Mitra: your last reply produced nothing visible for a long time and was stopped. Answer the user "
                "now, directly and briefly, or call one tool. No long reasoning.]")


class Runaway(Exception):
    """A model call that kept generating without any visible answer or tool call."""


def guard_runaway(chunks, limit: int = RUNAWAY_HIDDEN_CHUNKS):
    """Pass chunks through; raise Runaway (closing the stream, so Ollama stops) after `limit` chunks in a row that
    carry no visible text and no tool call. Only used when thinking is off: with thinking on, long reasoning is
    expected and shown."""
    hidden = 0
    try:
        for c in chunks:
            visible = str(getattr(c, "content", "") or "").strip() or getattr(c, "tool_call_chunks", None)
            hidden = 0 if visible else hidden + 1
            if hidden >= limit:
                raise Runaway(f"{limit} chunks with nothing visible")
            yield c
    finally:
        close = getattr(chunks, "close", None)
        if callable(close):
            close()

# Ollama parses Qwen3.5's tool calls (XML); a very long call that ends before it closes fails inside Ollama and comes
# back as an exception, not a reply (E-044). The model is told and tries again in smaller parts.
MAX_BAD_TOOL_CALLS = 2
BAD_TOOL_CALL_NOTE = (
    "[Mitra: your last tool call could not be read ({error}). It was probably too long and ended before it was "
    "closed. Nothing was run and nothing was written. Try again in smaller parts: write_file with the first ~100 "
    "lines, then append_file for the rest. Keep a report short, or write it to a file in parts the same way.]"
)


MAX_LEFT_BYTES = 200_000   # files bigger than this are not compared for corrections
MAX_DIFF_CHARS = 4_000
_PRIVATE = (".env", ".pem", ".key", "id_rsa", "credentials", "secrets")


def _rel(path: str, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_small(p: Path) -> str | None:
    """Text of a file Mitra may compare; None for missing, binary, big or private-looking files."""
    name = p.name.lower()
    if any(name == x or name.startswith(x) or name.endswith(x) for x in _PRIVATE):
        return None
    try:
        if not p.is_file() or p.stat().st_size > MAX_LEFT_BYTES:
            return None
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _short_diff(rel: str, old: str | None, new: str | None) -> tuple[str, int, int]:
    a, b = (old or "").splitlines(), (new or "").splitlines()
    lines = list(difflib.unified_diff(a, b, f"mitra/{rel}", f"you/{rel}", lineterm="", n=2))
    added = sum(1 for x in lines if x.startswith("+") and not x.startswith("+++"))
    removed = sum(1 for x in lines if x.startswith("-") and not x.startswith("---"))
    text = "\n".join(lines)
    return (text[:MAX_DIFF_CHARS] + ("\n… (cut)" if len(text) > MAX_DIFF_CHARS else "")), added, removed


def turn_outcome(res) -> str:
    """One label per turn for the dashboard and the training-data filter (D-041)."""
    if res.stopped:
        return "stopped_by_user" if "esc" in (res.stop_reason or "") else "stopped"
    if res.tests_run:
        return "tests_passed" if res.last_test_ok else "tests_failed"
    return "answered"


def is_connection_error(exc: BaseException) -> bool:
    """The connection to Ollama broke (restart, update, crash), not a model error (E-047)."""
    text = str(exc).lower()
    return (isinstance(exc, ConnectionError) or type(exc).__name__ in ("ConnectError", "RemoteProtocolError",
                                                                      "ReadError")
            or any(s in text for s in ("10054", "10061", "forcibly closed", "connection reset", "connection refused")))


class RemoteGone(Exception):
    """The remote GPU (Kaggle) stopped answering: switch to the laptop, write the report, stop (D-062 B3)."""


def is_remote_down(exc: BaseException) -> bool:
    """A remote that is gone: a lost connection, a tunnel that no longer resolves, or Cloudflare's 5xx pages."""
    if is_connection_error(exc):
        return True
    text = str(exc).lower()
    status = getattr(exc, "status_code", None)
    return status in (502, 503, 504, 530) or any(s in text for s in (
        "getaddrinfo", "name or service not known", "nodename nor servname", "trycloudflare", "error 1033",
        "connecterror", "timed out"))


def wait_for_ollama(base_url: str | None = None, timeout_s: float = 90, poll_s: float = 3) -> bool:
    """True once Ollama answers again (within timeout_s)."""
    import urllib.request
    url = (base_url or "http://127.0.0.1:11434").rstrip("/").removesuffix("/v1") + "/api/version"
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return True
        except OSError:
            time.sleep(poll_s)
    return False


def is_tool_call_parse_error(exc: BaseException) -> bool:
    """Ollama's 'XML syntax error ...' / 'tool call parsing failed' (ollama.ResponseError) for a broken tool call."""
    text = str(exc)
    return type(exc).__name__ == "ResponseError" and ("XML syntax error" in text or "tool call" in text.lower())
MAX_STEPS = 40

EXTRA_SPECS = [
    {"name": "run_command", "description": "Run ONE command in the project folder (tests, git, pip). No pipes, "
                                           "redirects or cd; use python -m pytest.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "web_search", "description": "Search Wikipedia, Hugging Face, GitHub, arXiv and the Ollama library. "
                                          "Short queries.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "fetch_url", "description": "Read a web page (Hugging Face and GitHub pages give their README).",
     "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "mcp_find", "description": "Find tools on the connected MCP servers (git, GitHub, docs, ...).",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "mcp_call", "description": "Call an MCP tool found with mcp_find.",
     "parameters": {"type": "object", "properties": {"server": {"type": "string"}, "tool": {"type": "string"},
                                                     "arguments": {"type": "object"}},
                    "required": ["server", "tool"]}},
    {"name": "run_plan", "description": "Build a plan file task by task: implement each task until its "
                                        "'Done when' tests pass, then run all tests. Runs in the plan's folder.",
     "parameters": {"type": "object", "properties": {"plan_path": {"type": "string"}},
                    "required": ["plan_path"]}},
]


def repair_history(messages: list) -> int:
    """After an interrupted turn: give every tool call a result, so the next model call is valid. Returns how many."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    added = 0
    i = 0
    while i < len(messages):
        m = messages[i]
        if isinstance(m, AIMessage) and m.tool_calls:
            j = i + 1
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                j += 1  # add missing results after the ones that exist, in call order
            for tc in m.tool_calls:
                if tc.get("id") not in answered:
                    messages.insert(j, ToolMessage(content="✗ Not run: the turn was interrupted.", tool_call_id=tc["id"]))
                    answered.add(tc.get("id"))
                    added += 1
                    j += 1
        i += 1
    return added


def tool_specs(mode: str) -> list[dict]:
    specs = [s for s in T.TOOL_SPECS if s["name"] != "finish"] + EXTRA_SPECS
    if mode in ("plan", "read-only"):
        specs = [s for s in specs if s["name"] in READ_ONLY_TOOLS]
    return specs


def diff_text(rel: str, old: str | None, new: str, max_lines: int = 80) -> str:
    lines = list(difflib.unified_diff((old or "").splitlines(), new.splitlines(),
                                      fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm=""))
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"… {len(lines) - max_lines} more diff lines"]
    return "\n".join(lines) if lines else "(no change)"


def _no_activity(label: str):
    import contextlib
    return contextlib.nullcontext()


@dataclass
class Hooks:
    """What the chat needs from the terminal (main.py provides these)."""
    stream: Callable                      # (chunks, step=n) -> ui.StreamResult-like (text, message, stopped, printed)
    show: Callable[[str, dict, str, bool], None]  # (tool, args, output, ok)
    confirm: Callable[[str, str, str], bool]      # (title, detail, question) -> approved
    run_shell: Callable[[str], tuple[str, bool]]  # command -> (output for the model, ok)
    web_search: Callable[[str], str]
    fetch_url: Callable[[str], str]
    mcp_find: Callable[[str], str]
    mcp_call: Callable[[str, str, dict], str]
    on_plan_event: Callable | None = None  # core loop events while run_plan works
    # (rel, old text or None, new text) -> "yes" | "all" | "no: <reason>"; None = use `confirm` with a plain diff
    confirm_write: Callable[[str, str | None, str], str] | None = None
    working: Callable[[str], object] = _no_activity  # (label) -> context manager shown while a tool runs


@dataclass
class TurnResult:
    text: str = ""
    steps: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    ctx_used: int = 0
    stopped: bool = False
    stop_reason: str = ""
    journal: list = field(default_factory=list)
    tests_run: int = 0
    last_test_ok: bool | None = None
    last_test_summary: str = ""
    remote_gone: bool = False  # the remote GPU stopped mid-turn (D-062 B3)
    first_s: float | None = None  # time to the first answer word or tool call of the turn (D-068)


class ChatSession:
    def __init__(self, *, workspace: str | Path, llm, hooks: Hooks, mode: str = "approve", num_ctx: int = 131072,
                 harness=None, traces: bool = True):
        self.llm, self.hooks, self.mode, self.num_ctx = llm, hooks, mode, num_ctx
        self.harness = harness if harness is not None else H.load()
        self.ws = T.Workspace(Path(workspace), read_only=())  # in the chat the user may ask for test edits
        self.ws.spill_dir = self.ws.root / ".mitra" / "output"
        # every step of every turn, scrubbed, one file per day: follow a session live, replay it later (D-022)
        self.rec = core_loop.Recorder(self.ws.root / ".mitra" / "runs" / f"chat-{time.strftime('%Y%m%d')}.jsonl",
                                      traces=traces)  # + full model calls for the fine-tune (D-041)
        self.turn_no = 0
        self.backend_kind = "laptop"  # laptop | remote: a remote that drops raises RemoteGone (D-062)
        self.turn_log: list[dict] = []  # {no, user, outcome, files}: the facts for the Kaggle-ended report
        self._plans_run: dict = {}  # (plan path, text hash) -> result, reset every turn (E-050)
        self._last_user = ""  # start of the last turn's message, named when you mark it (E-052)
        self.last_night: dict | None = None  # a /run started after the last turn: /good /bad judge it (E-052)
        self.approve_all = False  # "yes to all" for the rest of this turn
        self._left: dict[str, str | None] = {}  # file -> content Mitra left at the end of a turn (corrections, item 0)
        # role routing (D-049..D-051): which tools and MCP servers this role may use; None = all
        self.noticed: list[str] = []  # your corrections found at the start of the last turn (shown once)
        self.role = "chat"
        self.allowed_tools: tuple[str, ...] | None = None
        self.allowed_mcp: tuple[str, ...] | None = None
        # D-068 step 0: what the coach needs to see per turn; main sets these before each turn
        self.request_kind = ""      # how the request was sorted (intent.classify, or /plan /do)
        self.path = "loop"          # which path ran it: loop | plan_first | resume_brief (more in later steps)
        self.thinking: bool | None = None  # the model's thinking setting for this role (None = model default)
        self._prev_user_full = ""   # the last request in full, to notice when you ask the same thing again
        self.answer_on_last_step = False  # D-068 step 2: the last step gets no tools, so a turn always ends answered
        self.last_step_note = LAST_STEP_NOTE  # what the model is told on that last step
        self.deciding = False       # D-071 phased: the first call offers only the phase switches (PHASE_SPECS)
        self.phase_request: dict | None = None  # {"name", "args"} when the model chose a phase
        self.end_info: dict = {}    # extra fields for this turn's turn_end row (the explainer's budget, files cited)
        self.last_speed: float | None = None  # tokens/s of the last answer (Ollama's eval_count / eval_duration)
        self.best_speed: dict[str, float] = {}  # per machine this session: a much slower answer = spilled to CPU
        self.cancelled = False      # set from another thread (a score case that timed out): stop before the next
                                    # model call or tool, so an abandoned turn does not keep working in the background

    def apply_route(self, route: dict, llm=None, num_ctx: int | None = None, thinking: bool | None = None) -> None:
        """Switch role: model (if given), tools, MCP servers and read-only paths at once; recorded for the dashboard.
        `thinking` is the effective setting the model was built with (None = the model's default)."""
        self.role = route["role"]
        self.thinking = thinking
        self.allowed_tools = route.get("tools")
        self.allowed_mcp = route.get("mcp")
        self.ws.read_only = tuple(route.get("read_only") or ())
        if llm is not None:
            self.llm = llm
        if num_ctx:
            self.num_ctx = num_ctx
        self.rec.write("route", turn=self.turn_no, role=self.role, model=route.get("model"), source=route.get("source"),
                       tools=list(self.allowed_tools) if self.allowed_tools is not None else "all",
                       mcp=list(self.allowed_mcp) if self.allowed_mcp is not None else "all",
                       thinking=route.get("thinking"), read_only=list(self.ws.read_only), num_ctx=self.num_ctx)

    # ── what you think of Mitra's work (item 0: the strongest self-improvement signals) ────────────────────────
    def note_session(self, **info) -> None:
        """One row per chat session: model, context, memory fit, free RAM/VRAM, Mitra version."""
        from app.core import runinfo
        self.rec.write("session", code_version=runinfo.code_version(), workspace=str(self.ws.root), **info)

    def feedback(self, verdict: str, note: str = "") -> str:
        """`/good` / `/bad`: your verdict on the last thing Mitra did: a /run night started after the last turn, else
        the last turn (the last verdict given counts). The reply names what was marked (E-052)."""
        mark = "👍 good" if verdict == "good" else "👎 bad"
        tail = f": {note}" if note else ""
        if self.last_night:
            n = self.last_night
            self.rec.write("feedback", of_turn=None, of_night=n.get("plan", ""), night_started=n.get("started"),
                           verdict=verdict, note=note[:1000], author="user")
            return f"Night run {Path(n.get('plan', '')).name} marked {mark}{tail}"
        if not self.turn_no:
            return "No turn yet to mark."
        self.rec.write("feedback", of_turn=self.turn_no, verdict=verdict, note=note[:1000], author="user")
        said = f' ("{self._last_user}")' if self._last_user else ""
        return f"Turn {self.turn_no}{said} marked {mark}{tail}"

    def signal(self, name: str, of_turn: int | None = None, **info) -> None:
        """A quiet sign of what you thought of a turn (D-068): rephrase, interrupt, undo, copy."""
        if name not in SIG.SIGNALS:
            raise ValueError(f"unknown signal {name!r}")
        of = self.turn_no if of_turn is None else of_turn
        if not of:
            return
        self.rec.write("signal", of_turn=of, signal=name, author="user", **info)

    def _start_row(self, user: str) -> dict:
        """The turn_start fields every path shares (D-068 step 0 adds kind, path, backend, thinking, notes)."""
        from app.core import runinfo
        return dict(turn=self.turn_no, mode=self.mode, user=str(user)[:2000], harness_version=self.harness.version,
                    model=str(getattr(self.llm, "model", "") or ""), num_ctx=self.num_ctx,
                    code_version=runinfo.code_version(), ram_free_gb=runinfo.ram_free_gb(), role=self.role,
                    request_kind=self.request_kind, path=self.path, backend=self.backend_kind,
                    thinking=self.thinking, notes_version=SIG.notes_version(self.ws.root))

    def _new_turn(self, user: str) -> None:
        """Count a turn; if you asked the same thing again, the turn before gets a rephrase signal."""
        self.turn_no += 1
        if self._prev_user_full and SIG.is_rephrase(self._prev_user_full, str(user)):
            self.signal("rephrase", of_turn=self.turn_no - 1)
        self._prev_user_full = str(user)
        said = " ".join(str(user).split())
        self._last_user = said if len(said) <= 50 else said[:49] + "…"

    def note_request(self, user: str, kind: str, path: str, outcome: str, seconds: float = 0.0, **info) -> None:
        """A request handled outside the chat loop (resume brief, plan first) is still a numbered turn in the records,
        with its kind, path and outcome, so /good, /bad and the coach see it like any other (D-068)."""
        self.request_kind, self.path = kind, path
        self._new_turn(user)
        self.last_night = None
        self.rec.write("turn_start", **self._start_row(user))
        end = dict(turn=self.turn_no, steps=0, stopped=False, reason="", text="", tokens_in=0, tokens_out=0,
                   ctx_used=0, seconds=round(seconds, 1), outcome=outcome, changed=[])
        end.update(info)  # e.g. choice, rounds, steps_passed, or the planner error as `reason`
        self.rec.write("turn_end", **end)
        self.request_kind, self.path = "", "loop"

    def night_started(self, plan: Path, started: float) -> None:
        """/run started a night: /good /bad judge it (E-052), and the files it may change are no longer watched for
        your corrections, since the night changes them, not you (E-057)."""
        self.last_night = {"plan": str(plan), "started": started}
        project = Path(plan).resolve().parent
        for path in list(self._left):
            if Path(path).resolve().is_relative_to(project):
                del self._left[path]

    def _remember_left(self, journal: list) -> None:
        for entry in journal:
            path = entry.get("path")
            if not path:
                continue
            self._left[path] = _read_small(Path(path))

    def _check_corrections(self, of_turn: int) -> int:
        """Files Mitra changed that differ now from what it left: you corrected them. Recorded with a short diff."""
        found = 0
        for path, left in list(self._left.items()):
            now = _read_small(Path(path))
            if now == left:
                continue
            found += 1
            rel = _rel(path, self.ws.root)
            if now is None and Path(path).exists():
                diff, added, removed = "(binary, too big or private: no diff kept)", 0, 0
            else:
                diff, added, removed = _short_diff(rel, left, now)
            self.noticed.append(rel)
            self.rec.write("user_edit", of_turn=of_turn, path=rel, deleted=not Path(path).exists(),
                           added=added, removed=removed, diff=diff, author="user")
            self._left[path] = now
        return found

    # approval for edits in ask mode
    def _before_write(self, rel: str, old: str | None, new: str) -> None:
        if self.mode != "approve" or self.approve_all:
            return
        if self.hooks.confirm_write is not None:
            answer = self.hooks.confirm_write(rel, old, new)
            if answer == "all":
                self.approve_all = True
                return
            if answer == "yes":
                return
            reason = answer.split(":", 1)[1].strip() if ":" in answer else ""
            self.rec.write("declined", turn=self.turn_no, tool="edit", path=rel, reason=reason[:500], author="user")
            raise T.ToolError(f"The user declined the change to {rel}."
                              + (f" Their reason: {reason}" if reason else " Ask what they want instead."))
        title = f"{'Edit' if old is not None else 'Create'} {rel}"
        if not self.hooks.confirm(title, diff_text(rel, old, new), f"{title}?"):
            self.rec.write("declined", turn=self.turn_no, tool="edit", path=rel, reason="", author="user")
            raise T.ToolError(f"The user declined the change to {rel}. Ask what they want instead.")

    def _run(self, name: str, args: dict, plan_runner) -> tuple[str, bool]:
        if self.mode in ("plan", "read-only") and name not in READ_ONLY_TOOLS:
            return f"✗ {name} is not available in plan mode (read-only). Describe the change instead.", False
        if self.allowed_tools is not None and name not in self.allowed_tools:  # the role's promise, enforced (E-055)
            return (f"✗ {name} is not available to the {self.role} role. "
                    f"Available: {', '.join(self.allowed_tools) or 'none'}."), False
        try:
            if name == "run_command":
                out, ok = self.hooks.run_shell(str(args.get("command", "")))
                if not ok:
                    out += T.crash_hint(out)  # where it crashed and what to do next (E4)
                if "user declined" in out:
                    self.rec.write("declined", turn=self.turn_no, tool="run_command",
                                   command=str(args.get("command", ""))[:500], reason="", author="user")
                return out, ok
            if name == "web_search":
                with self.hooks.working(f"Searching: {str(args.get('query', ''))[:50]}"):
                    out = self.hooks.web_search(str(args.get("query", "")))
                return out, not out.startswith("✗")
            if name == "fetch_url":
                with self.hooks.working(f"Reading {str(args.get('url', ''))[:60]}"):
                    out = self.hooks.fetch_url(str(args.get("url", "")))
                return out, not out.startswith("✗")
            if name == "mcp_find":
                return self.hooks.mcp_find(str(args.get("query", ""))), True
            if name == "mcp_call":
                server = str(args.get("server", ""))
                if self.allowed_mcp is not None and server not in self.allowed_mcp:
                    return (f"✗ MCP server '{server}' is not available to the {self.role} role. "
                            f"Available: {', '.join(self.allowed_mcp) or 'none'}."), False
                raw = args.get("arguments") or {}
                if isinstance(raw, str):
                    raw = json.loads(raw) if raw.strip() else {}
                out = self.hooks.mcp_call(str(args.get("server", "")), str(args.get("tool", "")), raw)
                return out, not out.startswith("✗")
            if name == "run_plan":
                return plan_runner(str(args.get("plan_path", "plan.md")))  # never the model's test command (E-050)
        except Exception as exc:
            return f"✗ {name} failed: {type(exc).__name__}: {exc}", False
        label = {"run_tests": "Running tests"}.get(name)
        if label:
            with self.hooks.working(label):
                out, run = core_loop.run_tool(self.ws, name, args)
        else:
            out, run = core_loop.run_tool(self.ws, name, args)
        ok = run.passed if run is not None else not out.startswith("✗")
        return out, ok

    def _run_plan(self, plan_path: str, test_command: str = "python -m pytest -q") -> tuple[str, bool]:
        """E-050: the same check as /run, run inside the plan's folder (its git, its paths), the project's test
        command (never the model's), and one run per unchanged plan per turn."""
        from app.core import plans
        path = self.ws.path(plan_path)
        if not path.is_file():
            return f"✗ No plan file at {plan_path}.", False
        text = path.read_text(encoding="utf-8")
        folder = path.resolve().parent
        _, problem = plans.check_text(text, folder.name)
        if problem:
            return (f"✗ {plan_path} cannot run: {problem} Fix the plan first (format: `### T1: title`, `- Files:`, "
                    "`- Do:`, `- Done when: `<test command>` passes`, `- Needs: T1` or -)."), False
        key = (str(path.resolve()), hash(text))
        if key in self._plans_run:
            return (f"✗ {plan_path} already ran in this turn and has not changed since ({self._plans_run[key]}). "
                    "Running it again gives the same result: tell the user what failed, or change the plan or the "
                    "code first."), False
        _, tasks = core_loop.parse_plan(text)
        if self.mode == "approve" and not self.hooks.confirm(
                f"Run plan {self.ws.rel(path)}", "\n".join(f"{t.id}: {t.title}" for t in tasks),
                f"Build {len(tasks)} tasks in {folder}? Mitra edits files without asking during the run."):
            return "✗ The user declined to run the plan.", False
        if self.ws.journal is None:
            self.ws.journal = []
        # the same journal (absolute paths): /undo and the corrections check see the plan's changes too (E-064)
        ws = self.ws if folder == self.ws.root else T.Workspace(folder, read_only=self.ws.read_only,
                                                                  spill_dir=self.ws.spill_dir, journal=self.ws.journal)
        saved_hook, ws.before_write = ws.before_write, None
        try:
            out = core_loop.run_plan(text, ws, self.llm,
                                     full_test_command=test_command, on_event=self.hooks.on_plan_event,
                                     record_dir=ws.root / ".mitra" / "runs" / "plan", num_ctx=self.num_ctx,
                                     harness=self.harness)
        finally:
            ws.before_write = saved_hook
        self._plans_run[key] = f"{out['passed_tasks']}/{out['total_tasks']} tasks passed"
        lines =[f"Plan: {out['passed_tasks']}/{out['total_tasks']} tasks passed; all tests: {out['final_tests']}"]
        for tid, res in out["tasks"].items():
            lines.append(f"- {tid}: {res['status']} ({res['tests']}) {res['summary'][:120]}")
        return "\n".join(lines), out["final_tests_passed"]

    def reply(self, messages: list, kind: str, llm, notes: str = "") -> TurnResult:
        """The one-call path (D-068 step 1): `llm` is the same model with thinking off; no tools; your notes and a
        short instruction for the kind of request go in just before your message. Recorded as path "reply"."""
        saved = (self.llm, self.allowed_tools, self.request_kind, self.path, self.thinking)
        note = REPLY_NOTES.get(kind, REPLY_NOTES["general"])
        call = list(messages[:-1]) + [SystemMessage(content=(notes + "\n\n" if notes else "") + note), messages[-1]]
        self.llm, self.allowed_tools, self.request_kind, self.path, self.thinking = llm, (), kind, "reply", False
        try:
            res = self.turn(call, max_steps=1)
        finally:
            self.llm, self.allowed_tools, self.request_kind, self.path, self.thinking = saved
        if len(call) > len(messages) + 1 and isinstance(call[-1], AIMessage):
            messages.append(call[-1])  # the history keeps your message and the answer, not the instruction
        return res

    def phased(self, messages: list, notes: str = "") -> TurnResult:
        """D-071 phased: decide first (talk in text, or pick look / change / plan with no real tools), then act in that
        phase with only its tools, its note and its budget, all inside one turn. Recorded as path "phased"."""
        saved = (self.path, self.answer_on_last_step, self.last_step_note, self.allowed_tools)
        note = SystemMessage(content=notes) if notes else None
        if note is not None:
            messages.insert(len(messages) - 1, note)
        self.path, self.phase_request = "phased", None
        try:
            return self.turn(messages, body=self._phased_body)
        finally:
            self.path, self.answer_on_last_step, self.last_step_note, self.allowed_tools = saved
            self.deciding, self.phase_request = False, None
            messages[:] = [m for m in messages if m is not note and not (isinstance(m, HumanMessage) and m.content in (
                ONE_LAST_STEP_NOTE, LAST_STEP_NOTE, EMPTY_ANSWER_NOTE))]

    def _phased_body(self, messages: list, res: TurnResult, max_steps: int) -> TurnResult:
        self.deciding = True
        try:
            res = self._turn(messages, res, 1)
        finally:
            self.deciding = False
        if not self.phase_request:
            return res  # talked: one call
        name = self.phase_request["name"]
        if name not in PHASES:  # it called a real tool by name: the phase that has it
            name = "make_change" if name in ("edit_file", "write_file", "append_file", "make_dir", "run_command",
                                             "run_plan") else "look_at_code"
        phase = PHASES[name]
        messages.append(HumanMessage(content=phase["note"]))
        self.allowed_tools = phase["tools"]
        self.answer_on_last_step, self.last_step_note = True, ONE_LAST_STEP_NOTE
        budget = self.harness.limit(phase["budget"]) if phase["budget"] else 1
        acted = self._turn(messages, TurnResult(journal=res.journal), budget)
        acted.steps += res.steps  # the decide call counts
        return acted

    def converse(self, messages: list, notes: str = "") -> TurnResult:
        """One Mitra (D-071): the model decides whether to talk, look or change; every tool the role allows is
        offered; the step budget ends with an answer (the last step has no tools). Recorded as path "one". `notes`:
        your notes again, only when they changed since the start (they are in the system prompt)."""
        saved = (self.path, self.answer_on_last_step, self.last_step_note)
        note = SystemMessage(content=notes) if notes else None
        if note is not None:
            messages.insert(len(messages) - 1, note)
        self.path, self.answer_on_last_step, self.last_step_note = "one", True, ONE_LAST_STEP_NOTE
        try:
            return self.turn(messages)
        finally:
            self.path, self.answer_on_last_step, self.last_step_note = saved
            messages[:] = [m for m in messages if m is not note and not (
                isinstance(m, HumanMessage) and m.content == ONE_LAST_STEP_NOTE)]

    def explain(self, messages: list, notes: str = "") -> TurnResult:
        """A question about the project's code (D-068 step 2): read-only tools, a budget of `explain_max_steps`
        (6), and the last step has no tools, so it always ends with an answer. The history keeps what was read, so
        a follow-up question can build on it; the instruction itself is taken out again. Recorded as path
        "explain" with the steps used, whether the budget ran out, the files read and the files cited."""
        budget = self.harness.limit("explain_max_steps")
        saved = (self.allowed_tools, self.request_kind, self.path, self.answer_on_last_step)
        note = SystemMessage(content=(notes + "\n\n" if notes else "") + EXPLAIN_NOTE.format(steps=budget))
        messages.insert(len(messages) - 1, note)
        self._explain_from = len(messages) - 1
        self.allowed_tools, self.request_kind, self.path, self.answer_on_last_step = (
            EXPLAIN_TOOLS, "question", "explain", True)
        self.end_info = {"budget": budget}
        try:
            res = self.turn(messages, max_steps=budget)
        finally:
            self.allowed_tools, self.request_kind, self.path, self.answer_on_last_step = saved
            self.end_info = {}
            messages[:] = [m for m in messages if m is not note and not (
                isinstance(m, HumanMessage) and m.content == LAST_STEP_NOTE)]
        return res

    def _explain_info(self, messages: list, res: TurnResult) -> dict:
        read = []
        for m in messages[getattr(self, "_explain_from", 0):]:  # this turn only
            for tc in getattr(m, "tool_calls", None) or []:
                p = str((tc.get("args") or {}).get("path") or "").replace("\\", "/")
                if tc.get("name") == "read_file" and p and p not in read:
                    read.append(p)
        return {"budget_hit": res.steps >= self.end_info.get("budget", 0), "files_read": read[:20],
                "files_cited": cited_files(res.text, self.ws.root)[:20],
                "line_refs": bool(_LINE_REF.search(res.text or "")), "asked": res.text.rstrip().endswith("?")}

    def turn(self, messages: list, *, max_steps: int | None = None, body=None) -> TurnResult:
        """Run the loop on `messages` (the user's message is already the last one). Appends to `messages`."""
        res = TurnResult()
        max_steps = max_steps or self.harness.limit("chat_max_steps")
        self._plans_run = {}
        self.last_night = None
        t0 = time.monotonic()
        user = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        self._new_turn(str(user))
        self._check_corrections(of_turn=self.turn_no - 1)  # attributed to the turn they correct
        self.rec.write("turn_start", **self._start_row(str(user)))
        try:
            res = (body or self._turn)(messages, res, max_steps)
        except RemoteGone as exc:  # D-062 B3: not the model's failure; the chat switches to the laptop and reports
            res.stopped, res.remote_gone = True, True
            res.stop_reason = f"the remote GPU stopped answering ({exc})"
            repair_history(messages)
            self.rec.write("turn_end", turn=self.turn_no, steps=res.steps, stopped=True, reason=res.stop_reason,
                           text="", tokens_in=res.tokens_in, tokens_out=res.tokens_out, ctx_used=res.ctx_used,
                           seconds=round(time.monotonic() - t0, 1), outcome="kaggle_ended",
                           changed=[e["path"] for e in res.journal], first_s=res.first_s)
            self._remember_left(res.journal)
            self.turn_log.append({"no": self.turn_no, "user": str(user)[:300], "outcome": "kaggle_ended",
                                  "files": [e["path"] for e in res.journal]})
            return res
        except BaseException as exc:  # interrupted (esc / ctrl+c) or crashed: still recorded, the analyzer counts it
            self.rec.write("turn_end", turn=self.turn_no, steps=res.steps, stopped=True, interrupted=True,
                           reason=f"interrupted ({type(exc).__name__})", text="", tokens_in=res.tokens_in,
                           outcome="interrupted" if isinstance(exc, KeyboardInterrupt) else "error",
                           tokens_out=res.tokens_out, seconds=round(time.monotonic() - t0, 1),
                           changed=[e["path"] for e in res.journal], first_s=res.first_s)
            if isinstance(exc, KeyboardInterrupt):
                self.signal("interrupt", steps=res.steps)
            self._remember_left(res.journal)
            raise
        self.rec.write("turn_end", turn=self.turn_no, steps=res.steps, stopped=res.stopped, reason=res.stop_reason,
                       text=res.text[:2000], tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                       ctx_used=res.ctx_used, seconds=round(time.monotonic() - t0, 1), outcome=turn_outcome(res),
                       changed=[e["path"] for e in res.journal], first_s=res.first_s,
                       **({**self.end_info, **self._explain_info(messages, res)} if self.end_info else {}))
        self._remember_left(res.journal)
        self.turn_log.append({"no": self.turn_no, "user": str(user)[:300], "outcome": turn_outcome(res),
                              "files": [e["path"] for e in res.journal]})
        return res

    def _turn(self, messages: list, res: TurnResult, max_steps: int) -> TurnResult:
        self.approve_all = False
        self.ws.journal = res.journal
        self.ws.before_write = self._before_write
        specs = H.apply_tools(tool_specs(self.mode), self.harness)
        if self.allowed_tools is not None:  # the role's tool set (routing)
            specs = [s for s in specs if s["name"] in self.allowed_tools]
        if self.deciding:  # D-071 phased: talk, or pick a phase; no real tools yet
            specs = list(PHASE_SPECS)
        bound = self.llm.bind_tools(specs) if specs else self.llm  # the reply path: no tools at all (D-068)
        guard = RepeatGuard(max_repeats=self.harness.limit("max_repeats"),
                            max_failures=self.harness.limit("max_failures"))
        bad_calls = 0
        conn_retried = False
        runaway_retried = False
        empty_nudged = False
        for step in range(1, max_steps + 1):
            if self.cancelled:
                res.stopped, res.stop_reason = True, "cancelled (timed out)"
                return res
            res.steps = step
            last = self.answer_on_last_step and step == max_steps and step > 1
            if last:  # D-068 step 2: no tools on the last step, so the turn ends with an answer
                messages.append(HumanMessage(content=self.last_step_note))
            try:
                chunks = (self.llm if last else bound).stream(messages)
                streamed = self._stream(chunks if self.thinking else guard_runaway(chunks), step)
            except Runaway as exc:  # E-100: invisible thinking until the cap; stop, nudge, one more try
                self.rec.write("runaway", turn=self.turn_no, step=step, error=str(exc), retry=not runaway_retried)
                if runaway_retried:
                    res.stopped, res.stop_reason = True, "the model kept generating without answering"
                    return res
                runaway_retried = True
                self.hooks.show("retry", {}, "the model was generating without answering; asking it to answer now",
                                False)
                messages.append(HumanMessage(content=RUNAWAY_NOTE))
                continue
            except Exception as exc:  # Ollama could not read the model's tool call (E-044)
                if self.backend_kind == "remote" and is_remote_down(exc):  # D-062 B3: a tunnel blip, or gone
                    self.rec.write("model_error", turn=self.turn_no, step=step, error=str(exc)[:500],
                                   retry=not conn_retried, remote=True)
                    if not conn_retried:
                        conn_retried = True
                        self.hooks.show("retry", {}, f"the remote GPU did not answer ({str(exc)[:120]}); trying once more",
                                        False)
                        time.sleep(5)
                        continue
                    raise RemoteGone(str(exc)[:300]) from exc
                if is_connection_error(exc) and not conn_retried:  # Ollama restarted (E-047): wait, retry once
                    conn_retried = True
                    self.rec.write("model_error", turn=self.turn_no, step=step, error=str(exc)[:500], retry=True)
                    self.hooks.show("retry", {}, f"lost Ollama ({exc}); waiting for it to come back", False)
                    if wait_for_ollama(getattr(self.llm, "base_url", None)):
                        continue
                    raise
                if not is_tool_call_parse_error(exc) or bad_calls >= MAX_BAD_TOOL_CALLS:
                    raise
                bad_calls += 1
                self.rec.write("bad_tool_call", turn=self.turn_no, step=step, error=str(exc)[:500])
                self.rec.trace(messages, None, tools=specs, model=str(getattr(self.llm, "model", "") or ""),
                               num_ctx=self.num_ctx, turn=self.turn_no, step=step, purpose="failed",
                               error=str(exc)[:500], harness_version=self.harness.version)
                self.hooks.show("retry", {}, f"tool call cut off ({exc}); asking for smaller parts", False)
                messages.append(HumanMessage(content=BAD_TOOL_CALL_NOTE.format(error=exc)))
                continue
            self._trace(messages, streamed, specs, step)
            if step == 1:
                res.first_s = getattr(streamed, "first_s", None)
            if streamed.stopped:
                messages.append(AIMessage(content=streamed.text))
                res.text, res.stopped, res.stop_reason = streamed.text, True, "stopped by you (esc)"
                self.signal("interrupt", steps=res.steps, how="esc")
                return res
            reply = streamed.message
            if reply is None:
                res.stopped, res.stop_reason = True, "the model returned nothing"
                return res
            meta = getattr(reply, "usage_metadata", None) or {}
            self.rec.write("model", turn=self.turn_no, step=step, text=streamed.text[:4000],
                           tool_calls=reply.tool_calls, tokens_in=meta.get("input_tokens", 0),
                           tokens_out=meta.get("output_tokens", 0))
            res.tokens_in += int(meta.get("input_tokens", 0) or 0)
            res.tokens_out += int(meta.get("output_tokens", 0) or 0)
            res.ctx_used = int(meta.get("input_tokens", 0) or 0) or res.ctx_used
            self._note_speed(getattr(reply, "response_metadata", None) or {})
            if not reply.tool_calls and streamed.text and not last:
                calls, parse_error = text_tool_calls(streamed.text, {s["name"] for s in specs})
                if calls or parse_error:
                    self.rec.write("text_tool_calls", turn=self.turn_no, calls=calls, error=parse_error)
                if calls:  # the model wrote the call as text: run it as a real call
                    reply = AIMessage(content=reply.content, tool_calls=calls,
                                      usage_metadata=getattr(reply, "usage_metadata", None))
                elif parse_error:
                    messages.append(reply)
                    messages.append(HumanMessage(content=parse_error))
                    continue
            if last and reply.tool_calls:  # asked for a tool anyway: keep only its words as the answer
                if not (reply.content or streamed.text):
                    return self._wrap_up(messages, res, f"step limit ({max_steps} steps)")
                reply = AIMessage(content=reply.content or streamed.text or "")
            if not reply.tool_calls and not (streamed.text or "").strip() and not empty_nudged \
                    and step < max_steps and not last:
                empty_nudged = True  # an empty answer is never accepted (non-negotiable): ask once for one
                self.rec.write("empty_answer", turn=self.turn_no, step=step)
                messages.append(HumanMessage(content=EMPTY_ANSWER_NOTE))
                continue
            messages.append(reply)
            if not reply.tool_calls:
                res.text = streamed.text
                return res
            if self.deciding:  # the model chose a phase: record it, answer the switch, and hand back
                tc = reply.tool_calls[0]
                self.phase_request = {"name": tc["name"], "args": tc.get("args") or {}}
                self.rec.write("phase", turn=self.turn_no, step=step, name=tc["name"], args=tc.get("args") or {})
                for t in reply.tool_calls:
                    messages.append(ToolMessage(content=f"ok: {t['name'].replace('_', ' ')}", tool_call_id=t["id"]))
                return res
            stop = ""
            for tc in reply.tool_calls:
                if stop:  # every tool call gets a result, even when the turn is stopping
                    messages.append(ToolMessage(content="✗ Not run: the turn was stopped.", tool_call_id=tc["id"]))
                    continue
                name, args = tc["name"], tc.get("args") or {}
                if self.cancelled:
                    messages.append(ToolMessage(content="✗ Not run: the turn was cancelled.", tool_call_id=tc["id"]))
                    stop = "cancelled (timed out)"
                    continue
                refused = guard.before(name, args)
                if refused:
                    out, ok = refused, False
                else:
                    out, ok = self._run(name, args, self._run_plan)
                if name == "run_tests":
                    res.tests_run += 1
                    res.last_test_ok = ok
                    res.last_test_summary = (out.strip().splitlines() or [""])[0][:200]
                self.hooks.show(name, args, out, ok)
                self.rec.write("tool", turn=self.turn_no, step=step, name=name, args=args, ok=ok, output=out[:3000])
                messages.append(ToolMessage(content=out, tool_call_id=tc["id"]))
                stop = guard.after(name, out, ok) or ""
            if stop:
                return self._wrap_up(messages, res, stop)
        return self._wrap_up(messages, res, f"step limit ({max_steps} model calls)")

    SLOW_FRACTION = 0.5  # slower than half this machine's best answer this session: shown in orange

    def _note_speed(self, meta: dict) -> None:
        """Generation speed from Ollama's own timing (thinking included, prompt reading and loading not)."""
        n, ns = int(meta.get("eval_count") or 0), int(meta.get("eval_duration") or 0)
        if n < 10 or ns <= 0:
            return  # too short to say anything
        self.last_speed = n / (ns / 1e9)
        key = self.backend_kind
        self.best_speed[key] = max(self.best_speed.get(key, 0.0), self.last_speed)

    @property
    def speed_is_slow(self) -> bool:
        best = self.best_speed.get(self.backend_kind, 0.0)
        return bool(self.last_speed and best and self.last_speed < best * self.SLOW_FRACTION)

    def _trace(self, messages, streamed, specs, step: int) -> None:
        reply = streamed.message if streamed.message is not None else AIMessage(content=streamed.text or "")
        self.rec.trace(messages, reply, tools=specs, model=str(getattr(self.llm, "model", "") or ""),
                       num_ctx=self.num_ctx, seconds=getattr(streamed, "seconds", None),
                       thinking=getattr(streamed, "thinking", "") or "", turn=self.turn_no, step=step,
                       stopped=bool(streamed.stopped), harness_version=self.harness.version, role=self.role)

    def _stream(self, chunks, step: int):
        import inspect

        try:
            takes_step = "step" in inspect.signature(self.hooks.stream).parameters
        except (TypeError, ValueError):
            takes_step = False
        return self.hooks.stream(chunks, step=step) if takes_step else self.hooks.stream(chunks)

    def _wrap_up(self, messages: list, res: TurnResult, reason: str) -> TurnResult:
        """The loop was cut short: one call without tools, so the user still hears what was done (E-024)."""
        res.stopped, res.stop_reason = True, reason
        self.rec.write("stopped", turn=self.turn_no, reason=reason)
        if self.cancelled:  # nobody is waiting for this turn any more: no wrap-up call
            return res
        messages.append(HumanMessage(content=(
            f"[Mitra stopped the tools: {reason}.] Tell the user in a few short lines what you did, "
            "what failed and what is left. Do not call tools.")))
        streamed = self._stream(self.llm.stream(messages), res.steps + 1)
        reply = streamed.message if streamed.message is not None else AIMessage(content=streamed.text)
        self.rec.trace(messages, reply, tools=[], model=str(getattr(self.llm, "model", "") or ""),
                       num_ctx=self.num_ctx, seconds=getattr(streamed, "seconds", None),
                       thinking=getattr(streamed, "thinking", "") or "", turn=self.turn_no, step=res.steps + 1,
                       purpose="wrap_up", harness_version=self.harness.version)
        messages.append(reply)
        res.text = streamed.text
        return res
