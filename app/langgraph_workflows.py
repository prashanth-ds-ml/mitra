"""LangGraph-backed orchestration for bounded workflow loops.

This module keeps the existing workflow engine in place and uses LangGraph
only for state transitions. The graph nodes still call the same shell and
filesystem agents, and `WorkflowRun` remains the persistence and guardrail
layer.
"""

from __future__ import annotations

from typing import Hashable

from langgraph.graph import END, START, StateGraph
from rich.console import Console
from typing_extensions import TypedDict

from app import memory, workflows
from app.agents import filesystem, shell as shell_agent
from app.agents.response import render

_MAX_FAILURE_REPLIES = {
    "approval_denied": "Repair stopped because the failing command was not approved.",
    "no_code_changes": "Repair stopped because no code changes were applied.",
}


class FixWorkflowState(TypedDict, total=False):
    workspace: str
    command: str
    codegen_llm: object
    console: Console
    workflow: workflows.WorkflowRun
    attempt: int
    max_attempts: int
    last_result: shell_agent.ShellResult
    repair_request: str
    final_reply: str
    next_action: str


def _build_fix_prompt(command: str, result: shell_agent.ShellResult, attempt: int, max_attempts: int) -> str:
    tail = result.tail or result.output or "(no output)"
    return (
        f"The command `{command}` failed in the current workspace.\n\n"
        f"This is repair attempt {attempt} of {max_attempts}.\n"
        "Inspect the relevant files, apply the smallest safe code changes needed, and stop after the edits.\n"
        "Do not run shell commands yourself; I will rerun the failing command after your patch.\n"
        "Prefer fixing the actual failure over broad refactors.\n\n"
        "Failure details:\n"
        f"{tail}"
    )


def _response_has_code_changes(agent_response) -> bool:
    mutating_tools = {"create_file", "move_file", "delete_file", "delete_folder", "create_folder"}
    return any(step.tool in mutating_tools and step.ok for step in agent_response.steps)


def _failure_tail(result: shell_agent.ShellResult | None) -> str:
    if result is None:
        return "(no output)"
    return result.tail or result.output or "(no output)"


def _run_test_step(state: FixWorkflowState) -> FixWorkflowState:
    workspace = state["workspace"]
    command = state["command"]
    workflow = state["workflow"]
    console = state["console"]
    attempt = int(state.get("attempt", 0)) + 1
    max_attempts = int(state["max_attempts"])
    test_step_label = f"Test attempt {attempt}: {command}"

    try:
        workflow.start_step(test_step_label)
    except workflows.WorkflowLimitError as exc:
        return {
            **state,
            "final_reply": str(exc),
            "next_action": "done",
        }
    console.print(f"[yellow]Repair attempt {attempt}/{max_attempts}[/yellow]")
    console.print(f"[dim]Running `{command}` to confirm the current failure.[/dim]")

    shell_result = shell_agent.execute(command=command, cwd=None, console=console)
    console.print(shell_agent.render(shell_result))

    if shell_result.denied:
        workflow.block("approval_denied", "The failing command was not approved for execution.")
        return {
            **state,
            "attempt": attempt,
            "last_result": shell_result,
            "final_reply": _MAX_FAILURE_REPLIES["approval_denied"],
            "next_action": "done",
        }

    try:
        workflow.finish_step(
            test_step_label,
            detail=shell_result.tail or shell_result.output or "Command finished.",
        )
    except workflows.WorkflowLimitError as exc:
        return {
            **state,
            "attempt": attempt,
            "last_result": shell_result,
            "final_reply": str(exc),
            "next_action": "done",
        }

    if shell_result.ok:
        if attempt == 1:
            workflow.complete(f"The command `{command}` was already passing.")
            return {
                **state,
                "attempt": attempt,
                "last_result": shell_result,
                "final_reply": f"The command `{command}` is already passing.",
                "next_action": "done",
            }

        workflow.complete(f"`{command}` passed after {attempt - 1} repair attempt(s).")
        return {
            **state,
            "attempt": attempt,
            "last_result": shell_result,
            "final_reply": f"Fixed after {attempt - 1} repair attempt{'s' if attempt - 1 != 1 else ''}. `{command}` now passes.",
            "next_action": "done",
        }

    if attempt >= max_attempts:
        return {
            **state,
            "attempt": attempt,
            "last_result": shell_result,
            "next_action": "fail",
        }

    return {
        **state,
        "attempt": attempt,
        "last_result": shell_result,
        "repair_request": _build_fix_prompt(command, shell_result, attempt, max_attempts),
        "next_action": "repair",
    }


def _run_repair_step(state: FixWorkflowState) -> FixWorkflowState:
    workspace = state["workspace"]
    command = state["command"]
    workflow = state["workflow"]
    console = state["console"]
    attempt = int(state["attempt"])
    max_attempts = int(state["max_attempts"])
    shell_result = state["last_result"]
    repair_request = state["repair_request"]
    fix_step_label = f"Fix attempt {attempt}: {command}"

    console.print("[yellow]Applying a targeted patch[/yellow]")
    console.print(f"[dim]Repair attempt {attempt} is editing the code now.[/dim]")
    try:
        workflow.start_step(fix_step_label)
    except workflows.WorkflowLimitError as exc:
        return {
            **state,
            "final_reply": str(exc),
            "next_action": "done",
        }

    agent_resp = filesystem.run(state["codegen_llm"], repair_request, console=console)
    console.print(render(agent_resp))

    if not _response_has_code_changes(agent_resp):
        workflow.block(
            "no_code_changes",
            f"Repair attempt {attempt} produced no code changes after `{command}` failed.",
        )
        return {
            **state,
            "final_reply": (
                f"Repair stopped after attempt {attempt} because no code changes were applied.\n\n"
                f"Latest command output:\n{_failure_tail(shell_result)}"
            ),
            "next_action": "done",
        }

    try:
        workflow.finish_step(
            fix_step_label,
            detail=agent_resp.summary[:300],
            change_set=memory.load_last_change_set(workspace),
        )
    except workflows.WorkflowLimitError as exc:
        return {
            **state,
            "final_reply": str(exc),
            "next_action": "done",
        }

    return {
        **state,
        "repair_request": _build_fix_prompt(command, shell_result, attempt, max_attempts),
        "next_action": "test",
    }


def _run_failure_stop(state: FixWorkflowState) -> FixWorkflowState:
    command = state["command"]
    workflow = state["workflow"]
    last_result = state.get("last_result")
    latest = _failure_tail(last_result)
    workflow.block(
        "max_iterations",
        f"Repair stopped after {state['max_attempts']} attempts while `{command}` was still failing.",
    )
    return {
        **state,
        "final_reply": (
            f"Repair stopped after {state['max_attempts']} attempts. `{command}` is still failing.\n\n"
            f"Latest command output:\n{latest}"
        ),
        "next_action": "done",
    }


def _route_after_test(state: FixWorkflowState) -> Hashable:
    return state.get("next_action", "done")


def _route_after_repair(state: FixWorkflowState) -> Hashable:
    return state.get("next_action", "done")


def build_fix_graph():
    """Build the LangGraph graph for the bounded fix loop."""
    graph = StateGraph(FixWorkflowState)
    graph.add_node("test", _run_test_step)
    graph.add_node("repair", _run_repair_step)
    graph.add_node("fail", _run_failure_stop)
    graph.add_edge(START, "test")
    graph.add_conditional_edges(
        "test",
        _route_after_test,
        {
            "repair": "repair",
            "fail": "fail",
            "done": END,
        },
    )
    graph.add_conditional_edges(
        "repair",
        _route_after_repair,
        {
            "test": "test",
            "done": END,
        },
    )
    graph.add_edge("fail", END)
    return graph.compile()


_FIX_GRAPH = build_fix_graph()


def run_fix_workflow(
    command: str,
    workspace: str,
    codegen_llm,
    *,
    console: Console | None = None,
    max_attempts: int = 3,
) -> str:
    """Run the fix workflow through LangGraph while keeping WorkflowRun as the control layer."""
    if not command:
        raise ValueError("A command is required for the fix workflow.")

    console = console or Console()
    workflow = workflows.WorkflowRun(
        workspace,
        "FixWorkflow",
        f"Repair failing command: {command}",
    )
    final_state = _FIX_GRAPH.invoke(
        {
            "workspace": workspace,
            "command": command,
            "codegen_llm": codegen_llm,
            "console": console,
            "workflow": workflow,
            "attempt": 0,
            "max_attempts": max_attempts,
            "next_action": "test",
        }
    )
    return final_state.get("final_reply") or "Repair workflow finished without a final reply."
