# Status

**Now:** M2 terminal cleanup done; next is M1 (core loop) on the user's go · **Last updated:** 2026-11-06 · **Repo:** https://github.com/prashanth-ds-ml/mitra
**Plan:** [PLAN.md](PLAN.md) · **Scope:** [SCOPE.md](SCOPE.md) · **Decisions:** [DECISIONS.md](DECISIONS.md) ·
**Lessons:** [LESSONS.md](LESSONS.md) · **Open errors:** [ERROR_LOG.md](ERROR_LOG.md)

## Next
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
