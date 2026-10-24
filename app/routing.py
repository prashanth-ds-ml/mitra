from __future__ import annotations

from dataclasses import dataclass
import re


DEFAULT_INTENTS = (
    "plan",
    "build",
    "fix",
    "review",
    "test",
    "document",
    "explain",
    "refactor",
    "scaffold",
    "continue",
)


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    reason: str
    workflow_hint: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "reason": self.reason,
            "workflow_hint": self.workflow_hint,
        }


class IntentRouter:
    """Heuristic router for the first milestone routing contract."""

    def __init__(self, intents: tuple[str, ...] | None = None) -> None:
        self.intents = intents or DEFAULT_INTENTS

    def classify(self, user_input: str) -> IntentDecision:
        normalized = self._normalize(user_input)
        if not normalized:
            return IntentDecision("explain", 0.2, "empty request", workflow_hint="explain")

        if normalized.startswith("/"):
            return IntentDecision("continue", 0.6, "slash command", workflow_hint="continue")

        if self._is_continue_request(normalized):
            return IntentDecision("continue", 0.95, "explicit continue request", workflow_hint="continue")

        if self._is_test_request(normalized):
            return IntentDecision("test", 0.95, "test or verification request", workflow_hint="test")

        if self._is_fix_request(normalized):
            return IntentDecision("fix", 0.95, "debugging or error-related request", workflow_hint="fix")

        if self._is_review_request(normalized):
            return IntentDecision("review", 0.95, "review or inspection request", workflow_hint="review")

        if self._is_document_request(normalized):
            return IntentDecision("document", 0.95, "documentation request", workflow_hint="document")

        if self._is_refactor_request(normalized):
            return IntentDecision("refactor", 0.95, "refactor or cleanup request", workflow_hint="refactor")

        if self._is_scaffold_request(normalized):
            return IntentDecision("scaffold", 0.92, "project or file scaffolding request", workflow_hint="scaffold")

        if self._is_build_request(normalized):
            return IntentDecision("build", 0.92, "feature implementation request", workflow_hint="build")

        if self._is_plan_request(normalized):
            return IntentDecision("plan", 0.9, "request needs a plan", workflow_hint="plan")

        if self._is_explain_request(normalized):
            return IntentDecision("explain", 0.9, "explanation or guidance request", workflow_hint="explain")

        return IntentDecision("explain", 0.4, "defaulted to explain for a general request", workflow_hint="explain")

    def _normalize(self, user_input: str) -> str:
        normalized = re.sub(r"\s+", " ", (user_input or "").strip().lower())
        return re.sub(r"[!?.,]+$", "", normalized)

    def _is_continue_request(self, normalized: str) -> bool:
        return any(
            re.search(pattern, normalized)
            for pattern in (
                r"\bcontinue\b",
                r"\bnext step\b",
                r"\bproceed\b",
                r"\bkeep going\b",
                r"\bexecute the plan\b",
            )
        )

    def _is_fix_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "error",
                "bug",
                "issue",
                "debug",
                "fail",
                "failing",
                "broken",
                "exception",
                "traceback",
                "not working",
                "why is this error",
                "why is this failing",
            )
        )

    def _is_review_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "review",
                "inspect",
                "check this",
                "look over",
                "audit",
                "critique",
                "diff",
            )
        )

    def _is_test_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "test",
                "pytest",
                "unittest",
                "verify",
                "validate",
                "run tests",
            )
        )

    def _is_document_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "document",
                "documentation",
                "docs",
                "readme",
                "write docs",
                "write documentation",
            )
        )

    def _is_refactor_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "refactor",
                "clean up",
                "simplify",
                "rewrite",
                "restructure",
                "improve the code",
                "tidy up",
            )
        )

    def _is_scaffold_request(self, normalized: str) -> bool:
        explicit_matches = any(
            phrase in normalized
            for phrase in (
                "scaffold",
                "bootstrap",
                "create a new project",
                "create a new app",
                "create a new service",
                "set up a new project",
                "set up a new app",
                "initialize a new project",
                "start a new project",
                "start a new app",
                "new project",
                "new app",
                "new service",
            )
        )
        if explicit_matches:
            return True

        has_project_creation_signal = any(
            keyword in normalized
            for keyword in ("create", "start", "set up", "initialize", "bootstrap")
        ) and any(
            keyword in normalized
            for keyword in ("project", "app", "service")
        )
        return has_project_creation_signal and not any(
            keyword in normalized
            for keyword in ("file", "folder", "directory", "venv", "virtual environment")
        )

    def _is_build_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "build",
                "develop",
                "implement",
                "ship",
                "make a",
                "create a feature",
                "add a feature",
                "add support for",
            )
        )

    def _is_plan_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "plan",
                "roadmap",
                "strategy",
                "milestones",
                "phases",
                "sequence of steps",
                "step by step",
                "work plan",
                "implementation plan",
            )
        )

    def _is_explain_request(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in (
                "what is",
                "what does",
                "why",
                "how does",
                "how do i",
                "explain",
                "understand",
                "help me understand",
            )
        )


DEFAULT_ROUTER = IntentRouter()
