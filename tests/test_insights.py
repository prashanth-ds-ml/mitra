"""Dashboard steps 2-5 (D-041): sessions, tools and models, improvement, training data, from fixtures."""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.core import dashboard as D
from app.core import insights as I
from app.core import loop as L
from app.core import store as S


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _session_rows(v=0, outcome="answered", fail=False, t0=1000.0, retry=False):
    rows = [{"t": t0, "kind": "turn_start", "turn": 1, "user": "fix the paddle", "mode": "approve",
             "harness_version": v, "model": "qwen3.5:latest", "author": "mitra"},
            {"t": t0 + 20, "kind": "model", "turn": 1, "step": 1, "tool_calls": [{"name": "read_file"}],
             "tokens_out": 40, "author": "mitra"},
            {"t": t0 + 21, "kind": "tool", "turn": 1, "name": "read_file", "args": {"path": "game.py"}, "ok": not fail,
             "output": "✗ File not found: C:\\x\\game.py" if fail else "ok", "author": "mitra"}]
    if retry:
        rows.append({"t": t0 + 30, "kind": "bad_tool_call", "turn": 1, "step": 2, "error": "XML syntax error"})
    rows += [{"t": t0 + 25, "kind": "tool", "turn": 1, "name": "mcp_call", "args": {"server": "git", "tool": "log"},
              "ok": True, "output": "", "author": "mitra"},
             {"t": t0 + 40, "kind": "turn_end", "turn": 1, "steps": 2, "outcome": outcome, "seconds": 40,
              "tokens_in": 1600, "tokens_out": 120, "author": "mitra"}]
    return rows


def test_sessions_rebuild_turns_and_steps_in_order(tmp_path):
    f = tmp_path / "chat-1.jsonl"
    _write(f, _session_rows(fail=True, retry=True))
    (s,) = I.sessions([f])
    (t,) = s.turns
    assert s.kind == "chat" and t.outcome == "answered" and t.model == "qwen3.5:latest"
    assert [(st.kind, st.name) for st in t.steps] == [("model", "read_file"), ("tool", "read_file"),
                                                     ("retry", "bad_tool_call"), ("tool", "mcp:git")]
    assert t.steps[1].ok is False and t.steps[1].detail == "game.py" and t.steps[1].seconds == 1.0


def test_a_turn_with_no_end_is_interrupted(tmp_path):
    f = tmp_path / "chat-2.jsonl"
    _write(f, _session_rows()[:3])
    assert I.sessions([f])[0].turns[0].outcome == "interrupted"


def test_tool_stats_count_by_tool_and_mcp_server(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write(a, _session_rows(fail=True))
    _write(b, _session_rows(fail=False, t0=5000))
    stats = I.tool_stats(I.sessions([a, b]))
    I.tool_errors([a, b], stats)
    by = {s.name: s for s in stats}
    assert by["read_file"].calls == 2 and by["read_file"].failures == 1 and by["read_file"].fail_pct == 50
    assert by["mcp:git"].calls == 2 and by["read_file"].top_error.startswith("✗ File not found: <path>")


def test_model_stats_from_traces(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".codemitra" / "runs" / "r.jsonl")
    reply = AIMessage(content="hi", usage_metadata={"input_tokens": 26214, "output_tokens": 100, "total_tokens": 0})
    rec.trace([SystemMessage(content="s"), HumanMessage(content="u")], reply, model="qwen3.5:latest",
              num_ctx=262144, seconds=10.0)
    (m,) = I.model_stats([rec.trace_path])
    assert m.model == "qwen3.5:latest" and m.median_tok_s == 10.0 and m.num_ctx == 262144 and m.median_ctx_pct == 10


def test_improvement_per_version_with_not_enough_data(tmp_path):
    files = []
    for i in range(25):
        f = tmp_path / f"v0-{i}.jsonl"
        _write(f, _session_rows(v=0, fail=True, outcome="stopped_by_user" if i % 2 else "answered", t0=i * 100))
        files.append(f)
    f = tmp_path / "v1.jsonl"
    _write(f, _session_rows(v=1, fail=False, t0=99999))
    files.append(f)
    v0, v1 = I.improvement(I.sessions(files))
    assert (v0.version, v0.turns, v0.enough, v0.rate(v0.tool_failures)) == (0, 25, True, 1.0)
    assert v0.finished_pct == 52 and v1.turns == 1 and not v1.enough and v1.finished_pct == 100


def _traced_turn(root, outcome, author="mitra"):
    rec = L.Recorder(root / ".codemitra" / "runs" / "chat-1.jsonl")
    rec.write("turn_start", turn=1, user="make tests pass", harness_version=2, author=author)
    msgs = [SystemMessage(content="sys"), HumanMessage(content="make tests pass")]
    r1 = AIMessage(content="", tool_calls=[{"name": "run_tests", "args": {}, "id": "c1"}])
    rec.trace(list(msgs), r1, model="qwen3.5:4b", turn=1, step=1)
    msgs += [r1, ToolMessage(content="3 passed", tool_call_id="c1")]
    rec.trace(list(msgs), AIMessage(content="All 3 tests pass."), model="qwen3.5:4b", turn=1, step=2)
    rec.write("turn_end", turn=1, steps=2, outcome=outcome)
    return rec.path


def test_training_counts_usable_turns_and_why_others_are_out(tmp_path):
    good = _traced_turn(tmp_path / "good", "tests_passed")
    failed = _traced_turn(tmp_path / "bad", "tests_failed")
    claude = _traced_turn(tmp_path / "claude", "tests_passed", author="claude")
    old = tmp_path / "old" / ".codemitra" / "runs" / "chat-0.jsonl"
    _write(old, _session_rows(outcome="tests_passed"))
    tr = I.training([good, failed, claude, old])
    assert tr.turns == 4 and tr.usable == 1
    assert tr.reasons == {"tests failed": 1, "written partly by someone else (D-022)": 1,
                          "no trace (recorded before traces existed, or traces off)": 1}


def test_export_writes_only_usable_turns_with_the_whole_trajectory(tmp_path):
    good = _traced_turn(tmp_path / "good", "tests_passed")
    failed = _traced_turn(tmp_path / "bad", "tests_failed")
    out = tmp_path / "train.jsonl"
    assert I.export_training([good, failed], out) == 1
    (row,) = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant", "tool", "assistant"]
    assert row["messages"][0]["content"] == "sys" and row["messages"][-1]["content"] == "All 3 tests pass."
    assert row["meta"]["outcome"] == "tests_passed" and row["meta"]["harness_version"] == 2


def test_the_page_has_every_section_and_works_from_the_store_alone(tmp_path):
    import shutil
    good = _traced_turn(tmp_path / "proj", "tests_passed")
    shutil.rmtree(tmp_path / "proj")  # the project is gone; the store still has it
    out, _ = D.build(roots=[tmp_path], out=tmp_path / "dash.html")
    page = out.read_text(encoding="utf-8")
    for heading in ("<h2>Sessions</h2>", "Tools", "Models (from traces)", "Is CodeMitra improving?",
                    "Training data (D-022)"):
        assert heading in page
    assert "<b>proj</b>" in page and "qwen3.5:4b" in page and "tests_passed" in page
    assert S.stored_files() and not good.exists()


def test_the_page_with_no_data_says_so(tmp_path):
    out, _ = D.build(roots=[tmp_path], out=tmp_path / "dash.html")
    page = out.read_text(encoding="utf-8")
    assert "no sessions yet" in page and "no traces yet" in page and "no turns yet" in page
