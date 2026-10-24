"""Model Advisor — recommends the best installed models for each CodeMitra role.

Roles
-----
chat    : The main conversational model (local_model in config).
          Needs good reasoning, reliable tool-calling, and GPU speed.
code    : Code generation / heavy refactor tasks (codegen_model).
          Quality matters more than latency; split-mode is acceptable.
agent   : Sub-agent calls (filesystem, shell, planner).
          Currently shares the chat model — speed and tool-calling are critical.

The advisor scores every installed model for each role by combining a
curated quality score with a hardware-placement multiplier, then picks
the top candidate per role and explains its reasoning.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

try:
    import tomli_w
    _TOML_W_AVAILABLE = True
except ImportError:
    _TOML_W_AVAILABLE = False

# ── Model quality database ────────────────────────────────────────────────────
# Each entry is (name_pattern_regex, {role: base_quality_score 1-10}).
# Patterns are matched case-insensitively against the full model name.
# More-specific patterns should come first.
_MODEL_PROFILES: list[tuple[str, dict[str, float]]] = [
    # ── Top-tier coders ───────────────────────────────────────────────────────
    (r"codestral",              {"chat": 7.0, "code": 10.0, "agent": 7.0}),
    (r"qwen2\.5-coder:14b",    {"chat": 7.0, "code":  9.5, "agent": 8.5}),
    (r"qwen2\.5-coder:7b",     {"chat": 6.5, "code":  8.5, "agent": 8.5}),
    (r"deepseek-coder",        {"chat": 5.5, "code":  7.5, "agent": 6.5}),

    # ── Strong general / reasoning ─────────────────────────────────────────────
    (r"qwen3:8b",              {"chat": 9.5, "code":  7.5, "agent": 9.5}),
    (r"qwen3\.5:latest",       {"chat": 9.0, "code":  7.5, "agent": 9.0}),
    (r"qwen3\.5:7b",           {"chat": 9.0, "code":  7.5, "agent": 9.0}),
    (r"deepseek-r1:8b",        {"chat": 9.0, "code":  8.5, "agent": 6.5}),
    (r"deepseek-r1:7b",        {"chat": 8.5, "code":  8.0, "agent": 6.5}),
    (r"gemma4",                {"chat": 8.0, "code":  7.0, "agent": 7.5}),
    (r"mistral:7b",            {"chat": 7.0, "code":  6.5, "agent": 7.0}),
    (r"phi4-mini",             {"chat": 7.0, "code":  6.5, "agent": 7.0}),

    # ── Capable mid-tier ──────────────────────────────────────────────────────
    (r"qwen3\.5:4b",           {"chat": 7.0, "code":  6.0, "agent": 7.0}),
    (r"qwen2\.5vl",            {"chat": 7.0, "code":  6.0, "agent": 7.0}),
    (r"llama3\.2-vision",      {"chat": 7.0, "code":  5.0, "agent": 6.0}),

    # ── Small / vision ────────────────────────────────────────────────────────
    (r"qwen3-vl",              {"chat": 6.5, "code":  5.5, "agent": 6.5}),
    (r"llava",                 {"chat": 6.0, "code":  4.0, "agent": 5.0}),
    (r"llama3\.2:3b",          {"chat": 5.0, "code":  4.0, "agent": 5.0}),
]

# Placement speed multipliers per role.
# "agent" strongly favours GPU (many rapid tool-call round-trips).
# "code"  tolerates split — you wait a bit longer for quality output.
# "chat"  balanced.
_PLACEMENT_MULTIPLIERS: dict[str, dict[str, float]] = {
    "gpu":   {"chat": 1.00, "code": 1.00, "agent": 1.00},
    "split": {"chat": 0.78, "code": 0.90, "agent": 0.65},
    "cpu":   {"chat": 0.45, "code": 0.65, "agent": 0.30},
}

_ROLE_LABELS = {
    "chat": "🗨️  Chat / main model",
    "code": "💻  Code generation",
    "agent": "🤖  Sub-agent (tool calling)",
}

_ROLE_DESCRIPTIONS = {
    "chat":  "Conversational quality and tool-calling for the main session loop.",
    "code":  "Heavy coding, refactors, and code review. Quality > speed.",
    "agent": "Sub-agent calls inside plan/fix loops. Speed and reliability matter most.",
}


@dataclass
class ModelScore:
    model: object          # LocalModelInfo
    role: str
    base: float
    final: float
    placement_mult: float
    reason: str


@dataclass
class HardwareProfile:
    vram_gib: float | None
    ram_gib: float | None
    gpu_name: str | None = None

    @property
    def summary(self) -> str:
        parts = []
        if self.gpu_name:
            parts.append(self.gpu_name)
        if self.vram_gib is not None:
            parts.append(f"{self.vram_gib:.1f} GB VRAM")
        if self.ram_gib is not None:
            parts.append(f"{self.ram_gib:.1f} GB RAM")
        return " · ".join(parts) if parts else "Unknown hardware"


@dataclass
class Recommendations:
    hardware: HardwareProfile
    chat: ModelScore | None
    code: ModelScore | None
    runner_up: dict[str, ModelScore | None] = field(default_factory=dict)
    all_scores: dict[str, list[ModelScore]] = field(default_factory=dict)


# ── Scoring logic ─────────────────────────────────────────────────────────────

def _base_score(model_name: str, role: str) -> float:
    for pattern, scores in _MODEL_PROFILES:
        if re.search(pattern, model_name, re.IGNORECASE):
            return scores.get(role, 5.0)
    return 5.0  # unknown model — neutral score


def _score_model(model_info, role: str) -> ModelScore:
    base = _base_score(model_info.name, role)
    placement = getattr(model_info, "placement", "gpu")
    mult = _PLACEMENT_MULTIPLIERS.get(placement, _PLACEMENT_MULTIPLIERS["gpu"]).get(role, 1.0)
    final = round(base * mult, 2)

    placement_note = {
        "gpu":   "fully on GPU",
        "split": "GPU+CPU split",
        "cpu":   "CPU only",
    }.get(placement, placement)
    size_note = f"{model_info.size_text}" if getattr(model_info, "size_text", "") else ""
    reason = f"quality {base:.0f}/10 for {role} · {placement_note}"
    if size_note:
        reason += f" · {size_note}"
    return ModelScore(
        model=model_info,
        role=role,
        base=base,
        final=final,
        placement_mult=mult,
        reason=reason,
    )


def recommend_models(
    inventory: list,
    vram_gib: float | None = None,
    ram_gib: float | None = None,
    gpu_name: str | None = None,
) -> Recommendations:
    """Score every installed model for each role and return the top picks."""
    hardware = HardwareProfile(vram_gib=vram_gib, ram_gib=ram_gib, gpu_name=gpu_name)

    all_scores: dict[str, list[ModelScore]] = {}
    for role in ("chat", "code", "agent"):
        scored = sorted(
            [_score_model(m, role) for m in inventory if getattr(m, "size_gib", None) is not None],
            key=lambda s: s.final,
            reverse=True,
        )
        all_scores[role] = scored

    def top(role: str) -> ModelScore | None:
        return all_scores[role][0] if all_scores.get(role) else None

    def runner_up(role: str) -> ModelScore | None:
        scores = all_scores.get(role, [])
        return scores[1] if len(scores) > 1 else None

    return Recommendations(
        hardware=hardware,
        chat=top("chat"),
        code=top("code"),
        runner_up={"chat": runner_up("chat"), "code": runner_up("code"), "agent": runner_up("agent")},
        all_scores=all_scores,
    )


# ── Display helpers ───────────────────────────────────────────────────────────

def format_recommendations(recs: Recommendations, current_local: str = "", current_codegen: str = "") -> str:
    """Return a Rich-markup string summarising the recommendations."""
    lines: list[str] = []

    lines.append("[bold cyan]## Hardware analysis[/bold cyan]")
    lines.append(f"  {recs.hardware.summary}")
    lines.append("")

    # ── Chat model ────────────────────────────────────────────────────────────
    lines.append("[bold cyan]## Recommended config[/bold cyan]")
    lines.append("")

    for role_key, pick_attr, current in [
        ("chat", "chat", current_local),
        ("code", "code", current_codegen),
    ]:
        pick: ModelScore | None = getattr(recs, pick_attr)
        ru: ModelScore | None = recs.runner_up.get(role_key)
        label = _ROLE_LABELS[role_key]
        desc  = _ROLE_DESCRIPTIONS[role_key]

        lines.append(f"[bold]{label}[/bold]")
        lines.append(f"[dim]{desc}[/dim]")
        if pick:
            name = pick.model.name
            is_current = (name == current)
            badge = " [green](already set)[/green]" if is_current else ""
            placement = getattr(pick.model, "placement", "gpu")
            p_icon = {"gpu": "🟢", "split": "🟡", "cpu": "🔴"}.get(placement, "")
            lines.append(f"  ⭐ [bold green]{name}[/bold green]{badge}  {p_icon}")
            lines.append(f"     {pick.reason}  →  score {pick.final:.1f}")
            if ru and ru.model.name != name:
                ru_placement = getattr(ru.model, "placement", "gpu")
                ru_icon = {"gpu": "🟢", "split": "🟡", "cpu": "🔴"}.get(ru_placement, "")
                lines.append(f"  2nd: [dim]{ru.model.name}[/dim]  {ru_icon}  [dim]{ru.reason}[/dim]")
        else:
            lines.append("  No installed model found for this role.")
        lines.append("")

    # ── Agent note ────────────────────────────────────────────────────────────
    agent_pick = recs.all_scores.get("agent", [None])[0]
    if agent_pick:
        lines.append("[bold]🤖  Sub-agent (tool calling)[/bold]")
        lines.append("[dim]Sub-agents share the chat model — this is shown for reference.[/dim]")
        placement = getattr(agent_pick.model, "placement", "gpu")
        p_icon = {"gpu": "🟢", "split": "🟡", "cpu": "🔴"}.get(placement, "")
        lines.append(f"  Best for speed+tools: [dim]{agent_pick.model.name}[/dim]  {p_icon}  [dim]{agent_pick.reason}[/dim]")
        lines.append("")

    # ── Full ranked table ─────────────────────────────────────────────────────
    lines.append("[bold]Full ranking (chat score · code score · agent score):[/bold]")
    seen = set()
    merged: list[tuple[float, object]] = []
    for role in ("chat", "code", "agent"):
        for s in recs.all_scores.get(role, []):
            if s.model.name not in seen:
                chat_s  = next((x.final for x in recs.all_scores.get("chat", [])  if x.model.name == s.model.name), 0)
                code_s  = next((x.final for x in recs.all_scores.get("code", [])  if x.model.name == s.model.name), 0)
                agent_s = next((x.final for x in recs.all_scores.get("agent", []) if x.model.name == s.model.name), 0)
                merged.append((chat_s + code_s + agent_s, s.model, chat_s, code_s, agent_s))
                seen.add(s.model.name)

    merged.sort(key=lambda x: x[0], reverse=True)
    placement_icon = {"gpu": "🟢", "split": "🟡", "cpu": "🔴"}
    for _, m, cs, ks, ag in merged:
        pl = getattr(m, "placement", "gpu")
        icon = placement_icon.get(pl, "")
        active = " ◀ active" if m.name == current_local else ""
        lines.append(
            f"  {icon} [cyan]{m.name:<35}[/cyan]"
            f"  chat {cs:4.1f}  code {ks:4.1f}  agent {ag:4.1f}{active}"
        )

    return "\n".join(lines)


# ── Config writing ────────────────────────────────────────────────────────────

def apply_to_toml(workspace: str, local_model: str, codegen_model: str = "") -> tuple[bool, str]:
    """Write (or update) codemitra.toml with the recommended models.

    Returns (success, message).
    """
    if not _TOML_W_AVAILABLE:
        # Fall back to a simple line-based writer
        return _apply_to_toml_manual(workspace, local_model, codegen_model)

    toml_path = pathlib.Path(workspace) / "codemitra.toml"
    try:
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                cfg = tomllib.load(f)
        else:
            cfg = {}
        cfg["local_model"] = local_model
        if codegen_model:
            cfg["codegen_model"] = codegen_model
        with open(toml_path, "wb") as f:
            import tomli_w
            tomli_w.dump(cfg, f)
        return True, f"Updated `codemitra.toml` → local_model = {local_model!r}"
    except Exception as exc:
        return False, f"Could not update codemitra.toml: {exc}"


def _apply_to_toml_manual(workspace: str, local_model: str, codegen_model: str = "") -> tuple[bool, str]:
    """Simple line-based toml updater used when tomli_w is unavailable."""
    toml_path = pathlib.Path(workspace) / "codemitra.toml"
    try:
        lines = toml_path.read_text(encoding="utf-8").splitlines() if toml_path.exists() else []
        updates = {"local_model": local_model}
        if codegen_model:
            updates["codegen_model"] = codegen_model

        new_lines: list[str] = []
        applied: set[str] = set()
        for line in lines:
            matched = False
            for key in list(updates):
                if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                    new_lines.append(f'{key} = "{updates[key]}"')
                    applied.add(key)
                    matched = True
                    break
            if not matched:
                new_lines.append(line)

        for key, val in updates.items():
            if key not in applied:
                new_lines.append(f'{key} = "{val}"')

        toml_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return True, f"Updated `codemitra.toml` → local_model = {local_model!r}"
    except Exception as exc:
        return False, f"Could not update codemitra.toml: {exc}"


def get_best_local_model(inventory: list, vram_gib: float | None, ram_gib: float | None) -> str | None:
    """Convenience: return just the recommended chat-model name."""
    recs = recommend_models(inventory, vram_gib=vram_gib, ram_gib=ram_gib)
    return recs.chat.model.name if recs.chat else None
