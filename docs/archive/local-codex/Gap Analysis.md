---
title: Gap Analysis & Build Order
tags: [gap-analysis, roadmap, priorities, planning]
aliases: [Build Plan, Gap Analysis, Implementation Priorities]
---

# Gap Analysis & Build Order

*Generated from session analysis of Vision, Roadmap, Product Blueprint, Claude Code Comparison, and Architecture docs.*

---

## Current State Summary

**What's Working (Strong Baseline)**
- Core agent loop: 5 routing tools → 12 specialized agents
- Trust UX: 4 session modes (`read-only`, `plan`, `approve`, `auto`), diff preview, undo, `/fix`, `/review`
- Session controls: `/resume`, `/compact`, `/hibernate`, `/tasks`, named sessions
- Memory vault: `.codemitra/` with `activity.md`, `context.md`, `plan.md`, `session.json`
- Hardware-aware routing: GPU/CPU placement detection, `/recommend` model advisor
- Extensibility basics: Skills discovery, `/create` guided builder, plugin hooks
- 425 passing tests — solid regression coverage

**Key Insight from Docs**: The gap is in the **platform substrate**, not the chat surface. CodeMitra already has strong visible UX; the missing pieces are LSP integration, policy engine, event bus/hooks, and runtime boundaries.

---

## Prioritized Gap Analysis

| Priority | Gap | Why It Matters | Effort | Source |
|----------|-----|----------------|--------|--------|
| **P0** | Wire `num_gpu` to LLM init | GPU placement detected but never passed to `get_local_llm()` | 1 line fix | Roadmap P0 #1 |
| **P0** | Fix `nvidia-smi` bounds check | Crashes if driver returns empty output | 1 line fix | Roadmap P0 #2 |
| **P0** | Add `tomli_w`, `psutil` to `requirements.txt` | Used in advisor/config but missing from manifest | 2 lines | Roadmap P0 #3 |
| **P0** | Complete `/fix` loop | Handler exists; bounded retry logic incomplete | Medium | Roadmap P0 #4 |
| **P0** | Complete `/undo` file rollback | Skeleton present; revert logic needed | Medium | Roadmap P0 #5 |
| **P1** | **LSP-backed code intelligence** | Diagnostics, goto-def, references — biggest quality gap | Large | Comparison #2, Blueprint P2 |
| **P1** | **Richer policy engine** | Move from mode-centric → rule-centric (allow/ask/deny) | Large | Comparison #3, Blueprint P1 |
| **P1** | **Better compaction preservation** | Preserve decisions, changed files, plan state, failures | Medium | Comparison #11, Blueprint P1 |
| **P1** | **Stronger review-before-commit** | Commit helper, staged/unstaged guidance, pre-commit gate | Medium | Comparison #12, Blueprint P1 |
| **P2** | Layered settings model | User/project/local/CLI precedence for extensibility | Medium | Comparison #4, Blueprint P2 |
| **P2** | Internal event bus + hooks | pre-tool, post-tool, session lifecycle, compaction | Medium | Comparison #6, Blueprint P2 |
| **P2** | Skill model evolution | Decide: docs vs executable workflow units | Medium | Comparison #5, Blueprint P2 |
| **P2** | True subagent runtime | Fresh context, tool restriction, result summarization | Large | Comparison #8, Blueprint P2 |
| **P3** | MCP support | External tool ecosystem integration | Very Large | Comparison #7, Blueprint P2 |
| **P3** | Custom agents | User-defined agent definitions | Large | Comparison #8, Blueprint P3 |
| **P4** | Worktree orchestration | Session branching, isolated parallel work | Very Large | Comparison #9, Blueprint P4 |

---

## Recommended Build Order (4 Phases)

### Phase 1 — "Trust & Polish" (1-2 weeks)
*Low-risk, high-confidence fixes that complete existing features*

| Task | Description | Est. Time | Status |
|------|-------------|-----------|--------|
| P0 fixes | Wire `num_gpu`, fix `nvidia-smi` bounds, add missing deps | 1 day | ✅ **Done** |
| Complete `/fix` loop | Bounded retry logic for test-fix-retry workflow | 2 days | ✅ **Done** |
| Complete `/undo` rollback | Revert logic for last change set | 2 days | ✅ **Done** |
| Better compaction preservation | Preserve key decisions, changed files, failures, plan state | 3 days | ✅ **Done** |
| Stronger review-before-commit | Commit helper (`/commit --generate`), staged/unstaged guidance | 3 days | ✅ **Done** |

**Exit Criteria**: ✅ Compaction preserves structured artifacts (plan, change sets, failures); ✅ Review workflow includes commit readiness and commit message helper.

---

### Phase 2 — "Intelligence & Policy" (2-4 weeks)
*Highest-value technical upgrades for day-to-day coding quality*

| Task | Description | Est. Time | Status |
|------|-------------|-----------|--------|
| LSP-backed diagnostics | Integrate `python-lsp-server` / `pyright` / `typescript-language-server` | 1 week | ✅ **Done** |
| LSP goto-definition + references | Precise symbol navigation, hover/signature support | 1 week | ✅ **Done** |
| Richer policy engine | Deny-first rule engine: allow/ask/deny, path/tool/command scopes, precedence | 1 week | ✅ **Done** |
| Layered config model | User-level defaults, project settings, local gitignored overrides, CLI/session overrides | 3 days | ✅ **Done** |

**Exit Criteria**: ✅ LSP diagnostics working for Python/TS; ✅ Policy engine replaces mode-centric checks; ✅ Config layering supports extensibility.

---

### Phase 3 — "Platform Foundation" (1-2 months)
*Architectural substrate for true extensibility*

| Task | Description | Est. Time |
|------|-------------|-----------|
| Internal event bus + 5 core hooks | pre-tool, post-tool, session-start, session-end, compact-complete | 1 week |
| Skill model evolution | Executable workflow units: args, model override, pre-approved tools, auto-invocation | 1 week |
| True subagent runtime boundary | Fresh context, tool restriction, result summarization, permission behavior | 2 weeks |
| MCP client/server transport | Namespaced tools, deferred schema loading, MCP permission controls | 3 weeks |

**Exit Criteria**: Hooks enable policy/observability without hardcoding; skills become executable; subagents run isolated; MCP servers connect.

---

### Phase 4 — "Scale & Ecosystem" (Later)
*Parallel workflows and deeper git integration*

| Task | Description |
|------|-------------|
| Worktree orchestration | Session branching, worktree creation/switching/cleanup, task decomposition across branches |
| Batch parallel task decomposition | Parallel orchestration layer beyond background shell tasks |
| Git/PR-aware workflows | PR review loop, GitHub-aware context, commit message helpers |
| Custom agents | User-defined agent definitions with tool allowances |

---

## Architecture Decision Points (Need Explicit Choices)

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **LSP server for Python** | `python-lsp-server` (pure Python, Jedi-based) vs `pyright` (Microsoft, faster, TypeScript-based) | `pyright` for better type intelligence; `python-lsp-server` for lighter deps |
| **Policy engine DSL** | Minimal JSON/YAML rules vs deny-first matcher with glob/path scopes | Start with deny-first matcher; YAML config for rules |
| **Event bus sync/async** | Synchronous (blocking) hooks vs async (fire-and-forget) | Synchronous for safety (pre-tool can veto); async for post-tool |
| **Skill execution model** | Remain markdown playbooks vs become executable workflow units | Decide explicitly — executable units needed for true extensibility |

---

## Cross-Reference Map

| Doc | Relevant Sections |
|-----|-------------------|
| `docs/Roadmap.md` | Phases 1-17, P0-P4 next steps, Summary table |
| `docs/Vision.md` | Gap table (lines 60-77), Long-term goal (lines 83-94) |
| `docs/Product Blueprint.md` | Competitive baseline (lines 30-50), Priority tables (lines 90-128), Target behavior specs |
| `docs/Claude Code Comparison.md` | Executive summary (lines 47-76), Detailed gap analysis (lines 165-490), Priority order (lines 547-575) |
| `docs/Architecture.md` | System diagram, Component breakdown, Design decisions |

---

## Session Continuation Note

**Completed**: 
- Comprehensive gap analysis documented from all architecture/product docs
- **Phase 1 P0 fixes**: All 5 items already complete (verified by 425 passing tests)
- **Better compaction preservation**: Enhanced `_compact()` to explicitly include plan state, change sets, and recent failures in the compaction summary and metadata
- **Stronger review-before-commit**: Added `/commit` command with `--generate` flag for auto-suggesting conventional commit messages from diff
- **Phase 2 — Intelligence & Policy**: All 4 tasks complete (verified by 456 passing tests)
  - LSP-backed diagnostics (`diagnostics.py` with pyright/TS server)
  - LSP goto-definition + references (`codeintel.py` with LSP + grep fallback)
  - Richer policy engine (`policy.py` deny-first YAML rule engine, `/policy` command)
  - Layered config model (`config.py` 5-layer precedence, `/config` command)

**Pending**: 
- Phase 3 — Platform Foundation (event bus, executable skills, subagent runtime, MCP)

**Files Inspected**: All docs/*.md, AGENTS.md, pyproject.toml, codemitra.toml, app/agents/*.py, app/main.py, app/memory.py, app/llm.py, app/config.py

**Files Changed (this session)**: 
- `docs/Gap Analysis.md` (updated Phase 2 status)
- `app/policy.py` (new: deny-first policy engine)
- `app/agents/diagnostics.py` (added `request_definition`, `request_references`, `_collect_symbol_info`)
- `app/agents/codeintel.py` (rewritten to use LSP for symbol lookup)
- `app/agents/filesystem.py` (integrated policy engine)
- `app/agents/shell.py` (integrated policy engine)
- `app/config.py` (added layered config loading, deep merge, save functions)
- `app/main.py` (added `/policy` and `/config` commands)
- `tests/test_diagnostics.py` (new: 6 tests for LSP symbol lookup)
- `tests/test_policy.py` (new: 13 tests for policy engine)
- `tests/test_config_layered.py` (new: 12 tests for layered config)

**Next Recommended Action**: Phase 3 — Internal event bus + hooks, skill model evolution, true subagent runtime, MCP support.

**Recommended Model for Next Session**: Qwen Coder (efficient for focused coding tasks) or Nemotron 3 Ultra if architectural decisions needed.