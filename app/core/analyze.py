"""Find what goes wrong in CodeMitra's recorded runs (self-improvement step 2).

Reads the run records (`.codemitra/runs/**/*.jsonl`: chat sessions, `codemitra solve`, plan tasks) and groups problems into
patterns, each with a count and examples. The improve loop works on the top patterns; the dashboard shows them.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "worktrees", "site-packages", "AppData", "Library", "traces"}  # traces are not run records (D-041)

# what each pattern means, and the kind of harness change that could help (the improve loop reads this)
PATTERNS = {
    "repeated_failing_command": "The same shell command failed 3+ times in one turn or task.",
    "tool_error": "A tool call failed (grouped by tool and error).",
    "refused_repeat": "The guard refused an identical call.",
    "guard_stop": "The guard stopped a turn (repeats or failures in a row).",
    "step_limit": "A turn or task hit its step limit without finishing.",
    "declined_edit": "The user said no to a change.",
    "invalid_file": "A written file did not parse (Python, JSON, TOML).",
    "no_tests_after_code": "Code files were written but no tests were run in that turn or task.",
    "tests_never_passed": "Tests were run but never passed by the end.",
    "text_tool_call": "The model wrote a tool call as text.",
    "empty_answer": "A turn ended without an answer.",
    "interrupted": "The user stopped a turn before it finished (esc / ctrl+c): it was going the wrong way or too slow.",
    "model_error": "A model call failed.",
}
CODE_SUFFIXES = (".py", ".js", ".ts", ".html", ".css")
# turns that end without answer text by design (D-068): plan-first shows a plan and a menu, "where did we stop" is
# printed from the records, a stop by you or a failed planner is not the model's empty answer
NO_ANSWER_PATHS = {"plan_first", "resume_brief"}  # an esc stop (stopped_by_user) is your "interrupt" signal row


@dataclass
class Pattern:
    name: str
    count: int = 0
    examples: list[str] = field(default_factory=list)

    def add(self, example: str) -> None:
        self.count += 1
        if len(self.examples) < 5 and example not in self.examples:
            self.examples.append(example[:200])


@dataclass
class Report:
    files: int = 0
    units: int = 0            # turns + tasks
    passed_units: int = 0     # tasks that passed (solve / plan)
    steps: int = 0
    tokens_in: int = 0
    seconds: float = 0.0
    patterns: dict[str, Pattern] = field(default_factory=dict)
    harness_versions: Counter = field(default_factory=Counter)

    def pattern(self, name: str) -> Pattern:
        return self.patterns.setdefault(name, Pattern(name))

    def top(self, n: int = 5) -> list[Pattern]:
        return sorted(self.patterns.values(), key=lambda p: -p.count)[:n]

    def to_json(self) -> dict:
        return {"files": self.files, "units": self.units, "passed_units": self.passed_units, "steps": self.steps,
                "tokens_in": self.tokens_in, "seconds": round(self.seconds),
                "harness_versions": dict(self.harness_versions),
                "patterns": [{"name": p.name, "what": PATTERNS.get(p.name, ""), "count": p.count,
                              "examples": p.examples} for p in self.top(20)]}


def find_run_files(roots: list[Path], max_depth: int = 7) -> list[Path]:
    out: set[Path] = set()  # a set: overlapping roots must not count a record twice
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP and (d == ".codemitra" or not d.startswith("."))]
            parts = Path(dirpath).relative_to(root).parts
            if len(parts) > max_depth:
                dirnames[:] = []
                continue
            if ".codemitra" in parts and "runs" in parts:
                out |= {(Path(dirpath) / f).resolve() for f in filenames if f.endswith(".jsonl")}
    return sorted(out)


def _norm_error(text: str) -> str:
    first = next((ln.strip() for ln in str(text).splitlines() if ln.strip()), "")
    first = re.sub(r"[A-Za-z]:[\\/][^\s'\"]+", "<path>", first)
    first = re.sub(r"\d+", "N", first)
    return first[:120]


def _project(path: Path) -> str:
    """The project folder a record belongs to (the folder holding `.codemitra`, or its slug in the central store)."""
    from app.core import store
    return store.project_of(path)


def file_version(path: Path) -> int | None:
    """The harness version a record file ran with (records from before step 1 ran with the defaults, v0)."""
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("kind") in ("start", "turn_start"):
                    return int(r.get("harness_version") or 0)
    except (OSError, ValueError):
        return None
    return None


def _unit_key(row: dict) -> str:
    return f"turn {row['turn']}" if "turn" in row else "task"


def analyze(files: list[Path], harness_version: int | None = None) -> Report:
    """Patterns in `files`; with `harness_version`, only records made with that version (the problems left now)."""
    if harness_version is not None:
        files = [f for f in files if file_version(f) == harness_version]
    rep = Report(files=len(files))
    for path in files:
        try:
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            continue
        started, ended, paths = [], set(), {}
        units: dict[str, dict] = defaultdict(lambda: {"cmd_fail": Counter(), "code": False, "tests": 0,
                                                     "tests_ok": False, "steps": 0})
        for r in rows:
            kind = r.get("kind")
            u = units[_unit_key(r)]
            where = f"{_project(path)}/{path.name}"
            if kind == "turn_start":
                started.append(r.get("turn"))
                paths[r.get("turn")] = r.get("path")
            elif kind == "turn_end":
                ended.add(r.get("turn"))
            if kind in ("start", "turn_start"):
                rep.harness_versions[str(r.get("harness_version", "?"))] += 1
            elif kind == "model":
                u["steps"] += 1
                rep.steps += 1
                rep.tokens_in += int(r.get("tokens_in") or 0)
            elif kind == "model_error":
                rep.pattern("model_error").add(f"{where}: {_norm_error(r.get('error', ''))}")
            elif kind == "text_tool_calls":
                rep.pattern("text_tool_call").add(f"{where}: {'broken' if r.get('error') else 'recovered'}")
            elif kind == "tool":
                name, out, ok = r.get("name", ""), str(r.get("output", "")), r.get("ok", True)
                cmd = str((r.get("args") or {}).get("command", ""))
                if name in ("write_file", "edit_file") and str((r.get("args") or {}).get("path", "")).endswith(CODE_SUFFIXES):
                    u["code"] = True
                if "⚠" in out and "not valid" in out:
                    rep.pattern("invalid_file").add(f"{where}: {out.split('⚠', 1)[1].strip()[:150]}")
                if name == "run_tests":
                    u["tests"] += 1
                    u["tests_ok"] = u["tests_ok"] or bool(ok)
                if name == "run_command" and "pytest" in cmd:
                    u["tests"] += 1
                    u["tests_ok"] = u["tests_ok"] or bool(ok)
                if out.startswith("✗ Not run:"):
                    rep.pattern("refused_repeat").add(f"{where}: {name} {json.dumps(r.get('args', {}))[:100]}")
                elif "declined" in out and "user" in out.lower():
                    rep.pattern("declined_edit").add(f"{where}: {_norm_error(out)}")
                elif not ok:
                    is_test = name == "run_tests" or (name == "run_command" and "pytest" in cmd)
                    if not is_test:  # failing tests are normal while building
                        rep.pattern("tool_error").add(f"{name}: {_norm_error(out)}")
                    if name == "run_command":
                        u["cmd_fail"][json.dumps(r.get("args", {}), sort_keys=True)] += 1
            elif kind == "tests":
                u["tests"] += 1
                u["tests_ok"] = u["tests_ok"] or bool(r.get("passed"))
            elif kind in ("stopped", "end", "turn_end"):
                reason = str(r.get("reason") or r.get("summary") or "")
                counted = kind == "stopped" or (kind == "end" and r.get("status") != "passed")
                if counted and "step limit" in reason.lower():
                    rep.pattern("step_limit").add(f"{where}: {reason[:120]}")
                elif counted and ("Stopped:" in reason or "kept repeating" in reason or "in a row" in reason):
                    rep.pattern("guard_stop").add(f"{where}: {reason[:120]}")
                if kind == "turn_end" and r.get("interrupted"):
                    rep.pattern("interrupted").add(f"{where}: turn {r.get('turn')} after {r.get('steps', 0)} steps")
                elif kind == "turn_end" and not str(r.get("text") or "").strip() \
                        and paths.get(r.get("turn")) not in NO_ANSWER_PATHS \
                        and r.get("outcome") != "stopped_by_user":
                    rep.pattern("empty_answer").add(f"{where}: turn {r.get('turn')}")
                if kind in ("end", "turn_end"):
                    rep.units += 1
                    rep.seconds += float(r.get("seconds") or 0)
                    if r.get("status") == "passed":
                        rep.passed_units += 1
        # records from before interrupted turns were written: a turn that started and never ended was stopped
        # (the last turn of a file may still be running, so it is left out)
        for t in started[:-1]:
            if t not in ended:
                rep.pattern("interrupted").add(f"{_project(path)}/{path.name}: turn {t} (no end record)")
                rep.units += 1
        for key, u in units.items():
            for cmd, n in u["cmd_fail"].items():
                if n >= 3:
                    rep.pattern("repeated_failing_command").add(f"{n}× {json.loads(cmd).get('command', '')[:120]}")
            if u["code"] and u["tests"] == 0:
                rep.pattern("no_tests_after_code").add(f"{_project(path)}/{path.name} {key}")
            if u["tests"] and not u["tests_ok"]:
                rep.pattern("tests_never_passed").add(f"{_project(path)}/{path.name} {key}")
    return rep


def format_report(rep: Report, n: int = 8) -> str:
    lines = [f"CodeMitra run report: {rep.files} record files, {rep.units} turns/tasks, {rep.steps} model calls, "
             f"{rep.tokens_in:,} prompt tokens, {rep.seconds / 60:.0f} min"]
    if rep.passed_units:
        lines.append(f"Tasks passed: {rep.passed_units}")
    if not rep.patterns:
        lines.append("No problems found.")
    for p in rep.top(n):
        lines.append(f"\n{p.count:4}× {p.name}: {PATTERNS.get(p.name, '')}")
        for ex in p.examples[:3]:
            lines.append(f"       e.g. {ex}")
    return "\n".join(lines)
