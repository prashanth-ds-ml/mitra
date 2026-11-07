"""What the dashboard shows, computed from the central store (D-041; item 0 / SELF_IMPROVEMENT.md sections 4-6).
Pure functions over record and trace files, so every number is testable from fixtures.

- sessions():     each session as turns and steps, with your verdicts, corrections, declines and crashes
- tool_stats():   calls, failures and time per tool / MCP server; model_stats(): speed, context, prompt time, reloads
- improvement():  signals per harness version, or per Mitra code version + harness version
- trends():       the same signals day by day; breakdown(): by project / model / kind of task
- training():     usable turns for the fine-tune and why the rest are out; export_training()
"""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.core import store
from app.core.loop import rebuild_calls

MIN_TURNS_TO_JUDGE = 20   # below this a version's numbers are shown as "not enough data"
TRAINING_TARGET = 300     # SCOPE: a few hundred passing runs before any fine-tune
USABLE_OUTCOMES = {"tests_passed", "passed"}  # chat turns / mitra solve runs whose tests passed
TESTED_OUTCOMES = USABLE_OUTCOMES | {"tests_failed", "failed"}
EDIT_TOOLS = {"write_file", "edit_file", "append_file"}
USER_KINDS = {"feedback", "user_edit", "declined"}  # your judgment: never makes a turn "written by someone else"
RELOAD_S = 1.0            # an Ollama load time above this means the model was (re)loaded for that call


def _read(path: Path) -> list[dict]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return rows


def trace_file(record: Path) -> Path:
    return record.parent / "traces" / f"{record.stem}.jsonl"


def _day(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t)) if t else "?"


def _median(xs: list) -> float:
    return round(statistics.median(xs), 1) if xs else 0.0


# ── sessions ─────────────────────────────────────────────────────────────────

@dataclass
class Step:
    kind: str            # model | tool | retry | error | stopped | tests
    name: str = ""
    detail: str = ""
    ok: bool = True
    seconds: float | None = 0.0   # tool: run time (None when it cannot be measured from the records)
    tokens: int = 0


OLD = "not recorded (older)"   # label for records from before a field was saved


@dataclass
class Turn:
    no: int
    user: str = ""
    mode: str = ""
    model: str = ""
    outcome: str = ""
    reason: str = ""
    seconds: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    ctx_used: int = 0                       # prompt size of the turn's last call (how full the context was)
    harness_version: int = 0
    code_version: str = ""
    started: float = 0.0
    ram_free_gb: float | None = None
    steps: list[Step] = field(default_factory=list)
    authors: set = field(default_factory=set)
    verdict: str = ""                       # good | bad | "" (your /good /bad; the last one counts)
    verdict_note: str = ""
    corrections: list = field(default_factory=list)   # {path, added, removed, diff, deleted}
    declines: list = field(default_factory=list)      # {tool, path|command, reason}
    crashes: int = 0
    green_s: float | None = None            # first code edit -> first passing tests, within the turn
    _first_edit_t: float = 0.0

    @property
    def tested(self) -> bool:
        return self.outcome in TESTED_OUTCOMES

    @property
    def first_try(self) -> bool:
        """Tests passed, you did not correct it and did not mark it bad."""
        return self.outcome in USABLE_OUTCOMES and not self.corrections and self.verdict != "bad"

    @property
    def finished(self) -> bool:
        return self.outcome not in ("stopped_by_user", "interrupted", "error", "stopped")


@dataclass
class Session:
    project: str
    file: str
    kind: str            # chat | solve
    started: float = 0.0
    turns: list[Turn] = field(default_factory=list)
    machine: dict = field(default_factory=dict)       # the `session` row: model, context, fit, free RAM / VRAM
    code_version: str = ""
    crashes: list = field(default_factory=list)       # {t, error}


def _args_text(args) -> str:
    if not isinstance(args, dict):
        return str(args)[:120]
    for k in ("path", "command", "query", "server", "url", "pattern"):
        if args.get(k):
            return str(args[k])[:120]
    return json.dumps(args, ensure_ascii=False)[:120]


def _tool_label(name: str, args) -> str:
    if name == "mcp_call" and isinstance(args, dict) and args.get("server"):
        return f"mcp:{args['server']}"
    return name


def _turn_by_no(s: Session, no) -> Turn | None:
    try:
        no = int(no)
    except (TypeError, ValueError):
        return None
    return next((t for t in reversed(s.turns) if t.no == no), None)


def sessions(files: list[Path]) -> list[Session]:
    out = []
    for f in files:
        rows = _read(f)
        if not rows:
            continue
        kind = "chat" if any(r.get("kind") == "turn_start" for r in rows) else "solve"
        s = Session(project=store.project_of(f), file=f.name, kind=kind, started=float(rows[0].get("t") or 0))
        cur: Turn | None = None
        prev_t, prev_kind = None, ""
        for r in rows:
            k, t = r.get("kind"), float(r.get("t") or 0)
            dt = round(t - prev_t, 1) if prev_t else 0.0
            tool_dt = dt if prev_kind in ("model", "tool") else None  # a tool runs right after the model's reply
            prev_t, prev_kind = t, k
            if k == "session":
                if s.turns:  # the chat file is per day: each Mitra start begins a new session
                    out.append(s)
                    s = Session(project=s.project, file=s.file, kind=kind, started=t)
                    cur = None
                s.machine = {key: r.get(key) for key in ("model", "num_ctx", "fit", "need_ram_gb", "ram_free_gb",
                                                         "vram_free_gb", "mode")}
                s.code_version = str(r.get("code_version") or s.code_version)
                continue
            if k in ("turn_start", "start"):
                cur = Turn(no=int(r.get("turn") or len(s.turns) + 1), user=str(r.get("user") or r.get("task") or ""),
                           mode=str(r.get("mode") or ""), model=str(r.get("model") or ""),
                           harness_version=int(r.get("harness_version") or 0),
                           code_version=str(r.get("code_version") or ""), started=t,
                           ram_free_gb=r.get("ram_free_gb"))
                cur.authors.add(r.get("author", "mitra"))
                s.code_version = s.code_version or cur.code_version
                s.turns.append(cur)
                continue
            # your judgment attaches to the turn it judges
            if k == "feedback":
                tt = _turn_by_no(s, r.get("of_turn"))
                if tt:
                    tt.verdict, tt.verdict_note = str(r.get("verdict") or ""), str(r.get("note") or "")
                continue
            if k == "user_edit":
                tt = _turn_by_no(s, r.get("of_turn"))
                if tt:
                    tt.corrections.append({x: r.get(x) for x in ("path", "added", "removed", "diff", "deleted")})
                continue
            if k == "crash":
                s.crashes.append({"t": t, "error": str(r.get("error") or "")})
                tt = _turn_by_no(s, r.get("turn")) or cur
                if tt:
                    tt.crashes += 1
                continue
            if k == "declined":
                tt = _turn_by_no(s, r.get("turn")) or cur
                if tt:
                    tt.declines.append({x: r.get(x) for x in ("tool", "path", "command", "reason") if r.get(x)})
                continue
            if cur is None:
                continue
            if k not in USER_KINDS:
                cur.authors.add(r.get("author", "mitra"))
            if k == "model":
                calls = r.get("tool_calls") or []
                cur.steps.append(Step("model", "reply" if not calls else ", ".join(c.get("name", "?") for c in calls),
                                      str(r.get("text") or "")[:300], True, dt, int(r.get("tokens_out") or 0)))
            elif k == "tool":
                name = str(r.get("name"))
                ok = bool(r.get("ok"))
                cur.steps.append(Step("tool", _tool_label(name, r.get("args")), _args_text(r.get("args")), ok, tool_dt))
                if name in EDIT_TOOLS and ok and not cur._first_edit_t:
                    cur._first_edit_t = t
                if name == "run_tests" and ok and cur._first_edit_t and cur.green_s is None:
                    cur.green_s = round(t - cur._first_edit_t, 1)
            elif k in ("bad_tool_call", "model_error"):
                cur.steps.append(Step("retry", k, str(r.get("error") or "")[:300], False, dt))
            elif k == "stopped":
                cur.steps.append(Step("stopped", "", str(r.get("reason") or ""), False, dt))
            elif k == "tests":
                ok = bool(r.get("passed", r.get("ok")))
                cur.steps.append(Step("tests", "", str(r.get("summary") or r.get("output") or "")[:200], ok, dt))
                if ok and cur._first_edit_t and cur.green_s is None:
                    cur.green_s = round(t - cur._first_edit_t, 1)
            elif k in ("turn_end", "end"):
                cur.outcome = str(r.get("outcome") or r.get("status") or ("stopped" if r.get("stopped") else "answered"))
                cur.reason = str(r.get("reason") or r.get("summary") or "")[:300]
                cur.seconds = float(r.get("seconds") or 0)
                cur.tokens_in, cur.tokens_out = int(r.get("tokens_in") or 0), int(r.get("tokens_out") or 0)
                cur.ctx_used = int(r.get("ctx_used") or 0)
                if kind == "chat":
                    cur = None
        out.append(s)
    for s in out:
        for t in s.turns:  # a turn with a start and no end: the session was killed mid-turn
            t.outcome = t.outcome or "interrupted"
    return sorted(out, key=lambda s: s.started, reverse=True)


# ── tools and models ─────────────────────────────────────────────────────────

@dataclass
class ToolStat:
    name: str
    calls: int = 0
    failures: int = 0
    seconds: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)

    @property
    def fail_pct(self) -> int:
        return round(100 * self.failures / self.calls) if self.calls else 0

    @property
    def median_s(self) -> float:
        return _median(self.seconds)

    @property
    def worst_s(self) -> float:
        return round(max(self.seconds), 1) if self.seconds else 0.0

    @property
    def top_error(self) -> str:
        return max(self.errors, key=self.errors.get) if self.errors else ""


def tool_stats(sess: list[Session]) -> list[ToolStat]:
    stats: dict[str, ToolStat] = {}
    for s in sess:
        for t in s.turns:
            for st in t.steps:
                if st.kind != "tool":
                    continue
                ts = stats.setdefault(st.name, ToolStat(st.name))
                ts.calls += 1
                if st.seconds is not None:
                    ts.seconds.append(st.seconds)
                if not st.ok:
                    ts.failures += 1
    return sorted(stats.values(), key=lambda s: s.calls, reverse=True)


def tool_errors(files: list[Path], stats: list[ToolStat]) -> None:
    """Most common first error line per tool (from the records' tool output)."""
    from app.core.analyze import _norm_error
    by = {s.name: s for s in stats}
    for f in files:
        for r in _read(f):
            if r.get("kind") == "tool" and not r.get("ok"):
                s = by.get(_tool_label(str(r.get("name")), r.get("args")))
                if s:
                    key = _norm_error(r.get("output") or "")
                    s.errors[key] = s.errors.get(key, 0) + 1


@dataclass
class ModelStat:
    model: str
    calls: int = 0
    tok_s: list = field(default_factory=list)
    ctx_pct: list = field(default_factory=list)
    prompt_s: list = field(default_factory=list)
    reloads: int = 0
    failed: int = 0
    num_ctx: int = 0

    @property
    def median_tok_s(self) -> float:
        return _median(self.tok_s)

    @property
    def median_ctx_pct(self) -> int:
        return round(statistics.median(self.ctx_pct)) if self.ctx_pct else 0

    @property
    def max_ctx_pct(self) -> int:
        return round(max(self.ctx_pct)) if self.ctx_pct else 0

    @property
    def median_prompt_s(self) -> float:
        return _median(self.prompt_s)


def _call_rows(trace_files: list[Path]):
    for f in trace_files:
        for r in _read(f):
            if r.get("kind") == "call":
                yield r


def _tok_s(r: dict) -> float | None:
    out = int(r.get("gen_tokens") or r.get("tokens_out") or 0)
    secs = float(r.get("gen_s") or r.get("seconds") or 0)
    return out / secs if out and secs > 0 else None


def model_stats(trace_files: list[Path]) -> list[ModelStat]:
    stats: dict[str, ModelStat] = {}
    for r in _call_rows(trace_files):
        m = stats.setdefault(r.get("model") or "?", ModelStat(r.get("model") or "?"))
        m.calls += 1
        if r.get("error"):
            m.failed += 1
            continue
        ts = _tok_s(r)
        if ts:
            m.tok_s.append(ts)
        if r.get("prompt_s") is not None:
            m.prompt_s.append(float(r["prompt_s"]))
        if float(r.get("load_s") or 0) > RELOAD_S:
            m.reloads += 1
        ctx = int(r.get("num_ctx") or 0)
        if ctx:
            m.num_ctx = max(m.num_ctx, ctx)
            m.ctx_pct.append(100 * int(r.get("tokens_in") or 0) / ctx)
    return sorted(stats.values(), key=lambda m: m.calls, reverse=True)


# ── improvement, trends, breakdowns: one set of signals, grouped different ways ──────────────────────────────

@dataclass
class Signals:
    """The same numbers for any group of turns: a version, a day, a project, a model, a kind of task."""
    label: str = ""
    turns: int = 0
    finished: int = 0
    tool_calls: int = 0
    tool_failures: int = 0
    retries: int = 0
    steps: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0.0
    good: int = 0
    bad: int = 0
    corrections: int = 0
    declines: int = 0
    crashes: int = 0
    tested: int = 0
    first_try: int = 0
    green: list = field(default_factory=list)
    ctx: list = field(default_factory=list)
    sessions: set = field(default_factory=set)
    first: float = 0.0
    # from traces (filled by trends / model views)
    tok_s: list = field(default_factory=list)
    prompt_s: list = field(default_factory=list)
    reloads: int = 0

    def add(self, s: Session, t: Turn) -> None:
        self.turns += 1
        self.finished += t.finished
        self.tool_calls += sum(1 for st in t.steps if st.kind == "tool")
        self.tool_failures += sum(1 for st in t.steps if st.kind == "tool" and not st.ok)
        self.retries += sum(1 for st in t.steps if st.kind == "retry")
        self.steps += sum(1 for st in t.steps if st.kind == "model")
        self.tokens_in += t.tokens_in
        self.tokens_out += t.tokens_out
        self.seconds += t.seconds
        self.good += t.verdict == "good"
        self.bad += t.verdict == "bad"
        self.corrections += len(t.corrections)
        self.declines += len(t.declines)
        self.crashes += t.crashes
        self.tested += t.tested
        self.first_try += t.tested and t.first_try
        if t.green_s is not None:
            self.green.append(t.green_s)
        if t.ctx_used:
            self.ctx.append(t.ctx_used)
        self.sessions.add(f"{s.project}/{s.file}/{s.started}")
        start = t.started or s.started
        self.first = min(self.first, start) if self.first else start

    def rate(self, n: float) -> float:
        return round(n / self.turns, 2) if self.turns else 0.0

    @property
    def finished_pct(self) -> int:
        return round(100 * self.finished / self.turns) if self.turns else 0

    @property
    def first_try_pct(self) -> int | None:
        return round(100 * self.first_try / self.tested) if self.tested else None

    @property
    def first_try_text(self) -> str:
        return f"{self.first_try_pct}% ({self.first_try}/{self.tested})" if self.tested else "–"

    @property
    def median_ctx(self) -> int:
        return int(statistics.median(self.ctx)) if self.ctx else 0

    @property
    def median_green_s(self) -> float | None:
        return _median(self.green) if self.green else None

    @property
    def enough(self) -> bool:
        return self.turns >= MIN_TURNS_TO_JUDGE


class VersionStat(Signals):
    """Kept for the earlier API: `version` is the harness version."""

    def __init__(self, version: int = 0, **kw):
        super().__init__(label=f"h{version}", **kw)
        self.version = version


def _turns(sess: list[Session]):
    for s in sess:
        for t in s.turns:
            yield s, t


def improvement(sess: list[Session], by: str = "harness") -> list[Signals]:
    """by="harness": one group per harness version; by="code": per Mitra code version + harness version."""
    groups: dict = {}
    for s, t in _turns(sess):
        if by == "code":
            key = (t.code_version or s.code_version or OLD, t.harness_version)
            g = groups.get(key) or groups.setdefault(key, Signals(label=f"{key[0]} · h{key[1]}"))
        else:
            g = groups.get(t.harness_version) or groups.setdefault(t.harness_version, VersionStat(t.harness_version))
        g.add(s, t)
    return sorted(groups.values(), key=lambda g: g.first)


def trends(sess: list[Session], trace_files: list[Path] | None = None) -> list[Signals]:
    """Day by day (user, 2026-11-07), oldest first; speed and reloads from the traces of that day."""
    days: dict[str, Signals] = {}
    for s, t in _turns(sess):
        d = _day(t.started or s.started)
        days.setdefault(d, Signals(label=d)).add(s, t)
    for r in _call_rows(trace_files or []):
        d = _day(float(r.get("t") or 0))
        g = days.setdefault(d, Signals(label=d))
        ts = _tok_s(r)
        if ts:
            g.tok_s.append(ts)
        if r.get("prompt_s") is not None:
            g.prompt_s.append(float(r["prompt_s"]))
        if float(r.get("load_s") or 0) > RELOAD_S:
            g.reloads += 1
    return [days[k] for k in sorted(days)]


# kind of task, from the project's files (user, 2026-11-07): game / site / db / app / other
_KIND_CACHE: dict[str, str] = {}


def project_kind(project_dir: Path | None) -> str:
    if project_dir is None or not project_dir.is_dir():
        return "other"
    key = str(project_dir)
    if key in _KIND_CACHE:
        return _KIND_CACHE[key]
    kind, seen = "other", 0
    text_hits = {"game": 0, "app": 0, "db": 0, "site": 0}
    try:
        for p in project_dir.rglob("*"):
            if seen > 400:
                break
            if any(part in (".git", ".venv", "node_modules", ".mitra", "__pycache__") for part in p.parts):
                continue
            if not p.is_file():
                continue
            seen += 1
            suf = p.suffix.lower()
            if suf in (".sql", ".sqlite", ".db") or p.name.lower() in ("schema.sql", "alembic.ini"):
                text_hits["db"] += 2
            if suf in (".html", ".css"):
                text_hits["site"] += 1
            if suf == ".py" and p.stat().st_size < 300_000:
                src = p.read_text(encoding="utf-8", errors="ignore")
                if "import pygame" in src or "from pygame" in src:
                    text_hits["game"] += 3
                if "fastapi" in src.lower() or "flask" in src.lower() or "django" in src.lower():
                    text_hits["app"] += 3
                if "sqlite3" in src or "sqlalchemy" in src.lower():
                    text_hits["db"] += 1
            if p.name == "package.json":
                text_hits["app"] += 1
                text_hits["site"] += 1
    except OSError:
        pass
    best = max(text_hits, key=text_hits.get)
    kind = best if text_hits[best] > 0 else "other"
    _KIND_CACHE[key] = kind
    return kind


def _project_dirs() -> dict[str, Path]:
    """Display name -> folder, from the projects Mitra ran in (projects.json)."""
    out = {}
    for p in store.known_projects():
        out.setdefault(store.project_name(store.project_slug(p)), p)
    return out


def breakdown(sess: list[Session], by: str) -> list[Signals]:
    """by="project" | "model" | "kind"."""
    dirs = _project_dirs() if by == "kind" else {}
    groups: dict[str, Signals] = {}
    for s, t in _turns(sess):
        if by == "project":
            key = s.project
        elif by == "model":
            key = t.model or s.machine.get("model") or OLD
        else:
            key = project_kind(dirs.get(s.project))
        groups.setdefault(key, Signals(label=key)).add(s, t)
    return sorted(groups.values(), key=lambda g: g.turns, reverse=True)


# ── training data ────────────────────────────────────────────────────────────

@dataclass
class Training:
    turns: int = 0
    usable: int = 0
    untested: int = 0                               # usable through your 👍 without tests
    reasons: dict = field(default_factory=dict)     # why a turn is out -> count
    by_day: dict = field(default_factory=dict)      # day -> usable that day

    @property
    def target_pct(self) -> int:
        return min(100, round(100 * self.usable / TRAINING_TARGET))


def _turn_calls(record: Path) -> dict[int, list[dict]]:
    """Rebuilt trace calls of a record, by turn (solve runs: turn 1); failed calls left out."""
    tf = trace_file(record)
    by: dict[int, list[dict]] = {}
    if tf.exists():
        for c in rebuild_calls(_read(tf)):
            if c.get("error") or c.get("purpose") == "compact":
                continue
            by.setdefault(int(c.get("turn") or 1), []).append(c)
    return by


def _why_out(turn: Turn, calls: list[dict]) -> str:
    if turn.authors - {"mitra"}:
        return "written partly by someone else (D-022)"
    if turn.verdict == "bad":
        return "you marked it bad"
    if turn.corrections:
        return "you corrected it"
    if not calls:
        return "no trace (recorded before traces existed, or traces off)"
    if turn.verdict == "good":
        return ""  # your 👍 makes it usable even without tests (user, 2026-11-07), marked untested in the export
    if turn.outcome not in USABLE_OUTCOMES:
        return {"answered": "no tests run", "tests_failed": "tests failed", "stopped_by_user": "stopped by you",
                "interrupted": "interrupted", "error": "error"}.get(turn.outcome, turn.outcome or "unknown")
    return ""


def training(files: list[Path]) -> Training:
    tr = Training()
    for f in files:
        calls = _turn_calls(f)
        for s in sessions([f]):
            for t in s.turns:
                tr.turns += 1
                why = _why_out(t, calls.get(t.no, []))
                if why:
                    tr.reasons[why] = tr.reasons.get(why, 0) + 1
                else:
                    tr.usable += 1
                    tr.untested += t.outcome not in USABLE_OUTCOMES
                    d = _day(t.started or s.started)
                    tr.by_day[d] = tr.by_day.get(d, 0) + 1
    return tr


def export_training(files: list[Path], out: Path) -> int:
    """Usable turns only, one per line, chat format: {"messages": [... full trajectory, last reply], "tools": [...]}.
    The last call of a turn holds the whole trajectory of that turn. Written locally; nothing is sent anywhere."""
    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for f in files:
            calls = _turn_calls(f)
            for s in sessions([f]):
                for t in s.turns:
                    tc = calls.get(t.no, [])
                    if _why_out(t, tc):
                        continue
                    last = tc[-1]
                    fh.write(json.dumps({"messages": last["messages"] + ([last["reply"]] if last.get("reply") else []),
                                         "tools": last.get("tools") or [],
                                         "meta": {"project": s.project, "file": s.file, "turn": t.no,
                                                  "model": last.get("model"), "outcome": t.outcome,
                                                  "untested": t.outcome not in USABLE_OUTCOMES,
                                                  "verdict": t.verdict, "harness_version": t.harness_version,
                                                  "code_version": t.code_version}},
                                        ensure_ascii=False) + "\n")
                    n += 1
    return n
