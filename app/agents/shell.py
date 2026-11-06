"""Shell Agent — executes commands in the project workspace with live output streaming.

Design goals:
  - Streams stdout/stderr in real time so the user sees progress (tests, builds, servers)
  - Hard timeout with subprocess kill so a runaway process never hangs Mitra
  - Whitelisted executables (same _DEFAULT_COMMANDS as filesystem agent)
  - User sees a coloured "Shell Agent" panel with command, exit code, and truncated output
  - The main LLM gets the exit code + tail of output so it can react to failures
"""
from __future__ import annotations

import os
import inspect
import pathlib
import platform
import re
import shlex
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable

from rich.console import Console, Group
from rich.text import Text

from app.policy import Policy, Scope, Action, load_policy

# ─── Allowed executables ──────────────────────────────────────────────────────

_DEFAULT_COMMANDS: set[str] = {
    "python", "python3", "pip", "pip3",
    "git", "npm", "node", "npx",
    "uvicorn", "gunicorn",
    "pytest", "ruff", "mypy", "black", "isort",
    "make", "cargo", "go",
    # read-only directory listing (safe on all platforms)
    "dir", "ls", "tree",
}

# ─── Config ───────────────────────────────────────────────────────────────────

@dataclass
class ShellConfig:
    root_workspace: str | None = None
    allowed_roots: list[str] = field(default_factory=list)
    current_cwd: str | None = None
    session_mode: str = "approve"
    allowed_commands: set[str] = field(default_factory=lambda: set(_DEFAULT_COMMANDS))
    default_timeout: int = 60          # seconds
    max_output_lines: int = 200        # lines kept in memory
    stream_to_console: bool = True     # print output live
    confirm_fn: Callable[..., str | None] | None = None  # (command, cwd) -> amended_command | None
    policy: Policy | None = None
    policy_path: str | None = None

_config = ShellConfig()
_background_tasks: dict[str, "BackgroundTask"] = {}
_background_lock = threading.Lock()


def configure(
    workspace: str | None = None,
    allowed_roots: list[str] | None = None,
    session_mode: str = "approve",
    allowed_commands: set[str] | None = None,
    default_timeout: int = 60,
    max_output_lines: int = 200,
    stream_to_console: bool = True,
    confirm_fn: Callable[..., bool] | None = None,
    policy: Policy | None = None,
    policy_path: str | None = None,
) -> None:
    """Update the shell agent config for this session."""
    global _config
    resolved_workspace = pathlib.Path(workspace).resolve().__str__() if workspace else None
    _config = ShellConfig(
        root_workspace=resolved_workspace,
        allowed_roots=[str(pathlib.Path(root).resolve()) for root in (allowed_roots or [])],
        current_cwd=resolved_workspace,
        session_mode=session_mode,
        allowed_commands=allowed_commands if allowed_commands is not None else set(_DEFAULT_COMMANDS),
        default_timeout=default_timeout,
        max_output_lines=max_output_lines,
        stream_to_console=stream_to_console,
        confirm_fn=confirm_fn,
        policy=policy or load_policy(policy_path),
        policy_path=policy_path,
    )


# ─── Result ───────────────────────────────────────────────────────────────────

LIVE_OUTPUT_LINES = 10


@dataclass
class ShellResult:
    command: str
    cwd: str
    exit_code: int
    output_lines: list[str]          # combined stdout+stderr, chronological
    timed_out: bool = False
    denied: bool = False             # user declined
    hidden_lines: int = 0            # output lines not shown live (folded; ctrl+o shows them)
    timeout_s: float = 0             # the limit it ran under

    @property
    def still_running(self) -> bool:
        """Stopped at the timeout with no error in its output: a game, window or server that runs until closed."""
        if not self.timed_out:
            return False
        tail = self.tail.lower()
        return not any(w in tail for w in ("traceback", "error", "exception", "failed"))

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.denied

    @property
    def output(self) -> str:
        return "\n".join(self.output_lines)

    @property
    def tail(self) -> str:
        """Last 30 lines — what the LLM receives."""
        return "\n".join(self.output_lines[-30:])

    def to_llm_summary(self) -> str:
        if self.still_running:
            return (f"Command: {self.command}\nCWD: {self.cwd}\n[STILL RUNNING] The program ran for "
                    f"{self.timeout_s:.0f}s without an error and was stopped at the time limit. A game, window or "
                    "server keeps running until it is closed: this is not a crash. Do not run it again to test it; "
                    "tell the user the command to run it themselves.\n\n"
                    f"Output (last 30 lines):\n{self.tail or '(no output)'}")
        status = "OK" if self.ok else ("TIMEOUT" if self.timed_out else ("DENIED" if self.denied else "FAILED"))
        return (
            f"Command: {self.command}\n"
            f"CWD: {self.cwd}\n"
            f"Exit code: {self.exit_code}  [{status}]\n\n"
            f"Output (last 30 lines):\n{self.tail or '(no output)'}"
        )


@dataclass
class BackgroundTask:
    id: str
    command: str
    cwd: str
    status: str
    started_at: str
    completed_at: str | None = None
    exit_code: int | None = None
    output_lines: list[str] = field(default_factory=list)
    note: str = ""
    proc: subprocess.Popen | None = field(default=None, repr=False)
    watcher_thread: threading.Thread | None = field(default=None, repr=False)

    @property
    def tail(self) -> str:
        return "\n".join(self.output_lines[-30:])




def _task_snapshot(task: BackgroundTask) -> BackgroundTask:
    return BackgroundTask(
        id=task.id,
        command=task.command,
        cwd=task.cwd,
        status=task.status,
        started_at=task.started_at,
        completed_at=task.completed_at,
        exit_code=task.exit_code,
        output_lines=list(task.output_lines),
        note=task.note,
    )




# ─── Core runner ─────────────────────────────────────────────────────────────

def _resolve_cwd(cwd: str | None) -> str:
    """Resolve cwd: prefer current shell cwd, then explicit path, then os.getcwd()."""
    base = _config.current_cwd or _config.root_workspace or os.getcwd()
    if cwd and cwd not in (".", ""):
        p = pathlib.Path(cwd)
        if not p.is_absolute():
            p = pathlib.Path(base) / p
        return str(p.resolve())
    return str(pathlib.Path(base).resolve())


def get_cwd() -> str:
    """Return the current shell working directory for this session."""
    return _resolve_cwd(None)




def _check_path_in_workspace(path: pathlib.Path) -> str | None:
    roots = ([pathlib.Path(_config.root_workspace)] if _config.root_workspace else []) + [
        pathlib.Path(root) for root in _config.allowed_roots
    ]
    if not roots:
        # E-003: fail closed. Without a workspace there is nothing to keep commands inside.
        return "no workspace is set, so Mitra does not run commands"
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return None
        except ValueError:
            continue
    return f"Path is outside the workspace: {path}"


def _resolve_target_path(raw_path: str | None, cwd: str) -> pathlib.Path:
    if not raw_path or raw_path in (".", ""):
        return pathlib.Path(cwd)
    target = pathlib.Path(raw_path)
    if not target.is_absolute():
        target = pathlib.Path(cwd) / target
    return target.resolve()


def _split_command(command: str) -> list[str]:
    """Split a command line into arguments.

    On Windows shlex runs with posix=False (so backslashes in paths survive), which keeps the quote marks around
    quoted arguments: `python -c "print(42)"` passed the literal `"print(42)"` and printed nothing, and a quoted
    program path did not match the allow-list (E-021). Strip one pair of matching outer quotes from each argument.
    """
    if platform.system() != "Windows":
        return shlex.split(command, posix=True)
    parts = shlex.split(command, posix=False)
    return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]


_INTERPRETERS = {"python", "python3", "py", "node", "deno", "bun", "ruby", "perl", "php",
                 "powershell", "pwsh", "bash", "sh", "zsh", "cmd"}
_INLINE_CODE_FLAGS = {"-c", "-e", "--eval", "-p", "--print", "-command", "-encodedcommand", "/c", "/k", "-r"}


def runs_inline_code(command: str) -> bool:
    """`python -c "..."`, `node -e ...`, `powershell -Command ...`: the allow-list sees only the program name, so code
    passed inline could do anything (E-003)."""
    try:
        parts = _split_command(command)
    except ValueError:
        parts = command.split()
    if not parts:
        return False
    exe = re.sub(r"\.exe$", "", pathlib.Path(parts[0]).name, flags=re.IGNORECASE).lower()
    return exe in _INTERPRETERS and any(arg.lower() in _INLINE_CODE_FLAGS for arg in parts[1:])


def unix_to_windows_path(arg: str) -> str:
    """`/c/Users/x` (Git Bash style, which models often write) -> `C:/Users/x` on Windows."""
    if platform.system() == "Windows" and re.match(r"^/[a-zA-Z](/|$)", arg):
        return arg[1].upper() + ":" + (arg[2:] or "/")
    return arg


def _mask_quotes(command: str) -> str:
    """The command with everything inside quotes replaced by spaces (same length), so operators are only found
    where a shell would see them: `python -c "a; b"` has no `;` outside quotes (E-040)."""
    out, quote = [], None
    for ch in command:
        if quote:
            out.append(" " if ch != quote else ch)
            if ch == quote:
                quote = None
        else:
            if ch in "\"'":
                quote = ch
            out.append(ch)
    return "".join(out)


def has_pipe_or_redirect(command: str) -> bool:
    return any(tok in _mask_quotes(command) for tok in ("|", ">", "<"))


def split_chain(command: str) -> list[str] | None:
    """`cd X && pytest -q` -> ["cd X", "pytest -q"]; None for a single plain command.

    Model commands run without a shell, so `&&` and `cd` used to fail every time; the model retried the same chain
    30+ times (E-033). Chains of `&&` / `;` are run one part at a time; pipes and redirects are refused."""
    masked = _mask_quotes(command)
    if not any(tok in masked for tok in ("&&", ";")):
        return None  # a lone `cd X` stays the built-in that moves the session's folder
    parts, start = [], 0
    for m in re.finditer(r"&&|;", masked):  # positions in the masked text are positions in the command
        parts.append(command[start:m.start()].strip())
        start = m.end()
    parts.append(command[start:].strip())
    parts = [p for p in parts if p]
    return parts if len(parts) > 1 else None


def _run_chain(parts: list[str], cwd: str, timeout, console) -> ShellResult:
    """Run `cd` parts by changing the folder (inside the workspace only) and the rest one by one; stop at a failure."""
    here = pathlib.Path(cwd)
    lines: list[str] = []
    last = ShellResult(command=" && ".join(parts), cwd=str(here), exit_code=0, output_lines=[])
    for part in parts:
        if re.match(r"^cd(\s|$)", part, flags=re.IGNORECASE):
            target = unix_to_windows_path(part[2:].strip().strip("\"'") or ".")
            new = (here / target).resolve() if not pathlib.Path(target).is_absolute() else pathlib.Path(target).resolve()
            if err := _check_path_in_workspace(new):
                return ShellResult(command=part, cwd=str(here), exit_code=1, output_lines=lines + [f"✗ {err}"])
            if not new.is_dir():
                return ShellResult(command=part, cwd=str(here), exit_code=1,
                                   output_lines=lines + [f"✗ No folder {target} (from {here})"])
            here = new
            continue
        last = execute(part, cwd=str(here), timeout=timeout, console=console)
        lines += last.output_lines
        if not last.ok:
            break
    return ShellResult(command=" && ".join(parts), cwd=str(here), exit_code=last.exit_code,
                       output_lines=lines, timed_out=last.timed_out, denied=last.denied,
                       hidden_lines=getattr(last, "hidden_lines", 0))


def _model_command_args(command: str, cwd: str) -> list[str]:
    """Split a model's command; `python` means the project's Python (E-028).

    On Windows a child process looks for `python` next to the parent's exe first, so inside the installed `mitra`
    command a bare `python` found Mitra's private Python ("No module named pytest", 2026-11-06 session).
    """
    args = _split_command(command)
    if args and args[0].lower() in ("python", "python3", "py", "python.exe"):
        from app.core.tools import project_python

        root = _config.root_workspace or cwd
        args[0] = project_python(pathlib.Path(root))
    return args


def _confirm_command(command: str, cwd: str) -> str | None:
    """Call confirm_fn and return the (possibly amended) command, or None if denied."""
    if _config.confirm_fn is None:
        return command
    params = list(inspect.signature(_config.confirm_fn).parameters.values())
    positional = [
        param for param in params
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params) or len(positional) >= 2:
        return _config.confirm_fn(command, cwd)
    return _config.confirm_fn(command)








def list_background_tasks() -> list[BackgroundTask]:
    """Return tracked background tasks in creation order."""
    with _background_lock:
        tasks = list(_background_tasks.values())
    tasks.sort(key=lambda task: int(task.id.split("-")[-1]))
    return [_task_snapshot(task) for task in tasks]




def count_background_tasks(*, only_running: bool = False) -> int:
    """Count tracked background tasks."""
    with _background_lock:
        tasks = list(_background_tasks.values())
    if only_running:
        tasks = [task for task in tasks if task.status == "running"]
    return len(tasks)




def _check_executable(command: str) -> str | None:
    """Return error string if the executable is not allowed by policy, else None."""
    try:
        parts = _split_command(command)
    except ValueError:
        return "Could not parse command"
    if not parts:
        return "Empty command"
    exe = pathlib.Path(parts[0]).name
    # Strip .exe on Windows
    exe = re.sub(r"\.exe$", "", exe, flags=re.IGNORECASE)

    # Check policy first
    if _config.policy:
        action = _config.policy.evaluate(Scope.COMMAND, exe)
        if action == Action.DENY:
            return f"command '{exe}' denied by policy"
        if action == Action.ASK and _config.confirm_fn is None:
            return f"command '{exe}' requires approval but no confirm_fn available"

    # Fallback to legacy allowlist for backward compatibility
    if exe not in _config.allowed_commands:
        return (
            f"'{exe}' is not in the allowed commands list. "
            f"Allowed: {sorted(_config.allowed_commands)}"
        )
    return None


def _render_dir_listing(cwd: str) -> list[str]:
    root = pathlib.Path(cwd)
    entries = sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    if not entries:
        return [f"{root.name or root} (empty)"]
    lines = [str(root)]
    for entry in entries:
        prefix = "[dir] " if entry.is_dir() else "[file]"
        lines.append(f"{prefix} {entry.name}")
    return lines


def _render_tree(cwd: str, max_depth: int = 4) -> list[str]:
    root = pathlib.Path(cwd)
    lines: list[str] = [root.name or str(root)]

    def walk(path: pathlib.Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        for index, entry in enumerate(entries):
            connector = "└── " if index == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                walk(entry, prefix + ("    " if index == len(entries) - 1 else "│   "), depth + 1)

    walk(root, "", 1)
    return lines


def _read_text_file(path: pathlib.Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines() or [""]
    except UnicodeDecodeError:
        return [f"✗ Cannot display binary file: {path.name}"]


def _run_builtin(command: str, cwd: str) -> ShellResult | None:
    try:
        parts = _split_command(command)
    except ValueError:
        return None
    if not parts:
        return None

    exe = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    if exe == "cd":
        target = _resolve_target_path(arg, cwd)
        if err := _check_path_in_workspace(target):
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ {err}"])
        if not target.exists():
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ Directory not found: {arg or target}"])
        if not target.is_dir():
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ Not a directory: {arg or target}"])
        _config.current_cwd = str(target)
        return ShellResult(command=command, cwd=str(target), exit_code=0, output_lines=[str(target)])
    if exe == "pwd":
        return ShellResult(command=command, cwd=cwd, exit_code=0, output_lines=[cwd])
    if exe in {"ls", "dir", "ll"}:
        target = _resolve_target_path(arg, cwd)
        if err := _check_path_in_workspace(target):
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ {err}"])
        if not target.exists():
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ Path not found: {arg or target}"])
        if target.is_file():
            return ShellResult(command=command, cwd=str(target.parent), exit_code=0, output_lines=[str(target)])
        return ShellResult(command=command, cwd=str(target), exit_code=0, output_lines=_render_dir_listing(str(target)))
    if exe == "tree":
        target = _resolve_target_path(arg, cwd)
        if err := _check_path_in_workspace(target):
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ {err}"])
        if not target.exists():
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ Path not found: {arg or target}"])
        if target.is_file():
            return ShellResult(command=command, cwd=str(target.parent), exit_code=0, output_lines=[str(target)])
        return ShellResult(command=command, cwd=str(target), exit_code=0, output_lines=_render_tree(str(target)))
    if exe in {"cat", "type"}:
        target = _resolve_target_path(arg, cwd)
        if err := _check_path_in_workspace(target):
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ {err}"])
        if not target.exists():
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ File not found: {arg or target}"])
        if not target.is_file():
            return ShellResult(command=command, cwd=cwd, exit_code=1, output_lines=[f"✗ Not a file: {arg or target}"])
        return ShellResult(command=command, cwd=str(target.parent), exit_code=0, output_lines=_read_text_file(target))
    return None


def _user_shell_args(command: str) -> list[str]:
    """A command the user typed runs in their shell, so built-ins like `mkdir`, `dir` and pipes work."""
    if platform.system() == "Windows":
        exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [exe, "-NoLogo", "-NoProfile", "-Command", command]
    return [os.environ.get("SHELL") or "/bin/sh", "-c", command]


def execute(
    command: str,
    cwd: str | None = None,
    timeout: int | None = None,
    console: Console | None = None,
    *,
    typed_by_user: bool = False,
) -> ShellResult:
    """
    Run *command* in *cwd*, stream output, and return a ShellResult.

    - Output is streamed line-by-line to *console* if provided and stream_to_console is True.
    - Process is killed after *timeout* seconds (default: _config.default_timeout).
    - typed_by_user: the user typed it (`! <command>`), so it runs in their shell without the allow-list, the policy
      or a confirm step; it still runs only inside the workspace and under the timeout (E-014). Commands the model
      asks for always go through the allow-list, policy, mode and approval.
    """
    resolved_cwd = _resolve_cwd(cwd)
    timeout = timeout if timeout is not None else _config.default_timeout

    if not typed_by_user:
        if has_pipe_or_redirect(command):
            return ShellResult(command=command, cwd=resolved_cwd, exit_code=1, output_lines=[
                "✗ Pipes and redirects (| > <) are not supported for model commands. Run one command at a time."])
        chain = split_chain(command)
        if chain is not None:
            return _run_chain(chain, resolved_cwd, timeout, console)
        command = " ".join(unix_to_windows_path(a) if a.startswith("/") else a for a in command.split(" "))

    resolved_path = pathlib.Path(resolved_cwd)
    if err := _check_path_in_workspace(resolved_path):
        return ShellResult(command=command, cwd=resolved_cwd, exit_code=1, output_lines=[f"✗ {err}"])

    builtin_result = _run_builtin(command, resolved_cwd)
    if builtin_result is not None:
        return builtin_result

    if typed_by_user:
        pass  # the user is the author: no mode, policy or confirm checks
    elif _config.session_mode in {"read-only", "plan"}:
        return ShellResult(
            command=command,
            cwd=resolved_cwd,
            exit_code=1,
            output_lines=[
                f"✗ Shell execution is disabled in `{_config.session_mode}` mode. "
                "Use `/mode approve` or `/mode auto` to run commands."
            ],
        )

    # Permission check (model-run commands only)
    if not typed_by_user and (err := _check_executable(command)):
        return ShellResult(command=command, cwd=resolved_cwd, exit_code=1, output_lines=[f"✗ Permission denied: {err}"])

    # Inline code from the model is never run without the user seeing it (E-003), even in auto mode.
    if not typed_by_user and _config.confirm_fn is None and runs_inline_code(command):
        return ShellResult(command=command, cwd=resolved_cwd, exit_code=1, output_lines=[
            "✗ Permission denied: inline code (`-c` / `-e` / `-Command`) needs your approval. "
            "Write it to a file and run that, or switch to ask mode (shift+tab)."])

    # User confirmation — confirm_fn may return an amended command string or None (denied)
    if _config.confirm_fn is not None and not typed_by_user:
        approved_command = _confirm_command(command, resolved_cwd)
        if approved_command is None:
            return ShellResult(command=command, cwd=resolved_cwd, exit_code=1, output_lines=["Skipped: user declined"], denied=True)
        command = approved_command

    lines: list[str] = []
    proc: subprocess.Popen | None = None
    timed_out = False
    shown = {"live": 0, "hidden": 0}   # live output is capped at LIVE_OUTPUT_LINES (D-035)

    def _reader(stream, tag: str) -> None:
        """Read lines from a stream, print live, and append to lines list."""
        try:
            for raw in stream:
                line = raw.rstrip("\n")
                lines.append(line)
                if _config.stream_to_console and console is not None:
                    if shown["live"] < LIVE_OUTPUT_LINES:
                        console.print(Text("     " + line, style="m.dim"), soft_wrap=True)
                        shown["live"] += 1
                    else:
                        shown["hidden"] += 1
                if len(lines) > _config.max_output_lines * 2:
                    lines[:] = lines[-_config.max_output_lines:]
        except Exception:
            pass

    try:
        proc = subprocess.Popen(
            _user_shell_args(command) if typed_by_user else _model_command_args(command, resolved_cwd),
            cwd=resolved_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )
        t = threading.Thread(target=_reader, args=(proc.stdout, "out"), daemon=True)
        t.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            t.join(timeout=2)
            timed_out = True
        t.join(timeout=5)
        exit_code = proc.returncode if proc.returncode is not None else 1

    except FileNotFoundError:
        lines.append(f"✗ Executable not found: {_split_command(command)[0]}")
        exit_code = 1
    except Exception as exc:
        lines.append(f"✗ Failed to start process: {exc}")
        exit_code = 1

    # Trim to max_output_lines
    kept = lines[-_config.max_output_lines:]
    return ShellResult(
        command=command,
        cwd=resolved_cwd,
        exit_code=exit_code,
        output_lines=kept,
        timed_out=timed_out,
        hidden_lines=shown["hidden"],
        timeout_s=float(timeout or 0),
    )


# ─── LangChain tool ──────────────────────────────────────────────────────────



# ─── Agent loop (for direct invocation) ──────────────────────────────────────




# ─── Routing tool (called by the main LLM) ───────────────────────────────────



# ─── Rich renderer ───────────────────────────────────────────────────────────

def render(result: ShellResult):
    """`● Bash <command>` and its `⎿` result line (the output itself streamed live)."""
    from app.ui import shell_done, shell_start

    return Group(shell_start(result.command), shell_done(result))
