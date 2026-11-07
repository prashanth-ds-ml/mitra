"""The harness settings Mitra can tune itself (Harness²-style self-improvement, step 1).

Everything the improve loop may change lives here, not in code:
    rules   extra lines added to the chat and solve prompts ("learned rules")
    tools   replacement descriptions for tools, by name
    limits  step limits and guard settings

Active file: ~/.mitra/harness.toml (or $MITRA_HARNESS). Every save also writes a copy to ~/.mitra/harness/history/,
so each change can be traced and reverted. A missing or broken file means the built-in defaults: Mitra never breaks
because of this file.
"""
from __future__ import annotations

import copy
import os
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_LIMITS = {
    "chat_max_steps": 40,
    "solve_max_steps": 40,
    "max_repeats": 2,        # identical calls allowed before they are refused
    "max_failures": 4,       # failures of one tool in a row before the turn stops
    "fresh_round_after": 3,  # failing test runs in a row before solve starts a fresh round
}
MAX_RULES = 12              # keeps the prompt small (the 3K budget)
MAX_RULE_CHARS = 240
MAX_TOOL_CHARS = 250          # with MAX_RULES full rules, the worst case stays in the budget (CI); 300 -> 250 when append_file and check_code were added


@dataclass
class Harness:
    version: int = 0
    rules: list[str] = field(default_factory=list)
    tools: dict[str, str] = field(default_factory=dict)
    limits: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_LIMITS))
    note: str = ""          # why this version exists
    source: str = "defaults"

    def limit(self, name: str) -> int:
        return int(self.limits.get(name, DEFAULT_LIMITS[name]))

    def copy(self) -> "Harness":
        return copy.deepcopy(self)


def home() -> Path:
    return Path(os.environ.get("MITRA_HOME") or Path.home() / ".mitra")


def active_path() -> Path:
    return Path(os.environ.get("MITRA_HARNESS") or home() / "harness.toml")


def _clean(h: Harness) -> Harness:
    h.rules = [" ".join(str(r).split())[:MAX_RULE_CHARS] for r in h.rules if str(r).strip()][:MAX_RULES]
    h.tools = {str(k): " ".join(str(v).split())[:MAX_TOOL_CHARS] for k, v in h.tools.items() if str(v).strip()}
    limits = dict(DEFAULT_LIMITS)
    for k, v in (h.limits or {}).items():
        if k in DEFAULT_LIMITS:
            try:
                limits[k] = max(1, min(200, int(v)))
            except (TypeError, ValueError):
                pass
    h.limits = limits
    return h


def load(path: Path | None = None) -> Harness:
    p = Path(path) if path else active_path()
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return Harness()
    return _clean(Harness(version=int(data.get("version", 0) or 0), rules=list(data.get("rules", [])),
                          tools=dict(data.get("tools", {})), limits=dict(data.get("limits", {})),
                          note=str(data.get("note", "")), source=str(p)))


def to_toml(h: Harness) -> str:
    import tomli_w

    return tomli_w.dumps({"version": h.version, "note": h.note, "rules": h.rules, "tools": h.tools,
                          "limits": h.limits})


def save(h: Harness, note: str, path: Path | None = None) -> Path:
    """Write a new version (version + 1) as the active harness and keep a copy in history. Returns the history file."""
    h = _clean(h.copy())
    h.version += 1
    h.note = note
    p = Path(path) if path else active_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    text = to_toml(h)
    p.write_text(text, encoding="utf-8")
    hist = p.parent / "harness" / "history"
    hist.mkdir(parents=True, exist_ok=True)
    copy_path = hist / f"{time.strftime('%Y%m%d-%H%M%S')}-v{h.version}.toml"
    copy_path.write_text(text, encoding="utf-8")
    return copy_path


def apply_prompt(base: str, h: Harness) -> str:
    if not h.rules:
        return base
    return base + "\n\nRules learned from earlier runs:\n" + "\n".join(f"- {r}" for r in h.rules)


def apply_tools(specs: list[dict], h: Harness) -> list[dict]:
    if not h.tools:
        return specs
    out = []
    for s in specs:
        if s["name"] in h.tools:
            s = {**s, "description": h.tools[s["name"]]}
        out.append(s)
    return out
