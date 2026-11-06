"""Limits for agent loops: a small model that keeps calling tools must stop (E-002, E-023)."""
from __future__ import annotations

import json

MAX_AGENT_STEPS = 20  # model calls per agent run


def stopped_message(steps: int = MAX_AGENT_STEPS) -> str:
    return (f"✗ Stopped after {steps} model calls without a final answer (step limit). "
            "The task may be too big for one request; split it, or ask again with more detail.")


class RepeatGuard:
    """Stops the same call being made over and over (E-023: 100+ identical web searches).

    before(): returns a tool result to send instead of running a call already made `max_repeats` times.
    after(): returns a stop message once one tool has failed `max_failures` times in a row.
    """

    def __init__(self, *, max_repeats: int = 1, max_failures: int = 3) -> None:
        self.max_repeats, self.max_failures = max_repeats, max_failures
        self._calls: dict[str, int] = {}
        self._fail_tool = ""
        self._fail_count = 0
        self._repeats_refused = 0

    @staticmethod
    def _key(name: str, args: dict) -> str:
        try:
            return name + json.dumps(args or {}, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return name + repr(args)

    def before(self, name: str, args: dict) -> str | None:
        key = self._key(name, args)
        self._calls[key] = self._calls.get(key, 0) + 1
        if self._calls[key] > self.max_repeats:
            return (f"✗ Not run: {name} was already called with these exact arguments; the result will not change. "
                    "Use the result you have, try different arguments, or give your answer now.")
        return None

    def after(self, name: str, output: str) -> str | None:
        if str(output).startswith("✗ Not run:"):
            self._repeats_refused += 1
            if self._repeats_refused >= self.max_failures:
                return (f"✗ Stopped: the model kept repeating the same {name} call "
                        f"({self._repeats_refused} repeats refused) instead of answering.")
            return None
        failed = str(output).lstrip().startswith("✗")
        if not failed:
            self._fail_tool, self._fail_count = "", 0
            return None
        if name == self._fail_tool:
            self._fail_count += 1
        else:
            self._fail_tool, self._fail_count = name, 1
        if self._fail_count >= self.max_failures:
            first = str(output).strip().splitlines()[0][:200]
            return f"✗ Stopped: {name} failed {self._fail_count} times in a row. Last error: {first.lstrip('✗ ')}"
        return None
