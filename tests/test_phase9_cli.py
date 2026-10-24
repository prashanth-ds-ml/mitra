import pathlib
import sys

from typer.testing import CliRunner

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import cli


runner = CliRunner()


def test_mcp_command_lists_profiles(tmp_path):
    result = runner.invoke(cli, ["mcp", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "MCP integration" in result.stdout
    assert "filesystem" in result.stdout
    assert "context7" in result.stdout


def test_mcp_command_supports_slash_alias(tmp_path):
    result = runner.invoke(cli, ["/mcp", "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "filesystem" in result.stdout
