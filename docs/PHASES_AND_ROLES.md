# Phases and roles: one loop, a model, tools and MCP servers per phase (I-17, I-18, design 2026-11-08)

Status: **design agreed in discussion, nothing built.** Builds on: the planner work (PLAN 13-14d), overnight mode
([OVERNIGHT_MODE.md](OVERNIGHT_MODE.md), D-045/D-048), the tools (I-11) and MCP plans (PLAN M4).

## Why phases, not agents
Today one loop with one prompt does everything (build, test, fix, debug); there is no reviewer. Separate agents were
tried before and their hand-offs caused E-019, E-020, E-022 (removed in M1); sub-agents also do not fit this machine
(one model, one request at a time). So: **one loop that moves through phases; code decides the phase, not the
model**. Each phase has its own short prompt, small tool set, MCP servers and (optionally) model. Same history.

Gains for a small model: focus (short prompt, 4-6 tools: the bigtool idea per phase), honest tests (written from the
PRD in their own phase, read-only to the builder), real debugging (hypothesis → minimal fix → one test), no
hand-off bugs.

## Phases and models (one model loaded at a time; swaps only at phase boundaries)
| Phase | Model now | Candidates (after the screen) | Thinking |
|---|---|---|---|
| Planner | qwen3.5:latest (9B) | mimo-v2.6:9b, ornith-1.5:35b (if it fits), deepseek-r1:14b | on |
| Tester (tests first, from the PRD) | = planner (no swap) | follows the planner | on |
| Builder | night A: 9B · night B: qwen3.5:4b (D-048) | mimo-v2.6:9b, ornith-1.5:9b | adaptive (E2) |
| Debugger / fixer | builder model; **planner after 2 failed rounds** | - | on |
| Reviewer | per task: the loaded model · at the end: planner (whole project vs PRD) | - | on |
| Deployer | builder model | - | off |
| Reporter | the loaded model | - | off |
| Live chat | 9B, no swaps (`/think` may hand one question to the planner) | - | adaptive |
A night-B run swaps ~3-6 times: plan + tests (9B) → build (4B) → [stuck: re-plan (9B) → build (4B)] → final review +
report (9B). Context: 256K for both by default (user, D-048); option to test: planner phases at ~64K so a bigger
planner fits.

## Current choice: deepseek-r1 thinks, mimo-v2.6 does (user, 2026-11-08, D-050; pending the screen)
| Phase | Model | Note |
|---|---|---|
| Planner | **deepseek-r1:8b** (5.2 GB, the newer R1-0528 distill of Qwen3-8B; user picked it over :14b, D-051) | plan taken from its reply text; CodeMitra writes plan.md, so no tool calls needed; 128K context (enough for planning); always thinks, slow but rare |
| Final reviewer | **deepseek-r1** | diff + PRD go in the prompt; no tool calls |
| Tester, builder, debugger, deployer, live chat | **mimo-v2.6:9b** | tool-heavy phases; mimo = Qwen3.5-9B tuned for agent work (MIT); the tester moves here from the planner model |
- Baseline kept: qwen3.5:latest. Night A = qwen3.5:latest only; night B = deepseek-r1 plans/reviews + mimo builds.
- Screen first: `model_screen.py` (tools, speed, memory fit), Level 01 with mimo vs qwen3.5, planner eval deepseek-r1:8b vs
  qwen3.5; then nights A/B. Both added to an allowed-models list (CodeMitra lists only qwen3.5 tags today,
  D-032). Licences rechecked before any training use.

## Tools per phase (✓ exists, ✚ new / planned)
| Phase | Tools |
|---|---|
| Planner | ✓ list_files, read_file, search, web_search, fetch_url · ✚ recall, read_note |
| Tester | ✓ read_file, search, write_file (**tests/ only**), run_tests · ✚ run_tests(path/-k/-x), append_file |
| Builder | ✓ read_file, search, write_file, edit_file, make_dir, run_tests, run_command · ✚ append_file, check_code, setup_env · **tests/ read-only** |
| Debugger | ✓ read_file, search, edit_file, run_tests · ✚ run_tests(path/-k/-x, --tb=long), **inspect**, check_code, app_logs |
| Reviewer | ✓ read_file, search · ✚ diff (the task's changes), screenshot, recall |
| Deployer | ✓ run_command · ✚ setup_env, start_program, stop_program, http_request, app_logs, screenshot |
| Reporter | ✓ read_file · ✚ remember, vault note, README writer |

New tools in this design: **`inspect`** (evaluate an expression / short snippet in the project's venv, with a
timeout: the model's debugger, since it cannot drive pdb), **`diff`** (the current task's changes), **`app_logs`**
(output of a program started with start_program; browser console via Playwright).

## MCP servers per phase
| Phase | MCP servers |
|---|---|
| Planner | context7 · research-desk (planned) · github (read-only) · serena (existing codebases) |
| Tester | context7 · serena · playwright (end-to-end tests for web apps) |
| Builder | context7 · serena · shadcn (React apps only) |
| Debugger | serena · git (`git_diff` since the last green) · playwright (console errors, reproduce) |
| Reviewer | git (diff) · semgrep · playwright (visual check) |
| Deployer | playwright (health check, smoke click-through) |
| Reporter | git (log of the run's commits) |
Cleanup: the **filesystem** MCP duplicates CodeMitra's own read / list / search tools: turn it off (two ways to do the
same thing confuse a small model). Serena, Playwright, shadcn and research-desk only after their PLAN M4 / level steps.

## Missing pieces folded in (I-18)
Reviewer role (above); clarifying questions when a PRD is vague and short decision notes (why a design) in the
planner phase; runtime logs and browser console in debugger / deployer; project README + CHANGELOG in the reporter;
morning review-and-merge (with M5's review view); energy per night (nvidia-smi power x time, the repo rule).

## How it is checked
- Phase switches, tool sets and the read-only tests rule: unit tests.
- The model per phase: the screen (`bench/model_screen.py` at the phase's context), Level 01 for builders, the planner
  eval for planners, then nights A/B (hidden tests decide). Results in EVALS, winners in DECISIONS.
- Prompt budget: each phase's prompt + tools stays under the 3K budget (CI checks every phase).

## Order
With the week-2 planning work: planner + tester phases (and red-then-green) first, then builder with read-only tests,
debugger with `inspect`, reviewer; deployer and reporter with overnight mode (16b); model candidates after the screen.
