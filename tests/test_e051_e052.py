"""E-051 (a sentence's final period read as part of a slash command's argument) and E-052 (/good /bad after a /run
night landed on the chat turn before it)."""
import json

from langchain_core.messages import AIMessage

from app.core import chat as C
from app.main import _strip_sentence_dot
from tests.test_chat_core import Model, fake_hooks, msgs


def test_a_final_period_is_not_part_of_the_last_argument():
    assert _strip_sentence_dot("/run plan.md 4.") == "/run plan.md 4"
    assert _strip_sentence_dot("/plan check brick-breaker/plan.md.") == "/plan check brick-breaker/plan.md"
    assert _strip_sentence_dot("/night.") == "/night"


def test_paths_and_chat_messages_are_left_alone():
    assert _strip_sentence_dot("/run ../plan.md 4") == "/run ../plan.md 4"
    assert _strip_sentence_dot("/add ..") == "/add .."
    assert _strip_sentence_dot("fix the bug.") == "fix the bug."


def _feedback_rows(tmp_path):
    rows = []
    for f in (tmp_path / ".codemitra" / "runs").glob("chat-*.jsonl"):
        rows += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r.get("kind") == "feedback"]


def test_verdict_after_a_night_judges_the_night_not_the_turn_before(tmp_path):
    model = Model(AIMessage(content="Here is the plan."), AIMessage(content="ok"))
    hooks, _ = fake_hooks()
    session = C.ChatSession(workspace=tmp_path, llm=model, hooks=hooks, mode="auto")
    session.turn(msgs("write a plan for brick breaker"))
    assert 'Turn 1 ("write a plan for brick breaker") marked 👍 good' == session.feedback("good")
    session.last_night = {"plan": str(tmp_path / "plan.md"), "started": 123.0}  # what /run sets
    assert session.feedback("bad", "nothing ran") == "Night run plan.md marked 👎 bad: nothing ran"
    rows = _feedback_rows(tmp_path)
    assert rows[0]["of_turn"] == 1 and rows[0]["verdict"] == "good"
    assert rows[1]["of_turn"] is None and rows[1]["of_night"].endswith("plan.md") and rows[1]["verdict"] == "bad"
    session.turn(msgs("next thing"))  # a new turn: verdicts judge turns again
    assert session.feedback("good").startswith("Turn 2")
