# CodeMitra

> A local, offline AI coding assistant powered by [Ollama](https://ollama.com). No API keys. No cloud. No data leaves your machine.

---

## What it is

CodeMitra is a CLI tool that puts an AI coding assistant on your machine. It can chat about code, scaffold projects, create files and virtual environments, and install packages — all running locally via open-source models.

It is built with the same ideas behind Claude Code and GitHub Copilot, but entirely self-hosted.

---

## Features

- **Rich terminal UI** — clean startup screen, structured panels, persistent session toolbar
- **Chat-first UX** — starts conversationally, but uses direct fast paths for trivial setup tasks before escalating into plan/agent flows
- **Brainstorm loop** — `/plan` asks clarifying questions before generating a plan (ask before acting, not guess)
- **Planner agent** — breaks large goals into ordered steps, routes each step to the right agent
- **Filesystem agent** — creates folders, files, `.venv`, installs packages (10 tools)
- **Shell agent** — runs commands, captures output, streams results back to the LLM, and can launch background tasks
- **Shell approval UX** — approve / deny / Tab-to-amend (edit the command inline) before any shell command runs
- **Code reader agent** — reads and understands codebases (5 read-only tools)
- **Web agent** — native web search and page-reading with `/search` and `/open-url`
- **LSP diagnostics** — `/diagnostics [path]` runs local language servers when available and reports workspace diagnostics
- **Memory vault** — `.codemitra/` folder with session log, project context, and active plan
- **Operator controls** — `/status`, `/context`, `/permissions`, `/model`, `/diff`, `/review`, `/fix`, `/resume`, `/hibernate`, `/tasks`, `/plugins`
- **CodeMitra skills** — workspace skill discovery via `skills/*/SKILL.md`, plus `/skills` and `/skills show <name>` to inspect the active pack
- **Instruction-file compatibility** — loads repo guidance from `AGENTS.md`, `CLAUDE.md`, `.codemitra/instructions.md`, and `.github/copilot-instructions.md`
- **Workspace plugin hooks** — load custom slash commands from `plugins/*.py` or `.codemitra/plugins/*.py`
- **Guided artifact builder** — `/create` walks you through plain-English Q&A to generate Skills, Workflows, or Agent skeletons — no YAML or Python knowledge needed
- **Hardware-aware model advisor** — `/recommend` detects your GPU/CPU, scores every installed Ollama model for chat/code/agent roles, and offers to update `codemitra.toml` automatically
- **GPU/CPU placement routing** — models are classified as full-GPU 🟢, GPU+CPU split 🟡, or CPU-only 🔴 and launched accordingly; model picker shows placement badges
- **Terminal operating surface** — bottom toolbar with mode, model, cwd, context load, and current task
- **Composer ergonomics** — `Ctrl+G` opens the current prompt in your editor for longer inputs
- **Permission guard** — workspace sandboxing, mode-based approvals, configurable roots and blocked tools
- **Startup auto-detect** — derives a lightweight project brief from the workspace and injects it at startup

## Current baseline

- **Validated product baseline** — 525 passing tests
- **Shipped workflow coverage** — bootstrap, understand, session lifecycle, plan lifecycle, safe edit, fix loop, research, safety/approval, background task UX, model advisor, guided builder, diagnostics, plugin hooks
- **Operator decisions so far** — plan first for substantial work, diff before risky edits, explicit modes over hidden behavior, visible task state in the terminal, background shell work tracked as first-class tasks
- **Next product priorities** — MCP-style extensibility, deeper git workflow support, compaction polish

---

## Quick start

### 1. Install Ollama and pull models

```bash
# Run /recommend after starting CodeMitra to get model suggestions for your hardware
ollama pull qwen3:8b          # recommended chat model (fits in 8 GB VRAM)
ollama pull qwen2.5-coder:7b  # recommended code model
```

### 2. Clone and install

```bash
git clone https://github.com/prashanth-ds-ml/local-codex
cd local-codex
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -e .
```

### 3. Run

```bash
agent
```

Phase 0 foundation commands:

```bash
agent status
agent config
agent models
```

Compatibility aliases also work:

```bash
agent /status
agent /config
agent /models
```

---

## Usage

```bash
agent
```

```text
codemitra> hi
codemitra> create a FastAPI project called myapi with a src/ folder and install fastapi uvicorn
codemitra> /recommend                          # get model suggestions for your hardware
codemitra> /create                             # guided wizard: build a skill, workflow, or agent
codemitra> /diagnostics app                    # run local LSP diagnostics when a server is available
codemitra> /run --background python -m http.server
codemitra> /plugins
codemitra> /tasks
codemitra> search the web for FastAPI background tasks
codemitra> /permissions
codemitra> /hibernate
codemitra> exit
```

---

## Project structure

```
local-codex/
├── app/
│   ├── main.py          # CLI entry point, chat REPL, all slash command handlers
│   ├── config.py        # Hardware detection, model inventory, GPU/CPU placement, TOML config
│   ├── llm.py           # LLM factory (Ollama + cloud), num_gpu routing
│   ├── advisor.py       # Model recommendation engine — scores models per hardware/role
│   ├── builder.py       # Guided artifact builder — Q&A → Skill / Workflow / Agent
│   ├── prompts.py       # System prompts and routing rules
│   ├── memory.py        # .codemitra/ vault (context, plan, activity log)
│   ├── skills.py        # Skill discovery, parsing, and prompt formatting
│   ├── plugins.py       # Workspace plugin slash-command loader
│   └── agents/
│       ├── filesystem.py  # 10 tools + permission guard + agent loop
│       ├── shell.py       # Command execution + whitelist + streaming + Tab-to-amend approval
│       ├── reader.py      # 5 read-only tools for codebase understanding
│       ├── planner.py     # Step-by-step plan + per-step routing
│       ├── codeintel.py   # Symbol lookup and code intelligence
│       ├── diagnostics.py # LSP-backed diagnostics helper
│       ├── explainer.py   # File / symbol explanation agent
│       ├── reviewer.py    # Git diff code review agent
│       ├── session.py     # Session summarisation / compaction
│       ├── web.py         # Web search and page-reading helper
│       └── response.py    # ToolResult, AgentResponse, Rich renderer
├── skills/              # Built-in workspace skill playbooks (SKILL.md format)
├── tests/               # 525 unit and integration tests
├── misc/
│   └── ascii.py         # ASCII art generator for the banner
├── docs/                # Architecture and product documentation
├── codemitra.toml       # Workspace configuration
└── pyproject.toml       # Package metadata and test config
```

---

## Documentation

Full docs live in [`docs/`](docs/Home.md).

Key product-direction docs:

- [`docs/Phased Rollout.md`](docs/Phased%20Rollout.md) - the active phased execution document we are using for future work
- [`docs/Product Blueprint.md`](docs/Product%20Blueprint.md) - feature baseline and target UX
- [`docs/Roadmap.md`](docs/Roadmap.md) - implementation phases
- [`docs/Testing Strategy.md`](docs/Testing%20Strategy.md) - regression layers, workflows, and transcript coverage
- [`docs/Error Prevention Playbook.md`](docs/Error%20Prevention%20Playbook.md) - recurring error patterns, fixes, and prevention rules
- [`docs/Vision.md`](docs/Vision.md) - why CodeMitra exists and what gap it closes

---

## Roadmap

See [`docs/Roadmap.md`](docs/Roadmap.md) for the full phase-by-phase build plan.

| Phase | Description | Status |
|---|---|---|
| 1–4 | Foundation, chat, filesystem agent, routing | ✅ Done |
| 5 | Code reader agent | ✅ Done |
| 6 | Shell agent | ✅ Done |
| 7 | Planner agent | ✅ Done |
| 8 | Memory vault | ✅ Done |
| 9 | Brainstorm loop | ✅ Done |
| 10 | Trust layer: diff preview + approvals | ✅ Done |
| 11 | Repair loop + operator commands | ✅ Done |
| 12 | Session UX | ✅ Mostly done |
| 13 | Project auto-detect + code intelligence | ✅ Started |
| 14 | Extensibility + policy controls | ✅ Started |
| 15 | Git-aware workflows | 🔲 Planned |

---

## Tech stack

- **LLM runtime** — Ollama
- **LLM framework** — LangChain (`langchain-ollama`, `langchain-core`)
- **Terminal UI** — Rich, prompt-toolkit
- **Language** — Python 3.11+
