# Mitra

**Local-first coding agent built for small models.** It runs everyday coding tasks on the GPU you already own, checks
every result with your tests, and calls a frontier model only when the check fails.

> **Building in public.** Status: planning done, M0 next. Progress: [checklist](docs/PLAN.md) · [status](docs/STATUS.md)

## Why
Coding agents like Claude Code, Codex and OpenCode can connect to local models through Ollama, but they are built for
frontier models: 20-33K tokens of fixed prompt, many tools, strict tool-call formats. On a 4-9B model on a laptop GPU
they often break. Mitra asks one question and publishes the answer either way:

> On an 8 GB consumer GPU, how much everyday coding work can a small model do when the agent is built for it, and does
> test-gated escalation to a frontier model cut cost without hurting the success rate?

## Results
None yet. The first numbers (prompt overhead of stock agents, baseline pass rates) arrive with v0.0.

| Agent | Model | Pass rate | Fixed prompt (tokens) | Broken tool calls |
|---|---|---|---|---|
| - | - | - | - | - |

## Roadmap
- **Phase 1:** measure the problem → `mitra solve` → same-model comparison → test-gated escalation + cost meter → v1.0
- **Phase 2:** bigtool ops pack, data pack, MCP server mode, experiments (debug brief, learning from escalations)

Full checklist: [docs/PLAN.md](docs/PLAN.md) · Scope and honest limits: [docs/SCOPE.md](docs/SCOPE.md)

## Credits
Starts from [local-codex](https://github.com/prashanth-ds-ml/local-codex). Ideas from deepseek-harness, Google
Research Harness², Uber's Debug Assist write-up, LangChain Deep Agents and langgraph-bigtool (details in SCOPE.md).

## Licence
MIT
