"""Tests for app/main.py — error handling, hint bar, completer, extract_command."""
import pathlib
import sys

import pytest
from types import SimpleNamespace
from rich.console import Console

# Ensure project root is importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import (
    _build_context_reply,
    _build_commit_readiness,
    _build_resources_reply,
    _cmd_resume,
    _cmd_review,
    _clear_terminal,
    _confirm_shell,
    _confirm_tool,
    _build_model_inventory_reply,
    _build_permissions_reply,
    _build_project_instructions_prompt,
    _build_skills_prompt,
    _build_skills_reply,
    _build_change_set_review_input,
    _build_change_set_diff_reply,
    _build_move_preview,
    _build_diff_preview,
    _collect_review_risk_signals,
    _build_diff_reply,
    _build_fix_usage,
    _build_git_summary,
    _build_model_reply,
    _build_mode_reply,
    _build_reasoning_reply,
    _build_startup_project_brief,
    _build_status_reply,
    _detect_project_state,
    _friendly_error,
    _handle_model_command,
    _extract_command,
    _extract_bang_command,
    _extract_fix_command,
    _parse_review_target,
    _is_bang_command,
    _normalize_session_mode,
    _pick_model,
    _resolve_codegen_model,
)
from app import memory, skills as skills_registry


def _render_rich(renderable) -> str:
    console = Console(record=True, width=120)
    console.print(renderable)
    return console.export_text()


# ── _friendly_error ───────────────────────────────────────────────────────────

class TestFriendlyError:
    def test_ollama_connection(self):
        msg = _friendly_error(Exception("connection refused by server"))
        assert "Ollama" in msg

    def test_validation_error(self):
        msg = _friendly_error(Exception("1 validation error for install_packages"))
        assert "tool" in msg.lower() or "model" in msg.lower()

    def test_list_type(self):
        msg = _friendly_error(Exception("list_type: Input should be a valid list"))
        assert "Package" in msg or "package" in msg

    def test_context_length(self):
        msg = _friendly_error(Exception("context length exceeded 32768 tokens"))
        assert "/reset" in msg

    def test_memory_pressure_hint(self):
        msg = _friendly_error(Exception("model requires more system memory (10.2 GiB) than is available (6.3 GiB)"))
        assert "/model use qwen3.5:4b" in msg and "/hibernate" not in msg

    def test_unknown_error_includes_original(self):
        msg = _friendly_error(Exception("something totally unknown happened"))
        assert "something totally unknown" in msg


# ── _extract_command ──────────────────────────────────────────────────────────

class TestExtractCommand:
    def test_backtick_extracts_command(self):
        assert _extract_command("please run `python main.py` for me") == "python main.py"

    def test_no_backtick_returns_full_string(self):
        raw = "run the snake game"
        assert _extract_command(raw) == raw

    def test_first_backtick_wins(self):
        assert _extract_command("`pytest` then `ruff`") == "pytest"

    def test_empty_string(self):
        assert _extract_command("") == ""

    def test_detects_bang_command(self):
        assert _is_bang_command("! pwd")
        assert _extract_bang_command("! pwd") == "pwd"

    def test_extract_fix_command_uses_explicit_value(self):
        assert _extract_fix_command("/fix pytest -q") == "pytest -q"

    def test_extract_fix_command_falls_back_to_last_command(self):
        assert _extract_fix_command("/fix", last_command="python -m pytest") == "python -m pytest"


# ── _SLASH_COMMANDS ───────────────────────────────────────────────────────────



# ── `/` and `@` completion (D-035) ──────────────────────────────────────────

def _completions(completer, text):
    from prompt_toolkit.document import Document
    return list(completer.get_completions(Document(text), None))


class TestCompleter:
    def _make(self, root, extra=()):
        from app.main import _COMMAND_HELP
        from app.ui.input import FileIndex, MitraCompleter
        return MitraCompleter(list(_COMMAND_HELP) + list(extra), FileIndex(str(root)))

    def test_slash_menu_lists_commands_with_descriptions(self, tmp_path):
        items = _completions(self._make(tmp_path), "/m")
        names = [c.text for c in items]
        assert "/mcp" in names and "/model" in names and "/help" not in names
        assert all(c.display_meta_text for c in items)

    def test_at_finds_workspace_files_by_name(self, tmp_path):
        (tmp_path / "snake").mkdir()
        (tmp_path / "snake" / "game.py").write_text("pass")
        (tmp_path / "utils.py").write_text("pass")
        items = _completions(self._make(tmp_path), "explain @game")
        assert [c.text for c in items] == ["@snake/game.py"]

    def test_plugin_commands_are_offered(self, tmp_path):
        items = _completions(self._make(tmp_path, [("/hello-plugin", "plugin command")]), "/hel")
        assert "/hello-plugin" in [c.text for c in items]

    def test_secrets_and_tool_folders_are_never_offered(self, tmp_path):
        (tmp_path / ".env").write_text("SECRET=1")
        (tmp_path / "key.pem").write_text("x")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "site.py").write_text("x")
        (tmp_path / "app.py").write_text("x")
        texts = [c.text for c in _completions(self._make(tmp_path), "@")]
        assert texts == ["@app.py"]

    def test_bad_workspace_does_not_raise(self):
        from app.ui.input import FileIndex
        assert FileIndex("/nonexistent/path/xyz").files() == []


class TestCloudRoutingConfig:
    def test_codegen_model_defaults_to_cloud_model(self):
        assert _resolve_codegen_model({}) == "kimi-k2.5:cloud"

    def test_codegen_model_prefers_configured_value(self):
        assert _resolve_codegen_model({"codegen_model": "gpt-oss:120b"}) == "gpt-oss:120b"




    def test_load_config_resolves_allowed_roots(self, tmp_path):
        (tmp_path / "extra").mkdir()
        (tmp_path / "codemitra.toml").write_text('allowed_roots = ["extra"]\ndisabled_tools = ["delete_file"]\ndisabled_commands = ["python"]\n', encoding="utf-8")
        from app.config import load
        cfg = load(cwd=str(tmp_path))
        assert str((tmp_path / "extra").resolve()) in cfg["allowed_roots"]
        assert "delete_file" in cfg["disabled_tools"]
        assert "python" in cfg["disabled_commands"]

    def test_project_instruction_files_loaded_from_workspace(self, tmp_path):
        from app.config import load

        (tmp_path / "AGENTS.md").write_text("Prefer small focused patches.", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("Ask before guessing.", encoding="utf-8")
        (tmp_path / ".codemitra").mkdir()
        (tmp_path / ".codemitra" / "instructions.md").write_text("Keep plans explicit.", encoding="utf-8")

        cfg = load(cwd=str(tmp_path))
        loaded = {item["path"]: item["content"] for item in cfg["project_instructions"]}

        assert loaded["AGENTS.md"] == "Prefer small focused patches."
        assert loaded["CLAUDE.md"] == "Ask before guessing."
        assert loaded[str(pathlib.Path(".codemitra") / "instructions.md")] == "Keep plans explicit."

    def test_project_instruction_files_ignore_paths_outside_workspace(self, tmp_path):
        from app.config import load

        outside = tmp_path.parent / "outside-instructions.md"
        outside.write_text("Do not load me.", encoding="utf-8")
        (tmp_path / "codemitra.toml").write_text(
            f'instruction_files = ["{outside.as_posix()}"]\n',
            encoding="utf-8",
        )

        cfg = load(cwd=str(tmp_path))

        assert cfg["project_instructions"] == []

    def test_build_project_instructions_prompt_formats_loaded_files(self):
        prompt = _build_project_instructions_prompt([
            {"path": "AGENTS.md", "content": "Prefer tests first."},
            {"path": ".codemitra/instructions.md", "content": "Keep output concise."},
        ])

        assert "Project Instructions" in prompt
        assert "### AGENTS.md" in prompt
        assert "Prefer tests first." in prompt
        assert "### .codemitra/instructions.md" in prompt
        assert "Keep output concise." in prompt

    def test_skill_dirs_config_defaults_to_workspace_skill_locations(self, tmp_path):
        from app.config import load

        cfg = load(cwd=str(tmp_path))

        assert cfg["skill_dirs"] == ["skills", ".codemitra/skills"]

    def test_instruction_files_default_includes_claude_compat(self, tmp_path):
        from app.config import load

        cfg = load(cwd=str(tmp_path))

        assert "AGENTS.md" in cfg["instruction_files"]
        assert "CLAUDE.md" in cfg["instruction_files"]

    def test_build_skills_prompt_uses_compact_index(self):
        prompt = _build_skills_prompt([
            skills_registry.Skill(
                name="repo-analyzer",
                description="Analyze repositories before editing.",
                path="skills\\01-repo-analyzer\\SKILL.md",
            )
        ])

        assert "Available CodeMitra Skills" in prompt
        assert "repo-analyzer" in prompt
        assert "read that skill's `SKILL.md`" in prompt

    def test_build_skills_reply_lists_discovered_skills(self):
        reply = _build_skills_reply([
            skills_registry.Skill(
                name="rag-pipeline",
                description="Build or review RAG pipelines.",
                path="skills\\05-rag-pipeline\\SKILL.md",
            )
        ])

        assert "CodeMitra skills" in reply
        assert "**rag-pipeline**" in reply
        assert "05-rag-pipeline" in reply
        assert "/skills show <name>" in reply

    def test_build_skills_reply_handles_empty_registry(self):
        reply = _build_skills_reply([])
        assert "No CodeMitra skills found" in reply

    def test_build_skills_reply_shows_specific_skill_body(self, tmp_path):
        skill_dir = tmp_path / "skills" / "05-rag-pipeline"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: rag-pipeline\ndescription: Build RAG.\n---\n# RAG Pipeline\n",
            encoding="utf-8",
        )
        reply = _build_skills_reply(
            [
                skills_registry.Skill(
                    name="rag-pipeline",
                    description="Build RAG.",
                    path="skills\\05-rag-pipeline\\SKILL.md",
                )
            ],
            "/skills show rag",
            workspace=str(tmp_path),
        )

        assert "## rag-pipeline" in reply
        assert "```md" in reply
        assert "# RAG Pipeline" in reply

    def test_build_skills_reply_reports_unknown_skill(self):
        reply = _build_skills_reply([], "/skills show missing")
        assert "No matching skill found" in reply

    def test_build_skills_reply_reports_usage_for_unknown_subcommand(self):
        reply = _build_skills_reply([], "/skills delete rag")
        assert "Usage: `/skills` or `/skills show <name>`" in reply






class TestTerminalSurfaceHelpers:
    def test_context_reply_reports_usage(self):
        reply = _build_context_reply(total_tokens=60000, auto_compact_threshold=120000, num_ctx=131072)
        assert "131,072" in reply
        assert "60,000" in reply
        assert "50%" in reply
        assert "/compact" in reply


    def test_permissions_reply_includes_mode_and_roots(self, monkeypatch):
        from app import main as main_module

        monkeypatch.setattr(main_module.shell_agent, "get_cwd", lambda: r"C:\Users\dev\projects\snake-game")
        reply = _build_permissions_reply(
            {
                "workspace": r"C:\Users\dev\projects",
                "allowed_roots": [r"C:\Users\dev\projects\extra"],
                "disabled_tools": ["delete_file"],
                "disabled_commands": ["python"],
            },
            "approve",
        )
        assert "`approve`" in reply
        assert "projects\\extra" in reply
        assert "`delete_file`" in reply
        assert "`python`" in reply

class TestTerminalHelpers:
    def test_clear_terminal_uses_console(self, monkeypatch):
        calls = []
        from app import main as main_module

        monkeypatch.setattr(main_module.console, "clear", lambda: calls.append("clear"))
        _clear_terminal()
        assert calls == ["clear"]




class TestSessionModes:
    def test_normalize_session_mode_falls_back_to_approve(self):
        assert _normalize_session_mode("weird") == "approve"

    def test_build_mode_reply_mentions_behavior(self):
        reply = _build_mode_reply("plan")
        assert "Current mode" in reply
        assert "Inspect and plan work" in reply

    def test_build_reasoning_reply_mentions_setting(self):
        reply = _build_reasoning_reply(False)
        assert "hidden" in reply
















class TestProjectDetection:
    def test_detect_project_state(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        (tmp_path / ".venv").mkdir()
        (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")

        state = _detect_project_state(str(tmp_path), has_memory=True, has_plan=False)

        assert state["entrypoint"] == ".\\main.py"
        assert state["venv_exists"] is True
        assert state["dependency_source"] == "pyproject.toml"
        assert state["has_memory"] is True

    def test_detect_project_state_finds_top_level_cli_entrypoint(self, tmp_path):
        package_dir = tmp_path / "snake-game"
        package_dir.mkdir()
        (package_dir / "cli.py").write_text("print('hi')", encoding="utf-8")

        state = _detect_project_state(str(tmp_path))

        assert state["entrypoint"] == ".\\snake-game\\cli.py"

    def test_build_startup_project_brief_summarizes_workspace(self, tmp_path):
        (tmp_path / "README.md").write_text("# Demo\nA sample coding assistant.\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()

        brief = _build_startup_project_brief(str(tmp_path))

        assert brief is not None
        assert "Auto-detected project brief" in brief
        assert "A sample coding assistant" in brief
        assert "pyproject.toml" in brief
        assert ".\\main.py" in brief
        assert "**Tests:** present" in brief

    def test_build_startup_project_brief_returns_none_for_empty_workspace(self, tmp_path):
        brief = _build_startup_project_brief(str(tmp_path))
        assert brief is None


class TestOperatorReplies:
    def test_build_model_reply_reports_local_only_mode(self):
        reply = _build_model_reply("qwen3.5:latest", "kimi-k2.5:cloud", cloud_codegen_enabled=False)
        assert "qwen3.5:latest" in reply
        assert "Local-only" in reply
        assert "/model list" in reply

    def test_build_model_inventory_reply_marks_active_model_and_hidden_models(self):
        from app import config

        original = config.get_gpu_memory_info
        config.get_gpu_memory_info = lambda: SimpleNamespace(total_gib=8.0, used_gib=2.5, free_gib=5.5, usage_pct=31)
        try:
            reply = _build_model_inventory_reply(
                "qwen3.5:latest",
                "kimi-k2.5:cloud",
                cloud_codegen_enabled=False,
                model_inventory=[
                    SimpleNamespace(name="qwen3.5:latest", size_text="6.6 GB", recommended=True, placement="gpu"),
                    SimpleNamespace(name="gpt-oss:20b", size_text="13 GB", recommended=False, placement="cpu"),
                ],
            )
        finally:
            config.get_gpu_memory_info = original
        assert "GPU-accelerated" in reply
        assert "qwen3.5:latest" in reply
        assert "(active)" in reply
        assert "CPU-only" in reply
        assert "gpt-oss:20b" in reply
        assert "Live GPU usage" in reply
        assert "Use `/resources`" in reply

    def test_handle_model_command_lists_models(self, monkeypatch):
        from app import config

        monkeypatch.setattr(
            config,
            "get_local_model_inventory",
            lambda **_kw: [
                SimpleNamespace(name="qwen3.5:latest", size_text="6.6 GB", recommended=True, placement="gpu"),
                SimpleNamespace(name="gpt-oss:20b", size_text="13 GB", recommended=False, placement="cpu"),
            ],
        )
        monkeypatch.setattr(config, "get_total_system_memory_gib", lambda: 23.6)
        monkeypatch.setattr(config, "get_recommended_model_budget_gib", lambda: 11.8)
        monkeypatch.setattr(config, "get_gpu_memory_info", lambda: None)
        reply = _handle_model_command(
            "/model list",
            "qwen3.5:latest",
            "kimi-k2.5:cloud",
            cloud_codegen_enabled=False,
        )
        assert "Local models" in reply
        assert "System RAM" in reply
        assert "gpt-oss:20b" in reply

    def test_build_resources_reply_reports_cpu_gpu_and_processes(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "get_cpu_usage_pct", lambda: 28.5)
        monkeypatch.setattr(config, "get_total_system_memory_gib", lambda: 23.6)
        monkeypatch.setattr(config, "get_available_system_memory_gib", lambda: 11.2)
        monkeypatch.setattr(
            config,
            "get_gpu_memory_info",
            lambda: SimpleNamespace(total_gib=8.0, used_gib=3.0, free_gib=5.0, usage_pct=38),
        )
        monkeypatch.setattr(
            config,
            "list_local_ai_processes",
            lambda: [SimpleNamespace(name="ollama.exe", pid=1234, memory_gib=2.1)],
        )
        monkeypatch.setattr(
            config,
            "list_user_gpu_processes",
            lambda: [SimpleNamespace(name="python.exe", pid=2222, memory_gib=1.0, gpu_memory_gib=1.5)],
        )
        monkeypatch.setattr(
            config,
            "list_reclaimable_processes",
            lambda: [
                SimpleNamespace(name="ollama.exe", pid=1234, memory_gib=2.1),
                SimpleNamespace(name="python.exe", pid=2222, memory_gib=1.0, gpu_memory_gib=1.5),
            ],
        )

        reply = _build_resources_reply()

        assert "CPU usage" in reply
        assert "28.5%" in reply
        assert "11.2 GB" in reply
        assert "5.0 GB free" in reply
        assert "ollama.exe" in reply
        assert "python.exe" in reply
        assert "/make-space" in reply


    def test_handle_model_command_removes_model(self, monkeypatch):
        from app import config

        monkeypatch.setattr(config, "remove_local_model", lambda name: (True, f"Removed `{name}`."))
        monkeypatch.setattr(
            config,
            "get_local_model_inventory",
            lambda **_kw: [SimpleNamespace(name="qwen3.5:latest", size_text="6.6 GB", recommended=True)],
        )
        monkeypatch.setattr(config, "get_total_system_memory_gib", lambda: 23.6)
        monkeypatch.setattr(config, "get_recommended_model_budget_gib", lambda: 11.8)
        reply = _handle_model_command(
            "/model remove gemma4:latest",
            "qwen3.5:latest",
            "kimi-k2.5:cloud",
            cloud_codegen_enabled=False,
        )
        assert "Removed `gemma4:latest`." in reply
        assert "Local models" in reply

    def test_handle_model_command_blocks_active_model_removal(self):
        reply = _handle_model_command(
            "/model remove qwen3.5:latest",
            "qwen3.5:latest",
            "kimi-k2.5:cloud",
            cloud_codegen_enabled=False,
        )
        assert "Cannot remove the active chat model" in reply


    def test_pick_model_uses_only_recommended_models(self, monkeypatch):
        from app import config
        from app import main as main_module

        monkeypatch.setattr(
            config,
            "get_local_model_inventory",
            lambda **_kw: [
                SimpleNamespace(name="gpt-oss:20b", size_text="13 GB", recommended=False, placement="cpu"),
                SimpleNamespace(name="qwen2.5-coder:7b", size_text="4.7 GB", recommended=True, placement="gpu"),
                SimpleNamespace(name="qwen3.5:4b", size_text="3.4 GB", recommended=True, placement="gpu"),
            ],
        )
        monkeypatch.setattr(config, "get_total_system_memory_gib", lambda: 23.6)
        monkeypatch.setattr(config, "get_recommended_model_budget_gib", lambda: 11.8)
        monkeypatch.setattr(config, "get_gpu_memory_info", lambda: None)
        monkeypatch.setattr(main_module.console, "input", lambda _: "1")
        monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: None)

        chosen = _pick_model({})
        assert chosen == "qwen2.5-coder:7b"

    def test_pick_model_reports_live_gpu_usage(self, monkeypatch):
        from app import config
        from app import main as main_module

        printed = []
        monkeypatch.setattr(
            config,
            "get_local_model_inventory",
            lambda **_kw: [SimpleNamespace(name="qwen3.5:latest", size_text="6.6 GB", recommended=True, placement="gpu")],
        )
        monkeypatch.setattr(config, "get_total_system_memory_gib", lambda: 23.6)
        monkeypatch.setattr(config, "get_recommended_model_budget_gib", lambda: 7.4)
        monkeypatch.setattr(
            config,
            "get_gpu_memory_info",
            lambda: SimpleNamespace(total_gib=8.0, used_gib=3.5, free_gib=4.5, usage_pct=44),
        )
        monkeypatch.setattr(main_module.console, "input", lambda _: "1")
        monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))

        chosen = _pick_model({})

        assert chosen == "qwen3.5:latest"
        joined = "\n".join(printed)
        assert "GPU 8.0 GB (4.5 free)" in joined
        assert "partly in use by another program" in joined

    def test_build_status_reply_mentions_plan_and_usage(self, monkeypatch, tmp_path):
        from app.agents import shell as shell_agent
        from app import main as main_mod
        shell_agent.configure(workspace=str(tmp_path), stream_to_console=False, confirm_fn=None)
        monkeypatch.setattr(main_mod.config, "get_cpu_usage_pct", lambda: 18.0)
        monkeypatch.setattr(main_mod.config, "get_gpu_memory_info", lambda: SimpleNamespace(total_gib=8.0, free_gib=5.0))
        monkeypatch.setattr(main_mod.config, "get_total_system_memory_gib", lambda: 23.6)
        monkeypatch.setattr(main_mod.config, "get_available_system_memory_gib", lambda: 10.5)
        memory.write_plan(str(tmp_path), goal="Ship it", steps=["Do thing", "Verify"])
        reply = _build_status_reply(
            str(tmp_path),
            "qwen3.5:latest",
            "kimi-k2.5:cloud",
            cloud_codegen_enabled=False,
            session_mode="approve",
            show_reasoning=False,
            total_tokens=400,
            auto_compact_threshold=120000,
            num_ctx=131072,
        )
        assert "Session status" in reply
        assert "Session:" in reply
        assert "0/2 done" in reply
        assert "400 tokens" in reply
        assert str(tmp_path) in reply
        assert "`ask`" in reply  # mode shown by its user-facing name
        assert "131,072" in reply
        assert "120,000" in reply
        assert "MCP:" in reply
        assert "Git:" in reply
        assert "Commit readiness:" in reply
        assert "Resources:" in reply

    def test_build_git_summary_reports_not_repo(self, monkeypatch, tmp_path):
        from app import main as main_mod

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: False)

        assert _build_git_summary(str(tmp_path)) == "Not a git repository"

    def test_build_git_summary_reports_branch_upstream_and_counts(self, monkeypatch, tmp_path):
        from app import main as main_mod

        def fake_output(workspace, args):
            joined = " ".join(args)
            if joined == "rev-parse --abbrev-ref HEAD":
                return "feature/git-status"
            if joined == "rev-parse --abbrev-ref --symbolic-full-name @{u}":
                return "origin/feature/git-status"
            if joined == "status --short":
                return "M  app.py\n M tests/test_app.py\n?? notes.md"
            return ""

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: True)
        monkeypatch.setattr(main_mod, "_git_output", fake_output)

        summary = _build_git_summary(str(tmp_path))

        assert "`feature/git-status`" in summary
        assert "upstream `origin/feature/git-status`" in summary
        assert "1 staged" in summary
        assert "1 unstaged" in summary
        assert "1 untracked" in summary

    def test_build_commit_readiness_reports_clean_tree(self, monkeypatch, tmp_path):
        from app import main as main_mod

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: True)
        monkeypatch.setattr(main_mod, "_git_output", lambda workspace, args: "")

        assert _build_commit_readiness(str(tmp_path)) == "Clean working tree; nothing to commit"

    def test_build_commit_readiness_reports_no_staged_changes(self, monkeypatch, tmp_path):
        from app import main as main_mod

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: True)
        monkeypatch.setattr(main_mod, "_git_output", lambda workspace, args: " M app.py\n?? notes.md")

        assert _build_commit_readiness(str(tmp_path)) == "Not ready: no staged changes (2 unstaged/untracked)"

    def test_build_commit_readiness_reports_ready_staged_changes(self, monkeypatch, tmp_path):
        from app import main as main_mod

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: True)
        monkeypatch.setattr(main_mod, "_git_output", lambda workspace, args: "M  app.py\nA  tests/test_app.py")

        assert _build_commit_readiness(str(tmp_path)) == "Ready: 2 staged changes"

    def test_build_commit_readiness_reports_partial_commit(self, monkeypatch, tmp_path):
        from app import main as main_mod

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: True)
        monkeypatch.setattr(main_mod, "_git_output", lambda workspace, args: "M  app.py\n M app.py\n?? notes.md")

        assert _build_commit_readiness(str(tmp_path)) == "Partially ready: 1 staged, 1 unstaged and 1 untracked outside the commit"


    def test_build_change_set_diff_reply_uses_recorded_change(self, tmp_path):
        memory.record_last_change_set(
            str(tmp_path),
            {
                "entries": [
                    {
                        "kind": "create_file",
                        "path": str(tmp_path / "app.py"),
                        "existed": True,
                        "before": "print('old')\n",
                        "after": "print('new')\n",
                    }
                ]
            },
        )
        reply = _build_change_set_diff_reply(str(tmp_path))
        assert "Last CodeMitra change set" in reply
        assert "print('old')" in reply
        assert "print('new')" in reply

    def test_build_change_set_review_input_uses_recorded_change(self, tmp_path):
        memory.record_last_change_set(
            str(tmp_path),
            {
                "entries": [
                    {
                        "kind": "create_file",
                        "path": str(tmp_path / "app.py"),
                        "existed": True,
                        "before": "print('old')\n",
                        "after": "print('new')\n",
                    }
                ]
            },
        )
        review_input = _build_change_set_review_input(str(tmp_path))
        assert review_input is not None
        assert "Last CodeMitra change set" in review_input
        assert "print('old')" in review_input
        assert "print('new')" in review_input

    def test_collect_review_risk_signals_detects_incomplete_markers(self):
        review_input = "Diff:\n+def run():\n+    # TODO: handle failures\n+    pass\n"
        signals = _collect_review_risk_signals(review_input)
        assert any("TODO markers" in signal for signal in signals)
        assert any("`pass` statements" in signal for signal in signals)

    def test_build_diff_reply_without_git_or_changes_reports_empty(self, tmp_path):
        reply = _build_diff_reply(str(tmp_path))
        assert "No diff is available yet." in reply

    def test_cmd_review_without_changes_reports_empty(self, tmp_path):
        reply = _cmd_review(str(tmp_path), SimpleNamespace())
        assert "Nothing to review yet" in reply

    def test_cmd_review_uses_change_set_when_available(self, monkeypatch, tmp_path):
        from app import main as main_mod

        memory.record_last_change_set(
            str(tmp_path),
            {
                "entries": [
                    {
                        "kind": "create_file",
                        "path": str(tmp_path / "app.py"),
                        "existed": True,
                        "before": "print('old')\n",
                        "after": "print('new')\n",
                    }
                ]
            },
        )

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: False)
        monkeypatch.setattr(main_mod.console, "print", lambda *args, **kwargs: None)

        class FakeReviewLLM:
            def invoke(self, messages):
                return SimpleNamespace(content="Potential issue in app.py.")

        reply = _cmd_review(str(tmp_path), FakeReviewLLM())
        assert "Potential issue" in reply

    def test_cmd_review_appends_auto_risk_signals_when_model_reports_clean(self, monkeypatch, tmp_path):
        from app import main as main_mod

        memory.record_last_change_set(
            str(tmp_path),
            {
                "entries": [
                    {
                        "kind": "create_file",
                        "path": str(tmp_path / "app.py"),
                        "existed": True,
                        "before": "def run():\n    return 1\n",
                        "after": "def run():\n    # TODO: validate input\n    return 1\n",
                    }
                ]
            },
        )

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: False)
        monkeypatch.setattr(main_mod.console, "print", lambda *args, **kwargs: None)

        class FakeReviewLLM:
            def invoke(self, messages):
                return SimpleNamespace(content="No material issues found.")

        reply = _cmd_review(str(tmp_path), FakeReviewLLM())
        assert "Auto-detected risk signals" in reply
        assert "TODO markers" in reply

    def test_parse_review_target_defaults_to_working(self):
        assert _parse_review_target("/review") == "working"

    def test_parse_review_target_supports_staged(self):
        assert _parse_review_target("/review staged") == "staged"

    def test_cmd_review_supports_staged_git_review(self, monkeypatch, tmp_path):
        from app import main as main_mod

        monkeypatch.setattr(main_mod, "_is_git_repo", lambda workspace: True)
        monkeypatch.setattr(
            main_mod,
            "_build_git_review_input",
            lambda workspace, staged: ("staged git diff", "Git status:\nM app.py\n\nDiff:\n+change") if staged else None,
        )
        monkeypatch.setattr(main_mod.console, "print", lambda *args, **kwargs: None)

        class FakeReviewLLM:
            def invoke(self, messages):
                return SimpleNamespace(content="Review found no blocking issues.")

        reply = _cmd_review(str(tmp_path), FakeReviewLLM(), target="staged")
        assert "no blocking issues" in reply.lower()

    def test_cmd_resume_summarizes_session(self, monkeypatch, tmp_path):
        from app import main as main_mod

        memory.append_activity(str(tmp_path), "first ask", "first reply")
        monkeypatch.setattr(main_mod.console, "print", lambda *args, **kwargs: None)

        reply = _cmd_resume(str(tmp_path))
        assert "Session resume" in reply
        assert str(tmp_path) in reply
        assert "first ask" in reply


    def test_build_fix_usage_mentions_last_command(self):
        reply = _build_fix_usage("pytest -q")
        assert "/fix pytest -q" in reply

    def test_build_move_preview_mentions_scope(self, tmp_path):
        src = tmp_path / "snake-agent"
        src.mkdir()
        preview = _build_move_preview(str(src), str(tmp_path / "snake-game"))
        assert "Source type: folder" in preview
        assert "Imports and package names stay unchanged" in preview

    def test_build_move_preview_reports_missing_source(self, tmp_path):
        preview = _build_move_preview(str(tmp_path / "missing"), str(tmp_path / "snake-game"))
        assert "Source path: not found" in preview





class TestApprovalMenus:
    def test_confirm_shell_can_trust_command_in_directory(self, monkeypatch, tmp_path):
        from app import main as main_mod
        from app.agents import shell as shell_agent

        shell_agent.configure(workspace=str(tmp_path), stream_to_console=False, confirm_fn=None)
        monkeypatch.setattr(main_mod, "_choose_approval_option", lambda *args, **kwargs: "trust")

        assert _confirm_shell("pytest tests\\test_main_ux.py", str(tmp_path)) == "pytest tests\\test_main_ux.py"
        assert memory.is_shell_command_trusted(str(tmp_path), str(tmp_path), "pytest") is True

    def test_confirm_shell_skips_menu_for_trusted_command(self, monkeypatch, tmp_path):
        from app import main as main_mod
        from app.agents import shell as shell_agent

        shell_agent.configure(workspace=str(tmp_path), stream_to_console=False, confirm_fn=None)
        memory.trust_shell_command(str(tmp_path), str(tmp_path), "pytest")
        monkeypatch.setattr(
            main_mod,
            "_choose_approval_option",
            lambda *args, **kwargs: pytest.fail("trusted command should bypass chooser"),
        )

        assert _confirm_shell("pytest -q", str(tmp_path)) == "pytest -q"

    def test_confirm_tool_uses_chooser_result(self, monkeypatch, tmp_path):
        from app import main as main_mod

        target = tmp_path / "app.py"
        target.write_text("print('old')\n", encoding="utf-8")
        monkeypatch.setattr(main_mod, "_choose_approval_option", lambda *args, **kwargs: "approve")

        assert _confirm_tool("create_file", {"path": str(target), "content": "print('new')\n"}) is True

    def test_confirm_tool_edit_file_shows_diff_preview(self, monkeypatch, tmp_path):
        from app import main as main_mod

        target = tmp_path / "app.py"
        target.write_text("print('old')\n", encoding="utf-8")
        captured = {}

        def fake_choose(title, prompt, options, fallback_default=None):
            captured["title"] = title
            captured["prompt"] = prompt
            return "deny"

        monkeypatch.setattr(main_mod, "_choose_approval_option", fake_choose)
        monkeypatch.setattr(main_mod, "_print_approval_result", lambda *args, **kwargs: None)

        assert _confirm_tool("edit_file", {"path": str(target), "content": "print('new')\n"}) is False
        assert captured["title"] == "File diff preview"
        assert "--- current\\app.py" in captured["prompt"]
        assert "+++ new\\app.py" in captured["prompt"]
        assert "Change scope: +1 / -1 lines." in captured["prompt"]


class TestDiffPreview:
    def test_build_diff_preview_shows_before_and_after_lines(self, tmp_path):
        target = tmp_path / "app.py"
        target.write_text("print('old')\n", encoding="utf-8")

        preview = _build_diff_preview(str(target), "print('new')\n")

        assert "--- current\\app.py" in preview
        assert "+++ new\\app.py" in preview
        assert "-print('old')" in preview
        assert "+print('new')" in preview

    def test_build_diff_preview_truncates_long_output(self, tmp_path):
        target = tmp_path / "big.py"
        target.write_text("\n".join(f"old_{i}" for i in range(80)), encoding="utf-8")

        preview = _build_diff_preview(
            str(target),
            "\n".join(f"new_{i}" for i in range(80)),
            max_lines=12,
        )

        assert "more lines omitted" in preview


# ── Questions never start a plan or a build (E-019) ──────────────────────────



class TestWorkspaceNameIsNotNested:
    def test_path_starting_with_the_workspace_name_is_not_nested(self, tmp_path):
        from app.agents import filesystem
        ws = tmp_path / "codemitra-playground"
        ws.mkdir()
        filesystem.configure(workspace=str(ws), confirm_fn=None)
        try:
            resolved = filesystem._resolve_path("codemitra-playground/levels/01-snake/plan.md")
            assert resolved == (ws / "levels" / "01-snake" / "plan.md").resolve()
            (ws / "docs").mkdir()
            assert filesystem._resolve_path("docs/a.md") == (ws / "docs" / "a.md").resolve()
        finally:
            filesystem.configure(workspace=None, confirm_fn=None)

    def test_a_real_subfolder_with_the_same_name_is_kept(self, tmp_path):
        from app.agents import filesystem
        ws = tmp_path / "app"
        (ws / "app").mkdir(parents=True)
        filesystem.configure(workspace=str(ws), confirm_fn=None)
        try:
            assert filesystem._resolve_path("app/main.py") == (ws / "app" / "main.py").resolve()
        finally:
            filesystem.configure(workspace=None, confirm_fn=None)


# ── Replies never point to commands that no longer exist (E-020) ─────────────

def test_no_text_mentions_removed_commands():
    import re as _re
    removed = ["/next", "/start", "/build", "/brainstorm", "/understand", "/prd", "/playbook",
               "/hibernate", "/tasks", "/search", "/permissions", "/thinking", "/reset"]
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    hits = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for cmd in removed:
            for m in _re.finditer(rf"`{_re.escape(cmd)}(?:\s[^`]*)?`", text):
                hits.append(f"{path.name}: {m.group(0)}")
    assert hits == []




# ── The leading verb decides the route (E-022) ───────────────────────────────





def test_mode_names_match_shift_tab():
    from app.main import _build_mode_reply, _is_known_mode, _normalize_session_mode
    assert _normalize_session_mode("ask") == "approve" and _normalize_session_mode("auto-edit") == "auto"
    assert _is_known_mode("plan") and _is_known_mode("approve") and not _is_known_mode("yolo")
    assert "`ask`" in _build_mode_reply("approve") and "`auto-edit`" in _build_mode_reply("auto")


def test_context_use_is_the_latest_prompt_not_the_sum_of_calls():
    """E-025: compaction fired at 193,304 'tokens' on a 64K model; every call resends the whole history."""
    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "if ctx_used >= auto_compact_threshold" in src
    assert "if sess_in + sess_out >= auto_compact_threshold" not in src
    assert "total_tokens=ctx_used,          # E-025" in src and "context_limit=num_ctx," in src


def test_fix_runs_the_core_loop(tmp_path, monkeypatch):
    """/fix <command> = the core loop until the command passes (M1 stage 2)."""
    from app import main as main_mod
    from app.core.loop import RunResult

    seen = {}

    def fake_solve(task, ws, llm, **kw):
        seen["task"], seen["test"] = task, ws.test_command
        ws.journal.append({"kind": "create_file", "path": str(tmp_path / "a.py"), "existed": False,
                           "before": None, "after": "x"})
        return RunResult(status="passed", summary="fixed the import")

    monkeypatch.setattr("app.core.loop.solve", fake_solve)
    reply = main_mod._cmd_fix("pytest -q", str(tmp_path), object())
    assert seen["test"] == "pytest -q" and "pytest -q" in seen["task"]
    assert reply.startswith("`pytest -q`: fixed.")
    from app import memory
    assert memory.load_last_change_set(str(tmp_path))["entries"][0]["path"].endswith("a.py")
