"""The core loop's tools (M1): small, workspace-confined, built for small models.

    list_files · read_file · search · write_file · edit_file · run_tests · finish

Rules the tools enforce (not the prompt):
- every path stays inside the workspace (fail closed, E-003);
- a file must be read before it is edited, and it must not have changed since (dsh fs-observation-policy);
- `tests/` is read-only: the builder makes tests pass, it never edits them;
- edit_file matches exactly first, then ignoring indentation and trailing spaces (forgiving match);
- test output is trimmed to head + tail for the model; the full output is saved to a file (spill policy).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mitra", ".mypy_cache",
             ".ruff_cache", "dist", "build"}
MAX_READ_LINES = 400
MAX_OUTPUT_CHARS = 4000
TEST_TIMEOUT_S = 120


class ToolError(Exception):
    """A mistake the model can fix; the message is sent back as the tool result."""


@dataclass
class Workspace:
    root: Path
    test_command: str = "python -m pytest -q"
    read_only: tuple[str, ...] = ("tests",)
    seen: dict[str, float] = field(default_factory=dict)  # path -> mtime when last read or written
    spill_dir: Path | None = None
    changed: set[str] = field(default_factory=set)
    # before_write(rel, old_text_or_None, new_text): raise ToolError to refuse (the chat's ask mode uses it)
    before_write: object = None
    journal: list | None = None  # undo entries in the /undo format, when the caller wants them

    def __post_init__(self):
        self.root = Path(self.root).resolve()

    # ── paths ────────────────────────────────────────────────────────────
    def path(self, rel: str) -> Path:
        rel = (rel or ".").strip().strip("\"'")
        p = Path(rel)
        if p.is_absolute():
            raise ToolError(f"Use a path relative to the workspace, not '{rel}'.")
        parts = p.parts
        if len(parts) > 1 and parts[0].lower() == self.root.name.lower() and not (self.root / parts[0]).exists():
            p = Path(*parts[1:])  # E-019: model repeated the workspace folder name
        full = (self.root / p).resolve()
        try:
            full.relative_to(self.root)
        except ValueError:
            raise ToolError(f"'{rel}' is outside the workspace.") from None
        return full

    def rel(self, full: Path) -> str:
        return full.relative_to(self.root).as_posix() or "."

    def check_writable(self, full: Path) -> None:
        rel = self.rel(full)
        for ro in self.read_only:
            if rel == ro or rel.startswith(ro + "/"):
                raise ToolError(f"'{rel}' is a test file; tests are read-only. Change the code so the tests pass.")
        name = full.name.lower()
        if name.startswith(".env") or name.endswith((".pem", ".key")):
            raise ToolError(f"'{rel}' looks like a secret file; Mitra does not write those.")


def _commit(ws: Workspace, full: Path, new_text: str) -> None:
    """Write a file after the approval hook, recording an undo entry."""
    rel = ws.rel(full)
    old = full.read_text(encoding="utf-8", errors="replace") if full.exists() else None
    if callable(ws.before_write):
        ws.before_write(rel, old, new_text)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(new_text, encoding="utf-8")
    if ws.journal is not None:
        ws.journal.append({"kind": "create_file", "path": str(full), "existed": old is not None,
                           "before": old, "after": new_text})
    ws.seen[rel] = full.stat().st_mtime
    ws.changed.add(rel)


# ── tools ────────────────────────────────────────────────────────────────────

def list_files(ws: Workspace, path: str = ".") -> str:
    base = ws.path(path)
    if not base.exists():
        raise ToolError(f"'{path}' does not exist.")
    if base.is_file():
        return ws.rel(base)
    lines: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        depth = len(Path(dirpath).relative_to(base).parts)
        if depth > 4:
            dirnames[:] = []
            continue
        for name in sorted(filenames):
            lines.append(ws.rel(Path(dirpath) / name))
        if len(lines) > 300:
            lines.append("… (more files not shown)")
            break
    return "\n".join(lines) if lines else "(empty)"


def read_file(ws: Workspace, path: str, start: int = 1, end: int = 0) -> str:
    full = ws.path(path)
    if not full.is_file():
        raise ToolError(f"'{path}' is not a file. Use list_files to see what exists.")
    text = full.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    ws.seen[ws.rel(full)] = full.stat().st_mtime
    start = max(1, int(start or 1))
    end = int(end or 0) or min(len(lines), start + MAX_READ_LINES - 1)
    shown = lines[start - 1:end]
    body = "\n".join(f"{i:4} | {line}" for i, line in enumerate(shown, start))
    more = f"\n… {len(lines) - end} more lines (read_file with start={end + 1})" if end < len(lines) else ""
    return f"{ws.rel(full)} ({len(lines)} lines)\n{body}{more}" if lines else f"{ws.rel(full)} (empty file)"


def search(ws: Workspace, pattern: str, path: str = ".") -> str:
    base = ws.path(path)
    try:
        rx = re.compile(pattern)
    except re.error:
        rx = re.compile(re.escape(pattern))
    hits: list[str] = []
    files = [base] if base.is_file() else [Path(d) / f for d, ds, fs in os.walk(base)
                                           for f in fs if not any(s in Path(d).parts for s in SKIP_DIRS)]
    for f in sorted(files):
        try:
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{ws.rel(f)}:{n}: {line.strip()[:160]}")
                    if len(hits) >= 60:
                        return "\n".join(hits) + "\n… (more matches not shown)"
        except OSError:
            continue
    return "\n".join(hits) if hits else f"No matches for '{pattern}'."


def write_file(ws: Workspace, path: str, content: str) -> str:
    full = ws.path(path)
    ws.check_writable(full)
    rel = ws.rel(full)
    if full.exists() and rel not in ws.seen:
        raise ToolError(f"'{rel}' already exists. Read it first, then use edit_file (or write_file to replace it).")
    if isinstance(content, (dict, list)):
        import json
        content = json.dumps(content, indent=2) + "\n"
    _commit(ws, full, str(content))
    return f"Wrote {rel} ({len(str(content).splitlines())} lines)."


def _loose(s: str) -> str:
    return "\n".join(line.strip() for line in s.strip().splitlines())


def edit_file(ws: Workspace, path: str, old: str, new: str) -> str:
    full = ws.path(path)
    ws.check_writable(full)
    rel = ws.rel(full)
    if not full.is_file():
        raise ToolError(f"'{rel}' does not exist. Use write_file to create it.")
    if rel not in ws.seen:
        raise ToolError(f"Read '{rel}' with read_file before editing it.")
    if full.stat().st_mtime != ws.seen[rel]:
        raise ToolError(f"'{rel}' changed since you read it. Read it again, then edit.")
    text = full.read_text(encoding="utf-8")
    if old and text.count(old) == 1:
        text = text.replace(old, new, 1)
    elif old and text.count(old) > 1:
        raise ToolError(f"The old text appears {text.count(old)} times in '{rel}'. Include more lines to make it unique.")
    else:
        # forgiving match: compare lines ignoring indentation and trailing spaces
        lines = text.splitlines()
        want = _loose(old).splitlines()
        if not want:
            raise ToolError("old is empty. Give the exact lines to replace.")
        starts = [i for i in range(len(lines) - len(want) + 1)
                  if [line.strip() for line in lines[i:i + len(want)]] == want]
        if len(starts) != 1:
            raise ToolError(f"Could not find the old text in '{rel}'"
                            + (" exactly once" if starts else "") + ". Read the file again and copy the lines exactly.")
        i = starts[0]
        indent = re.match(r"\s*", lines[i]).group(0)
        first_new_indent = re.match(r"\s*", new.splitlines()[0]).group(0) if new.strip() else ""
        new_lines = [indent + line[len(first_new_indent):] if line.startswith(first_new_indent) else line
                     for line in new.splitlines()]
        lines[i:i + len(want)] = new_lines
        text = "\n".join(lines) + "\n"
    _commit(ws, full, text)
    return f"Edited {rel}."


def rollback(entries: list[dict]) -> int:
    """Undo journal entries (newest first): restore old content, delete files that did not exist. Returns count."""
    n = 0
    for e in reversed(entries):
        p = Path(e["path"])
        try:
            if e.get("existed"):
                p.write_text(e.get("before") or "", encoding="utf-8")
            elif p.exists():
                p.unlink()
            n += 1
        except OSError:
            continue
    return n


@dataclass
class TestRun:
    passed: bool
    summary: str       # last line, e.g. "3 failed, 9 passed in 0.4s"
    output: str        # what the model sees (head + tail)
    full_path: str = ""
    seconds: float = 0.0


def run_tests(ws: Workspace, command: str | None = None) -> TestRun:
    cmd = command or ws.test_command
    args = cmd.split()
    if args and args[0] == "python":
        args[0] = sys.executable
    t0 = time.monotonic()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(args, cwd=ws.root, capture_output=True, text=True, timeout=TEST_TIMEOUT_S,
                              encoding="utf-8", errors="replace", env=env)
        out, ok = (proc.stdout + proc.stderr).strip(), proc.returncode == 0
    except subprocess.TimeoutExpired:
        out, ok = f"Tests timed out after {TEST_TIMEOUT_S}s.", False
    except OSError as exc:
        out, ok = f"Could not run '{cmd}': {exc}", False
    secs = time.monotonic() - t0
    last = out.splitlines()[-1] if out else ("passed" if ok else "failed")
    full_path = ""
    if ws.spill_dir is not None:
        ws.spill_dir.mkdir(parents=True, exist_ok=True)
        f = ws.spill_dir / f"tests-{int(time.time() * 1000)}.txt"
        f.write_text(out, encoding="utf-8")
        full_path = str(f)
    shown = out
    if len(out) > MAX_OUTPUT_CHARS:
        head, tail = out[: MAX_OUTPUT_CHARS // 3], out[-(MAX_OUTPUT_CHARS * 2 // 3):]
        shown = f"{head}\n… {len(out) - len(head) - len(tail)} characters cut …\n{tail}"
    return TestRun(ok, last, shown, full_path, secs)


# ── tool specs for the model (kept short: the whole prompt stays under ~3K tokens) ──────────────────────────

TOOL_SPECS = [
    {"name": "list_files", "description": "List files in the workspace (or a folder).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "read_file", "description": "Read a text file with line numbers. Read a file before editing it.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"},
                                                     "end": {"type": "integer"}}, "required": ["path"]}},
    {"name": "search", "description": "Find a regex in files; returns file:line: text.",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
                    "required": ["pattern"]}},
    {"name": "write_file", "description": "Create a file, or replace a file you have read, with the full content.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace one exact block of lines `old` with `new` in a file you have read.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                                                     "new": {"type": "string"}}, "required": ["path", "old", "new"]}},
    {"name": "run_tests", "description": "Run the tests. Returns pass/fail and the output.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "finish", "description": "Call when the tests pass, with a one-line summary of what you did.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]
