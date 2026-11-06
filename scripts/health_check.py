"""Restart and check everything Mitra depends on, step by step, so a break shows up in one place.

    python scripts/health_check.py               # full: restart Ollama, reinstall, tests, live run
    python scripts/health_check.py --no-restart  # same, without restarting Ollama (e.g. while it is busy)
    python scripts/health_check.py --quick       # skip the slow steps (unit tests, live run)

Each step prints ok / FAIL with a short reason; the whole report is saved to .mitra/health/<time>.json.
Exit code 0 only if every step passed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYGROUND = ROOT.parent / "mitra-playground"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not OLLAMA.startswith("http"):
    OLLAMA = "http://" + OLLAMA
REQUIRED_MODELS = ("qwen3.5:4b",)
PY = sys.executable


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, encoding="utf-8",
                           errors="replace", env=env)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except OSError as exc:
        return 127, str(exc)


def last_line(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-1][:160] if lines else ""


def get_json(path: str, timeout: float = 5):
    with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ── steps: each returns (ok, detail) ─────────────────────────────────────────

def step_restart_ollama():
    if sys.platform != "win32":
        return True, "skipped (restart is Windows-only; checked below)"
    for image in ("ollama app.exe", "ollama.exe"):
        run(["taskkill", "/IM", image, "/F"], timeout=30)
    time.sleep(2)
    app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe"
    if not app.exists():
        return False, f"Ollama app not found at {app}"
    subprocess.Popen([str(app)], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)
    for _ in range(60):
        try:
            get_json("/api/tags", timeout=2)
            return True, "restarted and answering"
        except Exception:
            time.sleep(1)
    return False, "Ollama did not answer within 60 s after restart"


def step_ollama_models():
    try:
        names = {m["name"] for m in get_json("/api/tags").get("models", [])}
    except Exception as exc:
        return False, f"Ollama not reachable at {OLLAMA}: {exc}"
    missing = [m for m in REQUIRED_MODELS if m not in names]
    if missing:
        return False, f"missing models: {', '.join(missing)} (ollama pull {missing[0]})"
    return True, f"{len(names)} models installed; {', '.join(REQUIRED_MODELS)} present"


def step_clear_caches():
    n = 0
    for base in ("app", "tests", "misc", "scripts", "bench"):
        for d in (ROOT / base).rglob("__pycache__") if (ROOT / base).exists() else []:
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    return True, f"removed {n} __pycache__ folders"


def mitra_sessions_open() -> int:
    """Running `mitra` processes. Reinstalling under them deletes their packages mid-session (E-029)."""
    if sys.platform != "win32":
        return 0
    code, out = run(["tasklist", "/FI", "IMAGENAME eq mitra.exe", "/NH"], timeout=30)
    return sum(1 for ln in out.splitlines() if ln.lower().startswith("mitra.exe"))


def step_reinstall():
    uv = shutil.which("uv")
    if not uv:
        return False, "uv not found on PATH"
    open_sessions = mitra_sessions_open()
    if open_sessions:
        return True, f"skipped: {open_sessions} mitra session(s) open; close them, then rerun to reinstall"
    code, out = run([uv, "tool", "install", "--editable", str(ROOT), "--python", "3.12", "--reinstall"], timeout=600)
    return code == 0, last_line(out) or "installed"


def step_lint():
    code, out = run([PY, "-m", "ruff", "check", "."], cwd=ROOT, timeout=120)
    return code == 0, last_line(out)


def step_unit_tests():
    code, out = run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT, timeout=1500)
    return code == 0, last_line(out)


def step_cli_anywhere():
    exe = shutil.which("mitra")
    if not exe:
        return False, "`mitra` not on PATH (uv tool install --editable . --python 3.12)"
    with tempfile.TemporaryDirectory() as tmp:
        code, out = run([exe, "--version"], cwd=Path(tmp), timeout=60)
        if code != 0:
            return False, f"mitra --version failed: {last_line(out)}"
        version = last_line(out)
        code, out = run([exe, "models"], cwd=Path(tmp), timeout=120)
        if code != 0 or "qwen3.5" not in out:
            return False, f"mitra models failed: {last_line(out)}"
    return True, f"{version}; `mitra models` lists qwen3.5 (run from a temp folder)"


def step_mcp_config():
    exe = shutil.which("mitra") or ""
    code, out = run([exe, "mcp", "list"], cwd=ROOT, timeout=120) if exe else (1, "mitra not on PATH")
    if code != 0:
        return False, last_line(out)
    import re
    on = sum(1 for ln in out.splitlines() if re.match(r"^\s*\S+\s+on\s+(default|user|project)\b", ln) or "| on |" in ln)
    if on == 0:
        return False, "no MCP servers configured on"
    return True, f"{on} servers configured on (not started: first start needs your OK)"


def step_live_solve():
    exe = shutil.which("mitra")
    if not exe:
        return False, "`mitra` not on PATH"
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "tests").mkdir()
        (ws / "tests" / "test_fizz.py").write_text(
            "from fizz import fizzbuzz\n\n\ndef test_fizzbuzz():\n"
            "    assert [fizzbuzz(n) for n in (1, 3, 5, 15)] == ['1', 'Fizz', 'Buzz', 'FizzBuzz']\n",
            encoding="utf-8")
        t0 = time.monotonic()
        code, out = run([exe, "solve", "Create fizz.py so the tests pass.", "--test", "python -m pytest -q tests",
                         "-w", str(ws), "--json", "--max-steps", "15"], cwd=ws, timeout=900)
        secs = time.monotonic() - t0
        try:
            res = json.loads(out[out.index("{"):])
        except ValueError:
            return False, f"no JSON result (exit {code}): {last_line(out)}"
        ok = res.get("status") == "passed"
        return ok, f"{res.get('status')} in {res.get('steps')} steps, {secs:.0f}s ({res.get('tests', '')})"


def step_playground():
    if not PLAYGROUND.exists():
        return True, "skipped (no ../mitra-playground)"
    code, out = run([PY, "scripts/check_level.py", "--all"], cwd=PLAYGROUND, timeout=600)
    return code == 0, last_line(out)


STEPS = [
    ("Restart Ollama", step_restart_ollama, "restart"),
    ("Ollama models", step_ollama_models, ""),
    ("Clear Python caches", step_clear_caches, ""),
    ("Reinstall `mitra` command", step_reinstall, ""),
    ("Lint", step_lint, ""),
    ("Unit tests", step_unit_tests, "slow"),
    ("`mitra` from any folder", step_cli_anywhere, ""),
    ("MCP config", step_mcp_config, ""),
    ("Live run (real model)", step_live_solve, "slow"),
    ("Playground levels", step_playground, ""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-restart", action="store_true", help="do not restart Ollama")
    ap.add_argument("--quick", action="store_true", help="skip unit tests and the live run")
    args = ap.parse_args()
    report, failed = [], 0
    for name, fn, tag in STEPS:
        if (tag == "restart" and args.no_restart) or (tag == "slow" and args.quick):
            print(f"  --    {name}: skipped")
            report.append({"step": name, "ok": None, "detail": "skipped"})
            continue
        t0 = time.monotonic()
        try:
            ok, detail = fn()
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        secs = time.monotonic() - t0
        failed += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}: {detail}  ({secs:.0f}s)", flush=True)
        report.append({"step": name, "ok": ok, "detail": detail, "seconds": round(secs, 1)})
    out_dir = ROOT / ".mitra" / "health"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / time.strftime("%Y%m%d-%H%M%S.json")
    out.write_text(json.dumps({"failed": failed, "steps": report}, indent=2), encoding="utf-8")
    print(f"\n{'all steps passed' if not failed else f'{failed} step(s) failed'} · report: {out}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
