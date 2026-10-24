"""Explicit agent-role registry for Phase 4."""

from __future__ import annotations

from dataclasses import dataclass


_DEFAULT_AGENT_MODELS = {
    "planner": "qwen3:14b",
    "prd": "qwen3:14b",
    "task": "qwen3:14b",
    "coder": "qwen2.5-coder:14b",
    "tester": "qwen2.5-coder:7b",
    "reviewer": "qwen3:14b",
    "docs": "qwen2.5-coder:7b",
    "decision": "qwen3:14b",
}


@dataclass(frozen=True)
class AgentRole:
    key: str
    label: str
    workflows: tuple[str, ...]
    runtime_family: str
    description: str


_ROLES: tuple[AgentRole, ...] = (
    AgentRole(
        key="planner",
        label="Planner Agent",
        workflows=("PlanWorkflow", "NextWorkflow"),
        runtime_family="chat",
        description="Breaks goals into explicit steps and advances approved plans.",
    ),
    AgentRole(
        key="prd",
        label="PRD Agent",
        workflows=("PRDWorkflow",),
        runtime_family="chat",
        description="Owns product requirement shaping and structured requirement drafts.",
    ),
    AgentRole(
        key="task",
        label="Task Agent",
        workflows=("TaskWorkflow", "OrderWorkflow"),
        runtime_family="chat",
        description="Turns scoped goals into concrete ordered tasks.",
    ),
    AgentRole(
        key="coder",
        label="Coder Agent",
        workflows=("BuildWorkflow", "FixWorkflow"),
        runtime_family="codegen",
        description="Applies narrow code changes through the bounded workflow layer.",
    ),
    AgentRole(
        key="tester",
        label="Tester Agent",
        workflows=("TestWorkflow", "FixWorkflow"),
        runtime_family="codegen",
        description="Runs verification-oriented reasoning inside bounded test and repair loops.",
    ),
    AgentRole(
        key="reviewer",
        label="Reviewer Agent",
        workflows=("ReviewWorkflow",),
        runtime_family="chat",
        description="Reviews diffs and change sets for material issues only.",
    ),
    AgentRole(
        key="docs",
        label="Docs Agent",
        workflows=("DocsWorkflow",),
        runtime_family="codegen",
        description="Produces implementation-facing docs through explicit workflow steps.",
    ),
    AgentRole(
        key="decision",
        label="Decision Agent",
        workflows=("OrderWorkflow", "TaskWorkflow"),
        runtime_family="chat",
        description="Makes bounded tradeoff calls and keeps decision records explicit.",
    ),
)


def get_agent_roles() -> tuple[AgentRole, ...]:
    """Return the canonical Phase 4 agent roles."""
    return _ROLES


def default_agent_models() -> dict[str, str]:
    """Return the repo's default model mapping target for Phase 4 roles."""
    return dict(_DEFAULT_AGENT_MODELS)


def resolve_agent_models(
    cfg: dict,
    *,
    chat_model: str,
    codegen_model: str,
    cloud_codegen_enabled: bool,
) -> dict[str, str]:
    """Resolve explicit model names per agent role with config overrides."""
    configured = dict(default_agent_models())
    configured.update(dict(cfg.get("agent_models") or {}))

    resolved: dict[str, str] = {}
    for role in get_agent_roles():
        preferred = (configured.get(role.key) or "").strip()
        if preferred:
            resolved[role.key] = preferred
            continue
        if role.runtime_family == "codegen":
            resolved[role.key] = codegen_model if cloud_codegen_enabled and codegen_model else chat_model
        else:
            resolved[role.key] = chat_model
    return resolved


def summarize_agent_models(agent_models: dict[str, str]) -> str:
    """Return a compact status string grouped by role families."""
    planner_group = ", ".join(
        f"{role} `{agent_models.get(role, '?')}`"
        for role in ("planner", "prd", "task", "reviewer", "decision")
    )
    build_group = ", ".join(
        f"{role} `{agent_models.get(role, '?')}`"
        for role in ("coder", "tester", "docs")
    )
    return f"{planner_group} · {build_group}"
