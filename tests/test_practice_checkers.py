"""D-078 Phase 2 step 5a: the two practice checkers (Python hidden tests, SQL result rows) and the fixed split."""
import sqlite3

import pytest

from app.core import practice as P

# MBPP+ style: hidden inputs and results, checked with an assertion helper
MBPP_TEST = """
def assertion(out, exp, atol):
    assert out == exp, f"{out!r} != {exp!r}"

inputs = [[1, 2], [0, 0], [-3, 5]]
results = [3, 0, 2]
for inp, exp in zip(inputs, results):
    assertion(add(*inp), exp, 0)
"""
# HumanEval+ style: a check(candidate) function and a call
HE_TEST = "def check(candidate):\n    assert candidate('abc') == 'cba'\n    assert candidate('') == ''\n"


# ── python ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_correct_python_solution_passes_both_test_styles():
    assert P.check_python("def add(a, b):\n    return a + b\n", MBPP_TEST).passed
    assert P.check_python("def rev(s):\n    return s[::-1]\n", HE_TEST, "check(rev)").passed


def test_a_wrong_solution_fails_with_the_reason():
    c = P.check_python("def add(a, b):\n    return a - b\n", MBPP_TEST)
    assert not c.passed and "-1 != 3" in c.detail


def test_broken_or_endless_code_fails_cleanly():
    assert "SyntaxError" in P.check_python("def add(a, b)\n    return a+b\n", MBPP_TEST).detail
    c = P.check_python("def add(a, b):\n    while True:\n        pass\n", MBPP_TEST, timeout_s=2)
    assert not c.passed and "timed out" in c.detail


def test_a_solution_that_reads_input_at_import_does_not_hang():
    c = P.check_python("x = input()\ndef add(a, b):\n    return a + b\n", MBPP_TEST, timeout_s=5)
    assert not c.passed and "EOF" in c.detail


# ── sql ────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    p = tmp_path / "concert.sqlite"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE singer (id INTEGER PRIMARY KEY, name TEXT, country TEXT, age INTEGER);
        INSERT INTO singer VALUES (1,'Joe','France',52),(2,'Tim','US',29),(3,'Ann','France',41),(4,'Lia','US',29);
    """)
    con.commit()
    con.close()
    return p


def test_an_equivalent_query_passes_in_any_row_order(db):
    gold = "SELECT name FROM singer WHERE country = 'France'"
    assert P.check_sql(db, "select s.name from singer as s where s.country='France';", gold).passed
    assert P.check_sql(db, "```sql\nSELECT name FROM singer WHERE country = 'France' ORDER BY name DESC\n```",
                       gold).passed                                          # fences and order don't matter here


def test_order_counts_when_the_reference_sorts(db):
    gold = "SELECT name FROM singer ORDER BY age"
    assert P.check_sql(db, "SELECT name FROM singer ORDER BY age, id", gold).passed
    c = P.check_sql(db, "SELECT name FROM singer ORDER BY name", gold)
    assert not c.passed and "want 4" in c.detail


def test_wrong_rows_counts_and_averages_are_compared(db):
    assert P.check_sql(db, "SELECT avg(age) FROM singer WHERE country='US'",
                       "SELECT AVG(age) FROM singer WHERE country = 'US'").passed
    assert not P.check_sql(db, "SELECT count(*) FROM singer", "SELECT count(*) FROM singer WHERE age > 30").passed


def test_only_one_read_only_query_is_run_and_the_database_is_never_changed(db):
    c = P.check_sql(db, "DELETE FROM singer", "SELECT count(*) FROM singer")
    assert not c.passed and "only a SELECT" in c.detail
    c = P.check_sql(db, "SELECT 1; DROP TABLE singer", "SELECT 1")
    assert not c.passed and "one query only" in c.detail
    c = P.check_sql(db, "WITH x AS (SELECT 1) UPDATE singer SET age = 0", "SELECT 1")
    assert not c.passed                                                       # read-only connection refuses it
    assert P.run_sql(db, "SELECT count(*) FROM singer WHERE age > 0") == [(4,)]


def test_a_runaway_query_times_out(db):
    endless = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT count(*) FROM n"
    c = P.check_sql(db, endless, "SELECT 1", timeout_s=1)
    assert not c.passed and "timed out" in c.detail


def test_a_query_error_is_a_failed_task_with_the_reason(db):
    c = P.check_sql(db, "SELECT nme FROM singer", "SELECT name FROM singer")
    assert not c.passed and "no such column" in c.detail


# ── the split ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_split_is_fixed_and_about_thirty_percent_held_out():
    ids = [f"mbpp/{i}" for i in range(1000)]
    held = sum(P.split_of(i) == "held_out" for i in ids)
    assert 250 < held < 350
    assert P.split_of("mbpp/12") == P.split_of("mbpp/12")
    assert P.Task("mbpp/12", "python", "MBPP+", "Apache-2.0", "x").split == P.split_of("mbpp/12")
