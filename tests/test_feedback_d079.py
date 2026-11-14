"""D-079: feedback on every turn with no extra work. (1) your next message is the verdict on the last answer;
(2) + / - on the empty prompt rates it with one key; (3) a rare "worked?" hint; (4) one key at exit for the session.
The unhappy cases are the user's own messages from the Neon Chomp session (2026-11-13), none of which was recorded."""
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core import chat as C
from app.core import signals as SIG
from app.ui import input as uin
from app.ui import keys as K
from tests.test_chat_core import fake_hooks
from tests.test_phased import Heard
from tests.test_ui_input import run_prompt

ANSWER = "Neon Chomp is now running! Press Enter on the title screen."


@pytest.mark.parametrize("said", [
    "i thought neon chomp...???",
    "why dont you do that",
    "did you do that fix",
    "we are talking about neon chomp game right...???",
    "last time we launched we were unable to play the game",
    "i cant move the pac man in the maze check if you have included keyboard controls",
    "$ python neon_chomp.py\nTraceback (most recent call last):\n  File \"x.py\", line 3\nAttributeError: 'Maze' object "
    "has no attribute 'player'",
    "it's still not working",
])
def test_the_live_unhappy_messages_are_verdicts(said):
    got = SIG.implicit_label(ANSWER, said)
    assert got and got[0] == "unhappy", said


@pytest.mark.parametrize("said, label", [
    ("thanks!", "happy"),
    ("great, works now", "happy"),
    ("perfect", "happy"),
    ("great but the colours are off", None),     # praise with a "but" is not a verdict
    ("add a pause key", None),                    # a new task says nothing about the last answer
    ("yes", None),                                # handled with the offer (below), not here
    ("/bad wrong project", None),                 # an explicit verdict is recorded by itself
])
def test_other_messages(said, label):
    got = SIG.implicit_label(ANSWER, said)
    assert (got[0] if got else None) == label


def test_no_verdict_without_a_previous_answer():
    assert SIG.implicit_label("", "why dont you do that") is None


def _session(tmp_path, *replies):
    return C.ChatSession(workspace=tmp_path, llm=Heard(*replies), hooks=fake_hooks()[0])


def _rows(s):
    return [json.loads(x) for x in s.rec.path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _signals(s):
    return [(r["signal"], r["of_turn"], r.get("why")) for r in _rows(s) if r["kind"] == "signal"]


def test_the_next_message_marks_the_turn_before(tmp_path):
    s = _session(tmp_path, AIMessage(content="I've written the fix for you to apply."),
                 AIMessage(content="Sorry, I'll do it now."))
    msgs = [SystemMessage(content=C.PHASED_PROMPT), HumanMessage(content="fix the pellet count")]
    s.phased(msgs)
    msgs.append(HumanMessage(content="why dont you do that"))
    s.phased(msgs)
    assert _signals(s) == [("unhappy", 1, "why dont")]
    row = [r for r in _rows(s) if r["kind"] == "signal"][0]
    assert row["auto"] is True and row["author"] == "user"


def test_a_rephrase_is_not_counted_twice(tmp_path):
    s = _session(tmp_path, AIMessage(content="Here it is."), AIMessage(content="Here it is again."))
    msgs = [SystemMessage(content=C.PHASED_PROMPT), HumanMessage(content="explain the drone targeting code please")]
    s.phased(msgs)
    msgs.append(HumanMessage(content="no, i meant explain the drone targeting code please"))
    s.phased(msgs)
    assert [x[0] for x in _signals(s)] == ["rephrase"]


def test_yes_to_an_offer_is_happy(tmp_path):
    s = _session(tmp_path, AIMessage(content="I can add a pause key. **Should I add it now?**"),
                 AIMessage(content="Added."))
    msgs = [SystemMessage(content=C.PHASED_PROMPT), HumanMessage(content="what could make the game better")]
    s.phased(msgs)
    msgs.append(HumanMessage(content="yes"))
    s.phased(msgs)
    assert _signals(s)[0][:2] == ("happy", 1)


def test_unhappy_is_evidence_for_the_learning_round(tmp_path):
    from app.core import improve_chat as IC
    assert "unhappy" in IC.EVIDENCE_SIGNALS
    s = _session(tmp_path, AIMessage(content="Done, it works."), AIMessage(content="Sorry."))
    msgs = [SystemMessage(content=C.PHASED_PROMPT), HumanMessage(content="fix the controls")]
    s.phased(msgs)
    msgs.append(HumanMessage(content="i thought neon chomp...???"))
    s.phased(msgs)
    found = IC.conversation_signals([s.rec.path])
    assert found and found[0]["signal"] == "unhappy" and found[0]["next"] == "i thought neon chomp...???"


# ── + / - on the empty prompt ────────────────────────────────────────────────────────────────────────────────────

def test_plus_and_minus_rate_with_one_key_right_after_an_answer(tmp_path):
    text, state = run_prompt("+", tmp_path, state=uin.UiState(can_rate=True))
    assert text == uin.RATE_GOOD and not state.can_rate
    text, _ = run_prompt("-", tmp_path, state=uin.UiState(can_rate=True))
    assert text == uin.RATE_BAD


def test_plus_and_minus_type_normally_otherwise(tmp_path):
    text, _ = run_prompt("+1 for this\r", tmp_path, state=uin.UiState(can_rate=False))
    assert text == "+1 for this"
    text, _ = run_prompt("a - b\r", tmp_path, state=uin.UiState(can_rate=True))   # not first: just a character
    assert text == "a - b"


def test_the_key_verdict_is_recorded_as_feedback(tmp_path):
    s = _session(tmp_path, AIMessage(content="Hi!"))
    s.phased([SystemMessage(content=C.PHASED_PROMPT), HumanMessage(content="hi")])
    s.feedback("bad", via="key")
    row = [r for r in _rows(s) if r["kind"] == "feedback"][0]
    assert row["verdict"] == "bad" and row["via"] == "key" and row["of_turn"] == 1


# ── the session rating at exit ───────────────────────────────────────────────────────────────────────────────────

def test_one_key_takes_a_digit_and_skips_anything_else():
    keys = iter("4")
    assert K.one_key("12345", timeout=1, getch=lambda: next(keys), kbhit=lambda: True) == "4"
    keys = iter("\r")
    assert K.one_key("12345", timeout=1, getch=lambda: next(keys), kbhit=lambda: True) == ""
    assert K.one_key("12345", timeout=0.1, getch=lambda: "x", kbhit=lambda: False) == ""      # nothing pressed


def test_the_session_rating_is_recorded(tmp_path):
    s = _session(tmp_path)
    s.rate_session(4)
    s.rate_session(9)  # out of range: ignored
    rows = [r for r in _rows(s) if r["kind"] == "session_rating"]
    assert len(rows) == 1 and rows[0]["stars"] == 4
