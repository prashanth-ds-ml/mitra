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


def make_dir(ws: Workspace, path: str) -> str:
    """Create a folder (and its parents) inside the workspace. Without it the model tried `mkdir` in the shell,
    was refused, and told the user it could not create folders (2026-11-06 session)."""
    full = ws.path(path)
    ws.check_writable(full / "x")
    existed = full.is_dir()
    full.mkdir(parents=True, exist_ok=True)
    return f"{'Folder already exists' if existed else 'Created folder'}: {ws.rel(full)}"


def syntax_note(rel: str, text: str) -> str:
    """A warning when a written .py / .json / .toml file does not parse, so the model fixes it right away
    (2026-11-06: Mitra wrote level.toml as Markdown bullets)."""
    suffix = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
    try:
        if suffix == "py":
            compile(text, rel, "exec")
        elif suffix == "json":
            import json
            json.loads(text)
        elif suffix == "toml":
            import tomllib
            tomllib.loads(text)
        else:
            return ""
    except SyntaxError as exc:
        return f"\n⚠ {rel} is not valid Python: line {exc.lineno}: {exc.msg}. Fix it before going on."
    except ValueError as exc:  # json.JSONDecodeError and tomllib.TOMLDecodeError are ValueErrors
        kind = "JSON" if suffix == "json" else "TOML"
        return f"\n⚠ {rel} is not valid {kind}: {exc}. Fix it before going on."
    if suffix == "py":  # parses: now the errors that crash it at run time (A2 / E4)
        problems = flake(text, rel)
        if problems:
            shown = "; ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else "")
            return f"\n⚠ {rel} will likely fail when it runs: {shown}. Fix these before going on."
    return ""


# Errors that crash a program when it runs (E4: most brick-breaker crashes were these); unused imports etc. are noise.
_RUNTIME_ERRORS = ("UndefinedName", "UndefinedLocal", "UndefinedExport", "ReturnOutsideFunction",
                   "YieldOutsideFunction", "ContinueOutsideLoop", "BreakOutsideLoop", "DuplicateArgument")


def flake(text: str, rel: str) -> list[str]:
    """`line N: message` for errors pyflakes finds that would crash at run time; [] if clean or pyflakes is missing."""
    try:
        import ast

        from pyflakes import checker
    except ImportError:
        return []
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return [f"line {exc.lineno}: {exc.msg}"]
    w = checker.Checker(tree, filename=rel)
    out = []
    for m in sorted(w.messages, key=lambda m: m.lineno):
        if type(m).__name__ in _RUNTIME_ERRORS:
            out.append(f"line {m.lineno}: {m.message % m.message_args}")
    return out


def check_code(ws: Workspace, path: str = ".") -> str:
    """Quick check of Python files for errors that crash at run time (undefined names, variables used before
    assignment, syntax), before running the program (A2 / E4)."""
    base = ws.path(path)
    files = [base] if base.is_file() else [Path(d) / f for d, ds, fs in os.walk(base)
                                           if not any(s in Path(d).parts for s in SKIP_DIRS)
                                           for f in fs if f.endswith(".py")]
    files = sorted(files)[:300]
    found = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found += [f"{ws.rel(f)}: {p}" for p in flake(text, ws.rel(f))]
    if not files:
        return f"No Python files under '{path}'."
    if not found:
        return f"✓ No run-time errors found in {len(files)} Python file{'s' if len(files) != 1 else ''}."
    more = f"\n… {len(found) - 40} more" if len(found) > 40 else ""
    return f"Found {len(found)} likely run-time error(s):\n" + "\n".join(found[:40]) + more


def crash_hint(output: str) -> str:
    """When a program crashed with a traceback: where and why, and what to do next (E4)."""
    if "Traceback (most recent call last)" not in (output or ""):
        return ""
    locs = re.findall(r'File "([^"]+)", line (\d+)', output)
    last = next((ln.strip() for ln in reversed(output.strip().splitlines())
                 if re.match(r"^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt)\b", ln.strip())), "")
    where = ""
    for f, n in reversed(locs):  # the deepest frame in the project, not in a library
        if "site-packages" not in f and "lib\\python" not in f.lower() and "/lib/python" not in f:
            where = f"{os.path.basename(f)} line {n}"
            break
    return (f"\n\n⚠ It crashed ({where + ': ' if where else ''}{last or 'see the traceback'}). Fix this before running "
            "it again; check_code or run_tests would have caught it first.")


def append_file(ws: Workspace, path: str, content: str) -> str:
    """Add content to the end of a file written or read this turn: long files in parts (E3, E-044)."""
    full = ws.path(path)
    ws.check_writable(full)
    rel = ws.rel(full)
    if not full.is_file():
        raise ToolError(f"'{rel}' does not exist. Create it with write_file first, then append the rest.")
    if rel not in ws.seen:
        raise ToolError(f"Read '{rel}' (or write it) before appending to it.")
    if full.stat().st_mtime != ws.seen[rel]:
        raise ToolError(f"'{rel}' changed since you read it. Read it again, then append.")
    old = full.read_text(encoding="utf-8")
    sep = "" if (not old or old.endswith("\n")) else "\n"
    text = old + sep + str(content)
    _commit(ws, full, text)
    return f"Appended {len(str(content).splitlines())} lines to {rel} (now {len(text.splitlines())} lines)."


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
    return f"Wrote {rel} ({len(str(content).splitlines())} lines)." + syntax_note(rel, str(content))


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
    return f"Edited {rel}." + syntax_note(rel, text)


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


_PYTEST_CHECK: dict[str, bool] = {}


def _has_pytest(python: str) -> bool:
    if python not in _PYTEST_CHECK:
        try:
            p = subprocess.run([python, "-c", "import pytest"], capture_output=True, timeout=30)
            _PYTEST_CHECK[python] = p.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _PYTEST_CHECK[python] = False
    return _PYTEST_CHECK[python]


def project_python(root: Path) -> str:
    """The Python a test command's `python` should mean (E-028).

    Installed as a command, Mitra runs in its own private Python without the project's packages, so tests failed
    with "No module named pytest". Use, in order: the project's .venv / venv, then `python` on PATH if it has
    pytest, then Mitra's own Python (which ships pytest for small projects without a venv).
    """
    import shutil

    for venv in (".venv", "venv", "env"):
        for exe in ("Scripts/python.exe", "bin/python"):
            cand = Path(root) / venv / exe
            if cand.is_file():
                return str(cand)
    on_path = shutil.which("python") or shutil.which("python3")
    if on_path and "WindowsApps" not in on_path and _has_pytest(on_path):
        return on_path
    return sys.executable


_PYTEST_SUMMARY = re.compile(r"\b\d+ (passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b|no tests ran")


def test_summary(out: str) -> str:
    """pytest's result line ("2 failed, 30 passed in 1.2s"), not the last line (often a warning, E-047)."""
    for line in reversed((out or "").splitlines()):
        if _PYTEST_SUMMARY.search(line):
            return line.strip().strip("=").strip()
    lines = [ln for ln in (out or "").splitlines() if ln.strip()]
    return lines[-1].strip() if lines else ""


@dataclass
class TestRun:
    passed: bool
    summary: str       # last line, e.g. "3 failed, 9 passed in 0.4s"
    output: str        # what the model sees (head + tail)
    full_path: str = ""
    seconds: float = 0.0


def test_args(ws: Workspace, path: str = "", keyword: str = "", first_failure: bool = False) -> list[str]:
    """Extra pytest arguments for one file / a selection (A3); paths must stay inside the workspace."""
    extra = []
    if path:
        extra.append(ws.rel(ws.path(path)))
    if keyword:
        extra += ["-k", str(keyword)]
    if first_failure:
        extra += ["-x", "--tb=long"]
    return extra


def run_tests(ws: Workspace, command: str | None = None, extra: list[str] | None = None) -> TestRun:
    cmd = command or ws.test_command
    args = cmd.split()
    if extra:
        if "pytest" not in cmd:
            raise ToolError(f"The test command '{cmd}' is not pytest: run_tests cannot select a file or keyword.")
        args += extra
    if args and args[0] in ("python", "python3", "py"):
        args[0] = project_python(ws.root)
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
    last = test_summary(out) or ("passed" if ok else "failed")
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
    {"name": "make_dir", "description": "Create a folder (and parent folders) in the project.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Create a file, or replace a file you have read, with the full content.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace one exact block of lines `old` with `new` in a file you have read.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                                                     "new": {"type": "string"}}, "required": ["path", "old", "new"]}},
    {"name": "append_file", "description": "Add content to the end of a file you wrote or read. Write long files "
     "in parts: write_file with the first ~150 lines, then append_file for the rest.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}},
    {"name": "check_code", "description": "Find Python errors that crash at run time (undefined names, unbound "
     "variables). Use before running a program.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "run_tests", "description": "Run the tests (all, or one file / a keyword; first_failure stops at the "
     "first failure with the full traceback). Returns pass/fail and the output.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "keyword": {"type": "string"},
                                                     "first_failure": {"type": "boolean"}}}},
    {"name": "finish", "description": "Call when the tests pass, with a one-line summary of what you did.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]
