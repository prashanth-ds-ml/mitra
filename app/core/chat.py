"""The chat on the core loop (M1 stage 2): every message runs one agent loop until the model answers.

Replaces the keyword router and the agent hand-offs (planner / file / shell / reader / web agents). The model gets
the core tools plus shell, web, MCP and the plan runner, and keeps calling them until it gives an answer.

Modes (shift+tab):  ask = approve every edit and command · auto-edit = edits without asking · plan = read-only tools
"""
from __future__ import annotations

import difflib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.limits import RepeatGuard
from app.core import harness as H
from app.core import loop as core_loop
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

READ_ONLY_TOOLS = {"list_files", "read_file", "search", "web_search", "fetch_url", "mcp_find"}  # plan mode

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
    {"name": "run_command", "description": "Run a shell command in the project folder (tests, git, pip, ...).",
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

    def apply_route(self, route: dict, llm=None, num_ctx: int | None = None) -> None:
        """Switch role: model (if given), tools, MCP servers and read-only paths at once; recorded for the dashboard."""
        self.role = route["role"]
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

    def turn(self, messages: list, *, max_steps: int | None = None) -> TurnResult:
        """Run the loop on `messages` (the user's message is already the last one). Appends to `messages`."""
        res = TurnResult()
        max_steps = max_steps or self.harness.limit("chat_max_steps")
        self.turn_no += 1
        self._plans_run = {}
        self.last_night = None
        t0 = time.monotonic()
        user = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        said = " ".join(str(user).split())
        self._last_user = said if len(said) <= 50 else said[:49] + "…"
        from app.core import runinfo
        self._check_corrections(of_turn=self.turn_no - 1)  # attributed to the turn they correct
        self.rec.write("turn_start", turn=self.turn_no, mode=self.mode, user=str(user)[:2000],
                       harness_version=self.harness.version, model=str(getattr(self.llm, "model", "") or ""),
                       num_ctx=self.num_ctx, code_version=runinfo.code_version(), ram_free_gb=runinfo.ram_free_gb(),
                       role=self.role)
        try:
            res = self._turn(messages, res, max_steps)
        except RemoteGone as exc:  # D-062 B3: not the model's failure; the chat switches to the laptop and reports
            res.stopped, res.remote_gone = True, True
            res.stop_reason = f"the remote GPU stopped answering ({exc})"
            repair_history(messages)
            self.rec.write("turn_end", turn=self.turn_no, steps=res.steps, stopped=True, reason=res.stop_reason,
                           text="", tokens_in=res.tokens_in, tokens_out=res.tokens_out, ctx_used=res.ctx_used,
                           seconds=round(time.monotonic() - t0, 1), outcome="kaggle_ended",
                           changed=[e["path"] for e in res.journal])
            self._remember_left(res.journal)
            self.turn_log.append({"no": self.turn_no, "user": str(user)[:300], "outcome": "kaggle_ended",
                                  "files": [e["path"] for e in res.journal]})
            return res
        except BaseException as exc:  # interrupted (esc / ctrl+c) or crashed: still recorded, the analyzer counts it
            self.rec.write("turn_end", turn=self.turn_no, steps=res.steps, stopped=True, interrupted=True,
                           reason=f"interrupted ({type(exc).__name__})", text="", tokens_in=res.tokens_in,
                           outcome="interrupted" if isinstance(exc, KeyboardInterrupt) else "error",
                           tokens_out=res.tokens_out, seconds=round(time.monotonic() - t0, 1),
                           changed=[e["path"] for e in res.journal])
            self._remember_left(res.journal)
            raise
        self.rec.write("turn_end", turn=self.turn_no, steps=res.steps, stopped=res.stopped, reason=res.stop_reason,
                       text=res.text[:2000], tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                       ctx_used=res.ctx_used, seconds=round(time.monotonic() - t0, 1), outcome=turn_outcome(res),
                       changed=[e["path"] for e in res.journal])
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
        bound = self.llm.bind_tools(specs)
        guard = RepeatGuard(max_repeats=self.harness.limit("max_repeats"),
                            max_failures=self.harness.limit("max_failures"))
        bad_calls = 0
        conn_retried = False
        for step in range(1, max_steps + 1):
            res.steps = step
            try:
                streamed = self._stream(bound.stream(messages), step)
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
            if streamed.stopped:
                messages.append(AIMessage(content=streamed.text))
                res.text, res.stopped, res.stop_reason = streamed.text, True, "stopped by you (esc)"
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
            if not reply.tool_calls and streamed.text:
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
            messages.append(reply)
            if not reply.tool_calls:
                res.text = streamed.text
                return res
            stop = ""
            for tc in reply.tool_calls:
                if stop:  # every tool call gets a result, even when the turn is stopping
                    messages.append(ToolMessage(content="✗ Not run: the turn was stopped.", tool_call_id=tc["id"]))
                    continue
                name, args = tc["name"], tc.get("args") or {}
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
