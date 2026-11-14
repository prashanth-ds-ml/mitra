"""D-075: the two self-improvement layers. Layer 1: `codemitra improve --chat` starts by itself at exit when 3+ new
signals or a queued rule wait. Layer 2: `codemitra coach` sends a digest of the records to Claude (claude -p) and queues
the report's rules for layer 1. No model, no Claude: scripted."""
import json
import time

from langchain_core.messages import AIMessage

from app.core import coach as CO
from app.core import harness as H
from app.core import improve as I
from app.core import improve_chat as IC
from tests.test_improve_chat import BASE, FAILED, Proposer, Scores, _row, _run


def _record(path, turns):
    """turns: (you, mitra, extra rows) -> a chat record like the chat writes."""
    rows, t = [], time.time() - 3600
    for n, (you, mitra, extra) in enumerate(turns, 1):
        t += 10
        rows.append({"t": t, "kind": "turn_start", "turn": n, "user": you, "path": "phased", "backend": "laptop"})
        for e in extra:
            rows.append({"t": t + 1, **e, **({"turn": n} if e["kind"] in ("tool", "phase") else {"of_turn": n})})
        rows.append({"t": t + 2, "kind": "turn_end", "turn": n, "text": mitra, "seconds": 4.0})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def _session(tmp_path):
    return _record(tmp_path / "store" / "mitra-try-54b64f" / "chat-20261111.jsonl", [
        ("hi mitra", "Hi! How's your day?", []),
        ("can you pull information on self improving coding agents", "They often use reinforcement learning.",
         [{"kind": "feedback", "verdict": "bad", "note": "you did not search"}]),
        ("i said you to pick and tell me with a reason", "You're right! My pick: tests.",
         [{"kind": "signal", "signal": "rephrase"}]),
        ("how does step work?", "", [{"kind": "phase", "name": "look_at_code"},
                                     {"kind": "tool", "name": "read_file", "ok": False}]),
        ("/good", "", []),
    ])


# ── layer 2: the coach ───────────────────────────────────────────────────────────────────────────────────────────

def test_the_digest_puts_flagged_turns_first_and_skips_commands(tmp_path):
    turns = CO.turns_since([_session(tmp_path)], 0)
    assert [t["you"][:12] for t in turns] == ["hi mitra", "can you pull", "i said you t", "how does ste"]
    assert turns[0]["project"] == "mitra-try" and turns[3]["phase"] == "look_at_code"
    assert turns[1]["flags"] == ["you marked it /bad: you did not search"]
    assert "empty answer" in turns[3]["flags"] and "tool errors: read_file" in turns[3]["flags"]
    text = CO.digest(turns)
    flagged, every = text.split("## Every turn, in short")
    assert "## Turns that need a look (3)" in flagged and "hi mitra" not in flagged and "hi mitra" in every


def test_only_conversations_are_reviewed_not_score_or_plan_runs(tmp_path):
    score = _record(tmp_path / "store" / "_other" / "B3_how_are_you.jsonl", [("good what about you", "Fine!", [])])
    assert CO.turns_since([score, _session(tmp_path)], 0)[0]["you"] == "hi mitra"
    assert len(CO.turns_since([score], 0)) == 0


def test_a_review_writes_the_report_and_queues_its_rules_for_layer_1(tmp_path):
    seen = []
    report = """## Findings
1. "pull information" was answered from memory.
## Rules to test
```rules
{"text": "When the user asks you to find or pull information, search the web first.", "why": "1"}
{"text": "Never mention the snake game.", "why": "names the test set: refused"}
```
## Code fixes
- none
## New score cases
- "pull information on X": searches."""
    rec = _session(tmp_path)
    res = CO.coach([rec], ask=lambda text: seen.append(text) or report, say=lambda t: None)
    assert res["result"] == "done" and res["turns"] == 4 and res["rules"] == 2 and res["queued"] == 1
    assert seen[0].startswith(CO.COACH_PROMPT) and "you marked it /bad: you did not search" in seen[0]
    assert "## Findings" in open(res["report"], encoding="utf-8").read()
    assert [r["text"] for r in IC.queued_rules()] == [
        "When the user asks you to find or pull information, search the web first."]
    # the next review only sees new turns
    again = CO.coach([rec], ask=lambda text: report, say=lambda t: None)
    assert again["result"] == "skipped"


def test_a_failed_claude_call_changes_nothing(tmp_path):
    def broken(text):
        raise RuntimeError("claude -p failed (1): not logged in")

    res = CO.coach([_session(tmp_path)], ask=broken, say=lambda t: None)
    assert res["result"] == "error" and "not logged in" in res["reason"]
    assert CO.last_review_t() == 0 and IC.queued_rules() == []


def test_the_reminder_comes_after_a_week_or_40_turns(tmp_path):
    files = [_session(tmp_path)]
    assert CO.reminder(files) == ""                                         # 4 turns, never reviewed
    many = _record(tmp_path / "s2" / "chat-1.jsonl", [(f"question {i}", "answer", []) for i in range(40)])
    assert CO.reminder([many]) == "coach: no review yet, 40 new turns · `codemitra coach`"
    CO._save_state({"last_t": time.time() - 8 * 86400})
    assert CO.reminder(files).startswith("coach: last review 8 days ago, 4 new turns")


def test_rules_block_parsing_is_tolerant():
    rules = CO.parse_rules('x\n```rules\n{"text": "Ask one question back.", "why": "2"},\nnot json\n```\n')
    assert rules == [{"text": "Ask one question back.", "why": "2"}]
    assert CO.parse_rules("no block") == []


# ── layer 1 by itself ────────────────────────────────────────────────────────────────────────────────────────────

def test_a_queued_coach_rule_is_tested_before_asking_the_proposer():
    IC.queue_rules([{"text": "When the user asks to find information, search first.", "why": "1"}])
    p = Proposer()                                                          # never asked
    scores = Scores(BASE, {**BASE, "behaviour": [9, 10]})
    entry = _run(p, scores, None)                                           # no failures, no signals: the queue
    assert entry["result"] == "kept" and entry["source"] == "coach" and p.seen == []
    assert H.load().rules == ["When the user asks to find information, search first."]
    assert IC.queued_rules() == []                                          # taken off the queue either way


def test_a_round_starts_by_itself_at_3_new_signals_or_a_queued_rule(tmp_path):
    rec = _record(tmp_path / "chat-1.jsonl", [(f"try {i}", "x", [{"kind": "signal", "signal": "rephrase"}])
                                              for i in range(2)])
    due, why = IC.auto_due([rec])
    assert not due and "2 new signal(s)" in why
    rec3 = _record(tmp_path / "chat-1.jsonl", [(f"try {i}", "x", [{"kind": "signal", "signal": "rephrase"}])
                                               for i in range(3)])
    assert IC.auto_due([rec3, rec3]) == (True, "3 new signals since the last round")   # the same file twice: once
    I.log_attempt({"kind": "chat", "t": time.time(), "result": "dropped"})
    assert not IC.auto_due([rec3])[0]                                       # all older than the last round
    IC.queue_rules([{"text": "Ask one short question back.", "why": "x"}])
    assert IC.auto_due([rec3]) == (True, "1 queued rule(s) from the coach")


def test_the_background_round_is_started_once_and_logged(tmp_path, monkeypatch):
    started = []

    class P:
        pid = 4242

        def __init__(self, cmd, **kw):
            started.append((cmd, kw["cwd"]))

    log = IC.start_auto(tmp_path, popen=P)
    assert started[0][0][-4:] == ["improve", "--chat", "--rounds", "1"] and started[0][1] == str(tmp_path)
    assert log.parent.name == "auto" and (H.home() / "harness" / "auto.lock").read_text().startswith("4242 ")
    monkeypatch.setattr("psutil.pid_exists", lambda pid: pid == 4242)
    assert IC.auto_running() and IC.auto_due([]) == (False, "a round is already running")
