"""`codemitra improve --chat` (Phase B, first part): a rule is proposed from failed score cases and your signals, and the
score decides whether it stays. No model: a scripted proposer and a scripted score."""
import json

from langchain_core.messages import AIMessage

from app.core import harness as H
from app.core import improve as I
from app.core import improve_chat as IC


class Proposer:
    model = "qwen3.5:latest"

    def __init__(self, *texts):
        self.texts, self.seen = list(texts), []

    def invoke(self, messages):
        self.seen.append(messages[-1].content)
        return AIMessage(content=self.texts.pop(0) if self.texts else "")


def _rule(text, why="fixes small talk"):
    return json.dumps({"kind": "rule", "text": text, "why": why})


def _row(score, failed=()):
    cases = [{"id": i, "category": c, "passed": False, "why": w} for i, c, w in failed]
    return {"date": "2026-11-11 16:28", "model": "qwen3.5:latest", "arch": "phased", "only": None,
            "categories": list(IC.JUDGE_CATEGORIES), "score": score, "cases": cases}


BASE = {"behaviour": [7, 10], "writing": [2, 3], "explain": [3, 4], "ideas": [1, 2]}
FAILED = [("B3_how_are_you", "behaviour", "should not match: (?i)\\bsnake\\b"),
          ("W3_summary", "writing", "missing: 1 Feb")]


class Scores:
    """Scripted `score.run`: the first call is the current harness, the second the candidate."""

    def __init__(self, *scores):
        self.scores, self.harnesses = list(scores), []

    def __call__(self, cats, *, runner, model, cwd, on_case, results):
        self.harnesses.append(runner.harness)
        return _row(self.scores.pop(0))


def _run(proposer, scores, row, files=(), **kw):
    return IC.improve_chat(proposer=proposer, make_runner=lambda h, rec: type("R", (), {"harness": h})(),
                           model="qwen3.5:latest", arch="phased", score_row=row, files=list(files),
                           instructions=lambda h: H.apply_prompt("You are CodeMitra.", h), run_score=scores,
                           say=lambda t: None, **kw)


def test_a_rule_that_adds_cases_without_a_drop_is_kept_and_can_be_undone():
    better = {**BASE, "behaviour": [9, 10]}
    scores = Scores(BASE, better)
    entry = _run(Proposer(_rule("When the user makes small talk, reply without mentioning their work.")), scores,
                 _row(BASE, FAILED))
    assert entry["result"] == "kept" and entry["new_version"] == 1
    assert H.load().rules == ["When the user makes small talk, reply without mentioning their work."]
    assert scores.harnesses[0].rules == [] and scores.harnesses[1].rules == H.load().rules  # A then B
    assert entry["next_row"]["score"] == better                                              # next round's evidence
    assert [a["result"] for a in I.attempts()] == ["kept"] and I.attempts()[0]["kind"] == "chat"


def test_a_rule_that_drops_a_category_is_dropped_even_with_more_cases():
    scores = Scores(BASE, {"behaviour": [10, 10], "writing": [1, 3], "explain": [3, 4], "ideas": [1, 2]})
    entry = _run(Proposer(_rule("When the user writes, answer short.")), scores, _row(BASE, FAILED))
    assert entry["result"] == "dropped" and "writing 1/3 (was 2/3)" in entry["reason"]
    assert H.load().rules == [] and entry["next_row"]["score"] == BASE


def test_one_more_case_is_not_enough_one_run_is_noisy():
    entry = _run(Proposer(_rule("When the user thinks aloud, ask one question.")),
                 Scores(BASE, {**BASE, "ideas": [2, 2]}), _row(BASE, FAILED))
    assert entry["result"] == "dropped" and "needs at least 15/19" in entry["reason"]


def test_a_rule_naming_the_test_set_is_refused_and_asked_again():
    p = Proposer(_rule("Never mention the snake game in small talk."),
                 _rule("In small talk, never bring up the project."))
    entry = _run(p, Scores(BASE, BASE), _row(BASE, FAILED), dry_run=True)
    assert entry["result"] == "dry_run" and entry["change"] == "rule: In small talk, never bring up the project."
    assert "names the test set (snake)" in p.seen[1]


def test_only_rules_and_never_a_rule_already_tried():
    I.log_attempt({"kind": "chat", "result": "dropped", "change": "rule: Ask one question back."})
    p = Proposer(json.dumps({"kind": "limit", "name": "max_repeats", "value": 3, "why": "x"}),
                 _rule("Ask one question back."))
    entry = _run(p, Scores(), _row(BASE, FAILED), dry_run=True)
    assert entry["result"] == "no_proposal" and "already tried" in entry["reason"]
    assert "Ask one question back." in p.seen[0]                      # the proposer was told what failed before


def test_nothing_to_learn_from_changes_nothing():
    entry = _run(Proposer(), Scores(), None)
    assert entry["result"] == "skipped" and I.attempts() == [] and H.load().version == 0


def test_a_broken_model_is_not_judged():
    class Broken(Scores):
        def __call__(self, cats, **kw):
            row = _row({"behaviour": [0, 2]})
            row["cases"] = [{"id": "B1", "category": "behaviour", "passed": False, "why": "TimeoutError: 600 s"},
                            {"id": "B2", "category": "behaviour", "passed": False, "why": "ConnectError: refused"}]
            return row

    entry = _run(Proposer(_rule("Ask one question back.")), Broken(), _row(BASE, FAILED))
    assert entry["result"] == "bench_error" and H.load().version == 0


def test_signals_from_your_conversations_are_evidence(tmp_path):
    rec = tmp_path / "chat-1.jsonl"
    rows = [{"t": 1, "kind": "turn_start", "turn": 1, "user": "good what about you"},
            {"t": 2, "kind": "turn_end", "turn": 1, "text": "Fine! Shall we fix the snake tests?"},
            {"t": 3, "kind": "feedback", "of_turn": 1, "verdict": "bad", "note": "I did not ask about work"},
            {"t": 4, "kind": "turn_start", "turn": 2, "user": "/copy"},
            {"t": 5, "kind": "signal", "of_turn": 2, "signal": "undo"},              # a command: not evidence
            {"t": 6, "kind": "feedback", "of_turn": 1, "verdict": "good", "note": ""}]
    rec.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    sigs = IC.conversation_signals([rec])
    assert [s["signal"] for s in sigs] == ["bad"] and sigs[0]["note"] == "I did not ask about work"
    text = IC.evidence_text([], sigs)
    assert 'the user said "good what about you"' in text and "I did not ask about work" in text
    p = Proposer(_rule("In small talk, never bring up the project."))
    entry = _run(p, Scores(), None, files=[rec], dry_run=True)        # signals alone are enough to start
    assert entry["result"] == "dry_run" and entry["evidence"] == {"score": "", "failed_cases": 0, "signals": 1}


def test_failed_cases_carry_what_the_user_typed():
    f = IC.score_failures(_row(BASE, FAILED))
    assert f[0]["asked"] == "good what about you" and f[1]["asked"].startswith("summarise this:")
    assert IC.last_score_row([_row(BASE), {**_row(BASE), "arch": "one"}], model="qwen3.5:latest",
                             arch="phased")["arch"] == "phased"
