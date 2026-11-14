"""The core agent loop (M1): model -> tools -> results -> repeat, until the tests pass or a limit is hit.

One loop for everything: `codemitra solve`, the plan runner, and (next) the terminal chat. Built for small models:
- the tests decide "done", not the model: a passing test run ends the task;
- a step limit, a repeat guard and a cap on failed test runs stop a stuck model;
- one retry on a failed model call; an empty reply is a mistake the model is told about, never a pass (L-002);
- old tool output is dropped when the context fills, so a long task stays inside num_ctx (L-001);
- every event is recorded to a JSONL file with authorship "mitra" (D-022).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.limits import RepeatGuard
from app.core import harness as H
from app.core import tools as T
from app.core.parse import text_tool_calls
from app.core.scrub import scrub_obj

SYSTEM_PROMPT = """You are CodeMitra, a coding agent. You work inside one project folder using tools.

How to work:
1. Look first: list_files, then read the files that matter (the task, plan.md, the tests).
2. Make small changes. Read a file before you edit it. Create new files with write_file.
3. Run run_tests after each change. Read the failures and fix the code.
4. Never change files under tests/. Make the code pass the tests as they are.
5. When the tests pass you are done; call finish with one line about what you did.

Keep replies short. Use tools instead of describing what you would do. Paths are relative to the project folder."""

COMPACT_AT = 0.75        # share of num_ctx at which old tool output is dropped
FRESH_AT = 0.9           # share of num_ctx at which a fresh round starts (with a handoff note)
KEEP_RECENT = 8          # messages always kept in full
CALL_TIMEOUT_S = 600     # one model call; a stalled call counts as a failed call


@dataclass
class Event:
    kind: str            # "think" | "say" | "tool" | "result" | "tests" | "note" | "done"
    data: dict


@dataclass
class RunResult:
    status: str                      # "passed" | "failed" | "stopped" | "error"
    summary: str
    steps: int = 0
    tests: T.TestRun | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    changed: list[str] = field(default_factory=list)
    record_path: str = ""

    def to_json(self) -> dict:
        return {"status": self.status, "summary": self.summary, "steps": self.steps,
                "tests_passed": bool(self.tests and self.tests.passed),
                "tests": self.tests.summary if self.tests else "", "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out, "seconds": round(self.seconds, 1), "changed": self.changed,
                "record": self.record_path}


def _role(m) -> str:
    return {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}.get(getattr(m, "type", ""), "user")


def message_dict(m) -> dict:
    """A LangChain message as plain data, nothing cut (traces, D-041)."""
    d = {"role": _role(m), "content": m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)}
    if getattr(m, "tool_calls", None):
        d["tool_calls"] = [{"name": c.get("name"), "args": c.get("args"), "id": c.get("id")} for c in m.tool_calls]
    if getattr(m, "tool_call_id", None):
        d["tool_call_id"] = m.tool_call_id
    thinking = (getattr(m, "additional_kwargs", None) or {}).get("reasoning_content")
    if thinking:
        d["thinking"] = thinking
    return d


def _fp(d: dict) -> str:
    import hashlib
    return hashlib.sha1(json.dumps(d, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


class Recorder:
    """Append-only JSONL record of a run (authorship per part, D-022), mirrored to the central store (D-041).

    With traces on, every model call is also saved in full next to the record (`traces/<record>.jsonl`): the
    messages the model got, its reply with thinking and tool calls, model and context. The system prompt + tool specs
    are saved once (`prompt` row, by hash); a call stores only the messages new since the call before it when the
    history just grew (`base`), else all of them (after compaction or a fresh round). `rebuild_calls` undoes this."""

    def __init__(self, path: Path | None, *, traces: bool = True):
        self.path = path
        self.trace_path = (path.parent / "traces" / f"{path.stem}.jsonl") if (path and traces) else None
        self._prompts: set[str] = set()
        self._calls = 0
        self._last: list[str] = []  # fingerprints of the last call's input + reply
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, path: Path, row: dict) -> None:
        # secrets never reach a record or a trace: both may become training data (D-022)
        line = json.dumps(scrub_obj(row), ensure_ascii=False, default=str) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
        from app.core import store
        store.append(path, line)  # central copy: never lost with the project (D-041)

    def write(self, kind: str, **data) -> None:
        if not self.path:
            return
        self._append(self.path, {"t": time.time(), "kind": kind, "author": data.pop("author", "mitra"), **data})

    def trace(self, messages: list, reply, *, tools: list | None = None, model: str = "", num_ctx: int = 0,
              seconds: float | None = None, thinking: str = "", **meta) -> None:
        """Save one model call in full. Never raises: a trace must not break a run."""
        if not self.trace_path:
            return
        try:
            msgs = [message_dict(m) for m in messages]
            prompt = ""
            if msgs and msgs[0]["role"] == "system":
                prompt = _fp({"system": msgs[0]["content"], "tools": tools or []})[:16]
                if prompt not in self._prompts:
                    self._prompts.add(prompt)
                    self._append(self.trace_path, {"t": time.time(), "kind": "prompt", "hash": prompt,
                                                   "system": msgs[0]["content"], "tools": tools or []})
                msgs[0] = {"role": "system", "prompt": prompt}
            fps = [_fp(m) for m in msgs]
            grew = bool(self._last) and fps[:len(self._last)] == self._last
            new = msgs[len(self._last):] if grew else msgs
            out = message_dict(reply) if reply is not None else None
            if out is not None and thinking and "thinking" not in out:
                out["thinking"] = thinking  # the chat streams thinking separately from the reply
            self._calls += 1
            meta_in, meta_out = _tokens(reply) if reply is not None else (0, 0)
            from app.core import runinfo
            self._append(self.trace_path, {
                "t": time.time(), "kind": "call", "id": self._calls, "base": self._calls - 1 if grew else None,
                "author": "mitra", "model": model, "num_ctx": num_ctx, "prompt": prompt, "new": new, "reply": out,
                "seconds": round(seconds, 2) if seconds is not None else None, "tokens_in": meta_in,
                "tokens_out": meta_out, "code_version": runinfo.code_version(),
                **(runinfo.ollama_timings(reply) if reply is not None else {}), **meta})
            self._last = fps + ([_fp(out)] if out else [])
        except Exception:
            pass


def rebuild_calls(rows: list[dict]) -> list[dict]:
    """From trace rows back to full calls: [{"messages": [...], "reply": {...}, "tools": [...], **meta}]."""
    prompts = {r["hash"]: r for r in rows if r.get("kind") == "prompt"}
    out, history = [], []
    for r in rows:
        if r.get("kind") != "call":
            continue
        base = history if r.get("base") is not None else []
        msgs = base + [dict(m) for m in r.get("new") or []]
        p = prompts.get(r.get("prompt") or "")
        full = [{"role": "system", "content": p["system"]} if (m.get("role") == "system" and "prompt" in m and p)
                else m for m in msgs]
        out.append({**{k: v for k, v in r.items() if k not in ("new",)}, "messages": full,
                    "tools": p["tools"] if p else []})
        history = msgs + ([r["reply"]] if r.get("reply") else [])
    return out


def _tokens(msg) -> tuple[int, int]:
    meta = getattr(msg, "usage_metadata", None) or {}
    return int(meta.get("input_tokens", 0) or 0), int(meta.get("output_tokens", 0) or 0)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def _compact(messages: list) -> int:
    """Drop the content of old tool results (keeps the conversation shape). Returns how many were dropped."""
    n = 0
    for m in messages[2:-KEEP_RECENT]:
        if isinstance(m, ToolMessage) and not str(m.content).startswith("[old output removed"):
            m.content = "[old output removed to save context; call the tool again if you need it]"
            n += 1
    return n


def call_model(bound, messages: list, timeout: float):
    """bound.invoke(messages) with a time limit (E: a stalled model must not hang the loop forever)."""
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(bound.invoke, messages)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"the model did not answer within {timeout:.0f}s") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def handoff_note(task: str, ws: T.Workspace, last: T.TestRun | None, round_no: int, reason: str) -> str:
    """Short status for a fresh round (dsh tool-ralph): what was done, the evidence, the next step."""
    tail = "\n".join((last.output if last else "").splitlines()[-25:])
    changed = ", ".join(sorted(ws.changed)) or "none"
    return (f"Task:\n{task}\n\nThis is round {round_no}; the previous round ended because {reason}.\n"
            f"- Files changed so far (kept on disk): {changed}\n"
            f"- Last test result: {last.summary if last else 'not run yet'}\n"
            + (f"- Last test output (end):\n{tail}\n" if tail else "")
            + "- Next step: read the failing test and the code it calls, fix the cause, then run_tests.\n"
            f"Test command: {ws.test_command}")


def run_tool(ws: T.Workspace, name: str, args: dict) -> tuple[str, T.TestRun | None]:
    """Run one tool; mistakes come back as text starting with ✗ (never an exception)."""
    args = args or {}
    try:
        if name == "list_files":
            return T.list_files(ws, args.get("path", ".")), None
        if name == "read_file":
            return T.read_file(ws, args.get("path", ""), args.get("start", 1), args.get("end", 0)), None
        if name == "search":
            return T.search(ws, args.get("pattern", ""), args.get("path", ".")), None
        if name == "make_dir":
            return T.make_dir(ws, args.get("path", "")), None
        if name == "write_file":
            return T.write_file(ws, args.get("path", ""), args.get("content", "")), None
        if name == "edit_file":
            return T.edit_file(ws, args.get("path", ""), args.get("old", ""), args.get("new", "")), None
        if name == "append_file":
            return T.append_file(ws, args.get("path", ""), args.get("content", "")), None
        if name == "check_code":
            return T.check_code(ws, args.get("path", ".") or "."), None
        if name == "run_tests":
            folder, path = str(args.get("folder") or "").strip("/\\"), str(args.get("path") or "")
            if folder and path:  # E-126: a path inside the project folder is given relative to it
                full, base = ws.path(path), ws.path(folder)
                try:
                    path = full.relative_to(base).as_posix()
                except ValueError:
                    folder = ""  # a file outside the project folder: run from the workspace root
            extra = T.test_args(ws, "", str(args.get("keyword") or ""), bool(args.get("first_failure")))
            if path:
                extra = [path if folder else ws.rel(ws.path(path))] + extra
            run = T.run_tests(ws, extra=extra, folder=folder)
            head = "PASSED" if run.passed else "FAILED"
            scope = f" ({' '.join(([f'in {folder}/'] if folder else []) + extra)})" if extra or folder else ""
            return f"{head}{scope}: {run.summary}\n\n{run.output}", run
        return (f"✗ Unknown tool '{name}'. Tools: list_files, read_file, search, make_dir, write_file, edit_file, "
                "append_file, check_code, run_tests, finish."), None
    except T.ToolError as exc:
        return f"✗ {exc}", None
    except Exception as exc:  # a crash in a tool is reported, never fatal (E-018)
        return f"✗ {name} failed: {type(exc).__name__}: {exc}", None


def solve(
    task: str,
    ws: T.Workspace,
    llm,
    *,
    max_steps: int | None = None,
    max_failed_finishes: int = 3,
    num_ctx: int = 65536,
    on_event: Callable[[Event], None] | None = None,
    record_path: Path | None = None,
    context: str = "",
    call_timeout: float = CALL_TIMEOUT_S,
    fresh_round_after: int | None = None,
    max_rounds: int = 3,
    rollback: bool = False,
    harness=None,
) -> RunResult:
    """Work on `task` in `ws` until `ws.test_command` passes or a limit is hit."""
    emit = on_event or (lambda e: None)
    h = harness if harness is not None else H.load()
    max_steps = max_steps or h.limit("solve_max_steps")
    fresh_round_after = fresh_round_after or h.limit("fresh_round_after")
    system_prompt = H.apply_prompt(SYSTEM_PROMPT, h)
    specs = H.apply_tools(T.TOOL_SPECS, h)
    rec = Recorder(record_path)
    t0 = time.monotonic()
    result = RunResult(status="stopped", summary="", record_path=str(record_path or ""))
    from app.core import runinfo
    rec.write("start", task=task, test_command=ws.test_command, workspace=str(ws.root), max_steps=max_steps,
              harness_version=h.version, code_version=runinfo.code_version(), ram_free_gb=runinfo.ram_free_gb(),
              model=str(getattr(llm, "model", "") or ""), num_ctx=num_ctx)

    files = T.list_files(ws)
    user = (f"Task:\n{task}\n\n" + (f"{context}\n\n" if context else "")
            + f"Test command: {ws.test_command}\n\nFiles in the project:\n{files}")
    messages: list = [SystemMessage(content=system_prompt), HumanMessage(content=user)]
    bound = llm.bind_tools(specs)
    known = {s["name"] for s in specs}
    guard = RepeatGuard(max_repeats=h.limit("max_repeats"), max_failures=h.limit("max_failures"))
    failed_finishes = empty_replies = failing_runs = 0
    round_no = 1
    if ws.journal is None:
        ws.journal = []
    journal_start = len(ws.journal)

    def fresh_round(reason: str) -> None:
        nonlocal messages, guard, failing_runs, round_no
        round_no += 1
        note = handoff_note(task, ws, result.tests, round_no, reason)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=note)]
        guard = RepeatGuard(max_repeats=h.limit("max_repeats"), max_failures=h.limit("max_failures"))
        failing_runs = 0
        rec.write("fresh_round", round=round_no, reason=reason)
        emit(Event("note", {"text": f"fresh round {round_no}: {reason}"}))

    def finish_with(status: str, summary: str) -> RunResult:
        if status != "passed" and rollback:
            undone = T.rollback(ws.journal[journal_start:])
            del ws.journal[journal_start:]
            if undone:
                summary += f" Rolled back {undone} file change(s)."
                rec.write("rollback", files=undone)
        result.status, result.summary = status, summary
        result.seconds = time.monotonic() - t0
        result.changed = sorted(ws.changed)
        rec.write("end", **result.to_json())
        emit(Event("done", result.to_json()))
        return result

    for step in range(1, max_steps + 1):
        result.steps = step
        reply = None
        for attempt in range(2):  # one retry on a failed call
            try:
                t_call = time.monotonic()
                reply = call_model(bound, messages, call_timeout)
                rec.trace(messages, reply, tools=specs, model=str(getattr(llm, "model", "") or ""), num_ctx=num_ctx,
                          seconds=time.monotonic() - t_call, step=step, harness_version=h.version)
                break
            except Exception as exc:
                rec.write("model_error", error=str(exc), attempt=attempt)
                rec.trace(messages, None, tools=specs, model=str(getattr(llm, "model", "") or ""), num_ctx=num_ctx,
                          step=step, purpose="failed", error=str(exc)[:500], harness_version=h.version)
                emit(Event("note", {"text": f"model call failed: {exc}", "ok": False}))
                time.sleep(1)
        if reply is None:
            return finish_with("error", "The model call failed twice. Is Ollama running?")

        t_in, t_out = _tokens(reply)
        result.tokens_in += t_in
        result.tokens_out += t_out
        thinking = (getattr(reply, "additional_kwargs", None) or {}).get("reasoning_content", "")
        text = _strip_think(reply.content if isinstance(reply.content, str) else "")
        parse_error = ""
        if not reply.tool_calls and text:
            calls, parse_error = text_tool_calls(text, known)
            if calls:  # the model wrote the call as text: run it as a real call
                reply = AIMessage(content=reply.content, tool_calls=calls,
                                  usage_metadata=getattr(reply, "usage_metadata", None))
                rec.write("text_tool_calls", calls=calls)
        messages.append(reply)
        rec.write("model", step=step, text=text, thinking=thinking[:4000], tool_calls=reply.tool_calls,
                  tokens_in=t_in, tokens_out=t_out)
        if thinking:
            emit(Event("think", {"tokens": len(thinking) // 4}))
        if text:
            emit(Event("say", {"text": text}))

        if t_in > num_ctx * FRESH_AT and round_no < max_rounds and not reply.tool_calls:
            fresh_round(f"the context was {t_in:,} tokens")
            continue
        if t_in > num_ctx * COMPACT_AT:
            dropped = _compact(messages)
            if dropped:
                rec.write("compact", dropped=dropped, tokens_in=t_in)
                emit(Event("note", {"text": f"context {t_in:,} tokens: dropped {dropped} old tool outputs"}))

        if not reply.tool_calls:
            if parse_error:
                messages.append(HumanMessage(content=parse_error))
                continue
            empty_replies += 1
            if empty_replies >= 3:
                return finish_with("stopped", "The model stopped using tools before the tests passed.")
            messages.append(HumanMessage(content=(
                "Use the tools to continue: change the code, then run_tests. Call finish only when the tests pass.")))
            continue
        empty_replies = 0

        for tc in reply.tool_calls:
            name, args = tc["name"], tc.get("args") or {}
            if name == "finish":
                run = T.run_tests(ws)
                result.tests = run
                emit(Event("tests", {"passed": run.passed, "summary": run.summary}))
                rec.write("tests", passed=run.passed, summary=run.summary, full=run.full_path)
                if run.passed:
                    messages.append(ToolMessage(content="Tests pass. Done.", tool_call_id=tc["id"]))
                    return finish_with("passed", str(args.get("summary") or text or "Tests pass."))
                failed_finishes += 1
                messages.append(ToolMessage(content=(
                    f"✗ Not done: the tests still fail ({run.summary}).\n\n{run.output}\n\nFix the code and run_tests."),
                    tool_call_id=tc["id"]))
                if failed_finishes >= max_failed_finishes:
                    return finish_with("failed", f"Called finish {failed_finishes} times with failing tests ({run.summary}).")
                continue

            emit(Event("tool", {"name": name, "args": args}))
            refused = guard.before(name, args)
            if refused:
                output, run = refused, None
            else:
                output, run = run_tool(ws, name, args)
            ok = run.passed if run is not None else not output.startswith("✗")
            emit(Event("result", {"name": name, "args": args, "ok": ok, "output": output}))
            rec.write("tool", name=name, args=args, ok=ok, output=output[:4000])
            messages.append(ToolMessage(content=output, tool_call_id=tc["id"]))
            if run is not None:
                result.tests = run
                emit(Event("tests", {"passed": run.passed, "summary": run.summary}))
                if run.passed:
                    return finish_with("passed", text or f"Tests pass: {run.summary}")
                failing_runs += 1
            stop = guard.after(name, output, ok)
            if stop:
                return finish_with("stopped", stop)
        if failing_runs >= fresh_round_after:
            if round_no >= max_rounds:
                return finish_with("failed", f"Tests still fail after {round_no} rounds "
                                             f"({result.tests.summary if result.tests else 'no test run'}).")
            fresh_round(f"the tests failed {failing_runs} times in a row")

    return finish_with("stopped", f"Step limit reached ({max_steps}) before the tests passed.")


# ── plan runner: the user's loop (plan -> implement -> test -> fix -> repeat), one plan task at a time ──────

@dataclass
class PlanTask:
    id: str
    title: str
    body: str
    test_command: str
    needs: list[str]


def parse_plan(text: str) -> tuple[str, list[PlanTask]]:
    """Split a plan in the playground format (docs/PLAN_FORMAT.md) into its header and tasks."""
    parts = re.split(r"^### (T\d+):\s*(.*)$", text, flags=re.M)
    header = parts[0].replace("## Tasks", "").strip()
    tasks = []
    for i in range(1, len(parts) - 2, 3):
        tid, title, body = parts[i], parts[i + 1].strip(), parts[i + 2].strip()
        cmd = re.search(r"Done when:\s*`([^`]+)`", body)
        needs = re.search(r"Needs:\s*(.*)", body)
        need_ids = re.findall(r"T\d+", needs.group(1)) if needs else []
        tasks.append(PlanTask(tid, title, body, cmd.group(1) if cmd else "", need_ids))
    return header, tasks


def _git(ws: T.Workspace, *args: str) -> tuple[int, str]:
    import subprocess

    try:
        p = subprocess.run(["git", *args], cwd=ws.root, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def start_branch(ws: T.Workspace) -> tuple[str, str]:
    """Work on a new branch codemitra/plan-<time> so the user's branch is never touched. Returns (branch, error)."""
    code, top = _git(ws, "rev-parse", "--show-toplevel")
    if code != 0:
        return "", "not a git repository"
    branch = time.strftime("codemitra/plan-%Y%m%d-%H%M%S")
    code, out = _git(ws, "switch", "-c", branch)
    return (branch, "") if code == 0 else ("", out)


def commit_task(ws: T.Workspace, files: list[str], message: str) -> str:
    """Commit only the task's files. Returns the short hash, or "" if nothing was committed."""
    if not files:
        return ""
    _git(ws, "add", "--", *files)
    code, _ = _git(ws, "commit", "-m", message, "--", *files)
    if code != 0:
        return ""
    return _git(ws, "rev-parse", "--short", "HEAD")[1]


def needs_help(task: "PlanTask", res: RunResult, files: list[str]) -> str:
    out = res.tests.output if res.tests else ""
    tail = "\n".join(out.splitlines()[-20:])
    return (f"### {task.id}: {task.title}: needs help\n- Result: {res.status}: {res.summary}\n"
            f"- Files it tried: {', '.join(files) or 'none'} (changes rolled back)\n"
            f"- Test command: `{task.test_command}`\n" + (f"- Last test output:\n```\n{tail}\n```\n" if tail else ""))


def run_plan(plan_text: str, ws: T.Workspace, llm, *, full_test_command: str, max_steps: int | None = None,
             on_event: Callable[[Event], None] | None = None, record_dir: Path | None = None,
             num_ctx: int = 65536, git: bool = True, rollback: bool = True, harness=None) -> dict:
    """For each task: implement until its 'Done when' command passes; then run the full tests."""
    emit = on_event or (lambda e: None)
    t0 = time.monotonic()
    header, tasks = parse_plan(plan_text)
    results: dict[str, RunResult] = {}
    helps: list[str] = []
    commits: dict[str, str] = {}
    branch = ""
    if git:
        branch, why = start_branch(ws)
        emit(Event("note", {"text": f"working on branch {branch}" if branch else f"no git branch ({why})"}))
    if ws.journal is None:
        ws.journal = []
    for task in tasks:
        if any(results.get(n) is None or results[n].status != "passed" for n in task.needs):
            emit(Event("note", {"text": f"{task.id} skipped: needs {', '.join(task.needs)}", "ok": False}))
            continue
        emit(Event("task", {"id": task.id, "title": task.title}))
        ws.test_command = task.test_command or full_test_command
        rec = (record_dir / f"{task.id}.jsonl") if record_dir else None
        start = len(ws.journal)
        res = solve(f"{task.id}: {task.title}\n{task.body}", ws, llm, max_steps=max_steps,
                    on_event=on_event, record_path=rec, context=f"The plan's shared notes:\n{header}",
                    num_ctx=num_ctx, rollback=rollback, harness=harness)
        results[task.id] = res
        files = sorted({T.Path(e["path"]).resolve().relative_to(ws.root).as_posix() for e in ws.journal[start:]}
                       | set(res.changed))
        if res.status == "passed" and branch:
            commits[task.id] = commit_task(ws, files, f"codemitra: {task.id} {task.title}")
        elif res.status != "passed":
            helps.append(needs_help(task, res, files))
    ws.test_command = full_test_command
    final = T.run_tests(ws)
    emit(Event("tests", {"passed": final.passed, "summary": final.summary, "final": True}))
    report = {"tasks": {k: v.to_json() for k, v in results.items()},
              "passed_tasks": sum(1 for v in results.values() if v.status == "passed"),
              "total_tasks": len(tasks), "final_tests_passed": final.passed, "final_tests": final.summary,
              "needs_help": helps, "branch": branch, "commits": commits,
              "seconds": round(time.monotonic() - t0), "tokens_in": sum(v.tokens_in for v in results.values()),
              "tokens_out": sum(v.tokens_out for v in results.values())}
    if record_dir:
        record_dir.mkdir(parents=True, exist_ok=True)
        (record_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if helps:
            (record_dir / "needs-help.md").write_text("# Needs help\n\n" + "\n".join(helps), encoding="utf-8")
    return report
