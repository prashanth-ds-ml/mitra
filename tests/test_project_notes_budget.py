"""Project notes (AGENTS.md, CLAUDE.md, ...) share one 12,000-byte budget."""

import pathlib

from app.config import (
    PROJECT_NOTES_BUDGET_BYTES,
    _NOTES_CUT_LINE,
    _apply_notes_budget,
    load,
)

MITRA_NOTES = str(pathlib.Path(".mitra") / "instructions.md")
COPILOT_NOTES = str(pathlib.Path(".github") / "copilot-instructions.md")


def _lines(prefix: str, n_bytes: int) -> str:
    """About n_bytes of text made of numbered lines."""
    out, i = [], 0
    while sum(len(x) + 1 for x in out) < n_bytes:
        out.append(f"{prefix} rule {i:05d}")
        i += 1
    return "\n".join(out)


def _total_bytes(items) -> int:
    return sum(len(item["content"].encode("utf-8")) for item in items)


def _write_all(root: pathlib.Path, sizes: dict[str, int]) -> None:
    for rel, size in sizes.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_lines(rel, size), encoding="utf-8")


def test_budget_constant():
    assert PROJECT_NOTES_BUDGET_BYTES == 12_000
    assert "12,000 bytes" in _NOTES_CUT_LINE


def test_small_files_are_kept_whole_and_in_config_order(tmp_path):
    _write_all(tmp_path, {"AGENTS.md": 100, "CLAUDE.md": 100, MITRA_NOTES: 100, COPILOT_NOTES: 100})
    cfg = load(cwd=str(tmp_path))
    paths = [item["path"] for item in cfg["project_instructions"]]
    assert paths == ["AGENTS.md", "CLAUDE.md", MITRA_NOTES, COPILOT_NOTES]
    assert all(_NOTES_CUT_LINE not in item["content"] for item in cfg["project_instructions"])


def test_broad_file_is_dropped_first(tmp_path):
    # .mitra (5K) + root files (3K each) = 11K; copilot file (3K) does not fit.
    _write_all(tmp_path, {"AGENTS.md": 3000, "CLAUDE.md": 3000, MITRA_NOTES: 5000, COPILOT_NOTES: 3000})
    cfg = load(cwd=str(tmp_path))
    by_path = {item["path"]: item["content"] for item in cfg["project_instructions"]}
    assert by_path[MITRA_NOTES] == (tmp_path / MITRA_NOTES).read_text(encoding="utf-8")
    assert by_path["AGENTS.md"] == (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert by_path["CLAUDE.md"] == (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    # The copilot file gets what is left (about 1K), cut with the marker line.
    assert by_path[COPILOT_NOTES].endswith(_NOTES_CUT_LINE)
    assert _total_bytes(cfg["project_instructions"]) <= PROJECT_NOTES_BUDGET_BYTES


def test_partly_fitting_file_is_cut_on_a_line_with_marker():
    items = [{"path": "AGENTS.md", "content": _lines("A", 20_000)}]
    out = _apply_notes_budget(items)
    content = out[0]["content"]
    assert content.endswith("\n" + _NOTES_CUT_LINE)
    assert len(content.encode("utf-8")) <= PROJECT_NOTES_BUDGET_BYTES
    # Every kept line is whole.
    original_lines = set(items[0]["content"].splitlines())
    for line in content.splitlines()[:-1]:
        assert line in original_lines


def test_most_specific_file_wins_the_budget():
    items = [
        {"path": "AGENTS.md", "content": _lines("A", 8000)},
        {"path": MITRA_NOTES, "content": _lines("M", 8000)},
    ]
    out = _apply_notes_budget(items)
    by_path = {item["path"]: item["content"] for item in out}
    assert by_path[MITRA_NOTES] == items[1]["content"]
    assert by_path["AGENTS.md"].endswith(_NOTES_CUT_LINE)
    # Output keeps the configured order.
    assert [item["path"] for item in out] == ["AGENTS.md", MITRA_NOTES]
    assert _total_bytes(out) <= PROJECT_NOTES_BUDGET_BYTES


def test_files_after_a_cut_are_dropped():
    items = [
        {"path": "AGENTS.md", "content": _lines("A", 15_000)},
        {"path": COPILOT_NOTES, "content": "small"},
    ]
    out = _apply_notes_budget(items)
    assert [item["path"] for item in out] == ["AGENTS.md"]


def test_file_dropped_when_too_little_room_for_marker():
    items = [
        {"path": MITRA_NOTES, "content": "x" * (PROJECT_NOTES_BUDGET_BYTES - 10)},
        {"path": "AGENTS.md", "content": _lines("A", 500)},
    ]
    out = _apply_notes_budget(items)
    assert [item["path"] for item in out] == [MITRA_NOTES]


def test_multibyte_text_is_cut_on_a_char_boundary():
    items = [{"path": "AGENTS.md", "content": "नमस्ते " * 3000}]
    out = _apply_notes_budget(items)
    content = out[0]["content"]
    assert content.endswith(_NOTES_CUT_LINE)
    assert len(content.encode("utf-8")) <= PROJECT_NOTES_BUDGET_BYTES
    assert "�" not in content


def test_custom_budget_argument():
    items = [{"path": "AGENTS.md", "content": "a\nb\nc"}]
    assert _apply_notes_budget(items, budget=100) == items
