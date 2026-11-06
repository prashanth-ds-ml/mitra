"""`mitra solve`: run the core loop on one task or a whole plan, headless (M1).

    mitra solve "add a score counter" --test "python -m pytest -q"
    mitra solve --plan plan.md --test "python -m pytest -q tests"      # one plan task at a time
    add --json for a machine-readable result; exit code 0 = tests pass, 1 = not
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from app import config, ui
from app.core.loop import Event, run_plan, solve
from app.core.tools import Workspace
from app.llm import get_local_llm


class EventPrinter:
    """Shows the loop in the Mitra style: one line per tool, results under it."""

    def __init__(self, console: Console):
        self.c = console

    def __call__(self, e: Event) -> None:
        d = e.data
        if e.kind == "task":
            self.c.print()
            self.c.print(Text(f"━━ {d['id']}: {d['title']}", style="m.accent.b"))
        elif e.kind == "think":
            self.c.print(Text(f"✻ thought · {d['tokens']} tokens", style="m.faint"))
        elif e.kind == "say":
            self.c.print(Markdown(d["text"][:1500]))
        elif e.kind == "result":
            if d["name"] != "run_tests":  # test runs are shown by the "tests" event
                self.c.print(ui.step_line(_tool_name(d["name"]), d["args"], d["output"], d["ok"]))
        elif e.kind == "tests":
            label = "Tests" + (" (all)" if d.get("final") else "")
            self.c.print(ui.tool_line(label, ok=d["passed"], detail=("passed · " if d["passed"] else "failed · ")
                                      + d["summary"]))
        elif e.kind == "note":
            self.c.print(Text("  · " + d["text"], style="m.dim" if d.get("ok", True) else "m.err"))
        elif e.kind == "done":
            ok = d["status"] == "passed"
            self.c.print(ui.tool_line("Done" if ok else d["status"].capitalize(), ok=ok,
                                      detail=f"{d['summary'][:160]} · {d['steps']} steps · {d['seconds']}s"))


_NAMES = {"list_files": "list_directory", "write_file": "create_file", "search": "search_text"}


def _tool_name(name: str) -> str:
    return _NAMES.get(name, name)


def cmd_solve(task: str = "", *, test: str = "python -m pytest -q", plan: str = "", workspace: str = ".",
              model: str = "", max_steps: int = 40, as_json: bool = False) -> int:
    console = ui.apply(Console())
    cfg = config.load()
    model = model or cfg.get("local_model") or config.load_last_model() or "qwen3.5:4b"
    num_ctx = int(cfg.get("num_ctx") or 0) or config.context_for_model(model)
    ws = Workspace(Path(workspace), test_command=test)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    runs = ws.root / ".mitra" / "runs" / stamp
    ws.spill_dir = runs / "output"
    llm = get_local_llm(model, num_ctx=num_ctx)
    printer = None if as_json else EventPrinter(console)
    if not as_json:
        console.print(Text(f"✻ Mitra solve · {model} · {num_ctx // 1024}K context · {ws.root}", style="m.dim"))

    if plan:
        plan_text = Path(plan).read_text(encoding="utf-8")
        out = run_plan(plan_text, ws, llm, full_test_command=test, max_steps=max_steps, on_event=printer,
                       record_dir=runs, num_ctx=num_ctx)
        ok = out["final_tests_passed"]
        if as_json:
            print(json.dumps(out, indent=2))
        else:
            console.print()
            console.print(ui.tool_line("Plan", ok=ok, detail=f"{out['passed_tasks']}/{out['total_tasks']} tasks · "
                                                               f"all tests: {out['final_tests']}"))
            console.print(Text(f"  record: {runs}", style="m.faint"))
        return 0 if ok else 1

    if not task:
        console.print("[m.err]Give a task, or --plan <file>.[/m.err]")
        return 2
    res = solve(task, ws, llm, max_steps=max_steps, on_event=printer, record_path=runs / "run.jsonl",
                num_ctx=num_ctx)
    if as_json:
        print(json.dumps(res.to_json(), indent=2))
    else:
        console.print(Text(f"  record: {res.record_path}", style="m.faint"))
    return 0 if res.status == "passed" else 1
