"""The coding practice set (D-078 Phase 2, step 5; must-have 10): small Python and SQL tasks with hidden checks, so
Mitra can be measured (and later learn) on hundreds of tasks instead of 23 cases.

    python  -> Mitra writes solution.py (and its own tests); the hidden tests (MBPP+ / HumanEval+ style) run against it
               in a separate process with a time limit
    sql     -> Mitra writes query.sql for a SQLite database; it and the reference query run on a read-only connection
               and their result rows are compared (in order only when the reference sorts)

The hidden checks and their output never reach Mitra: they go to the records and the report only. Each task's split
(learn / held_out) is fixed by a hash of its id, so it never changes between runs. MongoDB comes later (our own tasks).
"""
from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

PY_TIMEOUT_S = 30
SQL_TIMEOUT_S = 10
HELD_OUT_PERCENT = 30
DETAIL_CHARS = 600


@dataclass
class Task:
    id: str                 # e.g. "mbpp/12", "spider/concert_singer/3"
    kind: str               # "python" or "sql"
    source: str             # dataset name, for the credit and the report
    licence: str
    prompt: str             # what Mitra is given: the question and the examples
    test: str = ""          # python: the hidden test code
    call: str = ""          # python: the line that runs it, e.g. "check(add)"
    db: str = ""            # sql: path to the .sqlite file
    gold: str = ""          # sql: the reference query
    extra: dict = field(default_factory=dict)

    @property
    def split(self) -> str:
        return split_of(self.id)


@dataclass
class Check:
    passed: bool
    detail: str = ""        # why it failed (records and report only; never shown to Mitra)
    seconds: float = 0.0


def split_of(task_id: str) -> str:
    """"held_out" for about 30% of tasks, fixed by the id's hash: the same task is always on the same side."""
    n = int(hashlib.sha1(task_id.encode("utf-8")).hexdigest(), 16) % 100
    return "held_out" if n < HELD_OUT_PERCENT else "learn"


def _tail(text: str) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return "\n".join(lines[-8:])[-DETAIL_CHARS:]


# ── python ─────────────────────────────────────────────────────────────────────────────────────────────────────

def check_python(solution: str, test: str, call: str = "", timeout_s: float = PY_TIMEOUT_S) -> Check:
    """Run the hidden `test` (plus `call`) against `solution` in a fresh Python process in a temporary folder."""
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="mitra-practice-") as tmp:
        d = Path(tmp)
        (d / "solution.py").write_text(solution, encoding="utf-8")
        runner = ("import sys\nsys.path.insert(0, " + repr(str(d)) + ")\nfrom solution import *\n\n"
                  + test + "\n\n" + (call or "") + "\n")
        (d / "hidden_check.py").write_text(runner, encoding="utf-8")
        try:
            p = subprocess.run([sys.executable, "-I", str(d / "hidden_check.py")], cwd=d, capture_output=True,
                               stdin=subprocess.DEVNULL,  # input() gets EOF at once, never the user's terminal
                               text=True, encoding="utf-8", errors="replace", timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return Check(False, f"timed out after {timeout_s:.0f} s", round(time.monotonic() - t0, 2))
    seconds = round(time.monotonic() - t0, 2)
    if p.returncode == 0:
        return Check(True, "", seconds)
    return Check(False, _tail(p.stderr or p.stdout) or f"exit code {p.returncode}", seconds)


# ── sql ────────────────────────────────────────────────────────────────────────────────────────────────────────

_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_READ_ONLY_START = re.compile(r"^\s*(select|with)\b", re.I)
_ORDER_BY = re.compile(r"\border\s+by\b", re.I)


def clean_sql(sql: str) -> str:
    """The query without comments, a trailing semicolon or ``` fences (a model often adds them)."""
    s = re.sub(r"^```\w*\s*|```\s*$", "", (sql or "").strip(), flags=re.M)
    s = _COMMENTS.sub(" ", s).strip()
    return s[:-1].strip() if s.endswith(";") else s


def run_sql(db: str | Path, sql: str, timeout_s: float = SQL_TIMEOUT_S) -> list[tuple]:
    """Run one read-only query; raises ValueError (not a query, several statements) or sqlite3.Error."""
    q = clean_sql(sql)
    if not _READ_ONLY_START.match(q):
        raise ValueError("only a SELECT (or WITH … SELECT) query is checked")
    if ";" in q:
        raise ValueError("one query only (found a ';' inside)")
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    deadline = time.monotonic() + timeout_s
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        return con.execute(q).fetchall()
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc):
            raise sqlite3.OperationalError(f"timed out after {timeout_s:.0f} s") from exc
        raise
    finally:
        con.close()


def _norm(value):
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return round(value, 6) if not value.is_integer() else int(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _rows(rows: list[tuple]) -> list[tuple]:
    return [tuple(_norm(v) for v in r) for r in rows]


def check_sql(db: str | Path, sql: str, gold: str, timeout_s: float = SQL_TIMEOUT_S) -> Check:
    """Mitra's query passes when it returns the same rows as the reference: as a multiset, or in the same order when
    the reference has ORDER BY. Column order counts (the question says what to show)."""
    t0 = time.monotonic()
    try:
        want = _rows(run_sql(db, gold, timeout_s))
    except Exception as exc:  # noqa: BLE001 - a broken reference is the task's fault, said plainly
        return Check(False, f"the reference query failed: {exc}", 0.0)
    try:
        got = _rows(run_sql(db, sql, timeout_s))
    except Exception as exc:  # noqa: BLE001 - Mitra's query does not run: a failed task with the reason
        return Check(False, f"query error: {exc}", round(time.monotonic() - t0, 2))
    seconds = round(time.monotonic() - t0, 2)
    same = got == want if _ORDER_BY.search(clean_sql(gold)) else Counter(got) == Counter(want)
    if same:
        return Check(True, "", seconds)
    return Check(False, f"{len(got)} rows, want {len(want)}; first got {got[:2]}, want {want[:2]}"[:DETAIL_CHARS],
                 seconds)
