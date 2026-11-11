from pathlib import Path

from clean import clean_rows, load


def r(name, email, age):
    return {"name": name, "email": email, "age": age}


def test_drops_rows_without_a_usable_email():
    rows = clean_rows([r("a", "", "1"), r("b", "   ", "2"), r("c", "not-an-email", "3"), r("d", "d@x.io", "4")])
    assert [x["name"] for x in rows] == ["d"]


def test_keeps_the_first_of_duplicate_emails_in_order():
    rows = clean_rows([r("z", "z@x.io", "1"), r("a", "A@x.io", "2"), r("a2", " a@X.io", "3"), r("m", "m@x.io", "4")])
    assert [x["name"] for x in rows] == ["z", "a", "m"]


def test_age_is_an_int_or_none():
    rows = clean_rows([r("a", "a@x.io", " 31 "), r("b", "b@x.io", "twenty"), r("c", "c@x.io", ""),
                       r("d", "d@x.io", "30.5"), r("e", "e@x.io", None)])
    assert [x["age"] for x in rows] == [31, None, None, None, None]


def test_the_csv_file():
    rows = load(Path(__file__).resolve().parents[1] / "signups.csv")
    assert rows == [{"name": "Asha", "email": "asha@example.com", "age": 31},
                    {"name": "Ravi", "email": "ravi@example.com", "age": None},
                    {"name": "Meena", "email": "meena@example.com", "age": 27}]
