"""Tests for the LangGraph-backed fix workflow."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app import langgraph_workflows
from app.agents.shell import ShellResult


def _silent_console():
    return SimpleNamespace(print=lambda *args, **kwargs: None)


def test_fix_workflow_graph_succeeds_after_one_repair(monkeypatch, tmp_path):
    shell_results = [
        ShellResult(command="pytest", cwd=str(tmp_path), exit_code=1, output_lines=["FAILED test_login"]),
        ShellResult(command="pytest", cwd=str(tmp_path), exit_code=0, output_lines=["12 passed"]),
    ]
    filesystem_calls = {"count": 0}

    monkeypatch.setattr(
        langgraph_workflows.shell_agent,
        "execute",
        lambda command, cwd, console=None: shell_results.pop(0),
    )
    monkeypatch.setattr(langgraph_workflows.shell_agent, "render", lambda result: result.output)

    def fake_run(_llm, _request, console=None):
        filesystem_calls["count"] += 1
        return SimpleNamespace(
            summary="patched",
            steps=[SimpleNamespace(tool="create_file", ok=True)],
        )

    monkeypatch.setattr(langgraph_workflows.filesystem, "run", fake_run)
    monkeypatch.setattr(langgraph_workflows, "render", lambda response: response.summary)
    monkeypatch.setattr(
        langgraph_workflows.memory,
        "load_last_change_set",
        lambda workspace: {"recorded_at": datetime.now().isoformat(timespec="seconds"), "entries": []},
    )

    reply = langgraph_workflows.run_fix_workflow(
        "pytest",
        str(tmp_path),
        SimpleNamespace(),
        console=_silent_console(),
        max_attempts=3,
    )

    assert reply == "Fixed after 1 repair attempt. `pytest` now passes."
    assert filesystem_calls["count"] == 1


def test_fix_workflow_graph_stops_when_repair_makes_no_changes(monkeypatch, tmp_path):
    shell_results = [
        ShellResult(command="pytest", cwd=str(tmp_path), exit_code=1, output_lines=["FAILED test_login"]),
    ]
    filesystem_calls = {"count": 0}

    monkeypatch.setattr(
        langgraph_workflows.shell_agent,
        "execute",
        lambda command, cwd, console=None: shell_results.pop(0),
    )
    monkeypatch.setattr(langgraph_workflows.shell_agent, "render", lambda result: result.output)

    def fake_run(_llm, _request, console=None):
        filesystem_calls["count"] += 1
        return SimpleNamespace(summary="no edits", steps=[])

    monkeypatch.setattr(langgraph_workflows.filesystem, "run", fake_run)
    monkeypatch.setattr(langgraph_workflows, "render", lambda response: response.summary)

    reply = langgraph_workflows.run_fix_workflow(
        "pytest",
        str(tmp_path),
        SimpleNamespace(),
        console=_silent_console(),
        max_attempts=3,
    )

    assert "Repair stopped after attempt 1 because no code changes were applied." in reply
    assert filesystem_calls["count"] == 1


def test_fix_workflow_graph_stops_after_max_attempts(monkeypatch, tmp_path):
    shell_results = [
        ShellResult(command="pytest", cwd=str(tmp_path), exit_code=1, output_lines=["FAILED first run"]),
        ShellResult(command="pytest", cwd=str(tmp_path), exit_code=1, output_lines=["FAILED final run"]),
    ]
    filesystem_calls = {"count": 0}

    monkeypatch.setattr(
        langgraph_workflows.shell_agent,
        "execute",
        lambda command, cwd, console=None: shell_results.pop(0),
    )
    monkeypatch.setattr(langgraph_workflows.shell_agent, "render", lambda result: result.output)
    monkeypatch.setattr(
        langgraph_workflows.filesystem,
        "run",
        lambda _llm, _request, console=None: filesystem_calls.__setitem__("count", filesystem_calls["count"] + 1)
        or SimpleNamespace(summary="patched", steps=[SimpleNamespace(tool="create_file", ok=True)]),
    )
    monkeypatch.setattr(langgraph_workflows, "render", lambda response: response.summary)
    monkeypatch.setattr(
        langgraph_workflows.memory,
        "load_last_change_set",
        lambda workspace: {"recorded_at": datetime.now().isoformat(timespec="seconds"), "entries": []},
    )

    reply = langgraph_workflows.run_fix_workflow(
        "pytest",
        str(tmp_path),
        SimpleNamespace(),
        console=_silent_console(),
        max_attempts=2,
    )

    assert "Repair stopped after 2 attempts. `pytest` is still failing." in reply
    assert filesystem_calls["count"] == 1
