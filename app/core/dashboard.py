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


def render(results: list[dict], rep: A.Report, history: list[tuple[str, str]], current: H.Harness) -> str:
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
`mitra report --html` to refresh</div><div class="tiles">{tile_html}</div>
<h2>Playground results</h2><div class="wrap"><table><tr><th>date</th><th>level</th><th>model</th><th>visible</th>
<th>visible + hidden</th><th>build</th><th>result</th></tr>{''.join(rows) or "<tr><td colspan=7 class='dim'>no results yet</td></tr>"}
</table></div>
<h2>Problems in run records ({rep.files} files)</h2><div class="wrap"><table><tr><th>count</th><th>pattern</th></tr>
{''.join(pats) or "<tr><td colspan=2 class='dim'>none found</td></tr>"}</table></div>
<h2>What Mitra has learned (harness v{current.version})</h2><ul>{rules}</ul>
<h2>Harness history</h2><div class="wrap"><table><tr><th>version</th><th>why</th></tr>
{hist or "<tr><td colspan=2 class='dim'>no changes yet</td></tr>"}</table></div></main></body></html>"""


def build(roots: list[Path] | None = None, out: Path | None = None) -> tuple[Path, A.Report]:
    roots = roots or default_roots()
    rep = A.analyze(A.find_run_files(roots))
    out = out or (H.home() / "dashboard.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(load_results(roots), rep, harness_history(), H.load()), encoding="utf-8")
    return out, rep
