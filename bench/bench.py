"""Mitra benchmark: build task workspaces, grade them, validate the task set.

A task is `bench/tasks/<id>_<slug>/`:
  task.toml   id, title, kind (bug|feature), split (tune|heldout), prompt, [[break]] find/replace edits
  visible/    tests copied into the workspace's tests/ (the agent sees and may run them)
  hidden/     tests copied in only at grading time, in a separate copy (the agent never sees them)

Start state = bench/base + breaks + visible tests. Reference solution = bench/base + visible tests.

    python bench/bench.py list
    python bench/bench.py validate [--task T01]
    python bench/bench.py prepare T01 <dest>
    python bench/bench.py grade T01 <workspace>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

BENCH = Path(__file__).resolve().parent
BASE = BENCH / "base"
TASKS = BENCH / "tasks"
GRADE_TIMEOUT_S = 120
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    kind: str
    split: str
    prompt: str
    breaks: list[dict]
    dir: Path

    @property
    def visible(self) -> list[Path]:
        return sorted((self.dir / "visible").glob("test_*.py"))

    @property
    def hidden(self) -> list[Path]:
        return sorted((self.dir / "hidden").glob("test_*.py"))


@dataclass(frozen=True)
class Grade:
    task: str
    passed: bool
    tampered: list[str]
    infra_error: str | None
    output_tail: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def load_tasks(only: str | None = None) -> list[Task]:
    tasks = []
    for path in sorted(TASKS.glob("*/task.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        task = Task(
            id=data["id"],
            title=data["title"],
            kind=data["kind"],
            split=data["split"],
            prompt=data["prompt"].strip(),
            breaks=data.get("break", []),
            dir=path.parent,
        )
        if task.split not in {"tune", "heldout"} or task.kind not in {"bug", "feature"}:
            raise ValueError(f"{task.id}: bad split or kind")
        if only is None or task.id == only:
            tasks.append(task)
    if only and not tasks:
        raise SystemExit(f"no task {only}")
    return tasks


def _copy_base(dest: Path) -> None:
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"{dest} is not empty")
    shutil.copytree(BASE, dest, ignore=IGNORE, dirs_exist_ok=True)


def _add_visible(task: Task, dest: Path) -> None:
    for test in task.visible:
        shutil.copy2(test, dest / "tests" / test.name)


def apply_breaks(task: Task, dest: Path) -> None:
    for edit in task.breaks:
        target = dest / edit["file"]
        text = target.read_text(encoding="utf-8")
        count = text.count(edit["old"])
        if count != 1:
            raise ValueError(f"{task.id}: break text found {count} times in {edit['file']} (must be exactly 1)")
        target.write_text(text.replace(edit["old"], edit["new"]), encoding="utf-8")


def prepare(task: Task, dest: Path) -> None:
    """Start state: the workspace an agent receives."""
    _copy_base(dest)
    apply_breaks(task, dest)
    _add_visible(task, dest)


def prepare_solved(task: Task, dest: Path) -> None:
    """Reference solution: base code plus the task's visible tests."""
    _copy_base(dest)
    _add_visible(task, dest)


def protected_hashes(task: Task) -> dict[str, str]:
    """Hashes of test files the agent must not change, taken from the task source (not the workspace)."""
    files = {f"tests/{p.name}": p for p in task.visible}
    for p in (BASE / "tests").glob("*.py"):
        files[f"tests/{p.name}"] = p
    return {rel: hashlib.sha256(p.read_bytes()).hexdigest() for rel, p in sorted(files.items())}


def _tampered(task: Task, workspace: Path) -> list[str]:
    changed = []
    for rel, digest in protected_hashes(task).items():
        f = workspace / rel
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            changed.append(rel)
    return changed


def run_pytest(workspace: Path, *args: str, timeout: int = GRADE_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def grade(task: Task, workspace: Path) -> Grade:
    """Pass = protected tests unchanged and visible + hidden tests all pass, in a separate copy."""
    tampered = _tampered(task, workspace)
    with tempfile.TemporaryDirectory(prefix=f"mitra-grade-{task.id}-") as tmp:
        copy = Path(tmp) / "ws"
        shutil.copytree(workspace, copy, ignore=IGNORE)
        for test in task.hidden:
            shutil.copy2(test, copy / "tests" / test.name)
        try:
            proc = run_pytest(copy)
        except subprocess.TimeoutExpired:
            return Grade(task.id, False, tampered, None, f"grading timed out after {GRADE_TIMEOUT_S}s")
    out = (proc.stdout + proc.stderr).strip()
    infra = None
    if proc.returncode not in (0, 1):  # 2 = interrupted / collection error, 3+ = pytest internal or usage error
        infra = f"pytest exit code {proc.returncode}"
    return Grade(task.id, proc.returncode == 0 and not tampered, tampered, infra, out[-1500:])


def validate(task: Task) -> list[str]:
    """Problems with a task; empty means the task is sound."""
    problems = []
    with tempfile.TemporaryDirectory(prefix=f"mitra-validate-{task.id}-") as tmp:
        start, solved = Path(tmp) / "start", Path(tmp) / "solved"
        prepare(task, start)
        prepare_solved(task, solved)
        if not task.visible or not task.hidden:
            problems.append("needs at least one visible and one hidden test")
        if run_pytest(start).returncode != 1:
            problems.append("start state: visible tests should fail (exit 1)")
        if grade(task, start).passed:
            problems.append("start state passes grading")
        solved_grade = grade(task, solved)
        if not solved_grade.passed:
            problems.append(f"reference solution fails grading:\n{solved_grade.output_tail}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    v = sub.add_parser("validate")
    v.add_argument("--task")
    p = sub.add_parser("prepare")
    p.add_argument("task")
    p.add_argument("dest", type=Path)
    g = sub.add_parser("grade")
    g.add_argument("task")
    g.add_argument("workspace", type=Path)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252 (task titles use ₹)

    if args.cmd == "list":
        for t in load_tasks():
            print(f"{t.id}  {t.split:<7}  {t.kind:<7}  {t.title}")
        return 0
    if args.cmd == "validate":
        bad = 0
        for t in load_tasks(args.task):
            problems = validate(t)
            print(f"{t.id} {'ok' if not problems else 'FAIL'}  {t.title}")
            for problem in problems:
                print(f"    - {problem}")
            bad += bool(problems)
        return 1 if bad else 0
    if args.cmd == "prepare":
        (task,) = load_tasks(args.task)
        prepare(task, args.dest)
        print(args.dest)
        return 0
    if args.cmd == "grade":
        (task,) = load_tasks(args.task)
        print(json.dumps(grade(task, args.workspace).to_dict(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
