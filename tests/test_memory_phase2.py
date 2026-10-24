import json
import pathlib
import sqlite3

from app import memory


def test_init_memory_creates_phase2_artifacts(tmp_path):
    created = memory.init_memory(str(tmp_path))
    normalized = {pathlib.Path(item).as_posix() for item in created}

    expected = {
        ".codemitra/activity.md",
        ".codemitra/session_log.md",
        ".codemitra/context.md",
        ".codemitra/plan.md",
        ".codemitra/brainstorm.md",
        ".codemitra/understand.md",
        ".codemitra/prd.md",
        ".codemitra/decisions.md",
        ".codemitra/errors.md",
        ".codemitra/task_board.md",
        ".codemitra/user_profile.yaml",
        ".codemitra/execution_trace.jsonl",
        ".codemitra/memory.sqlite",
        ".codemitra/README.md",
    }

    assert expected.issubset(normalized)


def test_append_activity_writes_session_log_and_trace(tmp_path):
    memory.init_memory(str(tmp_path))

    memory.append_activity(str(tmp_path), "build the api", "planned the next step")

    session_log = (tmp_path / ".codemitra" / "session_log.md").read_text(encoding="utf-8")
    trace_lines = (tmp_path / ".codemitra" / "execution_trace.jsonl").read_text(encoding="utf-8").splitlines()

    assert "build the api" in session_log
    assert trace_lines
    payload = json.loads(trace_lines[-1])
    assert payload["event_type"] == "activity"
    assert payload["payload"]["user"] == "build the api"


def test_record_last_change_set_writes_trace_event(tmp_path):
    memory.init_memory(str(tmp_path))

    memory.record_last_change_set(str(tmp_path), {"entries": [{"kind": "create_file", "path": "app.py"}]})

    trace_lines = (tmp_path / ".codemitra" / "execution_trace.jsonl").read_text(encoding="utf-8").splitlines()
    payload = json.loads(trace_lines[-1])
    assert payload["event_type"] == "change_set"
    assert payload["payload"]["entries"][0]["kind"] == "create_file"


def test_append_error_writes_markdown_and_trace(tmp_path):
    memory.init_memory(str(tmp_path))

    memory.append_error(str(tmp_path), "Command failed", "Traceback line 1")

    errors_text = (tmp_path / ".codemitra" / "errors.md").read_text(encoding="utf-8")
    trace_lines = (tmp_path / ".codemitra" / "execution_trace.jsonl").read_text(encoding="utf-8").splitlines()

    assert "Command failed" in errors_text
    payload = json.loads(trace_lines[-1])
    assert payload["event_type"] == "error"
    assert payload["payload"]["summary"] == "Command failed"


def test_append_decision_writes_markdown_and_sqlite_event(tmp_path):
    memory.init_memory(str(tmp_path))

    memory.append_decision(str(tmp_path), "Use local tools first", "The local tool layer is already stable enough.")

    decisions_text = (tmp_path / ".codemitra" / "decisions.md").read_text(encoding="utf-8")
    assert "Use local tools first" in decisions_text

    conn = sqlite3.connect(tmp_path / ".codemitra" / "memory.sqlite")
    try:
        rows = conn.execute("SELECT event_type, payload_json FROM events ORDER BY id DESC").fetchall()
    finally:
        conn.close()

    assert rows
    assert rows[0][0] == "decision"
    assert "Use local tools first" in rows[0][1]


def test_update_task_board_overwrites_board_and_traces(tmp_path):
    memory.init_memory(str(tmp_path))

    memory.update_task_board(str(tmp_path), ["Implement traces", "Verify logs"])

    board_text = (tmp_path / ".codemitra" / "task_board.md").read_text(encoding="utf-8")
    trace_lines = (tmp_path / ".codemitra" / "execution_trace.jsonl").read_text(encoding="utf-8").splitlines()

    assert "Implement traces" in board_text
    payload = json.loads(trace_lines[-1])
    assert payload["event_type"] == "task_board"
