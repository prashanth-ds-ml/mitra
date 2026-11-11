"""Which model does which job (phases and roles, D-049..D-051; PHASES_AND_ROLES.md).

Defaults follow D-051 and D-072 (deepseek-r1:8b thinks, qwen3.5:latest does; mimo-v2.6:9b replaced on
2026-11-11, it turned conversation into builds); the live chat keeps the model you picked last.
Your choices (`/model role <role> <model>`) are kept in ~/.mitra/roles.json and win over the defaults; mitra.toml
`[roles]` wins over both. A role whose model is not installed falls back to the chat model, so nothing breaks
before a download. Every switch is recorded, so the dashboard can compare models per role.
"""
from __future__ import annotations

import json
from pathlib import Path

from app import config

ROLES = ("chat", "planner", "tester", "builder", "debugger", "reviewer", "deployer", "reporter")

# D-051 (pending the screen): planner + final reviewer think; the tool-heavy phases do.
DEFAULTS: dict[str, str | None] = {
    "chat": None,            # = the model you picked last (/model use)
    "planner": "deepseek-r1:8b",
    "reviewer": "deepseek-r1:8b",
    "tester": "qwen3.5:latest",
    "builder": "qwen3.5:latest",
    "debugger": "qwen3.5:latest",
    "deployer": "qwen3.5:latest",
    "reporter": None,        # = whichever model is loaded (no swap)
}
WHY = {
    "chat": "live chat with you; no swaps while you wait",
    "planner": "PRD → plan, re-plan a stuck task (thinks; text only)",
    "reviewer": "final review of the project against the PRD (thinks; text only)",
    "tester": "writes each task's tests first, from the PRD",
    "builder": "writes the code that makes the tests pass",
    "debugger": "fixes failing tests (escalates to the planner after 2 rounds)",
    "deployer": "runs the app on localhost and checks it answers",
    "reporter": "handoff, morning report, README",
}


# Tools per role (only tools that exist today; planned ones join as they are built, PHASES_AND_ROLES.md).
_READ = ("list_files", "read_file", "search")
_MCP = ("mcp_find", "mcp_call")
TOOLS: dict[str, tuple[str, ...] | None] = {
    "chat": None,  # everything
    "planner": _READ + ("web_search", "fetch_url") + _MCP,
    "tester": _READ + ("write_file", "append_file", "edit_file", "make_dir", "run_tests") + _MCP,
    "builder": _READ + ("write_file", "append_file", "edit_file", "make_dir", "check_code", "run_tests",
                        "run_command") + _MCP,
    "debugger": _READ + ("edit_file", "check_code", "run_tests", "run_command") + _MCP,
    "reviewer": _READ + ("check_code",) + _MCP,
    "deployer": _READ + ("check_code", "run_command", "run_tests") + _MCP,
    "reporter": _READ + ("write_file", "append_file", "edit_file"),
}
# MCP servers per role (None = every enabled server); servers not configured yet are simply absent.
MCP: dict[str, tuple[str, ...] | None] = {
    "chat": None,
    "planner": ("context7", "research-desk", "github", "serena"),
    "tester": ("context7", "serena", "playwright"),
    "builder": ("context7", "serena", "shadcn"),
    "debugger": ("serena", "git", "playwright"),
    "reviewer": ("git", "semgrep", "playwright"),
    "deployer": ("playwright",),
    "reporter": ("git",),
}
# Thinking per role: "on" / "off" / None (= the session's setting). D-068 step 1: off by default, on only where it
# pays: the planner and the debugger (the chat thought for 5 minutes over "explain the game logic").
THINKING: dict[str, str | None] = {
    "chat": "off", "planner": "on", "tester": "off", "builder": "off", "debugger": "on",
    "reviewer": "off", "deployer": "off", "reporter": "off",
}
def thinking_for(role: str, cfg: dict | None = None) -> bool | str:
    """True / False / "auto" for a role. Your explicit `thinking = "on"|"off"` in mitra.toml wins for every role;
    otherwise the table above (review 2026-11-11: the table silently overrode mitra.toml)."""
    from app.llm import thinking_setting

    mine = str((cfg or {}).get("thinking") or "").strip().lower()
    if mine in ("on", "off", "true", "false", "yes", "no"):
        return thinking_setting(mine)
    return {"on": True, "off": False}.get(THINKING.get(role) or "", thinking_setting(None))


# Paths the role may read but not change: the builder cannot edit the tests it must pass (D-049).
READ_ONLY: dict[str, tuple[str, ...]] = {"builder": ("tests",)}


def context_for(model: str, cfg: dict | None = None) -> int:
    """Roles run every model at its own maximum context for the first days (user, 2026-11-08, D-052);
    a number in mitra.toml or your /context choice still wins. Data decides any limit later."""
    cfg = cfg or {}
    if cfg.get("num_ctx"):
        return int(cfg["num_ctx"])
    chosen = config.load_context_choice(model)
    native = int((config.get_model_facts(model) or {}).get("context") or 0)
    if chosen:
        return min(chosen, native) if native else chosen
    return native or config.context_for_model(model)


def choose_context(model: str, text: str, cfg: dict | None = None) -> tuple[int, str]:
    """`/context <size>|auto`: save the choice and return (num_ctx, "") by the same rule as startup and /role, or
    (0, error). E-061: the handler used config.context_for_model, so `auto` gave the measured 128K now and the
    model's 256K maximum after a restart."""
    native = int((config.get_model_facts(model) or {}).get("context") or 0)
    n, err = config.parse_context_choice(text, native)
    if err:
        return 0, err
    config.save_context_choice(model, n)
    return context_for(model, cfg), ""


def route(role: str, cfg: dict | None = None, have: set[str] | None = None) -> dict:
    """Everything a role switches at once: model, context, tools, MCP servers, thinking, read-only paths."""
    model, source = resolve(role, cfg, have)
    return {"role": role, "model": model, "source": source, "num_ctx": context_for(model, cfg),
            "tools": TOOLS.get(role), "mcp": MCP.get(role), "thinking": THINKING.get(role),
            "read_only": READ_ONLY.get(role, ())}


def describe(r: dict) -> str:
    tools = "all tools" if r["tools"] is None else f"{len(r['tools'])} tools"
    mcp = "all MCP servers" if r["mcp"] is None else ("MCP: " + ", ".join(r["mcp"]) if r["mcp"] else "no MCP")
    think = {"on": "thinking on", "off": "thinking off"}.get(r["thinking"] or "", "thinking as set")
    ro = f" · read-only: {', '.join(r['read_only'])}" if r["read_only"] else ""
    ctx = f" · {r['num_ctx'] // 1024}K" if r.get("num_ctx") else ""
    return f"{r['role']} · {r['model']}{ctx} ({r['source']}) · {tools} · {mcp} · {think}{ro}"


def _file() -> Path:
    return config._mitra_home() / "roles.json"


def load_choices() -> dict[str, str]:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items() if k in ROLES and v}
    except (OSError, ValueError, AttributeError):
        return {}


def save_choice(role: str, model: str | None) -> None:
    """Set a role's model; None or "default" puts the role back on its default."""
    data = load_choices()
    if model and model != "default":
        data[role] = model
    else:
        data.pop(role, None)
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=1), encoding="utf-8")


def use_for_chat(model: str) -> None:
    """`/model use X`: X becomes the chat model now and next time. Saved as the chat role's choice too, because a
    choice beats mitra.toml `local_model` and the last model in `resolve` (E-054: the switch silently did nothing)."""
    config.save_last_model(model)
    save_choice("chat", model)


def installed() -> set[str]:
    try:
        return {m.name for m in config.get_local_model_inventory()}
    except Exception:
        return set()


def chat_model(cfg: dict | None = None) -> str:
    cfg = cfg or {}
    return cfg.get("local_model") or config.load_last_model() or "qwen3.5:4b"


def resolve(role: str, cfg: dict | None = None, have: set[str] | None = None) -> tuple[str, str]:
    """(model, where it came from) for a role: mitra.toml [roles] > your choice > default > the chat model."""
    cfg = cfg or {}
    have = installed() if have is None else have
    toml_roles = cfg.get("roles") if isinstance(cfg.get("roles"), dict) else {}
    for source, model in (("mitra.toml", toml_roles.get(role)), ("your choice", load_choices().get(role)),
                          ("default", DEFAULTS.get(role))):
        if model:
            if model in have or not have:
                return model, source
            fallback = chat_model(cfg)
            return fallback, f"{source} {model} not installed → chat model"
    return chat_model(cfg), "chat model"


def table(cfg: dict | None = None) -> list[tuple[str, str, str, str]]:
    """(role, model, source, why) for every role, for `/model roles`."""
    have = installed()
    return [(r, *resolve(r, cfg, have), WHY[r]) for r in ROLES]
