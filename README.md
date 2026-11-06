# Mitra

**Local-first coding agent built for small models.** It runs everyday coding tasks on the GPU you already own, checks
every result with your tests, and calls a frontier model only when the check fails.

> **Building in public.** Status: planning done, M0 next. Progress: [checklist](docs/PLAN.md) · [status](docs/STATUS.md)

## Install the `mitra` command

Mitra installs as a command you can run in any folder, like other terminal assistants. It gets its own Python
environment (no clash with your other projects), and code changes apply without reinstalling:

```
uv tool install --editable . --python 3.12     # from this folder, once
mitra                                          # in any project folder: opens the chat there
mitra solve "fix the failing test" --test "pytest -q"
mitra --version
```

The project folder is the nearest parent with a git repo or project file (`pyproject.toml`, `package.json`, ...),
otherwise the folder you are in. To remove it: `uv tool uninstall mitra`.

## Self-improvement (local models only)

Mitra learns settings, not code: rules added to its prompt, tool descriptions and limits, kept in
`~/.mitra/harness.toml` with every version saved.

```
mitra report            # what goes wrong in recorded runs: problem patterns with counts and examples
mitra report --html     # the same + playground results and history as a local page (~/.mitra/dashboard.html)
mitra improve           # a local model proposes one change for the top problem; the benchmark's tune half decides
mitra improve --dry-run # only show the proposal
mitra harness           # what Mitra has learned so far; `mitra harness revert N` goes back to version N
```

A change is kept only if more benchmark tasks pass (hidden tests) and prompt tokens grow at most 20%; every attempt
is logged in `~/.mitra/harness/attempts.jsonl`. It looks only at records made with the current settings, checks free
RAM first (the 9B proposer needs about 10 GB; `--proposer qwen3.5:4b` otherwise), and with 5 tasks one run is noisy:
treat a single kept change as a candidate, not proof.

## Why
Coding agents like Claude Code, Codex and OpenCode can connect to local models through Ollama, but they are built for
frontier models: many tools, strict tool-call formats and a large fixed prompt (measured here: 2.7K-12.2K tokens
before the agent reads any code, 3x Ollama's default 4K context for three of five agents; see
[EVALS.md](docs/EVALS.md)). On a 4-9B model on a laptop GPU they often break. Mitra asks one question and publishes the answer either way:

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
