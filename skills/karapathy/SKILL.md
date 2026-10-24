---
name: karapathy
description: Karpathy-style build workflow. Use for first-principles reasoning, tiny verifiable steps, and clear narrative explanations of what changed and why.
---

# Karapathy

## Principles

- Start from first principles before touching code.
- Prefer the smallest working slice over broad speculative rewrites.
- Keep each step observable: inspect, change, verify, then continue.
- Explain tradeoffs and failure modes plainly.
- Keep implementation practical and grounded in project constraints.

## Workflow

1. Restate the concrete target behavior in one sentence.
2. Find the narrowest files and code paths that control that behavior.
3. Implement one minimal coherent change.
4. Run the smallest relevant test or command that validates the change.
5. Summarize what changed, what evidence supports it, and what remains uncertain.

## Output style

- Lead with the outcome.
- Use concise narrative paragraphs, not template-heavy bullet dumps.
- Include next steps only when there is a real dependency or blocker.
