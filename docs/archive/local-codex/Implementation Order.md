# Implementation Order

Use this checklist as the build sequence for the current tightening pass.

## Order

- [x] 1. Freeze the primitive contract
- [x] 2. Normalize routing
- [x] 3. Tighten context reuse
- [ ] 4. Improve edit quality
- [ ] 5. Keep document handling bounded
- [ ] 6. Polish operator UX

## Build Rules

- Do not start a later step before the earlier step is stable.
- Every change to primitives, routing, memory, or safety must include tests.
- Keep each increment small enough to verify in one pass.
- Prefer tightening existing code over adding new subsystems.

## Step Details

### 1. Freeze the primitive contract

- Lock the read/write/execute/safety boundary.
- Keep the primitive surface stable.
- Keep the contract tests green.

### 2. Normalize routing

- Use the best chat model for brainstorm, understand, and PRD.
- Use the coder model for build, fix, and test.
- Reduce heuristic over-planning.

### 3. Tighten context reuse

- Feed `understand` into `prd`.
- Feed `prd` into `plan`.
- Use memory files as the source of truth.

### 4. Improve edit quality

- Make diffs smaller and more precise.
- Keep approvals and undo behavior intact.
- Preserve safety gates.

### 5. Keep document handling bounded

- Keep `read_document` as the canonical document primitive.
- Support DOCX, simple PDF, and image metadata.
- Defer OCR-heavy extraction.

### 6. Polish operator UX

- Reduce unnecessary planning for simple tasks.
- Improve status and progress messaging.
- Keep the CLI predictable and local-first.
