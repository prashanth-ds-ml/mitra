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
    _write(tmp_path / "proj" / ".codemitra" / "runs" / "chat-20261106.jsonl", chat_session())
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
    _write(tmp_path / ".codemitra" / "runs" / "1" / "run.jsonl", [
        {"kind": "start", "harness_version": 2},
        {"kind": "tool", "name": "run_tests", "args": {}, "ok": False, "output": "FAILED: 1 failed"},
        {"kind": "tests", "passed": True},
        {"kind": "end", "status": "passed", "summary": "tests pass", "seconds": 9}])
    rep = A.analyze(A.find_run_files([tmp_path]))
    assert "tool_error" not in rep.patterns and "tests_never_passed" not in rep.patterns
    assert rep.passed_units == 1 and rep.harness_versions["2"] == 1


def test_records_inside_skipped_folders_are_ignored_and_bad_lines_dont_crash(tmp_path):
    _write(tmp_path / "node_modules" / ".codemitra" / "runs" / "x.jsonl", chat_session())
    bad = tmp_path / ".codemitra" / "runs" / "bad.jsonl"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json\n", encoding="utf-8")
    files = A.find_run_files([tmp_path])
    assert files == [bad]
    assert A.analyze(files).patterns == {}


def test_dashboard_page_shows_results_patterns_and_escapes(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEMITRA_HOME", str(tmp_path / "home"))
    res = tmp_path / "playground" / "results" / "01-snake"
    res.mkdir(parents=True)
    (res / "r.json").write_text(json.dumps({
        "level": "01-snake", "model": "qwen3.5:4b", "date": "2026-11-06 19:50", "build_seconds": 428,
        "visible": {"passed": 17}, "visible_plus_hidden": {"passed": 71, "failed": 1}, "passed": False}),
        encoding="utf-8")
    rows = chat_session()
    rows[1]["output"] = "⚠ <script>x</script> not valid"
    _write(tmp_path / "playground" / ".codemitra" / "runs" / "chat.jsonl", rows)
    out, rep = D.build([tmp_path])
    page = out.read_text(encoding="utf-8")
    assert out.parent == tmp_path / "home"
    assert "71/72" in page and "not passed" in page and "repeated_failing_command" in page
    assert "<script>x" not in page and "&lt;script&gt;" in page
    assert "<title>CodeMitra Dashboard</title>" in page


def test_overlapping_roots_count_each_record_once_and_examples_name_the_project(tmp_path):
    _write(tmp_path / "games" / "snake" / ".codemitra" / "runs" / "chat-1.jsonl", chat_session())
    files = A.find_run_files([tmp_path, tmp_path / "games"])
    assert len(files) == 1
    rep = A.analyze(files)
    assert rep.patterns["refused_repeat"].examples[0].startswith("snake/chat-1.jsonl")
    assert rep.patterns["tests_never_passed"].examples[0].startswith("snake/")


def test_pytest_through_run_command_is_a_test_run_not_a_tool_error(tmp_path):
    _write(tmp_path / ".codemitra" / "runs" / "c.jsonl", [
        {"kind": "turn_start", "turn": 1},
        {"kind": "tool", "turn": 1, "name": "run_command", "args": {"command": "python -m pytest -q"}, "ok": False,
         "output": "1 failed"},
        {"kind": "tool", "turn": 1, "name": "run_command", "args": {"command": "npm start"}, "ok": False,
         "output": "npm: not found"},
        {"kind": "turn_end", "turn": 1, "text": "ok"}])
    rep = A.analyze(A.find_run_files([tmp_path]))
    assert rep.patterns["tool_error"].count == 1 and "npm" in rep.patterns["tool_error"].examples[0]


def test_analyze_can_keep_only_records_of_one_harness_version(tmp_path):
    old = chat_session()                      # no harness_version: made before step 1 = defaults (v0)
    old[0].pop("harness_version")
    new = [dict(r) for r in chat_session()]
    new[0]["harness_version"] = 1
    _write(tmp_path / "a" / ".codemitra" / "runs" / "old.jsonl", old)
    _write(tmp_path / "b" / ".codemitra" / "runs" / "new.jsonl", new)
    files = A.find_run_files([tmp_path])
    assert [A.file_version(f) for f in files] == [0, 1]
    assert A.analyze(files, harness_version=1).files == 1
    assert A.analyze(files, harness_version=0).files == 1
    assert A.analyze(files).files == 2


def test_run_files_include_the_improve_benchmark_records(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEMITRA_HOME", str(tmp_path / "home"))
    _write(tmp_path / "home" / "harness" / "runs" / "20261106" / "candidate" / "T01.jsonl", [{"kind": "start"}])
    _write(tmp_path / "proj" / ".codemitra" / "runs" / "chat.jsonl", [{"kind": "turn_start", "turn": 1}])
    names = [p.name for p in D.run_files([tmp_path / "proj"])]
    assert sorted(names) == ["T01.jsonl", "chat.jsonl"]


def test_interrupted_turns_are_counted_with_or_without_an_end_record(tmp_path):
    """Live session 2026-11-06: turns 6 and 7 were stopped with esc and left no turn_end; nothing counted them."""
    _write(tmp_path / ".codemitra" / "runs" / "chat.jsonl", [
        {"kind": "turn_start", "turn": 1}, {"kind": "model", "turn": 1},           # old record: no end
        {"kind": "turn_start", "turn": 2},
        {"kind": "turn_end", "turn": 2, "interrupted": True, "steps": 11, "text": ""},  # new record
        {"kind": "turn_start", "turn": 3}, {"kind": "model", "turn": 3}])          # still running: not counted
    rep = A.analyze(A.find_run_files([tmp_path]))
    p = rep.patterns["interrupted"]
    assert p.count == 2 and "empty_answer" not in rep.patterns
    assert any("turn 1 (no end record)" in e for e in p.examples) and any("after 11 steps" in e for e in p.examples)


def test_chat_records_a_turn_that_is_interrupted(tmp_path):
    from types import SimpleNamespace

    import pytest
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.core import chat as C

    class Model:
        def bind_tools(self, specs):
            return self

        def stream(self, messages):
            raise KeyboardInterrupt

    hooks = C.Hooks(stream=lambda chunks, step=1: SimpleNamespace(message=next(iter(chunks)), text="", stopped=False,
                                                                   printed=True),
                    show=lambda *a: None, confirm=lambda *a: True, run_shell=lambda c: ("", True),
                    web_search=lambda q: "", fetch_url=lambda u: "", mcp_find=lambda q: "", mcp_call=lambda *a: "")
    session = C.ChatSession(workspace=tmp_path, llm=Model(), hooks=hooks)
    with pytest.raises(KeyboardInterrupt):
        session.turn([SystemMessage(content="s"), HumanMessage(content="go")])
    rows = [json.loads(x) for f in (tmp_path / ".codemitra" / "runs").glob("chat-*.jsonl")
            for x in f.read_text(encoding="utf-8").splitlines()]
    end = [r for r in rows if r["kind"] == "turn_end"]
    assert len(end) == 1 and end[0]["interrupted"] and "KeyboardInterrupt" in end[0]["reason"]
