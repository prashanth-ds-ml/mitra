"""Follow live CodeMitra chat sessions: one line per turn, plus every problem as it happens.

    python scripts/watch_sessions.py [root ...]     # default root: the parent of the parent of this repo

Watches every `.codemitra/runs/chat-*.jsonl` and `.codemitra/errors.log` under the roots (new files are picked up), from
their current end. Prints only lines worth acting on:
  TURN  one summary per turn (steps, seconds, tokens, files changed, stopped?)
  FAIL  a tool call failed          STOP  a turn was stopped (limit, repeats, esc)
  TEXT  a tool call written as text  SLOW  a model step took more than 90 s
  ERR   a new entry in errors.log
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "worktrees", "site-packages", ".pytest_cache"}
ROOTS = [Path(a) for a in sys.argv[1:]] or [Path(__file__).resolve().parents[3]]


def find_logs() -> list[Path]:
    found = []
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP]
            if len(Path(dirpath).relative_to(root).parts) > 6:
                dirnames[:] = []
                continue
            p = Path(dirpath)
            if p.name == "runs" and p.parent.name == ".codemitra":
                found += [p / f for f in filenames if f.startswith("chat-") and f.endswith(".jsonl")]
            if p.name == ".codemitra" and "errors.log" in filenames:
                found.append(p / "errors.log")
    return found


def short(text, n=110):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def project_of(path: Path) -> str:
    return path.parents[2].name if path.parent.name == "runs" else path.parents[1].name


def emit(line: str) -> None:
    print(time.strftime("%H:%M:%S ") + line, flush=True)


def handle(path: Path, raw: str, last_model_t: dict) -> None:
    proj = project_of(path)
    if path.name == "errors.log":
        if raw.strip() and not raw.startswith("="):
            emit(f"ERR  [{proj}] {short(raw)}")
        return
    try:
        r = json.loads(raw)
    except json.JSONDecodeError:
        return
    kind = r.get("kind")
    if kind == "turn_start":
        last_model_t[path] = r.get("t", time.time())
        emit(f"USER [{proj}] turn {r.get('turn')} ({r.get('mode')}): {short(r.get('user', ''), 90)}")
    elif kind == "model":
        t = r.get("t", time.time())
        gap = t - last_model_t.get(path, t)
        last_model_t[path] = t
        if gap > 90:
            emit(f"SLOW [{proj}] step {r.get('step')} took {gap:.0f}s")
    elif kind == "tool" and not r.get("ok"):
        out = str(r.get("output", ""))
        tag = "RPT " if out.startswith("✗ Not run:") else "FAIL"
        emit(f"{tag} [{proj}] {r.get('name')} {short(json.dumps(r.get('args', {})), 60)} -> {short(out, 120)}")
    elif kind == "text_tool_calls":
        emit(f"TEXT [{proj}] call written as text" + (f": {short(r.get('error'))}" if r.get("error") else " (recovered)"))
    elif kind == "stopped":
        emit(f"STOP [{proj}] {short(r.get('reason'))}")
    elif kind == "turn_end":
        changed = ", ".join(Path(c).name for c in r.get("changed") or []) or "-"
        flag = f" · STOPPED: {short(r.get('reason'), 60)}" if r.get("stopped") else ""
        empty = " · EMPTY ANSWER" if not (r.get("text") or "").strip() else ""
        emit(f"TURN [{proj}] {r.get('turn')}: {r.get('steps')} steps, {r.get('seconds')}s, "
             f"ctx {int(r.get('ctx_used') or 0):,} tok, changed: {changed}{flag}{empty}")


def main() -> None:
    offsets: dict[Path, int] = {}
    last_model_t: dict[Path, float] = {}
    for p in find_logs():
        offsets[p] = p.stat().st_size  # start at the end: only new activity
    emit(f"watching {len(offsets)} log(s) under {', '.join(str(r) for r in ROOTS)}")
    last_scan = time.monotonic()
    while True:
        if time.monotonic() - last_scan > 15:
            for p in find_logs():
                if p not in offsets:
                    offsets[p] = 0
                    emit(f"NEW  session log: {p}")
            last_scan = time.monotonic()
        for p in list(offsets):
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size < offsets[p]:
                offsets[p] = 0
            if size == offsets[p]:
                continue
            with p.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(offsets[p])
                data = f.read()
                offsets[p] = f.tell()
            for raw in data.splitlines():
                try:
                    handle(p, raw, last_model_t)
                except Exception as exc:  # one odd line must not stop the watch
                    emit(f"WARN watcher could not read a line in {p.name}: {exc}")
        time.sleep(2)


if __name__ == "__main__":
    main()
