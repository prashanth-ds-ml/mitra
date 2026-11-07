# Status

**Now:** first overnight build (brick breaker, 2026-11-08) + experiments registry next · **Last updated:** 2026-11-08 · **Repo:** https://github.com/prashanth-ds-ml/mitra
**Plan:** [PLAN.md](PLAN.md) · **Scope:** [SCOPE.md](SCOPE.md) · **Decisions:** [DECISIONS.md](DECISIONS.md) ·
**Lessons:** [LESSONS.md](LESSONS.md) · **Open errors:** [ERROR_LOG.md](ERROR_LOG.md)

## Next session starts here (handoff 2026-11-08)
0. 02:00 note: the user's first `/run` attempts ran an old Mitra in mitra-try with a plan that had 0 tasks
   (a Mitra-written test document, not the `### T1:` format): nothing ran. Fixed (D-054): plan check, background
   run, live view in the chat, `/night`. Verified with a real 1-minute background run in brick-breaker-night
   (cleaned up afterwards: branch deleted, project back on master).
1. **Read the night:** `C:\Users\prash\projects\brick-breaker-night\NIGHT_REPORT.md` (started by the user with
   `/run C:\Users\prash\projects\brick-breaker-night\plan.md 4`, qwen3.5:latest 256K, Mitra writes its own tests).
   Score it with the hidden judge (`brick-breaker-night-judge\JUDGE.md`, 25 tests, proven against a reference
   kept out of the project); compare with Mitra's own tests (test quality). Look at the night in the dashboard.
2. **PLAN block X** ([EXPERIMENTS.md](EXPERIMENTS.md), I-20): first registry entry, `mitra judge`, Experiments
   section on the dashboard, model screen re-run (qwen3.5 / mimo-v2.6:9b / deepseek-r1:8b --think on), E-048.
3. **Decide I-19** ([PIPELINES.md](PIPELINES.md)): the phase loop (14e) as a LangGraph pipeline with checkpoints +
   approval interrupt + bigtool (BM25) retrieval; then week 2 of [FIRST_TWO_WEEKS.md](FIRST_TWO_WEEKS.md)
   (`/plan`, plan check, re-plan, planner experiment).
- Still open: A6 adaptive thinking (+ its benchmark night), E-045 flaky MCP test, push (several local commits; the user has not said push yet), memory clean-up offer (WSL, Research Desk server).
- Machine: Ollama 0.40.15 (flash attention + q8_0 KV); models qwen3.5:4b/latest, mimo-v2.6:9b, deepseek-r1:8b.

## Next
2026-11-08 night: A1-A3 + E4 built (append_file, check_code also after every .py write, run_tests targets, crash
hint); E-047 fixed (/model vs /mode, lost Ollama → wait + retry, real pytest summary, no input gap); overnight
stopgap `mitra night` / `/run` (D-053). First night: C:\Users\prash\projects\brick-breaker-night (plan.md,
tests-first, Mitra writes tests; hidden judge in brick-breaker-night-judge). Ollama updated to 0.40.15 by the user;
mimo-v2.6:9b downloaded; model screen re-run stopped so the brick-breaker night gets the machine (user chose); re-run tomorrow (daytime). A6 adaptive
thinking and E-045 still open.

2026-11-08, role routing (D-052): `/role [name]` swaps model, max context, tools, MCP servers and thinking live;
`/model use` switches without a restart; defaults deepseek-r1:8b (planner, reviewer) and mimo-v2.6:9b (tester,
builder, debugger, deployer), falling back to the chat model until installed; builder cannot edit tests/; filesystem
MCP off; header shows roles / learning / dashboard. Downloads of deepseek-r1:8b and mimo-v2.6:9b running; the
model screen (14f) runs when they finish. Phase loop itself (planner → tester → builder ...) still to build.

2026-11-07 night, dashboard reworked after looking at it (headless Edge screenshots): most useful first
(headline with counts, trend tiles, improving per version, your judgment, where it works, sessions, tools/models,
training, then self-improvement internals with problem patterns folded); compact tables (no cut-off columns); real
tool times only (no idle gaps); output tokens instead of summed context; sessions split at each Mitra start;
"not recorded (older)" labels.

2026-11-07 night, item 0 built (D-044): code version, machine state, Ollama prompt/load time, your corrections
(diffs), declines, /good /bad, wrap-up / compaction / failed calls traced, crash rows; dashboard: trends day by day,
per Mitra version, by project / model / kind, first try, time to green, your judgment, crashes, project filter.
Live: streamed replies keep Ollama's timings (4B: load 7.6 s). No chat has run on the new code yet (0 traces):
the user waits to start. Pushed both repos earlier (11 + 1 commits). Brainstorm: I-14 friend's data, I-15 shared
knowledge base (SCOPE).

2026-11-07 late, brainstorm documented (no code): [SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md) (loop, what we
have / miss, item 0 recording design, trends, dashboard views, link); PLAN "Next up" item 0 first; the user's
running chat (started 19:18) was on pre-D-041 code: records merged by hand, restart needed for traces. The user
asked to keep brainstorming and documenting before building.

2026-11-07, MCP next steps added to PLAN M4 (no code): Serena on/off trial on a playground level, Playwright
when the first web project starts, Research Desk MCP as planned. Other candidates noted in chat (DuckDB, ABDM docs,
Docker) are not planned yet.

2026-11-07, E-046 (committed locally): compaction now at 80% of the context (was a fixed 120K, so 256K was half
unused); `/context 128k|256k|auto` switches the size live, kept per model. I-7 plan (+ step M: prompt-processing time)
and I-8 (one explore sub-agent, after M) waiting for the go; no sub-agents otherwise (user, 2026-11-07).

2026-11-07, dashboard I-6 / D-041 (committed locally, not pushed):
- Central append-only store `~/.mitra/data/` (records + traces, every folder Mitra ran in, never deleted); full traces
  with thinking; turn outcomes; page `~/.mitra/dashboard.html` with sessions, tools/MCP, models, improvement per harness
  version, training data; rebuilt on session end and by `/report`; `mitra report --export-training`.
- Live on real data: 8 sessions / 31 turns imported, build 2.1 s; run_command failed 19/20 (mostly real game bugs, plus
  pre-E-040/E-041 cases); 0 usable training turns yet (all records predate traces).
- D-042: `mitra dashboard` serves it on http://127.0.0.1:8765/ with a Refresh button (live check: page 25 ms
  from cache, Refresh 0.5 s).
- Next: the user looks at the page (PLAN I-6 step 6), then push. E-045 (flaky MCP start timeout under load) open.

2026-11-07 (D-039, D-040 pushed; E-044 committed locally):
- E-044: a cut-off Qwen3.5 tool call (Ollama `XML syntax error ... unexpected EOF`) no longer crashes the turn: the
  model is told and retries in parts (max 2). Seen live on "make a detailed report" (one 5.2K-token call, 3m20s).
- D-039: flash attention + q8_0 KV in Ollama; the 9B (`qwen3.5:latest`) runs at 256K (12 GB, 43% GPU); last model set
  to it.
- D-040 / E-043: memory check at every start (`app/fit.py`): one line ✓/⚠/✗, and when not comfortable the programs
  to close and a smaller option; also in `/doctor`. 15 tests; 570 pass. Live: ✗ with 6.3 GB free (VS Code 2.1 GB, a
  `pt_train.py` job 1.9 GB listed).

2026-11-06 night, self-improvement (D-038):
- Step 0 (E-033): shell chains / cd / Git Bash paths; guard counts real failures; failed commands show why.
- Step 1: harness settings (`app/core/harness.py`, `mitra harness`), used by solve, plans and chat.
- Step 2: `mitra report` (failure patterns from `.mitra/runs/**/*.jsonl`, `app/core/analyze.py`) and
  `mitra report --html` (dashboard at `~/.mitra/dashboard.html`, `app/core/dashboard.py`). Level runs now keep their
  records in `mitra-playground/.mitra/runs/level-*`. First report: Level 01 run, 28 calls, 4 tool errors (reading
  paths that do not exist yet).
- Step 3: `mitra improve` (`app/core/improve.py`): local proposer (9B by default, needs ~11 GB free RAM; `--proposer
  qwen3.5:4b` otherwise) suggests one rule / tool text / limit for the top pattern; the builder solves the bench tune
  half with the current and the proposed harness; kept only if more pass (hidden tests) at <=120% prompt tokens.
  Attempts in `~/.mitra/harness/attempts.jsonl` and on the dashboard. Live dry run (4B proposer): "verify file
  existence with list_files before reading or editing" for the tool_error pattern, 10 s.
- Deep dive (E-036..E-039): improve looks only at the current harness version's records, model errors and broken
  grading stop the A/B, proposer unloaded + free-RAM check, worst-case harness within the prompt budget, harness
  step limit applies to `mitra solve`, every subprocess has a timeout; health check has a self-improve step.
- Live session 2026-11-06 (brick breaker in mitra-try, user playing): E-040 (quote-blind chain split) and E-041
  (a running game reported as failed) fixed; chat prompt: project questions are answered from the files, not the web.
  Open: Mitra has no way to start a program and leave it running for the user (games, servers); pip installs went
  to the user Python, not a project venv.
- Next: step 4 overnight runs (needs the user's ok to create a scheduled task); more run records from real sessions.

2026-11-06 evening (all pushed; 431 tests; Windows + Linux CI green):
- **M1 core loop** (`app/core/`): one loop, 7 tools, tests decide done; `mitra solve "task"` and `mitra solve --plan plan.md`
  (task by task until each task's "Done when" test passes). Live: fizzbuzz solved in 4 steps / 12 s.
- **The chat runs on it** (D-037): every message is one agent loop until the model answers (tools: core + shell, web,
  MCP, run_plan); ask / auto-edit / plan modes; `/fix` = the loop until the command passes. Live: the user's
  "plan, implement, test, fix, repeat" message -> 10 steps, failing test fixed, all tests pass.
- **Old engine removed**: router, planner/brainstorm/reader/subagent/registry, file/shell/web agent loops, LangGraph
  fix workflow, work modes, plugins, advisor, cloud builders (-5,212 app lines, -2,805 test lines).
- **Level 01** (mitra-playground): plan + 17 visible + 55 hidden tests + reference; `scripts/run_level.py`.
  Waiting on the user's ok to run Mitra on it.
- 4B and 9B at 128K (D-036); context use = latest prompt size (E-025).

2026-11-06, terminal assistant session (all pushed; 645 tests; Windows **and Linux** CI green, Linux blocking again):
- **Interface (D-031..D-035):** `app/ui/` with the Phosphor theme, live streaming, thinking line, one line per tool
  step, inline arrow-key approvals with coloured diffs, startup straight to the header (remembered model), framed
  input + status line, multi-line input (shift+enter), saved history, `/` and `@` menus, paste folding, esc to stop
  with type-ahead, shift+tab modes (ask / auto-edit / plan), title + bell notifications, folded output + ctrl+o.
  Mock: https://claude.ai/artifact/DgT44qmxc48rG9n3LB6hiR. Person-only key checks: USER_TESTS.md (2026-11-06).
- **Models (D-032, D-033):** only official qwen3.5 tags with 4B+ are listed; context measured on this machine:
  4B at 64K (100% GPU, 82 tok/s), 9B at 128K (47% GPU, 10 tok/s). EVALS 2026-11-06.
- **Bugs fixed:** E-016 (thinking dropped), E-017 (old/new interface mixed), E-018 (bad tool args crashed a turn),
  E-019 (questions started builds; nested project copies), E-020 (silent turns; removed commands in replies),
  E-021 (Windows quotes), E-022 (keyword routing), and the old review findings E-001, E-002, E-003, E-005.
- **Playground:** leftovers from Mitra's runs moved out (backup in the session scratchpad); `.mitra/` ignored.

**Next decision (user):** go for M1, the core loop that can run plan -> implement -> test -> fix on a playground
level; it replaces the keyword router and the planner/file/shell agent hand-offs that caused E-019, E-020, E-022.
Level 01 needs its `plan.md` and tests written first (no level content exists yet). Still waiting on the user's OK:
starting the real MCP servers (downloads + GitHub token). M0 baselines still need ~10 GB free RAM.

Earlier:
2026-11-05: code renamed to Mitra (920ee63); MCP client on the official SDK with day-one servers (8a91474, D-030):
git, GitHub (remote HTTP, token from `gh auth token -u prashanth-ds-ml` via `~/.mitra/mcp.json`), Context7,
filesystem, Semgrep on; fetch, AWS docs, Serena off. 640 tests pass (Windows CI green; Linux has the same 8 E-005
failures as before). **Not yet done:** starting the real servers (`python -m app.main mcp test <name>` from this
folder) needs the user's OK, because it downloads the packages (`uvx`/`npx`) and sends the GitHub token to GitHub's
MCP endpoint. Pin their versions after the first good start.

M2 design written: [M2_PLAN.md](M2_PLAN.md) (D-028 MCP). Models stay qwen3.5:4b + 9b (D-029).

Plan v2 agreed 2026-11-05 (D-017..D-027): terminal coding assistant on local models (M2); Mitra plans and builds
locally, unattended (M3); Claude Code only as a fallback; practice ladder in a separate repo `mitra-playground`;
MCP + Harness² in M4; fine-tune last (M7). Old scope and plan in `docs/archive/`. GitHub milestones and tracking issues renamed to M0-M7 (old M8 closed).
Practice ladder repo created: https://github.com/prashanth-ds-ml/mitra-playground (public; skeleton, plan format v0,
`scripts/check_level.py`, CI green). Both repos push as prashanth-ds-ml via a repo-local credential helper.

The next unticked items in [PLAN.md](PLAN.md), M0:
1. Baseline runs: 5 stock agents x qwen3.5:4b and qwen3.5:9b on the 10 tasks. Start the bench server first
   (`python bench/ollama_server.py`, port 11435), then per agent and model:
   `python bench/run.py --agent bench/configs/<agent>.toml --model <model>`. At ~1-15 min per run this is several hours;
   the 9B runs need ~9.6 GB free RAM by the preflight rule (it worked at 6 GB with 3.2 GB lowest, see EVALS).
2. Kill check 1 (together), then release v0.0 + post 1 (lock file of tested versions first; release check shown to you)

Done 2026-10-26: model check, prompt overhead, 64K context setup (see EVALS.md). A Med360 overnight experiment was
running on this machine (uses a remote vLLM, not the GPU); RAM was ~6 GB free.

Session closed 2026-10-26: the bench Ollama server is **not running**. Claude Code stopped it while the session was
idle because the machine ran critically low on memory (nothing lost; all results were already pushed). Before the
baselines: free RAM first (U-006: close Edge, Chrome, the ChatGPT app, or reboot), then start the server and let
preflight check RAM.

To restart Research Desk afterwards: in `portfolio/04-local-deep-research-vertical`, run
`uv run langgraph dev --no-browser --no-reload --port 2025`.

## Bench tools
- `bench/bench.py` (tasks, grading, validate) · `bench/proxy.py` (logs every model call) ·
  `bench/preflight.py` (refuses unready runs) · `bench/run.py` (one agent x tasks, records in `results/runs/`) ·
  `bench/model_screen.py` (12 native tool-call cases per model, plus speed and GPU fit at 32K/64K) ·
  `bench/ollama_server.py` (bench Ollama on 11435: 64K context, one model, one request; D-016) ·
  `run.py --overhead` (stops an agent after its first work call and records its prompt cost)
- Stock agents installed: Claude Code 2.1.310, Codex 0.162.1, OpenCode 1.17.8, dsh 0.1.5-rc.1, Aider 0.86.2
  (uv tool, Python 3.12), deepagents-code 0.2.1 (uv tool, Python 3.14, Ollama extra,
  `--with colorama`: without it its local server crashes on Windows)

## Machine
- GPU: NVIDIA GeForce RTX 5050 Laptop, 8 GB (8151 MiB), driver 610.47; `nvidia-smi` power limit N/A (default 80 W)
- RAM: 24 GB · Ollama 0.40.8 · Python 3.12 (shared root `.venv`)

## Notes
- local-codex was imported from its public GitHub version (commit dd93fa6). Its own docs, AGENTS.md, CODEMITRA.md,
  skills.md and codemitra.toml are in `docs/archive/local-codex/` (history, not instructions).
- The package is not installed into the shared venv (a top-level `app` package would clash with other projects); run
  tests from this folder with `../../.venv/Scripts/python.exe -m pytest`.
- `requirements.txt` (old pins) was dropped; a lock file from the tested versions is due before the v0.0 release.
- Shared venv has an unrelated pre-existing conflict (`langgraph-api` vs `opentelemetry-exporter-prometheus`).

## Where things are
| File | What it tracks |
|---|---|
| `CLAUDE.md` | Rules for working in this repo; read-first order |
| `docs/PLAN.md` | The checklist; tick items with dates |
| `docs/SCOPE.md` | What and why, impact scoring, ideas to test, honest limits |
| `docs/DECISIONS.md` | D-numbered decisions (append-only) |
| `docs/ERROR_LOG.md` | What went wrong (E-nnn) |
| `docs/FIX_LOG.md` | What we changed (F-nnn), incl. fixes that failed |
| `docs/LESSONS.md` | Rules learned so mistakes are not repeated (L-nnn) |
| `docs/PROGRESS_LOG.md` | Timeline + scoreboard |
| `docs/EVALS.md` | Benchmark method and every result |
| `docs/CASE_STUDY.md` | One-page story (written at v1.0) |
| `docs/USER_TESTS.md` | Only the checks that need you |
| `docs/POSTS.md` | LinkedIn drafts, links, feedback |
| `CHANGELOG.md` | Changes per release |
