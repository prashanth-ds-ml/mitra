"""Tests for the Phase 3 bounded workflow contract."""

from __future__ import annotations

import json
from types import SimpleNamespace


from app import memory, workflows
from app.main import _cmd_review


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
