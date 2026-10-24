# Progress log: how Mitra was built

The detailed record behind the [case study](CASE_STUDY.md): one row per working session or milestone, in order.
Numbers link to [EVALS.md](EVALS.md); bugs to [ERROR_LOG.md](ERROR_LOG.md); fixes to [FIX_LOG.md](FIX_LOG.md);
decisions to [DECISIONS.md](DECISIONS.md).

## Timeline

| Date | Milestone | What happened | Release / post |
|---|---|---|---|
| 2026-10-24 | Planning | local-codex reviewed (E-001..E-003); deepseek-harness, Harness², Uber Debug Assist, Deep Agents, bigtool studied; research on local-model support in coding agents; scope, checklist and impact scoring agreed (D-001..D-012); repo set up with docs only | - |
| 2026-10-24 | M0 | Public repo created and pushed; local-codex (dd93fa6) imported, its docs archived; 561 tests pass in the shared venv; lint gate (undefined names) found and fixed E-004; CI added (Linux + Windows tests, gitleaks) | - |
| 2026-10-24 | M0 | Benchmark v0: fake payments SDK + FastAPI shop, 10 tasks (5 tune / 5 held-out), visible + hidden tests, tamper check; all 10 validated; 17 harness tests | - |
| 2026-10-24 | M0 | Bench tooling: logging proxy (every model call, tokens from Ollama itself), preflight (blocks at 3.8 GB free RAM), run recorder (fresh git workspace, timeout with process-tree kill, diff, grading, fingerprinted completion marker, infra kept apart); 15 new tests, 593 total | - |
| 2026-10-24 | M0 | Stock-agent configs from Ollama's own integration docs (Claude Code, Codex, OpenCode, Aider, deepagents-code; clean per-run config dirs); Ollama docs say these agents need >= 64K context; deepagents-cli found deprecated, replaced by deepagents-code; E-006/E-007 caught by tests before any real run | - |

## Scoreboard

Filled from EVALS.md at each milestone.

| Metric | Stock agents (best) | Mitra v0.1 | v0.2 | v0.3 |
|---|---|---|---|---|
| Pass rate, qwen 4B | - | - | - | - |
| Pass rate, qwen 8B | - | - | - | - |
| Fixed prompt + tools (tokens) | - | - | - | - |
| Broken tool calls per task | - | - | - | - |
| % solved locally (with escalation) | n/a | n/a | n/a | - |
| Frontier ₹ per task | - | - | - | - |
| GPU Wh per solved task | - | - | - | - |
