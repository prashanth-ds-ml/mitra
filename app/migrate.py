"""D-080: Mitra is CodeMitra again (the user kept reading "Mitra" as "Myntra"). The folders and files it keeps move to
the new names once, on the first `codemitra` command, and nothing is lost: each one is a single rename on the same
disk (the never-delete store moves with ~/.mitra as one folder). If a rename cannot happen (Windows keeps a file open
while the old Mitra still runs), the old folder keeps being used and the move is tried again next time.

  ~/.mitra          -> ~/.codemitra          (MITRA_HOME -> CODEMITRA_HOME, MITRA_HARNESS -> CODEMITRA_HARNESS)
  ~/.config/mitra   -> ~/.config/codemitra   (and mitra.toml in it -> codemitra.toml)
  <project>/.mitra  -> <project>/.codemitra
  <project>/mitra.toml -> codemitra.toml, <project>/MITRA.md -> CODEMITRA.md
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_NAMES = ((".mitra", ".codemitra"), ("mitra.toml", "codemitra.toml"), ("MITRA.md", "CODEMITRA.md"))
ENV_NAMES = (("MITRA_HOME", "CODEMITRA_HOME"), ("MITRA_HARNESS", "CODEMITRA_HARNESS"))


def _move(old: Path, new: Path) -> str:
    """'' when there was nothing to do, else one line saying what happened."""
    if not old.exists() or new.exists():
        return ""
    try:
        old.rename(new)
        return f"moved {old} -> {new}"
    except OSError as exc:
        return f"could not move {old} yet ({exc.__class__.__name__}): still using it; close any old Mitra and retry"


def env() -> None:
    """An old MITRA_HOME / MITRA_HARNESS still works when the new name is not set."""
    for old, new in ENV_NAMES:
        if os.environ.get(old) and not os.environ.get(new):
            os.environ[new] = os.environ[old]


def home(user_home: Path | None = None) -> list[str]:
    """~/.mitra and ~/.config/mitra to their new names (skipped when CODEMITRA_HOME points elsewhere)."""
    base = Path(user_home) if user_home else Path.home()
    notes = []
    if not os.environ.get("CODEMITRA_HOME") or Path(os.environ["CODEMITRA_HOME"]) == base / ".codemitra":
        notes.append(_move(base / ".mitra", base / ".codemitra"))
    cfg_old, cfg_new = base / ".config" / "mitra", base / ".config" / "codemitra"
    notes.append(_move(cfg_old, cfg_new))
    notes.append(_move(cfg_new / "mitra.toml", cfg_new / "codemitra.toml"))
    return [n for n in notes if n]


def project(root: Path) -> list[str]:
    """One project folder's .mitra/, mitra.toml and MITRA.md to their new names."""
    root = Path(root)
    return [n for n in (_move(root / a, root / b) for a, b in PROJECT_NAMES) if n]


def projects_up_from(cwd: Path, user_home: Path | None = None) -> list[str]:
    """The folder you run CodeMitra in and its parents up to (not including) your home folder."""
    base = (Path(user_home) if user_home else Path.home()).resolve()
    notes, d = [], Path(cwd).resolve()
    while True:
        if d == base or d.parent == d:
            break
        notes += project(d)
        d = d.parent
    return notes


def run(cwd: Path | None = None) -> list[str]:
    """Everything, once per command; returns what moved (shown once), [] when already done."""
    env()
    return home() + projects_up_from(Path(cwd) if cwd else Path.cwd())


def resolve_home(user_home: Path | None = None) -> Path:
    """Where CodeMitra keeps its things: CODEMITRA_HOME, else ~/.codemitra, else (a move that has not happened yet)
    ~/.mitra."""
    env()
    if os.environ.get("CODEMITRA_HOME"):
        return Path(os.environ["CODEMITRA_HOME"])
    base = Path(user_home) if user_home else Path.home()
    new, old = base / ".codemitra", base / ".mitra"
    return old if old.is_dir() and not new.exists() else new
