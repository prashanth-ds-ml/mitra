"""Tests for app/agents/filesystem.py — PermissionGuard, destructive confirm, tools."""
import pathlib
from types import SimpleNamespace
import pytest
from app.agents import filesystem


@pytest.fixture(autouse=True)
def reset_guard(tmp_path):
    """Reset filesystem guard to a clean state before each test."""
    filesystem.configure(workspace=str(tmp_path), confirm_fn=None)
    yield
    filesystem.configure(workspace=None, confirm_fn=None)


# ── PermissionGuard.check_path ────────────────────────────────────────────────

class TestCheckPath:
    def test_path_inside_workspace_allowed(self, tmp_path):
        guard = filesystem.PermissionGuard(workspace=str(tmp_path))
        assert guard.check_path(str(tmp_path / "foo.py")) is None

    def test_path_outside_workspace_denied(self, tmp_path):
        guard = filesystem.PermissionGuard(workspace=str(tmp_path))
        err = guard.check_path("/etc/passwd")
        assert err is not None
        assert "Permission denied" in err

    def test_no_workspace_denies_instead_of_allowing(self, tmp_path):
        """E-003: fail closed; without a workspace nothing keeps the model inside the project."""
        guard = filesystem.PermissionGuard(workspace=None)
        err = guard.check_path("/etc/passwd")
        assert err is not None and "no workspace is set" in err

    def test_allowed_root_permits_extra_path(self, tmp_path):
        extra = tmp_path.parent / "shared"
        extra.mkdir(exist_ok=True)
        guard = filesystem.PermissionGuard(workspace=str(tmp_path), allowed_roots=[str(extra)])
        assert guard.check_path(str(extra / "notes.txt")) is None


# ── Destructive tools in _DEFAULT_TOOLS ──────────────────────────────────────

class TestDefaultTools:
    def test_all_destructive_tools_in_defaults(self):
        missing = filesystem._DESTRUCTIVE_TOOLS - filesystem._DEFAULT_TOOLS
        assert missing == set(), f"Missing from _DEFAULT_TOOLS: {missing}"


# ── confirm_fn for destructive tools ─────────────────────────────────────────

class TestDestructiveConfirm:
    def test_denied_skips_delete(self, tmp_path):
        target = tmp_path / "todelete.txt"
        target.write_text("hello")
        filesystem.configure(workspace=str(tmp_path), confirm_fn=lambda tool, args: False)
        result = filesystem.delete_file.invoke({"path": str(target)})
        assert "Skipped" in result
        assert target.exists()  # file must still be there

    def test_approved_deletes_file(self, tmp_path):
        target = tmp_path / "todelete.txt"
        target.write_text("hello")
        filesystem.configure(workspace=str(tmp_path), confirm_fn=lambda tool, args: True)
        result = filesystem.delete_file.invoke({"path": str(target)})
        assert "✓" in result
        assert not target.exists()

    def test_non_destructive_tools_skip_confirm(self, tmp_path):
        called = []
        filesystem.configure(
            workspace=str(tmp_path),
            confirm_fn=lambda tool, args: called.append(tool) or True,
        )
        # create_file is not destructive — confirm_fn should NOT be called by the guard
        # (it's called inside the agent loop, not inside the tool itself)
        p = str(tmp_path / "new.py")
        filesystem.create_file.invoke({"path": p, "content": ""})
        # confirm_fn not invoked at the tool level for non-destructive tools
        assert called == []


# ── create_file tool ──────────────────────────────────────────────────────────

class TestCreateFile:
    def test_creates_file_with_content(self, tmp_path):
        p = tmp_path / "hello.py"
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.create_file.invoke({"path": str(p), "content": "print('hi')"})
        assert "✓" in result
        assert p.read_text() == "print('hi')"

    def test_creates_parent_directories(self, tmp_path):
        p = tmp_path / "src" / "utils" / "helpers.py"
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.create_file.invoke({"path": str(p), "content": ""})
        assert "✓" in result
        assert p.exists()

    def test_unchanged_file_reports_without_rewriting(self, tmp_path):
        p = tmp_path / "hello.py"
        p.write_text("print('hi')", encoding="utf-8")
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.create_file.invoke({"path": str(p), "content": "print('hi')"})
        assert "unchanged" in result.lower()

    def test_blocks_secret_like_paths(self, tmp_path):
        target = tmp_path / ".env"
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.create_file.invoke({"path": str(target), "content": "API_KEY=secret"})
        assert "Permission denied" in result


class TestEditFile:
    def test_updates_existing_file(self, tmp_path):
        target = tmp_path / "app.py"
        target.write_text("print('old')\n", encoding="utf-8")
        filesystem.configure(workspace=str(tmp_path))

        result = filesystem.edit_file.invoke({"path": str(target), "content": "print('new')\n"})

        assert "Updated file" in result
        assert target.read_text(encoding="utf-8") == "print('new')\n"

    def test_requires_existing_file(self, tmp_path):
        target = tmp_path / "missing.py"
        filesystem.configure(workspace=str(tmp_path))

        result = filesystem.edit_file.invoke({"path": str(target), "content": "print('new')\n"})

        assert "does not exist" in result


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        if not self.responses:
            raise AssertionError("No fake LLM responses left")
        return self.responses.pop(0)




# ── list_directory tool ───────────────────────────────────────────────────────

class TestListDirectory:
    def test_lists_files_and_dirs(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "subdir").mkdir()
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.list_directory.invoke({"path": str(tmp_path)})
        assert "a.py" in result
        assert "subdir" in result

    def test_empty_directory(self, tmp_path):
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.list_directory.invoke({"path": str(tmp_path)})
        assert "empty" in result.lower()

    def test_broken_entry_does_not_crash(self, tmp_path, monkeypatch):
        target = tmp_path / "ghost.txt"
        target.write_text("hello", encoding="utf-8")
        original_is_file = pathlib.Path.is_file

        def flaky_is_file(path_obj):
            if path_obj == target:
                raise FileNotFoundError("broken junction target")
            return original_is_file(path_obj)

        monkeypatch.setattr(pathlib.Path, "is_file", flaky_is_file)
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.list_directory.invoke({"path": str(tmp_path)})
        assert "ghost.txt" in result

    def test_relative_dot_uses_workspace_not_process_cwd(self, tmp_path, monkeypatch):
        (tmp_path / "inside.txt").write_text("hello", encoding="utf-8")
        monkeypatch.chdir(tmp_path.parent)
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.list_directory.invoke({"path": "."})
        assert "inside.txt" in result

    def test_lists_locally_without_starting_an_mcp_server(self, tmp_path, monkeypatch):
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        monkeypatch.setattr(filesystem.mcp_registry, "call_tool", lambda *a, **k: pytest.fail("MCP was called"))

        result = filesystem.list_directory.invoke({"path": str(tmp_path)})

        assert "a.txt" in result


class TestReadFile:
    def test_reads_locally_without_starting_an_mcp_server(self, tmp_path, monkeypatch):
        target = tmp_path / "note.txt"
        target.write_text("local content", encoding="utf-8")
        monkeypatch.setattr(filesystem.mcp_registry, "call_tool", lambda *a, **k: pytest.fail("MCP was called"))

        result = filesystem.read_file.invoke({"path": str(target)})

        assert result == "local content"


class TestMcpTools:
    def test_mcp_call_asks_through_confirm_fn(self, tmp_path, monkeypatch):
        asked = {}

        def confirm(tool_name, args):
            asked["tool_name"], asked["args"] = tool_name, args
            return False

        def fake_call_tool(workspace, server, tool, arguments, approve=None):
            approved = approve(None, tool, arguments)
            return SimpleNamespace(text=f"approved={approved}")

        filesystem.configure(workspace=str(tmp_path), confirm_fn=confirm)
        monkeypatch.setattr(filesystem.mcp_registry, "call_tool", fake_call_tool)

        result = filesystem.mcp_call.invoke({"server": "github", "tool": "create_issue", "arguments": '{"title": "t"}'})

        assert result == "approved=False"
        assert asked["tool_name"] == "mcp_call"
        assert asked["args"] == {"server": "github", "tool": "create_issue", "arguments": {"title": "t"}}

    def test_mcp_call_without_confirm_fn_never_approves(self, tmp_path, monkeypatch):
        def fake_call_tool(workspace, server, tool, arguments, approve=None):
            return SimpleNamespace(text=f"approved={approve(None, tool, arguments)}")

        monkeypatch.setattr(filesystem.mcp_registry, "call_tool", fake_call_tool)

        assert filesystem.mcp_call.invoke({"server": "s", "tool": "t", "arguments": {}}) == "approved=False"

    def test_mcp_call_rejects_bad_json(self):
        result = filesystem.mcp_call.invoke({"server": "s", "tool": "t", "arguments": "{not json"})
        assert result.startswith("✗ arguments must be a JSON object")

    def test_mcp_tools_are_on_by_default(self):
        assert {"mcp_find", "mcp_call"} <= filesystem._DEFAULT_TOOLS


class TestSearchText:
    def test_finds_matches_in_workspace_files(self, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("alpha\nfind me\nomega\n", encoding="utf-8")
        filesystem.configure(workspace=str(tmp_path))

        result = filesystem.search_text.invoke({"pattern": "find me", "path": str(tmp_path)})

        assert "notes.txt:2: find me" in result

    def test_skips_secret_like_files(self, tmp_path):
        target = tmp_path / ".env"
        target.write_text("API_KEY=find me\n", encoding="utf-8")
        filesystem.configure(workspace=str(tmp_path))

        result = filesystem.search_text.invoke({"pattern": "find me", "path": str(tmp_path)})

        assert "No matches found" in result


class TestMoveFile:
    def test_missing_source_reports_clear_error(self, tmp_path):
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.move_file.invoke(
            {"src": str(tmp_path / "missing"), "dest": str(tmp_path / "renamed")}
        )
        assert "source does not exist" in result

    def test_existing_destination_reports_clear_error(self, tmp_path):
        src = tmp_path / "snake-agent"
        dest = tmp_path / "snake-game"
        src.mkdir()
        dest.mkdir()
        filesystem.configure(workspace=str(tmp_path))
        result = filesystem.move_file.invoke({"src": str(src), "dest": str(dest)})
        assert "destination already exists" in result









class TestMarkdownTools:
    def test_create_markdown_file_requires_md_suffix(self, tmp_path):
        filesystem.configure(workspace=str(tmp_path))

        result = filesystem.create_markdown_file.invoke({"path": str(tmp_path / "README.txt"), "content": "# Hello"})

        assert "must end with .md" in result

    def test_create_and_update_markdown_file(self, tmp_path):
        target = tmp_path / "README.md"
        filesystem.configure(workspace=str(tmp_path))

        create_result = filesystem.create_markdown_file.invoke({"path": str(target), "content": "# Hello\n"})
        update_result = filesystem.update_markdown_file.invoke({"path": str(target), "content": "# Updated\n"})

        assert "Created file" in create_result
        assert "Updated file" in update_result
        assert target.read_text(encoding="utf-8") == "# Updated\n"


# ── Bad tool arguments never crash a turn (E-018) ─────────────────────────────

