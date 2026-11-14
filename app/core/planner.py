"""Plan first (D-065 P4, P5): a small context pack → a short runnable plan → (you: Go / Change / Save / Cancel) →
the steps run one at a time with fresh context → failed steps re-planned once → `.codemitra/resume.md`.

The plan uses the format `/run` understands (`### T1:` … `- Done when: ` + one command in backticks), so the same
plan can also run unattended. `plans.check_text` checks it; problems go back to the planner once.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

PLAN_TIMEOUT_S = 600
MAX_TREE_LINES = 60
MAX_OUTLINED = 5

PLANNER_PROMPT = """You plan coding work for a small local model that does ONE small step at a time with little
context. Write a plan of 2-6 tasks for the request, in exactly this format and nothing else:

# Feature: <one line>

## Goal
<two sentences: what it does when done>

## Design notes
- <exact names: files, functions, classes, numbers the tests can check>

## Tasks

### T1: <small piece>
- Files: `tests/test_<name>.py`, `<path>.py`
- Do: first write the test, then the code. <one or two sentences>
- Done when: `python -m pytest -q tests/test_<name>.py` passes
- Needs: -

Rules: each task touches at most 3 files and can be done in a few edits; every task has ONE Done-when command in
backticks (no && or pipes; python -m pytest ...); paths are relative to the project folder (as in the file tree);
reuse existing files and names from the outlines; Needs names earlier tasks or -. No text outside the plan."""

REPLAN_PROMPT = """These tasks of the plan failed. Rewrite ONLY them as smaller, clearer tasks (same format, new ids
T101, T102, ...; '- Needs: -'), using what the failure says. No text outside the tasks."""


def _invoke(llm, messages, timeout_s: float = PLAN_TIMEOUT_S) -> str:
    def call() -> str:
        # streamed, not one invoke: over the Kaggle tunnel a reply that sends nothing for 120 s is cut by
        # Cloudflare (error 524, live 2026-11-11); a stream keeps bytes flowing while the plan is written
        if hasattr(llm, "stream"):
            return "".join(str(getattr(c, "content", "") or "") for c in llm.stream(messages))
        return str(getattr(llm.invoke(messages), "content", "") or "")

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(call).result(timeout=timeout_s)
    except FutureTimeout as exc:
        raise TimeoutError(f"the planner did not answer within {timeout_s:.0f} s") from exc
    finally:
        pool.shutdown(wait=False)


DISCUSSION_MAX_CHARS = 4000


def with_discussion(request: str, messages: list, max_chars: int = DISCUSSION_MAX_CHARS) -> str:
    """"ok lets build it" after talking an idea through: the task is the discussion, not those four words.
    The last few user messages and CodeMitra's last answer, newest kept first when it is too long (live 2026-11-11)."""
    from langchain_core.messages import AIMessage, HumanMessage

    talk = [m for m in messages if isinstance(m, (HumanMessage, AIMessage)) and str(m.content or "").strip()
            and not getattr(m, "tool_calls", None)]
    users = [str(m.content).strip() for m in talk if isinstance(m, HumanMessage)
             and not str(m.content).lstrip().startswith(("[CodeMitra", "✗"))][-4:]  # CodeMitra's own notes are not yours
    answer = next((str(m.content).strip() for m in reversed(talk) if isinstance(m, AIMessage)), "")
    parts = [f"- {u[:1200]}" for u in users]
    text = "\n".join(parts) + (f"\n\nCodeMitra's last answer:\n{answer[:2000]}" if answer else "")
    if len(text) > max_chars:
        text = text[-max_chars:]
    return f"{request}\n\nBuild what we discussed just before. What you said, in order:\n{text}" if text else request


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9]{2,}", (text or "").lower())}


def context_pack(root: Path, task: str) -> str:
    """What the planner sees: the resume brief, the file tree, and outlines of the files that match the request."""
    from app.core import resume
    from app.core import tools as T
    ws = T.Workspace(Path(root))
    parts = []
    brief = resume.brief(Path(root), max_chars=1200)
    if brief:
        parts.append(brief)
    try:
        tree = T.list_files(ws, ".").splitlines()
    except T.ToolError:
        tree = []
    shown = tree[:MAX_TREE_LINES] + ([f"… {len(tree) - MAX_TREE_LINES} more"] if len(tree) > MAX_TREE_LINES else [])
    parts.append("## Files\n" + "\n".join(shown))
    want = _words(task)
    scored = []
    for line in tree:
        rel = line.strip().rstrip("/")
        if not rel.endswith((".py", ".md", ".js", ".ts", ".toml", ".json")) or "(" in rel:
            continue
        score = len(want & _words(Path(rel).stem.replace("_", " ").replace("-", " ")))
        score += 0.5 if rel.endswith(".py") else 0
        scored.append((score, rel))
    for _, rel in sorted(scored, reverse=True)[:MAX_OUTLINED]:
        path = Path(root) / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        entries = T.outline_entries(rel, text)
        if entries:
            parts.append(f"## Outline of {rel} ({len(text.splitlines())} lines)\n"
                         + "\n".join(f"{i}: {e}" for i, e in entries[:40]))
    return "\n\n".join(parts)


def extract(text: str) -> str:
    """The plan from a reply: the fenced block that holds it (if any), no chatter before or after."""
    for block in re.findall(r"```[a-zA-Z]*\n(.*?)```", text or "", flags=re.S):
        if "### T" in block:
            text = block
            break
    text = re.sub(r"```[a-zA-Z]*\n?", "", text or "").strip()
    start = min([i for i in (text.find("# Feature"), text.find("### T1")) if i >= 0] or [0])
    return text[start:].strip() + "\n"


def make_plan(llm, task: str, pack: str, *, feedback: str = "", previous: str = "") -> tuple[str, str]:
    """(plan text, problem). One repair round when the plan check finds problems."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core import plans
    ask = f"Request:\n{task}\n\nProject:\n{pack}"
    if previous:
        ask += f"\n\nYour previous plan:\n{previous}\n\nChange it like this: {feedback}"
    msgs = [SystemMessage(content=PLANNER_PROMPT), HumanMessage(content=ask)]
    text = extract(_invoke(llm, msgs))
    _, problem = plans.check_text(text)
    if problem:
        msgs += [HumanMessage(content=f"The plan cannot run: {problem} Write the whole plan again, fixed.")]
        text = extract(_invoke(llm, msgs))
        _, problem = plans.check_text(text)
    return text, problem


def slug(task: str) -> str:
    words = re.findall(r"[a-z0-9]+", (task or "").lower())[:5]
    return "-".join(words) or "task"


def save(root: Path, task: str, text: str) -> Path:
    """`<project>/<slug>.plan.md`: in the project folder, so `/run` runs it there too."""
    path = Path(root) / f"{slug(task)}.plan.md"
    if path.exists():
        path = Path(root) / f"{slug(task)}-{time.strftime('%H%M%S')}.plan.md"
    path.write_text(text, encoding="utf-8")
    return path


def replan_failed(llm, plan_text: str, failures: dict) -> str:
    """Tasks for the failed ones, smaller (ids R1..), or "" when the planner cannot."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core import plans
    from app.core.loop import parse_plan
    header, _ = parse_plan(plan_text)
    detail = "\n".join(f"- {tid}: {why}" for tid, why in failures.items())
    msgs = [SystemMessage(content=PLANNER_PROMPT + "\n\n" + REPLAN_PROMPT),
            HumanMessage(content=f"The plan:\n{plan_text}\n\nFailed:\n{detail}")]
    try:
        tasks = extract(_invoke(llm, msgs))
    except TimeoutError:
        return ""
    text = header.rstrip() + "\n\n## Tasks\n\n" + tasks[tasks.find("### "):] if "### " in tasks else ""
    if not text:
        return ""
    n, problem = plans.check_text(text)
    return "" if problem or not n else text


def resume_note(task: str, plan_path: Path | None, results: dict, final_tests: str) -> str:
    """`.codemitra/resume.md`: what the plan did, so "where did we stop" is instant next time."""
    lines = [f"# Plan: {task[:120]}", f"{time.strftime('%Y-%m-%d %H:%M')}"
             + (f" · plan file: {plan_path.name}" if plan_path else "")]
    next_step = ""
    for tid, r in results.items():
        ok = r.get("status") == "passed"
        lines.append(f"- {tid} {'✓' if ok else '✗'} {r.get('title', '')}: {r.get('tests', '')}".rstrip(": "))
        if not ok and not next_step:
            next_step = f"{tid} {r.get('title', '')}: {str(r.get('summary', ''))[:160]}"
    lines.append(f"- all tests at the end: {final_tests}")
    lines.append(f"Next: {next_step}" if next_step else "Next: all tasks passed; review the changes (`git diff`).")
    return "\n".join(lines) + "\n"
