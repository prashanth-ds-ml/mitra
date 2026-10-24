# Core Contracts

This document defines the smallest stable surface for CodeMitra before we add more workflows, agents, or integrations.

The rule is simple: keep the primitive tool layer narrow, keep workflows thin, and keep model routing role-based instead of one-model-for-everything.

## Goal

Build a local-first Ollama coding assistant that behaves like a small, reliable version of Claude, Copilot, Codex, or OpenCode.

That means:

- The assistant reads the workspace safely.
- The assistant writes changes only through explicit tools.
- The assistant runs commands only through gated execution.
- The assistant remembers decisions and traces every action.
- The assistant uses the right model for the right job.

## Primitive Tools

The product language can use canonical names like `list_files` and `search_text`, but the current codebase already implements those ideas under these concrete tool names:

- `list_files` -> `get_file_tree` / `list_directory`
- `read_file` -> `read_file`
- `search_text` -> `search_in_files` / `search_text`
- `create_file` -> `create_file`
- `edit_file` -> `edit_file`
- `write_file` -> `write_file` behavior through filesystem helpers
- `create_markdown_file` -> `create_markdown_file`
- `update_markdown_file` -> `update_markdown_file`
- `run_command` -> `run_command`
- `git_status` -> `git_status`
- `git_diff` -> `git_diff`

The rule is to keep the conceptual contract stable even if the implementation names are slightly different.

These are the core primitives the system should always have.

### 1. Read tools

Use these for inspection only.

- `list_files`
- `read_file`
- `search_text`
- `git_status`
- `git_diff`
- `read_document`

Optional later extension:

- deeper OCR-backed extraction for scanned images or complex PDFs

Responsibilities:

- Stay inside the project workspace.
- Never mutate files.
- Never read secrets or blocked paths.
- Return compact, useful output that is easy to summarize.

### 2. Write tools

Use these for controlled file changes.

- `create_file`
- `edit_file`
- `write_file`
- `create_markdown_file`
- `update_markdown_file`

Responsibilities:

- Stay inside the project workspace.
- Block `.env`, secret-like files, and other sensitive paths.
- Prefer explicit write operations over hidden auto-edits.
- Keep changes traceable in logs and memory.

### 3. Execution tools

Use these when the user explicitly wants the system to run something.

- `run_command`
- `git_status`
- `git_diff`

Responsibilities:

- Require approval before destructive commands.
- Require approval before install commands.
- Require approval before Docker commands.
- Respect shell whitelists and workspace boundaries.
- Return command output in a form that can be reviewed and logged.

### 4. Safety primitives

These are not optional helpers. They are part of the tool contract.

- Project root detection
- Workspace boundary enforcement
- Secret blocking
- Destructive-command confirmation
- Install confirmation
- Docker confirmation
- Trace logging for prompts, tool calls, file changes, commands, errors, and tests

## Current Repo Mapping

The current codebase already maps closely to this contract:

- `app/agents/reader.py` provides read-only inspection.
- `app/agents/filesystem.py` provides file mutation and workspace-guarded file tools.
- `app/agents/shell.py` provides command execution with restrictions.
- `app/policy.py` and filesystem guardrails enforce safety.
- `app/memory.py` captures session state, decisions, plans, and traces.
- `app/main.py` routes higher-level commands and intents to those primitives.

## What We Should Not Add Yet

To keep the system simple, do not expand beyond the primitive contract until the current layer is stable.

Avoid adding:

- More MCP integrations before the local primitives are tight.
- More agents before the primitives and workflows are stable.
- More model-routing complexity before role boundaries are clear.
- More file abstractions before the current read/write tools are coherent.

## Workflow Layer

The workflow layer should sit on top of the primitives and do only orchestration.

Minimum workflows:

- `understand`
- `brainstorm`
- `prd`
- `plan`
- `build`
- `test`
- `fix`
- `review`
- `docs`

Workflow rule:

- A workflow should call the primitive tools.
- A workflow should not reimplement primitive behavior.
- A workflow should be small enough to test directly.

## Model Routing

Use models by role, not by a single global default.

- Brainstorm / understand / PRD: best local general chat model
- Build / fix / test: coder model
- Review / decision: strong chat model
- Docs: whichever model fits the content type

This is a routing rule, not a user-facing feature.

## Test Contract

We should have tests for the contract itself, not just for features.

### Read tool tests

- Read paths stay inside the workspace.
- Read tools reject secret-like paths.
- Search returns expected matches and skips blocked files.
- File tree / read helpers work on nested directories.

### Write tool tests

- Create writes new files and parent directories correctly.
- Edit updates existing files and fails clearly for missing files.
- Markdown write helpers create both root and `.codemitra` artifacts when required.
- Sensitive paths are blocked.
- Overwrites remain traceable.

### Execution tool tests

- Allowed commands run.
- Blocked commands fail.
- Destructive commands require confirmation.
- Read-only mode suppresses subprocess execution.
- Background task behavior is tracked.

### Safety tests

- Workspace root detection works from nested directories.
- Policy rules evaluate allow / ask / deny correctly.
- Secret and destructive path rules are enforced consistently.

### CLI workflow tests

- Slash commands resolve to the correct workflow.
- `brainstorm`, `understand`, and `prd` use the idea-shaping model path.
- `build`, `fix`, and plan execution use the codegen path.
- Output is written to the expected session files.

### Regression tests

- Full suite passes before a merge.
- Any change to primitive tools must include a test.
- Any change to safety behavior must include a test.
- Any change to model routing must include a test.

## Decision

For now, the next work should be:

1. Tighten the primitive tools.
2. Keep workflows thin.
3. Keep role-based model routing.
4. Add only the tests required to prove the contract.
