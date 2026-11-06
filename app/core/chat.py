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
from app.core import loop as core_loop
from app.core import tools as T
from app.core.parse import text_tool_calls

CHAT_PROMPT = """You are Mitra, a local coding assistant working in the user's project folder.

Answer questions directly when you can. For work on the project, use the tools and keep going until it is done:
look first (list_files, read_file, search), make small changes (edit_file, write_file), check them (run_tests or
run_command), and fix what fails. Read a file before you edit it. For a plan file with tasks (plan.md), use run_plan:
it builds the tasks one at a time and runs each task's tests. Use web_search / fetch_url for facts you do not know.

Run the tests right after you write code, before writing more files. Create folders with make_dir.
A new project gets its code, its tests and a plan.md; folders like reference/ or tests/hidden/ are only for test
levels, so do not copy them unless the user asks for a level.

When the work is done, or you need the user, reply in a few short lines: what you did, what is left. Do not describe
changes you did not make."""

READ_ONLY_TOOLS = {"list_files", "read_file", "search", "web_search", "fetch_url", "mcp_find"}  # plan mode
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
                                        "'Done when' tests pass, then run all tests.",
     "parameters": {"type": "object", "properties": {"plan_path": {"type": "string"},
                                                     "test_command": {"type": "string"}},
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


class ChatSession:
    def __init__(self, *, workspace: str | Path, llm, hooks: Hooks, mode: str = "approve", num_ctx: int = 131072):
        self.llm, self.hooks, self.mode, self.num_ctx = llm, hooks, mode, num_ctx
        self.ws = T.Workspace(Path(workspace), read_only=())  # in the chat the user may ask for test edits
        self.ws.spill_dir = self.ws.root / ".mitra" / "output"
        # every step of every turn, scrubbed, one file per day: follow a session live, replay it later (D-022)
        self.rec = core_loop.Recorder(self.ws.root / ".mitra" / "runs" / f"chat-{time.strftime('%Y%m%d')}.jsonl")
        self.turn_no = 0
        self.approve_all = False  # "yes to all" for the rest of this turn

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
            raise T.ToolError(f"The user declined the change to {rel}."
                              + (f" Their reason: {reason}" if reason else " Ask what they want instead."))
        title = f"{'Edit' if old is not None else 'Create'} {rel}"
        if not self.hooks.confirm(title, diff_text(rel, old, new), f"{title}?"):
            raise T.ToolError(f"The user declined the change to {rel}. Ask what they want instead.")

    def _run(self, name: str, args: dict, plan_runner) -> tuple[str, bool]:
        if self.mode in ("plan", "read-only") and name not in READ_ONLY_TOOLS:
            return f"✗ {name} is not available in plan mode (read-only). Describe the change instead.", False
        try:
            if name == "run_command":
                return self.hooks.run_shell(str(args.get("command", "")))
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
                raw = args.get("arguments") or {}
                if isinstance(raw, str):
                    raw = json.loads(raw) if raw.strip() else {}
                out = self.hooks.mcp_call(str(args.get("server", "")), str(args.get("tool", "")), raw)
                return out, not out.startswith("✗")
            if name == "run_plan":
                return plan_runner(str(args.get("plan_path", "plan.md")),
                                   str(args.get("test_command") or "python -m pytest -q"))
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

    def _run_plan(self, plan_path: str, test_command: str) -> tuple[str, bool]:
        path = self.ws.path(plan_path)
        if not path.is_file():
            return f"✗ No plan file at {plan_path}.", False
        _, tasks = core_loop.parse_plan(path.read_text(encoding="utf-8"))
        if not tasks:
            return f"✗ {plan_path} has no tasks in the plan format (### T1: ... with a 'Done when' line).", False
        if self.mode == "approve" and not self.hooks.confirm(
                f"Run plan {self.ws.rel(path)}", "\n".join(f"{t.id}: {t.title}" for t in tasks),
                f"Build {len(tasks)} tasks? Mitra edits files without asking during the run."):
            return "✗ The user declined to run the plan.", False
        saved_hook, self.ws.before_write = self.ws.before_write, None
        try:
            out = core_loop.run_plan(path.read_text(encoding="utf-8"), self.ws, self.llm,
                                     full_test_command=test_command, on_event=self.hooks.on_plan_event,
                                     record_dir=self.ws.root / ".mitra" / "runs" / "plan", num_ctx=self.num_ctx)
        finally:
            self.ws.before_write = saved_hook
        lines = [f"Plan: {out['passed_tasks']}/{out['total_tasks']} tasks passed; all tests: {out['final_tests']}"]
        for tid, res in out["tasks"].items():
            lines.append(f"- {tid}: {res['status']} ({res['tests']}) {res['summary'][:120]}")
        return "\n".join(lines), out["final_tests_passed"]

    def turn(self, messages: list, *, max_steps: int = MAX_STEPS) -> TurnResult:
        """Run the loop on `messages` (the user's message is already the last one). Appends to `messages`."""
        res = TurnResult()
        self.turn_no += 1
        t0 = time.monotonic()
        user = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        self.rec.write("turn_start", turn=self.turn_no, mode=self.mode, user=str(user)[:2000])
        res = self._turn(messages, res, max_steps)
        self.rec.write("turn_end", turn=self.turn_no, steps=res.steps, stopped=res.stopped, reason=res.stop_reason,
                       text=res.text[:2000], tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                       ctx_used=res.ctx_used, seconds=round(time.monotonic() - t0, 1),
                       changed=[e["path"] for e in res.journal])
        return res

    def _turn(self, messages: list, res: TurnResult, max_steps: int) -> TurnResult:
        self.approve_all = False
        self.ws.journal = res.journal
        self.ws.before_write = self._before_write
        specs = tool_specs(self.mode)
        bound = self.llm.bind_tools(specs)
        guard = RepeatGuard(max_repeats=2, max_failures=4)
        for step in range(1, max_steps + 1):
            res.steps = step
            streamed = self._stream(bound.stream(messages), step)
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
                self.hooks.show(name, args, out, ok)
                self.rec.write("tool", turn=self.turn_no, step=step, name=name, args=args, ok=ok, output=out[:3000])
                messages.append(ToolMessage(content=out, tool_call_id=tc["id"]))
                stop = guard.after(name, out, ok) or ""
            if stop:
                return self._wrap_up(messages, res, stop)
        return self._wrap_up(messages, res, f"step limit ({max_steps} model calls)")

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
        messages.append(reply)
        res.text = streamed.text
        return res
