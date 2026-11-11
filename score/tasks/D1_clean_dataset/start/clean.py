"""Clean the sign-up rows exported from the form (a list of dicts: name, email, age)."""
import csv


def clean_rows(rows):
    out = []
    for row in rows:
        out.append({k: (v or "").strip() for k, v in row.items()})
    return out


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return clean_rows(list(csv.DictReader(f)))
