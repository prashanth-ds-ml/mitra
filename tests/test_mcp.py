import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import mcp


def test_default_mcp_profiles_are_discoverable():
    servers = mcp.discover()
    names = [server.name for server in servers]

    assert names == ["filesystem", "git", "sqlite", "context7"]
    assert servers[0].command == "python"
    assert servers[0].args == ("-m", "app.mcp_servers.filesystem")


def test_format_prompt_lists_local_fallbacks():
    reply = mcp.format_prompt(mcp.discover())

    assert "MCP integration" in reply
    assert "filesystem" in reply
    assert "Built-in filesystem tools" in reply
    assert "Context7-compatible" in reply


def test_find_supports_exact_match():
    servers = mcp.discover()

    selected = mcp.find(servers, "sqlite")

    assert selected is not None
    assert selected.name == "sqlite"


def test_probe_filesystem_server_connects_and_lists_tools(tmp_path):
    server = mcp.discover()[0]

    result = mcp.probe_server(server, str(tmp_path))

    assert result.ok is True
    assert result.server.name == "filesystem"
    assert "Connected" in result.message
    assert "list_files" in result.tools
    assert "read_file" in result.tools
