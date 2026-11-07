"""Runnable plans: the template, the check, and the note Mitra gets when it writes a plan (D-055).

A plan runs with `/run` (or `mitra night` / `mitra solve --plan`) when it has tasks `### T1: title`, each with a
line `- Done when: `<test command>` passes`. The same check is used by /run, `/plan check`, and right after Mitra
writes a plan file, so a plan it writes is fixed on the spot instead of failing at night.
"""
from __future__ import annotations

TEMPLATE = """# Feature: <what you are building, one line>

## Goal
<Two or three sentences: what it does, how it is run (e.g. `python -m mygame.app`), what is out of scope.>

## Design notes
- <Exact names and numbers the tests can check: modules, classes, function signatures, defaults, rules.>
- <One bullet per rule; keep the logic in plain Python modules that tests can import (no window, no network).>
- Tests first: in every task, first write that task's test file, run it and see it fail, then write the code.
- Tests run with `python -m pytest -q`; a project venv (`.venv`) has the packages.

## Tasks

### T1: <first small piece>
- Files: `tests/test_t1_<name>.py`, `<package>/__init__.py`, `<package>/<module>.py`
- Do: first write `tests/test_t1_<name>.py`, then <what to build, referring to the design notes>.
- Done when: `python -m pytest -q tests/test_t1_<name>.py` passes
- Needs: -

### T2: <next piece>
- Files: `tests/test_t2_<name>.py`, `<package>/<module>.py`
- Do: first write `tests/test_t2_<name>.py`, then <what to build>.
- Done when: `python -m pytest -q tests/test_t2_<name>.py` passes
- Needs: T1
"""

PLAN_NAMES = ("plan.md",)


def is_plan_file(rel: str) -> bool:
    name = rel.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name in PLAN_NAMES or name.endswith(".plan.md")


def check_text(text: str) -> tuple[int, str]:
    """(number of tasks, problem); problem is "" when the plan can run."""
    from app.core.loop import parse_plan
    _, tasks = parse_plan(text)
    if not tasks:
        return 0, ("no tasks found. Tasks look like `### T1: title`, each with a line '- Done when:' followed by the "
                   "test command in backticks, e.g. python -m pytest -q tests/test_t1_x.py.")
    missing = [t.id for t in tasks if not t.test_command]
    if missing:
        return len(tasks), f"{', '.join(missing)} have no 'Done when' test command in backticks."
    unknown = sorted({n for t in tasks for n in t.needs} - {t.id for t in tasks})
    if unknown:
        return len(tasks), f"'Needs' names tasks that do not exist: {', '.join(unknown)}."
    return len(tasks), ""


def write_note(rel: str, text: str) -> str:
    """Appended to the write_file / edit_file / append_file result when Mitra writes a plan file."""
    if not is_plan_file(rel):
        return ""
    n, problem = check_text(text)
    if problem:
        return (f"\n⚠ {rel} is not runnable with /run yet: {problem} Fix the plan (format: `### T1: title`, "
                "`- Files:`, `- Do:`, `- Done when: `<test command>` passes`, `- Needs: T1` or -).")
    return f"\n✓ {rel} is runnable with /run ({n} task{'s' if n != 1 else ''})."
