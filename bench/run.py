"""Run one coding agent on benchmark tasks and record everything.

Each run gets a fresh workspace (git repo of the task's start state), a logging proxy in front of Ollama,
a wall-clock timeout, hidden-test grading and a folder under results/runs/<agent>/<model>/<task>/r<rep>/:
  calls.jsonl  every model call (bench/proxy.py)      agent.out / agent.err  agent output
  diff.patch   what the agent changed                  result.json            outcome + metrics
  .complete    written last, holds the run fingerprint (Harness² runmark): only complete runs count, and a
               run is redone when the agent config, agent version, model, task or bench code changed.

Outcome is one of: pass, fail, timeout, infra. "infra" (Ollama down, agent never reached the model, grader
crash) is never scored as an agent failure.

--overhead stops the agent after its first answered model call and records what that call cost (prompt tokens
as Ollama counted them, tool count, sizes): the fixed price an agent pays before doing any work.
Results in results/overhead/<agent>/<model>/.

    python bench/run.py --agent bench/configs/claude-code.toml --model qwen3.5:4b [--task T01] [--reps 1]
    python bench/run.py --agent bench/configs/claude-code.toml --model qwen3.5:4b --overhead
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402
import preflight  # noqa: E402
import proxy  # noqa: E402

REPO = bench.BENCH.parent
RESULTS = REPO / "results" / "runs"
OVERHEAD = REPO / "results" / "overhead"
TEST_HINT = "Run the tests with: python -m pytest -q"
# endpoints that generate; /api/show, /api/tags, /v1/models are lookups, not model calls (E-011)
MODEL_PATHS = ("/api/chat", "/api/generate", "/v1/chat/completions", "/v1/completions", "/v1/messages", "/v1/responses")


@dataclass(frozen=True)
class AgentConfig:
    name: str
    cmd: list[str]
    env: dict[str, str]
    version_cmd: list[str]
    timeout_s: int
    path: Path
    unset_env: list[str] = field(default_factory=list)
    sends_tools: bool = True  # False for agents that edit through text (Aider): overhead = first model call

    @classmethod
    def load(cls, path: Path) -> AgentConfig:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(
            name=data["name"],
            cmd=data["cmd"],
            env=data.get("env", {}),
            version_cmd=data.get("version_cmd", []),
            timeout_s=int(data.get("timeout_s", 900)),
            path=path,
            unset_env=data.get("unset_env", []),
            sends_tools=bool(data.get("sends_tools", True)),
        )


def _fill(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def _sha(*parts: bytes) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(hashlib.sha256(part).digest())
    return h.hexdigest()[:16]


def agent_version(cfg: AgentConfig) -> str:
    if not cfg.version_cmd:
        return "unknown"
    exe = shutil.which(cfg.version_cmd[0]) or cfg.version_cmd[0]
    try:
        out = subprocess.run([exe, *cfg.version_cmd[1:]], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"error: {exc}"
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else "unknown"


def fingerprint(cfg: AgentConfig, version: str, task: bench.Task, model: str, model_digest: str | None) -> str:
    task_files = sorted(p for p in task.dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    base_files = sorted(p for p in bench.BASE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    code = [Path(bench.__file__), Path(proxy.__file__), Path(__file__)]
    return _sha(
        cfg.path.read_bytes(),
        version.encode(),
        model.encode(),
        (model_digest or "").encode(),
        *(p.read_bytes() for p in task_files + base_files + code),
    )


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        children = psutil.Process(proc.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for p in [*children, psutil.Process(proc.pid)] if psutil.pid_exists(proc.pid) else children:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    proc.wait(timeout=30)


def run_with_tree_kill(cmd, cwd, env, stdout, stderr, timeout_s, stop=None) -> tuple[int | None, bool]:
    """Run an agent; on timeout (or when stop() turns true) kill it and every child it started (agents spawn
    node, shells, servers). Returns (exit code or None if killed, timed out)."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            return proc.wait(timeout=1), False
        except subprocess.TimeoutExpired:
            if stop and stop():
                _kill_tree(proc)
                return None, False
    _kill_tree(proc)
    return None, True


def _git(ws: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True, timeout=60).stdout


def _init_repo(ws: Path) -> str:
    """Commit the start state; returns its sha (agents such as Aider commit their own changes)."""
    _git(ws, "init", "-q", "-b", "main")
    _git(ws, "-c", "user.name=bench", "-c", "user.email=bench@localhost", "add", "-A")
    _git(ws, "-c", "user.name=bench", "-c", "user.email=bench@localhost", "commit", "-q", "-m", "task start")
    return _git(ws, "rev-parse", "HEAD").strip()


def _calls(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize_calls(calls: list[dict]) -> dict:
    attempts = [c for c in calls if c["method"] == "POST" and c["path"].split("?")[0].rstrip("/") in MODEL_PATHS]
    model_calls = [c for c in attempts if c.get("status") == 200]
    first = model_calls[0] if model_calls else None
    work = next((c for c in model_calls if c["request"].get("n_tools")), None)
    return {
        "model_calls": len(model_calls),
        "rejected_calls": len(attempts) - len(model_calls),  # e.g. 404 for a model name the agent assumed
        "upstream_errors": sum(1 for c in calls if c.get("status") is None or (c.get("status") or 0) >= 500),
        "first_call_prompt_tokens": first["response"]["prompt_tokens"] if first else None,
        "first_call_tools": first["request"]["n_tools"] if first else None,
        "first_call_tools_chars": first["request"]["tools_chars"] if first else None,
        "first_call_system_chars": first["request"]["system_chars"] if first else None,
        "first_tool_call_index": model_calls.index(work) if work else None,  # earlier calls: titles, summaries
        "first_tool_call_prompt_tokens": work["response"]["prompt_tokens"] if work else None,
        "first_tool_call_tools": work["request"]["n_tools"] if work else None,
        "first_tool_call_tools_chars": work["request"]["tools_chars"] if work else None,
        "first_tool_call_system_chars": work["request"]["system_chars"] if work else None,
        "max_prompt_tokens": max((c["response"]["prompt_tokens"] or 0 for c in model_calls), default=None),
        "total_prompt_tokens": sum(c["response"]["prompt_tokens"] or 0 for c in model_calls),
        "total_output_tokens": sum(c["response"]["output_tokens"] or 0 for c in model_calls),
        "model_seconds": round(sum(c.get("seconds", 0) for c in model_calls), 1),
    }


def classify(exit_code: int | None, timed_out: bool, calls: dict, grade: bench.Grade) -> tuple[str, str]:
    if calls["upstream_errors"]:
        return "infra", f"{calls['upstream_errors']} upstream errors (Ollama down or crashed)"
    if calls["model_calls"] == 0:
        return "infra", "agent never reached the model (config or login problem)"
    if grade.infra_error:
        return "infra", f"grader: {grade.infra_error}"
    if grade.passed:
        return "pass", "hidden and visible tests pass"
    if timed_out:
        return "timeout", "agent hit the wall-clock limit"
    if grade.tampered:
        return "fail", f"changed protected tests: {grade.tampered}"
    return "fail", "tests fail"


def _launch(cfg, task, model, ollama, ws, home, out, log, stop_after_calls: str | None = None) -> tuple[int | None, bool, float]:
    """Start the proxy and the agent in the workspace; returns (exit code, timed out, wall seconds)."""
    server = proxy.serve(0, ollama, log)
    values = {
        "proxy": f"http://127.0.0.1:{server.server_address[1]}",
        "model": model,
        "workspace": str(ws),
        "home": str(home),
        "prompt": f"{task.prompt}\n\n{TEST_HINT}",
    }
    cmd = [_fill(part, values) for part in cfg.cmd]
    cmd[0] = shutil.which(cmd[0]) or cmd[0]
    env = {k: v for k, v in os.environ.items() if k not in cfg.unset_env}
    # `python` in the agent's shell must be the interpreter the grader uses (pytest + fastapi installed)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env |= {k: _fill(v, values) for k, v in cfg.env.items()}
    for key, raw in cfg.env.items():  # per-run config dirs must exist; Codex refuses a missing CODEX_HOME (E-010)
        if raw.startswith("{home}"):
            Path(env[key]).mkdir(parents=True, exist_ok=True)
    stop = None
    if stop_after_calls == "work":  # first answered call that carries tools (or any call, for text-edit agents)
        key = "first_tool_call_index" if cfg.sends_tools else "first_call_prompt_tokens"
        stop = lambda: summarize_calls(_calls(log))[key] is not None  # noqa: E731
    started = time.time()
    timed_out, exit_code = False, None
    with (out / "agent.out").open("w", encoding="utf-8") as so, (out / "agent.err").open("w", encoding="utf-8") as se:
        try:
            exit_code, timed_out = run_with_tree_kill(cmd, ws, env, so, se, cfg.timeout_s, stop)
        except OSError as exc:
            se.write(f"could not start agent: {exc}\n")
    server.shutdown()
    for name in ("agent.out", "agent.err"):  # results/ is public: no home-folder paths (user name)
        path = out / name
        home_dir = str(Path.home())
        text = path.read_text(encoding="utf-8", errors="replace")
        for form in (home_dir.replace("\\", "\\\\"), home_dir, home_dir.replace("\\", "/")):  # JSON-escaped too
            text = text.replace(form, "~")
        path.write_text(text, encoding="utf-8")
    return exit_code, timed_out, round(time.time() - started, 1)


def measure_overhead(cfg: AgentConfig, model: str, ollama: str, facts: dict, out_root: Path = OVERHEAD) -> dict:
    """Run the agent on T01 until its first answered model call; record what that call cost."""
    out = out_root / cfg.name / model.replace(":", "_").replace("/", "_")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (task,) = bench.load_tasks("T01")
    with tempfile.TemporaryDirectory(prefix="mitra-overhead-", ignore_cleanup_errors=True) as tmp:
        ws, home = Path(tmp) / "work", Path(tmp) / "home"
        home.mkdir()
        bench.prepare(task, ws)
        _init_repo(ws)
        log = out / "calls.jsonl"
        exit_code, timed_out, wall = _launch(cfg, task, model, ollama, ws, home, out, log, stop_after_calls="work")
    calls = summarize_calls(_calls(log))
    prefix = "first_tool_call" if cfg.sends_tools else "first_call"
    result = {
        "agent": cfg.name,
        "agent_version": facts.get("agent_version") or agent_version(cfg),
        "model": model,
        "ok": calls[f"{prefix}_prompt_tokens"] is not None,
        "prompt_tokens": calls[f"{prefix}_prompt_tokens"],
        "tools": calls[f"{prefix}_tools"],
        "tools_chars": calls[f"{prefix}_tools_chars"],
        "system_chars": calls[f"{prefix}_system_chars"],
        "calls_before": calls["first_tool_call_index"] or 0,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "wall_seconds": wall,
        "calls": calls,
        "facts": facts,
    }
    (out / "overhead.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_one(
    cfg: AgentConfig, task: bench.Task, model: str, rep: int, ollama: str, facts: dict, out_root: Path = RESULTS
) -> dict:
    out = out_root / cfg.name / model.replace(":", "_").replace("/", "_") / task.id / f"r{rep}"
    version = facts.setdefault("agent_version", agent_version(cfg))
    fp = fingerprint(cfg, version, task, model, facts.get("model_digest"))
    marker = out / ".complete"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == fp:
        return json.loads((out / "result.json").read_text(encoding="utf-8")) | {"cached": True}
    if out.exists():
        shutil.rmtree(out)  # incomplete or stale: redo, never adopt
    out.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix=f"mitra-{task.id}-", ignore_cleanup_errors=True) as tmp:
        ws = Path(tmp) / "work"
        home = Path(tmp) / "home"  # clean per-run config dir for agents that support one
        home.mkdir()
        bench.prepare(task, ws)
        start_sha = _init_repo(ws)
        log = out / "calls.jsonl"
        exit_code, timed_out, wall = _launch(cfg, task, model, ollama, ws, home, out, log)
        _git(ws, "add", "-A")  # include files the agent created, not only edits
        (out / "diff.patch").write_text(_git(ws, "diff", "--cached", start_sha), encoding="utf-8")
        grade = bench.grade(task, ws)

    calls = summarize_calls(_calls(log))
    outcome, reason = classify(exit_code, timed_out, calls, grade)
    result = {
        "agent": cfg.name,
        "agent_version": version,
        "model": model,
        "task": task.id,
        "split": task.split,
        "rep": rep,
        "outcome": outcome,
        "reason": reason,
        "exit_code": exit_code,
        "wall_seconds": wall,
        "calls": calls,
        "grade": grade.to_dict(),
        "facts": facts,
        "fingerprint": fp,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    marker.write_text(fp, encoding="utf-8")  # last: marks the run complete
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--task")
    parser.add_argument("--split", choices=["tune", "heldout"])
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--ollama", default=preflight.BENCH_OLLAMA)
    parser.add_argument("--min-free-ram-gb", type=float)
    parser.add_argument("--overhead", action="store_true", help="stop after the first model call; record its cost")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    facts, problems = preflight.check(args.ollama, args.model, args.min_free_ram_gb)
    if problems:
        for problem in problems:
            print(f"BLOCKED: {problem}")
        return 2
    cfg = AgentConfig.load(args.agent)
    if args.overhead:
        r = measure_overhead(cfg, args.model, args.ollama, dict(facts))
        c = r["calls"]
        print(
            f"{cfg.name:<16} {args.model:<16} ok={r['ok']} prompt_tokens={r['prompt_tokens']} tools={r['tools']} "
            f"tools_chars={r['tools_chars']} system_chars={r['system_chars']} calls_before={r['calls_before']} "
            f"(first call {c['first_call_prompt_tokens']} tokens) {r['wall_seconds']}s"
        )
        return 0 if r["ok"] else 1
    tasks = [t for t in bench.load_tasks(args.task) if not args.split or t.split == args.split]
    for task in tasks:
        for rep in range(1, args.reps + 1):
            r = run_one(cfg, task, args.model, rep, args.ollama, dict(facts))
            cached = " (cached)" if r.get("cached") else ""
            c = r["calls"]
            print(
                f"{task.id} r{rep} {r['outcome']:<7} {r['wall_seconds']:>6}s calls={c['model_calls']} "
                f"first_prompt={c['first_call_prompt_tokens']} tools={c['first_call_tools']}  {r['reason']}{cached}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
