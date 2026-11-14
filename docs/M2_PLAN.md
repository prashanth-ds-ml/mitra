# M2 plan: terminal assistant (`codemitra`)

**Written:** 2026-11-05 · **Starts:** after M1 (the core loop) and on the user's go · Checklist items are in
[PLAN.md](PLAN.md#m2-terminal-assistant-mitra); this page is the design behind them.

## Goal
Run `codemitra` in any project folder and work with it in plain words, on local models only: it explains code, finds it,
edits it with a diff you approve, runs tests and commands, fixes failures, and connects to MCP servers. It must stay
usable on qwen3.5:4b, so the fixed prompt stays under ~3K tokens and everything else loads on demand.

## What v1 does (the agreed ability list)
| # | Ability | How |
|---|---|---|
| 1 | Chat about the project | Answers cite `file:line`; reads only what it needs |
| 2 | Find code | Text search + file list (core tools); symbol search via Serena in M4 |
| 3 | Edit code | `str_replace` and new files; every change shown as a diff, approved by you (unless auto-edit) |
| 4 | Run commands and tests | Timeout on every command; output head/tail on screen, full output in a file; risky commands always ask |
| 5 | Fix loop | "make this pass" → edit → test → repeat; step limit; rollback if it gives up |
| 6 | Undo | `/undo` last change, `/undo all` for the session (change sets with before/after, from local-codex) |
| 7 | Modes | ask each time (default) / auto-edit / plan only (read-only) |
| 8 | Model + settings | `/model`, `/context`, `/think` change the model, context length and thinking budget |
| 9 | Sessions | Saved per project; `/resume`; when context fills, a fresh round starts with a short handoff note |
| 10 | Project notes | `AGENTS.md` / `CLAUDE.md` loaded within the byte budget |
| 11 | Token counter | Prompt tokens and context use in the status line; warning before the limit |
| 12 | Plan + run | `/plan` and `/run` arrive in M3; M2 only reserves the commands |
| 13 | Git help | `/diff`, `/commit` (message drafted, you approve); never pushes on its own |
| 15 | Skills on demand | Small files per stack (FastAPI, LangGraph, Next.js, uv on Windows) loaded when a task needs them |
| 16 | Machine doctor | `/doctor`: free RAM, GPU/VRAM, Ollama up, model loaded, context really applied |
| 17 | MCP | General MCP client; first servers Git, Context7, AWS Documentation (details below) |

Left for later: self-review of diffs (14), `/brainstorm`, `/prd`, playbooks, docs/release helper, post drafts, memory
across projects, notifications.

## Design rules
1. **One loop, five core tools** (read, search, `str_replace`, run, finish) from M1. MCP tools and skills are extra and
   loaded only when needed.
2. **Slash commands are code, not model calls.** `/diff`, `/undo`, `/model`, `/mcp`, `/doctor` cost zero tokens.
3. **Every change is a diff; every "done" means a check ran** (test, command exit code, or your approval).
4. **The fixed prompt stays under ~3K tokens.** CI checks it; the status line shows it.
5. **Every model call, command and MCP call has a timeout** and is logged in the session record.

## MCP in M2
### Client
- Official `mcp` Python SDK (or `langchain-mcp-adapters` if it fits the LangGraph loop better; decided in the first
  task by a small spike). local-codex's `app/mcp.py` is replaced: it uses `Content-Length` framing (MCP stdio uses one
  JSON message per line), starts a process per call, and has no read timeout.
- Transports: **stdio** (local servers) and **Streamable HTTP** (remote servers).
- One long-lived session per server, started on first use, closed on exit; a dead server is restarted once, then
  reported.

### Config
- Standard `mcpServers` JSON (same shape as Claude Code, Cursor and server READMEs) in `.codemitra/mcp.json` (project) and
  `~/.codemitra/mcp.json` (user). `/mcp import` reads an existing Claude Code config.
- Secrets come from env vars or a profile name (e.g. `AWS_PROFILE`), never written into the prompt, logs or training data.
- Per server: `enabled`, `timeout_s`, `allow` (tools on), `ask` (tools that need approval), and a short description per
  tool written by us (one line, plain words) instead of the server's long text.

### Safety
- Read-only tools run freely; **every write tool asks**, showing the exact call, even in auto-edit mode.
- No MCP write tools at all in unattended runs (M3).
- Every MCP call logged: server, tool, arguments (secrets masked), result size, time.
- Big results trimmed to head/tail, full result saved to a file.

### First servers (no account, low risk)
| Server | Why first |
|---|---|
| Git | Read-only history, diff, blame; useful from day one |
| Context7 | Current library docs; read-only |
| AWS Documentation | Public AWS docs; no AWS account, no risk |

The rest (Serena, GitHub, SQLite/Postgres, Docker, Research Desk, AWS with LocalStack or a read-only profile) and the
tool registry come in M4, with the ops sandbox (playground level 07) and the three-way comparison.

### `/mcp` command
`/mcp` (list servers, status, tool count, prompt tokens each adds) · `/mcp on|off <server>` · `/mcp test <server>`
(start, list tools, one harmless call) · `/mcp import`.

## What happens to local-codex's code
| Part | Lines | Decision |
|---|---|---|
| `app/main.py` (prompt_toolkit REPL, ~45 slash commands, 208 functions) | 6,076 | **Trim + split.** Keep the REPL shell, history, key bindings and the commands in the v1 list; move each command into `app/commands/`; remove the rest |
| `app/agents/filesystem.py` (native `bind_tools` loop, file tools) | 994 | **Replace the loop with M1's**; reuse the file tool code after the E-001 fix |
| `app/agents/shell.py` (safe `execute()`) | 725 | **Keep**, with E-003 workspace limits and timeouts |
| `app/config.py` | 792 | **Trim**: model, context, thinking, modes, MCP paths |
| `app/memory.py`, `app/agents/session.py` | 962 | **Trim** to session save/resume + handoff note |
| `app/skills.py` + `skills/` | 189 | **Keep**, rewrite the skill files short for our stacks |
| `app/events.py`, `app/logs.py` | ~250 | **Keep** for the session record |
| `app/llm.py` | 115 | **Keep**, default model from config instead of the hard-coded `qwen2.5-coder:7b` |
| `app/mcp.py`, `app/mcp_servers/` | ~500 | **Replace** (see MCP above) |
| `app/routing.py` (regex intent routing) | 253 | **Remove**: slash commands and the model decide |
| Planner, builder, workflows, langgraph_workflows | ~1,700 | **Archive**; M3 rebuilds planning on the M1 loop |
| Advisor, brainstorm, PRD, playbooks, plugins, policy, web, diagnostics, subagent, reader, explainer, codeintel | ~3,500 | **Archive** (kept in git history); some return later as skills |

Target: the M2 app is well under half of today's code, and every kept part has tests.

## Tasks (in order)
1. Spike: MCP SDK vs `langchain-mcp-adapters` with Context7 over stdio on Windows (an hour; pick one, note it in DECISIONS)
2. Split `main.py`: REPL shell + command registry; remove commands outside the v1 list (tests for each kept command)
3. Wire chat to the M1 loop; modes (ask / auto-edit / plan only); diff approval screen
4. `/undo`, `/diff`, `/commit`; session save, `/resume`, fresh round with handoff note
5. `/model`, `/context`, `/think`, token counter in the status line
6. Project notes with byte budget; skills on demand
7. `/doctor`
8. MCP client, config, `/mcp` commands, approvals, call log; Git, Context7, AWS Documentation connected and tested
9. Fresh-clone install test on Windows; Linux CI
10. A week of my own use on small real tasks; every problem → ERROR_LOG; fixes
11. Release v0.2 + post

## Done when
- I can run `codemitra` in Research Desk or the playground and finish small tasks without leaving the terminal.
- Fixed prompt under ~3K tokens (CI), every command and MCP call logged with a timeout.
- `/mcp test` passes for Git, Context7 and AWS Documentation on Windows.
- A week of real use is logged, with problems and fixes recorded.
