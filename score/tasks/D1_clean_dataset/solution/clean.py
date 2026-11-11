"""Clean the sign-up rows exported from the form (a list of dicts: name, email, age)."""
import csv


def _age(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_rows(rows):
    out, seen = [], set()
    for row in rows:
        row = {k: (v or "").strip() for k, v in row.items()}
        email = row.get("email", "").lower()
        if "@" not in email or email in seen:
            continue
        seen.add(email)
        row["email"] = email
        row["age"] = _age(row.get("age"))
        out.append(row)
    return out


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return clean_rows(list(csv.DictReader(f)))
