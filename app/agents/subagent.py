"""True subagent runtime boundary for CodeMitra.

Subagents are isolated workers with:
- Fresh context windows
- Restricted tool sets
- Separate execution boundaries
- Summarized results returned to the parent
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from rich.console import Console

from app.llm import get_local_llm
from app import config, events as event_bus
from app.agents import filesystem, shell as shell_agent, reader as reader_agent, web as web_agent


@dataclass(frozen=True)
class SubagentConfig:
    """Configuration for a subagent."""
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    temperature: float = 0.2
    num_ctx: int = 131072
    max_turns: int = 10


@dataclass(frozen=True)
class SubagentResult:
    """Result from a subagent execution."""
    success: bool
    summary: str
    tokens_in: int = 0
    tokens_out: int = 0
    turns: int = 0
    error: str | None = None


def _get_tokens(response) -> tuple[int, int]:
    """Extract token counts from response."""
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return 0, 0


def _build_subagent_tools(config: SubagentConfig, llm, console: Console | None = None):
    """Build the toolset available to the subagent."""
    tools = []
    
    if "filesystem" in config.allowed_tools or "all" in config.allowed_tools:
        tools.append(filesystem.make_routing_tool(llm))
    if "shell" in config.allowed_tools or "all" in config.allowed_tools:
        tools.append(shell_agent.make_routing_tool(llm, console=console))
    if "reader" in config.allowed_tools or "all" in config.allowed_tools:
        tools.append(reader_agent.make_routing_tool(llm, console=console))
    if "web" in config.allowed_tools or "all" in config.allowed_tools:
        tools.append(web_agent.make_routing_tool(llm, console=console))
    
    return tools


def run_subagent(
    subagent_cfg: SubagentConfig,
    task: str,
    parent_context: list[dict] | None = None,
    workspace: str | None = None,
    console: Console | None = None,
) -> SubagentResult:
    """Run a subagent with isolated context and restricted tools."""
    if console is None:
        console = Console()

    cfg = config.load()
    if workspace is None:
        workspace = cfg["workspace"]

    model = subagent_cfg.model or cfg.get("local_model") or ""
    if not model:
        return SubagentResult(
            success=False,
            summary="No model configured for subagent",
            error="No model configured",
        )
    temperature = subagent_cfg.temperature
    num_ctx = subagent_cfg.num_ctx

    _vram = config.get_gpu_vram_gib()
    _model_info = next(
        (m for m in config.get_local_model_inventory() if m.name == model), None
    )
    _placement = _model_info.placement if _model_info else config.get_model_placement(None, _vram)
    num_gpu = config.get_num_gpu_for_placement(_placement, cfg.get("gpu_layers", "auto"))

    subagent_llm = get_local_llm(
        model,
        temperature,
        base_url=cfg.get("ollama_local_base_url"),
        num_ctx=num_ctx,
        num_gpu=num_gpu,
        num_predict=2048,
    )

    tools = _build_subagent_tools(subagent_cfg, subagent_llm, console)
    if not tools:
        return SubagentResult(
            success=False,
            summary="No tools available for subagent",
            error="No tools configured",
        )

    subagent_llm_with_tools = subagent_llm.bind_tools(tools)

    messages = [SystemMessage(content=subagent_cfg.system_prompt)]

    if parent_context:
        for msg in parent_context:
            if msg.get("role") == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "ai":
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=task))

    hook_ctx = event_bus.HookContext(
        workspace=workspace,
        session_mode="subagent",
        metadata={"subagent": subagent_cfg.name},
    )

    total_in = total_out = 0
    turns = 0

    for turn in range(subagent_cfg.max_turns):
        event_bus.emit(event_bus.PreToolEvent(
            tool_name="subagent_turn",
            tool_args={"turn": turn, "task": task},
            request=task,
            context=hook_ctx,
        ))
        
        response = subagent_llm_with_tools.invoke(messages)
        t_in, t_out = _get_tokens(response)
        total_in += t_in
        total_out += t_out
        messages.append(response)
        turns += 1
        
        if not response.tool_calls:
            summary = response.content or ""
            event_bus.emit(event_bus.PostToolEvent(
                tool_name="subagent_turn",
                tool_args={"turn": turn, "task": task},
                result=summary,
                context=hook_ctx,
            ))
            return SubagentResult(
                success=True,
                summary=summary,
                tokens_in=total_in,
                tokens_out=total_out,
                turns=turns,
            )
        
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = {k: v for k, v in tc["args"].items() if k != "request"}
            request = tc["args"].get("request", task)
            
            tool_result = None
            tool_error = None
            
            if tool_name == "run_command":
                shell_result = shell_agent.execute(
                    command=tool_args.get("command", ""),
                    cwd=None,
                    console=console,
                )
                tool_result = shell_result.to_llm_summary()
                messages.append(ToolMessage(content=tool_result, tool_call_id=tc["id"]))
            elif tool_name == "read_codebase":
                reader_resp = reader_agent.run(subagent_llm, request, console=console)
                total_in += reader_resp.tokens_in
                total_out += reader_resp.tokens_out
                tool_result = reader_resp.summary
                messages.append(ToolMessage(content=tool_result, tool_call_id=tc["id"]))
            elif tool_name == "browse_web":
                web_resp = web_agent.run(subagent_llm, request, console=console)
                total_in += web_resp.tokens_in
                total_out += web_resp.tokens_out
                tool_result = web_resp.summary
                messages.append(ToolMessage(content=tool_result, tool_call_id=tc["id"]))
            else:
                agent_resp = filesystem.run(subagent_llm, request, console=console)
                total_in += agent_resp.tokens_in
                total_out += agent_resp.tokens_out
                tool_result = agent_resp.summary
                messages.append(ToolMessage(content=tool_result, tool_call_id=tc["id"]))
            
            event_bus.emit(event_bus.PostToolEvent(
                tool_name=tool_name,
                tool_args=tool_args,
                result=tool_result,
                context=hook_ctx,
                error=tool_error,
            ))
    
    return SubagentResult(
        success=False,
        summary="Subagent reached maximum turns without completing",
        tokens_in=total_in,
        tokens_out=total_out,
        turns=turns,
        error="Max turns exceeded",
    )


def create_subagent(
    name: str,
    description: str,
    system_prompt: str,
    allowed_tools: list[str] | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    num_ctx: int = 131072,
    max_turns: int = 10,
) -> SubagentConfig:
    """Factory function to create a subagent configuration."""
    return SubagentConfig(
        name=name,
        description=description,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools or ["filesystem"],
        model=model,
        temperature=temperature,
        num_ctx=num_ctx,
        max_turns=max_turns,
    )