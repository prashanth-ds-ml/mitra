# Progress log: how CodeMitra was built

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
| 2026-10-26 | M0 | Session closed. Idle bench Ollama server stopped by Claude Code for critically low system memory; U-006 (free RAM) reopened before the baselines | - |

## Scoreboard

Filled from EVALS.md at each milestone.

| Metric | Stock agents (best) | CodeMitra v0.1 | v0.2 | v0.3 |
|---|---|---|---|---|
| Pass rate, qwen 4B | - | - | - | - |
| Pass rate, qwen 9B | - | - | - | - |
| Fixed prompt + tools (tokens) | - | - | - | - |
| Broken tool calls per task | - | - | - | - |
| % solved locally (with escalation) | n/a | n/a | n/a | - |
| Frontier ₹ per task | - | - | - | - |
| GPU Wh per solved task | - | - | - | - |
| 2026-11-10 | v0.1.0 preview | Colleague preview prepared: deep-dive review fixes (E-050..E-066), `/free`, Kaggle GPU (`codemitra kaggle start|stop|status`, first live start worked: mimo 256K fully on GPU, 37.6 tok/s), README rewritten for first-time users, feedback + bug issue forms, dependencies pinned, fresh-clone install checked in isolated dirs (9 s, `mitra 0.1.0`), secret scan of files and history clean | v0.1.0 (tag + push waiting for the user's go) |
| 2026-11-11 | D-068 steps 1-3b | v0.4.0-v0.7.0 in two days: everyday chat (mail, general), the explainer, `codemitra score` (sorting, behaviour, writing, explain, ideas, small, medium; validated set), two deep dives (13 + 4 fixes, E-076..E-100), status line + working footer, conversation memory (threads), output cap + runaway guard. Root-level redesign: the word-rule router replaced by One CodeMitra, phased (decide with only look / change / plan, then act). Model: qwen3.5:latest replaces mimo-v2.6 (mimo turned conversation into builds; plain-chat probe + A/B). A/B (qwen, 64K): phased 13/19 in 8.3 min, router 12/19, one 11/19; mimo best 11/19 in 25 min. 882 tests | v0.7.0 (1e811cc), pushed |
| 2026-11-12 to 11-14 | D-078, E-125/E-126, D-079, D-080 · v0.8.0 | D-078 phases 1-3 (tests after every change, honest partner, `codemitra practice` 13/20 → 18/20, /bad → held-out case); the user's Neon Chomp PRD session found a yes-loop (E-125) and six trust faults in 22 turns (E-126: change requests stuck read-only, another project's tests, false "fixed", drift, 524 = "Kaggle ended"), fixed with 44 tests from the real turns; feedback on every turn from the next message + one key (D-079: 11 unhappy + 13 happy on 169 old turns, no action); renamed Mitra → CodeMitra (D-080, folders moved: 899 files, 322 MB, nothing lost); fresh clone installs and passes 1,068 tests | v0.8.0 published (pre-release, tag v0.8.0), repos renamed |
| 2026-11-14 | D-081, D-083 · v0.8.1 | `codemitra share` (light, scrubbed sessions → private logs repo prashanth-ds-ml/codemitra-logs; 0 leaks on 27 real sessions); one-command setup (`setup.ps1` / `setup.sh` → `codemitra setup`: Ollama, model by GPU/RAM, Kaggle guided, name, sharing; end-to-end on a fresh Windows clone); clean README + docs/guide/; D-082 learn-first plan recorded; 1,092 tests | v0.8.1 published (pre-release), CI green |
