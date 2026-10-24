# CodeMitra — Agent Instructions

## Quick Reference

| Action | Command |
|--------|---------|
| Run tests | `python -m pytest tests/ -v` |
| Run single test | `python -m pytest tests/test_<name>.py::TestClass::test_name -v` |
| Install deps | `pip install -e .` |
| Run CLI | `codemitra` (after `pip install -e .`) |
| Activate venv | `.venv\Scripts\activate` (Windows) |

## Project Overview

**CodeMitra** = Local, offline AI coding assistant powered by Ollama. Multi-agent CLI with filesystem, shell, planner, reader, code-intel, reviewer, session, web agents. Entry point: `app/main.py` (Typer CLI).

**Key directories:**
- `app/` — Core application (main, config, llm, agents/, memory, skills, plugins)
- `app/agents/` — 12 specialized agents (filesystem, shell, reader, planner, codeintel, diagnostics, explainer, reviewer, session, web, response, brainstorm)
- `skills/` — Built-in skill playbooks (`SKILL.md` format)
- `tests/` — 561 unit/integration tests
- `docs/` — Architecture & product docs (Vision, Roadmap, Product Blueprint, Claude Code Comparison)

## Development Workflow

1. **Always run tests before marking complete** — `python -m pytest tests/ -v`
2. **No lint/typecheck configured** — Project uses pytest only; no ruff, mypy, pre-commit
3. **Virtual env required** — Create `.venv` and activate before installing
4. **Editable install** — Use `pip install -e .` for development

## Architecture Notes (Non-Obvious)

- **Single shared LLM** — One `ChatOllama` instance used for chat + all agents (see `app/llm.py`)
- **Routing via tools** — Main loop binds 5 routing tools (`setup_project`, `run_command`, `read_codebase`, `execute_plan`, `browse_web`) to the shared LLM
- **PermissionGuard** — All filesystem ops checked against workspace root; destructive tools require confirmation
- **Shell whitelist** — Only allowed commands (python, pytest, git, npm, ruff, mypy, black, uvicorn, etc.) can execute
- **Memory vault** — `.codemitra/` folder with `activity.md`, `context.md`, `plan.md`, `session.json`
- **Skills are markdown** — Discovered from `skills/*/SKILL.md` and `.codemitra/skills/*/SKILL.md`; loaded as compact index at startup
- **GPU/CPU placement** — `config.py` detects hardware, classifies models (full-GPU 🟢, split 🟡, CPU-only 🔴); `advisor.py` scores models per role

## Common Pitfalls

- **Don't assume cloud LLM** — Default is local Ollama; cloud requires explicit API key config
- **Workspace sandboxing** — All paths must be inside configured workspace; `allowed_roots` in `codemitra.toml` extends scope
- **Session modes matter** — `read-only`, `plan`, `approve`, `auto` control what agents can do
- **Tab-to-amend** — Shell approval UX lets users edit commands inline before approving
- **Background tasks** — `/run --background` tracked via `/tasks`; not the same as agent parallelism

## Key Files to Know

| File | Purpose |
|------|---------|
| `app/main.py` | CLI entry, chat REPL, all slash command handlers (4600+ lines) |
| `app/config.py` | Hardware detection, model inventory, GPU/CPU placement, TOML config |
| `app/llm.py` | LLM factory (Ollama + cloud), `num_gpu` routing |
| `app/prompts.py` | System prompts & routing rules |
| `app/agents/filesystem.py` | 13 tools + PermissionGuard + agent loop |
| `app/agents/shell.py` | Command execution + whitelist + streaming + Tab-to-amend |
| `app/agents/planner.py`  | Step-by-step plan + per-step routing + `.codemitra/plan.md` |
| `app/agents/diagnostics.py` | LSP-backed diagnostics helper (`/diagnostics`) |
| `app/agents/brainstorm.py` | Iterative Q&A to clarify goals before planning |
| `app/memory.py` | `.codemitra/` vault (context, plan, activity log) |
| `app/skills.py` | Skill discovery, parsing, prompt formatting |
| `app/plugins.py` | Workspace plugin slash-command loader |

## Testing

- **425 tests** in `tests/` — run with `python -m pytest tests/ -v`
- **No fixtures/services required** — Pure unit tests, some integration
- **Async tests** — Use `pytest-asyncio` (configured in pyproject.toml)

## Configuration

- `codemitra.toml` — Workspace config (models, modes, roots, disabled tools/commands, instruction files, skill dirs)
- `.env` — Optional, for `OLLAMA_API_KEY` if using cloud
- Instruction files loaded: `AGENTS.md`, `CLAUDE.md`, `.codemitra/instructions.md`, `.github/copilot-instructions.md`

## Docs Reference

- `docs/Vision.md` — Why CodeMitra exists, gap analysis vs Claude Code
- `docs/Roadmap.md` — Phase-by-phase build plan (Phases 1-17)
- `docs/Product Blueprint.md` — Feature baseline & target UX
- `docs/Claude Code Comparison.md` — Detailed gap analysis
- `docs/Architecture.md` — System diagram & component breakdown