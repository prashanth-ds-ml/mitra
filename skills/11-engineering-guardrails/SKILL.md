---
name: engineering-guardrails
description: Apply cautious engineering guardrails when writing, reviewing, or refactoring code so changes stay simple, surgical, explicit about assumptions, and tied to verifiable outcomes.
---

# Engineering Guardrails

Use this skill for non-trivial implementation, debugging, refactoring, and review work where the model might otherwise over-assume, overbuild, or touch unrelated code.

## Rules

- State assumptions clearly when requirements are ambiguous.
- Prefer the smallest complete solution over flexible or speculative designs.
- Touch only the code required for the task and match existing repo patterns.
- Remove only the dead code created by your own change.
- Define success in a verifiable way before declaring the work done.

## Workflow

1. Inspect the relevant files and restate the concrete goal in implementation terms.
2. Identify assumptions, tradeoffs, and any ambiguity that could change the design.
3. Choose the simplest change that fully satisfies the request.
4. Implement only the necessary edits, keeping the diff narrow and behavior-safe.
5. Validate against the intended outcome and note any remaining risk or limitation plainly.

## Output

- A concise explanation of the chosen approach and any material assumptions
- Minimal code changes that trace directly to the task
- Clear evidence of completion, or a plain statement of what remains blocked
