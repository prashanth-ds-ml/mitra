"""The Mitra dashboard (D-041, D-042, D-044): one local HTML page from the central store, no network.

Order on the page, most useful first: headline → trends → is it improving → your judgment → where it works
(kind / project / model) → sessions → tools and models → training data → self-improvement internals
(learned rules, improve attempts, harness history, playground, problem patterns)."""
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
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{color:var(--acc);font-size:20px;margin:0 0 4px}
h2{color:var(--info);font-size:15px;margin:30px 0 8px}h3{color:var(--dim);font-size:13px;margin:16px 0 6px;font-weight:normal}
.dim{color:var(--dim)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px;margin-top:10px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.tile b{display:block;font-size:22px;color:var(--acc)}.tile small{color:var(--dim);display:block}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:8px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
th{color:var(--dim);font-weight:normal}td.wide{white-space:normal}
.ok{color:var(--acc)}.bad{color:var(--err)}.bar{height:8px;background:var(--line);border-radius:4px;min-width:80px}
.bar i{display:block;height:8px;background:var(--acc);border-radius:4px}.wrap{overflow-x:auto}
ul{margin:4px 0 0;padding-left:18px}.ex{color:var(--dim);font-size:12px}
details{background:var(--panel);border:1px solid var(--line);border-radius:8px;margin:6px 0;padding:6px 10px}
summary{cursor:pointer}details details{margin-left:8px}.steps td{font-size:12px;padding:3px 8px}
svg.spark{width:100%;height:30px;display:block;margin-top:4px}svg.spark polyline{fill:none;stroke:var(--acc);stroke-width:2}
.note{color:var(--dim);font-size:12px;margin:6px 0}
pre{white-space:pre-wrap;font-size:11px;margin:4px 0}
select{background:var(--panel);color:var(--text);border:1px solid var(--line)}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.t8{grid-template-columns:repeat(auto-fit,minmax(118px,1fr))}
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
    return f"<svg class='spark' viewBox='0 0 120 28' preserveAspectRatio='none' aria-hidden='true'><polyline points='{pts}'/></svg>"


def _fmt(v, suffix="", none="–"):
    if v is None:
        return none
    if isinstance(v, float):
        return f"{v:g}{suffix}"
    return f"{v}{suffix}"


def _when(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if t else ""


def store_text() -> str:
    from app.core import store
    return store.size_text()


# ── shared columns for any group of turns ────────────────────────────────────

_COLS = ("<th>turns</th><th>finished</th><th>first try</th><th>to green</th><th>steps/turn</th>"
         "<th>fails/turn</th><th>👍/👎</th><th>fixes</th><th>crashes</th>")


def _cells(g) -> str:
    return (f"<td>{g.turns}</td><td>{g.finished_pct}%</td><td>{g.first_try_text}</td>"
            f"<td>{_fmt(g.median_green_s, 's')}</td><td>{g.rate(g.steps)}</td><td>{g.rate(g.tool_failures)}</td>"
            f"<td>{g.good}/{g.bad}</td><td>{g.corrections}</td>"
            f"<td class='{'bad' if g.crashes else ''}'>{g.crashes}</td>")


def _group_table(groups, first_col: str, *, judge: bool = False, small: bool = False) -> str:
    from app.core import insights as I
    e = html.escape
    rows = []
    for g in groups:
        if small:
            cells = f"<td>{g.turns}</td><td>{g.first_try_text}</td><td>{g.rate(g.tool_failures)}</td>"
        else:
            cells = _cells(g)
        thin = (f"<div class='ex'>not enough data ({g.turns}/{I.MIN_TURNS_TO_JUDGE} turns)</div>"
                if judge and not g.enough else "")
        rows.append(f"<tr><td class='{'wide' if small else ''}'>{e(g.label)}{thin}</td>{cells}</tr>")
    head_cols = "<th>turns</th><th>first try</th><th>fails</th>" if small else _COLS
    head = f"<tr><th>{e(first_col)}</th>{head_cols}</tr>"
    span = 4 if small else 10
    empty = f"<tr><td colspan={span} class='dim'>no turns yet</td></tr>"
    return f"<div class='wrap'><table>{head}{''.join(rows) or empty}</table></div>"


# ── the sections ─────────────────────────────────────────────────────────────

def render_more(sess, tools, models, versions, tr, *, days=None, by_code=None, by_project=None, by_model=None,
                by_kind=None, max_sessions: int | None = None) -> str:
    """Everything from the store: headline, trends, improvement, your judgment, breakdowns, sessions, tools,
    models, training data."""
    from app.core import insights as I
    e = html.escape
    days = days or []

    # headline: the last 7 days, with counts so small numbers are not mistaken for trends
    last = days[-7:]
    pool = lambda attr: sum(getattr(g, attr) for g in last)  # noqa: E731
    tested, ft, turns7 = pool("tested"), pool("first_try"), pool("turns")
    greens = [x for g in last for x in g.green]
    headline = [
        ("turns", turns7, f"{len({x for g in last for x in g.sessions})} sessions"),
        ("first try", f"{round(100 * ft / tested)}%" if tested else "–", f"{ft} of {tested} tested turns"),
        ("time to green", f"{I._median(greens):g}s" if greens else "–", f"median of {len(greens)}"),
        ("👍 / 👎", f"{pool('good')} / {pool('bad')}", "your marks"),
        ("your fixes", pool("corrections"), f"declined {pool('declines')}"),
        ("crashes", pool("crashes"), "Mitra errors"),
        ("usable for training", tr.usable, f"of {I.TRAINING_TARGET} needed"),
    ]
    head_html = "<div class='tiles'>" + "".join(
        f"<div class='tile'><b>{e(str(v))}</b>{e(k)}<small>{e(sub)}</small></div>" for k, v, sub in headline) + "</div>"

    # trends: one small chart per signal, day by day
    if len(days) >= 2:
        series = [
            ("turns / day", [g.turns for g in days], days[-1].turns),
            ("first try %", [g.first_try_pct or 0 for g in days], f"{days[-1].first_try_pct}%" if days[-1].tested else "–"),
            ("steps / turn", [g.rate(g.steps) for g in days], days[-1].rate(days[-1].steps)),
            ("tool fails / turn", [g.rate(g.tool_failures) for g in days], days[-1].rate(days[-1].tool_failures)),
            ("out tokens / turn", [g.rate(g.tokens_out) for g in days], round(days[-1].rate(days[-1].tokens_out))),
            ("tok/s", [I._median(g.tok_s) for g in days], I._median(days[-1].tok_s) or "–"),
            ("your fixes / turn", [g.rate(g.corrections) for g in days], days[-1].rate(days[-1].corrections)),
            ("seconds / turn", [g.rate(g.seconds) for g in days], round(days[-1].rate(days[-1].seconds))),
        ]
        trend_html = "<div class='tiles t8'>" + "".join(
            f"<div class='tile'><small>{e(n)}</small><b>{e(str(latest))}</b>{_spark(v)}</div>" for n, v, latest in series
        ) + "</div><div class='note'>latest day shown; each line runs from the first day to today</div>"
    else:
        trend_html = f"<div class='note'>Trend lines appear from the second day of use ({len(days)} day so far).</div>"
    day_rows = []
    cum = 0
    for g in days:
        cum += tr.by_day.get(g.label, 0)
        day_rows.append(f"<tr><td>{e(g.label)}</td><td>{len(g.sessions)}</td>{_cells(g)}"
                        f"<td>{round(g.rate(g.tokens_out)):,}</td><td>{_fmt(I._median(g.tok_s) or None)}</td><td>{_fmt(I._median(g.prompt_s) or None, 's')}</td>"
                        f"<td>{g.reloads}</td><td>{cum}</td></tr>")
    day_table = (f"<details><summary>day by day ({len(days)} days)</summary><div class='wrap'><table><tr><th>day</th>"
                 f"<th>sessions</th>{_COLS}<th>out tokens/turn</th><th>tok/s</th><th>prompt s</th><th>reloads</th>"
                 f"<th>usable</th></tr>"
                 f"{''.join(reversed(day_rows))}</table></div></details>") if days else ""

    # your judgment and crashes
    judged, crashes = [], []
    for s in sess:
        for t in s.turns:
            when = t.started or s.started
            for c in t.corrections:
                judged.append((when, f"<tr><td>{e(_when(when))}</td><td>{e(s.project)}</td><td>turn {t.no}</td>"
                                     f"<td class='wide'>you fixed {e(c.get('path') or '')} (+{c.get('added') or 0} "
                                     f"-{c.get('removed') or 0})</td></tr>"))
            for d in t.declines:
                what = d.get("path") or d.get("command") or ""
                judged.append((when, f"<tr><td>{e(_when(when))}</td><td>{e(s.project)}</td><td>turn {t.no}</td>"
                                     f"<td class='wide'>declined {e(d.get('tool') or '')} {e(what)}"
                                     f"{' — ' + e(d.get('reason')) if d.get('reason') else ''}</td></tr>"))
            if t.verdict:
                mark = "👍" if t.verdict == "good" else "👎"
                judged.append((when, f"<tr><td>{e(_when(when))}</td><td>{e(s.project)}</td><td>turn {t.no}</td>"
                                     f"<td class='wide'>{mark} {e(t.verdict_note)}</td></tr>"))
        for c in s.crashes:
            crashes.append((c["t"], f"<tr><td>{e(_when(c['t']))}</td><td>{e(s.project)}</td>"
                                    f"<td class='wide'>{e(c['error'])}</td></tr>"))
    judged_html = "".join(r for _, r in sorted(judged, reverse=True)[:50])
    crash_html = "".join(r for _, r in sorted(crashes, reverse=True)[:30])

    # sessions: all of them, folded, filter by project
    projects = sorted({s.project for s in sess})
    s_html = []
    for s in (sess if max_sessions is None else sess[:max_sessions]):
        turns = []
        for t in s.turns:
            rows = "".join(
                f"<tr><td>{e(st.kind)}</td><td class='{'' if st.ok else 'bad'}'>{e(st.name)}</td>"
                f"<td class='wide'>{e(st.detail)}</td><td>{_fmt(st.seconds, 's')}</td><td>{'✓' if st.ok else '✗'}</td></tr>"
                for st in t.steps)
            marks = []
            if t.verdict:
                marks.append("👍" if t.verdict == "good" else "👎")
            if t.corrections:
                marks.append(f"<span class='bad'>you fixed {len(t.corrections)}</span>")
            if t.declines:
                marks.append(f"<span class='bad'>{len(t.declines)} declined</span>")
            if t.crashes:
                marks.append("<span class='bad'>crash</span>")
            fixes = "".join(f"<div class='ex'>{e(c.get('path') or '')}: +{c.get('added') or 0} -{c.get('removed') or 0}"
                            f"<pre>{e((c.get('diff') or '')[:1500])}</pre></div>" for c in t.corrections)
            info = [x for x in (t.model, t.mode, f"Mitra {t.code_version}" if t.code_version else "",
                                f"harness v{t.harness_version}",
                                f"{t.ram_free_gb} GB RAM free" if t.ram_free_gb is not None else "",
                                f"context {t.ctx_used:,}" if t.ctx_used else "",
                                f"time to green {t.green_s:g}s" if t.green_s is not None else "", t.reason) if x]
            turns.append(
                f"<details><summary>turn {t.no} · <span class='{_OUTCOME_CLS.get(t.outcome, '')}'>{e(t.outcome)}</span> · "
                f"{len(t.steps)} steps · {t.seconds:g}s{' · ' + ' · '.join(marks) if marks else ''} · {e(t.user[:80])}"
                f"</summary><div class='note'>{e(' · '.join(info))}</div>{fixes}"
                f"<div class='wrap'><table class='steps'>{rows}</table></div></details>")
        bad = sum(1 for t in s.turns if _OUTCOME_CLS.get(t.outcome) == "bad")
        m = s.machine
        machine = (f" · {e(str(m.get('model') or ''))} {int(m.get('num_ctx') or 0) // 1024}K · fit {e(str(m.get('fit')))}"
                   f" · {m.get('ram_free_gb')} GB free" if m else "")
        s_html.append(f"<details class='sess' data-project='{e(s.project)}'><summary>{e(_when(s.started))} · "
                      f"<b>{e(s.project)}</b> · {e(s.kind)} · {len(s.turns)} turns{machine}"
                      f"{f' · <span class=bad>{bad} not finished</span>' if bad else ''}</summary>{''.join(turns)}</details>")
    options = "".join(f"<option>{e(p)}</option>" for p in projects)
    filt = (f"<div class='note'>project: <select id='pf' onchange=\"for(const d of document.querySelectorAll('details.sess'))"
            f"d.style.display=(this.value===''||d.dataset.project===this.value)?'':'none'\"><option value=''>all</option>"
            f"{options}</select> · {len(sess)} sessions, newest first</div>") if projects else ""

    # tools and models
    t_rows = "".join(
        f"<tr><td>{e(t.name)}</td><td>{t.calls}</td><td class='{'bad' if t.fail_pct >= 20 else ''}'>{t.fail_pct}%</td>"
        f"<td>{_fmt(t.median_s or None, 's')}</td><td class='wide ex'>{e(t.top_error)}</td></tr>" for t in tools)
    m_rows = "".join(
        f"<tr><td>{e(m.model)}</td><td>{m.calls}</td><td>{m.median_tok_s:g}</td><td>{m.num_ctx // 1024}K</td>"
        f"<td>{m.median_ctx_pct}% / {m.max_ctx_pct}%</td><td>{_fmt(m.median_prompt_s or None, 's')}</td>"
        f"<td>{m.reloads}</td><td>{m.failed}</td></tr>" for m in models)

    # training
    r_rows = "".join(f"<tr><td>{n}</td><td>{e(w)}</td></tr>" for w, n in sorted(tr.reasons.items(), key=lambda x: -x[1]))

    return f"""
{head_html}
<h2>Trends</h2>{trend_html}{day_table}
<h2>Is Mitra improving?</h2>{_group_table(by_code or versions, "Mitra version · harness", judge=True)}
<div class="note">first try = tests passed, no fix from you, no 👎 (count of tested turns in brackets) · time to green
= first code edit to passing tests · fails/turn = tool failures per turn · fixes = files you changed after
Mitra · "{I.OLD}" = records from before the version was saved · a version needs {I.MIN_TURNS_TO_JUDGE}+ turns to judge</div>
<h2>Your corrections, declines and marks</h2><div class="wrap"><table><tr><th>when</th><th>project</th><th>turn</th>
<th>what</th></tr>{judged_html or "<tr><td colspan=4 class='dim'>none yet: /good, /bad and your own edits after a turn show here</td></tr>"}</table></div>
<h3>Crashes</h3><div class="wrap"><table><tr><th>when</th><th>project</th><th>error</th></tr>
{crash_html or "<tr><td colspan=3 class='dim'>none</td></tr>"}</table></div>
<h2>Where it works</h2><div class="grid3"><div><h3>by kind of task</h3>{_group_table(by_kind or [], "kind", small=True)}</div>
<div><h3>by project</h3>{_group_table(by_project or [], "project", small=True)}</div>
<div><h3>by model</h3>{_group_table(by_model or [], "model", small=True)}</div></div>
<h2>Sessions</h2>{filt}{''.join(s_html) or "<div class='dim'>no sessions yet</div>"}
<h2>Tools</h2><div class="wrap"><table><tr><th>tool</th><th>calls</th><th>failed</th><th>median time</th>
<th>most common error</th></tr>{t_rows or "<tr><td colspan=5 class='dim'>no tool calls yet</td></tr>"}</table></div>
<div class="note">run_tests "failed" = the tests failed, not the tool · read_file failures include repeats the guard refused</div>
<h2>Models (from traces)</h2><div class="wrap"><table><tr><th>model</th><th>calls</th><th>tok/s</th><th>context</th>
<th>context used (median / max)</th><th>prompt s (median)</th><th>reloads</th><th>failed calls</th></tr>
{m_rows or "<tr><td colspan=8 class='dim'>no traces yet</td></tr>"}</table></div>
<h2>Training data (D-022)</h2><div class="tiles"><div class="tile"><b>{tr.usable}</b>usable turns<small>tests passed or
👍 · all Mitra · traced · not corrected</small></div><div class="tile"><b>{tr.untested}</b>of them untested<small>your
👍 without tests</small></div><div class="tile"><b>{tr.turns}</b>turns recorded</div><div class="tile"><b>{tr.target_pct}%</b>
of {I.TRAINING_TARGET} needed<div class="bar"><i style="width:{tr.target_pct}%"></i></div></div></div>
<div class="wrap" style="margin-top:10px"><table><tr><th>turns</th><th>why not usable</th></tr>{r_rows or "<tr><td colspan=2 class='dim'>none</td></tr>"}
</table></div><div class="note">Export: <code>mitra report --export-training out.jsonl</code> (local file, nothing
sent) · store {e(store_text())}</div>"""


def render(results: list[dict], rep: A.Report, history: list[tuple[str, str]], current: H.Harness,
           tries: list[dict] | None = None, more_html: str = "") -> str:
    """The whole page: header, the store sections (`more_html`), then the self-improvement internals."""
    from app.core import runinfo
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
        pats.append(f"<details><summary><b>{p.count}</b> · {e(p.name)} <span class='dim'>— "
                    f"{e(A.PATTERNS.get(p.name, ''))}</span></summary><ul>{ex}</ul></details>")
    hist = "".join(f"<tr><td>{e(s)}</td><td class='wide'>{e(n)}</td></tr>" for s, n in reversed(history[-20:]))
    tried = []
    for t in reversed((tries or [])[-20:]):
        b, c = t.get("base") or {}, t.get("candidate") or {}
        ab = f"{b.get('passed')}/{b.get('total')} → {c.get('passed')}/{c.get('total')}" if b else ""
        cls = "ok" if t.get("result") == "kept" else "dim"
        tried.append(f"<tr><td>{e(t.get('date', ''))}</td><td class='wide'>{e(t.get('change', '') or t.get('top_pattern', ''))}"
                     f"<div class='ex'>{e(t.get('reason', ''))}</div></td><td>{e(ab)}</td>"
                     f"<td class='{cls}'>{e(t.get('result', ''))}</td></tr>")
    rules = "".join(f"<li>{e(r)}</li>" for r in current.rules) or "<li class='dim'>none yet</li>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mitra Dashboard</title><style>{CSS}</style></head>
<body><main><h1>Mitra dashboard</h1><div class="dim">made {time.strftime('%Y-%m-%d %H:%M')} · Mitra
{e(runinfo.code_version())} · harness v{current.version} · local only · rebuilt when a Mitra session ends · /report
or <code>mitra dashboard</code></div>
{more_html}
<h2>Self-improvement</h2>
<h3>What Mitra has learned (harness v{current.version})</h3><ul>{rules}</ul>
<h3>Improve attempts (mitra improve)</h3><div class="wrap"><table><tr><th>date</th><th>proposal</th>
<th>tune tasks passed</th><th>result</th></tr>{''.join(tried) or "<tr><td colspan=4 class='dim'>none yet</td></tr>"}
</table></div>
<h3>Harness history</h3><div class="wrap"><table><tr><th>version</th><th>why</th></tr>
{hist or "<tr><td colspan=2 class='dim'>no changes yet</td></tr>"}</table></div>
<h3>Playground results (hidden tests)</h3><div class="wrap"><table><tr><th>date</th><th>level</th><th>model</th>
<th>visible</th><th>visible + hidden</th><th>build</th><th>result</th></tr>{''.join(rows) or "<tr><td colspan=7 class='dim'>no results yet</td></tr>"}
</table></div>
<h3>Problem patterns in the records ({rep.files} files) — what <code>mitra improve</code> works on</h3>
{''.join(pats) or "<div class='dim'>none found</div>"}</main></body></html>"""


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
    more = render_more(sess, tools, I.model_stats(traces), I.improvement(sess), I.training(files),
                       days=I.trends(sess, traces), by_code=I.improvement(sess, by="code"),
                       by_project=I.breakdown(sess, "project"), by_model=I.breakdown(sess, "model"),
                       by_kind=I.breakdown(sess, "kind"))
    return render(load_results(roots), rep, harness_history(), H.load(), attempts(), more_html=more), rep


def build(roots: list[Path] | None = None, out: Path | None = None) -> tuple[Path, A.Report]:
    page, rep = page_html(roots)
    out = out or (H.home() / "dashboard.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out, rep
