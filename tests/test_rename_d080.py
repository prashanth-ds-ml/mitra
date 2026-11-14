"""D-080: Mitra -> CodeMitra. The folders move once with nothing lost; the command is `codemitra`; the records keep
their format, so the old sessions still read."""
import tomllib
from pathlib import Path

from app import migrate
from app.core import intent


def _old_home(tmp_path):
    home = tmp_path / "home"
    store = home / ".mitra" / "data" / "runs" / "mitra-try-54b64f"
    store.mkdir(parents=True)
    (store / "chat-20261113.jsonl").write_text('{"kind": "turn_start", "author": "mitra"}\n', encoding="utf-8")
    (home / ".mitra" / "me.md").write_text("# About me\n", encoding="utf-8")
    (home / ".config" / "mitra").mkdir(parents=True)
    (home / ".config" / "mitra" / "mitra.toml").write_text("model = 'x'\n", encoding="utf-8")
    return home


def test_the_home_folder_moves_once_with_everything_in_it(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEMITRA_HOME", raising=False)
    home = _old_home(tmp_path)
    notes = migrate.home(home)
    assert len(notes) == 3 and not (home / ".mitra").exists()
    assert (home / ".codemitra" / "data" / "runs" / "mitra-try-54b64f" / "chat-20261113.jsonl").read_text(
        encoding="utf-8").startswith('{"kind": "turn_start"')
    assert (home / ".config" / "codemitra" / "codemitra.toml").is_file()
    assert migrate.home(home) == []                                       # once only


def test_both_folders_present_nothing_is_overwritten(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEMITRA_HOME", raising=False)
    home = _old_home(tmp_path)
    (home / ".codemitra").mkdir()
    (home / ".codemitra" / "keep.txt").write_text("new", encoding="utf-8")
    migrate.home(home)
    assert (home / ".mitra" / "me.md").is_file() and (home / ".codemitra" / "keep.txt").read_text() == "new"


def test_a_failed_move_keeps_using_the_old_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEMITRA_HOME", raising=False)
    home = _old_home(tmp_path)
    assert migrate.resolve_home(home) == home / ".mitra"                  # not moved yet: the old one is used
    migrate.home(home)
    assert migrate.resolve_home(home) == home / ".codemitra"

    def no_rename(self, target):
        raise PermissionError("in use")
    home2 = _old_home(tmp_path / "b")
    monkeypatch.setattr(Path, "rename", no_rename)
    notes = migrate.home(home2)
    assert any("could not move" in n for n in notes) and (home2 / ".mitra").is_dir()


def test_a_project_and_its_parents_move(tmp_path):
    home = tmp_path / "home"
    proj = home / "projects" / "mitra-try"
    (proj / ".mitra" / "runs").mkdir(parents=True)
    (proj / "mitra.toml").write_text("", encoding="utf-8")
    (proj / "MITRA.md").write_text("# rules\n", encoding="utf-8")
    sub = proj / "neon_chomp"
    sub.mkdir()
    notes = migrate.projects_up_from(sub, user_home=home)
    assert len(notes) == 3
    assert (proj / ".codemitra" / "runs").is_dir() and (proj / "codemitra.toml").is_file()
    assert (proj / "CODEMITRA.md").is_file() and not (proj / ".mitra").exists()


def test_an_old_env_name_still_works(monkeypatch, tmp_path):
    monkeypatch.delenv("CODEMITRA_HOME", raising=False)
    monkeypatch.setenv("MITRA_HOME", str(tmp_path / "x"))
    assert migrate.resolve_home() == tmp_path / "x"


def test_the_command_is_codemitra():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "codemitra"
    assert list(data["project"]["scripts"]) == ["codemitra"]


def test_both_names_typed_in_the_chat_get_the_terminal_hint():
    assert intent.terminal_command("codemitra coach")
    assert intent.terminal_command("mitra coach")                         # old habit: still recognised


def test_the_assistant_calls_itself_codemitra():
    from app.core import chat as C
    assert "You are CodeMitra" in C.PHASED_PROMPT
    assert " Mitra" not in C.PHASED_PROMPT.replace("CodeMitra", "")
