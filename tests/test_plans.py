"""D-055: a plan template, one check, and a note when Mitra writes a plan, so its plans run with /run."""
import inspect

from app.core import plans as P
from app.core import tools as T

GOOD = """# Feature: x
## Tasks
### T1: one
- Done when: `python -m pytest -q tests/test_t1_a.py` passes
- Needs: -
### T2: two
- Done when: `python -m pytest -q tests/test_t2_b.py` passes
- Needs: T1
"""


def test_check_accepts_a_runnable_plan_and_explains_the_rest():
    assert P.check_text(GOOD) == (2, "")
    n, why = P.check_text("## Task 1: setup\n**Done when:** tests pass")
    assert n == 0 and "### T1" in why
    n, why = P.check_text("### T1: a\n- Done when: tests pass\n")
    assert n == 1 and "backticks" in why
    n, why = P.check_text("### T1: a\n- Done when: `pytest -q` passes\n- Needs: T7\n")
    assert "T7" in why


def test_the_template_has_the_runnable_shape():
    n, why = P.check_text(P.TEMPLATE)
    assert n == 2 and why == ""  # placeholders aside, the template itself parses as a runnable plan


def test_writing_a_plan_tells_mitra_whether_it_runs(tmp_path):
    ws = T.Workspace(tmp_path, read_only=())
    bad = T.write_file(ws, "plan.md", "# Plan\n## Task 1\nDone when: it works\n")
    assert "not runnable with /run yet" in bad and "### T1" in bad
    T.read_file(ws, "plan.md")
    good = T.write_file(ws, "plan.md", GOOD)
    assert "✓ plan.md is runnable with /run (2 tasks)" in good
    other = T.write_file(ws, "notes.md", "### T1: a")
    assert "runnable" not in other  # only plan files are checked


def test_plan_files_are_recognised():
    assert P.is_plan_file("plan.md") and P.is_plan_file("game/night.plan.md") and P.is_plan_file("x\\PLAN.md")
    assert not P.is_plan_file("planning.md")


def test_prompt_and_commands_know_the_format():
    from app import main
    from app.core import chat
    assert "### T1: title" in chat.CHAT_PROMPT
    src = inspect.getsource(main._chat)
    assert '"/plan template"' in src and "plans_mod.check_text(" in src
