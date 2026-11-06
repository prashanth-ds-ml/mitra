"""Run analyzer + dashboard (self-improvement step 2)."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core import analyze as A
from app.core import dashboard as D


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def chat_session():
    cmd = {"command": "cd brick-breaker && pytest"}
    rows = [{"kind": "turn_start", "turn": 1, "harness_version": 0},
            {"kind": "tool", "turn": 1, "name": "write_file", "args": {"path": "game.py"}, "ok": True,
             "output": "Wrote game.py\n⚠ game.py is not valid Python: line 3"}]
    rows += [{"kind": "model", "turn": 1, "tokens_in": 1000},
             {"kind": "tool", "turn": 1, "name": "run_command", "args": cmd, "ok": False,
              "output": "exit 1: no tests ran"}] * 4
    rows += [{"kind": "tool", "turn": 1, "name": "run_command", "args": cmd, "ok": False,
              "output": "✗ Not run: run_command was already called with these exact arguments"},
             {"kind": "stopped", "turn": 1, "reason": "Stopped: 4 failures in a row"},
             {"kind": "turn_end", "turn": 1, "reason": "Stopped: 4 failures in a row", "text": "", "seconds": 60},
             {"kind": "turn_start", "turn": 2, "harness_version": 0},
             {"kind": "tool", "turn": 2, "name": "edit_file", "args": {"path": "a.py"}, "ok": False,
              "output": "✗ The user declined the change to a.py. Ask what they want instead."},
             {"kind": "tool", "turn": 2, "name": "write_file", "args": {"path": "b.py"}, "ok": True, "output": "ok"},
             {"kind": "turn_end", "turn": 2, "text": "done", "seconds": 5}]
    return rows


def test_patterns_are_found_in_a_chat_record(tmp_path):
    _write(tmp_path / "proj" / ".mitra" / "runs" / "chat-20261106.jsonl", chat_session())
    files = A.find_run_files([tmp_path])
    assert len(files) == 1
    rep = A.analyze(files)
    got = {p.name: p.count for p in rep.patterns.values()}
    assert got["repeated_failing_command"] == 1 and "4× cd brick-breaker && pytest" in \
        rep.patterns["repeated_failing_command"].examples[0]
    assert got["refused_repeat"] == 1 and got["guard_stop"] == 1  # counted once, not again from turn_end
    assert got["invalid_file"] == 1 and got["declined_edit"] == 1 and got["empty_answer"] == 1
    assert got["tests_never_passed"] == 1      # turn 1 ran pytest, never green
    assert got["no_tests_after_code"] == 1     # turn 2 wrote b.py, ran nothing
    assert rep.units == 2 and rep.steps == 4 and rep.tokens_in == 4000
    assert rep.top(1)[0].name in got
    assert "repeated_failing_command" in A.format_report(rep)


def test_failing_tests_while_building_are_not_tool_errors(tmp_path):
    _write(tmp_path / ".mitra" / "runs" / "1" / "run.jsonl", [
        {"kind": "start", "harness_version": 2},
        {"kind": "tool", "name": "run_tests", "args": {}, "ok": False, "output": "FAILED: 1 failed"},
        {"kind": "tests", "passed": True},
        {"kind": "end", "status": "passed", "summary": "tests pass", "seconds": 9}])
    rep = A.analyze(A.find_run_files([tmp_path]))
    assert "tool_error" not in rep.patterns and "tests_never_passed" not in rep.patterns
    assert rep.passed_units == 1 and rep.harness_versions["2"] == 1


def test_records_inside_skipped_folders_are_ignored_and_bad_lines_dont_crash(tmp_path):
    _write(tmp_path / "node_modules" / ".mitra" / "runs" / "x.jsonl", chat_session())
    bad = tmp_path / ".mitra" / "runs" / "bad.jsonl"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json\n", encoding="utf-8")
    files = A.find_run_files([tmp_path])
    assert files == [bad]
    assert A.analyze(files).patterns == {}


def test_dashboard_page_shows_results_patterns_and_escapes(tmp_path, monkeypatch):
    monkeypatch.setenv("MITRA_HOME", str(tmp_path / "home"))
    res = tmp_path / "playground" / "results" / "01-snake"
    res.mkdir(parents=True)
    (res / "r.json").write_text(json.dumps({
        "level": "01-snake", "model": "qwen3.5:4b", "date": "2026-11-06 19:50", "build_seconds": 428,
        "visible": {"passed": 17}, "visible_plus_hidden": {"passed": 71, "failed": 1}, "passed": False}),
        encoding="utf-8")
    rows = chat_session()
    rows[1]["output"] = "⚠ <script>x</script> not valid"
    _write(tmp_path / "playground" / ".mitra" / "runs" / "chat.jsonl", rows)
    out, rep = D.build([tmp_path])
    page = out.read_text(encoding="utf-8")
    assert out.parent == tmp_path / "home"
    assert "71/72" in page and "not passed" in page and "repeated_failing_command" in page
    assert "<script>x" not in page and "&lt;script&gt;" in page
    assert "<title>Mitra Dashboard</title>" in page
