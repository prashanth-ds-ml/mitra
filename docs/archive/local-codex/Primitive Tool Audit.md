# Primitive Tool Audit

This audit compares the current repository against the core contract in `docs/Core Contracts.md`.

The short conclusion is:

- The repo already has a usable primitive tool layer.
- The layer is split across multiple modules, which is acceptable for now.
- The main remaining gap is richer OCR / PDF extraction depth for `read_document`.
- The next work should tighten, not expand.

## What Is Already In Place

### Read primitives

The repo already has strong inspection tools:

- `app/agents/reader.py:146` `get_file_tree`
- `app/agents/reader.py:189` `read_file`
- `app/agents/reader.py:216` `search_in_files`
- `app/agents/reader.py:259` `find_definition`
- `app/agents/reader.py:291` `grep_symbol`

The filesystem layer also exposes a separate read tool:

- `app/agents/filesystem.py:347` `read_file`
- `app/agents/filesystem.py:386` `list_directory`

### Write primitives

The repo already has the core mutation tools:

- `app/agents/filesystem.py:260` `create_file`
- `app/agents/filesystem.py:362` `edit_file`
- `app/agents/filesystem.py:674` `create_markdown_file`
- `app/agents/filesystem.py:682` `update_markdown_file`
- `app/agents/filesystem.py:269` `write_file` behavior exists through the filesystem tool layer and helpers

The destructive helpers are also present and guarded:

- `app/agents/filesystem.py:445` `delete_file`
- `app/agents/filesystem.py:480` `delete_folder`
- `app/agents/filesystem.py:503` `move_file`

### Execution primitives

- `app/agents/shell.py:621` `run_shell`
- `app/agents/shell.py:687` `run_command`
- `app/agents/filesystem.py:620` `git_status`
- `app/agents/filesystem.py:637` `git_diff`

### Memory and trace primitives

The session and memory layer is already present:

- `app/memory.py:49` activity logging
- `app/memory.py:205` brainstorm notes
- `app/memory.py:213` understand notes
- `app/memory.py:221` PRD loading
- `app/memory.py:275` understand writing
- `app/memory.py:305` PRD writing
- `app/memory.py:340` brainstorm append
- `app/memory.py:423` decisions log
- `app/memory.py:437` error log
- `app/memory.py:452` task board
- `app/memory.py:605` memory initialization

## Guardrails Already Working

The current repo already enforces the important boundaries:

- `app/agents/filesystem.py:93` workspace and allowed-root checks
- `app/agents/filesystem.py:103` secret / environment file blocking
- `app/agents/filesystem.py:41` destructive tool classification
- `app/agents/filesystem.py:77` confirmation plumbing
- `app/agents/filesystem.py:953` write-preview approval path
- `app/agents/shell.py:1` shell execution is separated from file mutation
- `app/policy.py` provides command and tool policy evaluation

## Overlap And Duplication

The repo is functional, but some primitives are duplicated across modules.

The intended canonical contract names are documented in `docs/Core Contracts.md`; the implementation may expose slightly different helper names, but the role of each primitive should remain stable.

### File reading exists in two places

- `app/agents/reader.py` is the natural read-only inspection layer.
- `app/agents/filesystem.py` also has `read_file`.

That duplication is not fatal, but it creates ambiguity about which layer is canonical.

### Git inspection exists in two places

- `app/agents/filesystem.py` includes `git_status` and `git_diff`.
- `app/main.py` also exposes git-related reporting through higher-level status surfaces.

This is fine as long as the lower-level primitive remains the source of truth.

### Markdown writes are special cases of file writes

- `create_markdown_file`
- `update_markdown_file`

These are useful, but they are not separate primitive categories. They are convenience wrappers over the write layer.

## Real Gaps

### No first-class document reader

The biggest functional gap is the lack of a dedicated primitive for non-text inputs:

- PDF
- DOCX
- images
- OCR-backed extraction

The current repo is strong for text and code, but not yet a complete universal read layer.

### Tool naming is not fully normalized

The contract uses labels like `list_files` and `search_text`, but the codebase currently uses names like:

- `get_file_tree`
- `list_directory`
- `search_in_files`

This is not a product problem, but it is a clarity problem. The contract should eventually normalize around a single naming scheme.

### Model routing is role-based but not fully formalized

The routing for brainstorm / understand / PRD is improved, but the repo still needs a clearer documented contract for:

- idea shaping
- code generation
- review
- decision making

That is a documentation and architecture gap, not a blocking implementation bug.

## Test Coverage Status

The current test suite is strong and already proves the base contract:

- workspace safety
- destructive confirmation
- file creation and editing
- line-based reading
- search and symbol lookup
- shell whitelist and read-only mode
- memory persistence
- policy evaluation

Current full suite status: `531 passed`.

### Good coverage already exists for

- `tests/test_reader.py`
- `tests/test_filesystem.py`
- `tests/test_shell.py`
- `tests/test_policy.py`
- `tests/test_memory_phase2.py`

### What is still missing in tests

- Deeper OCR / complex-PDF coverage for `read_document`
- A canonical naming contract test for the primitive tool surface
- A single audit test that asserts the primitive tool layer does not grow without an explicit decision

## Recommended Next Steps

### Phase 1: Freeze the primitive contract

- Keep the current read/write/execute/safety layers.
- Treat them as the baseline interface.
- Do not add new workflow capabilities yet.

### Phase 2: Normalize naming

- Decide whether the canonical public names are the current implementation names or a new normalized set.
- Keep backwards-compatible aliases if needed.

### Phase 3: Expand document reading if needed

- Keep `read_document` as the canonical read primitive for documents.
- Add richer OCR / complex-PDF extraction only when there is a real need.
- Keep it separate from code and file mutation tools.

### Phase 4: Tighten workflow routing

- Brainstorm / understand / PRD should use the best general chat model.
- Build / fix / test should use the coder model.
- Review / decision should remain separate from code generation.

### Phase 5: Keep the audit alive

- Any new primitive tool must come with tests.
- Any new safety rule must come with tests.
- Any routing change must come with tests.

## Decision

Do not expand yet.

The current codebase is good enough to serve as the local-first foundation. The right next move is to tighten the primitive contract, remove ambiguity, and only then add missing capability where there is a clear user-facing need.
