"""D-078 step 5a: building the practice set from the downloaded files (here: tiny offline copies in the same
formats): EvalPlus rows become Python tasks checked against the dataset's own solution; Spider questions become SQL
tasks; a task its own reference cannot pass is left out (live: mbpp/580 tuples stored as lists, mbpp/794 re.Match)."""
import gzip
import hashlib
import json
import sqlite3
import zipfile

import pytest

from app.core import practice as P

MBPP_ROWS = [
    {"task_id": "Mbpp/1", "prompt": '"""\nWrite a function to add two numbers.\nassert add(1, 2) == 3\n"""\n',
     "entry_point": "add", "canonical_solution": "def add(a, b):\n    return a + b\n",
     "base_input": [[1, 2], [0, 0]], "plus_input": [[-1, 5]], "atol": 0, "assertion": "assert add(1, 2) == 3\n"},
    {"task_id": "Mbpp/2", "prompt": '"""\nWrite a function for the shared elements.\n'
                                    'assert set(shared((3, 4), (4, 5))) == set((4,))\n"""\n',
     "entry_point": "shared", "canonical_solution": "def shared(a, b):\n    return tuple(set(a) & set(b))\n",
     "base_input": [[[3, 4, 5], [5, 4, 9]]], "plus_input": [], "atol": 0, "assertion": ""},
    {"task_id": "Mbpp/3", "prompt": '"""\nWrite a broken one.\n"""\n', "entry_point": "broken",
     "canonical_solution": "def broken(x):\n    return x % 2\n", "base_input": [[[1, 2]]], "plus_input": [],
     "atol": 0, "assertion": ""},
]
HE_ROWS = [{"task_id": "HumanEval/0", "prompt": 'def rev(s: str) -> str:\n    """Reverse s.\n    >>> rev("ab")\n'
                                                '    \'ba\'\n    """\n',
            "entry_point": "rev", "canonical_solution": "    return s[::-1]\n", "base_input": [["ab"], [""]],
            "plus_input": [["abc"]], "atol": 0}]


def _gz(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows))


@pytest.fixture
def files(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    _gz(src / "mbpp.jsonl.gz", MBPP_ROWS)
    _gz(src / "he.jsonl.gz", HE_ROWS)
    db = src / "concert.sqlite"
    con = sqlite3.connect(db)
    con.executescript("CREATE TABLE singer (id INTEGER, name TEXT, age INTEGER);"
                      "INSERT INTO singer VALUES (1,'Joe',52),(2,'Tim',29);")
    con.commit()
    con.close()
    with zipfile.ZipFile(src / "spider.zip", "w") as z:
        z.writestr("spider_data/dev.json", json.dumps([
            {"db_id": "concert", "question": "How many singers are there?", "query": "SELECT count(*) FROM singer"},
            {"db_id": "concert", "question": "Names of singers older than 40?",
             "query": "SELECT name FROM singer WHERE age > 40"}]))
        z.write(db, "spider_data/database/concert/concert.sqlite")
    sources = {k: dict(v) for k, v in P.SOURCES.items()}
    sources["spider"]["sha256"] = hashlib.sha256((src / "spider.zip").read_bytes()).hexdigest()
    monkeypatch.setattr(P, "SOURCES", sources)
    monkeypatch.setattr(P, "PYTHON_TASKS", 10)
    monkeypatch.setattr(P, "SQL_TASKS", 10)
    by_url = {sources["mbpp"]["url"]: src / "mbpp.jsonl.gz", sources["humaneval"]["url"]: src / "he.jsonl.gz",
              sources["spider"]["url"]: src / "spider.zip"}

    def fetch(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(by_url[url].read_bytes())
        return dest
    return fetch


def test_the_set_is_built_and_every_kept_reference_passes(tmp_path, files):
    said = []
    got = P.build(tmp_path / "practice", say=said.append, fetch=files)
    assert got["python"] == 3 and got["sql"] == 2                         # mbpp/3's reference crashes: left out
    assert any("mbpp/3" in s for s in said)
    tasks = {t.id: t for t in P.load(tmp_path / "practice")}
    assert set(tasks) == {"mbpp/1", "mbpp/2", "humaneval/0", "spider/concert/0", "spider/concert/1"}
    assert "Write a Python function `add` in solution.py" in tasks["mbpp/1"].prompt
    assert "CREATE TABLE singer" in tasks["spider/concert/0"].prompt
    assert (tmp_path / "practice" / "CREDITS.md").read_text(encoding="utf-8").count("Apache-2.0") == 2
    assert P.load(tmp_path / "practice", kind="sql") and all(
        t.kind == "sql" for t in P.load(tmp_path / "practice", kind="sql"))


def test_the_hidden_check_compares_with_the_reference(tmp_path, files):
    P.build(tmp_path / "practice", fetch=files)
    tasks = {t.id: t for t in P.load(tmp_path / "practice")}
    add, shared, rev = tasks["mbpp/1"], tasks["mbpp/2"], tasks["humaneval/0"]
    assert P.check_python("def add(a, b):\n    return b + a\n", add.test, add.call).passed
    assert not P.check_python("def add(a, b):\n    return a * b\n", add.test, add.call).passed
    assert P.check_python("def shared(a, b):\n    return [x for x in b if x in a]\n", shared.test,
                          shared.call).passed                              # compared as sets, like its example
    assert P.check_python("def rev(s):\n    return ''.join(reversed(s))\n", rev.test, rev.call).passed


def test_a_bad_spider_download_is_refused(tmp_path, files, monkeypatch):
    sources = {k: dict(v) for k, v in P.SOURCES.items()}
    sources["spider"]["sha256"] = "0" * 64
    monkeypatch.setattr(P, "SOURCES", sources)
    with pytest.raises(RuntimeError, match="checksum"):
        P.build(tmp_path / "practice", fetch=files)
    assert not (tmp_path / "practice" / "raw" / "spider.zip").exists()
