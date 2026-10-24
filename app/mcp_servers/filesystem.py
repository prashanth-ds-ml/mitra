"""Minimal stdio MCP filesystem server for workspace-local use."""
from __future__ import annotations

import json
import os
import pathlib
import sys


def _workspace_root() -> pathlib.Path:
    value = os.environ.get("CODEMITRA_WORKSPACE") or os.getcwd()
    return pathlib.Path(value).resolve()


def _resolve_path(workspace: pathlib.Path, path: str) -> pathlib.Path:
    target = (workspace / path).resolve()
    target.relative_to(workspace)
    return target


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _list_files(workspace: pathlib.Path, path: str = ".") -> str:
    target = _resolve_path(workspace, path)
    if not target.exists():
        return f"Path not found: {path}"
    if target.is_file():
        return target.name
    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        suffix = "/" if item.is_dir() else ""
        entries.append(f"{item.name}{suffix}")
    return "\n".join(entries) if entries else "(empty)"


def _read_file(workspace: pathlib.Path, path: str) -> str:
    target = _resolve_path(workspace, path)
    if not target.exists() or not target.is_file():
        return f"File not found: {path}"
    return _read_text(target)


def _search_text(workspace: pathlib.Path, pattern: str, path: str = ".") -> str:
    root = _resolve_path(workspace, path)
    if not root.exists():
        return f"Path not found: {path}"
    matches: list[str] = []
    needle = pattern.lower()
    for file in root.rglob("*"):
        if not file.is_file():
            continue
        try:
            text = _read_text(file)
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if needle in line.lower():
                matches.append(f"{file.relative_to(workspace)}:{lineno}: {line.strip()}")
    return "\n".join(matches) if matches else "No matches found."


def _tools() -> list[dict]:
    schema = lambda path_default=".": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": path_default},
        },
        "additionalProperties": False,
    }
    return [
        {
            "name": "list_files",
            "description": "List files and folders relative to the workspace root.",
            "inputSchema": schema(),
        },
        {
            "name": "read_file",
            "description": "Read a file inside the workspace.",
            "inputSchema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "search_text",
            "description": "Search plain text across workspace files.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        },
    ]


def _send_message(stream, payload: dict) -> None:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    stream.write(header + body)
    stream.flush()


def _read_message(stream) -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.buffer.readline()
        if not line:
            return None
        stripped = line.decode("utf-8", errors="replace").strip()
        if not stripped:
            break
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = stream.buffer.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def main() -> int:
    workspace = _workspace_root()
    stdout = sys.stdout
    while True:
        request = _read_message(sys.stdin)
        if request is None:
            break
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        try:
            if method == "initialize":
                response = _result(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "codemitra-filesystem", "version": "0.1.0"},
                        "capabilities": {"tools": {}},
                    },
                )
            elif method == "tools/list":
                response = _result(request_id, {"tools": _tools()})
            elif method == "tools/call":
                name = str(params.get("name", ""))
                arguments = params.get("arguments") or {}
                if name == "list_files":
                    text = _list_files(workspace, str(arguments.get("path", ".")))
                elif name == "read_file":
                    text = _read_file(workspace, str(arguments.get("path", "")))
                elif name == "search_text":
                    text = _search_text(workspace, str(arguments.get("pattern", "")), str(arguments.get("path", ".")))
                else:
                    raise ValueError(f"Unknown tool: {name}")
                response = _result(
                    request_id,
                    {
                        "content": [{"type": "text", "text": text}],
                        "isError": False,
                    },
                )
            elif method == "notifications/initialized":
                continue
            else:
                response = _error(request_id, -32601, f"Unknown method: {method}")
        except Exception as exc:
            response = _error(request_id, -32000, str(exc))
        _send_message(stdout.buffer, response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
