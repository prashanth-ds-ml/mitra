"""LSP-backed diagnostics for supported local source files."""
from __future__ import annotations

from dataclasses import dataclass
import json
import pathlib
import queue
import shutil
import subprocess
import threading
import time

from rich.markdown import Markdown
from rich.panel import Panel


_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}
_LANGUAGE_ID = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
}
_SERVER_CANDIDATES = {
    "python": [
        ["basedpyright-langserver", "--stdio"],
        ["pyright-langserver", "--stdio"],
        ["pylsp"],
    ],
    "javascript": [["typescript-language-server", "--stdio"]],
    "typescript": [["typescript-language-server", "--stdio"]],
}
_IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
}
_MAX_SCAN_FILES = 25


@dataclass(frozen=True)
class Diagnostic:
    file_path: str
    line: int
    column: int
    severity: str
    message: str
    source: str


@dataclass
class DiagnosticsResponse:
    target: str
    summary: str


def _resolve_target_files(workspace: str, raw_target: str | None = None) -> list[pathlib.Path]:
    root = pathlib.Path(workspace).resolve()
    target_text = (raw_target or "").strip()
    if target_text:
        raw_path = pathlib.Path(target_text)
        target = raw_path.resolve() if raw_path.is_absolute() else (root / raw_path).resolve()
    else:
        target = root
    try:
        target.relative_to(root)
    except ValueError:
        return []

    if target.is_file():
        return [target] if target.suffix.lower() in _LANGUAGE_BY_SUFFIX else []
    if not target.is_dir():
        return []

    files: list[pathlib.Path] = []
    for path in sorted(target.rglob("*")):
        if len(files) >= _MAX_SCAN_FILES:
            break
        if any(part in _IGNORED_DIRS or part.startswith(".") for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in _LANGUAGE_BY_SUFFIX:
            files.append(path)
    return files


def _server_command(language: str) -> list[str] | None:
    for candidate in _SERVER_CANDIDATES.get(language, []):
        if shutil.which(candidate[0]):
            return candidate
    return None


def _severity_label(value: int | None) -> str:
    mapping = {1: "error", 2: "warning", 3: "information", 4: "hint"}
    return mapping.get(value, "warning")


def _path_to_uri(path: pathlib.Path) -> str:
    return path.resolve().as_uri()


def _lsp_location_to_str(workspace: pathlib.Path, location: dict) -> str:
    """Convert an LSP Location or LocationLink to a readable string."""
    uri = location.get("uri") or location.get("targetUri")
    if not uri:
        return "unknown location"
    try:
        path = pathlib.Path(uri.replace("file://", ""))
        rel_path = path.relative_to(workspace)
    except Exception:
        rel_path = pathlib.Path(uri)
    range_info = location.get("range") or location.get("targetSelectionRange") or {}
    start = range_info.get("start") or {}
    line = start.get("line", 0) + 1
    column = start.get("character", 0) + 1
    return f"{rel_path}:{line}:{column}"


def _read_rpc_message(stream) -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        name, _, value = line.decode("utf-8", errors="replace").partition(":")
        headers[name.strip().lower()] = value.strip()
    try:
        length = int(headers.get("content-length", "0"))
    except ValueError:
        return None
    if length <= 0:
        return None
    payload = stream.read(length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8", errors="replace"))


class _LspClient:
    def __init__(self, command: list[str], root: pathlib.Path):
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._root = root
        self._queue: queue.Queue[dict] = queue.Queue()
        self._pending: list[dict] = []
        self._next_id = 0
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self._proc.stdout is not None
        while True:
            message = _read_rpc_message(self._proc.stdout)
            if message is None:
                return
            self._queue.put(message)

    def _drain_stderr(self) -> None:
        if self._proc.stderr is None:
            return
        for _ in iter(self._proc.stderr.readline, b""):
            pass

    def _send(self, payload: dict) -> None:
        assert self._proc.stdin is not None
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._proc.stdin.write(header + body)
        self._proc.stdin.flush()

    def request(self, method: str, params: dict) -> int:
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        return request_id

    def notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _pop_message(self, timeout: float) -> dict | None:
        if self._pending:
            return self._pending.pop(0)
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_for_response(self, request_id: int, timeout: float = 5.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self._pop_message(max(0.05, deadline - time.time()))
            if message is None:
                continue
            if message.get("id") == request_id:
                return message
            self._pending.append(message)
        return None

    def request_definition(self, uri: str, line: int, character: int, timeout: float = 5.0) -> list[dict] | None:
        """Request goto-definition for a symbol at the given position."""
        request_id = self.request(
            "textDocument/definition",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )
        response = self.wait_for_response(request_id, timeout=timeout)
        if response and "result" in response:
            result = response["result"]
            if isinstance(result, list):
                return result
            elif result:
                return [result]
        return None

    def request_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True, timeout: float = 5.0
    ) -> list[dict] | None:
        """Request references for a symbol at the given position."""
        request_id = self.request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": include_declaration},
            },
        )
        response = self.wait_for_response(request_id, timeout=timeout)
        if response and "result" in response:
            return response["result"] or []
        return None

    def collect_diagnostics(self, opened_uris: set[str], total_timeout: float = 4.0, idle_timeout: float = 0.6) -> dict[str, list[dict]]:
        diagnostics: dict[str, list[dict]] = {}
        deadline = time.time() + total_timeout
        last_message = time.time()
        while time.time() < deadline:
            message = self._pop_message(min(0.2, max(0.05, deadline - time.time())))
            if message is None:
                if time.time() - last_message >= idle_timeout:
                    break
                continue
            last_message = time.time()
            if message.get("method") != "textDocument/publishDiagnostics":
                continue
            params = message.get("params") or {}
            uri = params.get("uri")
            if uri in opened_uris:
                diagnostics[uri] = list(params.get("diagnostics") or [])
        return diagnostics

    def close(self) -> None:
        try:
            request_id = self.request("shutdown", {})
            self.wait_for_response(request_id, timeout=2.0)
        except Exception:
            pass
        try:
            self.notify("exit", {})
        except Exception:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=1.0)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass


def _collect_language_diagnostics(workspace: pathlib.Path, language: str, files: list[pathlib.Path]) -> tuple[list[Diagnostic], str | None]:
    command = _server_command(language)
    if command is None:
        return [], None

    client = _LspClient(command, workspace)
    diagnostics: list[Diagnostic] = []
    try:
        init_id = client.request(
            "initialize",
            {
                "processId": None,
                "rootUri": _path_to_uri(workspace),
                "capabilities": {},
            },
        )
        client.wait_for_response(init_id, timeout=5.0)
        client.notify("initialized", {})

        opened_uris: set[str] = set()
        for path in files:
            uri = _path_to_uri(path)
            opened_uris.add(uri)
            client.notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": _LANGUAGE_ID[language],
                        "version": 1,
                        "text": path.read_text(encoding="utf-8", errors="replace"),
                    }
                },
            )
        raw_diagnostics = client.collect_diagnostics(opened_uris)
        for path in files:
            uri = _path_to_uri(path)
            for item in raw_diagnostics.get(uri, []):
                start = (item.get("range") or {}).get("start") or {}
                diagnostics.append(
                    Diagnostic(
                        file_path=str(path.relative_to(workspace)),
                        line=int(start.get("line", 0)) + 1,
                        column=int(start.get("character", 0)) + 1,
                        severity=_severity_label(item.get("severity")),
                        message=str(item.get("message", "")).strip(),
                        source=str(item.get("source", command[0])),
                    )
                )
    finally:
        client.close()
    return diagnostics, command[0]


def _collect_symbol_info(
    workspace: pathlib.Path, language: str, files: list[pathlib.Path], symbol: str
) -> tuple[list[dict], list[dict], str | None]:
    """Collect LSP definitions and references for a symbol across files.
    Returns (definitions, references, server_name)."""
    command = _server_command(language)
    if command is None:
        return [], [], None

    client = _LspClient(command, workspace)
    definitions: list[dict] = []
    references: list[dict] = []
    try:
        init_id = client.request(
            "initialize",
            {
                "processId": None,
                "rootUri": _path_to_uri(workspace),
                "capabilities": {},
            },
        )
        client.wait_for_response(init_id, timeout=5.0)
        client.notify("initialized", {})

        opened_uris: set[str] = set()
        file_contents: dict[str, str] = {}
        for path in files:
            uri = _path_to_uri(path)
            opened_uris.add(uri)
            content = path.read_text(encoding="utf-8", errors="replace")
            file_contents[uri] = content
            client.notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": _LANGUAGE_ID[language],
                        "version": 1,
                        "text": content,
                    }
                },
            )

        for path in files:
            uri = _path_to_uri(path)
            content = file_contents.get(uri, "")
            lines = content.splitlines()
            for line_idx, line in enumerate(lines):
                char_idx = 0
                while True:
                    char_idx = line.find(symbol, char_idx)
                    if char_idx == -1:
                        break
                    if (char_idx == 0 or not line[char_idx - 1].isalnum()) and (
                        char_idx + len(symbol) >= len(line) or not line[char_idx + len(symbol)].isalnum()
                    ):
                        defs = client.request_definition(uri, line_idx, char_idx)
                        if defs:
                            definitions.extend(defs)
                        refs = client.request_references(uri, line_idx, char_idx)
                        if refs:
                            references.extend(refs)
                    char_idx += len(symbol)

    finally:
        client.close()

    unique_defs = []
    seen_uris = set()
    for d in definitions:
        uri = d.get("uri") or d.get("targetUri")
        if uri and uri not in seen_uris:
            seen_uris.add(uri)
            unique_defs.append(d)

    unique_refs = []
    seen_refs = set()
    for r in references:
        uri = r.get("uri")
        start = (r.get("range") or {}).get("start") or {}
        key = (uri, start.get("line"), start.get("character"))
        if key not in seen_refs:
            seen_refs.add(key)
            unique_refs.append(r)

    return unique_defs, unique_refs, command[0]


def run(workspace: str, target: str = "") -> DiagnosticsResponse:
    root = pathlib.Path(workspace).resolve()
    files = _resolve_target_files(workspace, target)
    shown_target = target.strip() or "."
    if not files:
        summary = (
            f"## Diagnostics for `{shown_target}`\n\n"
            "No supported source files were found. Supported extensions: `.py`, `.js`, `.jsx`, `.ts`, `.tsx`."
        )
        return DiagnosticsResponse(target=shown_target, summary=summary)

    by_language: dict[str, list[pathlib.Path]] = {}
    for path in files:
        by_language.setdefault(_LANGUAGE_BY_SUFFIX[path.suffix.lower()], []).append(path)

    unavailable: list[str] = []
    diagnostics: list[Diagnostic] = []
    server_names: list[str] = []
    for language, language_files in by_language.items():
        found, server_name = _collect_language_diagnostics(root, language, language_files)
        if server_name is None:
            unavailable.append(language)
            continue
        server_names.append(server_name)
        diagnostics.extend(found)

    lines = [f"## Diagnostics for `{shown_target}`", ""]
    if server_names:
        lines.append(f"- **LSP servers used:** {', '.join(sorted(set(server_names)))}")
    lines.append(f"- **Files scanned:** {len(files)}")
    if unavailable:
        lines.append(f"- **No server found for:** {', '.join(sorted(unavailable))}")
    lines.append("")

    if diagnostics:
        lines.append("### Reported diagnostics")
        for item in diagnostics[:25]:
            lines.append(
                f"- `{item.file_path}:{item.line}:{item.column}` [{item.severity}] {item.message} ({item.source})"
            )
        if len(diagnostics) > 25:
            lines.append(f"- ... and {len(diagnostics) - 25} more")
    else:
        lines.append("No diagnostics were reported by the available language servers.")
    return DiagnosticsResponse(target=shown_target, summary="\n".join(lines))


def render(response: DiagnosticsResponse) -> Panel:
    return Panel(
        Markdown(response.summary),
        title="[bold cyan]Diagnostics[/bold cyan]",
        border_style="cyan",
    )
