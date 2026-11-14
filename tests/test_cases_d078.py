"""D-078 Phase 2 step 6: your /bad turns become private, held-out score cases ("real"); E-120: a /bad was matched to
the turn with the same number in an earlier session of the same file (turn numbers restart every session)."""
import json

import pytest

from app.core import cases as K
from app.core import coach
from app.core import improve_chat as IC
from app.core import score as S


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEMITRA_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _chat(tmp_path, sessions):
    """sessions: [[(you, mitra, verdict, note), ...], ...] -> one chat file with a session row before each."""
    d = tmp_path / "runs" / "mitra-try-54b64f"
    d.mkdir(parents=True, exist_ok=True)
    rows, t = [], 100.0
    for turns in sessions:
        rows.append({"t": t, "kind": "session"})
        for n, (you, mitra, verdict, note) in enumerate(turns, 1):
            t += 1
            rows += [{"t": t, "kind": "turn_start", "turn": n, "user": you, "path": "phased"},
                     {"t": t + 0.5, "kind": "turn_end", "turn": n, "text": mitra, "seconds": 3}]
            if verdict:
                rows.append({"t": t + 0.7, "kind": "feedback", "of_turn": n, "verdict": verdict, "note": note})
    f = d / "chat-20261112.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return f


LIVE = [[("hello mitra", "Hello!", None, ""), ("i fixed you", "Great!", None, "")],
        [("hi", "Hi!", None, ""),
         ("can you do a deep dive on the model once again", "Would you like me to search?", "bad",
          "i thought it would directly do websearch and consolidate")]]


# ── E-120 ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_bad_is_matched_to_its_own_session(tmp_path):
    f = _chat(tmp_path, LIVE)
    [turn] = K.bad_turns([f])
    assert turn["you"].startswith("can you do a deep dive") and turn["history"] == [["hi", "Hi!"]]
    [sig] = IC.conversation_signals([f])
    assert sig["you"].startswith("can you do a deep dive")              # was "i fixed you" (session 1, turn 2)
    [t] = [x for x in coach.turns_since([f], 0) if x["flags"]]
    assert t["you"].startswith("can you do a deep dive")


# ── drafting ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_template_guesses_what_should_have_happened_from_the_note():
    assert K.guess_expect({"note": "i thought it would directly do websearch", "you": "deep dive on the model"}) \
        == "lookup"
    assert K.guess_expect({"note": "we expect what it can do and cant do", "you": "tell me about you"}) == "talk"


def test_the_coach_drafts_and_a_bad_draft_falls_back_to_the_template(tmp_path):
    f = _chat(tmp_path, LIVE)
    [turn] = K.bad_turns([f])
    good = ('[[case]]\nid = "R_deep_dive_model"\ntext = "x"\nexpect = "lookup"\n'
            "must_not = ['(?i)would you like me to search']\n")
    case, who = K.draft(turn, run_claude=lambda prompt: good)
    assert who == "coach" and case["expect"] == "lookup" and case["text"] == turn["you"]   # your exact words
    case, who = K.draft(turn, run_claude=lambda prompt: "Sure! Here is a case: expect lookup")
    assert who == "template" and case["expect"] == "lookup"
    def offline(prompt):
        raise RuntimeError("no claude")
    assert K.draft(turn, run_claude=offline)[1] == "template"


def test_drafts_are_written_once_and_kept_cases_go_to_the_private_real_set(tmp_path, home):
    f = _chat(tmp_path, LIVE)
    [p] = K.write_drafts([f])
    assert p.parent == home / "cases" / "drafts" and "CodeMitra answered: Would you like me to search?" in p.read_text(
        encoding="utf-8")
    assert K.write_drafts([f]) == []                                          # not drafted twice
    case = K.keep(p)
    assert not p.exists() and case["id"] in K.kept_ids()
    assert K.real_path() == home / "score" / "real.toml"                      # never in the repo
    data = S.real_cases()
    assert data["project"] == "snake" and data["case"][0]["expect"] == "lookup"
    with pytest.raises(ValueError, match="already"):
        (home / "cases" / "drafts").mkdir(exist_ok=True)
        dup = home / "cases" / "drafts" / "dup.toml"
        dup.write_text(K.to_toml(case), encoding="utf-8")
        K.keep(dup)


def test_a_draft_with_unknown_keys_or_no_expect_is_refused():
    with pytest.raises(ValueError, match="unknown keys"):
        K.parse_case('[[case]]\ntext = "x"\nexpect = "talk"\nscore = 5\n')
    with pytest.raises(ValueError, match="expect"):
        K.parse_case('[[case]]\ntext = "x"\nexpect = "maybe"\n')


# ── held out ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_real_cases_are_scored_but_never_learned_from(tmp_path):
    assert "real" in S.QUICK and "real" in S.HELD_OUT and "real" not in IC.JUDGE_CATEGORIES
    row = {"cases": [{"id": "R_x", "category": "real", "passed": False, "why": "w"},
                     {"id": "B2_thinking", "category": "behaviour", "passed": False, "why": "w"}]}
    assert [c["id"] for c in IC.score_failures(row)] == ["B2_thinking"]
    f = _chat(tmp_path, LIVE)
    K.keep(K.write_drafts([f])[0])
    assert IC.conversation_signals([f]) == []                                 # its /bad is held out too
