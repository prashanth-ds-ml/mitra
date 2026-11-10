"""D-065 P3 (sorting), P4 (planner), P5 (steps, re-plan, resume note)."""
from langchain_core.messages import AIMessage

from app.core import intent, planner
from app.core import plans

GOOD = """# Feature: score counter

## Goal
Count points when a brick breaks.

## Design notes
- `game/score.py`: class Score with add(points) and value.

## Tasks

### T1: score class
- Files: `tests/test_score.py`, `game/score.py`
- Do: first write the test, then the class.
- Done when: `python -m pytest -q tests/test_score.py` passes
- Needs: -
"""


# ── P3 ────────────────────────────────────────────────────────────────────────

def test_requests_are_sorted_without_a_model():
    cases = {
        "hi mitra where did we last stop": "resume",
        "what does brick_breaker.py do?": "question",
        "how do I run the tests?": "question",
        "add a test for the paddle speed": "small",
        "fix the failing test in tests/test_game.py": "small",
        "rename Ball to Puck": "small",
        "build a brick breaker game with levels and a score screen": "big",
        "refactor the ball physics and add a pause menu": "big",
    }
    for text, kind in cases.items():
        assert intent.classify(text) == kind, text


# ── P4 ────────────────────────────────────────────────────────────────────────

class Planner:
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def invoke(self, messages):
        self.prompts.append(messages)
        return AIMessage(content=self.replies.pop(0))


def test_the_plan_is_extracted_and_checked():
    llm = Planner("Sure! Here is the plan:\n```markdown\n" + GOOD + "```\nGood luck.")
    text, problem = planner.make_plan(llm, "add a score counter", "## Files\ngame/")
    assert problem == "" and text.startswith("# Feature: score counter") and "Good luck" not in text
    assert plans.check_text(text)[0] == 1


def test_a_plan_with_problems_is_repaired_once():
    bad = GOOD.replace("`python -m pytest -q tests/test_score.py`", "`pytest tests/test_score.py && echo ok`")
    llm = Planner(bad, GOOD)
    text, problem = planner.make_plan(llm, "add a score counter", "")
    assert problem == "" and len(llm.prompts) == 2
    assert "cannot run" in llm.prompts[1][-1].content


def test_change_feedback_reaches_the_planner():
    llm = Planner(GOOD)
    planner.make_plan(llm, "task", "pack", feedback="split T1 in two", previous="old plan")
    ask = llm.prompts[0][1].content
    assert "old plan" in ask and "split T1 in two" in ask


def test_the_context_pack_has_the_tree_and_outlines_of_matching_files(tmp_path):
    (tmp_path / "game").mkdir()
    (tmp_path / "game" / "score.py").write_text("class Score:\n    def add(self, n):\n        pass\n",
                                                encoding="utf-8")
    (tmp_path / "game" / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
    pack = planner.context_pack(tmp_path, "add bonus points to the score")
    assert "## Files" in pack and "score.py" in pack
    assert "## Outline of game/score.py" in pack and "1: class Score" in pack


def test_saved_plans_live_in_the_project_folder(tmp_path):
    first = planner.save(tmp_path, "Add a score counter!", GOOD)
    again = planner.save(tmp_path, "Add a score counter!", GOOD)
    assert first.name == "add-a-score-counter.plan.md" and first.parent == tmp_path
    assert again != first and plans.is_plan_file(again.name)


# ── P5 ────────────────────────────────────────────────────────────────────────

def test_failed_steps_are_replanned_smaller():
    retry_tasks = ("### T101: score class only\n- Files: `game/score.py`\n- Do: the class.\n"
                   "- Done when: `python -m pytest -q tests/test_score.py` passes\n- Needs: -\n")
    llm = Planner(retry_tasks)
    text = planner.replan_failed(llm, GOOD, {"T1": "1 failed · AttributeError: add"})
    assert text.startswith("# Feature: score counter") and "### T101: score class only" in text
    assert "AttributeError: add" in llm.prompts[0][1].content
    assert planner.replan_failed(Planner("no idea"), GOOD, {"T1": "x"}) == ""


def test_the_resume_note_says_what_is_done_and_what_is_next(tmp_path):
    note = planner.resume_note("add a score counter", tmp_path / "add-a-score.plan.md",
                               {"T1": {"status": "passed", "title": "score class", "tests": "3 passed"},
                                "T2": {"status": "failed", "title": "show it", "tests": "1 failed",
                                       "summary": "NameError: font"}}, "1 failed, 3 passed")
    assert "- T1 ✓ score class: 3 passed" in note and "- T2 ✗ show it: 1 failed" in note
    assert "Next: T2 show it: NameError: font" in note and "add-a-score.plan.md" in note
