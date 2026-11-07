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


def render_more(sess, tools, models, versions, tr, *, max_sessions: int = 40) -> str:
    """Steps 2-5: sessions, tools and models, improvement, training data."""
    from app.core import insights as I
    e = html.escape

    # step 2: sessions
    s_html = []
    for s in sess[:max_sessions]:
        turns = []
        for t in s.turns:
            rows = "".join(
                f"<tr><td>{e(st.kind)}</td><td class='{'' if st.ok else 'bad'}'>{e(st.name)}</td>"
                f"<td>{e(st.detail)}</td><td>{st.seconds:g}s</td><td>{'✓' if st.ok else '✗'}</td></tr>"
                for st in t.steps)
            cls = _OUTCOME_CLS.get(t.outcome, "")
            turns.append(
                f"<details><summary>turn {t.no} · <span class='{cls}'>{e(t.outcome)}</span> · {len(t.steps)} steps · "
                f"{t.seconds:g}s · ↑{t.tokens_in:,} ↓{t.tokens_out:,} · {e(t.user[:90])}</summary>"
                f"<div class='note'>{e(t.model)} · {e(t.mode)} · harness v{t.harness_version}"
                f"{' · ' + e(t.reason) if t.reason else ''}</div>"
                f"<div class='wrap'><table class='steps'>{rows}</table></div></details>")
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.started)) if s.started else ""
        bad = sum(1 for t in s.turns if _OUTCOME_CLS.get(t.outcome) == "bad")
        s_html.append(f"<details><summary>{e(when)} · <b>{e(s.project)}</b> · {e(s.kind)} · {len(s.turns)} turns"
                      f"{f' · <span class=bad>{bad} not finished</span>' if bad else ''}</summary>{''.join(turns)}</details>")
    more = f"<div class='note'>showing the newest {max_sessions} of {len(sess)}</div>" if len(sess) > max_sessions else ""

    # step 3: tools and models
    t_rows = "".join(
        f"<tr><td>{e(t.name)}</td><td>{t.calls}</td><td class='{'bad' if t.fail_pct >= 20 else ''}'>{t.fail_pct}%</td>"
        f"<td>{t.median_s:g}s / {t.worst_s:g}s</td><td class='ex'>{e(t.top_error)}</td></tr>" for t in tools)
    m_rows = "".join(
        f"<tr><td>{e(m.model)}</td><td>{m.calls}</td><td>{m.median_tok_s:g}</td><td>{m.num_ctx // 1024}K</td>"
        f"<td>{m.median_ctx_pct}% / {m.max_ctx_pct}%</td></tr>" for m in models)

    # step 4: improvement
    v_rows = []
    for v in versions:
        note = "" if v.enough else f"<span class='dim'>not enough data ({v.turns} of {I.MIN_TURNS_TO_JUDGE} turns)</span>"
        v_rows.append(f"<tr><td>v{v.version}</td><td>{v.turns}</td><td>{v.finished_pct}%</td>"
                      f"<td>{v.rate(v.tool_failures)}</td><td>{v.rate(v.retries)}</td><td>{v.rate(v.steps)}</td>"
                      f"<td>{note}</td></tr>")
    trend = ""
    if len(versions) >= 2:
        trend = (f"<div class='note'>finished % {_spark([v.finished_pct for v in versions])} · tool failures/turn "
                 f"{_spark([v.rate(v.tool_failures) for v in versions])} · retries/turn "
                 f"{_spark([v.rate(v.retries) for v in versions])} (one point per harness version)</div>")

    # step 5: training
    r_rows = "".join(f"<tr><td>{n}</td><td>{e(w)}</td></tr>"
                     for w, n in sorted(tr.reasons.items(), key=lambda x: -x[1]))

    return f"""
<h2>Sessions (every project, every run ever)</h2>{''.join(s_html) or "<div class='dim'>no sessions yet</div>"}{more}
<h2>Tools</h2><div class="wrap"><table><tr><th>tool</th><th>calls</th><th>failed</th><th>median / worst</th>
<th>most common error</th></tr>{t_rows or "<tr><td colspan=5 class='dim'>no tool calls yet</td></tr>"}</table></div>
<h2>Models (from traces)</h2><div class="wrap"><table><tr><th>model</th><th>calls</th><th>tok/s (median)</th>
<th>context</th><th>context used median / max</th></tr>{m_rows or "<tr><td colspan=5 class='dim'>no traces yet</td></tr>"}
</table></div>
<h2>Is Mitra improving? (real sessions, per harness version)</h2><div class="wrap"><table><tr><th>version</th>
<th>turns</th><th>finished</th><th>tool failures / turn</th><th>retries / turn</th><th>steps / turn</th><th></th></tr>
{''.join(v_rows) or "<tr><td colspan=7 class='dim'>no turns yet</td></tr>"}</table></div>{trend}
<div class="note">Playground pass rates (hidden tests) are in "Playground results" above; lower failures and retries
and a higher finished share mean better. A version needs {I.MIN_TURNS_TO_JUDGE}+ turns to judge.</div>
<h2>Training data (D-022)</h2><div class="tiles"><div class="tile"><b>{tr.usable}</b><span class="dim">usable turns
(tests passed, all Mitra, traced)</span></div><div class="tile"><b>{tr.turns}</b><span class="dim">turns recorded</span></div>
<div class="tile"><b>{tr.target_pct}%</b><span class="dim">of the {I.TRAINING_TARGET} needed before a fine-tune</span>
<div class="bar"><i style="width:{tr.target_pct}%"></i></div></div></div>
<div class="wrap"><table><tr><th>turns</th><th>why not usable</th></tr>{r_rows or "<tr><td colspan=2 class='dim'>none</td></tr>"}
</table></div><div class="note">Export: <code>mitra report --export-training out.jsonl</code> (local file, nothing sent).
Store: {e(store_text())}</div>"""


def store_text() -> str:
    from app.core import store
    return store.size_text()


def build(roots: list[Path] | None = None, out: Path | None = None) -> tuple[Path, A.Report]:
    from app.core import insights as I
    from app.core import store

    roots = roots or default_roots()
    files = run_files(roots)
    rep = A.analyze(files)
    out = out or (H.home() / "dashboard.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    from app.core.improve import attempts

    sess = I.sessions(files)
    tools = I.tool_stats(sess)
    I.tool_errors(files, tools)
    page = render(load_results(roots), rep, harness_history(), H.load(), attempts())
    extra = render_more(sess, tools, I.model_stats(store.stored_files("traces")), I.improvement(sess), I.training(files))
    out.write_text(page.replace("</main></body></html>", extra + "</main></body></html>"), encoding="utf-8")
    return out, rep
