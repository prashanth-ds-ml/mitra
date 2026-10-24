---
title: Roadmap
tags: [roadmap, planning, phases]
aliases: [Build Plan, Phases]
---

# Roadmap

CodeMitra is being built incrementally, one capability layer at a time. Each phase is self-contained and testable before the next begins.

This doc is the historical milestone and product roadmap view. For the current v1 tightening sequence, use [[V1 Roadmap]]. For the active layered implementation sequence now being followed, use [[Phased Rollout]]. For product behavior targets, use [[Product Blueprint]]. For the Claude-specific benchmark and gaps, use [[Claude Code Reference]] and [[Claude Code Comparison]].

---

## Phase 1 — Project foundation ✅

- [x] Project structure (`app/`, `misc/`, `pyproject.toml`)
- [x] `codemitra` CLI entry point
- [x] Virtual environment + dependencies
- [x] Config module (model names)
- [x] Banner with ASCII avatar and taglines

---

## Phase 2 — Chat core ✅

- [x] `get_chat_llm()` — `qwen2.5-coder:7b`
- [x] `get_agent_llm()` — `qwen3.5:latest`
- [x] System prompt
- [x] In-memory message history
- [x] Chat loop (input → LLM → Rich panel)

---

## Phase 3 — Filesystem agent ✅

- [x] Tool: `create_folder`
- [x] Tool: `create_file`
- [x] Tool: `read_file`
- [x] Tool: `list_directory`
- [x] Tool: `delete_file`
- [x] Tool: `delete_folder`
- [x] Tool: `move_file`
- [x] Tool: `create_venv`
- [x] Tool: `install_packages`
- [x] Tool: `run_command`
- [x] `PermissionGuard` — workspace + command whitelist
- [x] Agent loop (LLM → tool calls → results → repeat)
- [x] `ToolResult`, `AgentResponse`, `render()` templates

---

## Phase 4 — Routing ⚠️

- [x] Verified agent model supports structured tool calling
- [x] `setup_project` routing tool bound to chat LLM
- [x] Main loop handles `tool_calls` → delegates to filesystem agent
- [x] Follow-up reply after agent completes
- [ ] End-to-end test with `qwen3.5:latest` as agent

---

## Phase 5 — Code reader agent ✅

- [x] `read_file` (reuse)
- [x] `list_directory` (reuse)
- [x] `search_in_files` — grep pattern across a directory
- [x] `get_file_tree` — full nested directory tree as text
- [x] `find_definition` — locate def/class/constant by name
- [x] `grep_symbol` — find all usages of a symbol

Agent behaviour:
- [x] System prompt tuned for code understanding
- [x] Can answer: "what does X do?", "find where Y is called", "summarise this file"
- [x] Routing: chat LLM detects code-reading intent → delegates

---

## Phase 6 — Shell agent ✅

- [x] `run_command` (reuse, extended)
- [x] Streaming stdout back to the LLM mid-run
- [x] Timeout + kill handling
- [x] Command whitelist (`python`, `pytest`, `git`, `npm`, `ruff`, `mypy`, `black`, `uvicorn`, …)
- [x] `ShellResult` — exit code, output, timed_out, denied flags
- [x] Routing: "run the tests", "start the server", "build the project"

---

## Phase 7 — Planner agent ✅

- [x] Takes a large, multi-step task
- [x] Breaks it into an ordered list of sub-tasks
- [x] Routes each sub-task to the correct agent (filesystem / code reader / shell)
- [x] Collects results, handles partial failures, writes a summary
- [x] Writes and reads `.codemitra/plan.md` with completion markers

---

## Phase 8 — Memory ✅

- [x] `.codemitra/activity.md` — append-only activity log
- [x] `.codemitra/context.md` — project context (editable)
- [x] `.codemitra/plan.md` — active plan with step checkboxes
- [x] `.codemitra/README.md` — vault index
- [x] Load context on startup so the LLM knows the project
- [x] Cross-session memory: context persists between sessions

---

## Phase 9 — Brainstorm loop ✅

- [x] `/plan` runs clarifying Q&A before generating plan steps
- [x] Up to 5 rounds of questions (max 3 questions per round)
- [x] `READY_TO_PLAN` signal when model has enough context
- [x] Full Q&A context passed to `create_plan()` for specific steps

---

## Phase 10 — Trust layer: diff preview + approvals 🔲

- [x] Show diff/summary before bulk file writes (confirm Y/N)
- [x] Add explicit permission modes (`read-only`, `plan`, `approve`, `auto`)
- [x] Separate approvals for file edits and shell commands, with workspace scope still enforced
- [x] Add undo / rewind for the last change set

---

## Phase 11 — Repair loop + operator commands 🔲

- [x] `/fix <command>` — run a bounded repair loop against a failing command
- [x] `run pytest -> read failures -> generate fix -> run again` loop (max 3 attempts)
- [x] `/diff` — inspect pending changes
- [x] `/review` — run reviewer agent on changed files or the last CodeMitra change set
- [x] `/explain <file>` — explain what a file does

---

## Phase 12 — Session UX 🔲

- [x] Named sessions
- [x] `/resume`, `/history`, `/rename`
- [x] Better task / progress timeline in the terminal UI
- [x] Clear model, usage, and current-task visibility
- [x] Persistent prompt toolbar with mode, model, cwd, context load, and task state
- [x] `/context` for live context-window usage
- [x] `/permissions` for live policy visibility
- [x] `/hibernate` for low-memory recovery after saving session state
- [x] Prompt-in-editor with `Ctrl+G`
- [x] Background shell tasks with `/run --background <cmd>` and `/tasks`
- [x] Plan-step checkpoint in session metadata so `/resume` can show interrupted or completed plan execution state
- [x] Explicit plan approval and controls with `/plan approve`, `/plan next`, `/plan run`, and `/plan pause`
- [x] Compaction checkpoint in session metadata so `/resume` can show the last manual or automatic compact event
- [ ] Improve `/compact` and automatic compaction controls and previews

---

## Phase 13 — Project auto-detect + code intelligence 🔲

- [x] On startup, scan README + entry points + file tree
- [x] Inject a concise project brief as startup context so the LLM knows the workspace without being told
- [ ] Skip manual `/context` load for known project layouts
- [x] Add a dedicated symbol lookup / references workflow
- [x] Add LSP-backed diagnostics when available

---

## Phase 14 — Extensibility + policy controls ✅ In progress

- [x] Configurable allowed directories and tool policies
- [x] Project-level instruction loading from configured workspace files
- [x] Workspace CodeMitra skill discovery with `/skills` and `/skills show <name>`
- [x] Tab-to-amend shell approval — edit a proposed command inline before approving it
- [ ] MCP server support
- [x] Plugin or custom slash command extension points

---

## Phase 16 — Hardware-aware model routing ✅

- [x] GPU VRAM detection via `nvidia-smi`
- [x] System RAM detection via `psutil` / platform fallback
- [x] Three-tier placement: full-GPU 🟢, GPU+CPU split 🟡, CPU-only 🔴
- [x] Model picker shows placement badge alongside each Ollama model
- [x] `/recommend` — scores every installed Ollama model for chat / code / agent roles, ranks by hardware fit, and offers to write the winner to `codemitra.toml`
- [x] 17 unit tests covering recommend_models, format_recommendations, apply_to_toml, get_best_local_model

---

## Phase 17 — Guided artifact builder ✅

- [x] `/create` — conversational wizard for Skill, Workflow, and Agent artifact types
- [x] Q&A banks per type: 8 questions for Skills, 6 for Workflows, 6 for Agents; conditional questions via `depends_on`
- [x] LLM generates the full artifact from collected answers; displayed in a Rich syntax preview panel
- [x] Approve / Regenerate / Regenerate-with-corrections / Cancel loop
- [x] Skill saved to `skills/<slug>/SKILL.md` and re-discovered in the same session
- [x] Workflow saved to `.codemitra/workflows/<slug>/WORKFLOW.md`
- [x] Agent saved to `app/agents/<slug>.py` + `_WIRING.md` wiring guide
- [x] 41 unit tests covering all pure-logic functions in `builder.py`

---

## Phase 15 — Git-aware workflows 🔲

- [x] Git diff-aware review flow
- [x] Branch-aware `/status` summary with upstream and working-tree counts
- [x] Commit-readiness summary in `/status`
- [ ] Commit message / commit-content summaries
- [ ] Stronger review-before-commit workflow
- [ ] Optional IDE / editor handoff later

---

## Current next steps

### P0 — Immediate bugs / missing wiring (do first)

1. **Wire GPU `num_gpu` to LLM init** — `get_num_gpu_for_placement()` exists but is never passed to `get_local_llm()`; one-line fix in `_chat()` in `main.py`
2. **nvidia-smi bounds check** — `splitlines()[0]` in `config.get_gpu_vram_gib()` crashes if driver returns empty output; add `if not lines: return None`
3. **Add `tomli_w` and `psutil` to `requirements.txt`** — both are used in `advisor.py` and `config.py` but missing from the manifest
4. **Complete `/fix` loop** — handler exists; bounded retry logic is incomplete
5. **Complete `/undo` file rollback** — skeleton present, revert logic needed

### P1 — High-value product gaps (next 2-4 weeks)

6. **LSP-backed code intelligence** — diagnostics, goto-definition, references, hover; integrate `python-lsp-server` / `pyright` / `typescript-language-server` with fallback to grep
7. **Richer policy engine** — move from mode-centric to deny-first rule engine with allow/ask/deny categories, path-scoped rules, precedence model
8. **Better compaction preservation** — preserve key decisions, changed files, failures, plan state; define reinjection rules; add circuit-breaker for repeated compaction
9. **Stronger review-before-commit workflow** — commit message helper, staged/unstaged guidance, pre-commit validation gate

### P2 — Platform foundation (next 1-2 months)

10. **Layered settings model** — user-level defaults, project settings, local gitignored overrides, CLI/session overrides
11. **Internal event bus + first hooks** — pre-tool, post-tool, session-start, session-end, compact-complete
12. **Skill model evolution** — decide: docs vs executable workflow units; add args, model override, pre-approved tools, auto-invocation
13. **True subagent runtime boundary** — fresh context, tool restriction, result summarization, permission behavior for delegated work

### P3 — Extensibility platform (later)

14. **MCP support** — client, server transport, namespaced tools, deferred schema loading, MCP permission controls
15. **Custom agents** — user-defined agent definitions with tool allowances
16. **Advanced tool and policy controls** — network/domain sandbox rules, managed config layering

### P4 — Scaled parallel workflows (future)

17. **Worktree orchestration** — session branching, worktree creation/switching/cleanup, task decomposition across isolated branches
18. **Batch parallel task decomposition** — parallel orchestration layer beyond background shell tasks
19. **Deeper git / PR-aware workflows** — PR review loop, GitHub-aware context

---

## Summary table

| Phase | Description | Status |
|---|---|---|
| 1 | Foundation | ✅ Done |
| 2 | Chat core | ✅ Done |
| 3 | Filesystem agent | ✅ Done |
| 4 | Routing | ✅ Done |
| 5 | Code reader agent | ✅ Done |
| 6 | Shell agent | ✅ Done |
| 7 | Planner agent | ✅ Done |
| 8 | Memory vault | ✅ Done |
| 9 | Brainstorm loop | ✅ Done |
| 10 | Trust layer: diff preview + approvals | ✅ Done |
| 11 | Repair loop + operator commands | ✅ Done |
| 12 | Session UX | ✅ Mostly done |
| 13 | Project auto-detect + code intelligence | ✅ Done |
| 14 | Extensibility + policy controls | ✅ Done |
| 15 | Git-aware workflows | ✅ In progress |
| 16 | Hardware-aware model routing + `/recommend` | ✅ Done |
| 17 | Guided artifact builder `/create` | ✅ Done |

---

## See also

- [[Vision]]
- [[Product Blueprint]]
- [[Claude Code Reference]]
- [[Claude Code Comparison]]
