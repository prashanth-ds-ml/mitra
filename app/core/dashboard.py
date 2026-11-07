"""A local dashboard page (self-improvement step 2): playground results over time, problems found in run records,
and the harness history. One static HTML file, no server, no network."""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

from app.core import analyze as A
from app.core import harness as H

MITRA_ROOT = Path(__file__).resolve().parents[2]


def default_roots() -> list[Path]:
    """Where to look for records: the current folder and the folder holding the Mitra repo (playground lives there)."""
    cwd, home = Path.cwd().resolve(), MITRA_ROOT.parent
    if cwd == home or home in cwd.parents:
        return [home]
    return [home, cwd]


def run_files(roots: list[Path] | None = None) -> list[Path]:
    """Every run record ever made, from the central store (D-041). Records under `roots`, the known projects and
    ~/.mitra are merged in first (append-only), so nothing written before the store existed is missed."""
    from app.core import store
    store.import_all(roots or default_roots())
    return store.stored_files()


def load_results(roots: list[Path]) -> list[dict]:
    rows = []
    seen = set()
    for root in roots:
        for f in list(root.glob("results/*/*.json")) + list(root.glob("*/results/*/*.json")):
            if f.resolve() in seen:
                continue
            seen.add(f.resolve())
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if "level" in d and "visible_plus_hidden" in d:
                rows.append(d)
    return sorted(rows, key=lambda d: d.get("date", ""))


def _rate(counts: dict) -> tuple[int, int]:
    passed = int(counts.get("passed", 0))
    total = passed + int(counts.get("failed", 0)) + int(counts.get("error", 0)) + int(counts.get("errors", 0))
    return passed, total


def harness_history() -> list[tuple[str, str]]:
    hist = sorted((H.active_path().parent / "harness" / "history").glob("*-v*.toml"))
    return [(p.stem, H.load(p).note) for p in hist]


CSS = """
:root{--bg:#050a06;--panel:#0b140d;--line:#1d3322;--text:#b8f0c0;--dim:#5f9a68;--acc:#5cff7a;--err:#ff6b5c;--info:#9ef0d0}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f4faf5;--panel:#fff;--line:#cfe3d3;
--text:#16301c;--dim:#4d7356;--acc:#137a2c;--err:#b3261e;--info:#0b6b5a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 ui-monospace,Consolas,monospace}
main{max-width:1000px;margin:0 auto;padding:24px 16px}h1{color:var(--acc);font-size:20px;margin:0 0 4px}
h2{color:var(--info);font-size:15px;margin:28px 0 8px}.dim{color:var(--dim)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.tile b{display:block;font-size:22px;color:var(--acc)}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:8px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--dim);font-weight:normal}
.ok{color:var(--acc)}.bad{color:var(--err)}.bar{height:8px;background:var(--line);border-radius:4px;min-width:80px}
.bar i{display:block;height:8px;background:var(--acc);border-radius:4px}.wrap{overflow-x:auto}
ul{margin:4px 0 0;padding-left:18px}.ex{color:var(--dim);font-size:12px}
"""


def render(results: list[dict], rep: A.Report, history: list[tuple[str, str]], current: H.Harness,
           tries: list[dict] | None = None) -> str:
    e = html.escape
    rows = []
    for d in results:
        vp, vt = _rate(d.get("visible", {}))
        hp, ht = _rate(d.get("visible_plus_hidden", {}))
        pct = round(100 * hp / ht) if ht else 0
        rows.append(
            f"<tr><td>{e(d.get('date', ''))}</td><td>{e(str(d['level']))}</td><td>{e(d.get('model', ''))}</td>"
            f"<td>{vp}/{vt}</td><td>{hp}/{ht}<div class='bar'><i style='width:{pct}%'></i></div></td>"
            f"<td>{round(d.get('build_seconds', 0) / 60, 1)} min</td>"
            f"<td class='{'ok' if d.get('passed') else 'bad'}'>{'passed' if d.get('passed') else 'not passed'}</td></tr>")
    pats = []
    for p in rep.top(12):
        ex = "".join(f"<li class='ex'>{e(x)}</li>" for x in p.examples[:3])
        pats.append(f"<tr><td>{p.count}</td><td>{e(p.name)}<div class='dim'>{e(A.PATTERNS.get(p.name, ''))}</div>"
                    f"<ul>{ex}</ul></td></tr>")
    hist = "".join(f"<tr><td>{e(s)}</td><td>{e(n)}</td></tr>" for s, n in reversed(history[-20:]))
    tried = []
    for t in reversed((tries or [])[-20:]):
        b, c = t.get("base") or {}, t.get("candidate") or {}
        ab = f"{b.get('passed')}/{b.get('total')} → {c.get('passed')}/{c.get('total')}" if b else ""
        cls = "ok" if t.get("result") == "kept" else "dim"
        tried.append(f"<tr><td>{e(t.get('date', ''))}</td><td>{e(t.get('change', '') or t.get('top_pattern', ''))}"
                     f"<div class='ex'>{e(t.get('reason', ''))}</div></td><td>{e(ab)}</td>"
                     f"<td class='{cls}'>{e(t.get('result', ''))}</td></tr>")
    rules = "".join(f"<li>{e(r)}</li>" for r in current.rules) or "<li class='dim'>none yet</li>"
    last = results[-1] if results else None
    lp, lt = _rate(last["visible_plus_hidden"]) if last else (0, 0)
    tiles = [("runs recorded", len(results)), ("latest hidden+visible", f"{lp}/{lt}" if last else "n/a"),
             ("turns / tasks analysed", rep.units), ("model calls", rep.steps),
             ("problems found", sum(p.count for p in rep.patterns.values())), ("harness version", current.version)]
    tile_html = "".join(f"<div class='tile'><b>{e(str(v))}</b><span class='dim'>{e(k)}</span></div>" for k, v in tiles)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mitra Dashboard</title><style>{CSS}</style></head>
<body><main><h1>Mitra dashboard</h1><div class="dim">made {time.strftime('%Y-%m-%d %H:%M')} · local only ·
rebuilt when a Mitra session ends · /report or `mitra report --html` to refresh</div><div class="tiles">{tile_html}</div>
<h2>Playground results</h2><div class="wrap"><table><tr><th>date</th><th>level</th><th>model</th><th>visible</th>
<th>visible + hidden</th><th>build</th><th>result</th></tr>{''.join(rows) or "<tr><td colspan=7 class='dim'>no results yet</td></tr>"}
</table></div>
<h2>Problems in run records ({rep.files} files)</h2><div class="wrap"><table><tr><th>count</th><th>pattern</th></tr>
{''.join(pats) or "<tr><td colspan=2 class='dim'>none found</td></tr>"}</table></div>
<h2>What Mitra has learned (harness v{current.version})</h2><ul>{rules}</ul>
<h2>Improve attempts (mitra improve)</h2><div class="wrap"><table><tr><th>date</th><th>proposal</th>
<th>tune tasks passed</th><th>result</th></tr>{''.join(tried) or "<tr><td colspan=4 class='dim'>none yet</td></tr>"}
</table></div>
<h2>Harness history</h2><div class="wrap"><table><tr><th>version</th><th>why</th></tr>
{hist or "<tr><td colspan=2 class='dim'>no changes yet</td></tr>"}</table></div></main></body></html>"""


CSS += """
details{background:var(--panel);border:1px solid var(--line);border-radius:8px;margin:6px 0;padding:6px 10px}
summary{cursor:pointer}details details{margin-left:8px}.steps td{font-size:12px;padding:3px 8px}
.pill{display:inline-block;padding:0 6px;border-radius:4px;border:1px solid var(--line);font-size:12px}
svg.spark{width:120px;height:28px;vertical-align:middle}svg.spark polyline{fill:none;stroke:var(--acc);stroke-width:2}
.note{color:var(--dim);font-size:12px;margin:4px 0}
pre{white-space:pre-wrap;font-size:11px;margin:4px 0}
select{background:var(--panel);color:var(--text);border:1px solid var(--line)}
"""

_OUTCOME_CLS = {"tests_passed": "ok", "answered": "", "passed": "ok", "tests_failed": "bad", "failed": "bad",
                "stopped_by_user": "bad", "interrupted": "bad", "error": "bad", "stopped": "bad"}


def _spark(values: list[float]) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pts = " ".join(f"{round(i * 118 / (len(values) - 1) + 1)},{round(26 - (v - lo) * 24 / span)}"
                   for i, v in enumerate(values))
    return f"<svg class='spark' viewBox='0 0 120 28' aria-hidden='true'><polyline points='{pts}'/></svg>"


def _fmt(v, suffix="", none="–"):
    if v is None:
        return none
    if isinstance(v, float):
        return f"{v:g}{suffix}"
    return f"{v}{suffix}"


def _signal_cells(g) -> str:
    """The shared columns for any group (version, day, project, model, kind)."""
    ft = g.first_try_pct
    return (f"<td>{g.turns}</td><td>{g.finished_pct}%</td><td>{_fmt(ft, '%')}</td>"
            f"<td>{_fmt(g.median_green_s, 's')}</td><td>{g.rate(g.steps)}</td><td>{g.rate(g.tool_failures)}</td>"
            f"<td>{g.rate(g.retries)}</td><td>{round(g.rate(g.tokens_in + g.tokens_out)):,}</td>"
            f"<td>{g.good}/{g.bad}</td><td>{g.rate(g.corrections)}</td><td>{g.declines}</td><td>{g.crashes}</td>")


_SIGNAL_HEAD = ("<th>turns</th><th>finished</th><th>first try</th><th>time to green</th><th>steps/turn</th>"
                "<th>tool fails/turn</th><th>retries/turn</th><th>tokens/turn</th><th>👍/👎</th><th>your fixes/turn</th>"
                "<th>declined</th><th>crashes</th>")


def _group_table(groups, first_col: str, *, note_thin: bool = False) -> str:
    from app.core import insights as I
    e = html.escape
    rows = []
    for g in groups:
        thin = (f"<td class='dim'>not enough data ({g.turns} of {I.MIN_TURNS_TO_JUDGE})</td>"
                if note_thin and not g.enough else ("<td></td>" if note_thin else ""))
        rows.append(f"<tr><td>{e(g.label)}</td>{_signal_cells(g)}{thin}</tr>")
    head = f"<tr><th>{e(first_col)}</th>{_SIGNAL_HEAD}{'<th></th>' if note_thin else ''}</tr>"
    empty = "<tr><td colspan=14 class='dim'>no turns yet</td></tr>"
    return f"<div class='wrap'><table>{head}{''.join(rows) or empty}</table></div>"


def render_more(sess, tools, models, versions, tr, *, days=None, by_code=None, by_project=None, by_model=None,
                by_kind=None, max_sessions: int | None = None) -> str:
    """Sessions, trends, improvement, breakdowns, your judgment, crashes, tools, models, training data."""
    from app.core import insights as I
    e = html.escape
    days = days or []

    # ── headline + trends (day by day) ──
    tiles = ""
    trend = ""
    day_table = ""
    if days:
        last = days[-7:]
        def pool(gs, attr):
            return sum(getattr(g, attr) for g in gs)
        tested, ft = pool(last, "tested"), pool(last, "first_try")
        greens = [x for g in last for x in g.green]
        turns7 = pool(last, "turns")
        tiles_data = [
            ("first try (last 7 days)", f"{round(100 * ft / tested)}%" if tested else "–"),
            ("time to green, median", f"{I._median(greens):g}s" if greens else "–"),
            ("👍 / 👎 (last 7 days)", f"{pool(last, 'good')} / {pool(last, 'bad')}"),
            ("your fixes per turn", f"{round(pool(last, 'corrections') / turns7, 2) if turns7 else 0}"),
            ("turns (last 7 days)", turns7),
            ("crashes (last 7 days)", pool(last, "crashes")),
        ]
        tiles = "<div class='tiles'>" + "".join(
            f"<div class='tile'><b>{e(str(v))}</b><span class='dim'>{e(k)}</span></div>" for k, v in tiles_data) + "</div>"
        series = [
            ("turns", [g.turns for g in days]),
            ("first try %", [g.first_try_pct or 0 for g in days]),
            ("steps / turn", [g.rate(g.steps) for g in days]),
            ("tool fails / turn", [g.rate(g.tool_failures) for g in days]),
            ("tokens / turn", [g.rate(g.tokens_in + g.tokens_out) for g in days]),
            ("tok/s", [I._median(g.tok_s) for g in days]),
            ("your fixes / turn", [g.rate(g.corrections) for g in days]),
        ]
        trend = "<div class='note'>" + " · ".join(f"{e(n)} {_spark(v)}" for n, v in series if len(v) >= 2) + "</div>"
        rows = []
        cum = 0
        for g in days:
            cum += tr.by_day.get(g.label, 0)
            rows.append(f"<tr><td>{e(g.label)}</td><td>{len(g.sessions)}</td>{_signal_cells(g)}"
                        f"<td>{_fmt(I._median(g.tok_s) or None)}</td><td>{_fmt(I._median(g.prompt_s) or None, 's')}</td>"
                        f"<td>{g.reloads}</td><td>{cum}</td></tr>")
        day_table = (f"<div class='wrap'><table><tr><th>day</th><th>sessions</th>{_SIGNAL_HEAD}<th>tok/s</th>"
                     f"<th>prompt s</th><th>reloads</th><th>usable (total)</th></tr>{''.join(reversed(rows))}</table></div>")

    # ── sessions (all, folded, filter by project) ──
    projects = sorted({s.project for s in sess})
    options = "".join(f"<option>{e(p)}</option>" for p in projects)
    s_html = []
    for s in (sess if max_sessions is None else sess[:max_sessions]):
        turns = []
        for t in s.turns:
            rows = "".join(
                f"<tr><td>{e(st.kind)}</td><td class='{'' if st.ok else 'bad'}'>{e(st.name)}</td>"
                f"<td>{e(st.detail)}</td><td>{st.seconds:g}s</td><td>{'✓' if st.ok else '✗'}</td></tr>"
                for st in t.steps)
            judged = []
            if t.verdict:
                judged.append(("👍" if t.verdict == "good" else "👎") + (f" {e(t.verdict_note)}" if t.verdict_note else ""))
            if t.corrections:
                judged.append(f"<span class='bad'>you fixed {len(t.corrections)} file(s)</span>")
            if t.declines:
                judged.append(f"<span class='bad'>{len(t.declines)} declined</span>")
            if t.crashes:
                judged.append(f"<span class='bad'>crash</span>")
            fixes = "".join(f"<div class='ex'>{e(c.get('path') or '')}: +{c.get('added') or 0} -{c.get('removed') or 0}"
                            f"<pre>{e((c.get('diff') or '')[:1500])}</pre></div>" for c in t.corrections)
            cls = _OUTCOME_CLS.get(t.outcome, "")
            turns.append(
                f"<details><summary>turn {t.no} · <span class='{cls}'>{e(t.outcome)}</span> · {len(t.steps)} steps · "
                f"{t.seconds:g}s · ↑{t.tokens_in:,} ↓{t.tokens_out:,}{' · ' + ' · '.join(judged) if judged else ''}"
                f" · {e(t.user[:90])}</summary>"
                f"<div class='note'>{e(t.model)} · {e(t.mode)} · Mitra {e(t.code_version or '?')} · harness "
                f"v{t.harness_version}{f' · {t.ram_free_gb} GB RAM free' if t.ram_free_gb is not None else ''}"
                f"{' · time to green ' + str(t.green_s) + 's' if t.green_s is not None else ''}"
                f"{' · ' + e(t.reason) if t.reason else ''}</div>{fixes}"
                f"<div class='wrap'><table class='steps'>{rows}</table></div></details>")
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.started)) if s.started else ""
        bad = sum(1 for t in s.turns if _OUTCOME_CLS.get(t.outcome) == "bad")
        m = s.machine
        machine = (f" · {e(str(m.get('model') or ''))} {int(m.get('num_ctx') or 0) // 1024}K · fit {e(str(m.get('fit')))}"
                   f" · {m.get('ram_free_gb')} GB RAM free" if m else "")
        s_html.append(f"<details class='sess' data-project='{e(s.project)}'><summary>{e(when)} · <b>{e(s.project)}</b> · "
                      f"{e(s.kind)} · {len(s.turns)} turns{machine}"
                      f"{f' · <span class=bad>{bad} not finished</span>' if bad else ''}</summary>{''.join(turns)}</details>")
    filt = (f"<div class='note'>project: <select id='pf' onchange=\"for(const d of document.querySelectorAll('details.sess'))"
            f"d.style.display=(this.value===''||d.dataset.project===this.value)?'':'none'\"><option value=''>all</option>"
            f"{options}</select> · {len(sess)} sessions</div>") if projects else ""

    # ── your judgment and crashes ──
    judged_rows, crash_rows = [], []
    for s in sess:
        for t in s.turns:
            for c in t.corrections:
                judged_rows.append((t.started or s.started, f"<tr><td>{e(_when(t.started or s.started))}</td>"
                                    f"<td>{e(s.project)}</td><td>turn {t.no}</td><td>fixed {e(c.get('path') or '')} "
                                    f"(+{c.get('added') or 0} -{c.get('removed') or 0})</td></tr>"))
            for d in t.declines:
                what = d.get("path") or d.get("command") or ""
                judged_rows.append((t.started or s.started, f"<tr><td>{e(_when(t.started or s.started))}</td>"
                                    f"<td>{e(s.project)}</td><td>turn {t.no}</td><td>declined {e(d.get('tool') or '')} "
                                    f"{e(what)}{' — ' + e(d.get('reason')) if d.get('reason') else ''}</td></tr>"))
            if t.verdict == "bad":
                judged_rows.append((t.started or s.started, f"<tr><td>{e(_when(t.started or s.started))}</td>"
                                    f"<td>{e(s.project)}</td><td>turn {t.no}</td><td>👎 {e(t.verdict_note)}</td></tr>"))
        for c in s.crashes:
            crash_rows.append((c["t"], f"<tr><td>{e(_when(c['t']))}</td><td>{e(s.project)}</td><td>{e(c['error'])}</td></tr>"))
    judged_html = "".join(r for _, r in sorted(judged_rows, reverse=True)[:50])
    crash_html = "".join(r for _, r in sorted(crash_rows, reverse=True)[:30])

    # ── tools and models ──
    t_rows = "".join(
        f"<tr><td>{e(t.name)}</td><td>{t.calls}</td><td class='{'bad' if t.fail_pct >= 20 else ''}'>{t.fail_pct}%</td>"
        f"<td>{t.median_s:g}s / {t.worst_s:g}s</td><td class='ex'>{e(t.top_error)}</td></tr>" for t in tools)
    m_rows = "".join(
        f"<tr><td>{e(m.model)}</td><td>{m.calls}</td><td>{m.median_tok_s:g}</td><td>{m.num_ctx // 1024}K</td>"
        f"<td>{m.median_ctx_pct}% / {m.max_ctx_pct}%</td><td>{_fmt(m.median_prompt_s or None, 's')}</td>"
        f"<td>{m.reloads}</td><td>{m.failed}</td></tr>" for m in models)

    # ── training ──
    r_rows = "".join(f"<tr><td>{n}</td><td>{e(w)}</td></tr>"
                     for w, n in sorted(tr.reasons.items(), key=lambda x: -x[1]))

    return f"""
<h2>Trends (day by day)</h2>{tiles}{trend}{day_table or "<div class='dim'>no turns yet</div>"}
<h2>Is Mitra improving? (per Mitra version · harness version)</h2>{_group_table(by_code or versions, "version", note_thin=True)}
<div class="note">first try = tests passed with no fix from you and no 👎 (of the turns that ran tests) · time to
green = first code edit to passing tests · a version needs {I.MIN_TURNS_TO_JUDGE}+ turns to judge · playground
pass rates (hidden tests) are in "Playground results" above.</div>
<h2>By kind of task</h2>{_group_table(by_kind or [], "kind")}
<h2>By project</h2>{_group_table(by_project or [], "project")}
<h2>By model</h2>{_group_table(by_model or [], "model")}
<h2>Sessions (every project, every run ever)</h2>{filt}{''.join(s_html) or "<div class='dim'>no sessions yet</div>"}
<h2>Your corrections, declines and 👎</h2><div class="wrap"><table><tr><th>when</th><th>project</th><th>turn</th>
<th>what</th></tr>{judged_html or "<tr><td colspan=4 class='dim'>none yet (/good, /bad and your own edits after a turn show here)</td></tr>"}</table></div>
<h2>Crashes</h2><div class="wrap"><table><tr><th>when</th><th>project</th><th>error</th></tr>
{crash_html or "<tr><td colspan=3 class='dim'>none</td></tr>"}</table></div>
<h2>Tools</h2><div class="wrap"><table><tr><th>tool</th><th>calls</th><th>failed</th><th>median / worst</th>
<th>most common error</th></tr>{t_rows or "<tr><td colspan=5 class='dim'>no tool calls yet</td></tr>"}</table></div>
<h2>Models (from traces)</h2><div class="wrap"><table><tr><th>model</th><th>calls</th><th>tok/s (median)</th>
<th>context</th><th>context used median / max</th><th>prompt s (median)</th><th>reloads</th><th>failed calls</th></tr>
{m_rows or "<tr><td colspan=8 class='dim'>no traces yet</td></tr>"}</table></div>
<h2>Training data (D-022)</h2><div class="tiles"><div class="tile"><b>{tr.usable}</b><span class="dim">usable turns
(tests passed or 👍, all Mitra, traced, not corrected)</span></div><div class="tile"><b>{tr.untested}</b><span class="dim">of
them untested (your 👍)</span></div><div class="tile"><b>{tr.turns}</b><span class="dim">turns recorded</span></div>
<div class="tile"><b>{tr.target_pct}%</b><span class="dim">of the {I.TRAINING_TARGET} needed before a fine-tune</span>
<div class="bar"><i style="width:{tr.target_pct}%"></i></div></div></div>
<div class="wrap"><table><tr><th>turns</th><th>why not usable</th></tr>{r_rows or "<tr><td colspan=2 class='dim'>none</td></tr>"}
</table></div><div class="note">Export: <code>mitra report --export-training out.jsonl</code> (local file, nothing sent).
Store: {e(store_text())}</div>"""


def _when(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if t else ""


def store_text() -> str:
    from app.core import store
    return store.size_text()


def page_html(roots: list[Path] | None = None) -> tuple[str, A.Report]:
    """The whole dashboard page from the central store (old records merged in first)."""
    from app.core import insights as I
    from app.core import store
    from app.core.improve import attempts

    roots = roots or default_roots()
    files = run_files(roots)
    rep = A.analyze(files)
    sess = I.sessions(files)
    tools = I.tool_stats(sess)
    I.tool_errors(files, tools)
    traces = store.stored_files("traces")
    page = render(load_results(roots), rep, harness_history(), H.load(), attempts())
    extra = render_more(sess, tools, I.model_stats(traces), I.improvement(sess), I.training(files),
                        days=I.trends(sess, traces), by_code=I.improvement(sess, by="code"),
                        by_project=I.breakdown(sess, "project"), by_model=I.breakdown(sess, "model"),
                        by_kind=I.breakdown(sess, "kind"))
    return page.replace("</main></body></html>", extra + "</main></body></html>"), rep


def build(roots: list[Path] | None = None, out: Path | None = None) -> tuple[Path, A.Report]:
    page, rep = page_html(roots)
    out = out or (H.home() / "dashboard.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out, rep
