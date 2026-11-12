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


# ── the datasets (step 5a): downloaded once, kept in ~/.mitra/practice, so practice also works offline ────────────

SOURCES = {
    "mbpp": {"url": "https://github.com/evalplus/mbppplus_release/releases/download/v0.2.0/MbppPlus.jsonl.gz",
             "name": "MBPP+ (EvalPlus v0.2.0)", "licence": "Apache-2.0 (EvalPlus); MBPP by Google Research"},
    "humaneval": {"url": "https://github.com/evalplus/humanevalplus_release/releases/download/v0.1.10/"
                         "HumanEvalPlus.jsonl.gz",
                  "name": "HumanEval+ (EvalPlus v0.1.10)", "licence": "Apache-2.0 (EvalPlus); HumanEval by OpenAI"},
    "spider": {"url": "https://drive.usercontent.google.com/download?id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J"
                      "&export=download&confirm=t",
               "sha256": "00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b",
               "name": "Spider 1.0 (Yale LILY, dev set)", "licence": "CC BY-SA 4.0 (kept on this machine only)"},
}
PYTHON_TASKS = 100        # v1 sample (fixed by hash): from 542
SQL_TASKS = 50            # v1 sample (fixed by hash): from Spider's 1,034 dev questions
PLUS_INPUTS = 50          # hidden inputs per Python task beyond the base ones (keeps a check under the time limit)
DOWNLOAD_TIMEOUT_S = 600


def home() -> Path:
    from app.core import harness as H
    return H.home() / "practice"


def _pick(ids: list[str], n: int) -> set[str]:
    """A fixed sample: the n ids with the smallest hash (the same every time, spread over the set)."""
    return set(sorted(ids, key=lambda i: hashlib.sha1(("pick:" + i).encode()).hexdigest())[:n])


def evalplus_test(row: dict) -> tuple[str, str]:
    """(hidden test code, call) for an EvalPlus row: the reference solution (renamed) and Mitra's function run on the
    same inputs, results compared (a float tolerance; as sets when the task's own example compares sets)."""
    entry = row["entry_point"]
    ref_src = re.sub(rf"\b{re.escape(entry)}\b", "_mitra_ref", reference(row))
    inputs = (row.get("base_input") or []) + (row.get("plus_input") or [])[:PLUS_INPUTS]
    as_set = bool(re.search(rf"set\(\s*{re.escape(entry)}\(", row.get("prompt", "") + row.get("assertion", "")))
    atol = float(row.get("atol") or 0)
    test = (ref_src + "\n\nimport copy as _copy, math as _math\n"
            f"_INPUTS = {inputs!r}\n_ATOL = {atol!r}\n_AS_SET = {as_set!r}\n"
            "def _same(a, b):\n"
            "    if isinstance(a, float) or isinstance(b, float):\n"
            "        try:\n"
            "            return _math.isclose(a, b, rel_tol=1e-6, abs_tol=max(_ATOL, 1e-6))\n"
            "        except TypeError:\n"
            "            return False\n"
            "    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):\n"
            "        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))\n"
            "    return a == b\n"
            "def _check(fn):\n"
            "    for i, inp in enumerate(_INPUTS):\n"
            "        want = _mitra_ref(*_copy.deepcopy(inp))\n"
            "        got = fn(*_copy.deepcopy(inp))\n"
            "        ok = set(got) == set(want) if _AS_SET else _same(got, want)\n"
            "        assert ok, f'input {i}: got {got!r:.200}, want {want!r:.200}'\n")
    return test, f"_check({entry})"


def reference(row: dict) -> str:
    """The dataset's own solution as a whole module (HumanEval keeps the signature in the prompt)."""
    code = row["canonical_solution"]
    return code if f"def {row['entry_point']}(" in code else row["prompt"] + code


def python_prompt(row: dict, source: str) -> str:
    entry = row["entry_point"]
    spec = row["prompt"].strip()
    if source == "mbpp":
        spec = spec.strip('"').strip()
    return (f"Practice task. Write a Python function `{entry}` in solution.py:\n\n{spec}\n\n"
            f"Keep the name `{entry}` and its arguments. Also write your own tests in test_solution.py (the example, "
            "normal cases and edge cases such as empty input), run them, and fix the code until they pass.")


def sql_prompt(question: str, db_id: str, schema: str) -> str:
    return (f"Practice task. Write one SQLite query that answers:\n\n{question}\n\nThe database `{db_id}` is the file "
            f"database.sqlite in this folder. Its tables:\n\n{schema}\n\nReturn only the columns the question asks "
            "for, in that order. Save only the query in query.sql (one SELECT). You may write test_query.py that runs it with sqlite3 and checks the result, and fix it until it "
            "is right.")


def schema_text(db: Path) -> str:
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL").fetchall()
    finally:
        con.close()
    return "\n".join(" ".join(r[0].split()) + ";" for r in rows)


def python_tasks(rows: list[dict], source: str) -> list[Task]:
    meta = SOURCES[source]
    out = []
    for r in rows:
        test, call = evalplus_test(r)
        out.append(Task(f"{source}/{r['task_id'].split('/')[-1]}", "python", meta["name"], meta["licence"],
                        python_prompt(r, source), test=test, call=call, extra={"entry": r["entry_point"]}))
    return out


def sql_tasks(examples: list[dict], db_dir: Path) -> list[Task]:
    meta, out, schemas = SOURCES["spider"], [], {}
    for i, e in enumerate(examples):
        db = Path(db_dir) / e["db_id"] / f"{e['db_id']}.sqlite"
        if not db.exists():
            continue
        if e["db_id"] not in schemas:
            schemas[e["db_id"]] = schema_text(db)
        out.append(Task(f"spider/{e['db_id']}/{e.get('n', i)}", "sql", meta["name"], meta["licence"],
                        sql_prompt(e["question"], e["db_id"], schemas[e["db_id"]]), db=str(db), gold=e["query"]))
    return out


def _fetch(url: str, dest: Path, timeout_s: float = DOWNLOAD_TIMEOUT_S) -> Path:
    import urllib.request
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mitra"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp, dest.open("wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    return dest


def build(dest: Path | None = None, say=lambda t: None, fetch=_fetch) -> dict:
    """Download the sets (once), check Spider's checksum, keep the sample's tasks in tasks.jsonl and only the Spider
    databases they use. Returns {"python": n, "sql": n, "dir": path}."""
    import gzip
    import json
    import zipfile
    from dataclasses import asdict

    dest = Path(dest) if dest else home()
    raw = dest / "raw"
    py_rows: dict[str, list] = {}
    for src in ("mbpp", "humaneval"):
        f = raw / f"{src}.jsonl.gz"
        if not f.exists():
            say(f"downloading {SOURCES[src]['name']}…")
            fetch(SOURCES[src]["url"], f)
        py_rows[src] = [json.loads(x) for x in gzip.open(f, "rt", encoding="utf-8") if x.strip()]
    z = raw / "spider.zip"
    if not z.exists():
        say(f"downloading {SOURCES['spider']['name']} (about 200 MB)…")
        fetch(SOURCES["spider"]["url"], z)
    if hashlib.sha256(z.read_bytes()).hexdigest() != SOURCES["spider"]["sha256"]:
        z.unlink()
        raise RuntimeError("the Spider download does not match its published checksum; deleted, try again")
    with zipfile.ZipFile(z) as zf:
        examples = json.loads(zf.read("spider_data/dev.json"))
        for i, e in enumerate(examples):
            e["n"] = i
        keep_sql = _pick([f"spider/{e['db_id']}/{e['n']}" for e in examples], SQL_TASKS)
        chosen = [e for e in examples if f"spider/{e['db_id']}/{e['n']}" in keep_sql]
        db_dir = dest / "spider"
        for db_id in {e["db_id"] for e in chosen}:
            target = db_dir / db_id / f"{db_id}.sqlite"
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(f"spider_data/database/{db_id}/{db_id}.sqlite"))
    every = python_tasks(py_rows["mbpp"], "mbpp") + python_tasks(py_rows["humaneval"], "humaneval")
    refs = {f"{s}/{r['task_id'].split('/')[-1]}": reference(r) for s in py_rows for r in py_rows[s]}
    py, dropped = [], []
    for t in sorted(every, key=lambda x: hashlib.sha1(("pick:" + x.id).encode()).hexdigest()):
        if len(py) >= PYTHON_TASKS:
            break
        if check_python(refs[t.id], t.test, t.call).passed:  # a task its own reference cannot pass is dropped
            py.append(t)
        else:
            dropped.append(t.id)
    sql = [t for t in sql_tasks(chosen, db_dir) if check_sql(t.db, t.gold, t.gold).passed]
    if dropped:
        say(f"left out {len(dropped)} task(s) whose reference fails its own check: {', '.join(dropped)}")
    tasks = py + sql
    (dest / "tasks.jsonl").write_text("\n".join(json.dumps(asdict(t)) for t in tasks) + "\n", encoding="utf-8")
    (dest / "CREDITS.md").write_text(
        "# Practice sets\n\n" + "\n".join(f"- {m['name']}: {m['licence']} · {m['url'].split('?')[0]}"
                                          for m in SOURCES.values()) + "\n", encoding="utf-8")
    n_py, n_sql = sum(t.kind == "python" for t in tasks), sum(t.kind == "sql" for t in tasks)
    say(f"practice set ready: {n_py} Python + {n_sql} SQL tasks in {dest}")
    return {"python": n_py, "sql": n_sql, "dir": str(dest)}


def load(dest: Path | None = None, kind: str = "", split: str = "") -> list[Task]:
    import json
    f = Path(dest or home()) / "tasks.jsonl"
    try:
        tasks = [Task(**json.loads(x)) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    except OSError:
        return []
    return [t for t in tasks if (not kind or t.kind == kind) and (not split or t.split == split)]
