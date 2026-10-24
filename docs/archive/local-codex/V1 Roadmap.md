# V1 Roadmap

This roadmap defines the next tightening pass for CodeMitra.

The goal is not to add more surface area. The goal is to make the current local-first assistant more reliable, more predictable, and easier to extend later.

## V1 Goal

Build a local-first Ollama assistant that feels like a small, trustworthy version of Claude, Codex, Copilot, or OpenCode.

V1 should emphasize:

- Stable primitive tools
- Role-based model routing
- Thin workflows on top of the primitives
- Safe file and shell behavior
- Clear logs, memory, and decision traces

## What V1 Is Not

V1 is not:

- More MCP integration
- More agent types
- More UI surfaces
- Full OCR / scanned-PDF support
- Worktree orchestration
- Parallel task scheduling

Those can wait.

## Milestone 1: Freeze the primitive contract

### Scope

- Keep read, write, execute, and safety as the core layers.
- Treat `reader`, `filesystem`, `shell`, `policy`, and `memory` as the stable primitive boundary.
- Keep `read_document` as the canonical document-read primitive for now.
- Avoid adding new low-level tool categories unless there is a clear need.

### Acceptance tests

- The reader surface remains read-only.
- The filesystem surface still contains the mutation tools.
- The shell surface still exposes command execution through the routed tool.
- Workspace boundary and secret-path tests continue to pass.
- The full suite stays green.

## Milestone 2: Normalize routing

### Scope

- Use the best general chat model for brainstorming, understanding, and PRD drafting.
- Keep build, fix, and test flows on the coder model path.
- Keep review and decision behavior separate from code generation.
- Reduce heuristic detours for simple actions.

### Acceptance tests

- Brainstorm, understand, and PRD prompts follow the idea-shaping model path.
- Build and fix prompts follow the codegen path.
- Routing tests confirm the selected model path per workflow.
- Simple action prompts still execute without unnecessary planning.

## Milestone 3: Tighten context reuse

### Scope

- Make `understand` feed `prd` more reliably.
- Make `prd` feed `plan` more reliably.
- Keep memory files as the source of truth for project state.
- Reduce repeated questions when the answer is already in workspace memory.

### Acceptance tests

- `understand` output is persisted and reused by `prd`.
- `prd` loads existing context instead of starting from scratch.
- `plan` can consume the prior context without losing the main goal.
- Resume and memory tests continue to pass.

## Milestone 4: Improve edit quality

### Scope

- Make file edits smaller and more precise.
- Improve review feedback when changes are incomplete or risky.
- Keep destructive, install, and Docker operations explicitly gated.
- Preserve undo behavior for the last change set.

### Acceptance tests

- Edit and overwrite tests continue to pass.
- Diff preview and approval behavior continue to pass.
- Undo / rollback tests continue to pass.
- Destructive command tests continue to pass.

## Milestone 5: Keep document handling bounded

### Scope

- Keep `read_document` as the main document read primitive.
- Support `.docx`, simple `.pdf`, and image metadata reads.
- Defer richer OCR and scanned-document support until there is a proven need.

### Acceptance tests

- DOCX extraction returns readable text.
- Simple PDF extraction returns readable text or a clear fallback message.
- Image reads return metadata such as format and dimensions.
- Unsupported document types fail clearly.

## Milestone 6: Polish the operator flow

### Scope

- Reduce unnecessary planning prompts for simple tasks.
- Improve progress, status, and error messages.
- Keep the terminal flow predictable and easy to follow.
- Preserve local-first behavior and explicit visibility into state.

### Acceptance tests

- Session UX tests continue to pass.
- Status and toolbar outputs remain consistent.
- Intent routing tests still classify simple and complex requests correctly.
- No safety regression is introduced by UX changes.

## V1 Exit Criteria

V1 is ready when:

- The primitive tool boundary is stable.
- Routing is role-based and predictable.
- Context reuse is reliable across the idea-to-plan flow.
- File edits remain safe and reviewable.
- Document reading is good enough for normal project work.
- The full test suite stays green.

## Current Status

- Milestone 1: complete
- Milestone 2: complete
- Milestone 3: complete
- Milestone 4: next

## Testing Rule

Any change to the following must include tests:

- Primitive tools
- Safety behavior
- Routing behavior
- Memory persistence
- Document reading

## Recommended Build Order

1. Freeze the primitive contract
2. Normalize routing
3. Tighten context reuse
4. Improve edit quality
5. Keep document handling bounded
6. Polish the operator flow
