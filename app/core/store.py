"""Central append-only store for every run record and trace (dashboard step 0, D-041).

Records are written to the project's `.mitra/runs/` (as before) and mirrored here, so deleting a project or its
`.mitra/` loses nothing. Mitra never deletes or rewrites a stored file; it only appends.

    ~/.mitra/data/runs/<project-slug>/<same path as under .mitra/runs>
    ~/.mitra/data/projects.json     every folder Mitra ran in
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

from app.core import harness as H

HOME_SLUG = "_mitra-home"  # records written under ~/.mitra itself (mitra improve benchmark runs)
OTHER_SLUG = "_other"


def root() -> Path:
    return H.home() / "data"


def runs_root() -> Path:
    return root() / "runs"


def projects_file() -> Path:
    return root() / "projects.json"


def project_slug(project: Path) -> str:
    """Readable and unique: folder name + 6 hex of the full path (two projects called `app` stay apart)."""
    p = Path(project).resolve()
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", p.name or "root").strip("-") or "root"
    return f"{name}-{hashlib.sha1(str(p).lower().encode('utf-8')).hexdigest()[:6]}"


def project_name(slug: str) -> str:
    """Display name of a slug: `mitra-try-1a2b3c` -> `mitra-try`."""
    return re.sub(r"-[0-9a-f]{6}$", "", slug)


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def mirror_path(record: Path) -> Path | None:
    """Where a project record is mirrored; None for files already in the store."""
    record = Path(record).resolve()
    home, store = H.home().resolve(), runs_root().resolve()
    if _within(record, root().resolve()):
        return None
    tmp = Path(tempfile.gettempdir()).resolve()  # E-108: resolved for both (CI's temp is C:\Users\RUNNER~1\...)
    if _within(record, tmp) and not _within(home, tmp):
        # a workspace in the temp folder is a test, a score case or a dev check, never one of your projects: it
        # would show up as a project and feed the coach (deep dive 2026-11-11: 8 such folders were found)
        return None
    if _within(record, home):
        return store / HOME_SLUG / record.relative_to(home)
    parts = record.parts
    if ".mitra" in parts[1:]:
        i = len(parts) - 1 - parts[::-1].index(".mitra")  # the innermost .mitra
        project = Path(*parts[:i])
        rest = parts[i + 1:]
        if rest and rest[0] == "runs":
            rest = rest[1:]
        return store / project_slug(project) / Path(*rest)
    return store / OTHER_SLUG / record.name


def project_of(stored: Path) -> str:
    """Project display name for a file in the store (or any record path)."""
    stored = Path(stored).resolve()
    store = runs_root().resolve()
    if _within(stored, store):
        rel = stored.relative_to(store).parts
        return project_name(rel[0]) if rel else "?"
    parts = stored.parts
    return parts[parts.index(".mitra") - 1] if ".mitra" in parts[1:] else stored.parent.name


def note_project(project: Path) -> None:
    """Remember a folder Mitra ran in (first and last seen). Never raises."""
    try:
        p = str(Path(project).resolve())
        f = projects_file()
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = data.get(p) or {"first_seen": now, "slug": project_slug(Path(p))}
        entry["last_seen"] = now
        data[p] = entry
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.replace(tmp, f)
    except Exception:
        pass


def known_projects() -> list[Path]:
    try:
        return [Path(p) for p in json.loads(projects_file().read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        return []


def append(record: Path, line: str) -> None:
    """Mirror one record line. A failing store never breaks the run."""
    try:
        target = mirror_path(record)
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(line if line.endswith("\n") else line + "\n")
    except Exception:
        pass


def merge(source: Path) -> int:
    """Append the lines of `source` its mirror does not have yet (by exact line). Returns lines added.
    Safe to repeat; never removes or reorders what is stored."""
    target = mirror_path(source)
    if target is None or not source.is_file():
        return 0
    try:
        new = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    have = set(target.read_text(encoding="utf-8").splitlines()) if target.exists() else set()
    missing = [ln for ln in new if ln.strip() and ln not in have]
    if missing:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write("\n".join(missing) + "\n")
    return len(missing)


def import_all(roots: list[Path]) -> dict:
    """Copy every record found under `roots`, the known projects and ~/.mitra into the store."""
    from app.core import analyze as A

    search = [Path(r) for r in roots] + known_projects()
    files = set(A.find_run_files([r for r in search if r.is_dir()]))
    bench_runs = H.home() / "harness" / "runs"
    if bench_runs.is_dir():
        files |= {p.resolve() for p in bench_runs.rglob("*.jsonl")}
    added = {"files": 0, "lines": 0}
    for f in sorted(files):
        n = merge(f)
        if n:
            added["files"] += 1
            added["lines"] += n
    return added


def stored_files(kind: str = "runs") -> list[Path]:
    """Every record file in the store (`traces/` folders excluded unless kind == 'traces')."""
    base = runs_root()
    if not base.is_dir():
        return []
    files = [p for p in base.rglob("*.jsonl")]
    if kind == "traces":
        return sorted(p for p in files if "traces" in p.parts)
    return sorted(p for p in files if "traces" not in p.parts)


def size_text() -> str:
    """For /doctor: where the store is and how big."""
    base = root()
    if not base.is_dir():
        return f"`{base}` (empty)"
    total = sum(p.stat().st_size for p in base.rglob("*") if p.is_file())
    n = len(stored_files())
    return f"`{base}`: {total / 2**20:.1f} MB, {n} record files"
