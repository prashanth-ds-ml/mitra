"""What the dashboard shows, computed from the central store (dashboard steps 2-5, D-041). Pure functions over
record and trace files, so every number is testable from fixtures.

- sessions():    each session as turns and steps (step 2)
- tool_stats():  calls, failures and time per tool / MCP server; model_stats(): speed and context per model (step 3)
- improvement(): signals per harness version (step 4)
- training():    usable runs for the fine-tune and why the rest are out; export_training() (step 5)
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from app.core import store
from app.core.loop import rebuild_calls

MIN_TURNS_TO_JUDGE = 20   # below this a version's numbers are shown as "not enough data"
TRAINING_TARGET = 300     # SCOPE: a few hundred passing runs before any fine-tune
USABLE_OUTCOMES = {"tests_passed", "passed"}  # chat turns / mitra solve runs whose tests passed


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


# ── step 2: sessions ─────────────────────────────────────────────────────────

@dataclass
class Step:
    kind: str            # model | tool | retry | error | stopped | tests
    name: str = ""
    detail: str = ""
    ok: bool = True
    seconds: float = 0.0
    tokens: int = 0


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
    harness_version: int = 0
    steps: list[Step] = field(default_factory=list)
    authors: set = field(default_factory=set)


@dataclass
class Session:
    project: str
    file: str
    kind: str            # chat | solve
    started: float = 0.0
    turns: list[Turn] = field(default_factory=list)


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


def sessions(files: list[Path]) -> list[Session]:
    out = []
    for f in files:
        rows = _read(f)
        if not rows:
            continue
        kind = "chat" if any(r.get("kind") == "turn_start" for r in rows) else "solve"
        s = Session(project=store.project_of(f), file=f.name, kind=kind, started=float(rows[0].get("t") or 0))
        cur: Turn | None = None
        prev_t = None
        for r in rows:
            k, t = r.get("kind"), float(r.get("t") or 0)
            dt = round(t - prev_t, 1) if prev_t else 0.0
            prev_t = t
            if k in ("turn_start", "start"):
                cur = Turn(no=int(r.get("turn") or len(s.turns) + 1), user=str(r.get("user") or r.get("task") or ""),
                           mode=str(r.get("mode") or ""), model=str(r.get("model") or ""),
                           harness_version=int(r.get("harness_version") or 0))
                cur.authors.add(r.get("author", "mitra"))
                s.turns.append(cur)
                continue
            if cur is None:
                continue
            cur.authors.add(r.get("author", "mitra"))
            if k == "model":
                calls = r.get("tool_calls") or []
                cur.steps.append(Step("model", "reply" if not calls else ", ".join(c.get("name", "?") for c in calls),
                                      str(r.get("text") or "")[:300], True, dt, int(r.get("tokens_out") or 0)))
            elif k == "tool":
                cur.steps.append(Step("tool", _tool_label(str(r.get("name")), r.get("args")), _args_text(r.get("args")),
                                      bool(r.get("ok")), dt))
            elif k in ("bad_tool_call", "model_error"):
                cur.steps.append(Step("retry", k, str(r.get("error") or "")[:300], False, dt))
            elif k == "stopped":
                cur.steps.append(Step("stopped", "", str(r.get("reason") or ""), False, dt))
            elif k == "tests":
                cur.steps.append(Step("tests", "", str(r.get("summary") or r.get("output") or "")[:200],
                                      bool(r.get("passed", r.get("ok"))), dt))
            elif k in ("turn_end", "end"):
                cur.outcome = str(r.get("outcome") or r.get("status") or ("stopped" if r.get("stopped") else "answered"))
                cur.reason = str(r.get("reason") or r.get("summary") or "")[:300]
                cur.seconds = float(r.get("seconds") or 0)
                cur.tokens_in, cur.tokens_out = int(r.get("tokens_in") or 0), int(r.get("tokens_out") or 0)
                if kind == "chat":
                    cur = None
        for t in s.turns:  # a turn with a start and no end: the session was killed mid-turn
            t.outcome = t.outcome or "interrupted"
        out.append(s)
    return sorted(out, key=lambda s: s.started, reverse=True)


# ── step 3: tools and models ─────────────────────────────────────────────────

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
        return round(statistics.median(self.seconds), 1) if self.seconds else 0.0

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
    num_ctx: int = 0

    @property
    def median_tok_s(self) -> float:
        return round(statistics.median(self.tok_s), 1) if self.tok_s else 0.0

    @property
    def median_ctx_pct(self) -> int:
        return round(statistics.median(self.ctx_pct)) if self.ctx_pct else 0

    @property
    def max_ctx_pct(self) -> int:
        return round(max(self.ctx_pct)) if self.ctx_pct else 0


def model_stats(trace_files: list[Path]) -> list[ModelStat]:
    stats: dict[str, ModelStat] = {}
    for f in trace_files:
        for r in _read(f):
            if r.get("kind") != "call":
                continue
            m = stats.setdefault(r.get("model") or "?", ModelStat(r.get("model") or "?"))
            m.calls += 1
            out, secs = int(r.get("tokens_out") or 0), float(r.get("seconds") or 0)
            if out and secs > 0:
                m.tok_s.append(out / secs)
            ctx = int(r.get("num_ctx") or 0)
            if ctx:
                m.num_ctx = max(m.num_ctx, ctx)
                m.ctx_pct.append(100 * int(r.get("tokens_in") or 0) / ctx)
    return sorted(stats.values(), key=lambda m: m.calls, reverse=True)


# ── step 4: is it improving ──────────────────────────────────────────────────

@dataclass
class VersionStat:
    version: int
    turns: int = 0
    finished: int = 0          # not stopped by the user, not interrupted, not an error
    tool_failures: int = 0
    retries: int = 0
    steps: int = 0
    first: float = 0.0

    def rate(self, n: int) -> float:
        return round(n / self.turns, 2) if self.turns else 0.0

    @property
    def finished_pct(self) -> int:
        return round(100 * self.finished / self.turns) if self.turns else 0

    @property
    def enough(self) -> bool:
        return self.turns >= MIN_TURNS_TO_JUDGE


def improvement(sess: list[Session]) -> list[VersionStat]:
    by: dict[int, VersionStat] = {}
    for s in sess:
        for t in s.turns:
            v = by.setdefault(t.harness_version, VersionStat(t.harness_version, first=s.started))
            v.first = min(v.first, s.started) if v.first else s.started
            v.turns += 1
            v.finished += t.outcome not in ("stopped_by_user", "interrupted", "error", "stopped")
            v.tool_failures += sum(1 for st in t.steps if st.kind == "tool" and not st.ok)
            v.retries += sum(1 for st in t.steps if st.kind == "retry")
            v.steps += sum(1 for st in t.steps if st.kind == "model")
    return [by[k] for k in sorted(by)]


# ── step 5: training data ────────────────────────────────────────────────────

@dataclass
class Training:
    turns: int = 0
    usable: int = 0
    reasons: dict = field(default_factory=dict)   # why a turn is out -> count

    @property
    def target_pct(self) -> int:
        return min(100, round(100 * self.usable / TRAINING_TARGET))


def _turn_calls(record: Path) -> dict[int, list[dict]]:
    """Rebuilt trace calls of a record, by turn (solve runs: turn 1)."""
    tf = trace_file(record)
    by: dict[int, list[dict]] = {}
    if tf.exists():
        for c in rebuild_calls(_read(tf)):
            by.setdefault(int(c.get("turn") or 1), []).append(c)
    return by


def _why_out(turn: Turn, calls: list[dict]) -> str:
    if turn.authors - {"mitra"}:
        return "written partly by someone else (D-022)"
    if not calls:
        return "no trace (recorded before traces existed, or traces off)"
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
                                                  "harness_version": t.harness_version}},
                                        ensure_ascii=False) + "\n")
                    n += 1
    return n
