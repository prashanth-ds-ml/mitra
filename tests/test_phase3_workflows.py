"""Tests for the Phase 3 bounded workflow contract."""

from __future__ import annotations

import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage

from app import memory, workflows
from app.agents import planner as planner_agent
from app.agents.response import AgentResponse, ToolResult
from app.agents.shell import ShellResult
from app.main import _cmd_fix, _cmd_review


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, messages):
        if not self.responses:
            raise AssertionError("No fake LLM responses left")
        return self.responses.pop(0)


def _load_trace_events(workspace: str) -> list[dict]:
    trace_path = memory._dir(workspace) / "execution_trace.jsonl"
    return [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_estimate_change_impact_counts_files_and_line_churn():
    change_set = {
        "entries": [
            {
                "kind": "create_file",
                "path": "app.py",
                "before": "print('old')\n",
                "after": "print('new')\nprint('again')\n",
            },
            {
                "kind": "move_file",
                "src": "old.py",
                "dest": "new.py",
            },
        ]
    }

    impact = workflows.estimate_change_impact(change_set)

    assert impact.files_changed == 3
    assert impact.lines_changed >= 2


def test_plan_workflow_records_state_and_trace(tmp_path):
    memory.write_plan(str(tmp_path), goal="Ship feature", steps=["Inspect app.py", "Run pytest"])

    llm = FakeLLM([
        AIMessage(content="direct"),
        AIMessage(content="Inspected app.py and identified the next change."),
    ])

    summary = planner_agent.run_plan(llm=llm, workspace=str(tmp_path), max_steps=1)
    metadata = memory.load_session_metadata(str(tmp_path))
    events = _load_trace_events(str(tmp_path))

    assert "Executed 1 step(s). 1 step(s) remaining." in summary
    assert metadata is not None
    assert metadata["workflow_execution"]["name"] == "PlanWorkflow"
    assert metadata["workflow_execution"]["status"] == "paused"
    assert metadata["workflow_execution"]["iteration"] == 1
    assert any(event["event_type"] == "workflow_started" for event in events)
    assert any(event["event_type"] == "workflow_step_finished" for event in events)
    assert any(event["event_type"] == "workflow_paused" for event in events)


def test_plan_workflow_stops_at_phase3_iteration_limit(tmp_path):
    steps = [f"Step {index}" for index in range(1, 7)]
    memory.write_plan(str(tmp_path), goal="Ship feature", steps=steps)

    responses = []
    for index in range(1, 6):
        responses.extend([
            AIMessage(content="direct"),
            AIMessage(content=f"Completed step {index}."),
        ])
    llm = FakeLLM(responses)

    summary = planner_agent.run_plan(llm=llm, workspace=str(tmp_path))
    plan = planner_agent._parse_plan(str(tmp_path))
    metadata = memory.load_session_metadata(str(tmp_path))

    assert "PlanWorkflow stopped because it reached the iteration limit (5)." in summary
    assert plan is not None
    assert len(plan.completed) == 5
    assert len(plan.pending) == 1
    assert metadata is not None
    assert metadata["workflow_execution"]["status"] == "blocked"


def test_fix_workflow_stops_on_scope_change(monkeypatch, tmp_path):
    from app import main as main_mod

    monkeypatch.setattr(main_mod.console, "print", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_mod.shell_agent, "render", lambda result: result.output)
    monkeypatch.setattr(
        main_mod.shell_agent,
        "execute",
        lambda command, cwd, console=None: ShellResult(
            command=command,
            cwd=str(tmp_path),
            exit_code=1,
            output_lines=["FAILED test_login"],
        ),
    )

    def fake_run(llm, request, console=None):
        memory.record_last_change_set(
            str(tmp_path),
            {
                "entries": [
                    {
                        "kind": "create_file",
                        "path": str(tmp_path / "app.py"),
                        "before": "",
                        "after": "\n".join(f"line {index}" for index in range(350)),
                    }
                ]
            },
        )
        return AgentResponse(
            request=request,
            steps=[ToolResult(tool="create_file", args={"path": "app.py"}, output="✓ Created file: app.py")],
            summary="Applied a large patch.",
        )

    monkeypatch.setattr(main_mod.filesystem, "run", fake_run)
    monkeypatch.setattr(main_mod, "render", lambda response: response.summary)

    reply = _cmd_fix("pytest", str(tmp_path), codegen_llm=SimpleNamespace())
    metadata = memory.load_session_metadata(str(tmp_path))

    assert "FixWorkflow stopped because the workflow changed too many lines" in reply
    assert metadata is not None
    assert metadata["workflow_execution"]["status"] == "blocked"


def test_review_workflow_records_state_and_trace(monkeypatch, tmp_path):
    from app import main as main_mod

    memory.record_last_change_set(
        str(tmp_path),
        {
            "entries": [
                {
                    "kind": "create_file",
                    "path": str(tmp_path / "app.py"),
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
    metadata = memory.load_session_metadata(str(tmp_path))
    events = _load_trace_events(str(tmp_path))

    assert "Potential issue" in reply
    assert metadata is not None
    assert metadata["workflow_execution"]["name"] == "ReviewWorkflow"
    assert metadata["workflow_execution"]["status"] == "completed"
    assert any(
        event["event_type"] == "workflow_completed"
        and event["payload"]["name"] == "ReviewWorkflow"
        for event in events
    )
