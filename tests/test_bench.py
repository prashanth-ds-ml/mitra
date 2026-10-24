"""Tests for the benchmark harness in bench/bench.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

BENCH_PY = Path(__file__).resolve().parents[1] / "bench" / "bench.py"
_spec = importlib.util.spec_from_file_location("mitra_bench", BENCH_PY)
bench = importlib.util.module_from_spec(_spec)
sys.modules["mitra_bench"] = bench
_spec.loader.exec_module(bench)


def test_task_set_shape():
    tasks = bench.load_tasks()
    assert len(tasks) == 10
    assert len({t.id for t in tasks}) == 10
    splits = [t.split for t in tasks]
    assert splits.count("tune") == splits.count("heldout") == 5


@pytest.mark.parametrize("task", bench.load_tasks(), ids=lambda t: t.id)
def test_task_is_valid(task):
    assert bench.validate(task) == []


def test_hidden_tests_never_in_workspace(tmp_path):
    for task in bench.load_tasks():
        ws = tmp_path / task.id
        bench.prepare(task, ws)
        names = {p.name for p in (ws / "tests").iterdir()}
        assert not names & {p.name for p in task.hidden}


def test_editing_a_visible_test_is_tampering(tmp_path):
    (task,) = bench.load_tasks("T03")
    ws = tmp_path / "ws"
    bench.prepare_solved(task, ws)
    visible = ws / "tests" / task.visible[0].name
    visible.write_text(visible.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    result = bench.grade(task, ws)
    assert not result.passed
    assert result.tampered == [f"tests/{visible.name}"]


def test_deleting_a_base_test_is_tampering(tmp_path):
    (task,) = bench.load_tasks("T01")
    ws = tmp_path / "ws"
    bench.prepare_solved(task, ws)
    (ws / "tests" / "test_smoke.py").unlink()
    assert bench.grade(task, ws).tampered == ["tests/test_smoke.py"]


def test_grading_does_not_touch_the_workspace(tmp_path):
    (task,) = bench.load_tasks("T02")
    ws = tmp_path / "ws"
    bench.prepare(task, ws)
    before = sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*") if "__pycache__" not in p.parts)
    bench.grade(task, ws)
    after = sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*") if "__pycache__" not in p.parts)
    assert before == after


def test_break_must_match_exactly_once(tmp_path):
    (task,) = bench.load_tasks("T01")
    broken = bench.Task(**{**task.__dict__, "breaks": [{"file": "shop/app.py", "old": "no such text", "new": ""}]})
    with pytest.raises(ValueError, match="found 0 times"):
        bench.prepare(broken, tmp_path / "ws")


def test_prepare_refuses_non_empty_dest(tmp_path):
    (task,) = bench.load_tasks("T01")
    (tmp_path / "ws").mkdir()
    (tmp_path / "ws" / "x").write_text("x")
    with pytest.raises(FileExistsError):
        bench.prepare(task, tmp_path / "ws")
