"""Tests for app/mcp.py: config, trust, approval, masking, and live calls to a local fake stdio server."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import mcp

FAKE_SERVER = pathlib.Path(__file__).resolve().parent / "fixtures" / "fake_mcp_server.py"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Own ~/.mitra per test; no built-in servers unless a test asks for them."""
    monkeypatch.setenv("MITRA_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MITRA_MCP_NO_DEFAULTS", "1")
    monkeypatch.setenv("MITRA_CLAUDE_CONFIG", str(tmp_path / "claude.json"))
    yield
    mcp.manager().close_all()


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


def write_user_servers(servers: dict) -> None:
    path = mcp.user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")


def fake_entry(**extra):
    return {"command": sys.executable, "args": [str(FAKE_SERVER)],
            "allow": ["echo", "slow", "big", "show_env"], "timeout_s": 5, **extra}


# ── config ──────────────────────────────────────────────────────────────────

def test_defaults_include_the_day_one_servers(monkeypatch, workspace):
    monkeypatch.delenv("MITRA_MCP_NO_DEFAULTS")
    specs = {s.name: s for s in mcp.discover(workspace)}

    for name in ("git", "github", "context7", "semgrep"):
        assert specs[name].usable, name
    assert specs["github"].kind == "http"
    assert not specs["aws-docs"].enabled
    assert not specs["filesystem"].enabled  # duplicates Mitra's own read/list/search tools (D-049)


def test_user_file_overrides_a_default_per_key(monkeypatch, workspace):
    monkeypatch.delenv("MITRA_MCP_NO_DEFAULTS")
    write_user_servers({"github": {"env_commands": {"GITHUB_TOKEN": "gh auth token -u someone"}}})

    github = mcp.find(mcp.discover(workspace), "github")

    assert github.env_commands == {"GITHUB_TOKEN": "gh auth token -u someone"}
    assert github.url == "https://api.githubcopilot.com/mcp/"  # rest of the default kept
    assert github.source == "user"


def test_project_servers_need_trust_and_lose_it_when_the_file_changes(workspace):
    project = mcp.project_config_path(workspace)
    project.parent.mkdir(parents=True)
    project.write_text(json.dumps({"mcpServers": {"proj": fake_entry()}}), encoding="utf-8")

    assert not mcp.find(mcp.discover(workspace), "proj").usable
    mcp.trust_project(workspace)
    assert mcp.find(mcp.discover(workspace), "proj").usable

    project.write_text(json.dumps({"mcpServers": {"proj": fake_entry(args=["other"])}}), encoding="utf-8")
    assert not mcp.find(mcp.discover(workspace), "proj").usable


def test_untrusted_project_server_is_never_started(workspace):
    project = mcp.project_config_path(workspace)
    project.parent.mkdir(parents=True)
    project.write_text(json.dumps({"mcpServers": {"proj": fake_entry()}}), encoding="utf-8")

    result = mcp.call_tool(workspace, "proj", "echo", {"text": "x"})

    assert not result.ok
    assert "/mcp trust" in result.text


def test_resolve_expands_workspace_env_commands_and_env(monkeypatch, workspace):
    monkeypatch.setenv("SOME_VAR", "from-env")
    spec = mcp.ServerSpec(
        name="x", command="python", args=["--repo", "${WORKSPACE}", "${SOME_VAR}"],
        headers={"Authorization": "Bearer ${TOKEN}"},
        env_commands={"TOKEN": f'"{sys.executable}" -c "print(123456789)"'},
    )
    resolved = mcp.resolve(spec, workspace)

    assert resolved.args == ["--repo", str(workspace.resolve()), "from-env"]
    assert resolved.headers == {"Authorization": "Bearer 123456789"}
    assert "123456789" in resolved.secrets


def test_resolve_reports_a_missing_variable(workspace):
    spec = mcp.ServerSpec(name="x", url="https://example.com/${NOPE_NOT_SET}")
    with pytest.raises(KeyError, match="NOPE_NOT_SET"):
        mcp.resolve(spec, workspace)


# ── approval and masking ────────────────────────────────────────────────────

@pytest.mark.parametrize("tool,expected", [
    ("get_issue", False), ("list_pulls", False), ("create_issue", True), ("merge_pull_request", True),
    ("get_secret_scanning_alert", True),
])
def test_needs_approval_uses_allow_and_ask_patterns(tool, expected):
    spec = mcp.ServerSpec(name="github", allow=["get_*", "list_*"], ask=["*secret*"])
    assert mcp.needs_approval(spec, tool) is expected


def test_tools_need_approval_when_no_allow_list():
    assert mcp.needs_approval(mcp.ServerSpec(name="imported"), "anything") is True


def test_mask_hides_secret_keys_and_values():
    masked = mcp.mask({"token": "abc", "query": "use 987654321 here", "nested": [{"api_key": "k"}]}, {"987654321"})
    assert masked == {"token": "***", "query": "use *** here", "nested": [{"api_key": "***"}]}


def test_trim_output_keeps_head_and_tail_and_saves_the_rest(tmp_path):
    text = "H" * 5000 + "M" * 5000 + "T" * 5000
    short, path = mcp.trim_output(text, tmp_path, "srv-tool")

    assert short.startswith("H" * 100) and short.endswith("T" * 100)
    assert len(short) < mcp.MAX_RESULT_CHARS + 200
    assert pathlib.Path(path).read_text(encoding="utf-8") == text


# ── live calls against the fake stdio server ───────────────────────────────

def test_lists_tools_and_calls_a_free_tool(workspace):
    write_user_servers({"fake": fake_entry()})

    names = {t.name for t in mcp.list_tools(workspace, "fake")}
    result = mcp.call_tool(workspace, "fake", "echo", {"text": "hi"})

    assert {"echo", "write_note", "slow", "big", "show_env"} <= names
    assert result.ok and result.text == "echo:hi"


def test_write_tool_is_refused_without_approval_and_runs_with_it(workspace):
    write_user_servers({"fake": fake_entry()})

    refused = mcp.call_tool(workspace, "fake", "write_note", {"text": "x"})
    asked = []
    approved = mcp.call_tool(workspace, "fake", "write_note", {"text": "x"},
                             approve=lambda spec, tool, args: asked.append((tool, args)) or True)

    assert not refused.ok and "needs your approval" in refused.text
    assert approved.ok and approved.text == "written:x"
    assert asked == [("write_note", {"text": "x"})]


def test_timeout_is_reported_and_the_server_keeps_working(workspace):
    write_user_servers({"fake": fake_entry(timeout_s=2)})

    slow = mcp.call_tool(workspace, "fake", "slow", {"seconds": 8})
    after = mcp.call_tool(workspace, "fake", "echo", {"text": "still here"})

    assert not slow.ok and "timed out" in slow.text
    assert after.ok and after.text == "echo:still here"


def test_big_result_is_trimmed_with_the_full_text_saved(workspace):
    write_user_servers({"fake": fake_entry()})

    result = mcp.call_tool(workspace, "fake", "big", {"size": 20000})

    assert result.ok
    assert "characters cut" in result.text
    assert len(pathlib.Path(result.full_output_path).read_text(encoding="utf-8")) == 20000


def test_secrets_are_masked_in_results_and_logs(workspace):
    write_user_servers({"fake": fake_entry(env={"API_TOKEN": "s3cr3t-value-123"})})

    result = mcp.call_tool(workspace, "fake", "show_env", {"name": "API_TOKEN"})
    log = (workspace / ".mitra" / "logs" / "mcp_calls.jsonl").read_text(encoding="utf-8")

    assert result.ok and result.text == "***"
    assert "s3cr3t-value-123" not in log
    assert json.loads(log.splitlines()[-1])["tool"] == "show_env"


def test_unknown_tool_and_unknown_server_fail_cleanly(workspace):
    write_user_servers({"fake": fake_entry()})

    assert "has no tool" in mcp.call_tool(workspace, "fake", "nope", {}).text
    assert "No MCP server" in mcp.call_tool(workspace, "ghost", "echo", {}).text


def test_broken_server_command_is_reported(workspace):
    write_user_servers({"broken": {"command": sys.executable, "args": ["-c", "import sys; sys.exit(3)"],
                                   "allow": ["*"], "connect_timeout_s": 10}})

    result = mcp.call_tool(workspace, "broken", "anything", {})

    assert not result.ok and "Could not start" in result.text


def test_search_finds_tools_and_formats_them(workspace):
    write_user_servers({"fake": fake_entry()})
    mcp.list_tools(workspace, "fake")  # fills the cache

    tools = mcp.search_tools(workspace, "echo text", connect_missing=False)
    text = mcp.format_search(workspace, tools)

    assert tools[0].name == "echo"
    assert "fake / echo" in text and "args: text*" in text


# ── /mcp command ────────────────────────────────────────────────────────────

def test_command_list_test_and_tools(workspace):
    write_user_servers({"fake": fake_entry()})

    listing = mcp.handle_command(workspace, "")
    tested = mcp.handle_command(workspace, "test fake")
    listing_after = mcp.handle_command(workspace, "list")

    assert "| fake | on |" in listing
    assert "✓ `fake` started" in tested and "`write_note` (asks)" in tested
    assert "| fake | on | user | 5 |" in listing_after


def test_command_on_off_writes_project_file_and_keeps_trust(workspace):
    write_user_servers({"fake": fake_entry()})

    mcp.handle_command(workspace, "off fake")
    assert not mcp.find(mcp.discover(workspace), "fake").enabled
    mcp.handle_command(workspace, "on fake")

    spec = mcp.find(mcp.discover(workspace), "fake")
    assert spec.enabled and spec.trusted


def test_command_call_counts_as_approval(workspace):
    write_user_servers({"fake": fake_entry()})

    assert mcp.handle_command(workspace, 'call fake write_note {"text": "y"}') == "written:y"


def test_import_from_claude_code_goes_to_the_user_file(workspace, tmp_path):
    (tmp_path / "claude.json").write_text(json.dumps({
        "mcpServers": {"from-user": {"command": "x"}},
        "projects": {str(workspace.resolve()): {"mcpServers": {"from-project": {"command": "y"}}}},
    }), encoding="utf-8")

    reply = mcp.handle_command(workspace, "import")
    names = {s.name for s in mcp.discover(workspace)}

    assert "Imported 2" in reply
    assert {"from-user", "from-project"} <= names
    assert not mcp.project_config_path(workspace).exists()
