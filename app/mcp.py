"""Local-first MCP profile registry and formatting helpers."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class MCPServer:
    name: str
    description: str
    fallback: str
    transport: str = "local-fallback"
    command: str = ""
    args: tuple[str, ...] = ()
    enabled: bool = False
    source: str = "built-in"


@dataclass(frozen=True)
class MCPProbeResult:
    server: MCPServer
    ok: bool
    message: str
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class MCPCallResult:
    server: MCPServer
    ok: bool
    message: str
    text: str = ""


_DEFAULT_MCP_SERVERS: tuple[MCPServer, ...] = (
    MCPServer(
        name="filesystem",
        description="Workspace file access through MCP-compatible filesystem servers.",
        fallback="Built-in filesystem tools",
        command="python",
        args=("-m", "app.mcp_servers.filesystem"),
        enabled=True,
    ),
    MCPServer(
        name="git",
        description="Repository inspection through an MCP git server.",
        fallback="Built-in git helpers",
    ),
    MCPServer(
        name="sqlite",
        description="Structured local memory through an MCP SQLite server.",
        fallback="Built-in memory and trace storage",
    ),
    MCPServer(
        name="context7",
        description="Reference lookup through a Context7-compatible MCP server.",
        fallback="Built-in web and docs tools",
    ),
)


def _normalize_args(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    return (str(value),)


def _normalize_server(entry, *, source: str = "configured") -> MCPServer:
    if not isinstance(entry, dict):
        raise TypeError("Each MCP server entry must be a dict.")
    name = str(entry.get("name", "")).strip().lower()
    if not name:
        raise ValueError("Each MCP server entry must have a name.")
    description = str(entry.get("description", "")).strip() or "MCP server"
    fallback = str(entry.get("fallback", "")).strip() or "Built-in local tools"
    transport = str(entry.get("transport", "local-fallback")).strip() or "local-fallback"
    command = str(entry.get("command", "")).strip()
    args = _normalize_args(entry.get("args"))
    enabled = bool(entry.get("enabled", False))
    return MCPServer(
        name=name,
        description=description,
        fallback=fallback,
        transport=transport,
        command=command,
        args=args,
        enabled=enabled,
        source=source,
    )


def discover(configured=None) -> list[MCPServer]:
    """Return configured MCP server profiles, or the built-in local-first set."""
    if configured is None or configured == []:
        return list(_DEFAULT_MCP_SERVERS)
    if isinstance(configured, dict):
        configured = [configured]

    servers: list[MCPServer] = []
    seen: set[str] = set()
    for entry in configured:
        server = _normalize_server(entry)
        if server.name in seen:
            continue
        servers.append(server)
        seen.add(server.name)
    return servers or list(_DEFAULT_MCP_SERVERS)


def find(servers: list[MCPServer], query: str) -> MCPServer | None:
    """Find an MCP server by exact or partial name."""
    target = (query or "").strip().lower()
    if not target:
        return None
    for server in servers:
        if server.name == target:
            return server
    matches = [server for server in servers if target in server.name]
    return matches[0] if len(matches) == 1 else None


def _message_bytes(payload: dict) -> bytes:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    return header + raw


def _read_message(stream) -> dict:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            raise EOFError("MCP server closed the stream")
        stripped = line.decode("utf-8", errors="replace").strip()
        if not stripped:
            break
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        headers[key.strip().lower()] = value.strip()

    content_length = int(headers.get("content-length", "0"))
    if content_length <= 0:
        raise ValueError("MCP message missing content length")
    body = stream.read(content_length)
    if not body:
        raise EOFError("MCP server returned no body")
    return json.loads(body.decode("utf-8"))


def _spawn_server(server: MCPServer, workspace: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["CODEMITRA_WORKSPACE"] = workspace
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    command = [sys.executable if server.command.lower() == "python" else server.command, *server.args]
    return subprocess.Popen(
        command,
        cwd=str(repo_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def probe_server(server: MCPServer, workspace: str, *, timeout_seconds: float = 5.0) -> MCPProbeResult:
    """Connect to a configured MCP server and collect its advertised tools."""
    reply = _exchange(server, workspace, [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "codemitra", "version": "0.1.0"},
                "capabilities": {},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    ])
    if reply is None:
        return MCPProbeResult(server=server, ok=False, message=f"Failed to connect to `{server.name}`: unavailable")
    init_reply, tools_reply = reply
    if init_reply.get("error"):
        return MCPProbeResult(server=server, ok=False, message=f"Failed to connect to `{server.name}`: {init_reply['error']}")
    if tools_reply.get("error"):
        return MCPProbeResult(server=server, ok=False, message=f"Failed to connect to `{server.name}`: {tools_reply['error']}")
    tools = tools_reply.get("result", {}).get("tools", [])
    tool_names = tuple(
        str(tool.get("name", "")).strip()
        for tool in tools
        if isinstance(tool, dict) and str(tool.get("name", "")).strip()
    )
    message = f"Connected via `{server.command}` with {len(tool_names)} tool(s)"
    return MCPProbeResult(server=server, ok=True, message=message, tools=tool_names)


def call_tool(server: MCPServer, workspace: str, tool_name: str, arguments: dict | None = None) -> MCPCallResult:
    """Call a single MCP tool through the configured filesystem server."""
    if not server.command:
        return MCPCallResult(
            server=server,
            ok=False,
            message=f"{server.name} uses the local fallback: {server.fallback}",
        )

    reply = _exchange(
        server,
        workspace,
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "codemitra", "version": "0.1.0"},
                    "capabilities": {},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments or {}},
            },
        ],
    )
    if reply is None:
        return MCPCallResult(server=server, ok=False, message=f"Failed to connect to `{server.name}`: unavailable")
    init_reply, call_reply = reply
    if init_reply.get("error"):
        return MCPCallResult(server=server, ok=False, message=f"Failed to connect to `{server.name}`: {init_reply['error']}")
    if call_reply.get("error"):
        return MCPCallResult(server=server, ok=False, message=f"Failed to call `{tool_name}` on `{server.name}`: {call_reply['error']}")
    content = call_reply.get("result", {}).get("content", [])
    text = "\n".join(
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ).strip()
    return MCPCallResult(
        server=server,
        ok=True,
        message=f"Connected via `{server.command}`",
        text=text,
    )


def _exchange(server: MCPServer, workspace: str, requests: list[dict]) -> list[dict] | None:
    proc = _spawn_server(server, workspace)
    assert proc.stdin is not None
    assert proc.stdout is not None
    try:
        replies: list[dict] = []
        for request in requests:
            proc.stdin.write(_message_bytes(request))
            proc.stdin.flush()
            replies.append(_read_message(proc.stdout))
        return replies
    except Exception:
        return None
    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def format_prompt(servers: list[MCPServer]) -> str:
    """Render a compact operator-facing MCP catalog."""
    if not servers:
        return ""
    lines = [
        "## MCP integration",
        "",
        "MCP support is local-first here: the built-in Python tools remain the fallback until an external server is configured.",
        "",
    ]
    for server in servers:
        meta = [server.transport]
        if server.command:
            meta.append(server.command)
        if server.enabled:
            meta.append("enabled")
        meta.append(f"fallback: {server.fallback}")
        lines.append(f"- `{server.name}` ({', '.join(meta)}): {server.description}")
    return "\n".join(lines)


def build_reply(workspace: str, servers: list[MCPServer]) -> str:
    """Render a workspace-aware MCP status report."""
    if not servers:
        return "No MCP profiles found yet."

    lines = [
        "## MCP integration",
        "",
        "MCP support is local-first here: built-in Python tools remain the fallback unless a server probes successfully.",
        "",
    ]
    for server in servers:
        if server.command and server.enabled:
            probe = probe_server(server, workspace)
            if probe.ok:
                tool_text = ", ".join(f"`{name}`" for name in probe.tools) if probe.tools else "no advertised tools"
                lines.append(f"- `{server.name}`: connected via `{server.command}` with {tool_text}")
            else:
                lines.append(f"- `{server.name}`: {probe.message} (fallback: {server.fallback})")
        elif server.command:
            lines.append(f"- `{server.name}`: configured with `{server.command}` but not enabled; fallback: {server.fallback}")
        else:
            lines.append(f"- `{server.name}`: {server.fallback}")
    return "\n".join(lines)


def summarize(servers: list[MCPServer]) -> str:
    if not servers:
        return "No MCP profiles configured yet."
    enabled = sum(1 for server in servers if server.enabled)
    names = ", ".join(f"`{server.name}`" for server in servers)
    if enabled:
        return f"{len(servers)} MCP profiles, {enabled} enabled: {names}"
    return f"{len(servers)} MCP profiles available with local fallbacks: {names}"
