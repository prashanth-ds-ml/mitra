"""Dashboard step 0 (D-041): central append-only store; deleting a project loses nothing."""
import json
import shutil

from app.core import analyze as A
from app.core import dashboard as D
from app.core import harness as H
from app.core import loop as L
from app.core import store as S


def _rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_every_record_line_is_mirrored_to_the_store(tmp_path):
    proj = tmp_path / "game"
    rec = L.Recorder(proj / ".mitra" / "runs" / "chat-20261107.jsonl")
    rec.write("turn_start", turn=1, user="hi")
    rec.write("turn_end", turn=1, steps=1)
    stored = S.mirror_path(proj / ".mitra" / "runs" / "chat-20261107.jsonl")
    assert stored.parent.parent == S.runs_root() and stored.parent.name.startswith("game-")
    assert [r["kind"] for r in _rows(stored)] == ["turn_start", "turn_end"]


def test_deleting_the_project_keeps_its_sessions_on_the_dashboard(tmp_path):
    proj = tmp_path / "brick"
    rec = L.Recorder(proj / ".mitra" / "runs" / "chat-1.jsonl")
    rec.write("turn_start", turn=1, user="go", harness_version=0)
    rec.write("tool", turn=1, step=1, name="read_file", args={"path": "x"}, ok=False, output="no such file")
    shutil.rmtree(proj)
    files = D.run_files([tmp_path])
    assert len(files) == 1 and A._project(files[0]) == "brick"
    assert A.analyze(files).files == 1


def test_import_copies_old_records_once_and_merges_new_lines(tmp_path):
    old = tmp_path / "proj" / ".mitra" / "runs" / "chat-old.jsonl"
    old.parent.mkdir(parents=True)
    old.write_text('{"kind": "turn_start", "turn": 1}\n{"kind": "turn_end", "turn": 1}\n', encoding="utf-8")
    assert S.import_all([tmp_path]) == {"files": 1, "lines": 2}
    assert S.import_all([tmp_path]) == {"files": 0, "lines": 0}  # repeat adds nothing
    with old.open("a", encoding="utf-8") as f:
        f.write('{"kind": "turn_start", "turn": 2}\n')
    assert S.import_all([tmp_path])["lines"] == 1
    assert len(_rows(S.mirror_path(old))) == 3


def test_live_mirror_and_import_do_not_double_count(tmp_path):
    rec = L.Recorder(tmp_path / "p" / ".mitra" / "runs" / "r.jsonl")
    rec.write("start", task="t")
    assert S.import_all([tmp_path])["lines"] == 0


def test_same_folder_name_in_two_places_stays_apart(tmp_path):
    a, b = S.project_slug(tmp_path / "x" / "app"), S.project_slug(tmp_path / "y" / "app")
    assert a != b and S.project_name(a) == S.project_name(b) == "app"


def test_records_under_mitra_home_go_to_their_own_slug(tmp_path):
    bench = H.home() / "harness" / "runs" / "v2" / "T01.jsonl"
    assert S.mirror_path(bench).relative_to(S.runs_root()).parts[0] == S.HOME_SLUG
    assert S.mirror_path(S.runs_root() / "a" / "b.jsonl") is None  # store files are never mirrored again


def test_projects_are_noted_and_found_by_import(tmp_path):
    far = tmp_path / "elsewhere" / "deep" / "project"
    (far / ".mitra" / "runs").mkdir(parents=True)
    (far / ".mitra" / "runs" / "chat.jsonl").write_text('{"kind": "start"}\n', encoding="utf-8")
    S.note_project(far)
    S.note_project(far)
    data = json.loads(S.projects_file().read_text(encoding="utf-8"))
    assert list(data) == [str(far.resolve())] and data[str(far.resolve())]["slug"].startswith("project-")
    assert S.import_all([tmp_path / "nowhere"])["files"] == 1  # found through projects.json


def test_a_broken_store_never_breaks_recording(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "mirror_path", lambda p: (_ for _ in ()).throw(OSError("disk full")))
    rec = L.Recorder(tmp_path / "p" / ".mitra" / "runs" / "r.jsonl")
    rec.write("start", task="t")
    assert (tmp_path / "p" / ".mitra" / "runs" / "r.jsonl").exists()


def test_size_text_names_the_folder():
    assert "empty" in S.size_text()
    L.Recorder(S.H.home().parent / "p" / ".mitra" / "runs" / "r.jsonl").write("start")
    assert "1 record files" in S.size_text()


def test_a_short_temp_name_still_counts_as_the_test_home(tmp_path, monkeypatch):
    """E-108: on the Windows CI runner gettempdir() is the 8.3 name (C:/Users/RUNNER~1/...) while the home is
    resolved to the long one: every test record looked like a dev run and was skipped (CI red since v0.7.0)."""
    import tempfile

    from app.core import store

    (tmp_path / "x").mkdir()
    # the same folder, spelled so that only resolving makes it match (as RUNNER~1 vs runneradmin does on CI)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "x" / ".."))
    rec = tmp_path / "proj" / ".mitra" / "runs" / "chat-1.jsonl"
    assert store.mirror_path(rec) is not None
