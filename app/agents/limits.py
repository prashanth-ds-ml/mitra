"""Step limits for agent loops (E-002): a small model that keeps calling tools must stop."""
MAX_AGENT_STEPS = 20  # model calls per agent run


def stopped_message(steps: int = MAX_AGENT_STEPS) -> str:
    return (f"✗ Stopped after {steps} model calls without a final answer (step limit). "
            "The task may be too big for one request; split it, or ask again with more detail.")
