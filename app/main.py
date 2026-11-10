import difflib
import os
import json
import pathlib
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime

import typer
from langchain_core.messages import HumanMessage, SystemMessage

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from app.llm import get_local_llm, probe_ollama, thinking_setting
from app.agents import filesystem
from app.agents import reviewer as reviewer_agent
from app.agents import session as session_agent
from app.agents import shell as shell_agent
from app.agents import web as web_agent
from app import ui
from app import config, logs as app_logs, memory, skills as skills_registry, mcp as mcp_registry, policy as policy_module, events as event_bus, workflows

cli = typer.Typer(invoke_without_command=True, add_completion=False)


def _utf8_streams(streams=None) -> None:
    """E-062: output redirected to a file or pipe on Windows is cp1252, so `mitra night ... > night.log` crashed on
    the first ✗ / ✓ before anything ran. Such streams are switched to UTF-8 (unknown characters replaced)."""
    for stream in streams if streams is not None else (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "").replace("_", "")
        if enc != "utf8" and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


_utf8_streams()
console = ui.apply(Console())




def _say(markdown_text: str) -> None:
    """Mitra's reply to a command: plain markdown in the Phosphor theme, no box (D-031)."""
    console.print()
    console.print(Markdown(markdown_text or ""))


def show_banner():
    """Nothing up front: the header box after startup is the welcome screen (D-031 mock).
    The title line is shown only when the model picker has to ask."""
    return None


_MITRA_MD_TEMPLATE = """\
# Project Rules

<!-- Mitra will follow these rules in every response. -->

## General
- Always write clean, readable, well-structured code
- Use meaningful names for variables, functions, and files
- Keep functions small and focused on a single responsibility
- Add comments only where the intent is not obvious from the code
- Do not delete files without explicit permission

## Project Management
- Always check if a file or folder exists before creating it
- Ask for the project path if not provided
- Create a virtual environment before installing any packages
- Update requirements.txt / package.json when adding dependencies

## AI / ML Projects
- Use clear, modular pipeline design (data → model → eval → serve)
- Log experiments with enough detail to reproduce results
- Keep model configs separate from code (use config files or env vars)
- Document dataset sources and any preprocessing steps

## Web / API Projects
- Separate concerns: routes → services → data layer
- Validate all inputs at the boundary
- Never hardcode secrets — use .env files
- Write at least one test per endpoint

## Safety
- Show a diff or summary before applying bulk changes
- Run tests before marking any task as complete
- Confirm before running destructive commands
"""

_MITRA_TOML_TEMPLATE = """\
model = ""                   # legacy fallback; prefer local_model
local_model = ""             # leave empty to pick at startup
codegen_model = "kimi-k2.5:cloud"  # used only when cloud codegen is enabled
temperature = 0.2
session_mode = "approve"     # read-only | plan | approve | auto
show_reasoning = false       # show the model's thinking text (ctrl+o shows it anyway)
thinking = "auto"            # auto | on | off: off answers faster but plans less (D-020)
memory_enabled = false
require_diff_approval = true
auto_compact_threshold = 0       # 0 = compact at 80% of num_ctx (E-046); a number caps it lower
num_ctx = 0                      # 0 = per model: 4B 128K, 9B 256K (measured, D-036, D-039); /context changes it
ollama_local_base_url = "http://localhost:11434"
ollama_cloud_base_url = "https://ollama.com"
allowed_roots = []           # extra folders Mitra may inspect/edit beyond the workspace
disabled_tools = []          # tool names Mitra may not use
disabled_commands = []       # shell executables to block (e.g. ["python", "git"])
instruction_files = ["AGENTS.md", "CLAUDE.md", ".mitra/instructions.md", ".github/copilot-instructions.md"]
skill_dirs = ["skills", ".mitra/skills"]
# MCP servers live in .mitra/mcp.json (project) and ~/.mitra/mcp.json (you); see /mcp
"""

_DEFAULT_CLOUD_CODEGEN_MODEL = "kimi-k2.5:cloud"


def _run_init() -> None:
    """Shared init logic — works from CLI and from inside the chat REPL."""
    cwd = pathlib.Path.cwd()
    created = []

    rules_path = cwd / "MITRA.md"
    if rules_path.exists():
        console.print("[m.dim]MITRA.md already exists — skipped.[/m.dim]")
    else:
        rules_path.write_text(_MITRA_MD_TEMPLATE, encoding="utf-8")
        created.append("MITRA.md")

    toml_path = cwd / "mitra.toml"
    if toml_path.exists():
        console.print("[m.dim]mitra.toml already exists — skipped.[/m.dim]")
    else:
        toml_path.write_text(_MITRA_TOML_TEMPLATE, encoding="utf-8")
        created.append("mitra.toml")

    if created:
        console.print(f"[m.ok]✓ Created:[/m.ok] {', '.join(created)}")
        console.print("[dim]Edit MITRA.md to add your project rules.[/dim]")
    else:
        console.print("[dim]Nothing to create — already initialised.[/dim]")

    # Always scaffold the Obsidian memory vault (skips existing files)
    vault_files = memory.init_memory(str(cwd))
    if vault_files:
        console.print(f"\n[m.ok]✓ Memory vault:[/m.ok] .mitra/")
        for f in vault_files:
            console.print(f"  [dim cyan]  {f}[/dim cyan]")
        console.print(
            "\n[dim]Tip: Open [bold].mitra/[/bold] as an Obsidian vault for "
            "graph view, search, and history.[/dim]"
        )
    else:
        console.print("[dim]Memory vault already exists — skipped.[/dim]")


@cli.command("init")
@cli.command("/init", hidden=True)
def cmd_init():
    """Initialise Mitra in the current project directory."""
    _run_init()


def _resolve_phase0_workspace(cwd: str | None = None) -> pathlib.Path:
    return config.detect_project_root(cwd)


def _print_phase0_status(cwd: str | None = None) -> None:
    workspace = _resolve_phase0_workspace(cwd)
    cfg = config.load(cwd=str(workspace))
    logger = app_logs.setup_logging(str(workspace))
    ollama_ok, ollama_message = probe_ollama(cfg.get("ollama_local_base_url"))
    active_model = cfg.get("local_model") or cfg.get("model") or "(not set)"
    paths = config.get_config_paths(str(workspace))

    logger.info("status command workspace=%s ollama_ok=%s", workspace, ollama_ok)

    table = Table(title="Mitra Status")
    table.add_column("Item", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Workspace", str(workspace))
    table.add_row("Project root", workspace.name)
    table.add_row("Config file", "present" if paths["project"].exists() else "missing")
    table.add_row("Rules file", "present" if paths["rules"].exists() else "missing")
    table.add_row("Active model", active_model)
    table.add_row("Ollama", ollama_message if ollama_ok else f"[m.err]{ollama_message}[/m.err]")
    table.add_row("Local endpoint", cfg.get("ollama_local_base_url", "http://localhost:11434"))
    console.print(table)


def _print_phase0_config(cwd: str | None = None) -> None:
    workspace = _resolve_phase0_workspace(cwd)
    cfg = config.load(cwd=str(workspace))
    logger = app_logs.setup_logging(str(workspace))
    paths = config.get_config_paths(str(workspace))

    logger.info("config command workspace=%s", workspace)

    path_table = Table(title="Config Layers")
    path_table.add_column("Layer", style="cyan", no_wrap=True)
    path_table.add_column("Path", style="white")
    path_table.add_column("State", style="white")
    for layer in ("user", "project", "local", "rules"):
        path = paths[layer]
        path_table.add_row(layer, str(path), "present" if path.exists() else "missing")

    value_table = Table(title="Resolved Settings")
    value_table.add_column("Key", style="cyan", no_wrap=True)
    value_table.add_column("Value", style="white")
    for key in (
        "local_model",
        "codegen_model",
        "temperature",
        "session_mode",
        "work_mode",
        "num_ctx",
        "ollama_local_base_url",
    ):
        value = cfg.get(key, "")
        if value in ("", None):
            value = "(empty)"
        value_table.add_row(key, str(value))

    console.print(path_table)
    console.print(value_table)


def _print_phase0_models(cwd: str | None = None, show_all: bool = False) -> None:
    workspace = _resolve_phase0_workspace(cwd)
    cfg = config.load(cwd=str(workspace))
    logger = app_logs.setup_logging(str(workspace))
    ollama_ok, ollama_message = probe_ollama(cfg.get("ollama_local_base_url"))
    inventory = config.get_local_model_inventory(include_incompatible=show_all)

    logger.info("models command workspace=%s model_count=%s", workspace, len(inventory))

    if not inventory:
        console.print(ui.tool_line("Local models", ok=False, detail=ollama_message if not ollama_ok else "none installed (ollama pull qwen3.5:4b)"))
        return

    table = Table(title="Local Models" + ("" if show_all else " (compatible with Mitra)"))
    table.add_column("Model", style="cyan")
    table.add_column("Size", style="white")
    table.add_column("Placement", style="white")
    table.add_column("Recommended", style="white")
    if show_all:
        table.add_column("Mitra", style="white")
    for item in inventory:
        row = [item.name, item.size_text or "-", item.placement, "yes" if item.recommended else "no"]
        if show_all:
            problem = config.compatibility_problem(config.get_model_facts(item.name), item.name)
            row.append("ok" if problem is None else f"hidden: {problem}")
        table.add_row(*row)
    console.print(table)
    if not show_all:
        hidden = len(config.get_local_model_inventory(include_incompatible=True)) - len(inventory)
        if hidden:
            console.print(f"[dim]{hidden} more installed model(s) cannot run Mitra; `mitra models --all` shows why.[/dim]")


def cmd_status(cwd: str | None = typer.Option(None, "--cwd", help="Start path for project root detection.")) -> None:
    """Show the current workspace and Ollama status."""
    _print_phase0_status(cwd)


def cmd_config(cwd: str | None = typer.Option(None, "--cwd", help="Start path for project root detection.")) -> None:
    """Show resolved configuration layers."""
    _print_phase0_config(cwd)


def cmd_models(
    cwd: str | None = typer.Option(None, "--cwd", help="Start path for project root detection."),
    show_all: bool = typer.Option(False, "--all", help="Also list models Mitra cannot use, and why."),
) -> None:
    """List the local models Mitra can use (qwen3.5, 4B or larger; --all shows the others and why)."""
    _print_phase0_models(cwd, show_all=show_all)


def cmd_test(command: str = typer.Argument("pytest"), cwd: str | None = typer.Option(None, "--cwd", help="Start path for project root detection.")) -> None:
    """Run a test command in the workspace."""
    _cfg, workspace = _phase5_workspace(cwd)
    output = _cmd_test(command, workspace)
    if output:
        _say(output)


def cmd_mcp(
    args: list[str] | None = typer.Argument(None, help="list | test <name> | tools <name> | on|off <name> | trust | import | call <server> <tool> {json}"),
    cwd: str | None = typer.Option(None, "--cwd", help="Start path for project root detection."),
) -> None:
    """List, test and manage MCP servers."""
    cfg, workspace = _phase5_workspace(cwd)
    reply = _build_mcp_reply(workspace, cfg, " ".join(args or []))
    _say(reply)


def cmd_logs(target: str = typer.Argument("summary"), cwd: str | None = typer.Option(None, "--cwd", help="Start path for project root detection.")) -> None:
    """Inspect saved `.mitra` logs and traces."""
    _cfg, workspace = _phase5_workspace(cwd)
    reply = _build_logs_reply(workspace, target)
    _say(reply)


cli.command("status")(cmd_status)
cli.command("/status", hidden=True)(cmd_status)
cli.command("config")(cmd_config)
cli.command("/config", hidden=True)(cmd_config)
cli.command("models")(cmd_models)


def cmd_solve(
    task: str = typer.Argument("", help="What to do. Leave empty with --plan."),
    test: str = typer.Option("python -m pytest -q", "--test", help="Command that decides when the task is done."),
    plan: str = typer.Option("", "--plan", help="A plan file: do its tasks one at a time (plan, implement, test, fix)."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Project folder."),
    model: str = typer.Option("", "--model", help="Local model (default: the last one used, else qwen3.5:4b)."),
    max_steps: int = typer.Option(0, "--max-steps", help="Model calls per task before stopping (0 = the harness "
                                  "setting, 40 by default)."),
    as_json: bool = typer.Option(False, "--json", help="Print a JSON result instead of progress."),
    write_tests: bool = typer.Option(False, "--write-tests", help="Let Mitra write tests/ (tests-first plans)."),
) -> None:
    """Work on a task until its tests pass (the core loop, M1). Exit 0 = tests pass."""
    from app.core.cli import cmd_solve as _solve

    raise typer.Exit(_solve(task, test=test, plan=plan, workspace=workspace, model=model,
                            max_steps=max_steps or None, as_json=as_json, write_tests=write_tests))


def cmd_night(
    plan: str = typer.Argument("plan.md", help="The plan file (tasks with 'Done when' tests)."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Project folder."),
    hours: float = typer.Option(4.0, "--hours", help="Stop after this many hours."),
    model: str = typer.Option("", "--model", help="Model (default: the builder role)."),
    read_only_tests: bool = typer.Option(False, "--read-only-tests", help="Mitra may not write tests/."),
) -> None:
    """Build a plan unattended (overnight): keeps Windows awake, stops at the time limit, writes NIGHT_REPORT.md."""
    from app.core import night

    raise typer.Exit(night.run(plan, workspace=workspace, hours=hours, model=model,
                               write_tests=not read_only_tests, echo=lambda s: console.print(s)))


cli.command("night")(cmd_night)


def cmd_remote(
    action: str = typer.Argument("status", help="status | set <url> | off"),
    url: str = typer.Argument("", help="For set: the URL the Kaggle notebook printed (it holds the token)."),
    ctx: int = typer.Option(262_144, "--ctx", help="Context to run at on the remote (default 256K)."),
    name: str = typer.Option("kaggle", "--name", help="A short name for records and the header."),
) -> None:
    """Run the model on a remote Ollama (a Kaggle GPU, see remote/kaggle/README.md) instead of this machine (D-060)."""
    from app import remote

    if action == "set":
        if not url:
            console.print("Usage: mitra remote set <url from the notebook> [--ctx 262144]")
            raise typer.Exit(2)
        target = remote.clean_url(url)
        models, err = remote.probe(target)
        if err:
            console.print(f"✗ cannot reach {remote.shown(target)}: {err}\n  Is the notebook still running? Copy the "
                          "whole line it printed (the token is part of the URL).")
            raise typer.Exit(1)
        data = remote.set_remote(target, ctx, name)
        names = ", ".join(str(m.get("name")) for m in models) or "none yet"
        console.print(f"☁ remote set: {name} · {remote.shown(data['url'])} · {ctx // 1024}K context · models: {names}\n"
                      "  Start (or restart) Mitra: every model call now goes there. `mitra remote off` to go back.")
        return
    if action == "off":
        console.print("✓ back to this machine's Ollama" if remote.clear() else "No remote was set.")
        return
    r = remote.active()
    if not r:
        console.print("No remote: Mitra uses this machine's Ollama. `mitra remote set <url>` uses a Kaggle GPU.")
        return
    models, err = remote.probe(r["url"], timeout=10)
    state = f"✗ not reachable ({err})" if err else "✓ reachable · models: " + (
        ", ".join(str(m.get("name")) for m in models) or "none")
    console.print(f"☁ {r.get('name')} · {remote.shown(r['url'])} · {int(r.get('num_ctx') or 0) // 1024}K · {state}")


cli.command("remote")(cmd_remote)


def _kaggle_model() -> str:
    from app.core import roles
    return roles.resolve("chat", config.load())[0]


def cmd_kaggle(
    action: str = typer.Argument("status", help="setup [token|path] | start | stop | status | use <now|when-needed|never>"),
    path: str = typer.Argument("", help="For setup: the downloaded kaggle.json (default: look in Downloads)."),
    model: str = typer.Option("", "--model", help="Model to run there (default: your chat model)."),
    ctx: int = typer.Option(262_144, "--ctx", help="Context (default 256K, mimo's maximum)."),
    idle: int = typer.Option(30, "--idle", help="Stop by itself after this many minutes unused."),
    hours: float = typer.Option(11.5, "--hours", help="Hard time limit for the run."),
) -> None:
    """Use your Kaggle GPU hours from Mitra: start a private GPU notebook, stop it, see hours left (D-061)."""
    from app import kaggle

    try:
        if action == "setup":
            if not kaggle.setup(path, echo=console.print):
                raise typer.Exit(1)
        elif action == "use":  # D-064: when Mitra uses Kaggle
            from app import backend
            if path not in backend.USE_VALUES:
                console.print("Usage: mitra kaggle use now|when-needed|never")
                raise typer.Exit(2)
            backend.save_prefs(kaggle_use=path, onboarded=True)
            console.print(f"☁ Kaggle {backend.USE_TEXT[path]}")
        elif action == "start":
            kaggle.start(model or _kaggle_model(), ctx, idle_min=idle, max_hours=hours, echo=console.print)
            console.print("  Start Mitra (or restart it): it now runs on Kaggle. `mitra kaggle stop` when done.")
        elif action == "stop":
            kaggle.stop(echo=console.print)
        else:
            from app import backend
            use = backend.kaggle_use()
            console.print(f"Setting: {use or 'not decided yet'} ({backend.USE_TEXT.get(use, 'asked at the next start')})")
            kaggle.status(echo=console.print)
    except kaggle.KaggleError as exc:
        console.print(f"✗ {exc}")
        raise typer.Exit(1)


cli.command("kaggle")(cmd_kaggle)


cli.command("solve")(cmd_solve)


def cmd_harness(
    action: str = typer.Argument("show", help="show | revert"),
    version: int = typer.Argument(0, help="With revert: the version to go back to."),
) -> None:
    """Show what Mitra has learned (rules, tool texts, limits) and its history; revert to an earlier version."""
    from app.core import harness as H

    active = H.active_path()
    history = sorted((active.parent / "harness" / "history").glob("*-v*.toml"))
    if action == "revert":
        match = [p for p in history if p.stem.endswith(f"-v{version}")]
        if not match:
            console.print(f"[m.err]No saved version {version}. `mitra harness` lists them.[/m.err]")
            raise typer.Exit(1)
        old = H.load(match[-1])
        current = H.load()
        old.version = current.version  # save() makes it the next version number
        H.save(old, f"revert to v{version}")
        console.print(f"Reverted to the rules of v{version} (saved as v{current.version + 1}).")
        return
    h = H.load()
    console.print(Text(f"Harness v{h.version} · {h.source}", style="m.tool"))
    if h.note:
        console.print(Text(f"  why: {h.note}", style="m.dim"))
    console.print(Text("  rules:" + ("" if h.rules else " none yet"), style="m.dim"))
    for r in h.rules:
        console.print(Text(f"    - {r}", style="m.text"))
    for name, desc in h.tools.items():
        console.print(Text(f"  tool {name}: {desc}", style="m.text"))
    console.print(Text("  limits: " + ", ".join(f"{k}={v}" for k, v in h.limits.items()), style="m.dim"))
    if history:
        console.print(Text("  history:", style="m.dim"))
        for p in history[-10:]:
            note = H.load(p).note
            console.print(Text(f"    {p.stem}  {note}", style="m.faint"))


cli.command("harness")(cmd_harness)


def cmd_report(
    html_page: bool = typer.Option(False, "--html", help="Also write the dashboard page and print its path."),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
    export_training: str = typer.Option("", "--export-training",
                                        help="Write the usable turns (tests passed, all Mitra) to this JSONL file."),
) -> None:
    """What goes wrong in recorded runs (patterns with counts), and a local dashboard page with --html."""
    from app.core import analyze as A
    from app.core import dashboard as D

    if export_training:
        from app.core import insights as I
        n = I.export_training(D.run_files(), pathlib.Path(export_training))
        console.print(Text(f"{n} usable turns written to {export_training} (local file, nothing sent)", style="m.tool"))
        return
    if html_page:
        out, rep = D.build()
    else:
        rep = A.analyze(D.run_files())
    if as_json:
        print(json.dumps(rep.to_json(), indent=2))
    else:
        console.print(Text(A.format_report(rep), style="m.text"))
    if html_page:
        console.print(Text(f"dashboard: {out}", style="m.tool"))


cli.command("report")(cmd_report)


def cmd_dashboard(
    port: int = typer.Option(8765, "--port", help="Port on 127.0.0.1."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open the browser."),
) -> None:
    """The dashboard on localhost (127.0.0.1 only, read-only): sessions, tools, improvement, training data."""
    from app.core import server as S

    if S.running(port):
        console.print(Text(f"Already running: http://127.0.0.1:{port}/", style="m.tool"))
        if not no_open:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{port}/")
        return
    try:
        srv = S.make_server(port)
    except OSError as exc:
        console.print(f"[m.err]Port {port} is in use ({exc}). Try --port 8766.[/m.err]")
        raise typer.Exit(1)
    console.print(Text("Building the page from the store ...", style="m.dim"))
    srv.pages.get()
    url = f"http://127.0.0.1:{port}/"
    console.print(Text(f"✻ Mitra dashboard: {url}  (Refresh button on the page · ctrl+c stops)", style="m.tool"))
    if not no_open:
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        console.print(Text("dashboard stopped", style="m.dim"))


cli.command("dashboard")(cmd_dashboard)


def cmd_improve(
    model: str = typer.Option("", "--model", help="Builder model for the benchmark (default: the last one used)."),
    proposer: str = typer.Option("", "--proposer", help="Model that proposes the change (default: the 9B if installed)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Only show the proposal; no benchmark, nothing saved."),
    tasks: str = typer.Option("", "--tasks", help="Comma-separated tune task ids (default: the whole tune half)."),
    max_steps: int = typer.Option(30, "--max-steps", help="Model calls per benchmark task."),
    force: bool = typer.Option(False, "--force", help="Run even if the free-RAM check fails."),
) -> None:
    """Self-improve: a local model proposes one settings change for the top problem; the benchmark decides."""
    import json as _json
    import urllib.request

    import psutil

    from app import config as cfg_mod
    from app.core import analyze as A
    from app.core import dashboard as D
    from app.core import harness as H
    from app.core import improve as I
    from app.llm import get_local_llm, thinking_setting

    cfg = cfg_mod.load()
    builder_name = model or cfg.get("local_model") or cfg_mod.load_last_model() or "qwen3.5:4b"
    inventory = {m.name: (m.size_gib or 0.0) for m in cfg_mod.get_local_model_inventory()}
    proposer_name = proposer or next((m for m in ("qwen3.5:9b", "qwen3.5:latest") if m in inventory), builder_name)
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=10) as r:
            loaded = [m.get("name", "") for m in _json.loads(r.read()).get("models", [])]
    except (OSError, ValueError):
        loaded = []
    problems = I.machine_problems([proposer_name] if dry_run else [proposer_name, builder_name], sizes=inventory,
                                  loaded=loaded, free_gb=psutil.virtual_memory().available / 2**30)
    if problems and not force:
        for p in problems:
            console.print(f"[m.err]✗ {p}[/m.err]")
        console.print(Text("Nothing was run. --force runs anyway.", style="m.dim"))
        raise typer.Exit(1)
    files = D.run_files()
    version = H.load().version
    rep = A.analyze(files, harness_version=version)  # problems left with the current settings
    if not rep.files:
        console.print(Text(f"No records made with harness v{version} yet: using all {len(files)} record files.",
                           style="m.dim"))
        rep = A.analyze(files)
    num_ctx = int(cfg.get("num_ctx") or 0) or cfg_mod.context_for_model(builder_name)
    proposer_llm = get_local_llm(proposer_name, num_ctx=32768, reasoning=False)
    builder_llm = get_local_llm(builder_name, num_ctx=num_ctx, reasoning=thinking_setting(cfg.get("thinking")))
    bench = I.load_bench()
    chosen = None
    if tasks:
        wanted = {t.strip().upper() for t in tasks.split(",") if t.strip()}
        chosen = [t for t in bench.load_tasks() if t.split == "tune" and t.id.upper() in wanted]
        if not chosen:
            console.print("[m.err]None of those are tune tasks (`python bench/bench.py list`).[/m.err]")
            raise typer.Exit(1)
    entry = I.improve(rep, proposer=proposer_llm, builder=builder_llm, builder_name=builder_name,
                      proposer_name=proposer_name, dry_run=dry_run, tasks=chosen, bench=bench, num_ctx=num_ctx,
                      max_steps=max_steps, say=lambda t: console.print(Text(t, style="m.text")))
    raise typer.Exit(0 if entry.get("result") in ("kept", "dropped", "dry_run", "skipped") else 1)


cli.command("improve")(cmd_improve)
cli.command("/models", hidden=True)(cmd_models)
cli.command("test")(cmd_test)
cli.command("/test", hidden=True)(cmd_test)
cli.command("mcp")(cmd_mcp)
cli.command("/mcp", hidden=True)(cmd_mcp)
cli.command("logs")(cmd_logs)
cli.command("/logs", hidden=True)(cmd_logs)


def _phase5_workspace(cwd: str | None = None) -> tuple[dict, str]:
    cfg = config.load(cwd=cwd)
    workspace = cfg["workspace"]
    _apply_session_mode(cfg, _normalize_session_mode(cfg.get("session_mode")))
    return cfg, workspace














def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("mitra")
    except PackageNotFoundError:
        return "dev"


@cli.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    show_version: bool = typer.Option(False, "--version", "-V", help="Show the version and exit."),
):
    """Mitra: a local coding assistant on Ollama. Run `mitra` in a project folder to start the chat."""
    if show_version:
        console.print(f"mitra {_version()}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is not None:
        return
    try:
        _chat()
    except Exception as exc:  # E-066: no real terminal (piped input, an IDE output pane): one line, not a traceback
        if type(exc).__name__ != "NoConsoleScreenBufferError":
            raise
        console.print("✗ Mitra's chat needs a terminal window: Windows Terminal, PowerShell, cmd or Git Bash. "
                      "It cannot draw its input box when input is piped or in an output pane. "
                      "Commands like `mitra kaggle status` work anywhere.")
        raise typer.Exit(1)






# ── Known friendly error patterns ────────────────────────────────────────────
_ERROR_HINTS: list[tuple[str, str]] = [
    ("connection refused",        "Ollama is not running. Start it with: ollama serve"),
    ("10054",                     "Lost the connection to Ollama (it restarted or stopped). Make sure it runs, then send your message again."),
    ("10061",                     "Ollama is not running. Start it, then send your message again."),
    ("forcibly closed",           "Lost the connection to Ollama (it restarted or stopped). Make sure it runs, then send your message again."),
    ("connection reset",          "Lost the connection to Ollama (it restarted or stopped). Make sure it runs, then send your message again."),
    ("ollama",                    "Cannot reach Ollama. Is it running? Try: ollama serve"),
    ("validation error",          "The model returned malformed tool arguments. Try rephrasing your request."),
    ("list_type",                 "Package list was not recognised. Try: install pygame numpy"),
    ("context length",            "The conversation is too long. Use /reset to start a fresh session."),
    ("requires more system memory", "The selected model is too large for the free RAM. Close other programs, or switch now with `/model use qwen3.5:4b` or `/context 128k`."),
    ("rate_limit",                "Request rate-limited. Wait a moment and try again."),
]


def _friendly_error(exc: Exception) -> str:
    """Return a human-readable error message for known exception patterns."""
    msg = str(exc).lower()
    for pattern, hint in _ERROR_HINTS:
        if pattern in msg:
            return hint
    return f"Unexpected error: {exc}"


def _log_error(workspace: str, exc: Exception) -> None:
    """Append full traceback to .mitra/errors.log."""
    try:
        log_dir = pathlib.Path(workspace) / ".mitra"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "errors.log"
        from datetime import datetime
        trace = traceback.format_exc()
        entry = f"\n{'='*60}\n{datetime.now().isoformat()}\n{trace}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        memory.append_error(workspace, str(exc), trace)
    except Exception:
        pass  # never crash the crash handler


# ── Slash command completer ───────────────────────────────────────────────────
_SESSION_MODES = ("read-only", "plan", "approve", "auto")
_KEY_HELP = [
    ("shift+enter",  "New line (also alt+enter, ctrl+j)"),
    ("↑ ↓",          "Move between lines; earlier prompts at the first/last line"),
    ("ctrl+r",       "Search earlier prompts"),
    ("ctrl+← →",     "Jump a word (ctrl+backspace deletes one)"),
    ("/  @",         "Command menu · file search"),
    ("esc",          "Stop the model while it writes; esc esc clears the input"),
    ("shift+tab",    "Next mode: ask → auto-edit → plan"),
    ("ctrl+o",       "Show the last folded output or thinking"),
    ("ctrl+l",       "Clear the screen (the conversation is kept)"),
    ("ctrl+c",       "Clear the input; twice on an empty line to quit"),
]
# Shown by /help and in the `/` menu as you type (D-035).
_COMMAND_HELP = [
        ("/help",          "Show this help"),
        ("/init",          "Create MITRA.md + mitra.toml in this folder"),
        ("/status",        "Workspace, model, mode and session status"),
        ("/doctor",        "Machine and setup check: RAM, GPU, Ollama, permissions, MCP"),
        ("/free",          "Make RAM room for the model: tick programs, Mitra closes them"),
        ("/kaggle [start|stop|use|setup]", "Kaggle GPU: status and hours · start/stop · use now|when-needed|never"),
        ("/report",        "Rebuild the dashboard (sessions, tools, improvement, training data) and open it"),
        ("/role [name]",   "Show roles, or switch role: model, tools and MCP servers at once"),
        ("/model use <m>", "Switch the chat model now (no restart)"),
        ("/run [plan] [h]", "Build a plan unattended in the background (overnight), up to h hours (default 4)"),
        ("/night",         "The latest night run: running?, progress, report"),
        ("/plan template", "Write a runnable plan template here · /plan check [file] checks a plan"),
        ("/good [note]",   "Mark the last turn good (your verdict teaches Mitra)"),
        ("/bad [why]",     "Mark the last turn bad, ideally with why"),
        ("/model",         "Show the active models (/model list: installed Ollama models)"),
        ("/context",       "Context use and when it compacts · /context 128k|256k|auto changes the size"),
        ("/think on|off",  "Show or hide the model's reasoning"),
        ("/mode [name]",   "Show or change the session mode"),
        ("! <command>",    "Run a shell command in the workspace (e.g. ! pytest -q)"),
        ("/test [cmd]",    "Run the tests (default: pytest)"),
        ("/fix <cmd>",     "Run a command, and edit + retry until it passes (bounded)"),
        ("/diff",          "Show the git diff or Mitra's last change set"),
        ("/undo [all]",    "Undo Mitra's last change (all: every change this session)"),
        ("/commit [msg]",  "Commit staged changes (--generate drafts the message); never pushes"),
        ("/review [staged]", "Review the current or staged diff for real problems"),
        ("/mcp",           "MCP servers: list, test, tools, on/off, trust, import, call"),
        ("/skills",        "List skills (/skills show <name>)"),
        ("/logs [name]",   "Inspect .mitra logs"),
        ("/resume",        "Saved session summary and recent activity"),
        ("/compact",       "Compress the conversation to free context"),
        ("/clear",         "Clear the conversation (saved files are kept)"),
        ("exit / quit",    "Exit Mitra"),
]
_LAST_SHELL_COMMAND: str | None = None





def _shorten_display(text: str, max_len: int = 28) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


def _build_context_reply(total_tokens: int, auto_compact_threshold: int, num_ctx: int) -> str:
    pct = min(100, int(total_tokens / max(auto_compact_threshold, 1) * 100))
    bar_filled = pct // 5
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    state = "Healthy" if pct < 80 else ("Getting heavy" if pct < 100 else "Ready to compact")
    return (
        "## Context window\n\n"
        f"- **Requested max context:** `{num_ctx:,}`\n"
        f"- **Auto-compact threshold:** `{auto_compact_threshold:,}`\n"
        f"- **Current session usage:** `{total_tokens:,}` tokens\n"
        f"- **Load:** `{pct}%`\n"
        f"- **State:** {state}\n"
        f"- **Usage bar:** `{bar}`\n\n"
        "Use `/compact` to compress the conversation while keeping the active session alive."
    )


def _build_permissions_reply(cfg: dict, session_mode: str) -> str:
    allowed_roots = cfg.get("allowed_roots") or []
    disabled_tools = cfg.get("disabled_tools") or []
    disabled_commands = cfg.get("disabled_commands") or []
    roots_text = ", ".join(f"`{path}`" for path in allowed_roots) if allowed_roots else "None"
    tools_text = ", ".join(f"`{name}`" for name in disabled_tools) if disabled_tools else "None"
    commands_text = ", ".join(f"`{name}`" for name in disabled_commands) if disabled_commands else "None"
    return (
        "## Permissions\n\n"
        f"- **Mode:** `{session_mode}`\n"
        f"- **Behavior:** {_mode_summary(session_mode)}\n"
        f"- **Workspace:** `{cfg['workspace']}`\n"
        f"- **Current shell cwd:** `{shell_agent.get_cwd()}`\n"
        f"- **Additional allowed roots:** {roots_text}\n"
        f"- **Disabled file tools:** {tools_text}\n"
        f"- **Disabled shell commands:** {commands_text}\n"
        "- **Shell trust:** approved commands can be trusted per directory and then auto-approved on repeat.\n\n"
        "Use `/mode` to change the session behavior. Edit `mitra.toml` to change allowed roots or disabled tools and commands."
    )






def _build_project_instructions_prompt(instructions: list[dict[str, str]]) -> str:
    """Format loaded project instruction files for the system prompt."""
    sections: list[str] = []
    for item in instructions:
        path = item.get("path", "project instructions")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        sections.append(f"### {path}\n{content}")
    if not sections:
        return ""
    return "## Project Instructions\n" + "\n\n".join(sections)


def _build_skills_prompt(skills: list[skills_registry.Skill]) -> str:
    return skills_registry.format_prompt(skills)


def _build_skills_reply(
    skills: list[skills_registry.Skill],
    raw: str = "/skills",
    *,
    workspace: str | None = None,
) -> str:
    target = raw.strip()[7:].strip() if raw.strip().lower().startswith("/skills") else raw.strip()
    if target.startswith("show "):
        query = target[5:].strip()
        if not query:
            return "Usage: `/skills show <name>`"
        skill = skills_registry.find(skills, query)
        if skill is None:
            return f"No matching skill found for `{query}`. Use `/skills` to list available skills."
        if workspace is None:
            return f"## {skill.name}\n\n- **Path:** `{skill.path}`\n- **Description:** {skill.description}"
        body = skills_registry.read_body(workspace, skill)
        if body is None:
            return f"Could not read `{skill.path}`."
        return f"## {skill.name}\n\n- **Path:** `{skill.path}`\n- **Description:** {skill.description}\n\n```md\n{body}\n```"

    if target:
        return "Usage: `/skills` or `/skills show <name>`."

    if not skills:
        return (
            "No Mitra skills found yet.\n\n"
            "Add skills under `skills/<name>/SKILL.md` or `.mitra/skills/<name>/SKILL.md`."
        )
    lines = ["## Mitra skills", ""]
    for skill in skills:
        lines.append(f"- **{skill.name}** — `{skill.path}`")
        lines.append(f"  {skill.description}")
    lines.extend(["", "Use `/skills show <name>` to inspect a skill."])
    return "\n".join(lines)


def _clear_terminal() -> None:
    """Clear the terminal before rendering startup UI."""
    try:
        console.clear()
    except Exception:
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except Exception:
            pass


def _print_progress_message(message: str, detail: str | None = None, *, color: str = "cyan") -> None:

    console.print(ui.tool_line(message, detail=_shorten_display(detail, 110) if detail else ""))




_MODE_ALIASES = {"ask": "approve", "auto-edit": "auto", "autoedit": "auto", "auto_edit": "auto"}


def _normalize_session_mode(raw: str | None) -> str:
    mode = (raw or "approve").strip().lower()
    mode = _MODE_ALIASES.get(mode, mode)
    return mode if mode in _SESSION_MODES else "approve"


def _is_known_mode(raw: str) -> bool:
    mode = (raw or "").strip().lower()
    return mode in _SESSION_MODES or mode in _MODE_ALIASES








def _mode_summary(mode: str) -> str:
    summaries = {
        "read-only": "Read and inspect only. No shell execution except built-in navigation/listing helpers.",
        "plan": "Inspect and plan work. Code edits and shell execution stay blocked.",
        "approve": "Ask before shell commands and file changes. Best default for active coding.",
        "auto": "Allow in-workspace edits and shell commands without interactive approval.",
    }
    return summaries.get(mode, summaries["approve"])






























































def _ps_path(relative) -> str:
    """A workspace-relative path as Mitra prints it in PowerShell hints: `.\\src\\app.py` on every OS (E-005).

    Mitra's run hints are PowerShell commands; before this, Linux gave mixed `.\\src/app.py`."""
    rel = str(relative).replace("/", "\\").lstrip("\\")
    if rel.startswith(".\\"):
        return rel
    return ".\\" + rel






def _strip_sentence_dot(user_input: str) -> str:
    """E-051: a slash command typed like a sentence (`/run plan.md 4.`) loses its final period, so it is not read as
    part of the last argument. `..` and paths ending in `/` are left alone; chat messages are never changed."""
    text = user_input.rstrip()
    if text.startswith("/") and text.endswith(".") and not text.endswith(".."):
        return text[:-1].rstrip()
    return user_input


def _is_bang_command(user_input: str) -> bool:
    return user_input.strip().startswith("!")


def _extract_bang_command(user_input: str) -> str:
    return user_input.strip()[1:].strip()


def _read_readme_summary(workspace: str) -> str | None:
    for name in ("README.md", "readme.md"):
        path = pathlib.Path(workspace) / name
        if not path.exists():
            continue
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        heading_fallback: str | None = None
        for line in lines:
            if line.startswith("#"):
                if heading_fallback is None:
                    heading_fallback = line.lstrip("#").strip().rstrip(".")
                continue
            cleaned = line.lstrip("#> -*`").strip()
            if cleaned and not cleaned.lower().startswith(("usage", "install", "setup")):
                return cleaned.rstrip(".")
        if heading_fallback:
            return heading_fallback
    return None


def _detect_project_state(workspace: str, *, has_memory: bool = False, has_plan: bool = False) -> dict:
    root = pathlib.Path(workspace)
    targets = _find_run_targets(workspace)
    entrypoint = targets[0] if targets else None
    req = root / "requirements.txt"
    pyproject = root / "pyproject.toml"
    package_json = root / "package.json"
    state = {
        "workspace_name": root.name,
        "workspace_path": str(root),
        "entrypoint": entrypoint,
        "venv_exists": (root / ".venv").exists(),
        "requirements_exists": req.exists(),
        "pyproject_exists": pyproject.exists(),
        "package_json_exists": package_json.exists(),
        "is_git_repo": (root / ".git").exists(),
        "has_memory": has_memory,
        "has_plan": has_plan,
        "has_tests": any(
            (root / name).exists() for name in ("tests", "test", "pytest.ini")
        ) or bool(list(root.glob("test_*.py"))),
    }
    if state["requirements_exists"]:
        state["dependency_source"] = "requirements.txt"
    elif state["pyproject_exists"]:
        state["dependency_source"] = "pyproject.toml"
    elif state["package_json_exists"]:
        state["dependency_source"] = "package.json"
    else:
        state["dependency_source"] = None
    return state


def _find_run_targets(workspace: str) -> list[str]:
    root = pathlib.Path(workspace)
    candidates = [
        root / "main.py",
        root / "app.py",
        root / "snake.py",
    ]
    candidates.extend(
        path for path in sorted(root.glob("*/cli.py"))
        if path.parts[-2] not in {".venv", ".mitra", "__pycache__"}
    )
    candidates.extend(
        path for path in sorted(root.glob("*/__main__.py"))
        if path.parts[-2] not in {".venv", ".mitra", "__pycache__"}
    )
    candidates.extend(sorted(root.glob("src/*/cli.py")))
    candidates.extend(sorted(root.glob("src/*/__main__.py")))

    targets: list[str] = []
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            targets.append(_ps_path(candidate.relative_to(root)))
    return targets


def _workspace_snapshot(workspace: str) -> tuple[list[str], list[str]]:
    root = pathlib.Path(workspace)
    dirs: list[str] = []
    files: list[str] = []
    for entry in sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
        if entry.name.startswith(".") and entry.name not in {".venv", ".mitra"}:
            continue
        if entry.is_dir():
            dirs.append(entry.name)
        else:
            files.append(entry.name)
    return dirs[:6], files[:6]








def _build_startup_project_brief(workspace: str) -> str | None:
    state = _detect_project_state(workspace)
    dirs, files = _workspace_snapshot(workspace)
    purpose = _read_readme_summary(workspace)

    details: list[str] = []
    if purpose:
        details.append(f"- **Purpose:** {purpose}.")
    details.append(f"- **Workspace:** `{state['workspace_name']}`")
    if state["dependency_source"]:
        details.append(f"- **Dependencies:** `{state['dependency_source']}`")
    if state["entrypoint"]:
        details.append(f"- **Entrypoint:** `{state['entrypoint']}`")
    if state["has_tests"]:
        details.append("- **Tests:** present")
    if state["venv_exists"]:
        details.append("- **Environment:** `.venv` detected")
    elif state["dependency_source"]:
        details.append("- **Environment:** dependencies exist but `.venv` is not ready yet")
    if dirs:
        details.append("- **Top folders:** " + ", ".join(f"`{name}/`" for name in dirs[:4]))
    if files:
        details.append("- **Top files:** " + ", ".join(f"`{name}`" for name in files[:4]))
    if len(details) <= 2:
        return None
    return "## Auto-detected project brief\n\n" + "\n".join(details)


def _summarize_plan_progress(workspace: str) -> str:
    plan_text = memory.load_plan(workspace)
    if not plan_text:
        return "No active plan"
    done = plan_text.count("- [x]")
    pending = plan_text.count("- [ ]")
    total = done + pending
    if total == 0:
        return "Plan loaded"
    return f"{done}/{total} done"


def _format_session_usage(total_tokens: int, auto_compact_threshold: int) -> str:
    pct = min(100, int(total_tokens / max(auto_compact_threshold, 1) * 100))
    return f"{total_tokens:,} tokens ({pct}% of compact threshold)"


def _describe_last_change(workspace: str) -> str:
    change_set = memory.load_last_change_set(workspace)
    if not change_set:
        return "None"
    entries = change_set.get("entries") or []
    recorded_at = change_set.get("recorded_at", "recently")
    return f"{len(entries)} step{'s' if len(entries) != 1 else ''} recorded at {recorded_at}"


def _summarize_background_tasks() -> str:
    tasks = shell_agent.list_background_tasks()
    if not tasks:
        return "None"
    running = sum(1 for task in tasks if task.status == "running")
    finished = len(tasks) - running
    return f"{running} running · {finished} finished"


def _build_model_reply(model: str, codegen_model: str, *, cloud_codegen_enabled: bool) -> str:
    codegen_value = codegen_model if cloud_codegen_enabled else f"{model} (local fallback)"
    mode = "Cloud-assisted code generation" if cloud_codegen_enabled else "Local-only"
    return (
        "## Active models\n\n"
        f"- **Chat / routing:** `{model}`\n"
        f"- **Code generation:** `{codegen_value}`\n"
        f"- **Mode:** {mode}\n\n"
        "Use `/model list` to inspect installed local models or `/model remove <name>` to delete one."
    )


def _build_mode_reply(session_mode: str) -> str:
    return (
        "## Session mode\n\n"
        f"- **Current mode:** `{ui.mode_label(session_mode)}`\n"
        f"- **Behavior:** {_mode_summary(session_mode)}\n\n"
        "Modes: `ask` (approve each change), `auto-edit` (change files without asking), "
        "`plan` (read and plan only). Shift+tab cycles them."
    )


def _build_reasoning_reply(show_reasoning: bool) -> str:
    state = "shown" if show_reasoning else "hidden"
    return (
        "## Reasoning display\n\n"
        f"- **Current setting:** `{state}`\n"
        "- **Behavior:** raw `<think>` output stays hidden by default; short task and plan panels remain visible."
    )


def _build_status_reply(
    workspace: str,
    model: str,
    codegen_model: str,
    *,
    cloud_codegen_enabled: bool,
    session_mode: str,
    show_reasoning: bool,
    total_tokens: int,
    auto_compact_threshold: int,
    num_ctx: int,
) -> str:
    state = _detect_project_state(
        workspace,
        has_memory=bool(memory.load_context(workspace)),
        has_plan=bool(memory.load_plan(workspace)),
    )
    session_meta = session_agent.ensure_session(workspace)
    shell_cwd = shell_agent.get_cwd()
    approval_mode = _mode_summary(session_mode)
    cpu_pct = config.get_cpu_usage_pct()
    gpu_info = config.get_gpu_memory_info()
    ram_total = config.get_total_system_memory_gib()
    ram_free = config.get_available_system_memory_gib()
    resource_parts = []
    if cpu_pct is not None:
        resource_parts.append(f"CPU `{cpu_pct:.1f}%`")
    if ram_total is not None and ram_free is not None:
        resource_parts.append(f"RAM `{ram_free:.1f} / {ram_total:.1f} GB free`")
    if gpu_info is not None:
        resource_parts.append(f"GPU `{gpu_info.free_gib:.1f} / {gpu_info.total_gib:.1f} GB free`")
    mcp_summary = mcp_registry.summarize(mcp_registry.discover(workspace))
    return (
        "## Session status\n\n"
        f"- **Session:** `{session_meta.get('name', pathlib.Path(workspace).resolve().name)}`\n"
        f"- **Workspace:** `{state['workspace_path']}`\n"
        f"- **Shell cwd:** `{shell_cwd}`\n"
        f"- **Entrypoint:** `{state['entrypoint'] or 'Not detected yet'}`\n"
        f"- **Plan:** {_summarize_plan_progress(workspace)}\n"
        f"- **Memory:** {'Loaded' if state['has_memory'] else 'Not loaded yet'}\n"
        f"- **Mode:** `{ui.mode_label(session_mode)}`\n"
        f"- **Reasoning display:** {'shown' if show_reasoning else 'hidden'}\n"
        f"- **Model:** `{model}`\n"
        f"- **MCP:** {mcp_summary}\n"
        f"- **Context settings:** `{num_ctx:,}` max · compact at `{auto_compact_threshold:,}`\n"
        f"- **Session usage:** {_format_session_usage(total_tokens, auto_compact_threshold)}\n"
        f"- **Resources:** {' · '.join(resource_parts) if resource_parts else 'Unavailable'}\n"
        f"- **Behavior:** {approval_mode}\n"
        f"- **Background tasks:** {_summarize_background_tasks()}\n"
        f"- **Git:** {_build_git_summary(workspace)}\n"
        f"- **Commit readiness:** {_build_commit_readiness(workspace)}\n"
        f"- **Last undoable change:** {_describe_last_change(workspace)}"
    )


def _build_logs_reply(workspace: str, target: str = "summary") -> str:
    vault = pathlib.Path(workspace) / ".mitra"
    if not vault.exists():
        return "No `.mitra/` workspace logs exist yet. Run `agent init` or start a session first."

    target_name = (target or "summary").strip().lower()
    files = {
        "history": "activity.md",
        "session": "session_log.md",
        "trace": "execution_trace.jsonl",
        "decisions": "decisions.md",
        "errors": "errors.md",
        "tasks": "task_board.md",
        "plan": "plan.md",
    }
    if target_name in files:
        path = vault / files[target_name]
        if not path.exists():
            return f"No `{files[target_name]}` log exists yet."
        text = path.read_text(encoding="utf-8")
        preview = text[-2000:] if len(text) > 2000 else text
        return f"## {files[target_name]}\n\n```text\n{preview.strip()}\n```"

    lines = [
        "## Logs",
        "",
        f"- **Vault:** `{vault}`",
    ]
    for key, filename in files.items():
        path = vault / filename
        state = "present" if path.exists() else "missing"
        lines.append(f"- **{key}:** `{filename}` · {state}")
    lines.append("")
    lines.append("Use `agent logs <history|session|trace|decisions|errors|tasks|plan>` for one artifact.")
    return "\n".join(lines)


def _build_model_inventory_reply(
    active_model: str,
    codegen_model: str,
    *,
    cloud_codegen_enabled: bool,
    model_inventory: list | None = None,
) -> str:
    inventory = model_inventory if model_inventory is not None else config.get_local_model_inventory()
    gpu_info = config.get_gpu_memory_info()
    vram_gib = gpu_info.total_gib if gpu_info else None
    total_ram_gib = config.get_total_system_memory_gib()
    budget_gib = config.get_recommended_model_budget_gib()
    cpu_pct = config.get_cpu_usage_pct()
    ram_free_gib = config.get_available_system_memory_gib()
    lines = [
        "## Local models",
        "",
        f"- **Active chat model:** `{active_model}`",
        f"- **Active codegen model:** `{codegen_model if cloud_codegen_enabled else active_model}`",
    ]
    if vram_gib is not None:
        lines.append(f"- **GPU VRAM:** `{vram_gib:.1f} GB`")
    if gpu_info is not None:
        lines.append(
            f"- **Live GPU usage:** `{gpu_info.used_gib:.1f} GB used` · `{gpu_info.free_gib:.1f} GB free` ({gpu_info.usage_pct}% in use)"
        )
    if total_ram_gib is not None:
        lines.append(f"- **System RAM:** `{total_ram_gib:.1f} GB`")
    if ram_free_gib is not None:
        lines.append(f"- **RAM free now:** `{ram_free_gib:.1f} GB`")
    if cpu_pct is not None:
        lines.append(f"- **CPU usage now:** `{cpu_pct:.1f}%`")
    if budget_gib is not None:
        label = "GPU budget" if vram_gib is not None else "Recommended budget"
        lines.append(f"- **{label}:** `{budget_gib:.1f} GB`")
    lines.append("")

    _PLACEMENT_LABEL = {"gpu": "🟢 GPU", "split": "🟡 GPU+CPU", "cpu": "🔴 CPU"}

    normalized_inventory = []
    for item in inventory:
        if isinstance(item, str):
            normalized_inventory.append({"name": item, "size_text": "", "recommended": True, "placement": "gpu"})
            continue
        normalized_inventory.append(
            {
                "name": getattr(item, "name", ""),
                "size_text": getattr(item, "size_text", ""),
                "recommended": bool(getattr(item, "recommended", True)),
                "placement": getattr(item, "placement", "gpu"),
            }
        )

    recommended = [item for item in normalized_inventory if item["recommended"]]
    hidden = [item for item in normalized_inventory if not item["recommended"]]

    if not normalized_inventory:
        lines.append("No local Ollama models found.")
    else:
        if recommended:
            lines.append("### GPU-accelerated (recommended)")
            lines.append("")
            for item in recommended:
                suffix = " **(active)**" if item["name"] == active_model else ""
                size = f" — {item['size_text']}" if item["size_text"] else ""
                badge = f" {_PLACEMENT_LABEL.get(item['placement'], '')}"
                lines.append(f"- `{item['name']}`{suffix}{size}{badge}")
            lines.append("")
        if hidden:
            lines.append("### CPU-only (too large for GPU)")
            lines.append("")
            for item in hidden:
                suffix = " **(active)**" if item["name"] == active_model else ""
                size = f" — {item['size_text']}" if item["size_text"] else ""
                lines.append(f"- `{item['name']}`{suffix}{size} 🔴 CPU")
            lines.append("")

    lines.append("Use `/model remove <name>` to delete a local model and free space.")
    lines.append("Use `/resources` for live CPU/RAM/GPU usage, or `/make-space` to stop reclaimable local AI and GPU processes.")
    lines.append("Override GPU layer count with `gpu_layers` in `mitra.toml` (`0` = CPU, `-1` = full GPU, `auto` = let Ollama decide).")
    return "\n".join(lines)


def _build_resources_reply() -> str:
    cpu_pct = config.get_cpu_usage_pct()
    ram_total = config.get_total_system_memory_gib()
    ram_free = config.get_available_system_memory_gib()
    gpu_info = config.get_gpu_memory_info()
    local_ai_processes = config.list_local_ai_processes()
    gpu_processes = config.list_user_gpu_processes()
    reclaimable = config.list_reclaimable_processes()

    lines = ["## System resources", ""]
    if cpu_pct is not None:
        lines.append(f"- **CPU usage:** `{cpu_pct:.1f}%`")
    if ram_total is not None:
        lines.append(f"- **System RAM:** `{ram_total:.1f} GB`")
    if ram_free is not None:
        lines.append(f"- **RAM free now:** `{ram_free:.1f} GB`")
    if gpu_info is not None:
        lines.append(
            f"- **GPU VRAM:** `{gpu_info.used_gib:.1f} / {gpu_info.total_gib:.1f} GB used` · `{gpu_info.free_gib:.1f} GB free` ({gpu_info.usage_pct}% in use)"
        )
    else:
        lines.append("- **GPU VRAM:** unavailable")
    lines.append("")
    if local_ai_processes:
        lines.append("### Detected Ollama / local AI processes")
        for proc in local_ai_processes:
            memory = f" · `{proc.memory_gib:.2f} GB RAM`" if proc.memory_gib is not None else ""
            lines.append(f"- `{proc.name}` pid `{proc.pid}`{memory}")
        lines.append("")
    else:
        lines.append("No Ollama/local AI processes detected beyond this Mitra session.")
        lines.append("")
    if gpu_processes:
        lines.append("### User-owned GPU processes from nvidia-smi")
        for proc in gpu_processes:
            memory = f" · `{proc.memory_gib:.2f} GB RAM`" if proc.memory_gib is not None else ""
            gpu = f" · `{proc.gpu_memory_gib:.2f} GB GPU`" if proc.gpu_memory_gib is not None else ""
            lines.append(f"- `{proc.name}` pid `{proc.pid}`{memory}{gpu}")
        lines.append("")
    else:
        lines.append("No user-owned GPU processes detected in `nvidia-smi` beyond this session.")
        lines.append("")
    if reclaimable:
        lines.append("Use `/make-space` to stop these reclaimable processes and free CPU/GPU memory.")
    else:
        lines.append("No reclaimable local AI or user-owned GPU processes detected right now.")
    return "\n".join(lines)


def _handle_model_command(
    raw_input: str,
    active_model: str,
    codegen_model: str,
    *,
    cloud_codegen_enabled: bool,
) -> str:
    parts = raw_input.strip().split(maxsplit=2)
    if len(parts) == 1:
        return _build_model_reply(active_model, codegen_model, cloud_codegen_enabled=cloud_codegen_enabled)

    action = parts[1].lower()
    if action in {"list", "ls"}:
        return _build_model_inventory_reply(
            active_model,
            codegen_model,
            cloud_codegen_enabled=cloud_codegen_enabled,
        )

    if action in {"remove", "rm", "delete"}:
        if len(parts) < 3 or not parts[2].strip():
            return "Usage: `/model remove <name>`."
        target = parts[2].strip()
        if target == active_model:
            return f"Cannot remove the active chat model `{active_model}` while this session is using it."
        success, detail = config.remove_local_model(target)
        if not success:
            return f"Could not remove `{target}`.\n\n{detail}"
        inventory = _build_model_inventory_reply(
            active_model,
            codegen_model,
            cloud_codegen_enabled=cloud_codegen_enabled,
        )
        return f"{detail}\n\n{inventory}"

    if action in {"use", "switch", "set"}:
        if len(parts) < 3 or not parts[2].strip():
            return "Usage: `/model use <name>`."
        target = parts[2].strip()
        names = {m.name for m in config.get_local_model_inventory()}
        if target not in names:
            return f"`{target}` is not one of Mitra's models. `/model list` shows them."
        config.save_last_model(target)
        return f"Mitra will start with `{target}` next time. Type `exit` and start Mitra again to switch now."

    return "Usage: `/model`, `/model list`, `/model use <name>`, or `/model remove <name>`."








def _is_git_repo(workspace: str) -> bool:
    try:
        result = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=workspace, capture_output=True,
                                text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):  # no git, or git hung: treat as not a repo
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_output(workspace: str, args: list[str]) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=workspace, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _parse_git_status_counts(status_text: str) -> dict[str, int]:
    """Count staged, unstaged, and untracked entries from git status --short."""
    lines = [line for line in status_text.splitlines() if line.strip()]
    return {
        "staged": sum(1 for line in lines if not line.startswith("??") and line[0] != " "),
        "unstaged": sum(1 for line in lines if not line.startswith("??") and len(line) > 1 and line[1] != " "),
        "untracked": sum(1 for line in lines if line.startswith("??")),
        "total": len(lines),
    }


def _build_git_summary(workspace: str) -> str:
    """Return a compact branch-aware git summary for operator status surfaces."""
    if not _is_git_repo(workspace):
        return "Not a git repository"

    branch = _git_output(workspace, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    if branch == "HEAD":
        commit = _git_output(workspace, ["rev-parse", "--short", "HEAD"])
        branch = f"detached at {commit}" if commit else "detached HEAD"

    upstream = _git_output(workspace, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    counts = _parse_git_status_counts(_git_output(workspace, ["status", "--short"]))
    if counts["total"] == 0:
        state = "clean"
    else:
        parts = []
        if counts["staged"]:
            parts.append(f"{counts['staged']} staged")
        if counts["unstaged"]:
            parts.append(f"{counts['unstaged']} unstaged")
        if counts["untracked"]:
            parts.append(f"{counts['untracked']} untracked")
        state = ", ".join(parts) if parts else f"{counts['total']} changed"

    upstream_text = f" · upstream `{upstream}`" if upstream else ""
    return f"`{branch}`{upstream_text} · {state}"


def _build_commit_readiness(workspace: str) -> str:
    """Return a deterministic commit-readiness summary from git status."""
    if not _is_git_repo(workspace):
        return "Not a git repository"

    counts = _parse_git_status_counts(_git_output(workspace, ["status", "--short"]))
    if counts["total"] == 0:
        return "Clean working tree; nothing to commit"
    if counts["staged"] == 0:
        pending = counts["unstaged"] + counts["untracked"]
        return f"Not ready: no staged changes ({pending} unstaged/untracked)"
    if counts["unstaged"] == 0 and counts["untracked"] == 0:
        return f"Ready: {counts['staged']} staged change{'s' if counts['staged'] != 1 else ''}"

    leftovers = []
    if counts["unstaged"]:
        leftovers.append(f"{counts['unstaged']} unstaged")
    if counts["untracked"]:
        leftovers.append(f"{counts['untracked']} untracked")
    return (
        f"Partially ready: {counts['staged']} staged, "
        f"{' and '.join(leftovers)} outside the commit"
    )


def _generate_commit_message(workspace: str, llm, *, staged: bool = True) -> str | None:
    """Generate a suggested commit message from the diff using the LLM."""
    if not _is_git_repo(workspace):
        return None
    # Plain git with a timeout (E-027): the git_diff tool's reply is "✓ git diff\n(no diff)"
    # when nothing changed, which the old check missed, so the model drafted from nothing.
    args = ["git", "diff", "--cached"] if staged else ["git", "diff"]
    try:
        result = subprocess.run(args, cwd=workspace, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
    except subprocess.TimeoutExpired:
        return None
    diff_output = (result.stdout or "").strip() if result.returncode == 0 else ""
    if not diff_output:
        return None

    prompt = (
        "Generate a concise, conventional commit message for the following diff.\n"
        "Format: <type>(<scope>): <subject>\n\n"
        "Types: feat, fix, refactor, chore, docs, test, perf, build, ci\n"
        "Rules:\n"
        "  - Single line subject (max 72 chars)\n"
        "  - Imperative mood (add, fix, remove, not added, fixed, removed)\n"
        "  - No trailing period\n"
        "  - If multiple logical changes, suggest multiple commits\n"
        "Output ONLY the commit message, nothing else.\n\n"
        f"Diff:\n{diff_output}"
    )

    from langchain_core.messages import HumanMessage
    with console.status("[m.dim]Generating commit message...[/m.dim]", spinner_style="m.accent"):
        response = llm.invoke([HumanMessage(content=prompt)])
    msg = (response.content or "").strip()
    return msg if msg else None


def _cmd_commit(workspace: str, llm, message: str | None = None, *, staged: bool = True, generate: bool = False) -> str:
    """Handle `/commit`: commit the staged changes only, with an optional drafted message.

    Never stages and never pushes. E-027: it used the git_commit tool, which runs
    `git add -A` first, so unstaged and untracked files were committed too.
    """
    if not _is_git_repo(workspace):
        return "Not a git repository."

    # `--quiet` exits 1 when something is staged, 0 when nothing is.
    try:
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workspace,
                                capture_output=True, timeout=30).returncode == 1
    except subprocess.TimeoutExpired:
        return "✗ git diff timed out after 30 s."
    if not staged:
        return ("Nothing is staged. `/commit` commits staged changes only: "
                "stage files with `! git add <files>` first.")

    if generate:
        suggested = _generate_commit_message(workspace, llm, staged=True)
        if not suggested:
            return "Could not draft a message. Use `/commit <message>`."
        console.print()
        console.print(ui.tool_line("Commit message"))
        console.print(ui.detail_block(suggested))
        choice = ui.menu.choose(console, "Use this message?",
                                [("yes", "Yes"), ("edit", "No, I'll type my own")], default="yes")
        if choice == "yes":
            message = suggested
        elif choice == "edit":
            message = console.input("[dim]Enter custom message: [/dim]").strip()
            if not message:
                return "Commit cancelled: empty message."
        else:
            return "Commit cancelled."

    if not message:
        return "Usage: `/commit <message>` or `/commit --generate` to auto-suggest."

    try:
        result = subprocess.run(["git", "commit", "-m", message], cwd=workspace, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return "✗ git commit timed out after 120 s (a commit hook may be stuck)."
    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    return f"✓ Committed: {message}\n{output}" if result.returncode == 0 else f"✗ {output}"


def _truncate_diff(text: str, max_lines: int = 160) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    kept = "\n".join(lines[:max_lines])
    return f"{kept}\n... ({len(lines) - max_lines} more lines omitted)"


def _render_change_entry_diff(entry: dict, workspace: str) -> str:
    kind = entry.get("kind")
    if kind == "move_file":
        src = pathlib.Path(entry["src"])
        dest = pathlib.Path(entry["dest"])
        try:
            src_display = _ps_path(src.relative_to(workspace))
            dest_display = _ps_path(dest.relative_to(workspace))
        except ValueError:
            src_display = str(src)
            dest_display = str(dest)
        return f"- moved `{src_display}` -> `{dest_display}`"

    path = pathlib.Path(entry["path"])
    try:
        display = _ps_path(path.relative_to(workspace))
    except ValueError:
        display = str(path)

    before = (entry.get("before") or "").splitlines()
    after = (entry.get("after") or "").splitlines()
    if kind == "delete_file":
        after = []
    diff = "\n".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"before\\{path.name}",
            tofile=f"after\\{path.name}",
            lineterm="",
        )
    )
    if not diff:
        return f"- changed `{display}`"
    return f"### `{display}`\n```diff\n{diff}\n```"


def _build_change_set_diff_reply(workspace: str) -> str | None:
    change_set = memory.load_last_change_set(workspace)
    if not change_set:
        return None

    entries = change_set.get("entries") or []
    if not entries:
        return None

    lines = ["## Last Mitra change set", ""]
    for entry in entries:
        lines.append(_render_change_entry_diff(entry, workspace))
        lines.append("")
    return "\n".join(lines).strip()


def _build_diff_reply(workspace: str) -> str:
    if _is_git_repo(workspace):
        diff_output = filesystem.git_diff.invoke({"cwd": workspace, "staged": False})
        if isinstance(diff_output, str) and diff_output.startswith("✓ git diff"):
            body = diff_output.split("\n", 1)[1] if "\n" in diff_output else "(no diff)"
            if body.strip() != "(no diff)":
                return f"## Working tree diff\n\n```diff\n{_truncate_diff(body)}\n```"

    change_set_reply = _build_change_set_diff_reply(workspace)
    if change_set_reply:
        return change_set_reply

    return "No diff is available yet."


def _build_change_set_review_input(workspace: str) -> str | None:
    change_set = memory.load_last_change_set(workspace)
    if not change_set:
        return None

    entries = change_set.get("entries") or []
    if not entries:
        return None

    lines = ["Last Mitra change set", ""]
    for entry in entries:
        kind = entry.get("kind")
        if kind == "move_file":
            src = pathlib.Path(entry["src"])
            dest = pathlib.Path(entry["dest"])
            try:
                src_display = _ps_path(src.relative_to(workspace))
                dest_display = _ps_path(dest.relative_to(workspace))
            except ValueError:
                src_display = str(src)
                dest_display = str(dest)
            lines.append(f"- moved {src_display} -> {dest_display}")
            continue

        path = pathlib.Path(entry["path"])
        try:
            display = _ps_path(path.relative_to(workspace))
        except ValueError:
            display = str(path)
        lines.append(f"File: {display}")
        lines.append(_render_change_entry_diff(entry, workspace))
        lines.append("")

    return "\n".join(lines).strip()


_REVIEW_INCOMPLETE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bTODO\b", "Added TODO markers that may indicate unfinished work."),
    (r"\bFIXME\b", "Added FIXME markers that may indicate known unresolved issues."),
    (r"\bXXX\b", "Added XXX markers that often signal incomplete code."),
    (r"\bpass\b", "Added `pass` statements that may leave logic unimplemented."),
    (r"NotImplementedError", "Added `NotImplementedError`, which may leave runtime paths incomplete."),
)
_REVIEW_RISK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bshell\s*=\s*True\b", "Introduced shell=True in subprocess usage, which increases command-injection risk."),
    (r"\beval\s*\(", "Introduced `eval(...)`, which is risky with untrusted input."),
    (r"\bexec\s*\(", "Introduced `exec(...)`, which is risky with untrusted input."),
    (r"\bverify\s*=\s*False\b", "Disabled TLS verification, which weakens transport security."),
    (r"\b(shutil\.rmtree|os\.remove|os\.unlink)\b", "Added destructive file-system operations."),
)


def _collect_review_risk_signals(review_input: str) -> list[str]:
    """Extract deterministic risk/incomplete signals from review material."""
    lines = review_input.splitlines()
    added_lines = [
        line[1:].strip()
        for line in lines
        if line.startswith("+") and not line.startswith("+++")
    ]
    corpus = "\n".join(added_lines if added_lines else lines)
    signals: list[str] = []
    for pattern, message in (*_REVIEW_INCOMPLETE_PATTERNS, *_REVIEW_RISK_PATTERNS):
        if re.search(pattern, corpus, flags=re.IGNORECASE | re.MULTILINE):
            signals.append(message)
    # Preserve insertion order while deduplicating.
    return list(dict.fromkeys(signals))


def _append_review_risk_summary(summary: str, signals: list[str]) -> str:
    if not signals:
        return summary
    section = "### Auto-detected risk signals\n" + "\n".join(f"- {signal}" for signal in signals)
    if "no material issues found" in summary.lower():
        return (
            f"{summary}\n\n{section}\n\n"
            "Please confirm these are intentional; otherwise tighten the patch before merging."
        )
    return f"{summary}\n\n{section}"


def _parse_review_target(raw: str) -> str:
    remainder = raw.strip()[7:].strip().lower()
    if remainder == "staged":
        return "staged"
    return "working"


def _build_git_review_input(workspace: str, *, staged: bool) -> tuple[str, str] | None:
    status_output = filesystem.git_status.invoke({"cwd": workspace})
    diff_output = filesystem.git_diff.invoke({"cwd": workspace, "staged": staged})
    if not (isinstance(diff_output, str) and diff_output.startswith("✓ git diff")):
        return None

    body = diff_output.split("\n", 1)[1] if "\n" in diff_output else ""
    if not body.strip() or body.strip() == "(no diff)":
        return None

    status_body = ""
    if isinstance(status_output, str) and status_output.startswith("✓ git status"):
        status_body = status_output.split("\n", 1)[1] if "\n" in status_output else ""

    label = "staged git diff" if staged else "current git diff"
    review_input = (
        f"Git status:\n{status_body or '(nothing to report)'}\n\n"
        f"Diff:\n{_truncate_diff(body, max_lines=220)}"
    )
    return (label, review_input)


def _get_review_material(workspace: str, target: str = "working") -> tuple[str, str] | None:
    if _is_git_repo(workspace):
        git_material = _build_git_review_input(workspace, staged=(target == "staged"))
        if git_material is not None:
            return git_material

    change_set_input = _build_change_set_review_input(workspace)
    if change_set_input:
        return ("last Mitra change set", change_set_input)

    return None


def _cmd_review(workspace: str, llm, target: str = "working") -> str:
    material = _get_review_material(workspace, target=target)
    if material is None:
        return "Nothing to review yet. Make a change first or use `/diff` to inspect the current state."

    source, review_input = material
    workflow = workflows.WorkflowRun(
        workspace,
        "ReviewWorkflow",
        f"Review {source}",
    )
    step_label = f"Review {source}"
    workflow.start_step(step_label)
    risk_signals = _collect_review_risk_signals(review_input)
    review_request = "Review the current changes and surface any material issues."
    if risk_signals:
        review_request = (
            f"{review_request}\n\n"
            "Pay extra attention to these potential risk signals:\n"
            + "\n".join(f"- {signal}" for signal in risk_signals)
        )
    response = reviewer_agent.run(
        llm,
        review_request,
        review_input,
        source=source,
    )
    response.summary = _append_review_risk_summary(response.summary, risk_signals)
    workflow.finish_step(step_label, detail=response.summary[:300])
    workflow.complete(response.summary[:300])
    console.print(reviewer_agent.render(response))
    return response.summary


def _cmd_logs(raw: str, workspace: str) -> str:
    target = raw.strip()[5:].strip() if raw.strip().startswith("/logs") else raw.strip()
    return _build_logs_reply(workspace, target or "summary")


def _build_mcp_reply(workspace: str, cfg: dict | None = None, args: str = "") -> str:
    return mcp_registry.handle_command(workspace, args)


def _cmd_test(command: str, workspace: str) -> str:
    target = command.strip() or "pytest"
    result = shell_agent.execute(command=target, cwd=workspace, console=console)
    console.print(shell_agent.render(result))
    return result.output


def _cmd_resume(workspace: str) -> str:
    reply = session_agent.build_resume_reply(workspace)
    console.print(session_agent.render_resume(reply))
    return reply














def _choose_approval_option(
    title: str,
    prompt: str,
    options: list[tuple[str, str]],
    *,
    fallback_default: str | None = None,
) -> str | None:
    """Show what needs approval as a tool line + detail, then an inline arrow-key menu (D-031)."""
    lines = (prompt or "").rstrip().splitlines()
    question = "What should Mitra do?"
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and (lines[-1].strip().endswith("?") or lines[-1].strip().startswith("Choose ")):
        last = lines.pop().strip()
        if last.endswith("?"):
            question = last
    console.print()
    console.print(ui.tool_line(title))
    detail = "\n".join(lines).strip()
    if detail:
        console.print(ui.detail_block(detail))
    return ui.menu.choose(console, question, options, default=fallback_default)


def _print_approval_result(message: str, *, approved: bool) -> None:
    from rich.text import Text as _T
    console.print(_T(f"    {message}", style="m.faint" if approved else "m.err"))


def _shell_command_name(command: str) -> str:
    try:
        parts = shell_agent._split_command(command)
    except ValueError:
        parts = command.strip().split()
    if not parts:
        return command.strip().lower()
    exe = pathlib.Path(parts[0]).name
    return re.sub(r"\.exe$", "", exe, flags=re.IGNORECASE).lower()
















def _rebuild_dashboard(quiet: bool = False):
    """Rebuild ~/.mitra/dashboard.html from the central store. Never raises (an exit must not fail on it)."""
    from app.core import dashboard as D
    try:
        out, _ = D.build()
    except Exception as exc:
        if not quiet:
            console.print(Text(f"  ✗ dashboard not rebuilt: {exc}", style="m.err"))
        return None
    console.print(Text(f"  dashboard: {out}", style="m.faint"))
    return out


def _header_extras(cfg: dict, harness) -> tuple[str, str, str]:
    """Header rows: role models at a glance, what Mitra has learned and records, the dashboard link."""
    roles_line = learning = dash = ""
    try:
        from app.core import roles as R
        have = R.installed()
        picks = [(r, R.resolve(r, cfg, have)[0]) for r in ("planner", "builder")]
        roles_line = " · ".join(f"{r} {m}" for r, m in picks) + " · /role to switch"
    except Exception:
        pass
    try:
        from app.core import runinfo
        traces = "traces on" if cfg.get("save_traces", True) else "traces off"
        learning = (f"harness v{harness.version} · {len(harness.rules)} learned rule{'s' if len(harness.rules) != 1 else ''}"
                    f" · {traces} · Mitra {runinfo.code_version()}")
    except Exception:
        pass
    try:
        from app.core import server as dash_server
        dash = dash_server.URL if dash_server.running() else "mitra dashboard (not running)"
    except Exception:
        pass
    return roles_line, learning, dash


def _follow_night() -> None:
    """Live view of the latest night run in the chat; ctrl+c stops watching only."""
    from app.core import night as night_mod
    try:
        st = night_mod.follow(lambda line: console.print(Text("  " + line, style="m.dim")))
    except KeyboardInterrupt:
        console.print(Text("\n  stopped watching; the night keeps going · `/night` to watch again", style="m.faint"))
        return
    if st and not st["running"]:
        console.print(Text("  ⏾ the night run finished", style="m.tool"))
        if st["report"]:
            console.print(Markdown(st["report"]))
        else:
            console.print(Text(f"  no report was written: see {st['console_log']}", style="m.err"))


def _cmd_free(model: str, num_ctx: int, base_url: str, *, fit_mod=None, tick=None, choose=None) -> None:
    """/free (I-21): what the model needs vs what is free, a tick list of programs (the ones covering the shortfall
    ticked), close the ticked ones politely, force only on a second yes, unload other Ollama models, check again."""
    from app import fit as _fit
    from app.ui import menu
    fit_mod = fit_mod or _fit
    tick = tick or menu.tick
    choose = choose or menu.choose
    before = fit_mod.check(model, num_ctx, base_url=base_url)
    style = {"ok": "m.ok", "tight": "m.info", "no": "m.err"}.get(before.verdict, "m.faint")
    console.print(Text(f"  {model} · {num_ctx // 1024}K · " + fit_mod.summary(before), style=style))
    if before.verdict == "remote":
        console.print(Text("    nothing to free here: `mitra remote off` goes back to this machine", style="m.faint"))
        return
    programs, pre = fit_mod.free_choices(before, fit_mod.live_programs())
    unload = [m.split(" (")[0] for m in before.unload]
    options = [fit_mod.label(p) for p in programs] + [f"unload {m} from Ollama" for m in unload]
    pre = pre | {len(programs) + i for i in range(len(unload))}
    if not options:
        console.print(Text("    nothing big enough to close (Mitra's terminal, Ollama and Windows are never listed)",
                           style="m.faint"))
        return
    picked = tick(console, "Close which programs to make room? (Mitra's terminal, Ollama and Windows are never "
                           "listed)", options, pre)
    if not picked:
        if picked is not None:
            console.print(Text("    nothing ticked: nothing closed", style="m.faint"))
        return
    chosen = [programs[i] for i in picked if i < len(programs)]
    models = [unload[i - len(programs)] for i in picked if i >= len(programs)]
    if models:
        done = fit_mod.unload_models(models, base_url)
        console.print(Text(f"    unloaded from Ollama: {', '.join(done) or 'none (Ollama did not answer)'}",
                           style="m.tool"))
    if chosen:
        console.print(Text(f"    closing {', '.join(p.name for p in chosen)} (like clicking ✕, up to 10 s) …",
                           style="m.dim"))
        result = fit_mod.close_programs(chosen)
        still = [p for p in chosen if not result.get(p.name)]
        if still:
            names = ", ".join(p.name for p in still)
            answer = choose(console, f"{names} did not close (a save prompt or a hidden window?). Force it?",
                            [("no", "No, leave it open (finish its prompts yourself, then /free again)"),
                             ("yes", "Yes, force it now: unsaved work in it is lost")], default="no")
            if answer == "yes":
                result.update(fit_mod.close_programs(still, force=True, wait_s=5.0))
        closed = [n for n, ok in result.items() if ok]
        left = [n for n, ok in result.items() if not ok]
        console.print(Text("    " + (f"✓ closed {', '.join(closed)}" if closed else "nothing closed")
                           + (f" · still open: {', '.join(left)}" if left else ""),
                           style="m.ok" if closed else "m.info"))
    after = fit_mod.check(model, num_ctx, base_url=base_url)
    gained = (after.free_ram_gb or 0.0) - (before.free_ram_gb or 0.0)
    style = {"ok": "m.ok", "tight": "m.info", "no": "m.err"}.get(after.verdict, "m.faint")
    console.print(Text(f"  freed {max(gained, 0.0):.1f} GB · " + fit_mod.summary(after), style=style))


def _print_memory_fit(model: str, num_ctx: int, base_url: str) -> None:
    """Startup line: can this machine run the model at this context, and what to close if not (D-040).
    Only warns; never blocks the start."""
    from app import fit as fit_mod
    try:
        fit = fit_mod.check(model, num_ctx, base_url=base_url)
    except Exception as exc:  # a failed check must not stop Mitra
        console.print(Text(f"  ? could not check memory: {exc}", style="m.faint"))
        return None
    style = {"ok": "m.ok", "tight": "m.info", "no": "m.err"}.get(fit.verdict, "m.faint")
    console.print(Text("  " + fit_mod.summary(fit), style=style))
    for line in fit_mod.advice(fit):
        console.print(Text("    " + line, style="m.dim"))
    return fit


def _startup_model(cfg: dict) -> str:
    """Model for this session without asking: mitra.toml, else the last one used, else qwen3.5:4b (D-034).
    Falls back to the picker only when none of those is installed."""
    configured = cfg.get("local_model") or cfg.get("model")
    if configured:
        return configured
    names = [m.name for m in config.get_local_model_inventory()]
    last = config.load_last_model()
    if last and last in names:
        return last
    for preferred in config.DEFAULT_MODELS:
        if preferred in names:
            return preferred
    console.print()
    console.print(ui.header.title_line())
    console.print()
    return _pick_model(cfg)


def _pick_model(cfg: dict) -> str:
    """Return the model to use: from config if set, otherwise prompt the user."""
    configured = cfg.get("local_model") or cfg.get("model")
    if configured:
        console.print(f"[m.faint]  · model from config: {configured}[/m.faint]")
        return configured

    while True:
        inventory = config.get_local_model_inventory()
        if not inventory:
            console.print(
                "[m.err]No compatible local Ollama models found. Mitra needs a chat model with tool calling, "
                "e.g. 'ollama pull qwen3.5:4b'.[/m.err]"
            )
            raise SystemExit(1)
        incompatible = len(config.get_local_model_inventory(include_incompatible=True)) - len(inventory)
        if incompatible > 0:
            console.print(Text(
                f"  {incompatible} other installed models hidden: Mitra runs on qwen3.5 4B and 9B, 128K context. "
                "`mitra models --all` lists them",
                style="m.faint",
            ))

        recommended_models = [model for model in inventory if model.recommended]
        hidden_models = [model for model in inventory if not model.recommended]
        visible_models = recommended_models or inventory
        gpu_info = config.get_gpu_memory_info()
        vram_gib = gpu_info.total_gib if gpu_info else None
        total_ram_gib = config.get_total_system_memory_gib()
        free_ram_gib = config.get_available_system_memory_gib()
        budget_gib = config.get_recommended_model_budget_gib()

        console.print(Text("  Pick a model", style="m.tool"))
        console.print(ui.header.hardware_line(
            vram_gib=vram_gib,
            vram_free_gib=gpu_info.free_gib if gpu_info else None,
            ram_free_gib=free_ram_gib,
            ram_total_gib=total_ram_gib,
        ))
        if gpu_info is not None and budget_gib is not None and gpu_info.free_gib + 0.5 < budget_gib:
            console.print(Text("  GPU memory is partly in use by another program; larger models may spill to CPU.",
                               style="m.err"))
        if not recommended_models:
            console.print(Text("  No model fits the GPU right now, so all installed models are listed.", style="m.err"))
        console.print()
        console.print(ui.header.model_table(visible_models))
        if hidden_models:
            console.print(Text("\n  Too large for the GPU (slow): " + ", ".join(m.name for m in hidden_models),
                               style="m.faint"))
        console.print(Text("\n  number or name · rm <n> deletes a model · refresh reloads", style="m.faint"))

        choice = console.input("\n[m.accent]›[/m.accent] ").strip()
        if not choice:
            console.print("[m.dim]Pick a model name or number.[/m.dim]")
            continue

        normalized = choice.lower()
        if normalized in {"refresh", "reload"}:
            continue

        if normalized.startswith(("rm ", "remove ", "delete ")):
            _, raw_target = choice.split(None, 1)
            target = raw_target.strip()
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(visible_models):
                    target = visible_models[idx].name
                else:
                    console.print("[m.dim]Invalid model number to remove.[/m.dim]")
                    continue
            elif target not in {model.name for model in inventory}:
                console.print("[m.dim]Unknown model name to remove.[/m.dim]")
                continue

            success, detail = config.remove_local_model(target)
            style = "green" if success else "red"
            console.print(f"[{style}]{detail}[/{style}]")
            continue

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(visible_models):
                return visible_models[idx].name
        elif choice in {model.name for model in visible_models}:
            return choice
        elif choice in {model.name for model in hidden_models}:
            console.print("[m.err]  That model runs on CPU only (too large for GPU); expect slow replies.[/m.err]")
            return choice
        else:
            # Typing the exact name of a hidden model still works, with a warning.
            others = {m.name: m for m in config.get_local_model_inventory(include_incompatible=True)}
            if choice in others:
                problem = config.compatibility_problem(config.get_model_facts(choice), choice) or "untested with Mitra"
                console.print(f"[m.err]  {choice} is not a Mitra model ({problem}); it may fail at tool calls.[/m.err]")
                return choice
        console.print("[m.dim]Invalid choice, try again.[/m.dim]")


def _resolve_codegen_model(cfg: dict) -> str:
    """Return the cloud model to use for code generation when enabled."""
    return (cfg.get("codegen_model") or _DEFAULT_CLOUD_CODEGEN_MODEL).strip()




def _apply_session_mode(cfg: dict, session_mode: str) -> None:
    normalized = _normalize_session_mode(session_mode)
    read_only_tools = {"read_file", "list_directory", "git_status", "git_diff"}
    disabled_tools = {str(name) for name in (cfg.get("disabled_tools") or [])}
    disabled_commands = {str(name).lower() for name in (cfg.get("disabled_commands") or [])}
    allowed_roots = list(cfg.get("allowed_roots") or [])

    # Load policy if configured
    policy_path = cfg.get("policy_path")
    policy = policy_module.load_policy(policy_path) if policy_path else policy_module.load_policy()

    if normalized in {"read-only", "plan"}:
        allowed_tools = read_only_tools - disabled_tools
        confirm_tool = None
        require_diff = False
        shell_confirm = None
    elif normalized == "auto":
        allowed_tools = set(filesystem._DEFAULT_TOOLS) - disabled_tools
        confirm_tool = None
        require_diff = False
        shell_confirm = None
    else:
        allowed_tools = set(filesystem._DEFAULT_TOOLS) - disabled_tools
        confirm_tool = _confirm_tool
        require_diff = cfg.get("require_diff_approval", True)
        shell_confirm = _confirm_shell
    allowed_commands = {
        command for command in shell_agent._DEFAULT_COMMANDS
        if command.lower() not in disabled_commands
    }

    filesystem.configure(
        workspace=cfg["workspace"],
        allowed_roots=allowed_roots,
        allowed_tools=allowed_tools,
        allowed_commands=allowed_commands,
        confirm_fn=confirm_tool,
        require_diff_approval=require_diff,
        policy=policy,
    )
    shell_agent.configure(
        workspace=cfg["workspace"],
        allowed_roots=allowed_roots,
        session_mode=normalized,
        allowed_commands=allowed_commands,
        stream_to_console=True,
        confirm_fn=shell_confirm,
        policy=policy,
    )


def _chat():
    global _LAST_SHELL_COMMAND
    _clear_terminal()
    show_banner()

    cfg = config.load()
    from app import remote as _remote
    _remote.check_alive(cfg, echo=lambda s: console.print(Text("  " + s, style="m.info")))  # E-067
    _kaggle_died_turns = None
    if cfg.pop("_remote_died", "") == "kaggle":  # D-062 B3 at start-up: report on the last session's records
        from app.core import handoff as _handoff
        _rec = _handoff.latest_record(pathlib.Path(cfg["workspace"]))
        _kaggle_died_turns = _handoff.turns_from_record(_rec) if _rec else []
    model = _startup_model(cfg)
    config.save_last_model(model)
    from app.core import store as _store
    _store.note_project(cfg["workspace"])  # the dashboard reads every folder Mitra ran in (D-041)
    codegen_model = _resolve_codegen_model(cfg)
    temperature = cfg.get("temperature", 0.2)
    session_mode = _normalize_session_mode(cfg.get("session_mode"))
    show_reasoning = bool(cfg.get("show_reasoning", False))
    from app.core import roles as _roles
    num_ctx = _roles.context_for(model, cfg)  # max context for the first days (D-052); mitra.toml / /context still win
    gpu_layers_cfg = cfg.get("gpu_layers", "auto")

    # Determine GPU placement for the chosen model
    _vram = config.get_gpu_vram_gib()
    _model_info = next(
        (m for m in config.get_local_model_inventory() if m.name == model), None
    )
    _placement = _model_info.placement if _model_info else config.get_model_placement(None, _vram)
    if cfg.get("remote"):
        _placement = "remote"
    num_gpu = config.get_num_gpu_for_placement(_placement, gpu_layers_cfg)

    loaded: list[str] = []  # shown on one line in the header

    _apply_session_mode(cfg, session_mode)

    # Build system prompt, appending project rules + memory context
    from app.core import harness as harness_mod
    from app.core.chat import CHAT_PROMPT

    harness = harness_mod.load()
    system_prompt = harness_mod.apply_prompt(CHAT_PROMPT, harness)  # learned rules (self-improvement, step 1)
    if cfg.get("rules"):
        system_prompt += f"\n\n## Project Rules (from MITRA.md)\n{cfg['rules']}"
        loaded.append("MITRA.md")

    project_instructions = cfg.get("project_instructions") or []
    instructions_prompt = _build_project_instructions_prompt(project_instructions)
    if instructions_prompt:
        system_prompt += f"\n\n{instructions_prompt}"
        count = len(project_instructions)
        loaded.append(f"{count} instruction file{'s' if count != 1 else ''}")

    available_skills = skills_registry.discover(cfg["workspace"], cfg.get("skill_dirs"))
    skills_prompt = _build_skills_prompt(available_skills)
    if skills_prompt:
        system_prompt += f"\n\n{skills_prompt}"
        count = len(available_skills)
        loaded.append(f"{count} skill{'s' if count != 1 else ''}")

    # (workspace plugins were removed with the old engine, M1 stage 2)

    ctx_text = memory.load_context(cfg["workspace"])
    if ctx_text:
        system_prompt += f"\n\n## Project Memory (from .mitra/context.md)\n{ctx_text}"
        loaded.append("project memory")

    startup_project_brief = _build_startup_project_brief(cfg["workspace"])
    if startup_project_brief:
        system_prompt += f"\n\n{startup_project_brief}"
        loaded.append("project brief")

    from app.core import resume as resume_mod  # D-065 P1: where we stopped, from the records (before this session)
    resume_brief = resume_mod.brief(pathlib.Path(cfg["workspace"]))
    if resume_brief:
        system_prompt += f"\n\n{resume_brief}\nFor 'where did we stop' questions answer from this; do not search."
        loaded.append("where we stopped")

    plan_text = memory.load_plan(cfg["workspace"])
    if plan_text:
        system_prompt += f"\n\n## Active Plan (from .mitra/plan.md)\n{plan_text}"
        loaded.append("plan")


    cloud_api_key = ""  # Mitra is local-only (D-025)
    local_llm = get_local_llm(model, temperature, base_url=cfg.get("ollama_local_base_url"),
                              num_ctx=num_ctx, num_gpu=num_gpu, reasoning=thinking_setting(cfg.get("thinking")))
    review_llm = codegen_llm = local_llm  # one model for everything (M1)

    # Compact before the model's context is full: at most 80% of num_ctx (D-033).
    auto_compact_threshold = config.compact_threshold(cfg, num_ctx)  # 80% of the context (E-046)
    from app.core.chat import ChatSession, Hooks, repair_history
    from app.core.cli import EventPrinter

    def _chat_stream(chunks, step=1):
        with ui.KeyWatcher() as keys:
            streamed = ui.stream_reply(console, chunks, show_reasoning=show_reasoning, stop=keys.stop,
                                       folded=ui_state.folded, label=f"Thinking · step {step}",
                                       thinking_line=False)
        typed_buffer.append(keys.take_typed())
        return streamed

    def _chat_show(name, args, out, ok):
        if name in ("run_command", "run_plan"):
            return  # shown by their own hooks
        if name == "run_tests":
            first = out.splitlines()[0] if out else ""
            console.print(ui.tool_line("Tests", ok=ok, detail=first))
            ui_state.folded.remember("Test output", out)
            return
        if name in ("write_file", "edit_file"):
            first, _, warning = out.partition("\n")
            if chat.mode == "approve" and ok:  # the card was just shown: one result line, no repeat
                console.print(Text("  ⎿  " + first, style="m.dim"))
            else:
                console.print(ui.tool_line("Write" if name == "write_file" else "Edit",
                                           str(args.get("path", "")), ok=ok, detail="" if ok else first))
            if warning.strip():
                console.print(Text("  " + warning.strip(), style="m.err"))
            return
        if name == "make_dir":
            console.print(ui.tool_line("Folder", str(args.get("path", "")), ok=ok, detail="" if ok else out))
            return
        console.print(ui.step_line({"list_files": "list_directory", "search": "search_text",
                                    "web_search": "search_web"}.get(name, name), args, out, ok))

    def _chat_confirm_write(rel, old, new):
        """New files as a card, edits as numbered hunks; the full text is behind ctrl+o (user feedback)."""
        view, hidden = ui.files.change_view(rel, old, new)
        console.print()
        console.print(view)
        if hidden:
            ui_state.folded.remember(f"{rel} (proposed)", new if old is None else "\n".join(
                difflib.unified_diff((old or "").splitlines(), new.splitlines(), lineterm="")))
        verb = "Create this file" if old is None else "Apply this edit"
        choice = ui.menu.choose(console, f"{verb}?", [("yes", "Yes"), ("all", "Yes to all for this request"),
                                                     ("no", "No, and tell Mitra why")], default="yes")
        if choice in ("yes", "all"):
            return choice
        try:
            reason = console.input("[m.accent]  why? [/m.accent]").strip()
        except (EOFError, KeyboardInterrupt):
            reason = ""
        return f"no: {reason}"

    def _chat_working(label):
        return console.status(f"[m.dim]{label}…[/m.dim]", spinner="dots", spinner_style="m.accent")

    def _chat_confirm(title, detail, question):
        choice = _choose_approval_option(title, f"{detail}\n\n{question}",
                                         [("approve", "Yes"), ("deny", "No")], fallback_default="approve")
        return choice == "approve"

    def _chat_shell(command):
        console.print(ui.shell_start(command))
        result = shell_agent.execute(command=command, cwd=None, console=console)
        console.print(ui.shell_done(result))
        ui_state.folded.remember(f"Output of {command}", result.output)
        return result.to_llm_summary(), result.ok or result.still_running  # E-041: running != failed

    def _chat_mcp_find(query):  # only the active role's MCP servers (routing)
        return mcp_registry.format_search(cfg["workspace"], mcp_registry.search_tools(
            cfg["workspace"], query, servers=chat.allowed_mcp))

    def _chat_mcp_call(server, tool, arguments):
        res = mcp_registry.call_tool(
            cfg["workspace"], server, tool, arguments,
            approve=lambda spec, t, a: _chat_confirm(f"MCP {server} / {t}",
                                                     json.dumps(mcp_registry.mask(a), indent=2)[:1500],
                                                     f"Call {server} / {t}?"))
        return res.text if res.ok else f"✗ {res.text}"

    typed_buffer: list[str] = []
    chat = ChatSession(
        workspace=cfg["workspace"],
        llm=local_llm,
        mode=session_mode,
        num_ctx=num_ctx,
        harness=harness,
        traces=bool(cfg.get("save_traces", True)),  # full model calls, the fine-tune data (D-041)
        hooks=Hooks(
            stream=_chat_stream,
            show=_chat_show,
            confirm=_chat_confirm,
            run_shell=_chat_shell,
            web_search=lambda q: web_agent.search_web.invoke({"query": q}),
            fetch_url=lambda u: web_agent.fetch_url.invoke({"url": u}),
            mcp_find=_chat_mcp_find,
            mcp_call=_chat_mcp_call,
            on_plan_event=EventPrinter(console),
            confirm_write=_chat_confirm_write,
            working=_chat_working,
        ),
    )

    hook_ctx = event_bus.HookContext(
        workspace=cfg["workspace"],
        session_mode=session_mode,
        metadata={"model": model},
    )
    event_bus.emit(event_bus.SessionStartEvent(
        workspace=cfg["workspace"],
        session_mode=session_mode,
        model=model,
        context=hook_ctx,
    ))

    # ── Header + prompt setup ─────────────────────────────────────────────────
    try:
        _mcp_names = [spec.name for spec in mcp_registry.discover(cfg["workspace"]) if spec.usable]
    except Exception:
        _mcp_names = []
    console.print()
    _roles_line, _learning_line, _dash_line = _header_extras(cfg, harness)
    console.print(ui.header.header(
        model=model,
        folder=_shorten_display(str(cfg["workspace"]), 60),
        context=num_ctx,
        placement=_placement,
        mcp_servers=_mcp_names,
        loaded=loaded,
        roles=_roles_line,
        learning=_learning_line,
        dashboard=_dash_line,
    ))
    _fit = _print_memory_fit(model, num_ctx, cfg.get("ollama_local_base_url") or "http://127.0.0.1:11434")
    if cfg.get("remote") == "kaggle":  # Kaggle's own count of your GPU hours (D-061)
        try:
            from app import kaggle as _kaggle
            console.print(Text("    " + _kaggle.quota_line(_kaggle.quota(_kaggle.client()))
                               + " · /kaggle stop when done", style="m.dim"))
        except Exception:
            pass
    try:  # machine state for the dashboard (item 0)
        _gpu = config.get_gpu_memory_info()
        chat.note_session(model=model, num_ctx=num_ctx, mode=session_mode,
                          fit=getattr(_fit, "verdict", None), need_ram_gb=getattr(_fit, "need_ram_gb", None),
                          ram_free_gb=getattr(_fit, "free_ram_gb", None),
                          vram_free_gb=_gpu.free_gib if _gpu else None,
                          remote=cfg.get("remote") or "")  # e.g. "kaggle": not this machine's energy (D-060)
    except Exception:
        pass
    console.print(ui.header.tips())
    current_task = "Ready"

    def _set_current_task(label: str) -> None:
        nonlocal current_task
        current_task = label or "Ready"

    ui_state = ui.UiState(mode=session_mode)

    def _print_folded() -> None:
        console.print()
        console.print(ui.tool_line(ui_state.folded.title or "Folded output"))
        console.print(ui.detail_block(ui_state.folded.text, max_lines=400))

    input_box = ui.InputBox(
        workspace=cfg["workspace"],
        commands=list(_COMMAND_HELP),
        state=ui_state,
        message=ui.prompt_message,
        toolbar=lambda: ui.framed_status(
            model=model if chat.role == "chat" else f"{chat.role} · {model}",
            mode=ui.mode_label(ui_state.mode),
            total_tokens=ctx_used,          # E-025: what is in the context now, not the sum of all calls
            context_limit=num_ctx,
            cwd=shell_agent.get_cwd(),
            background_tasks=shell_agent.count_background_tasks(only_running=True),
            notice=ui_state.current_notice(),
            **dict(zip(("backend", "backend_level"),
                       backend_mod.status_text(bsession.kind, model, num_ctx, health.s))),
        ),
        print_folded=_print_folded,
    )
    typed_ahead = ""
    session_changes: list[list[dict]] = []  # one journal per turn, for /undo all
    messages = [SystemMessage(content=system_prompt)]
    sess_in = sess_out = 0  # cumulative session token counts (work done)
    ctx_used = 0            # prompt tokens of the latest model call = how full the context is (E-025)

    from app.core import roles as roles_mod

    def _apply_role(role_name: str, *, model_override: str | None = None, ctx_override: int | None = None,
                    quiet: bool = False) -> None:
        """Swap model, context, tools, MCP servers and thinking for a role, live (D-049..D-052). The overrides are
        the laptop fallback model (D-062 B2); quiet = the caller prints its own one line."""
        nonlocal model, num_ctx, local_llm, review_llm, codegen_llm, auto_compact_threshold
        r = roles_mod.route(role_name, cfg)
        if model_override:
            r = {**r, "model": model_override, "num_ctx": ctx_override or r["num_ctx"]}
        think = {"on": True, "off": False}.get(r["thinking"] or "", thinking_setting(cfg.get("thinking")))
        swapped = r["model"] != model or r["num_ctx"] != num_ctx
        model, num_ctx = r["model"], r["num_ctx"]
        local_llm = get_local_llm(model, temperature, base_url=cfg.get("ollama_local_base_url"), num_ctx=num_ctx,
                                  num_gpu=num_gpu, reasoning=think)
        review_llm = codegen_llm = local_llm
        auto_compact_threshold = config.compact_threshold(cfg, num_ctx)
        chat.apply_route(r, llm=local_llm, num_ctx=num_ctx)
        if quiet:
            return
        console.print(Text("  ⇄ " + roles_mod.describe(r), style="m.tool"))
        if swapped:
            console.print(Text("    Ollama loads the model on the next message (one model at a time)", style="m.faint"))
            _print_memory_fit(model, num_ctx, cfg.get("ollama_local_base_url") or "http://127.0.0.1:11434")

    # ── Where the model runs: laptop or Kaggle (D-062, docs/BACKENDS.md) ─────────────────────────────────────────
    from app import backend as backend_mod
    from app import kaggle as kaggle_mod
    from app import remote as remote_mod
    from app import fit as fit_mod

    def _kaggle_quota():
        return kaggle_mod.quota(kaggle_mod.client())

    health = backend_mod.Health(quota=_kaggle_quota)
    bsession = backend_mod.Session(kind=backend_mod.REMOTE if cfg.get("remote") else backend_mod.LAPTOP)
    chat.backend_kind = bsession.kind
    health.start()
    last_test_summary = ""

    def _guard_context(new_ctx: int) -> None:
        """B4: a long chat moving to a smaller context is compacted first, so the next call fits."""
        nonlocal messages, ctx_used
        if ctx_used and ctx_used > 0.8 * new_ctx:
            console.print(ui.tool_line("Compacting", detail=f"the chat ({ctx_used:,} tokens) is too long for "
                                                            f"{new_ctx // 1024}K: summarising older turns first"))
            messages = _compact(local_llm, messages, system_prompt, workspace=cfg["workspace"], reason="backend",
                                total_tokens=ctx_used, rec=chat.rec)
            ctx_used = 0

    def _to_laptop(reason: str, *, report: bool = False) -> None:
        """B2 + B3: this machine's model that fits the free memory (quietly smaller), optionally the report."""
        remote_mod.unapply(cfg)
        r = roles_mod.route(chat.role, cfg)
        pick, ctx, note = backend_mod.laptop_choice(
            r["model"], roles_mod.context_for(r["model"], cfg), roles_mod.installed(),
            lambda m, c: fit_mod.check(m, c, base_url=cfg.get("ollama_local_base_url") or "http://127.0.0.1:11434",
                                       local=True).verdict,
            cfg.get("laptop_models"))
        _apply_role(chat.role, model_override=pick, ctx_override=ctx, quiet=True)
        bsession.kind, chat.backend_kind = backend_mod.LAPTOP, "laptop"
        console.print(Text(f"  💻 {reason} → laptop · {pick} {ctx // 1024}K" + (f" · {note}" if note else ""),
                           style="m.info"))
        _guard_context(ctx)
        if report:
            _kaggle_report(reason, note)

    def _to_remote(reason: str) -> None:
        remote_mod.apply(cfg)
        _apply_role(chat.role, quiet=True)
        bsession.kind, chat.backend_kind = backend_mod.REMOTE, "remote"
        console.print(Text(f"  ☁ {reason} → {cfg.get('remote') or 'remote'} · {model} {num_ctx // 1024}K",
                           style="m.tool"))

    def _kaggle_report(reason: str, note: str = "", turns=None, summarize: bool = True) -> None:
        """B3: facts from Mitra's records + a short summary by the laptop model; written, shown, then Mitra waits."""
        from app.core import handoff
        st = kaggle_mod.load_state()
        session_min = int((time.time() - st["started"]) / 60) if st.get("started") else None
        night = None
        try:
            from app.core import night as _night
            ns = _night.status(n=5)
            if ns:
                night = {"state": "running" if ns["running"] else "finished", "plan": pathlib.Path(ns["plan"]).name,
                         "detail": f"{ns['elapsed_min']} min of up to {ns['hours']} h"}
        except Exception:
            pass
        summary = ""
        if summarize and len(messages) > 1:
            console.print(Text("  writing the report with the laptop model (the first load takes a moment; "
                               "ctrl+c skips the summary) …", style="m.faint"))
            try:
                summary = handoff.summarize(local_llm, messages)
            except KeyboardInterrupt:
                summary = ""
        text = handoff.build(reason=reason, workspace=pathlib.Path(cfg["workspace"]),
                             turns=chat.turn_log if turns is None else turns,
                             laptop=f"{model} at {num_ctx // 1024}K" + (f" ({note})" if note else ""),
                             summary=summary, last_tests=last_test_summary, night=night,
                             kaggle={"session_min": session_min, "left_h": health.s.hours_left})
        path = handoff.write(pathlib.Path(cfg["workspace"]), text)
        console.print(Markdown(text))
        console.print(Text(f"  report saved: {path}", style="m.faint"))

    def _kaggle_ended(reason: str) -> None:
        """Kaggle is gone: its address is useless now (a new one every session): laptop, report, stop (B3)."""
        if (remote_mod.active() or {}).get("name") == "kaggle":
            remote_mod.clear()
        st = kaggle_mod.load_state()
        if st:
            kaggle_mod.save_state({**st, "ended": time.time()})
        _to_laptop(reason, report=True)

    def _start_kaggle_background() -> None:
        """B5 a: start Kaggle while you keep working here; the next turn after it is ready moves write work there."""
        import threading as _threading
        health.starting("uploading the notebook")

        def run():
            try:
                kaggle_mod.start(model, 262_144,
                                 echo=lambda s: health.starting(str(s).strip(" ·✓⏳☁").strip()[:60]))
                health.check()
            except Exception as exc:  # noqa: BLE001 - reported before the next turn
                health.s.state, health.s.stage = "none", ""
                bsession.notes.append(f"Kaggle did not start: {exc}")

        _threading.Thread(target=run, daemon=True, name="mitra-kaggle-start").start()
        console.print(Text("  ☁ starting Kaggle in the background (4-8 min): keep working; the status line shows "
                           "its progress and write work moves there when it is ready", style="m.tool"))

    def _has_kaggle_key() -> bool:
        return kaggle_mod.has_key()

    def _say_line(text: str, style: str = "m.tool") -> None:
        console.print(Text("  " + text, style=style))

    def _ask_use(user: str = "", left_h=None) -> str | None:
        """Case 2 (D-064): Kaggle works here; does the user want it, and when? Saved; None = later."""
        who = f" for {user}" if user else ""
        hours = f" · {left_h:.1f} h left this week" if left_h is not None else ""
        answer = ui.menu.choose(console, f"Kaggle is set up{who}{hours}. Use its GPU with Mitra (3-4x faster, 256K)?",
                                [("when-needed", "Yes, when I need it (starts on your first write work; no hours "
                                                 "used before)"),
                                 ("now", "Yes, start it now, and at every Mitra start"),
                                 ("later", "Ask me later"),
                                 ("never", "No, this machine only")], default="when-needed")
        if answer in backend_mod.USE_VALUES:
            backend_mod.save_prefs(kaggle_use=answer, onboarded=True)
            if answer != "never":
                _say_line(f"☁ Kaggle {backend_mod.USE_TEXT[answer]} · `/kaggle use now|when-needed|never` "
                          "changes it", "m.faint")
            return answer
        backend_mod.save_prefs(later_day=time.strftime("%Y-%m-%d"), onboarded=True)
        return None

    def _guide_setup() -> bool:
        """Case 1: no key yet: open Kaggle's settings page, take the pasted token, check it."""
        import webbrowser
        try:
            webbrowser.open("https://www.kaggle.com/settings")
        except Exception:
            pass
        console.print(Text("  On kaggle.com → Settings (opened in your browser; sign up free if needed):\n"
                           "    1. Phone verification: verify (Kaggle needs it for GPUs)\n"
                           "    2. API → Generate New Token, then copy it", style="m.text"))
        try:
            token = console.input("[m.accent]  paste the token here (enter = later) ›[/m.accent] ", password=True).strip()
        except (EOFError, KeyboardInterrupt):
            token = ""
        if token and kaggle_mod.setup(token, echo=lambda s: _say_line(str(s))):
            return True
        _say_line("later: `/kaggle setup <token>`", "m.faint")
        return False

    def _kaggle_at_start() -> None:
        """D-064: at every start, one check (key, still works, phone verified, hours left) and one of five cases."""
        use = backend_mod.kaggle_use()
        if bsession.kind == backend_mod.REMOTE or use == "never":   # case 5 (running) or the user said no
            return
        interactive = sys.stdin.isatty()
        if not _has_kaggle_key():                                    # case 1: no key
            if use is None and interactive and not backend_mod.asked_later_today():
                answer = ui.menu.choose(console, "Use a free Kaggle GPU with Mitra? About 30 h a week, 3-4x faster, "
                                                 "256K context (2 minutes to connect)",
                                        [("yes", "Yes, guide me"), ("later", "Later"),
                                         ("never", "No, this machine only")], default="yes")
                if answer == "never":
                    backend_mod.save_prefs(kaggle_use="never", onboarded=True)
                elif answer == "yes" and _guide_setup():
                    _kaggle_at_start()  # now case 2: ask when to use it
                else:
                    backend_mod.save_prefs(later_day=time.strftime("%Y-%m-%d"), onboarded=True)
            elif use in ("now", "when-needed"):
                _say_line("☁ Kaggle: no key on this machine any more · `/kaggle setup <token>`", "m.info")
            return
        console.print(Text("  checking Kaggle …", style="m.faint"))
        r = kaggle_mod.readiness()
        if r["problem"]:                                             # case 4: something to fix, with the fix
            if use is not None or not backend_mod.asked_later_today():
                _say_line("☁ " + r["problem"], "m.info")
            return
        if use is None:                                              # case 2: works, never asked
            if not interactive or backend_mod.asked_later_today():
                return
            use = _ask_use(r["user"], r["left_h"])
            if use is None or use == "never":
                return
        if use == "now":                                             # case 3: said yes
            _start_kaggle_background()
        else:
            _say_line(f"☁ Kaggle ready · {r['left_h']:.1f} h left · starts on your first write work "
                      "(`/kaggle start` now)", "m.faint")

    def _maybe_offer_kaggle() -> None:
        """Write work and Kaggle is not running: 'when-needed' starts it in the background without asking; not
        decided yet: ask once per session; 'never': nothing."""
        if bsession.asked_start or bsession.no_kaggle_this_session or health.s.state == "starting":
            return
        use = backend_mod.kaggle_use()
        if use == "never" or not _has_kaggle_key():
            return
        bsession.asked_start = True
        if use in ("now", "when-needed"):
            _start_kaggle_background()
            return
        answer = ui.menu.choose(console, "Write work runs 3-4x faster on your Kaggle GPU. Start it?",
                                [("bg", "Yes, in the background (4-8 min; keep working here, I switch when ready)"),
                                 ("no", "No, this machine for this session")], default="bg")
        if answer == "bg":
            _start_kaggle_background()
        else:
            bsession.no_kaggle_this_session = True

    if _kaggle_died_turns is not None:
        _kaggle_report("the Kaggle GPU ended while Mitra was closed", turns=_kaggle_died_turns, summarize=False)
    _kaggle_at_start()

    while True:
        _set_current_task("Ready")
        ui_state.mode = session_mode
        ui.notify.ready(console)
        try:
            user_input = input_box.prompt(default=typed_ahead)
        except (EOFError, KeyboardInterrupt):
            user_input = "exit"
        typed_ahead = ""
        if ui_state.mode != session_mode:   # shift+tab while typing
            session_mode = ui_state.mode
            _apply_session_mode(cfg, session_mode)

        if user_input.strip() in ["/exit", "exit", "quit"]:
            event_bus.emit(event_bus.SessionEndEvent(
                workspace=cfg["workspace"],
                session_mode=session_mode,
                total_tokens=sess_in + sess_out,
                message_count=len(messages),
                context=hook_ctx,
            ))
            _rebuild_dashboard(quiet=True)  # the page always shows every session so far (D-041)
            console.print(Text("  Bye.", style="m.dim"))
            break

        if not user_input.strip():
            continue

        if _is_bang_command(user_input):
            bang_command = _extract_bang_command(user_input)
            _set_current_task(f"Running {bang_command}")
            _cmd_run(bang_command, folded=ui_state.folded)
            continue

        # ── Slash commands ────────────────────────────────────────────────────
        user_input = _strip_sentence_dot(user_input)
        cmd = user_input.strip().lower()

        if cmd in ("/help", "help"):
            _print_help()
            continue

        if cmd in ("/clear", "clear", "/reset"):
            messages = [SystemMessage(content=system_prompt)]
            console.print("[dim]Session reset.[/dim]")
            continue

        if cmd in ("/init", "mitra init"):
            _run_init()
            continue

        if cmd.startswith("/skills"):
            ai_reply = _build_skills_reply(available_skills, user_input, workspace=cfg["workspace"])
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd in ("/good", "/bad") or cmd.startswith(("/good ", "/bad ")):  # your verdict on the last turn (A4)
            verdict = "good" if cmd.startswith("/good") else "bad"
            note = user_input.strip()[len("/" + verdict):].strip()
            console.print(Text("  " + chat.feedback(verdict, note), style="m.tool"))
            continue

        if cmd.startswith("/context "):  # /context 128k|256k|auto: speed vs room, kept per model (E-046)
            if cfg.get("num_ctx"):
                _say(f"`num_ctx = {cfg['num_ctx']}` is set in mitra.toml; change it there (it wins over /context).")
                continue
            new_ctx, err = roles_mod.choose_context(model, user_input.strip()[len("/context "):], cfg)
            if err:
                _say(err)
                continue
            num_ctx = new_ctx
            auto_compact_threshold = config.compact_threshold(cfg, num_ctx)
            local_llm = get_local_llm(model, temperature, base_url=cfg.get("ollama_local_base_url"), num_ctx=num_ctx,
                                      num_gpu=num_gpu, reasoning=thinking_setting(cfg.get("thinking")))
            review_llm = codegen_llm = local_llm
            chat.llm, chat.num_ctx = local_llm, num_ctx
            console.print(Text(f"  context: {num_ctx // 1024}K for {model} (kept for next time) · compacts at "
                               f"{auto_compact_threshold:,} tokens · Ollama reloads the model on the next message",
                               style="m.tool"))
            _print_memory_fit(model, num_ctx, cfg.get("ollama_local_base_url") or "http://127.0.0.1:11434")
            continue

        if cmd == "/context":
            ai_reply = _build_context_reply(ctx_used, auto_compact_threshold, num_ctx)
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/status":
            ai_reply = _build_status_reply(
                cfg["workspace"],
                model,
                codegen_model,
                cloud_codegen_enabled=bool(cloud_api_key),
                session_mode=session_mode,
                show_reasoning=show_reasoning,
                total_tokens=ctx_used,
                auto_compact_threshold=auto_compact_threshold,
                num_ctx=num_ctx,
            )
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/mcp" or cmd.startswith("/mcp "):
            ai_reply = _build_mcp_reply(cfg["workspace"], cfg, user_input.strip()[len("/mcp"):].strip())
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd.startswith("/test"):
            target = user_input.strip()[5:].strip() or "pytest"
            ai_reply = _cmd_test(target, cfg["workspace"])
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd.startswith("/logs"):
            ai_reply = _cmd_logs(user_input, cfg["workspace"])
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/mode" or cmd.startswith("/mode "):  # not /model (E-047)
            requested = user_input.strip()[5:].strip()
            if not requested:
                ai_reply = _build_mode_reply(session_mode)
            else:
                normalized = _normalize_session_mode(requested)
                if not _is_known_mode(requested):
                    ai_reply = f"Unknown mode: `{requested}`. Modes: `ask`, `auto-edit`, `plan` (shift+tab cycles them)."
                else:
                    session_mode = normalized
                    _apply_session_mode(cfg, session_mode)
                    ai_reply = _build_mode_reply(session_mode)
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/think" or cmd.startswith("/think "):
            requested = user_input.strip()[len("/think"):].strip().lower()
            if not requested:
                ai_reply = _build_reasoning_reply(show_reasoning)
            elif requested in {"on", "show", "true"}:
                show_reasoning = True
                ai_reply = _build_reasoning_reply(show_reasoning)
            elif requested in {"off", "hide", "false"}:
                show_reasoning = False
                ai_reply = _build_reasoning_reply(show_reasoning)
            else:
                ai_reply = "Usage: `/think on` or `/think off`."
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/role" or cmd == "/model roles":  # which model, tools and MCP servers each role uses
            lines = ["| role | model | context | from | tools | MCP | thinking |", "|---|---|---|---|---|---|---|"]
            have = roles_mod.installed()
            for rn in roles_mod.ROLES:
                r = roles_mod.route(rn, cfg, have)
                mark = " ◀ now" if rn == chat.role else ""
                lines.append(f"| {rn}{mark} | `{r['model']}` | {r['num_ctx'] // 1024}K | {r['source']} | "
                             f"{'all' if r['tools'] is None else len(r['tools'])} | "
                             f"{'all' if r['mcp'] is None else ', '.join(r['mcp']) or '-'} | {r['thinking'] or 'as set'} |")
            lines.append("\n`/role <name>` switches role (model, tools, MCP at once) · `/model role <role> <model|default>` "
                         "sets a role's model · `/model use <model>` switches the chat model now")
            _say("\n".join(lines))
            continue

        if cmd.startswith("/role "):
            role_name = cmd.split(maxsplit=1)[1].strip()
            if role_name not in roles_mod.ROLES:
                _say(f"Unknown role `{role_name}`. Roles: {', '.join(roles_mod.ROLES)}.")
                continue
            _apply_role(role_name)
            continue

        if cmd.startswith("/model role "):
            parts = user_input.strip().split()
            if len(parts) < 4 or parts[2].lower() not in roles_mod.ROLES:
                _say(f"Usage: `/model role <role> <model|default>`. Roles: {', '.join(roles_mod.ROLES)}.")
                continue
            role_name, target = parts[2].lower(), parts[3]
            if target != "default" and target not in roles_mod.installed():
                _say(f"`{target}` is not one of Mitra's installed models. `/model list` shows them.")
                continue
            roles_mod.save_choice(role_name, target)
            console.print(Text(f"  {role_name} → {target} (kept for next time)", style="m.tool"))
            if role_name == chat.role:
                _apply_role(role_name)
            continue

        if cmd.startswith(("/model use ", "/model switch ", "/model set ")):  # live, no restart (was: restart)
            target = user_input.strip().split(maxsplit=2)[2].strip()
            if target not in roles_mod.installed():
                _say(f"`{target}` is not one of Mitra's installed models. `/model list` shows them.")
                continue
            roles_mod.use_for_chat(target)  # beats mitra.toml local_model and an older chat choice (E-054)
            toml_chat = (cfg.get("roles") or {}).get("chat") if isinstance(cfg.get("roles"), dict) else None
            if toml_chat and toml_chat != target:
                _say(f"mitra.toml sets `[roles] chat = \"{toml_chat}\"`, which wins over `/model use`: change it there.")
            _apply_role("chat")
            continue

        if cmd.startswith("/model"):
            ai_reply = _handle_model_command(
                user_input,
                model,
                codegen_model,
                cloud_codegen_enabled=bool(cloud_api_key),
            )
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/resume":
            _set_current_task("Resuming session")
            _print_progress_message("Resuming the current session", "Loading the saved session summary, plan, and recent activity.")
            ai_reply = _cmd_resume(cfg["workspace"])
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/diff":
            ai_reply = _build_diff_reply(cfg["workspace"])
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd.startswith("/review"):
            review_target = _parse_review_target(user_input)
            detail = "Checking the staged git diff and status." if review_target == "staged" else "Checking the current git diff or last Mitra change set."
            _print_progress_message("Reviewing current changes", detail)
            ai_reply = _cmd_review(cfg["workspace"], review_llm, target=review_target)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd in ("/undo", "/undo all"):
            if cmd == "/undo all":
                entries = [e for journal in session_changes for e in journal]
                if entries:
                    memory.record_last_change_set(cfg["workspace"], {"entries": entries})
                session_changes.clear()
            elif session_changes:
                session_changes.pop()
            ai_reply = filesystem.undo_last_change_set(cfg["workspace"])
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd.startswith("/commit"):
            rest = user_input.strip()[7:].strip()
            generate = "--generate" in rest or "-g" in rest
            if generate:
                rest = rest.replace("--generate", "").replace("-g", "").strip()
            message = rest if rest and not generate else None
            ai_reply = _cmd_commit(cfg["workspace"], local_llm, message=message, staged=True, generate=generate)
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd.startswith("/fix"):
            fix_command = _extract_fix_command(user_input, last_command=_LAST_SHELL_COMMAND)
            ai_reply = _cmd_fix(fix_command or "", cfg["workspace"], codegen_llm)
            _say(ai_reply)
            memory.append_activity(cfg["workspace"], user_input, ai_reply)
            memory.update_context(cfg["workspace"], user_input)
            continue

        if cmd == "/compact":
            messages = _compact(
                local_llm,
                messages,
                system_prompt,
                workspace=cfg["workspace"],
                reason="manual",
                total_tokens=ctx_used,
                rec=chat.rec,
            )
            sess_in = sess_out = 0
            ctx_used = 0
            continue

        if cmd == "/report":
            import webbrowser

            from app.core import server as dash_server
            if dash_server.running():  # the live page (mitra dashboard) rebuilds itself on Refresh
                console.print(Text(f"  dashboard: {dash_server.URL}", style="m.faint"))
                webbrowser.open(dash_server.URL)
                continue
            out = _rebuild_dashboard()
            if out:
                webbrowser.open(out.as_uri())
                console.print(Text("  tip: `mitra dashboard` in another terminal serves it on localhost", style="m.faint"))
            continue

        if cmd == "/doctor":
            from app.doctor import ollama_report
            ollama_url = cfg.get("ollama_local_base_url") or "http://127.0.0.1:11434"
            from app import fit as fit_mod
            ai_reply = "\n\n".join([
                _build_resources_reply(),
                "## Memory fit\n\n" + fit_mod.markdown(fit_mod.check(model, num_ctx, base_url=ollama_url)),
                "## Run data\n\n- **Central store (never deleted, back it up yourself):** " + _store.size_text(),
                "## Ollama\n\n" + ollama_report(model, num_ctx, base_url=ollama_url),
                _build_permissions_reply(cfg, session_mode),
                "## MCP\n\n" + mcp_registry.summarize(mcp_registry.discover(cfg["workspace"])),
            ])
            _say(ai_reply)
            continue

        if cmd == "/kaggle" or cmd.startswith("/kaggle "):  # Kaggle GPU from the chat, switched live (D-061)
            from app import kaggle as kaggle_mod
            from app import remote as remote_mod
            sub = (user_input.strip().split() + ["status"])[1].lower()
            try:
                if sub == "start":
                    console.print(Text("  starting a Kaggle GPU (4-8 min) · ctrl+c stops waiting, not the run",
                                       style="m.dim"))
                    kaggle_mod.start(model, 262_144,
                                     echo=lambda s: console.print(Text(str(s), style="m.tool")))
                    health.check()
                    _want = backend_mod.route(session_mode, chat.role)
                    if _want == backend_mod.REMOTE:
                        _to_remote("Kaggle is ready")  # this chat now talks to Kaggle at its context
                    else:
                        console.print(Text(f"  ☁ Kaggle is ready; {backend_mod.why(_want, session_mode, chat.role)}"
                                           " until you leave it", style="m.tool"))
                elif sub == "stop":
                    kaggle_mod.stop(echo=lambda s: console.print(Text(str(s), style="m.tool")))
                    health.check()
                    if bsession.kind == backend_mod.REMOTE:
                        _to_laptop("Kaggle stopped")  # back on this machine
                elif sub == "use":  # D-064: when Mitra uses Kaggle
                    value = (user_input.strip().split() + ["", "", ""])[2].lower()
                    if value not in backend_mod.USE_VALUES:
                        _say("`/kaggle use now` (start at every Mitra start) · `/kaggle use when-needed` (on your "
                             "first write work) · `/kaggle use never` (this machine only)")
                    else:
                        backend_mod.save_prefs(kaggle_use=value, onboarded=True)
                        console.print(Text(f"  ☁ Kaggle {backend_mod.USE_TEXT[value]}", style="m.tool"))
                        if value == "now" and health.s.state not in ("up", "starting") and _has_kaggle_key():
                            _start_kaggle_background()
                elif sub == "setup":
                    _guide_setup()
                else:
                    use = backend_mod.kaggle_use()
                    console.print(Text(f"  setting: {use or 'not decided yet'} · "
                                       f"{backend_mod.USE_TEXT.get(use, 'asked at the next start')} · "
                                       "`/kaggle use now|when-needed|never`", style="m.tool"))
                    kaggle_mod.status(echo=lambda s: console.print(Text("  " + str(s), style="m.tool")))
            except kaggle_mod.KaggleError as exc:
                console.print(Text(f"  ✗ {exc}", style="m.err"))
            except KeyboardInterrupt:
                console.print(Text("  stopped waiting; the Kaggle run goes on: `/kaggle status`", style="m.info"))
            continue

        if cmd == "/free":  # make RAM room for the model: tick programs, Mitra closes them (I-21)
            _cmd_free(model, num_ctx, cfg.get("ollama_local_base_url") or "http://127.0.0.1:11434")
            continue

        if cmd == "/run" or cmd.startswith("/run "):
            parts = user_input.strip().split()
            plan_file = parts[1] if len(parts) > 1 else "plan.md"
            hours = parts[2] if len(parts) > 2 else "4"
            plan_path = (pathlib.Path(cfg["workspace"]) / plan_file.strip('"')).resolve()  # absolute paths work too
            if not plan_path.is_file():
                _say(f"No plan file `{plan_file}` here. Usage: `/run [plan.md] [hours]` (a plan with 'Done when' tests).")
                continue
            try:
                float(hours)
            except ValueError:
                _say("Usage: `/run [plan.md] [hours]`, e.g. `/run plan.md 4`.")
                continue
            project = plan_path.parent  # the project is the plan's folder, so /run works from any folder
            from app.core import night as night_mod
            n_tasks, problem = night_mod.check_plan(plan_path)
            if problem:
                _say(f"The plan cannot run: {problem}\n\n`/plan template` writes a runnable example; "
                     "`/plan check` checks a plan.")
                continue
            try:  # a branch + one commit per task needs a repo with at least one commit
                has_commit = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=str(project),
                                            capture_output=True, timeout=15).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                has_commit = False
            if not has_commit:
                console.print(Text("  note: this folder's git has no commit yet (or no git): tasks will not get their own "
                                   "commits. First run e.g. `! git init` then `! git add -A` and `! git commit -m start`.",
                                   style="m.info"))
            info = night_mod.launch(plan_path, project, float(hours), model)
            chat.night_started(plan_path, info["started"])  # /good /bad judge it; its edits are not yours (E-052, E-057)
            console.print(Text(f"  ⏾ night run started: {plan_path.name} ({n_tasks} tasks) in {project} · {model} · "
                               f"up to {hours} h", style="m.tool"))
            import time as _t
            _t.sleep(6)  # an error in the first seconds is shown here, not lost in a closing window
            if info["proc"].poll() is not None:
                st = night_mod.status(n=40)
                if st and st["report"]:  # it ran, just fast (e.g. every task skipped): show what happened, not an error
                    console.print(Text("  ⏾ the night run finished within seconds:", style="m.info"))
                    console.print(Text(st["tail"] or "", style="m.dim"))
                    console.print(Markdown(st["report"]))
                else:
                    console.print(Text("  ✗ the night run stopped right away:", style="m.err"))
                    console.print(Text(night_mod.tail(pathlib.Path(info["console_log"]), 25) or "(no output)",
                                       style="m.dim"))
            else:
                console.print(Text("    showing it live here · ctrl+c stops watching (the night keeps going, also if you "
                                   "close Mitra) · `/night` shows it again · don't chat meanwhile", style="m.faint"))
                _follow_night()
            continue

        if cmd in ("/plan", "/plan help") or cmd.startswith(("/plan template", "/plan check")):  # runnable plans (D-055)
            from app.core import plans as plans_mod
            parts = user_input.strip().split()
            sub = parts[1].lower() if len(parts) > 1 else "help"
            target = pathlib.Path(cfg["workspace"]) / (parts[2] if len(parts) > 2 else "plan.md")
            if sub == "template":
                if target.exists():
                    _say(f"`{target.name}` already exists here; `/plan check` checks it.")
                else:
                    target.write_text(plans_mod.TEMPLATE, encoding="utf-8")
                    _say(f"Wrote the plan template to `{target}`. Fill it in (or ask Mitra: \"fill plan.md for <idea>\"), "
                         "then `/plan check` and `/run plan.md`.")
            elif sub == "check":
                if not target.is_file():
                    _say(f"No `{target.name}` here. `/plan template` writes one.")
                else:
                    n, problem = plans_mod.check_text(target.read_text(encoding="utf-8"), target.resolve().parent.name)
                    _say(f"✗ `{target.name}` cannot run: {problem}" if problem
                         else f"✓ `{target.name}` is runnable with `/run {target.name}` ({n} tasks).")
            else:
                _say("`/plan template` writes a runnable plan template here · `/plan check [file]` checks a plan · "
                     "`/run [plan] [hours]` builds it (Mitra writing whole plans itself comes with the planner).")
            continue

        if cmd == "/night":  # the latest night run: live while it runs, then the report
            from app.core import night as night_mod
            st = night_mod.status()
            if st and st["running"]:
                console.print(Text(f"  ⏾ night running · {st['elapsed_min']} min of up to {st['hours']} h · "
                                   "live below · ctrl+c stops watching", style="m.tool"))
                _follow_night()
                continue
            if not st:
                _say("No night run yet. Start one with `/run <plan.md> [hours]`.")
                continue
            state = "running" if st["running"] else "finished"
            lines = [f"**Night:** {state} · {pathlib.Path(st['plan']).name} in `{st['project']}` · {st['model']} · "
                     f"{st['elapsed_min']} min of up to {st['hours']} h"]
            if st["tail"]:
                lines += ["", "Latest lines:", "```", st["tail"], "```"]
            if st["report"] and not st["running"]:
                lines += ["", st["report"]]
            elif not st["running"] and not st["report"]:
                lines += ["", f"No report was written: see `{st['console_log']}`."]
            _say("\n".join(lines))
            continue

        if user_input.strip().startswith("/"):
            unknown = user_input.strip().split()[0]
            _say(f"Unknown command `{unknown}`. Type `/help` for the list.")
            continue

        # ── Where this turn runs: laptop or Kaggle (D-062) ─────────────────────────
        for _note in bsession.notes:
            console.print(Text("  ✗ " + _note, style="m.err"))
        bsession.notes.clear()
        _hstate = health.check().state if (remote_mod.active() or bsession.kind == backend_mod.REMOTE) else "none"
        if bsession.kind == backend_mod.REMOTE and _hstate != "up":
            _kaggle_ended("the Kaggle GPU stopped answering (30 min unused, its time limit, or stopped on Kaggle)")
            typed_ahead = user_input
            console.print(Text("  your message was not sent: it is back in the input box (enter sends it on the "
                               "laptop)", style="m.faint"))
            continue
        if _hstate == "up":
            _want = backend_mod.route(session_mode, chat.role)
            if _want != bsession.kind:
                (_to_remote if _want == backend_mod.REMOTE else _to_laptop)(
                    backend_mod.why(_want, session_mode, chat.role))
        elif backend_mod.route(session_mode, chat.role) == backend_mod.REMOTE:
            _maybe_offer_kaggle()

        messages.append(HumanMessage(content=user_input))

        console.print()
        turn_started = time.monotonic()
        ui.notify.working(console)

        try:
            # ── One turn of the core loop (M1 stage 2) ────────────────────────
            turn_in = turn_out = 0
            chat.mode = session_mode
            typed_buffer.clear()
            turn = chat.turn(messages)
            if chat.noticed:  # your edits since the last turn: recorded as corrections (self-improvement)
                console.print(Text(f"  ✎ noticed your change to {', '.join(chat.noticed[:3])}"
                                   f"{' …' if len(chat.noticed) > 3 else ''}: recorded as a correction of the turn before",
                                   style="m.faint"))
                chat.noticed.clear()
            typed_ahead += "".join(typed_buffer)
            turn_in, turn_out = turn.tokens_in, turn.tokens_out
            ctx_used = turn.ctx_used or ctx_used
            ai_reply = turn.text.strip()
            if turn.journal:
                memory.record_last_change_set(cfg["workspace"], {"entries": turn.journal})
                session_changes.append(list(turn.journal))
            if turn.stopped and turn.stop_reason:
                console.print(ui.tool_line("Stopped", ok=False, detail=turn.stop_reason))
            elif not ai_reply:
                console.print(ui.tool_line("Empty reply", ok=False, detail="the model wrote no answer. Try again."))

            # ── Token bar ─────────────────────────────────────────────────────
            sess_in += turn_in; sess_out += turn_out
            if turn_in or turn_out:
                console.print(ui.turn_summary(
                    seconds=time.monotonic() - turn_started, steps=turn.steps,
                    files=len({e["path"] for e in turn.journal}), tests_run=turn.tests_run,
                    last_test_ok=turn.last_test_ok, tokens_in=turn_in, tokens_out=turn_out))
            ui.notify.done(console, time.monotonic() - turn_started)
            last_test_summary = turn.last_test_summary or last_test_summary
            if turn.remote_gone:  # D-062 B3: the remote stopped in the middle of the turn
                _kaggle_ended("the Kaggle GPU stopped answering in the middle of the turn")
                continue

            # ── Auto-compact ──────────────────────────────────────────────────
            if ctx_used >= auto_compact_threshold:  # E-025: compare the real context size
                console.print(ui.tool_line("Compacting", detail="the context is 80% full; summarising older turns"))
                tokens_before = ctx_used
                msg_count_before = len(messages)
                messages = _compact(
                    local_llm,
                    messages,
                    system_prompt,
                    workspace=cfg["workspace"],
                    reason="auto",
                    total_tokens=ctx_used,
                    rec=chat.rec,
                )
                tokens_after = 0
                msg_count_after = len(messages)
                event_bus.emit(event_bus.CompactCompleteEvent(
                    workspace=cfg["workspace"],
                    reason="auto",
                    tokens_before=tokens_before,
                    tokens_after=tokens_after,
                    messages_removed=msg_count_before - msg_count_after,
                    context=hook_ctx,
                ))
                sess_in = sess_out = 0
                ctx_used = 0

            # ── Persist to memory ─────────────────────────────────────────
            if ai_reply:
                memory.append_activity(cfg["workspace"], user_input, ai_reply)
                memory.update_context(cfg["workspace"], user_input)

        except KeyboardInterrupt:
            _set_current_task("Ready")
            repair_history(messages)
            console.print(Text("\n  Interrupted.", style="m.dim"))
        except Exception as e:
            _set_current_task("Ready")
            repair_history(messages)
            _log_error(cfg["workspace"], e)
            try:  # crashes reach the store and the dashboard too (item 0)
                import traceback as _tb
                chat.rec.write("crash", turn=chat.turn_no, error=f"{type(e).__name__}: {e}"[:500],
                               trace="".join(_tb.format_exception(e)[-8:])[-3000:])
            except Exception:
                pass
            console.print(ui.tool_line("Error", ok=False,
                                       detail=f"{_friendly_error(e)} (full trace in .mitra/errors.log)"))


# ── Guided Builder (/create) ──────────────────────────────────────────────────


def _amend_command(original: str) -> str | None:
    """Let the user edit the command inline before running it.

    Pre-fills the prompt with the original command so the user can adjust it.
    Returns the edited command, or None if the user cancels (Ctrl+C / empty submit).
    """
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.history import InMemoryHistory

    console.print(
        "\n  [m.tool]Amend command[/m.tool] — edit below, then press Enter to run. Ctrl+C to cancel.\n"
    )
    history = InMemoryHistory()
    history.append_string(original)
    try:
        amended = pt_prompt("  $ ", default=original, history=history).strip()
    except (KeyboardInterrupt, EOFError):
        _print_approval_result("Cancelled", approved=False)
        return None
    if not amended:
        _print_approval_result("Cancelled (empty command)", approved=False)
        return None
    if amended != original:
        _print_approval_result(f"Amended to: {amended}", approved=True)
    else:
        _print_approval_result("Approved (unchanged)", approved=True)
    return amended


def _confirm_shell(command: str, cwd: str) -> str | None:
    """Ask the user before the shell agent runs any command.

    Returns the (possibly amended) command string to run, or None to deny.
    """
    workspace = shell_agent._config.root_workspace or cwd
    command_name = _shell_command_name(command)
    # Inline code (python -c, node -e, ...) is never covered by "trusted": the program name says nothing about
    # what the code does (2026-11-06: `python -c "os.makedirs(...)"` ran without asking).
    if memory.is_shell_command_trusted(workspace, cwd, command_name) and not shell_agent.runs_inline_code(command):
        _print_approval_result(f"Trusted `{command_name}` in {cwd}", approved=True)
        return command

    choice = _choose_approval_option(
        "Run shell command",
        f"{command}\nin {cwd}\n\nRun this command?",
        [
            ("approve", "Yes"),
            ("trust", f"Yes, and don't ask again for `{command_name}` in this directory"),
            ("amend", "Tab to amend — edit the command before running"),
            ("deny", "No, and cancel this command"),
        ],
        fallback_default="approve",
    )
    if choice == "trust":
        memory.trust_shell_command(workspace, cwd, command_name)
        _print_approval_result(f"Approved and trusted `{command_name}` in {cwd}", approved=True)
        return command
    if choice == "amend":
        return _amend_command(command)
    approved = choice == "approve"
    if not approved:
        _print_approval_result("Skipped", approved=False)
    return command if approved else None


def _cmd_run(command: str, workspace: str | None = None, *, folded=None) -> None:
    """`! <command>`: run a command the user typed, in their shell, inside the workspace."""
    if not command:
        console.print("[dim]Usage: [m.info]! <command>[/m.info]  e.g. ! pytest -q[/dim]")
        return
    global _LAST_SHELL_COMMAND
    _LAST_SHELL_COMMAND = command
    console.print(ui.shell_start(command))
    result = shell_agent.execute(command=command, cwd=workspace, console=console, typed_by_user=True)
    console.print(ui.shell_done(result))
    if folded is not None:
        folded.remember(f"Output of {command}", result.output)


def _extract_fix_command(raw: str, *, last_command: str | None = None) -> str | None:
    target = raw.strip()[4:].strip()
    if not target:
        return last_command
    if target.lower().startswith("/run "):
        return target[5:].strip() or last_command
    return _extract_command(target).strip() or last_command


def _build_fix_usage(last_command: str | None = None) -> str:
    example = last_command or "pytest"
    return (
        "Usage: `/fix <failing command>`\n\n"
        f"Example: `/fix {example}`\n\n"
        "If you already ran a command in this session, `/fix` without arguments will reuse it."
    )


def _cmd_fix(command: str, workspace: str, codegen_llm) -> str:
    global _LAST_SHELL_COMMAND
    if not command:
        return _build_fix_usage(_LAST_SHELL_COMMAND)
    _LAST_SHELL_COMMAND = command
    from app.core.cli import EventPrinter
    from app.core.loop import solve
    from app.core.tools import Workspace

    ws = Workspace(pathlib.Path(workspace), test_command=command, read_only=())
    ws.spill_dir = ws.root / ".mitra" / "output"
    journal: list = []
    ws.journal = journal
    res = solve(f"Make this command succeed: `{command}`. Find the cause of the failure and fix the code.",
                ws, codegen_llm, on_event=EventPrinter(console),
                record_path=ws.root / ".mitra" / "runs" / time.strftime("fix-%Y%m%d-%H%M%S.jsonl"))
    if journal:
        memory.record_last_change_set(workspace, {"entries": journal})
    status = "fixed" if res.status == "passed" else f"not fixed ({res.status})"
    return f"`{command}`: {status}. {res.summary}"


def _extract_command(request: str) -> str:
    """Pull a bare shell command out of a natural-language request.

    Looks for backtick-quoted text first, then takes the whole request as-is
    so the shell agent's LLM loop can handle it directly.
    """
    import re
    match = re.search(r"`([^`]+)`", request)
    return match.group(1) if match else request


def _confirm_tool(tool_name: str, args: dict) -> bool:
    """Ask the user before the filesystem agent executes a guarded file operation."""
    _LABELS = {
        "delete_file":   ("Delete file",   "red"),
        "delete_folder": ("Delete folder", "red"),
        "move_file":     ("Move / rename", "yellow"),
        "create_file":   ("Overwrite file", "yellow"),
        "edit_file":     ("Edit file", "yellow"),
        "update_markdown_file": ("Edit markdown file", "yellow"),
        "mcp_call":      ("Call MCP tool", "yellow"),
    }
    label, _colour = _LABELS.get(tool_name, (tool_name, "yellow"))

    if tool_name == "move_file":
        detail = f"{args.get('src', '?')}  →  {args.get('dest', '?')}"
    elif tool_name == "mcp_call":
        detail = f"{args.get('server', '?')} / {args.get('tool', '?')}"
    else:
        detail = args.get("path", "?")

    preview = ""
    if tool_name in {"create_file", "edit_file", "update_markdown_file"}:
        preview = _build_diff_preview(detail, args.get("content", ""))
        scope_note = _build_edit_scope_note(preview)
        if scope_note:
            preview = f"{preview}\n\n{scope_note}"
        title = "File diff preview"
    elif tool_name == "move_file":
        preview = _build_move_preview(args.get("src", ""), args.get("dest", ""))
        title = "Destructive operation"
    elif tool_name == "mcp_call":
        preview = "Arguments:\n" + json.dumps(mcp_registry.mask(args.get("arguments") or {}), indent=2)[:2000]
        title = "MCP tool call (not on the free list)"
    else:
        title = "Destructive operation"

    choice = _choose_approval_option(
        title,
        f"{label}: {detail}\n\n{preview or 'No preview available.'}\n\n{label} {detail}?",
        [
            ("approve", "Yes"),
            ("deny", "No, skip it"),
        ],
        fallback_default="approve" if tool_name in {"create_file", "edit_file", "update_markdown_file", "mcp_call"} else "deny",
    )
    approved = choice == "approve"
    if not approved:
        _print_approval_result("Skipped", approved=False)
    return approved


def _build_diff_preview(path: str, new_content: str, max_lines: int = 60) -> str:
    """Return a small unified diff preview for an existing file overwrite."""
    target = pathlib.Path(path)
    try:
        old_content = target.read_text(encoding="utf-8")
    except Exception as exc:
        return f"(Could not read current file for diff preview: {exc})"

    if old_content == new_content:
        return "(No content changes)"

    diff_lines = list(
        difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"current\\{target.name}",
            tofile=f"new\\{target.name}",
            lineterm="",
        )
    )
    if len(diff_lines) > max_lines:
        hidden = len(diff_lines) - max_lines
        diff_lines = diff_lines[:max_lines] + [f"... ({hidden} more lines omitted)"]
    return "\n".join(diff_lines)


def _build_edit_scope_note(diff_preview: str) -> str:
    """Return a compact scope hint so operators can spot broad rewrites quickly."""
    lines = diff_preview.splitlines()
    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    changed = added + removed
    if changed == 0:
        return ""
    note = f"Change scope: +{added} / -{removed} lines."
    if changed > 120:
        return (
            f"{note} This is a broad rewrite; if the task is narrow, consider a smaller targeted edit."
        )
    return note


def _build_move_preview(src: str, dest: str) -> str:
    try:
        source = filesystem._resolve_path(src)
        destination = filesystem._resolve_path(dest)
    except Exception:
        return "Move the selected file or folder. Imports and package names stay unchanged unless you ask for that too."

    if not source.exists():
        return (
            "Source path: not found inside the current workspace\n"
            "Destination: "
            + ("already exists" if destination.exists() else "will be created as the new path")
            + "\nNote: if you meant the current project root folder itself, rename it from the parent directory instead of inside this workspace."
        )

    source_type = "folder" if source.is_dir() else "file"
    destination_state = "already exists" if destination.exists() else "will be created as the new path"
    lines = [
        f"Source type: {source_type}",
        f"Destination: {destination_state}",
        "Note: this only renames/moves the selected path. Imports and package names stay unchanged unless you request that too. Internal code references also stay unchanged by default.",
    ]
    return "\n".join(lines)








# ── Tokens at which auto-compact kicks in ────────────────────────────────────
_AUTO_COMPACT_THRESHOLD = 0  # 0 = 80% of num_ctx (E-046); overridden at runtime from mitra.toml


def _compact(
    llm,
    messages: list,
    system_prompt: str,
    *,
    workspace: str | None = None,
    reason: str = "manual",
    total_tokens: int | None = None,
    rec=None,
) -> list:
    """
    Summarise the conversation so far and return a fresh messages list.
    The system prompt is kept; everything else is replaced with a single
    HumanMessage containing the condensed history.
    Preserves structured artifacts: plan state, change sets, failures.
    """
    from langchain_core.messages import HumanMessage as HM

    # Only summarise if there is history beyond the system prompt
    history = [m for m in messages if not isinstance(m, SystemMessage)]
    if not history:
        console.print("[dim]Nothing to compact.[/dim]")
        return messages

    turns_text = []
    for m in history:
        role = type(m).__name__.replace("Message", "")
        turns_text.append(f"{role}: {getattr(m, 'content', '') or ''}")
    history_blob = "\n".join(turns_text)

    # Load structured artifacts to include in compaction
    plan_summary = ""
    change_summary = ""
    failure_summary = ""
    if workspace:
        plan_text = memory.load_plan(workspace)
        if plan_text:
            plan_summary = f"\n\n--- Active Plan ---\n{plan_text}"
        change_set = memory.load_last_change_set(workspace)
        if change_set:
            entries = change_set.get("entries") or []
            if entries:
                change_summary = f"\n\n--- Last Change Set ({len(entries)} steps) ---\n"
                for e in entries:
                    kind = e.get("kind", "unknown")
                    path = e.get("path") or e.get("src") or e.get("dest") or ""
                    change_summary += f"  {kind}: {path}\n"
        # Check activity for recent failures
        recent = memory.load_recent_activity(workspace, limit=10)
        failures = [r for r in recent if "error" in r.get("assistant", "").lower() or "failed" in r.get("assistant", "").lower() or "✗" in r.get("assistant", "")]
        if failures:
            failure_summary = f"\n\n--- Recent Failures ({len(failures)}) ---\n"
            for f in failures[-3:]:
                failure_summary += f"  {f.get('assistant', '')[:200]}\n"

    summarise_prompt = (
        "Summarise the following conversation history concisely. "
        "PRESERVE THESE EXPLICITLY:\n"
        "1. Key decisions and rationale\n"
        "2. Files created/modified/deleted\n"
        "3. Errors, failures, and their resolutions (or lack thereof)\n"
        "4. Active plan steps (completed, in-progress, pending)\n"
        "5. Next steps and unresolved blockers\n"
        "Output plain text — no JSON, no tool calls.\n\n"
        + history_blob
        + plan_summary
        + change_summary
        + failure_summary
    )

    with console.status("[m.dim]Compacting history...[/m.dim]", spinner_style="m.accent"):
        summary_msg = llm.invoke([HM(content=summarise_prompt)])
    if rec is not None:  # the compaction call is traced too (item 0)
        rec.trace([HM(content=summarise_prompt)], summary_msg, model=str(getattr(llm, "model", "") or ""),
                  purpose="compact", reason=reason)

    summary = (summary_msg.content or "").strip()
    if workspace:
        session_meta = session_agent.ensure_session(workspace)
        compact_meta = {
            "reason": reason,
            "summary": summary,
            "compacted_at": datetime.now().isoformat(timespec="seconds"),
            "turns_compacted": len(history),
            "preserved_artifacts": {
                "plan": bool(plan_summary),
                "change_set": bool(change_summary),
                "failures": bool(failure_summary),
            },
        }
        if total_tokens is not None:
            compact_meta["usage_tokens_before"] = total_tokens
        memory.save_session_metadata(
            workspace,
            {
                **session_meta,
                "last_compaction": compact_meta,
            },
        )
    console.print(ui.tool_line("Compacted", detail="the conversation was summarised to free context"))
    console.print(ui.detail_block(summary, max_lines=20))
    return [
        SystemMessage(content=system_prompt),
        HM(content=f"[Compacted context from previous turns]\n\n{summary}"),
    ]


def _print_help(extra_commands=None):
    table = Table.grid(padding=(0, 2))
    table.add_column(style="m.accent", no_wrap=True)
    table.add_column(style="m.dim")
    commands = list(_COMMAND_HELP)
    for cmd, desc in commands:
        table.add_row(cmd, desc)
    console.print()
    console.print(table)
    keys = Table.grid(padding=(0, 2))
    keys.add_column(style="m.accent", no_wrap=True)
    keys.add_column(style="m.dim")
    for key, desc in _KEY_HELP:
        keys.add_row(key, desc)
    console.print()
    console.print(Text("  Keys", style="m.tool"))
    console.print(keys)


if __name__ == "__main__":
    cli()
