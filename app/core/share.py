"""D-081: share your sessions so CodeMitra learns from everyone's, whenever you want.

  codemitra share --setup        once: your name, the shared logs repo, whether to ask at exit
  codemitra share                pick sessions, see a preview, write them (light + scrubbed) to ~/.codemitra/share/out
  codemitra share --push         the same, then commit + push them to the logs repo with your own git login
  codemitra share --pull         (the maintainer) bring everyone's shared sessions into the store: the coach,
                                 `codemitra improve --chat` and the dashboard read them like your own

A shared session is the same record rows CodeMitra writes anyway, cut down (light): your messages, its answers, which
tools ran and whether they failed (a short error, a test summary), the labels (unhappy / happy, + / -, the session
rating, unverified claims) and the setup (CodeMitra version, model, context, backend). Left out: file contents, tool
outputs, the code it wrote or edited, your notes (me.md), absolute paths. Scrubbed: tokens and keys, emails, your user
name and home folder. Nothing is ever sent without a preview and your yes (or the "always" you chose at setup).
"""
from __future__ import annotations

import getpass
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from app.core import harness as H

DEFAULT_REPO = "prashanth-ds-ml/codemitra-logs"
AT_EXIT = ("ask", "always", "never")
MAX_TEXT = 3000       # one message or answer
MAX_ERROR = 200       # a failed tool's error
MAX_CLAIM = 160
GIT_TIMEOUT_S = 120

# ── scrubbing ────────────────────────────────────────────────────────────────────────────────────────────────────
_SECRETS = [
    re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"), re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), re.compile(r"\bAKIA[0-9A-Z]{16}\b"), re.compile(r"\bKGAT_[A-Za-z0-9]{10,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\btrycloudflare\.com/[A-Za-z0-9_-]{16,}"),
]
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def scrubber(user: str | None = None, home: str | None = None):
    """A function that removes secrets, emails, your home folder and your user name from a text."""
    user = user if user is not None else getpass.getuser()
    home = home if home is not None else str(Path.home())
    homes = {home, home.replace("\\", "/"), "/" + home.replace(":", "").replace("\\", "/").lower()}
    home_rx = re.compile("|".join(re.escape(h) for h in sorted(homes, key=len, reverse=True) if h), re.IGNORECASE)
    user_rx = re.compile(rf"(?<![A-Za-z0-9]){re.escape(user)}(?![A-Za-z0-9])", re.IGNORECASE) if len(user) >= 3 else None

    def scrub(text) -> str:
        s = str(text or "")
        for rx in _SECRETS:
            s = rx.sub("[secret]", s)
        s = _EMAIL.sub("[email]", s)
        s = home_rx.sub("~", s)
        if user_rx is not None:
            s = user_rx.sub("[user]", s)
        return s
    return scrub


# ── settings and state ───────────────────────────────────────────────────────────────────────────────────────────
def folder() -> Path:
    return H.home() / "share"


def settings() -> dict:
    try:
        return json.loads((folder() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**new) -> dict:
    cur = {**settings(), **{k: v for k, v in new.items() if v is not None}}
    folder().mkdir(parents=True, exist_ok=True)
    (folder() / "settings.json").write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return cur


def _state() -> dict:
    try:
        return json.loads((folder() / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"shared": []}


def _mark_shared(ids: list[str]) -> None:
    st = _state()
    st["shared"] = sorted(set(st.get("shared", [])) | set(ids))
    folder().mkdir(parents=True, exist_ok=True)
    (folder() / "state.json").write_text(json.dumps(st, indent=1), encoding="utf-8")


# ── sessions in your records ─────────────────────────────────────────────────────────────────────────────────────
def _rows(path: Path) -> list[dict]:
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def sessions(files: list[Path]) -> list[dict]:
    """Every chat session in the records, newest first: {id, path, project, started, turns, labels, rows}."""
    from app.core import cases as cases_mod
    from app.core import store
    found = []
    for f in files:
        if not f.name.startswith("chat-") or f.parent.name.startswith("shared-"):
            continue  # your own conversations only (not plan tasks, score runs, or sessions others shared)
        for rows in cases_mod._sessions(_rows(f)):
            starts = [r for r in rows if r.get("kind") == "turn_start" and not str(r.get("user", "")).startswith("/")]
            if not starts:
                continue
            t0 = float(rows[0].get("t") or starts[0].get("t") or 0)
            sid = hashlib.sha1(f"{f.parent.name}/{f.name}/{t0:.3f}".encode()).hexdigest()[:10]
            labels = sum(1 for r in rows if r.get("kind") in ("signal", "feedback", "session_rating"))
            found.append({"id": sid, "path": f, "project": store.project_name(f.parent.name), "started": t0,
                          "turns": len(starts), "labels": labels, "rows": rows})
    return sorted(found, key=lambda s: -s["started"])


def unshared(files: list[Path]) -> list[dict]:
    done = set(_state().get("shared", []))
    return [s for s in sessions(files) if s["id"] not in done]


# ── the light, scrubbed copy ─────────────────────────────────────────────────────────────────────────────────────
def _rel(path, workspace: str) -> str:
    p = str(path or "").replace("\\", "/")
    ws = str(workspace or "").replace("\\", "/").rstrip("/")
    if ws and p.lower().startswith(ws.lower() + "/"):
        return p[len(ws) + 1:]
    return p.rsplit("/", 1)[-1] if ("/" in p and (p[1:3] == ":/" or p.startswith("/"))) else p


def light(rows: list[dict], scrub, project_id: str, friend: str) -> list[dict]:
    """The rows worth learning from, cut down: no file contents, no tool outputs (a short error or test summary only),
    no absolute paths. Every row says where it came from (`shared_by`)."""
    from app.core import tools as T
    ws = next((str(r.get("workspace", "")) for r in rows if r.get("kind") == "session"), "")
    out = []

    def keep(r: dict, **fields) -> None:
        row = {"t": r.get("t"), "kind": r.get("kind"), "author": r.get("author", "mitra"), "shared_by": friend}
        row.update({k: v for k, v in fields.items() if v is not None})
        out.append(row)

    for r in rows:
        k = r.get("kind")
        if k == "session":
            keep(r, project=project_id, code_version=r.get("code_version"), model=r.get("model"),
                 num_ctx=r.get("num_ctx"), mode=r.get("mode"), fit=r.get("fit"), remote=r.get("remote"))
        elif k == "turn_start":
            keep(r, turn=r.get("turn"), user=scrub(r.get("user", ""))[:MAX_TEXT], request_kind=r.get("request_kind"),
                 path=r.get("path"), backend=r.get("backend"), model=r.get("model"), num_ctx=r.get("num_ctx"),
                 role=r.get("role"), harness_version=r.get("harness_version"), code_version=r.get("code_version"),
                 mode=r.get("mode"))
        elif k == "turn_end":
            keep(r, turn=r.get("turn"), text=scrub(r.get("text", ""))[:MAX_TEXT], outcome=r.get("outcome"),
                 seconds=r.get("seconds"), steps=r.get("steps"), stopped=r.get("stopped"),
                 reason=scrub(r.get("reason", ""))[:MAX_ERROR], first_s=r.get("first_s"),
                 changed=[scrub(_rel(p, ws)) for p in (r.get("changed") or [])][:30])
        elif k == "tool":
            args = r.get("args") or {}
            small = {}
            if args.get("path"):
                small["path"] = scrub(_rel(args["path"], ws))[:160]
            if r.get("name") == "run_command" and args.get("command"):
                small["command"] = scrub(str(args["command"]).splitlines()[0])[:120]
            for a in ("folder", "keyword"):
                if args.get(a):
                    small[a] = scrub(args[a])[:80]
            output = str(r.get("output") or "")
            short = (T.test_summary(output) if r.get("name") == "run_tests" else
                     ("" if r.get("ok") else output.strip().splitlines()[0] if output.strip() else ""))
            keep(r, turn=r.get("turn"), step=r.get("step"), name=r.get("name"), ok=r.get("ok"), args=small,
                 output=scrub(short)[:MAX_ERROR] if short else None, after_change=r.get("after_change"))
        elif k == "phase":
            what = (r.get("args") or {}).get("what") or (r.get("args") or {}).get("goal")
            keep(r, turn=r.get("turn"), step=r.get("step"), name=r.get("name"),
                 args={"what": scrub(what)[:MAX_ERROR]} if what else {}, go_ahead=r.get("go_ahead"),
                 switched=r.get("switched"))
        elif k == "signal":
            keep(r, of_turn=r.get("of_turn"), signal=r.get("signal"), why=scrub(r.get("why", ""))[:80] or None,
                 auto=r.get("auto"))
        elif k == "feedback":
            keep(r, of_turn=r.get("of_turn"), verdict=r.get("verdict"), note=scrub(r.get("note", ""))[:MAX_ERROR],
                 via=r.get("via"))
        elif k == "session_rating":
            keep(r, stars=r.get("stars"), turns=r.get("turns"))
        elif k == "grounding":
            keep(r, turn=r.get("turn"), claims=[scrub(c)[:MAX_CLAIM] for c in (r.get("claims") or [])][:5])
        elif k in ("repeat", "focus", "model_error", "stopped", "empty_answer"):
            keep(r, turn=r.get("turn"), error=scrub(r.get("error", ""))[:MAX_ERROR] or None,
                 reason=scrub(r.get("reason", ""))[:MAX_ERROR] or None, folder=r.get("folder"), slow=r.get("slow"))
    return out


def friend_name() -> str:
    name = settings().get("name") or getpass.getuser()
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "friend"


def export(chosen: list[dict], *, friend: str | None = None, scrub=None) -> list[Path]:
    """Write the light copy of each chosen session to ~/.codemitra/share/out/<friend>/; returns the files."""
    friend = friend or friend_name()
    scrub = scrub or scrubber()
    out_dir = folder() / "out" / friend
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for s in chosen:
        project_id = "p-" + hashlib.sha1(s["project"].encode()).hexdigest()[:6]
        stamp = time.strftime("%Y%m%d-%H%M", time.localtime(s["started"]))
        path = out_dir / f"chat-{stamp}-{project_id}-{s['id']}.jsonl"
        rows = light(s["rows"], scrub, project_id, friend)
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        written.append(path)
    return written


def preview(path: Path, n: int = 3) -> str:
    """What a shared file holds, in a few lines, so you see it before it leaves."""
    rows = _rows(path)
    turns = [r for r in rows if r.get("kind") == "turn_start"]
    ends = {r.get("turn"): r for r in rows if r.get("kind") == "turn_end"}
    labels = [r for r in rows if r.get("kind") in ("signal", "feedback", "session_rating")]
    lines = [f"{path.name}: {len(turns)} turns, {len(labels)} labels, {len(rows)} rows"]
    for t in turns[:n]:
        lines.append(f"  you: {' '.join(str(t.get('user', '')).split())[:100]}")
        lines.append(f"  it:  {' '.join(str(ends.get(t.get('turn'), {}).get('text', '')).split())[:100]}")
    if len(turns) > n:
        lines.append(f"  … {len(turns) - n} more turns")
    return "\n".join(lines)


# ── the logs repo ────────────────────────────────────────────────────────────────────────────────────────────────
def repo_url(repo: str) -> str:
    return repo if "://" in repo or repo.startswith(("git@", "/", ".")) or re.match(r"^[A-Za-z]:", repo) else \
        f"https://github.com/{repo}.git"


def _git(args: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def rmtree(path: Path) -> None:
    """Delete a folder, git's read-only object files too (Windows refuses them otherwise)."""
    import os
    import stat

    def unlock(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if Path(path).exists():
        shutil.rmtree(path, onerror=unlock)


def checkout(repo: str) -> tuple[Path | None, str]:
    """A local copy of the logs repo (cloned once, then pulled)."""
    local = folder() / "repo"
    if (local / ".git").is_dir():
        ok, out = _git(["pull", "--rebase", "--quiet"], local)
        return (local, "") if ok else (None, f"could not update the logs repo: {out[:300]}")
    if local.exists():  # a broken copy: clone it again
        rmtree(local)
    ok, out = _git(["clone", "--quiet", repo_url(repo), str(local)])
    return (local, "") if ok else (None, f"could not clone {repo}: {out[:300]} (do you have access? see `codemitra "
                                          "share --setup`)")


def push(files: list[Path], *, repo: str | None = None, friend: str | None = None) -> tuple[bool, str]:
    """Commit the files to people/<friend>/ in the logs repo and push them with your own git login."""
    repo = repo or settings().get("repo") or DEFAULT_REPO
    friend = friend or friend_name()
    local, err = checkout(repo)
    if local is None:
        return False, err
    dest = local / "people" / friend
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dest / f.name)
    _git(["add", "people"], local)
    ok, out = _git(["commit", "--quiet", "-m", f"logs: {friend}, {len(files)} session(s)"], local)
    if not ok and "nothing to commit" in out:
        return True, "already shared: nothing new to push"
    for _ in range(2):
        ok, out = _git(["push", "--quiet"], local)
        if ok:
            return True, f"pushed {len(files)} session(s) to {repo} (people/{friend}/)"
        _git(["pull", "--rebase", "--quiet"], local)  # someone pushed meanwhile
    return False, f"could not push to {repo}: {out[:300]}"


def share(chosen: list[dict], *, do_push: bool, friend: str | None = None) -> tuple[bool, str, list[Path]]:
    files = export(chosen, friend=friend)
    if not do_push:
        _mark_shared([s["id"] for s in chosen])
        return True, f"wrote {len(files)} file(s) to {files[0].parent if files else folder() / 'out'}", files
    ok, msg = push(files, friend=friend)
    if ok:
        _mark_shared([s["id"] for s in chosen])
    return ok, msg, files


# ── the maintainer: everyone's sessions into the store ───────────────────────────────────────────────────────────
def pull(repo: str | None = None) -> tuple[int, str]:
    """Copy every shared session not yet in the store to data/runs/shared-<friend>/: the coach, `codemitra improve
    --chat` and the dashboard then read them like your own records. Returns (new files, message)."""
    from app.core import store
    repo = repo or settings().get("repo") or DEFAULT_REPO
    local, err = checkout(repo)
    if local is None:
        return 0, err
    new = 0
    for f in sorted((local / "people").glob("*/chat-*.jsonl")):
        dest = store.runs_root() / f"shared-{f.parent.name}" / f.name
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, dest)  # a fresh time: the coach reviews it as new (arrival, not when it was said)
        new += 1
    people = len({p.parent.name for p in (local / "people").glob("*/chat-*.jsonl")})
    return new, f"{new} new shared session(s) from {people} people in {repo}"


def check_access(repo: str) -> tuple[bool, str]:
    ok, out = _git(["ls-remote", "--heads", repo_url(repo)])
    return ok, ("" if ok else out[:300])
