"""Workflow-style regression tests for Mitra."""


from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app import memory
from app.agents import shell as shell_agent
from app.main import (
    _build_startup_project_brief,
    _confirm_shell,
    _compact,
)


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        if not self.responses:
            raise AssertionError("No fake LLM responses left")
        return self.responses.pop(0)


class CapturingSummaryLLM:
    def __init__(self, summary: str):
        self.summary = summary
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.summary)




class TestStartupUnderstandingWorkflow:
    def test_startup_brief_captures_project_shape(self, tmp_path):
        (tmp_path / "README.md").write_text("# Demo\nAn offline coding assistant.\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()

        brief = _build_startup_project_brief(str(tmp_path))

        assert brief is not None
        assert "offline coding assistant" in brief.lower()
        assert ".\\main.py" in brief
        assert "pyproject.toml" in brief
        assert "**Tests:** present" in brief




class TestSessionRecoveryWorkflow:
    def test_compact_replaces_history_with_summary_context(self):
        llm = CapturingSummaryLLM("Summary with app.py, pytest failure, and next step.")
        messages = [
            SystemMessage(content="SYSTEM"),
            HumanMessage(content="Open app.py and inspect the failing test output."),
            AIMessage(content="I found a pytest failure in tests/test_api.py."),
            HumanMessage(content="Patch app.py and keep the undo path."),
        ]

        compacted = _compact(llm, messages, "SYSTEM")

        assert len(llm.calls) == 1
        compact_prompt = llm.calls[0][0].content
        assert "Open app.py and inspect the failing test output." in compact_prompt
        assert "I found a pytest failure in tests/test_api.py." in compact_prompt
        assert "Patch app.py and keep the undo path." in compact_prompt
        assert len(compacted) == 2
        assert isinstance(compacted[0], SystemMessage)
        assert compacted[0].content == "SYSTEM"
        assert isinstance(compacted[1], HumanMessage)
        assert "[Compacted context from previous turns]" in compacted[1].content
        assert "Summary with app.py, pytest failure, and next step." in compacted[1].content

    def test_compact_records_session_checkpoint_when_workspace_is_available(self, tmp_path):
        llm = CapturingSummaryLLM("Summary with next action preserved.")
        messages = [
            SystemMessage(content="SYSTEM"),
            HumanMessage(content="Inspect app.py."),
            AIMessage(content="Found the relevant function."),
        ]

        _compact(
            llm,
            messages,
            "SYSTEM",
            workspace=str(tmp_path),
            reason="manual",
            total_tokens=42000,
        )

        metadata = memory.load_session_metadata(str(tmp_path))
        assert metadata is not None
        assert metadata["last_compaction"]["reason"] == "manual"
        assert metadata["last_compaction"]["summary"] == "Summary with next action preserved."
        assert metadata["last_compaction"]["turns_compacted"] == 2
        assert metadata["last_compaction"]["usage_tokens_before"] == 42000














class TestSafetyApprovalWorkflow:
    def test_trusted_shell_command_runs_once_with_prompt_then_bypasses_menu(self, monkeypatch, tmp_path):
        from app import main as main_mod

        chooser_calls = {"count": 0}

        def fake_choose(*args, **kwargs):
            chooser_calls["count"] += 1
            return "trust"

        monkeypatch.setattr(main_mod, "_choose_approval_option", fake_choose)
        monkeypatch.setattr(main_mod, "_print_approval_result", lambda *args, **kwargs: None)

        shell_agent.configure(
            workspace=str(tmp_path),
            stream_to_console=False,
            confirm_fn=_confirm_shell,
        )

        first = shell_agent.execute("python --version", cwd=str(tmp_path))
        second = shell_agent.execute("python --version", cwd=str(tmp_path))

        assert first.ok
        assert second.ok
        assert chooser_calls["count"] == 1
        assert memory.is_shell_command_trusted(str(tmp_path), str(tmp_path), "python") is True


    def test_read_only_mode_blocks_shell_but_keeps_safe_builtins_available(self, tmp_path):
        nested = tmp_path / "pkg"
        nested.mkdir()
        (nested / "module.py").write_text("print('hi')\n", encoding="utf-8")

        shell_agent.configure(
            workspace=str(tmp_path),
            session_mode="read-only",
            stream_to_console=False,
            confirm_fn=None,
        )

        blocked = shell_agent.execute("python --version", cwd=str(tmp_path))
        allowed = shell_agent.execute("ls", cwd=str(tmp_path))

        assert not blocked.ok
        assert "disabled in `read-only` mode" in blocked.output
        assert allowed.ok
        assert "pkg" in allowed.output
