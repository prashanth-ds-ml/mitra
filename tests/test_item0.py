"""Item 0 (SELF_IMPROVEMENT.md section 4): every signal that helps self-improvement is recorded and shown."""
import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C
from app.core import dashboard as D
from app.core import insights as I
from app.core import loop as L
from app.core import runinfo
from app.core import store as S


def _rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


class _Model:
    model = "qwen3.5:4b"

    def __init__(self, replies):
        self.replies = list(replies)

    def bind_tools(self, specs):
        return self

    def stream(self, messages):
        return iter([self.replies.pop(0)])


def _session(tmp_path, model, confirm=True):
    hooks = C.Hooks(stream=lambda chunks, step=1: (lambda m: SimpleNamespace(
                        message=m, text=m.content, stopped=False, printed=True, seconds=0.5, thinking=""))(
                        next(iter(chunks))),
                    show=lambda *a: None, confirm=lambda *a: confirm, run_shell=lambda c: ("Skipped: user declined", False),
                    web_search=lambda q: "", fetch_url=lambda u: "", mcp_find=lambda q: "", mcp_call=lambda *a: "")
    return C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks)


def _write_call(path, content, cid="c1"):
    return AIMessage(content="", tool_calls=[{"name": "write_file", "args": {"path": path, "content": content}, "id": cid}])


def _record(tmp_path):
    return next((tmp_path / ".mitra" / "runs").glob("chat-*.jsonl"))


# ── recording ────────────────────────────────────────────────────────────────

def test_your_edit_after_a_turn_is_recorded_as_a_correction_of_that_turn(tmp_path):
    model = _Model([_write_call("a.py", "x = 1\n"), AIMessage(content="done"), AIMessage(content="ok")])
    s = _session(tmp_path, model)
    msgs = [SystemMessage(content="s"), HumanMessage(content="make a.py")]
    s.turn(msgs)
    (tmp_path / "a.py").write_text("x = 2\n", encoding="utf-8")  # you fix it
    msgs.append(HumanMessage(content="thanks"))
    s.turn(msgs)
    edits = [r for r in _rows(_record(tmp_path)) if r["kind"] == "user_edit"]
    assert len(edits) == 1 and edits[0]["of_turn"] == 1 and edits[0]["path"] == "a.py"
    assert edits[0]["added"] == 1 and edits[0]["removed"] == 1 and "+x = 2" in edits[0]["diff"]
    assert edits[0]["author"] == "user"


def test_no_correction_when_you_change_nothing_and_private_files_keep_no_diff(tmp_path):
    model = _Model([_write_call(".env", "TOKEN=abc\n"), AIMessage(content="done"), AIMessage(content="ok")])
    s = _session(tmp_path, model)
    msgs = [SystemMessage(content="s"), HumanMessage(content="go")]
    s.turn(msgs)
    msgs.append(HumanMessage(content="next"))
    s.turn(msgs)
    assert not [r for r in _rows(_record(tmp_path)) if r["kind"] == "user_edit"]
    assert C._read_small(tmp_path / ".env") is None


def test_declined_edit_and_command_are_recorded_as_yours(tmp_path):
    model = _Model([_write_call("a.py", "x = 1\n"),
                    AIMessage(content="", tool_calls=[{"name": "run_command", "args": {"command": "rm -r x"}, "id": "c2"}]),
                    AIMessage(content="ok")])
    s = _session(tmp_path, model, confirm=False)
    s.turn([SystemMessage(content="s"), HumanMessage(content="go")])
    declined = [r for r in _rows(_record(tmp_path)) if r["kind"] == "declined"]
    assert [d["tool"] for d in declined] == ["edit", "run_command"] and declined[0]["path"] == "a.py"
    assert all(d["author"] == "user" for d in declined)


def test_feedback_marks_the_last_turn(tmp_path):
    s = _session(tmp_path, _Model([AIMessage(content="hi")]))
    assert s.feedback("good") == "No turn yet to mark."
    s.turn([SystemMessage(content="s"), HumanMessage(content="hello")])
    assert s.feedback("bad", "wrong file").startswith('Turn 1 ("hello") marked 👎 bad')  # names the turn (E-052)
    fb = [r for r in _rows(_record(tmp_path)) if r["kind"] == "feedback"]
    assert fb[0]["of_turn"] == 1 and fb[0]["verdict"] == "bad" and fb[0]["note"] == "wrong file"


def test_turn_start_has_code_version_and_ram(tmp_path):
    s = _session(tmp_path, _Model([AIMessage(content="hi")]))
    s.note_session(model="qwen3.5:4b", num_ctx=131072, fit="ok", ram_free_gb=9.0)
    s.turn([SystemMessage(content="s"), HumanMessage(content="hello")])
    rows = _rows(_record(tmp_path))
    start = next(r for r in rows if r["kind"] == "turn_start")
    assert start["code_version"] == runinfo.code_version() and "ram_free_gb" in start
    session = next(r for r in rows if r["kind"] == "session")
    assert session["fit"] == "ok" and session["code_version"]


def test_code_version_is_a_short_commit_or_unknown():
    v = runinfo.code_version()
    assert v == "unknown" or (len(v.split("-")[0]) >= 7 and all(c in "0123456789abcdef" for c in v.split("-")[0]))


def test_ollama_timings_in_seconds():
    reply = AIMessage(content="x", response_metadata={"prompt_eval_count": 2000, "prompt_eval_duration": 4_000_000_000,
                                                      "eval_count": 100, "eval_duration": 10_000_000_000,
                                                      "load_duration": 12_500_000_000})
    assert runinfo.ollama_timings(reply) == {"prompt_tokens": 2000, "gen_tokens": 100, "prompt_s": 4.0,
                                             "gen_s": 10.0, "load_s": 12.5}


def test_trace_carries_timings_and_failed_and_wrap_up_calls(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".mitra" / "runs" / "r.jsonl")
    reply = AIMessage(content="x", response_metadata={"prompt_eval_duration": 2_000_000_000, "load_duration": 3_000_000_000})
    rec.trace([SystemMessage(content="s"), HumanMessage(content="u")], reply)
    rec.trace([SystemMessage(content="s"), HumanMessage(content="u")], None, purpose="failed", error="XML syntax error")
    calls = [r for r in _rows(rec.trace_path) if r["kind"] == "call"]
    assert calls[0]["prompt_s"] == 2.0 and calls[0]["load_s"] == 3.0 and calls[0]["code_version"]
    assert calls[1]["reply"] is None and calls[1]["error"] == "XML syntax error"


def test_wrap_up_call_is_traced(tmp_path):
    s = _session(tmp_path, _Model([AIMessage(content="I did X; Y is left.")]))
    s.turn_no = 1
    msgs = [SystemMessage(content="s"), HumanMessage(content="go")]
    s._wrap_up(msgs, C.TurnResult(steps=3), "step limit (3 model calls)")
    calls = [r for r in _rows(s.rec.trace_path) if r["kind"] == "call"]
    assert calls[-1]["purpose"] == "wrap_up" and calls[-1]["reply"]["content"] == "I did X; Y is left."


def test_crash_rows_and_compaction_trace_are_wired_in_main():
    import inspect

    from app import main
    src = inspect.getsource(main._chat)
    assert 'chat.rec.write("crash"' in src and "rec=chat.rec" in src and "chat.note_session(" in src
    assert 'cmd in ("/good", "/bad")' in src
    assert 'purpose="compact"' in inspect.getsource(main._compact)


# ── what the dashboard computes ───────────────────────────────────────────────

def _w(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _day_rows(t0, version="abc1234", outcome="tests_passed", fix=False, verdict="", crash=False):
    rows = [{"t": t0, "kind": "session", "model": "qwen3.5:latest", "num_ctx": 262144, "fit": "tight",
             "ram_free_gb": 8.9, "code_version": version},
            {"t": t0 + 1, "kind": "turn_start", "turn": 1, "user": "fix it", "harness_version": 0,
             "code_version": version, "model": "qwen3.5:latest", "author": "mitra"},
            {"t": t0 + 5, "kind": "model", "turn": 1, "tool_calls": [{"name": "edit_file"}], "author": "mitra"},
            {"t": t0 + 6, "kind": "tool", "turn": 1, "name": "edit_file", "args": {"path": "g.py"}, "ok": True},
            {"t": t0 + 9, "kind": "model", "turn": 1, "tool_calls": [{"name": "run_tests"}], "author": "mitra"},
            {"t": t0 + 16, "kind": "tool", "turn": 1, "name": "run_tests", "args": {}, "ok": outcome == "tests_passed"},
            {"t": t0 + 18, "kind": "turn_end", "turn": 1, "outcome": outcome, "seconds": 17, "tokens_in": 900,
             "tokens_out": 100, "author": "mitra"}]
    if fix:
        rows.append({"t": t0 + 60, "kind": "user_edit", "of_turn": 1, "path": "g.py", "added": 1, "removed": 1,
                     "diff": "-a\n+b", "author": "user"})
    if verdict:
        rows.append({"t": t0 + 61, "kind": "feedback", "of_turn": 1, "verdict": verdict, "note": "n", "author": "user"})
    if crash:
        rows.append({"t": t0 + 62, "kind": "crash", "turn": 1, "error": "ResponseError: XML"})
    return rows


def test_sessions_carry_your_judgment_machine_and_time_to_green(tmp_path):
    f = tmp_path / "chat-1.jsonl"
    _w(f, _day_rows(1_000_000, fix=True, verdict="bad", crash=True))
    (s,) = I.sessions([f])
    (t,) = s.turns
    assert s.machine["fit"] == "tight" and s.code_version == "abc1234" and s.crashes[0]["error"].startswith("Response")
    assert t.verdict == "bad" and len(t.corrections) == 1 and t.crashes == 1
    assert t.green_s == 10.0 and t.tested and not t.first_try
    assert t.authors == {"mitra"}  # your rows never make it "written by someone else"


def test_trends_by_day_and_improvement_by_code_version(tmp_path):
    day = 86_400
    a, b, c = tmp_path / "a.jsonl", tmp_path / "b.jsonl", tmp_path / "c.jsonl"
    _w(a, _day_rows(1_700_000_000, version="aaa1111", outcome="tests_failed"))
    _w(b, _day_rows(1_700_000_000 + day, version="bbb2222", fix=True))
    _w(c, _day_rows(1_700_000_000 + day + 100, version="bbb2222", verdict="good"))
    sess = I.sessions([a, b, c])
    days = I.trends(sess)
    assert [g.turns for g in days] == [1, 2] and days[1].first_try_pct == 50 and days[0].first_try_pct == 0
    assert days[1].good == 1 and days[1].corrections == 1 and days[1].median_green_s == 10.0
    by_code = I.improvement(sess, by="code")
    assert [g.label for g in by_code] == ["aaa1111 · h0", "bbb2222 · h0"] and by_code[1].turns == 2


def test_breakdown_by_kind_detects_a_game_from_its_files(tmp_path):
    proj = tmp_path / "space-game"
    proj.mkdir()
    (proj / "main.py").write_text("import pygame\n", encoding="utf-8")
    S.note_project(proj)
    rec = L.Recorder(proj / ".mitra" / "runs" / "chat-1.jsonl")
    rec.write("turn_start", turn=1, user="go", model="qwen3.5:4b")
    rec.write("turn_end", turn=1, outcome="answered")
    sess = I.sessions(S.stored_files())
    assert [(g.label, g.turns) for g in I.breakdown(sess, "kind")] == [("game", 1)]
    assert [g.label for g in I.breakdown(sess, "model")] == ["qwen3.5:4b"]


def test_training_rules_for_good_bad_and_corrected_turns(tmp_path):
    def traced(root, outcome, verdict="", fix=False):
        rec = L.Recorder(root / ".mitra" / "runs" / "chat-1.jsonl")
        rec.write("turn_start", turn=1, user="u")
        rec.trace([SystemMessage(content="s"), HumanMessage(content="u")], AIMessage(content="a"), turn=1)
        rec.write("turn_end", turn=1, outcome=outcome)
        if fix:
            rec.write("user_edit", of_turn=1, path="x.py", added=1, removed=0, diff="+y", author="user")
        if verdict:
            rec.write("feedback", of_turn=1, verdict=verdict, note="", author="user")
        return rec.path
    files = [traced(tmp_path / "a", "answered", verdict="good"),       # 👍 without tests: usable, untested
             traced(tmp_path / "b", "tests_passed", verdict="bad"),    # 👎 wins over passing tests
             traced(tmp_path / "c", "tests_passed", fix=True),         # you fixed it: out
             traced(tmp_path / "d", "tests_passed")]                   # plain pass: usable
    tr = I.training(files)
    assert (tr.usable, tr.untested) == (2, 1)
    assert tr.reasons == {"you marked it bad": 1, "you corrected it": 1}
    out = tmp_path / "train.jsonl"
    assert I.export_training(files, out) == 2
    metas = [json.loads(x)["meta"] for x in out.read_text(encoding="utf-8").splitlines()]
    assert sorted(m["untested"] for m in metas) == [False, True]


def test_page_shows_trends_versions_judgment_crashes_and_filter(tmp_path):
    proj = tmp_path / "proj"
    rec = L.Recorder(proj / ".mitra" / "runs" / "chat-1.jsonl")
    for r in _day_rows(1_700_000_000, fix=True, verdict="bad", crash=True):
        kind = r.pop("kind")
        r.pop("t")
        rec.write(kind, **r)
    out, _ = D.build(roots=[tmp_path], out=tmp_path / "d.html")
    page = out.read_text(encoding="utf-8")
    for needed in ("<h2>Trends</h2>", "Mitra version · harness", "by kind of task", "by project",
                   "by model", "Your corrections, declines and marks", "Crashes", "ResponseError: XML",
                   "you fixed g.py", "👎 n", "id='pf'", "first try", "time to green", "prompt s (median)", "reloads",
                   "usable for training", "Self-improvement"):
        assert needed in page, needed
