"""A tiny stdio MCP server for tests (no downloads). Run: python tests/fixtures/fake_mcp_server.py"""
import asyncio
import os

from mcp.server import MCPServer

server = MCPServer("fake")


@server.tool()
def echo(text: str) -> str:
    """Echo the text back. Used to check a free (read-only) call."""
    return f"echo:{text}"


@server.tool()
def write_note(text: str) -> str:
    """Write a note. Stands in for a write tool that needs approval."""
    return f"written:{text}"


@server.tool()
async def slow(seconds: float) -> str:
    """Sleep for a while, to test timeouts."""
    await asyncio.sleep(seconds)
    return "done"


@server.tool()
def big(size: int = 20000) -> str:
    """Return a long text, to test trimming."""
    return "".join(chr(97 + i % 26) for i in range(size))


@server.tool()
def show_env(name: str) -> str:
    """Return an environment variable, to test secret masking."""
    return os.environ.get(name, "")


if __name__ == "__main__":
    server.run("stdio")
