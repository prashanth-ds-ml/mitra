"""D-078 step 5b: `mitra practice` runs Mitra's own chat loop on a task in a fresh folder, then the hidden check decides;
a task its own tests pass but the hidden check fails is "misread". Also E-122 (phase names leaked to the user) and
the terminal-command hint for "mitra practice" typed in the chat."""
import json
import sqlite3

from langchain_core.messages import AIMessage

from app.core import chat as C
from app.core import harness as H
from app.core import intent
from app.core import practice as P
from app.core import score as S
from tests.test_chat_core import tc
from tests.test_trust_d077 import Spy

ADD = P.Task("mbpp/1", "python", "MBPP+", "Apache-2.0", "Write a Python function `add` in solution.py ...",
             test="def _check(fn):\n    for a, b in [(1, 2), (0, 0), (-3, 5)]:\n        assert fn(a, b) == a + b\n",
             call="_check(add)")
OWN_TEST = "from solution import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"


def _runner(tmp_path, m):
    return S.Runner(llm=m, harness=H.Harness(), num_ctx=8192, records=tmp_path / "records", arch="phased")


def _solves(code, own_test=OWN_TEST):
    return Spy(AIMessage(content="", tool_calls=[tc("make_change", 1, what="write add")]),
               AIMessage(content="", tool_calls=[tc("write_file", 2, path="solution.py", content=code)]),
               AIMessage(content="", tool_calls=[tc("write_file", 3, path="test_solution.py", content=own_test)]),
               AIMessage(content="Wrote add in solution.py; my test passes."))


def test_a_solved_task_passes_the_hidden_check(tmp_path):
    r = P.solve(ADD, _runner(tmp_path, _solves("def add(a, b):\n    return a + b\n")))
    assert r.passed and r.own_tests and r.own_ok is True and not r.misread
    assert (tmp_path / "records" / "mbpp_1.jsonl").exists()                  # recorded like a score case


def test_own_tests_passing_but_hidden_failing_is_a_misread(tmp_path):
    wrong = "def add(a, b):\n    return 3 if (a, b) == (1, 2) else a * b\n"     # fits its own single test only
    r = P.solve(ADD, _runner(tmp_path, _solves(wrong)))
    assert not r.passed and r.own_ok is True and r.misread
    assert "AssertionError" in r.detail


def test_no_solution_file_fails_plainly(tmp_path):
    r = P.solve(ADD, _runner(tmp_path, Spy(AIMessage(content="I would write add like this: a + b."))))
    assert not r.passed and r.detail == "no solution.py" and not r.own_tests


def test_a_sql_task_is_checked_on_the_original_database(tmp_path):
    db = tmp_path / "concert.sqlite"
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE singer (name TEXT, age INTEGER); INSERT INTO singer VALUES ('Joe',52),('Tim',29);")
    con.commit()
    con.close()
    task = P.Task("spider/concert/0", "sql", "Spider", "CC BY-SA 4.0", "How many singers?", db=str(db),
                  gold="SELECT count(*) FROM singer")
    m = Spy(AIMessage(content="", tool_calls=[tc("make_change", 1, what="query")]),
            AIMessage(content="", tool_calls=[tc("write_file", 2, path="query.sql",
                                                  content="SELECT COUNT(*) FROM singer;\n")]),
            AIMessage(content="Saved the query in query.sql."))
    r = P.solve(task, _runner(tmp_path, m))
    assert r.passed and r.kind == "sql"


def test_a_run_writes_one_row_and_a_report(tmp_path):
    out = tmp_path / "practice.jsonl"
    row = P.run([ADD], _runner(tmp_path, _solves("def add(a, b):\n    return a + b\n")), model="m", results=out)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["summary"]["all"] == [1, 1] and saved["results"][0]["id"] == "mbpp/1"
    assert "Write a Python function" not in out.read_text(encoding="utf-8")   # ids and outcomes only, no task text
    assert "practice: 1/1 passed · python 1/1" in P.report(row)


def test_the_order_is_fixed_and_mixes_kinds():
    tasks = [P.Task(f"mbpp/{i}", "python", "", "", "") for i in range(30)] + \
            [P.Task(f"spider/db/{i}", "sql", "", "", "") for i in range(30)]
    first = P.order(tasks)[:20]
    assert [t.id for t in first] == [t.id for t in P.order(list(reversed(tasks)))[:20]]
    assert {t.kind for t in first} == {"python", "sql"}


# ── E-122 and the chat hint ────────────────────────────────────────────────────────────────────────────────────

def test_the_phase_names_are_never_named_to_the_user():
    """E-122 (live 2026-11-12): "ask what you want to do (e.g., look_at_code, look_up, make_change, or just chat)"."""
    assert "never name them to the user" in C.PHASED_PROMPT


def test_mitra_practice_typed_in_the_chat_gets_the_terminal_hint():
    assert intent.terminal_command("mitra practice")
    assert intent.terminal_command("mitra practice --download")
