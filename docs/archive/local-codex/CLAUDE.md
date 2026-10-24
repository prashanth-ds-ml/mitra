# CodeMitra — Claude Code Behavioral Spec

## Project Context
Local offline AI coding assistant (Ollama + LangGraph). Multi-agent CLI. Goal: user says "CodeMitra built this." No cloud, no API costs. Hardware baseline: 16 GB RAM · 6 GB GPU · 512 GB disk.

```
pip install -e .                         # install
codemitra                                # run CLI
python -m pytest tests/ -v              # all tests (525)
python -m pytest tests/test_<name>.py   # single file
```

---

## Model Tiers

| Task | Model |
|------|-------|
| Planning, orchestration, architecture decisions, audits | Opus |
| Code implementation, debugging, refactoring, analysis | Sonnet |
| Creating or updating markdown, docs, SKILL.md files | Haiku |

Never upgrade a tier without stating the reason upfront. Never use Haiku for code. Never use Sonnet for docs-only work.

---

## How I Work

**Ambiguity** — Proceed with stated assumptions. State the assumption in one line before acting. Only stop to ask when the action is destructive or irreversible: file deletes, core rewrites, schema changes, anything affecting git history.

**Responses** — Done + what changed. One sentence of reasoning only if the decision was non-obvious. No trailing summaries. No "next steps" sections unless asked.

**Multi-step tasks (3+ changes)** — State the plan as a compact numbered checklist, then execute immediately without waiting for approval. Pause mid-plan only if something turns out riskier than expected.

**Scope creep** — If I spot something broken nearby while in a file, mention it in one line at the end but do not touch it. You decide if it becomes the next task.

---

## Tool Discipline

- **Grep first** to find exact content matches. **Glob** to enumerate file candidates. **Read** only after both confirm the right target.
- Batch all independent tool calls in a single message — never sequential when parallel is possible.
- Fork for research or multi-file analysis that would fill context with raw output I won't need again.

---

## Scope Rules

- Touch only the files required for the stated task.
- No opportunistic refactoring or cleanup of adjacent code.
- No `# TODO` in code — unfinished items go to `.codemitra/context.md`.
- **Current phase:** no new agents, no new features — quality, consolidation, and correctness only.

---

## Git Rules

- Never `git push` without explicit instruction in that message.
- Never `--no-verify` or skip hooks — fix the root cause if a hook fails.
- Never amend published commits — create a new commit instead.
- Stage specific files by name — never `git add -A` or `git add .`.
- Commit message: one focused line on the *why*, not the what.

---

## LLM Engineering Rules

This project uses **Ollama + LangChain only**. No Anthropic API.

- **Always use factory functions** — `get_local_llm()` or `get_cloud_llm()` from `app/llm.py`. Never instantiate `ChatOllama` directly in any other file.
- **Always set `temperature`** — `0` for agent/deterministic tasks (tool-calling loops), `0.2` for conversational. No other value without a stated reason.
- **Always set `num_predict`** — the per-call token cap. Set it per task context; never rely on Ollama's unlimited default.
- **Always pass `num_ctx`** — 131072 is the project default from `codemitra.toml`. Never hardcode a different value; read it from config.
- **Pass `num_gpu` from config** — hardware-aware GPU placement via `app/config.py`. Never hardcode GPU layer counts.
- **`codemitra.toml` is the source of truth** for model names and defaults. Never hardcode model names in new code.
- **Prompts live in `app/prompts.py`** — never inline system prompt strings in agent or main code.
- **No implicit telemetry** — no `langsmith`, no auto-tracing packages. Any observability must be explicit and opt-in.

---

## Testing

- Run `python -m pytest tests/ -v` before marking any code task done.
- If tests fail, fix the code — never report done with "tests may need updating."
- Never modify tests to make them pass — fix the code instead.
- Async tests require `@pytest.mark.asyncio` on every async test (strict mode) — never add `asyncio_mode = "auto"` to override this.

---

## Code Quality

- Write no comments by default. Add one only when the WHY is non-obvious: a hidden constraint, a subtle invariant, a specific workaround.
- No error handling for scenarios that cannot happen — trust framework and internal guarantees.
- No feature flags or backwards-compat shims — just change the code.
- No half-finished implementations — incomplete work goes to `.codemitra/context.md` as an open item.

---

## Skills to Use

**Built-in Claude Code skills:**

| Situation | Skill |
|-----------|-------|
| After any significant code change | `/code-review` |
| Confirm a fix works in the running CLI | `/verify` |
| Start the CLI to test a feature manually | `/run` |
| Changes touching policy, permissions, PermissionGuard | `/security-review` |
| Working code that looks over-complicated or bloated | `/simplify` |
| Investigating an unfamiliar library or pattern | `/deep-research` |
| Reducing repeated permission prompts during a session | `/fewer-permission-prompts` |

**Project commands (`.claude/commands/`):**

| Situation | Command |
|-----------|---------|
| Writing any LLM call, tool binding, or config access | `/ollama-langchain` |
| Adding or modifying a LangGraph workflow | `/langgraph-codemitra` |
| Adding a CLI command or extracting from `app/main.py` | `/cli-patterns` |
| Writing tests for any new code | `/test-patterns` |
| Adding or modifying an agent module | `/agent-patterns` |
| Diagnosing a silent failure, crash, or unexpected behaviour | `/debug-codemitra` |

---

## Architecture — Non-Obvious

- **Single shared LLM** — one `ChatOllama` in `app/llm.py`; never create extra instances elsewhere.
- **Routing via bound tools** — routing tools on the shared LLM drive the main loop; not a classifier.
- **Skills are markdown, loaded on-demand** — compact index at startup; body loaded only when invoked.
- **All prompts in `app/prompts.py`** — never inline system prompts in agent or main code.
- **Workspace sandboxed** — all paths checked via `PermissionGuard`; never bypass it.
- **Session modes** — `read-only / plan / approve / auto` control agent permissions; always respect them.
- **Tool calling required** — only Ollama models with tool-calling support are valid; no graceful degradation path.
- **`.codemitra/`** — persistent memory vault (`activity.md`, `context.md`, `plan.md`, `session.json`).
- **`app/main.py` is 4600 lines** — extract command groups out, never add more handlers into it.

---

## Known Issues (do not re-discover)

| Issue | Location |
|-------|----------|
| `config` param shadows module import → crash | `app/agents/subagent.py:69` |
| LangGraph graph rebuilt on every `/fix` call | `app/langgraph_workflows.py` |
| `PyYAML` used but missing from `pyproject.toml` | `pyproject.toml` |
| `langsmith` in `requirements.txt` — silent telemetry | `requirements.txt` |
| Test count stale — `AGENTS.md` says 425, actual is 525 | `AGENTS.md:68` |

---

> `AGENTS.md` is the instruction file for CodeMitra's Ollama model. This file governs Claude Code only. They are separate.
