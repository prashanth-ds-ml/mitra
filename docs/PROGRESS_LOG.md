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
| 2026-10-24 | M0 | Model choice made a measurement (D-014): `bench/model_screen.py` runs 12 native tool-call cases (exact `str_replace`, error recovery, no-tool restraint, ~10K-token prompt) plus speed and GPU fit on 13 local tools-capable models; 7 scorer tests | - |
| 2026-10-25 | M0 | Screen not run: free RAM 2.7 GB even after stopping the Research Desk backend (9.6 GB); browsers and the ChatGPT app hold ~10 GB more. Blocker recorded as U-006 | - |
| 2026-10-26 | M0 | Models picked from published benchmarks (D-015): qwen3.5:4b + qwen3.5:9b. Bench-owned Ollama server at 64K (D-016). Model check: 4B 9/12 at 81 tok/s, fully on GPU at 64K; 9B 11/12 at 20 tok/s, 64% on GPU. Prompt overhead of 5 stock agents: 2.7K-12.2K tokens. First real runs found 4 bench bugs (E-008 cut prompt in our own screen, E-009..E-011), all fixed with tests; README/SCOPE overhead claim corrected to measured numbers | - |

## Scoreboard

Filled from EVALS.md at each milestone.

| Metric | Stock agents (best) | Mitra v0.1 | v0.2 | v0.3 |
|---|---|---|---|---|
| Pass rate, qwen 4B | - | - | - | - |
| Pass rate, qwen 9B | - | - | - | - |
| Fixed prompt + tools (tokens) | - | - | - | - |
| Broken tool calls per task | - | - | - | - |
| % solved locally (with escalation) | n/a | n/a | n/a | - |
| Frontier ₹ per task | - | - | - | - |
| GPU Wh per solved task | - | - | - | - |
