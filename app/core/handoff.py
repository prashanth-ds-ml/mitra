"""The "Kaggle ended" report (D-062 B3): what was done, from CodeMitra's own records + a short summary by the laptop model.

Written to `<project>/.codemitra/reports/kaggle-ended-<time>.md` and shown in the chat; then CodeMitra stops and waits.
Facts never come from the model: requests, outcomes, changed files, last tests, night progress and Kaggle time are
read from the session (or, at start-up, from the last session's records). The model only writes the summary.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

SUMMARY_PROMPT = (
    "You are writing a handoff note for a developer. The coding session below ran on a remote GPU that has just "
    "stopped. In at most 10 short bullet lines: what was done, what is half done, and the one next step you suggest. "
    "Only use what is in the transcript; say 'unclear' when unsure. No preamble.")
OUTCOME_WORDS = {"tests_passed": "✓ tests passed", "tests_failed": "✗ tests failed", "answered": "answered",
                 "stopped": "stopped", "stopped_by_user": "stopped by you", "interrupted": "interrupted",
                 "error": "error", "kaggle_ended": "cut off: Kaggle ended"}


def turns_from_record(record: Path) -> list[dict]:
    """The last session's turns in a chat record (for the start-up case): [{no, user, outcome, files}]."""
    try:
        rows = [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError):
        return []
    start = max((i for i, r in enumerate(rows) if r.get("kind") == "session"), default=0)
    turns: dict[int, dict] = {}
    for r in rows[start:]:
        k, no = r.get("kind"), r.get("turn")
        if k == "turn_start" and no is not None:
            turns[no] = {"no": no, "user": str(r.get("user") or ""), "outcome": "", "files": []}
        elif k == "turn_end" and no in turns:
            turns[no]["outcome"] = str(r.get("outcome") or "")
            turns[no]["files"] = [str(p) for p in (r.get("changed") or [])]
    return [turns[n] for n in sorted(turns)]


def latest_record(workspace: Path) -> Path | None:
    runs = Path(workspace) / ".codemitra" / "runs"
    found = sorted(runs.glob("chat-*.jsonl"), key=lambda p: p.stat().st_mtime) if runs.is_dir() else []
    return found[-1] if found else None


def _rel(path: str, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return path


def transcript(messages: list, limit_chars: int = 12_000) -> str:
    """The conversation as plain text for the summary: user, CodeMitra, and tool calls by name (newest kept)."""
    lines = []
    for m in messages:
        kind = type(m).__name__
        if kind == "SystemMessage":
            continue
        text = str(getattr(m, "content", "") or "")
        if kind == "HumanMessage":
            lines.append(f"USER: {text[:1500]}")
        elif kind == "AIMessage":
            calls = [c.get("name", "?") for c in (getattr(m, "tool_calls", None) or [])]
            if text.strip():
                lines.append(f"CODEMITRA: {text[:1500]}")
            if calls:
                lines.append(f"CODEMITRA used: {', '.join(calls)}")
        elif kind == "ToolMessage":
            lines.append(f"RESULT: {text[:300]}")
    out = "\n".join(lines)
    return out[-limit_chars:]


def summarize(llm, messages: list, timeout_s: float = 180) -> str:
    """A short summary by the laptop model; "" when it fails or times out (the facts are enough on their own)."""
    if llm is None or not messages:
        return ""
    from langchain_core.messages import HumanMessage, SystemMessage
    prompt = [SystemMessage(content=SUMMARY_PROMPT), HumanMessage(content=transcript(messages))]
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        reply = pool.submit(llm.invoke, prompt).result(timeout=timeout_s)
        return str(getattr(reply, "content", "") or "").strip()
    except (FutureTimeout, Exception):  # noqa: BLE001 - the report is written anyway
        return ""
    finally:
        pool.shutdown(wait=False)


def night_for_report(ns: dict | None, kaggle_started: float | None) -> dict | None:
    """The night run worth naming in a Kaggle-ended report: one still running, or one started in this Kaggle
    session. An old finished night's "elapsed" is the time since it started (live 2026-11-11: "4176 min of up to
    4.0 h"), so a finished night shows no minutes."""
    if not ns or not (ns.get("running") or (kaggle_started and ns.get("started", 0) >= kaggle_started)):
        return None
    return {"state": "running" if ns["running"] else "finished", "plan": Path(str(ns.get("plan", ""))).name,
            "detail": (f"{ns.get('elapsed_min')} min so far, up to {ns.get('hours')} h" if ns["running"]
                       else f"up to {ns.get('hours')} h")}


SHOWN_TURNS = 8  # on screen; the saved report keeps every turn


def _turn_line(t: dict) -> str:
    """'- 12 · you: 1. reading the code → answered': a bullet, so your own '1.' never starts a nested list (E-107)."""
    out = OUTCOME_WORDS.get(t.get("outcome") or "", t.get("outcome") or "")
    text = " ".join(str(t.get("user", "")).split())
    text = text[:120] + ("…" if len(text) > 120 else "")
    return f"- {t['no']} · {text}" + (f" → {out}" if out else "")


def build(*, reason: str, workspace: Path, turns: list[dict], laptop: str, summary: str | None = "",
          last_tests: str = "", night: dict | None = None, kaggle: dict | None = None, now: float | None = None,
          max_turns: int | None = None) -> str:
    """`summary`: None = no summary was tried (Kaggle ended while CodeMitra was closed: the conversation is gone);
    "" = it was tried and failed. `max_turns`: the last N turns only (the screen); None = all (the saved file)."""
    now = now or time.time()
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    # E-107: one fact per line ("Why" and "Now on" ran together); "used" (the session is over), not "this session"
    lines = [f"# Kaggle ended · {when}", "", f"- **Why:** {reason}", f"- **Now on:** {laptop}"]
    if kaggle:
        used = kaggle.get("session_min")
        facts = " · ".join(x for x in (
            f"used {used} min" if used is not None else "",
            f"{kaggle['left_h']:.1f} h left this week" if kaggle.get("left_h") is not None else "") if x)
        if facts:
            lines.append(f"- **Kaggle:** {facts}")
    lines += ["", "## What you asked", ""]
    if turns:
        shown = turns if max_turns is None else turns[-max_turns:]
        if len(shown) < len(turns):
            lines.append(f"- … {len(turns) - len(shown)} earlier")
        lines += [_turn_line(t) for t in shown]
    else:
        lines.append("(no turns recorded)")
    files = sorted({_rel(f, workspace) for t in turns for f in t.get("files", [])})
    if files:  # E-107: "Files changed (none)" said nothing
        lines += ["", "## Files changed", ""]
        lines += [f"- `{f}`" for f in files]
        lines.append("")
        lines.append("`/undo` undoes the last change set; `git diff` shows everything.")
    if last_tests:
        lines += ["", f"**Last test run:** {last_tests}"]
    if night:
        lines += ["", f"**Night run:** {night.get('state', '?')} · {night.get('plan', '')} · "
                      f"{night.get('detail', '')}".rstrip(" ·")]
    # E-105: every start-up report said "could not write a summary" although none is tried there
    if summary is not None:
        lines += ["", "## Summary (by the laptop model)", "", summary or "(the laptop model could not write a "
                                                                         "summary; the facts above are complete)"]
    lines += ["", "## Next", "",
              "CodeMitra stopped here and waits for you: carry on on the laptop by sending a message, or "
              "`/kaggle start` for the GPU again."]
    return "\n".join(lines) + "\n"


def startup_line(turns: list[dict], workspace: Path, session_min: int | None, report: Path) -> str:
    """E-107: Kaggle ended while CodeMitra was closed: one line at start-up, the full report stays in its file.
    '☁ Kaggle ended while CodeMitra was closed · last session 111 min, 30 turns, no files changed · report: …'"""
    files = sorted({_rel(f, workspace) for t in turns for f in t.get("files", [])})
    parts = [f"last session {session_min} min" if session_min is not None else "last session",
             f"{len(turns)} turn{'s' if len(turns) != 1 else ''}"]
    if files:
        named = ", ".join(files[:3]) + (f" +{len(files) - 3}" if len(files) > 3 else "")
        parts.append(f"{len(files)} file{'s' if len(files) != 1 else ''} changed: {named}")
    else:
        parts.append("no files changed")
    try:
        where = report.parent.relative_to(workspace).as_posix() + "/"
    except ValueError:
        where = str(report.parent)
    return f"☁ Kaggle ended while CodeMitra was closed · {', '.join(parts)} · report in {where}"


def write(workspace: Path, text: str, now: float | None = None) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    out = Path(workspace) / ".codemitra" / "reports" / f"kaggle-ended-{stamp}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out
