"""`mitra night` / `/run`: a plan built unattended, with a time limit (the overnight stopgap before I-16).

It runs `mitra solve --plan <plan> --json` as a child process in the project folder, keeps Windows awake while it
runs (no system settings changed), stops it at the time limit, and writes `NIGHT_REPORT.md` (tasks, tests, the git
branch, how to play) plus a fresh dashboard. Everything the child does is recorded as usual (records, traces).
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def keep_awake(on: bool) -> bool:
    """Ask Windows not to sleep while this process runs (released when it exits). False elsewhere."""
    if os.name != "nt":
        return False
    try:
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except Exception:
        return False


def solve_command(plan: Path, workspace: Path, model: str, write_tests: bool) -> list[str]:
    cmd = [sys.executable, "-m", "app.main", "solve", "--plan", str(plan), "--workspace", str(workspace), "--json"]
    if model:
        cmd += ["--model", model]
    if write_tests:
        cmd.append("--write-tests")
    return cmd


def _git(workspace: Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=workspace, capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def report(workspace: Path, plan: Path, model: str, hours: float, started: float, ended: float,
           result: dict | None, stopped_at_limit: bool, log: Path) -> str:
    mins = round((ended - started) / 60)
    lines = [f"# Night report: {plan.name}", "",
             f"- When: {time.strftime('%Y-%m-%d %H:%M', time.localtime(started))} → "
             f"{time.strftime('%H:%M', time.localtime(ended))} ({mins} min, limit {hours:g} h)",
             f"- Model: {model or 'the builder role default'}",
             f"- Log: `{log}`"]
    if stopped_at_limit:
        lines.append("- **Stopped at the time limit**: the last task was cut off (its changes were rolled back).")
    if result:
        lines += ["", f"## Tasks: {result.get('passed_tasks', 0)}/{result.get('total_tasks', 0)} passed", ""]
        for tid, r in (result.get("tasks") or {}).items():
            mark = "✓" if r.get("status") == "passed" else "✗"
            lines.append(f"- {mark} {tid}: {r.get('status')} · {r.get('tests', '')} · {str(r.get('summary', ''))[:160]}")
        lines += ["", f"## All tests at the end: {result.get('final_tests', '?')}"]
        if result.get("needs_help"):
            lines += ["", "## Needs help"] + [f"- {h}" for h in result["needs_help"]]
    elif not stopped_at_limit:
        lines += ["", "No result from the run: see the log."]
    branch = _git(workspace, "rev-parse", "--abbrev-ref", "HEAD")
    commits = _git(workspace, "log", "--oneline", "-15")
    if branch:
        lines += ["", f"## Git: branch `{branch}`", "```", commits or "(no commits)", "```"]
    lines += ["", "## Try it", "```", r".venv\Scripts\python -m breakout.app" if (workspace / "breakout").is_dir()
              else "(see the plan for how to run it)", "```",
              "", "Then mark the night in Mitra with `/good` or `/bad <why>`, and look at the dashboard (`mitra dashboard`)."]
    return "\n".join(lines) + "\n"


def run(plan: str, workspace: str = ".", hours: float = 4.0, model: str = "", write_tests: bool = True,
        echo=print) -> int:
    ws = Path(workspace).resolve()
    plan_path = (ws / plan) if not Path(plan).is_absolute() else Path(plan)
    if not plan_path.is_file():
        echo(f"✗ No plan file at {plan_path}")
        return 2
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log = ws / ".mitra" / f"night-{stamp}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    awake = keep_awake(True)
    echo(f"✻ Mitra night · {plan_path.name} · {model or 'builder default'} · limit {hours:g} h · "
         f"{'keeping Windows awake' if awake else 'could not keep Windows awake'}")
    echo(f"  log: {log}")
    started = time.time()
    stopped_at_limit = False
    result = None
    mitra_root = Path(__file__).resolve().parents[2]
    try:
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.Popen(solve_command(plan_path, ws, model, write_tests), cwd=mitra_root, stdout=fh,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            try:
                proc.wait(timeout=hours * 3600)
            except subprocess.TimeoutExpired:
                stopped_at_limit = True
                proc.kill()
                proc.wait(timeout=60)
        text = log.read_text(encoding="utf-8", errors="replace")
        start = text.find("{")
        if start >= 0:
            try:
                result = json.loads(text[start:])
            except ValueError:
                result = None
    finally:
        keep_awake(False)
    ended = time.time()
    md = report(ws, plan_path, model, hours, started, ended, result, stopped_at_limit, log)
    (ws / "NIGHT_REPORT.md").write_text(md, encoding="utf-8")
    try:
        from app.core import dashboard as D
        D.build()
    except Exception:
        pass
    echo(md)
    return 0 if result and result.get("final_tests_passed") else 1
