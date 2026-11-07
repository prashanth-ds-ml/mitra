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


def _cycle(tasks) -> str:
    """A task that (indirectly) needs itself, e.g. T1 → T2 → T1; "" if none."""
    needs = {t.id: list(t.needs) for t in tasks}
    state: dict[str, int] = {}

    def visit(n: str, path: list[str]) -> str:
        if state.get(n) == 1:
            return " → ".join(path[path.index(n):] + [n]) if n in path else n
        if state.get(n) == 2:
            return ""
        state[n] = 1
        for m in needs.get(n, []):
            found = visit(m, path + [n])
            if found:
                return found
        state[n] = 2
        return ""

    for t in tasks:
        found = visit(t.id, [])
        if found:
            return found
    return ""


def check_text(text: str, folder: str = "") -> tuple[int, str]:
    """(number of tasks, problem); problem is "" when the plan can run. `folder` is the name of the plan's folder:
    /run runs the commands inside it, so paths must not start with it (2026-11-08: `brick-breaker/tests/...`)."""
    from app.core.loop import parse_plan
    _, tasks = parse_plan(text)
    if not tasks:
        return 0, ("no tasks found. Tasks look like `### T1: title`, each with a line '- Done when:' followed by the "
                   "test command in backticks, e.g. python -m pytest -q tests/test_t1_x.py.")
    problems = []
    missing = [t.id for t in tasks if not t.test_command]
    if missing:
        problems.append(f"{', '.join(missing)} have no 'Done when' test command in backticks")
    for t in tasks:
        cmd = t.test_command or ""
        if any(op in cmd for op in ("&&", "||", ";", "|")):
            problems.append(f"{t.id}: one command per task, no && / ; / | (pytest takes several tests at once: "
                            "python -m pytest -q tests/a.py::test_x tests/b.py::test_y)")
        if cmd.split()[:1] == ["pytest"]:
            problems.append(f"{t.id}: write `python -m pytest ...` (not `pytest ...`) so the project's own Python runs it")
        if folder and any(w.replace("\\", "/").startswith(folder + "/") for w in cmd.split()):
            problems.append(f"{t.id}: paths are relative to the plan's folder '{folder}': write tests/... "
                            f"not {folder}/tests/...")
        if t.id in t.needs:
            problems.append(f"{t.id} needs itself (write '- Needs: -' for a first task)")
    unknown = sorted({n for t in tasks for n in t.needs} - {t.id for t in tasks})
    if unknown:
        problems.append(f"'Needs' names tasks that do not exist: {', '.join(unknown)}")
    if not any(t.id in t.needs for t in tasks):
        cyc = _cycle(tasks)
        if cyc:
            problems.append(f"tasks need each other in a circle ({cyc}): nothing could start")
    if problems:
        shown = problems[:5] + ([f"… and {len(problems) - 5} more"] if len(problems) > 5 else [])
        return len(tasks), "; ".join(shown) + "."
    return len(tasks), ""


def write_note(rel: str, text: str) -> str:
    """Appended to the write_file / edit_file / append_file result when Mitra writes a plan file."""
    if not is_plan_file(rel):
        return ""
    parts = rel.replace("\\", "/").split("/")
    n, problem = check_text(text, parts[-2] if len(parts) > 1 else "")
    if problem:
        return (f"\n⚠ {rel} is not runnable with /run yet: {problem} Fix the plan (format: `### T1: title`, "
                "`- Files:`, `- Do:`, `- Done when: `<test command>` passes`, `- Needs: T1` or -).")
    return f"\n✓ {rel} is runnable with /run ({n} task{'s' if n != 1 else ''})."
