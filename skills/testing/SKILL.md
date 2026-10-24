---
name: testing
description: Design and run tests that protect user-facing workflows and regressions.
---

# Testing

## Workflow

1. Map the behavior that must stay stable.
2. Add the smallest test that would fail before the fix.
3. Prefer workflow or integration tests for operator-facing paths.
4. Keep helper tests narrow and explicit.

## Output

- Test scope
- New or updated tests
- Validation result
