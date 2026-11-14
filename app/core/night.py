"""`codemitra night` / `/run`: a plan built unattended, with a time limit (the overnight stopgap before I-16).

It runs `codemitra solve --plan <plan> --json` as a child process in the project folder, keeps Windows awake while it
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


def check_plan(plan: Path) -> tuple[int, str]:
    """(number of tasks, problem) before anything starts: a plan with no tasks or no 'Done when' test is refused."""
    from app.core import plans
    try:
        return plans.check_text(plan.read_text(encoding="utf-8"), plan.resolve().parent.name)
    except OSError as exc:
        return 0, f"cannot read {plan}: {exc}"


def _state_file() -> Path:
    from app import config
    return config._mitra_home() / "night.json"


def launch(plan: Path, project: Path, hours: float, model: str) -> dict:
    """Start `codemitra night` in the background: no window, and it keeps running if CodeMitra is closed."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    console_log = project / ".codemitra" / f"night-console-{stamp}.log"
    console_log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "app.main", "night", str(plan), "--workspace", str(project), "--hours", str(hours)]
    if model:
        cmd += ["--model", model]
    flags = (0x08000000 | 0x00000200) if os.name == "nt" else 0  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}
    fh = console_log.open("w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parents[2]), stdout=fh, stderr=subprocess.STDOUT,
                            creationflags=flags, env=env, start_new_session=(os.name != "nt"))
    info = {"pid": proc.pid, "project": str(project), "plan": str(plan), "model": model, "hours": hours,
            "started": time.time(), "console_log": str(console_log)}
    _state_file().parent.mkdir(parents=True, exist_ok=True)
    _state_file().write_text(json.dumps(info, indent=1), encoding="utf-8")
    info["proc"] = proc
    return info


def _alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != "zombie"
    except Exception:
        return False


def tail(path: Path, n: int = 15) -> str:
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    except OSError:
        return ""
    return "\n".join(lines[-n:])


def status(n: int = 15) -> dict | None:
    """The latest night (from ~/.codemitra/night.json): running?, elapsed, last log lines, the report when done."""
    try:
        info = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    project = Path(info["project"])
    logs = sorted(project.glob(".codemitra/night-2*.log"))
    night_log = logs[-1] if logs and logs[-1].stat().st_mtime >= info["started"] - 5 else None
    report_path = project / "NIGHT_REPORT.md"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() and \
        report_path.stat().st_mtime >= info["started"] else ""
    info.update(running=_alive(int(info["pid"])), elapsed_min=round((time.time() - info["started"]) / 60),
                tail=tail(night_log, n) if night_log else tail(Path(info["console_log"]), n),
                night_log=str(night_log or ""), report=report)
    return info


def follow(echo, poll_s: float = 2.0, sleep=time.sleep, max_polls: int | None = None) -> dict | None:
    """Show the latest night's progress live, line by line, until it ends (ctrl+c stops watching, not the night)."""
    st = status(n=10_000)
    if not st:
        return None
    shown = 0
    polls = 0
    while True:
        lines = [ln for ln in (st["tail"] or "").splitlines()]
        for ln in lines[shown:]:
            echo(ln)
        shown = max(shown, len(lines))
        if not st["running"]:
            return st
        polls += 1
        if max_polls is not None and polls >= max_polls:
            return st
        sleep(poll_s)
        new = status(n=10_000)
        if new and new.get("night_log") != st.get("night_log"):
            shown = 0  # the night log replaced the console log: start from its top
        st = new or st


def solve_command(plan: Path, workspace: Path, model: str, write_tests: bool) -> list[str]:
    cmd = [sys.executable, "-m", "app.main", "solve", "--plan", str(plan), "--workspace", str(workspace)]
    if model:
        cmd += ["--model", model]
    if write_tests:
        cmd.append("--write-tests")
    return cmd


def _git_run(workspace: Path, *args: str) -> tuple[int, str]:
    """(exit code, stdout + stderr) of a git command; (-1, why) when git cannot run."""
    try:
        p = subprocess.run(["git", *args], cwd=workspace, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)


def _git(workspace: Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=workspace, capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def kill_tree(proc) -> None:
    """Stop the child and everything it started (pytest, the app under test, a shell command) (E-053).
    Windows: taskkill /T; POSIX: the child runs in its own session, so its whole process group is killed."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        pass


STASH_MESSAGE = "codemitra night: task cut off at the time limit"


def save_cut_off(workspace: Path) -> str:
    """Keep the unfinished work of a task cut off at the time limit (E-053): killing the run skips its rollback.
    Returns "stash" (saved in git stash), "nothing" (no unfinished changes), "no git", or "left: <why>"."""
    code, out = _git_run(workspace, "rev-parse", "--is-inside-work-tree")
    if code != 0 or out.strip() != "true":
        return "no git"
    # the night's logs live in .codemitra and must stay; NIGHT_REPORT.md is rewritten right after (a pop would clash)
    spec = ("--", ".", ":(exclude).codemitra", ":(exclude)NIGHT_REPORT.md")
    code, out = _git_run(workspace, "status", "--porcelain", "--untracked-files=all", *spec)
    if code != 0:
        return f"left: {out[:200]}"
    if not out.strip():
        return "nothing"
    code, out = _git_run(workspace, "stash", "push", "-u", "-m", STASH_MESSAGE, *spec)
    if code != 0:
        return f"left: {out[:200]}"
    return "stash"


def _cut_off_text(cut_off: str) -> str:
    if cut_off == "stash":
        return ("its unfinished changes are in `git stash` (`git stash list` shows them, `git stash pop` brings them "
                "back).")
    if cut_off == "nothing":
        return "it had no unfinished changes to save."
    if cut_off == "no git":
        return "its unfinished changes are left in the folder (no git)."
    if cut_off.startswith("left"):
        why = cut_off.split(":", 1)[1].strip() if ":" in cut_off else ""
        return f"its unfinished changes are left in the folder (git stash failed{': ' + why if why else ''})."
    return "its unfinished changes are left in the folder."


def report(workspace: Path, plan: Path, model: str, hours: float, started: float, ended: float,
           result: dict | None, stopped_at_limit: bool, log: Path, cut_off: str = "") -> str:
    mins = round((ended - started) / 60)
    lines = [f"# Night report: {plan.name}", "",
             f"- When: {time.strftime('%Y-%m-%d %H:%M', time.localtime(started))} → "
             f"{time.strftime('%H:%M', time.localtime(ended))} ({mins} min, limit {hours:g} h)",
             f"- Model: {model or 'the builder role default'}",
             f"- Log: `{log}`"]
    if stopped_at_limit:
        lines.append(f"- **Stopped at the time limit**: the last task was cut off; {_cut_off_text(cut_off)}")
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
              "", "Then mark the night in CodeMitra with `/good` or `/bad <why>`, and look at the dashboard (`codemitra dashboard`)."]
    return "\n".join(lines) + "\n"


def _latest_result(ws: Path, since: float) -> dict | None:
    """The result.json `codemitra solve --plan` left next to its records during this night."""
    found = [p for p in ws.glob(".codemitra/runs/*/result.json") if p.stat().st_mtime >= since - 5]
    if not found:
        return None
    try:
        return json.loads(max(found, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run(plan: str, workspace: str = ".", hours: float = 4.0, model: str = "", write_tests: bool = True,
        echo=print) -> int:
    ws = Path(workspace).resolve()
    plan_path = (ws / plan) if not Path(plan).is_absolute() else Path(plan)
    if not plan_path.is_file():
        echo(f"✗ No plan file at {plan_path}")
        return 2
    n_tasks, problem = check_plan(plan_path)
    if problem:
        echo(f"✗ The plan cannot run: {problem}")
        return 2
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log = ws / ".codemitra" / f"night-{stamp}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    awake = keep_awake(True)
    echo(f"✻ CodeMitra night · {plan_path.name} · {model or 'builder default'} · limit {hours:g} h · "
         f"{'keeping Windows awake' if awake else 'could not keep Windows awake'}")
    echo(f"  log: {log}")
    started = time.time()
    stopped_at_limit = False
    cut_off = ""
    result = None
    mitra_root = Path(__file__).resolve().parents[2]
    try:
        with log.open("w", encoding="utf-8") as fh:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}
            proc = subprocess.Popen(solve_command(plan_path, ws, model, write_tests), cwd=mitra_root, stdout=fh,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env,
                                    **({} if os.name == "nt" else {"start_new_session": True}))
            try:
                proc.wait(timeout=hours * 3600)
            except subprocess.TimeoutExpired:
                stopped_at_limit = True
                kill_tree(proc)  # the whole tree: a killed solve leaves pytest / the app running otherwise (E-053)
        if stopped_at_limit:
            cut_off = save_cut_off(ws)  # killing skips the task's rollback: keep its work, out of the way (E-053)
        result = _latest_result(ws, started)
    finally:
        keep_awake(False)
    ended = time.time()
    md = report(ws, plan_path, model, hours, started, ended, result, stopped_at_limit, log, cut_off=cut_off)
    (ws / "NIGHT_REPORT.md").write_text(md, encoding="utf-8")
    try:
        from app.core import dashboard as D
        D.build()
    except Exception:
        pass
    echo(md)
    return 0 if result and result.get("final_tests_passed") else 1
