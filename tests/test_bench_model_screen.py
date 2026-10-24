"""Tests for the scoring in bench/model_screen.py (no model needed)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bench" / "model_screen.py"
_spec = importlib.util.spec_from_file_location("mitra_model_screen", _PATH)
ms = importlib.util.module_from_spec(_spec)
sys.modules["mitra_model_screen"] = ms
_spec.loader.exec_module(ms)

CASES = {c.id: c for c in ms.cases()}


def _call(name, args):
    return {"content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def test_twelve_cases_serialisable():
    assert len(CASES) == 12
    for case in CASES.values():
        json.dumps(case.messages)


def test_exact_edit_passes_and_near_miss_fails():
    case = CASES["C04"]
    good = {"path": "shop/payments.py", "old": 'key = f"order-{order.id}"', "new": 'key = f"order-{order.id}-v2"'}
    assert ms.score(case, _call("str_replace", good)) == (True, "ok")
    near = good | {"old": "key = f'order-{order.id}'"}
    passed, why = ms.score(case, _call("str_replace", near))
    assert not passed and "old not exact" in why


def test_arguments_as_json_string_are_accepted():
    assert ms.score(CASES["C01"], _call("read_file", json.dumps({"path": "shop/payments.py"})))[0]


def test_text_tool_call_is_not_native():
    msg = {"content": '{"name": "read_file", "arguments": {"path": "shop/payments.py"}}'}
    passed, why = ms.score(CASES["C01"], msg)
    assert not passed and "as text" in why


def test_wrong_tool_and_missing_arg():
    assert "wrong tool" in ms.score(CASES["C03"], _call("read_file", {"path": "x"}))[1]
    assert "missing argument" in ms.score(CASES["C01"], _call("read_file", {}))[1]


def test_no_tool_case():
    assert ms.score(CASES["C08"], {"content": "A key that makes retries safe."})[0]
    assert not ms.score(CASES["C08"], _call("search", {"pattern": "x"}))[0]


def test_long_prompt_case_is_long():
    chars = sum(len(json.dumps(m)) for m in CASES["C09"].messages)
    assert chars > 40_000  # roughly 10K tokens
