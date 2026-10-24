from __future__ import annotations

import base64
import pathlib
import platform
import re
import shlex
import shutil
import subprocess

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from app.agents.response import AgentResponse, ToolResult
from app import memory, mcp as mcp_registry
from app.policy import Policy, Scope, Action, load_policy
from app.prompts import FILESYSTEM_SYSTEM_PROMPT as _SYSTEM_PROMPT

# ─── Permissions ────────────────────────────────────────────────────────────__

# Safe tools enabled by default.
_DEFAULT_TOOLS: set[str] = {
    "create_folder",
    "create_file",
    "edit_file",
    "read_file",
    "list_directory",
    "search_text",
    "delete_file",
    "delete_folder",
    "move_file",
    "create_venv",
    "install_packages",
    "git_status",
    "git_diff",
    "git_commit",
    "create_markdown_file",
    "update_markdown_file",
}

# Tools that modify or destroy existing content — require user confirmation.
_DESTRUCTIVE_TOOLS: set[str] = {
    "delete_file",
    "delete_folder",
    "move_file",
}

_WRITE_PREVIEW_TOOLS: set[str] = {
    "create_file",
    "edit_file",
    "create_markdown_file",
    "update_markdown_file",
}

# Executables allowed when run_command is enabled.
_DEFAULT_COMMANDS: set[str] = {
    "python", "python3", "pip", "pip3",
    "git", "npm", "node", "uvicorn",
}


class PermissionGuard:
    """
    Controls what the filesystem agent is allowed to do.

    workspace       – if set, all path arguments must live inside this directory.
    allowed_tools   – set of tool names the agent may call.
    allowed_commands– executables permitted when run_command is enabled.
    policy          – Policy engine for deny-first rule evaluation.
    """

    def __init__(
        self,
        workspace: str | None = None,
        allowed_roots: list[str] | None = None,
        allowed_tools: set[str] | None = None,
        allowed_commands: set[str] | None = None,
        confirm_fn=None,
        require_diff_approval: bool = False,
        policy: Policy | None = None,
        policy_path: str | None = None,
    ) -> None:
        self.workspace = pathlib.Path(workspace).resolve() if workspace else None
        self.allowed_roots = [pathlib.Path(root).resolve() for root in (allowed_roots or [])]
        self.allowed_tools = allowed_tools if allowed_tools is not None else set(_DEFAULT_TOOLS)
        self.allowed_commands = allowed_commands if allowed_commands is not None else set(_DEFAULT_COMMANDS)
        # Callable(tool_name, args_dict) -> bool. None = auto-approve (no TTY).
        self.confirm_fn = confirm_fn
        self.require_diff_approval = require_diff_approval
        self.policy = policy or load_policy(policy_path)

    # ── Checks ────────────────────────────────────────────────────────────────

    def check_path(self, *paths: str) -> str | None:
        """Return an error string if any path escapes the workspace, else None."""
        if self.workspace is None and not self.allowed_roots:
            return None
        for p in paths:
            resolved = _resolve_path(p)
            roots = ([self.workspace] if self.workspace else []) + self.allowed_roots
            if not any(_is_relative_to(resolved, root) for root in roots):
                return f"✗ Permission denied: '{p}' is outside the allowed roots"
            if _is_sensitive_path(resolved):
                return f"✗ Permission denied: '{p}' looks like a secret or environment file"
        return None

    def check_command(self, command: str) -> str | None:
        """Return an error string if the executable is not allowed by policy, else None."""
        try:
            parts = shlex.split(command)
        except ValueError:
            return "✗ Could not parse command"
        if not parts:
            return "✗ Empty command"
        exe = pathlib.Path(parts[0]).name

        # Check policy first
        action = self.policy.evaluate(Scope.COMMAND, exe)
        if action == Action.DENY:
            return f"✗ Permission denied: command '{exe}' denied by policy"
        if action == Action.ASK and self.confirm_fn is None:
            return f"✗ Permission denied: command '{exe}' requires approval but no confirm_fn available"

        # Fallback to legacy allowlist for backward compatibility
        if exe not in self.allowed_commands:
            return (
                f"✗ Permission denied: '{exe}' is not in the allowed commands list. "
                f"Allowed: {sorted(self.allowed_commands)}"
            )
        return None

    def check_tool(self, tool_name: str) -> str | None:
        """Return an error string if the tool is not allowed by policy, else None."""
        action = self.policy.evaluate(Scope.TOOL, tool_name)
        if action == Action.DENY:
            return f"✗ Permission denied: tool '{tool_name}' denied by policy"
        if action == Action.ASK and self.confirm_fn is None:
            return f"✗ Permission denied: tool '{tool_name}' requires approval but no confirm_fn available"
        return None

    def filter_tools(self, tools: list) -> list:
        """Return only the tools allowed by policy."""
        allowed = []
        for t in tools:
            action = self.policy.evaluate(Scope.TOOL, t.name)
            if action != Action.DENY:
                allowed.append(t)
        return allowed


# Module-level guard — replace with configure() to change settings.
_guard = PermissionGuard()
_active_change_set: list[dict] | None = None
_mcp_servers_config: list[dict] | None = None


def configure(
    workspace: str | None = None,
    allowed_roots: list[str] | None = None,
    allowed_tools: set[str] | None = None,
    allowed_commands: set[str] | None = None,
    confirm_fn=None,
    require_diff_approval: bool = False,
    policy: Policy | None = None,
    policy_path: str | None = None,
    mcp_servers: list[dict] | None = None,
) -> None:
    """
    Update the permission guard for this session.

    Examples
    --------
    # Lock agent to a specific project folder
    filesystem.configure(workspace="C:/Users/dev/projects/myapi")

    # Also allow destructive tools
    filesystem.configure(
        workspace="C:/Users/dev/projects/myapi",
        allowed_tools=filesystem._DEFAULT_TOOLS | {"delete_file", "run_command"},
    )
    """
    global _guard, _mcp_servers_config
    _guard = PermissionGuard(
        workspace=workspace,
        allowed_roots=allowed_roots,
        allowed_tools=allowed_tools,
        allowed_commands=allowed_commands,
        confirm_fn=confirm_fn,
        require_diff_approval=require_diff_approval,
        policy=policy,
        policy_path=policy_path,
    )
    _mcp_servers_config = list(mcp_servers) if mcp_servers is not None else None


# ─── System prompt ─── (defined in app/prompts.py as FILESYSTEM_SYSTEM_PROMPT)


# ─── Tools ────────────────────────────────────────────────────────────────────

@tool
def create_folder(path: str) -> str:
    """Create a directory and any missing parent directories at the given path."""
    if err := _guard.check_path(path):
        return err
    try:
        target = _resolve_path(path)
        existed = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        if not existed:
            _record_change({
                "kind": "create_folder",
                "path": str(target),
            })
        return f"✓ Created folder: {path}"
    except Exception as exc:
        return f"✗ create_folder failed: {exc}"


@tool
def create_file(path: str, content: str = "") -> str:
    """Create a file at path with optional text content. Parent directories are created automatically."""
    if err := _guard.check_path(path):
        return err
    try:
        p = _resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists() and p.is_file()
        previous = None
        if p.exists() and p.is_file():
            previous = p.read_text(encoding="utf-8")
            if previous == content:
                return f"✓ File unchanged: {path}"
        p.write_text(content, encoding="utf-8")
        _record_change({
            "kind": "create_file",
            "path": str(p),
            "existed": existed,
            "before": previous,
            "after": content,
        })
        return f"✓ Created file: {path}"
    except Exception as exc:
        return f"✗ create_file failed: {exc}"


def _safe_is_dir(path: pathlib.Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _safe_is_file(path: pathlib.Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _resolve_path(path: str | None) -> pathlib.Path:
    target = pathlib.Path(path or ".")
    if not target.is_absolute() and _guard.workspace is not None:
        target = _guard.workspace / target
    return target.resolve()


def _is_relative_to(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _is_sensitive_path(path: pathlib.Path) -> bool:
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    if name in {"secret", "secrets"}:
        return True
    if name.startswith("secret.") or name.startswith("secrets."):
        return True
    return False


def _filesystem_mcp_server():
    if not _guard.workspace or _mcp_servers_config is None:
        return None
    servers = mcp_registry.discover(_mcp_servers_config)
    server = mcp_registry.find(servers, "filesystem")
    if not server or not server.enabled or not server.command:
        return None
    return server


def _route_filesystem_mcp(tool_name: str, arguments: dict, fallback):
    server = _filesystem_mcp_server()
    if server is None:
        return None
    result = mcp_registry.call_tool(server, str(_guard.workspace), tool_name, arguments)
    if result.ok and result.text.strip():
        return result.text.strip()
    return fallback()


@tool
def read_file(path: str) -> str:
    """Read and return the full text content of a file."""
    def _fallback() -> str:
        if err := _guard.check_path(path):
            return err
        try:
            return _resolve_path(path).read_text(encoding="utf-8")
        except Exception as exc:
            return f"✗ read_file failed: {exc}"

    routed = _route_filesystem_mcp("read_file", {"path": path}, _fallback)
    return routed if routed is not None else _fallback()


@tool
def edit_file(path: str, content: str) -> str:
    """Replace the contents of an existing text file."""
    if err := _guard.check_path(path):
        return err
    try:
        target = _resolve_path(path)
        if not target.exists() or not target.is_file():
            return f"✗ edit_file failed: file does not exist: {path}"
        previous = target.read_text(encoding="utf-8")
        if previous == content:
            return f"✓ File unchanged: {path}"
        target.write_text(content, encoding="utf-8")
        _record_change({
            "kind": "edit_file",
            "path": str(target),
            "before": previous,
            "after": content,
        })
        return f"✓ Updated file: {path}"
    except Exception as exc:
        return f"✗ edit_file failed: {exc}"


@tool
def list_directory(path: str = ".") -> str:
    """List all files and sub-folders inside a directory."""
    def _fallback() -> str:
        if err := _guard.check_path(path):
            return err
        try:
            p = _resolve_path(path)
            entries = sorted(
                p.iterdir(),
                key=lambda e: (_safe_is_file(e), e.name.lower()),
            )
            if not entries:
                return f"{path}/ (empty)"
            lines = [
                f"  {'[dir] ' if _safe_is_dir(e) else '[file]'} {e.name}"
                for e in entries
            ]
            return f"{path}/\n" + "\n".join(lines)
        except Exception as exc:
            return f"✗ list_directory failed: {exc}"

    routed = _route_filesystem_mcp("list_files", {"path": path}, _fallback)
    return routed if routed is not None else _fallback()


@tool
def search_text(pattern: str, path: str = ".") -> str:
    """Search for plain text under a directory and return matching file:line entries."""
    if err := _guard.check_path(path):
        return err
    needle = (pattern or "").strip()
    if not needle:
        return "✗ search_text failed: pattern is empty"
    try:
        root = _resolve_path(path)
        if root.is_file():
            targets = [root]
        else:
            targets = [candidate for candidate in root.rglob("*") if candidate.is_file()]
        matches: list[str] = []
        for target in targets:
            if _is_sensitive_path(target):
                continue
            try:
                text = target.read_text(encoding="utf-8")
            except Exception:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                if needle in line:
                    rel = target.relative_to(root) if root.is_dir() else target.name
                    matches.append(f"{rel}:{line_no}: {line.strip()}")
                    if len(matches) >= 50:
                        return "\n".join(matches)
        return "\n".join(matches) if matches else f"No matches found for: {needle}"
    except Exception as exc:
        return f"✗ search_text failed: {exc}"


@tool
def delete_file(path: str) -> str:
    """Delete a single file at the given path."""
    if err := _guard.check_path(path):
        return err
    if _guard.confirm_fn and not _guard.confirm_fn("delete_file", {"path": path}):
        return "✗ Skipped: user declined delete_file"
    try:
        target = _resolve_path(path)
        existed = target.exists()
        if existed:
            try:
                snapshot = _snapshot_file(target)
            except Exception:
                _record_change({
                    "kind": "delete_file",
                    "path": str(target),
                    "undo_supported": False,
                    "reason": "The deleted file could not be captured safely for undo.",
                })
                target.unlink(missing_ok=True)
                return f"✓ Deleted file: {path}"
        target.unlink(missing_ok=True)
        if existed:
            _record_change({
                "kind": "delete_file",
                "path": str(target),
                "undo_supported": True,
                "before": snapshot,
            })
        return f"✓ Deleted file: {path}"
    except Exception as exc:
        return f"✗ delete_file failed: {exc}"


@tool
def delete_folder(path: str) -> str:
    """Delete a folder and all its contents recursively."""
    if err := _guard.check_path(path):
        return err
    if _guard.confirm_fn and not _guard.confirm_fn("delete_folder", {"path": path}):
        return "✗ Skipped: user declined delete_folder"
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"✗ delete_folder failed: folder does not exist: {path}"
        _record_change({
            "kind": "delete_folder",
            "path": str(target),
            "undo_supported": True,
            "snapshot": _snapshot_directory(target),
        })
        shutil.rmtree(target)
        return f"✓ Deleted folder: {path}"
    except Exception as exc:
        return f"✗ delete_folder failed: {exc}"


@tool
def move_file(src: str, dest: str) -> str:
    """Move or rename a file or folder from src to dest."""
    if err := _guard.check_path(src, dest):
        return err
    if _guard.confirm_fn and not _guard.confirm_fn("move_file", {"src": src, "dest": dest}):
        return "✗ Skipped: user declined move_file"
    try:
        source = _resolve_path(src)
        destination = _resolve_path(dest)
        if not source.exists():
            return f"✗ move_file failed: source does not exist: {src}"
        if destination.exists():
            return f"✗ move_file failed: destination already exists: {dest}"
        _record_change({
            "kind": "move_file",
            "src": str(source),
            "dest": str(destination),
            "is_dir": source.is_dir(),
        })
        shutil.move(str(source), str(destination))
        return f"✓ Moved '{src}' → '{dest}'"
    except Exception as exc:
        return f"✗ move_file failed: {exc}"


@tool
def create_venv(project_path: str) -> str:
    """Create a Python virtual environment (.venv) inside the given project directory."""
    if err := _guard.check_path(project_path):
        return err
    try:
        project_dir = _resolve_path(project_path)
        result = subprocess.run(
            ["python", "-m", "venv", ".venv"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return f"✗ create_venv failed: {result.stderr.strip()}"
        return f"✓ Created .venv in {project_path}"
    except Exception as exc:
        return f"✗ create_venv failed: {exc}"


@tool
def install_packages(project_path: str, packages: list[str] | None = None) -> str:
    """
    Install packages into the project's .venv.
    If packages is omitted or empty, installs from requirements.txt in project_path.
    If packages are given, installs them and writes the pinned result to requirements.txt.
    """
    if err := _guard.check_path(project_path):
        return err
    try:
        project_dir = _resolve_path(project_path)
        pip = _pip(str(project_dir))
        if packages:
            result = subprocess.run(
                [pip, "install", *packages],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return f"✗ install failed: {result.stderr.strip()}"
            freeze = subprocess.run([pip, "freeze"], capture_output=True, text=True)
            (project_dir / "requirements.txt").write_text(
                freeze.stdout, encoding="utf-8"
            )
            return f"✓ Installed {', '.join(packages)} and wrote requirements.txt"
        else:
            req = project_dir / "requirements.txt"
            if not req.exists():
                return "✗ No requirements.txt found and no packages specified."
            result = subprocess.run(
                [pip, "install", "-r", str(req)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return f"✗ install failed: {result.stderr.strip()}"
            return "✓ Installed all packages from requirements.txt"
    except Exception as exc:
        return f"✗ install_packages failed: {exc}"


@tool
def run_command(command: str, cwd: str = ".") -> str:
    """
    Run a whitelisted shell command in the given working directory.
    Only executables in the allowed_commands list are permitted.
    """
    if err := _guard.check_path(cwd):
        return err
    if err := _guard.check_command(command):
        return err
    try:
        resolved_cwd = _resolve_path(cwd)
        result = subprocess.run(
            shlex.split(command),
            cwd=resolved_cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        status = "✓" if result.returncode == 0 else "✗"
        return f"{status} [{result.returncode}]\n{output}" if output else f"{status} Done"
    except subprocess.TimeoutExpired:
        return "✗ Command timed out after 120 seconds"
    except Exception as exc:
        return f"✗ run_command failed: {exc}"


# ─── Git tools ───────────────────────────────────────────────────────────────

@tool
def git_status(cwd: str = ".") -> str:
    """Show the git working tree status (short format) for a repository."""
    if err := _guard.check_path(cwd):
        return err
    try:
        resolved_cwd = _resolve_path(cwd)
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=resolved_cwd, capture_output=True, text=True,
        )
        output = result.stdout.strip() or "(nothing to report)"
        return f"✓ git status\n{output}" if result.returncode == 0 else f"✗ {result.stderr.strip()}"
    except Exception as exc:
        return f"✗ git_status failed: {exc}"


@tool
def git_diff(cwd: str = ".", staged: bool = False) -> str:
    """Show the diff of unstaged changes (staged=False) or staged changes (staged=True)."""
    if err := _guard.check_path(cwd):
        return err
    try:
        resolved_cwd = _resolve_path(cwd)
        args = ["git", "diff"]
        if staged:
            args.append("--staged")
        result = subprocess.run(args, cwd=resolved_cwd, capture_output=True, text=True)
        output = result.stdout.strip() or "(no diff)"
        return f"✓ git diff\n{output}" if result.returncode == 0 else f"✗ {result.stderr.strip()}"
    except Exception as exc:
        return f"✗ git_diff failed: {exc}"


@tool
def git_commit(cwd: str, message: str) -> str:
    """Stage all changes (git add -A) and create a commit with the given message."""
    if err := _guard.check_path(cwd):
        return err
    try:
        resolved_cwd = _resolve_path(cwd)
        add = subprocess.run(["git", "add", "-A"], cwd=resolved_cwd, capture_output=True, text=True)
        if add.returncode != 0:
            return f"✗ git add failed: {add.stderr.strip()}"
        commit = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=resolved_cwd, capture_output=True, text=True,
        )
        output = commit.stdout.strip() or commit.stderr.strip()
        return f"✓ Committed: {message}\n{output}" if commit.returncode == 0 else f"✗ {output}"
    except Exception as exc:
        return f"✗ git_commit failed: {exc}"


@tool
def create_markdown_file(path: str, content: str = "") -> str:
    """Create a markdown file with .md suffix."""
    if not str(path).lower().endswith(".md"):
        return f"✗ create_markdown_file failed: path must end with .md: {path}"
    return create_file.invoke({"path": path, "content": content})


@tool
def update_markdown_file(path: str, content: str) -> str:
    """Update an existing markdown file with .md suffix."""
    if not str(path).lower().endswith(".md"):
        return f"✗ update_markdown_file failed: path must end with .md: {path}"
    return edit_file.invoke({"path": path, "content": content})


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _pip(project_path: str) -> str:
    p = pathlib.Path(project_path)
    if platform.system() == "Windows":
        return str(p / ".venv" / "Scripts" / "pip")
    return str(p / ".venv" / "bin" / "pip")


def _clean(text: str) -> str:
    """Strip JSON tool-call blocks the model sometimes echoes in its final reply."""
    text = re.sub(r'\{[^{}]*"name"\s*:[^{}]*\}', "", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _augment_request_with_workspace(user_request: str) -> str:
    """Attach explicit workspace guidance for path-light requests."""
    if _guard.workspace is None:
        return user_request

    normalized = user_request.lower()
    hints: list[str] = []
    if any(phrase in normalized for phrase in ("same folder", "current folder", "this folder", "here")):
        hints.append(f"Use the current workspace as the target path: {_guard.workspace}")
    if any(phrase in normalized for phrase in (".venv", "venv", "virtual environment")):
        hints.append("If you need a project path, use '.' which refers to the current workspace.")

    if not hints:
        return user_request
    joined = "\n".join(f"- {hint}" for hint in hints)
    return f"{user_request}\n\nExecution notes:\n{joined}"


def _first_error_text(agent_response: AgentResponse) -> str:
    for step in agent_response.steps:
        if not step.ok:
            return step.output.lstrip("✗").strip().splitlines()[0]
    return ""


def _finalize_summary(agent_response: AgentResponse, model_summary: str) -> str:
    """Prefer deterministic summaries whenever tool execution had any failures."""
    if agent_response.err_count == 0:
        return model_summary

    first_error = _first_error_text(agent_response)
    if agent_response.ok_count == 0:
        if first_error:
            return f"Could not complete the request. {first_error}."
        return "Could not complete the request."

    success_labels = [step.label for step in agent_response.steps if step.ok][:2]
    completed = ", ".join(label for label in success_labels if label) or f"{agent_response.ok_count} step(s)"
    if first_error:
        return (
            f"Completed {completed}, but hit {agent_response.err_count} error"
            f"{'s' if agent_response.err_count != 1 else ''}. {first_error}."
        )
    return (
        f"Completed {completed}, but hit {agent_response.err_count} error"
        f"{'s' if agent_response.err_count != 1 else ''}."
    )


def _record_change(entry: dict) -> None:
    global _active_change_set
    if _active_change_set is not None:
        _active_change_set.append(entry)


def _persist_active_change_set() -> None:
    global _active_change_set
    if not _active_change_set or _guard.workspace is None:
        _active_change_set = None
        return
    memory.record_last_change_set(
        str(_guard.workspace),
        {"entries": _active_change_set},
    )
    _active_change_set = None


def _discard_active_change_set() -> None:
    global _active_change_set
    _active_change_set = None


def _snapshot_file(path: pathlib.Path) -> dict:
    return {"kind": "base64", "content": base64.b64encode(path.read_bytes()).decode("ascii")}


def _restore_file(path: pathlib.Path, snapshot: dict | str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(snapshot, str) or snapshot is None:
        path.write_text(snapshot or "", encoding="utf-8")
        return
    if snapshot.get("kind") == "base64":
        path.write_bytes(base64.b64decode(snapshot.get("content", "")))
        return
    path.write_text(snapshot.get("content", ""), encoding="utf-8")


def _snapshot_directory(path: pathlib.Path) -> dict:
    directories = [str(item.relative_to(path)) for item in sorted(path.rglob("*")) if item.is_dir()]
    files = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            files.append(
                {
                    "path": str(item.relative_to(path)),
                    "snapshot": _snapshot_file(item),
                }
            )
    return {"directories": directories, "files": files}


def undo_last_change_set(workspace: str) -> str:
    """Undo the last persisted create/move/delete file change set for this workspace."""
    change_set = memory.load_last_change_set(workspace)
    if not change_set:
        return "No undoable change set is available yet."

    entries = change_set.get("entries") or []
    unsupported = [
        entry for entry in entries
        if entry.get("undo_supported") is False
    ]
    if unsupported:
        reasons = "; ".join(entry.get("reason", "unsupported operation") for entry in unsupported[:2])
        return f"Cannot undo the last change set safely. {reasons}"

    try:
        for entry in reversed(entries):
            kind = entry.get("kind")
            if kind == "create_folder":
                target = pathlib.Path(entry["path"])
                if target.exists() and target.is_dir():
                    try:
                        target.rmdir()
                    except OSError:
                        pass
            elif kind == "create_file":
                target = pathlib.Path(entry["path"])
                if entry.get("existed"):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(entry.get("before") or "", encoding="utf-8")
                elif target.exists():
                    target.unlink()
            elif kind == "delete_file":
                target = pathlib.Path(entry["path"])
                _restore_file(target, entry.get("before"))
            elif kind == "delete_folder":
                target = pathlib.Path(entry["path"])
                snapshot = entry.get("snapshot") or {}
                target.mkdir(parents=True, exist_ok=True)
                for relative_dir in snapshot.get("directories", []):
                    (target / relative_dir).mkdir(parents=True, exist_ok=True)
                for file_entry in snapshot.get("files", []):
                    _restore_file(target / file_entry["path"], file_entry.get("snapshot"))
            elif kind == "move_file":
                src = pathlib.Path(entry["src"])
                dest = pathlib.Path(entry["dest"])
                if not dest.exists():
                    return f"Cannot undo the last rename because `{dest}` no longer exists."
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(src))
        memory.clear_last_change_set(workspace)
        return f"Undid {len(entries)} change step{'s' if len(entries) != 1 else ''} from the last change set."
    except Exception as exc:
        return f"Undo failed: {exc}"


def execute_cleanup(paths: list[str], request: str = "Apply approved cleanup plan") -> AgentResponse:
    """Delete a pre-approved list of files/folders with one approval handled upstream."""
    response = AgentResponse(request=request)
    saved_confirm = _guard.confirm_fn
    global _active_change_set
    _active_change_set = []
    _guard.confirm_fn = None
    try:
        for path in paths:
            target = _resolve_path(path)
            if target.is_dir():
                output = delete_folder.invoke({"path": path})
                tool_name = "delete_folder"
            else:
                output = delete_file.invoke({"path": path})
                tool_name = "delete_file"
            response.steps.append(ToolResult(tool=tool_name, args={"path": path}, output=str(output)))
        response.summary = _finalize_summary(
            response,
            f"Removed {response.ok_count} cleanup item{'s' if response.ok_count != 1 else ''}.",
        )
        _persist_active_change_set()
        return response
    finally:
        _discard_active_change_set()
        _guard.confirm_fn = saved_confirm


def _should_confirm_write(tool_name: str, args: dict) -> bool:
    """Return True when a write tool should show a diff preview before execution."""
    if tool_name not in _WRITE_PREVIEW_TOOLS or not _guard.require_diff_approval:
        return False

    path = args.get("path")
    if not path or _guard.check_path(path):
        return False

    target = pathlib.Path(path)
    if not target.exists() or not target.is_file():
        return False

    try:
        existing = target.read_text(encoding="utf-8")
    except Exception:
        return True

    return existing != args.get("content", "")


# ─── All tools (unfiltered) ───────────────────────────────────────────────────

_ALL_TOOLS = [
    create_folder,
    create_file,
    edit_file,
    read_file,
    list_directory,
    search_text,
    delete_file,
    delete_folder,
    move_file,
    create_venv,
    install_packages,
    run_command,
    git_status,
    git_diff,
    git_commit,
    create_markdown_file,
    update_markdown_file,
]


# ─── Public API ───────────────────────────────────────────────────────────────

def make_routing_tool(llm):
    """Return a LangChain tool that the main LLM can call to invoke this agent."""
    @tool
    def setup_project(request: str) -> str:
        """
        Set up a Python project on disk. Use when the user asks to create folders,
        create files, create a virtual environment (.venv), or install Python packages.
        Pass the full user request unchanged.
        """
        return run(llm, request).summary
    return setup_project


def _invoke_tool_call(tool_name: str, args: dict, tool_map: dict[str, object], console=None) -> str:
    fn = tool_map.get(tool_name)
    if fn is None:
        return f"✗ Unknown tool: {tool_name}"
    if _guard.confirm_fn is not None and _should_confirm_write(tool_name, args):
        approved = _guard.confirm_fn(tool_name, args)
        if not approved:
            return f"✗ Skipped: user declined {tool_name}"
    if console is not None:
        with console.status(f"[bold cyan]Running {tool_name}...[/bold cyan]", spinner="dots"):
            return fn.invoke(args)
    return fn.invoke(args)


def run_direct(tool_name: str, args: dict, *, request: str | None = None, console=None) -> AgentResponse:
    """Execute one filesystem tool directly without an LLM routing loop."""
    active_tools = _guard.filter_tools(_ALL_TOOLS)
    tool_map = {t.name: t for t in active_tools}
    agent_response = AgentResponse(request=request or tool_name.replace("_", " "))

    global _active_change_set
    _active_change_set = []
    try:
        output = _invoke_tool_call(tool_name, args, tool_map, console=console)
        agent_response.steps.append(ToolResult(tool=tool_name, args=args, output=str(output)))
        agent_response.summary = _finalize_summary(agent_response, _clean(str(output).lstrip("✓ ").strip()))
        _persist_active_change_set()
        return agent_response
    finally:
        _discard_active_change_set()


def run(llm, user_request: str, console=None) -> AgentResponse:
    """Run the filesystem agent and return a structured AgentResponse."""
    active_tools = _guard.filter_tools(_ALL_TOOLS)
    tool_map = {t.name: t for t in active_tools}
    llm_with_tools = llm.bind_tools(active_tools)

    agent_response = AgentResponse(request=user_request)

    messages: list = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_augment_request_with_workspace(user_request)),
    ]

    global _active_change_set
    _active_change_set = []
    try:
        while True:
            phase = "Summarizing file changes..." if any(isinstance(m, ToolMessage) for m in messages) else "Planning file changes..."
            if console is not None:
                with console.status(f"[bold cyan]{phase}[/bold cyan]", spinner="dots"):
                    response: AIMessage = llm_with_tools.invoke(messages)
            else:
                response = llm_with_tools.invoke(messages)

            # Accumulate token usage
            meta = getattr(response, "usage_metadata", None) or {}
            agent_response.tokens_in += meta.get("input_tokens", 0)
            agent_response.tokens_out += meta.get("output_tokens", 0)

            messages.append(response)

            if not response.tool_calls:
                agent_response.summary = _finalize_summary(agent_response, _clean(response.content))
                _persist_active_change_set()
                return agent_response

            for tc in response.tool_calls:
                # Show live progress
                if console is not None:
                    args_str = ", ".join(
                        f"{k}={repr(str(v))[:50]}" for k, v in tc["args"].items()
                    )
                    console.print(
                        f"  [dim cyan]⋯[/dim cyan] [cyan]{tc['name']}[/cyan][dim]({args_str})[/dim]"
                    )

                output = _invoke_tool_call(tc["name"], tc["args"], tool_map, console=console)
                agent_response.steps.append(
                    ToolResult(tool=tc["name"], args=tc["args"], output=str(output))
                )
                messages.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
    finally:
        _discard_active_change_set()
