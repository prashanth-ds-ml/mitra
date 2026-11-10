"""The resume brief (D-065 P1): "where did we stop?" from Mitra's own records, no exploring.

Put in the system prompt at start (capped) and shown directly when you ask where we stopped (P3). Sources, newest
first: `.mitra/resume.md` (written when a plan finishes, P5), the last session's requests and outcomes, the latest
"Kaggle ended" report, night reports, and git (last commits, uncommitted files).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

MAX_CHARS = 2500
OUTCOMES = {"tests_passed": "✓ tests passed", "tests_failed": "✗ tests failed", "answered": "answered",
            "stopped": "stopped", "stopped_by_user": "stopped by you", "interrupted": "interrupted",
            "error": "error", "kaggle_ended": "cut off: Kaggle ended"}
SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mitra"}


def _git(root: Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="replace")
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _when(t: float) -> str:
    return time.strftime("%d %b %H:%M", time.localtime(t))


def _night_reports(root: Path, limit: int = 2) -> list[Path]:
    found = []
    for depth_glob in ("NIGHT_REPORT.md", "*/NIGHT_REPORT.md"):
        for p in root.glob(depth_glob):
            if not any(x in p.parts for x in SKIP):
                found.append(p)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


RESUME_WORDS = ("where did we", "where we stopped", "where were we", "last stop", "what did we do",
                "what were we doing", "status of the project", "pick up where", "continue from where")


def is_resume_question(text: str) -> bool:
    low = " ".join((text or "").lower().split())
    return any(w in low for w in RESUME_WORDS)


def recent_turns(root: Path, files: int = 3) -> list[dict]:
    """Work turns from the last few chat records, oldest first: {t, user, outcome, files}. Resume questions and
    interrupted turns that changed nothing are left out (they say nothing about the work)."""
    import json
    runs = root / ".mitra" / "runs"
    recs = sorted(runs.glob("chat-*.jsonl"), key=lambda p: p.stat().st_mtime)[-files:] if runs.is_dir() else []
    out: list[dict] = []
    for rec in recs:
        open_: dict = {}
        try:
            lines = rec.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k, no = r.get("kind"), r.get("turn")
            if k == "session":
                open_ = {}
            elif k == "turn_start" and no is not None:
                open_[no] = {"t": float(r.get("t") or 0), "user": str(r.get("user") or ""), "outcome": "",
                             "files": []}
                out.append(open_[no])
            elif k == "turn_end" and no in open_:
                open_[no]["outcome"] = str(r.get("outcome") or "")
                open_[no]["files"] = [str(f) for f in (r.get("changed") or [])]
    return [t for t in out if len(t["user"].split()) >= 3 and not is_resume_question(t["user"])
            and not (t["outcome"] in ("interrupted", "") and not t["files"])]


def _first_lines(text: str, n: int, keep=lambda line: True) -> list[str]:
    return [line for line in text.splitlines() if line.strip() and keep(line)][:n]


def brief(workspace: Path, max_chars: int = MAX_CHARS) -> str:
    """Markdown, '' when there is nothing to say (a new project)."""
    root = Path(workspace)
    out: list[str] = []
    resume = root / ".mitra" / "resume.md"
    if resume.is_file():
        out += [f"**Last plan** ({_when(resume.stat().st_mtime)}, .mitra/resume.md):"]
        out += _first_lines(resume.read_text(encoding="utf-8", errors="replace"), 12, lambda l: not l.startswith("# "))
    turns = recent_turns(root)
    if turns:
        out += ["", f"**Recent work** (last {_when(turns[-1]['t'])}): what you asked"]
        for t in turns[-6:]:
            outcome = OUTCOMES.get(t.get("outcome") or "", t.get("outcome") or "")
            files = sorted({Path(f).name for f in t.get("files", [])})
            said = " ".join(t["user"].split())
            out.append(f"- {said[:110]}{'…' if len(said) > 110 else ''}" + (f" → {outcome}" if outcome else "")
                       + (f" ({', '.join(files[:4])})" if files else ""))
    reports = sorted((root / ".mitra" / "reports").glob("kaggle-ended-*.md"), key=lambda p: p.stat().st_mtime)
    if reports:
        out += ["", f"**Kaggle ended report:** .mitra/reports/{reports[-1].name}"]
    for night in _night_reports(root):
        text = night.read_text(encoding="utf-8", errors="replace")
        tasks = _first_lines(text, 1, lambda l: l.startswith("## Tasks"))
        out += ["", f"**Night run** ({_when(night.stat().st_mtime)}, {night.relative_to(root).as_posix()}): "
                    + (tasks[0].lstrip("# ") if tasks else "see the report")]
    log = _git(root, "log", "-5", "--format=%h %s (%cr)")
    status = _git(root, "status", "--short")
    if log:
        out += ["", "**Last commits:**"] + [f"- {line}" for line in log.splitlines()]
    if status:
        changed = status.splitlines()
        out += ["", f"**Uncommitted:** {len(changed)} file(s): " + ", ".join(c[3:] for c in changed[:8])
                + (" …" if len(changed) > 8 else "")]
    if not out:
        return ""
    text = "\n".join(out).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0] + "\n…"
    return "## Where we stopped last time (from Mitra's records)\n" + text
