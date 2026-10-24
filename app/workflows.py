"""Bounded workflow contracts for plan and repair execution."""

from __future__ import annotations

import dataclasses
import difflib
from datetime import datetime

from app import memory


WORKFLOW_NAMES = (
    "PlanWorkflow",
    "PRDWorkflow",
    "OrderWorkflow",
    "TaskWorkflow",
    "BuildWorkflow",
    "FixWorkflow",
    "TestWorkflow",
    "ReviewWorkflow",
    "DocsWorkflow",
    "NextWorkflow",
)


@dataclasses.dataclass(frozen=True)
class WorkflowLimits:
    max_iterations: int = 5
    max_files_changed: int = 6
    max_lines_changed: int = 300
    require_tests: bool = True
    stop_on_scope_change: bool = True


@dataclasses.dataclass(frozen=True)
class ChangeImpact:
    files_changed: int = 0
    lines_changed: int = 0


class WorkflowLimitError(RuntimeError):
    """Raised when a workflow exceeds an explicit Phase 3 bound."""


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _line_change_count(before: str | None, after: str | None) -> int:
    before_lines = (before or "").splitlines()
    after_lines = (after or "").splitlines()
    diff = difflib.ndiff(before_lines, after_lines)
    return sum(1 for line in diff if line.startswith("+ ") or line.startswith("- "))


def estimate_change_impact(change_set: dict | None) -> ChangeImpact:
    """Estimate changed files and line churn from the latest persisted change set."""
    if not change_set:
        return ChangeImpact()

    paths: set[str] = set()
    line_count = 0

    for entry in change_set.get("entries") or []:
        kind = entry.get("kind")
        path = entry.get("path")
        if path:
            paths.add(str(path))
        src = entry.get("src")
        dest = entry.get("dest")
        if src:
            paths.add(str(src))
        if dest:
            paths.add(str(dest))

        if kind in {"create_file", "edit_file"}:
            line_count += _line_change_count(entry.get("before"), entry.get("after"))
        elif kind == "delete_file":
            before = entry.get("before")
            if isinstance(before, str):
                line_count += len(before.splitlines())

    return ChangeImpact(files_changed=len(paths), lines_changed=line_count)


def workflow_limits(*, max_iterations: int | None = None) -> WorkflowLimits:
    """Return the default Phase 3 limits, optionally tightening iteration count."""
    limits = WorkflowLimits()
    if max_iterations is None:
        return limits
    return dataclasses.replace(limits, max_iterations=max(1, min(limits.max_iterations, max_iterations)))


class WorkflowRun:
    """Persist and enforce an explicit bounded workflow execution contract."""

    def __init__(
        self,
        workspace: str,
        name: str,
        goal: str,
        *,
        limits: WorkflowLimits | None = None,
    ) -> None:
        self.workspace = workspace
        self.name = name
        self.goal = goal
        self.limits = limits or WorkflowLimits()
        self.iterations = 0
        self.total_files_changed = 0
        self.total_lines_changed = 0
        self.status = "draft"
        self.current_step: str | None = None
        self._current_started_at: datetime | None = None

    def start(self) -> None:
        self.status = "running"
        self._persist()
        memory.append_execution_trace(
            self.workspace,
            "workflow_started",
            {
                "name": self.name,
                "goal": self.goal,
                "limits": dataclasses.asdict(self.limits),
            },
        )

    def start_step(self, label: str) -> None:
        if self.iterations >= self.limits.max_iterations:
            self.block(
                "max_iterations",
                f"{self.name} stopped before `{label}` because it reached the iteration limit "
                f"({self.limits.max_iterations}).",
            )
            raise WorkflowLimitError(
                f"{self.name} stopped because it reached the iteration limit ({self.limits.max_iterations})."
            )
        if self.status == "draft":
            self.start()
        self.iterations += 1
        self.current_step = label
        self._current_started_at = datetime.now()
        self.status = "running"
        self._persist()
        memory.append_execution_trace(
            self.workspace,
            "workflow_step_started",
            {
                "name": self.name,
                "goal": self.goal,
                "step": label,
                "iteration": self.iterations,
            },
        )

    def finish_step(self, label: str, *, detail: str, change_set: dict | None = None) -> None:
        impact = ChangeImpact()
        if self._change_set_belongs_to_current_step(change_set):
            impact = estimate_change_impact(change_set)
            self.total_files_changed += impact.files_changed
            self.total_lines_changed += impact.lines_changed

        self.current_step = label
        self.status = "running"
        self._persist()
        memory.append_execution_trace(
            self.workspace,
            "workflow_step_finished",
            {
                "name": self.name,
                "goal": self.goal,
                "step": label,
                "iteration": self.iterations,
                "detail": detail,
                "impact": dataclasses.asdict(impact),
                "totals": {
                    "files_changed": self.total_files_changed,
                    "lines_changed": self.total_lines_changed,
                },
            },
        )

        if self.limits.stop_on_scope_change:
            if self.total_files_changed > self.limits.max_files_changed:
                self.block(
                    "scope_change",
                    f"{self.name} stopped because it touched {self.total_files_changed} files, "
                    f"which exceeds the limit of {self.limits.max_files_changed}.",
                )
                raise WorkflowLimitError(
                    f"{self.name} stopped because the workflow changed too many files "
                    f"({self.total_files_changed}/{self.limits.max_files_changed})."
                )
            if self.total_lines_changed > self.limits.max_lines_changed:
                self.block(
                    "scope_change",
                    f"{self.name} stopped because it changed about {self.total_lines_changed} lines, "
                    f"which exceeds the limit of {self.limits.max_lines_changed}.",
                )
                raise WorkflowLimitError(
                    f"{self.name} stopped because the workflow changed too many lines "
                    f"({self.total_lines_changed}/{self.limits.max_lines_changed})."
                )

    def pause(self, reason: str) -> None:
        self.status = "paused"
        self._persist(extra={"reason": reason})
        memory.append_execution_trace(
            self.workspace,
            "workflow_paused",
            {
                "name": self.name,
                "goal": self.goal,
                "reason": reason,
                "iteration": self.iterations,
            },
        )

    def complete(self, summary: str) -> None:
        self.status = "completed"
        self._persist(extra={"summary": summary})
        memory.append_execution_trace(
            self.workspace,
            "workflow_completed",
            {
                "name": self.name,
                "goal": self.goal,
                "summary": summary,
                "iterations": self.iterations,
                "files_changed": self.total_files_changed,
                "lines_changed": self.total_lines_changed,
            },
        )

    def block(self, reason: str, message: str) -> None:
        self.status = "blocked"
        self._persist(extra={"reason": reason, "message": message})
        memory.append_execution_trace(
            self.workspace,
            "workflow_blocked",
            {
                "name": self.name,
                "goal": self.goal,
                "reason": reason,
                "message": message,
                "iterations": self.iterations,
                "files_changed": self.total_files_changed,
                "lines_changed": self.total_lines_changed,
            },
        )

    def _change_set_belongs_to_current_step(self, change_set: dict | None) -> bool:
        if not change_set or self._current_started_at is None:
            return False
        recorded_at = _parse_iso_timestamp(change_set.get("recorded_at"))
        if recorded_at is None:
            return False
        return recorded_at >= self._current_started_at.replace(microsecond=0)

    def _persist(self, *, extra: dict | None = None) -> None:
        metadata = memory.ensure_session_metadata(self.workspace)
        payload = {
            "name": self.name,
            "goal": self.goal,
            "status": self.status,
            "iteration": self.iterations,
            "current_step": self.current_step,
            "files_changed": self.total_files_changed,
            "lines_changed": self.total_lines_changed,
            "limits": dataclasses.asdict(self.limits),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        if extra:
            payload.update(extra)
        memory.save_session_metadata(
            self.workspace,
            {
                **metadata,
                "workflow_execution": payload,
            },
        )
