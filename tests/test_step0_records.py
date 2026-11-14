"""D-068 step 0: the records a coach needs: kind, path, machine, thinking, notes version, time to the first word, and
quiet signals (rephrase, interrupt, undo, copy). Each test fails without the step 0 change it names."""
import json
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C
from app.core import harness as H
from app.core import insights as I
from app.core import signals as SIG
from tests.test_chat_core import Model, fake_hooks


def rows(session, kind=None):
    out = [json.loads(x) for x in session.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in out if kind is None or r.get("kind") == kind]


def msgs(text):
    return [SystemMessage(content=C.CHAT_PROMPT), HumanMessage(content=text)]


def session(tmp_path, *replies, hooks=None):
    return C.ChatSession(workspace=tmp_path, llm=Model(*replies), hooks=hooks or fake_hooks()[0])


# ── signals.py ───────────────────────────────────────────────────────────────

def test_notes_version_changes_with_your_notes(tmp_path):
    assert SIG.notes_version(tmp_path) == "none"
    (tmp_path / ".codemitra").mkdir()
    (tmp_path / ".codemitra" / "notes.md").write_text("use uv", encoding="utf-8")
    v1 = SIG.notes_version(tmp_path)
    H.home().mkdir(parents=True, exist_ok=True)
    (H.home() / "me.md").write_text("Prashanth, concise", encoding="utf-8")
    v2 = SIG.notes_version(tmp_path)
    assert v1 != "none" and v2 != v1 and len(v2) == 8 and SIG.notes_version(tmp_path) == v2


def test_rephrase_is_asking_the_same_again_or_saying_it_was_wrong():
    assert SIG.is_rephrase("add a pause key to the game", "add a pause key to the brick game please")
    assert SIG.is_rephrase("fix the test", "no, I meant the other test")
    assert SIG.is_rephrase("make it work", "it still doesn't work")
    assert not SIG.is_rephrase("add a pause key to the game", "now write a mail to the team about kaggle")
    assert not SIG.is_rephrase("hi", "hi")          # greetings and short replies are not a complaint
    assert not SIG.is_rephrase("", "fix the test")


# ── chat records ─────────────────────────────────────────────────────────────

def test_turn_start_has_kind_path_backend_thinking_and_notes(tmp_path):
    s = session(tmp_path, AIMessage(content="Hello!"))
    s.backend_kind = "remote"
    s.apply_route({"role": "chat", "tools": None, "mcp": None}, thinking=False)
    s.request_kind = "small"
    s.turn(msgs("hi there"))
    start = rows(s, "turn_start")[0]
    assert start["request_kind"] == "small" and start["path"] == "loop" and start["backend"] == "remote"
    assert start["thinking"] is False and start["notes_version"] == "none"


def test_time_to_first_word_is_recorded(tmp_path):
    hooks, _ = fake_hooks()
    plain = hooks.stream

    def stream(chunks):
        r = plain(chunks)
        r.first_s = 1.25
        return r

    hooks.stream = stream
    s = session(tmp_path, AIMessage(content="Hi"), hooks=hooks)
    s.turn(msgs("hi"))
    assert rows(s, "turn_end")[0]["first_s"] == 1.25


def test_asking_again_marks_the_turn_before(tmp_path):
    s = session(tmp_path, AIMessage(content="done"), AIMessage(content="done again"))
    s.turn(msgs("add a pause key to the game"))
    s.turn(msgs("no, I meant the space bar pauses it"))
    sig = rows(s, "signal")
    assert sig == [dict(sig[0], of_turn=1, signal="rephrase", author="user")]


def test_ctrl_c_and_esc_are_interrupt_signals(tmp_path):
    hooks, _ = fake_hooks()

    def stream(chunks):
        raise KeyboardInterrupt

    hooks.stream = stream
    s = session(tmp_path, hooks=hooks)
    try:
        s.turn(msgs("explain the game"))
    except KeyboardInterrupt:
        pass
    hooks2, _ = fake_hooks()
    hooks2.stream = lambda chunks: SimpleNamespace(message=None, text="part", stopped=True, printed=True)
    s.hooks = hooks2
    s.turn(msgs("explain the snake"))
    assert [(r["of_turn"], r["signal"]) for r in rows(s, "signal")] == [(1, "interrupt"), (2, "interrupt")]


def test_undo_and_copy_signals_and_unknown_names(tmp_path):
    s = session(tmp_path, AIMessage(content="ok"))
    s.signal("undo")                      # no turn yet: nothing to mark (checked below: only two rows)
    s.turn(msgs("write hello.py"))
    s.signal("undo", all=False)
    s.signal("copy")
    assert [r["signal"] for r in rows(s, "signal")] == ["undo", "copy"]
    try:
        s.signal("liked")
        raise AssertionError("unknown signal accepted")
    except ValueError:
        pass


def test_a_request_outside_the_loop_is_a_numbered_turn(tmp_path):
    s = session(tmp_path, AIMessage(content="ok"))
    s.note_request("where did we stop", "resume", "resume_brief", "answered")
    s.note_request("add levels and a high score file", "big", "plan_first", "plan_saved", seconds=12.3,
                   choice="save", rounds=2)
    s.turn(msgs("thanks"))
    starts, ends = rows(s, "turn_start"), rows(s, "turn_end")
    assert [(r["turn"], r["request_kind"], r["path"]) for r in starts] == [
        (1, "resume", "resume_brief"), (2, "big", "plan_first"), (3, "", "loop")]
    assert ends[1]["outcome"] == "plan_saved" and ends[1]["choice"] == "save" and ends[1]["rounds"] == 2
    s.feedback("good")                    # /good after the loop turn marks turn 3, not a plan turn
    assert rows(s, "feedback")[0]["of_turn"] == 3


# ── insights ─────────────────────────────────────────────────────────────────

def test_insights_split_by_path_request_and_backend_with_signals(tmp_path):
    s = session(tmp_path, AIMessage(content="ok"), AIMessage(content="ok"))
    s.note_request("where did we stop", "resume", "resume_brief", "answered")
    s.request_kind, s.backend_kind = "small", "remote"
    s.turn(msgs("add a pause key to the game"))
    s.turn(msgs("add a pause key to the game, space bar"))
    s.signal("copy")
    sess = I.sessions([s.rec.path])
    turns = sess[0].turns
    assert [t.path for t in turns] == ["resume_brief", "loop", "loop"]
    assert turns[1].signals == ["rephrase"] and turns[2].signals == ["copy"]
    by_path = {g.label: g for g in I.breakdown(sess, "path")}
    assert by_path["loop"].turns == 2 and by_path["loop"].signals == {"rephrase": 1, "copy": 1}
    assert {g.label for g in I.breakdown(sess, "backend")} == {"laptop", "remote"}
    assert {g.label for g in I.breakdown(sess, "request")} == {"resume", "small"}


def test_old_records_still_load(tmp_path):
    f = tmp_path / "chat-old.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [
        {"kind": "turn_start", "t": 1.0, "turn": 1, "user": "hi", "mode": "approve"},
        {"kind": "turn_end", "t": 2.0, "turn": 1, "outcome": "answered", "seconds": 1}]) + "\n", encoding="utf-8")
    t = I.sessions([f])[0].turns[0]
    assert t.path == "" and t.first_s is None and t.signals == []
    assert [g.label for g in I.breakdown(I.sessions([f]), "path")] == [I.OLD]


def test_a_planner_error_reason_does_not_clash_with_the_record_fields(tmp_path):
    """Found by the driven chat test: the error path passes `reason`, which turn_end already had."""
    s = session(tmp_path)
    s.note_request("add levels", "big", "plan_first", "error", reason="the planner failed", rounds=1)
    assert rows(s, "turn_end")[0]["reason"] == "the planner failed"
