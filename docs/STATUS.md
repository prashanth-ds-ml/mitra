# Status

**Now:** M0 in progress, blocked on free RAM · **Last updated:** 2026-10-25 · **Repo:** https://github.com/prashanth-ds-ml/mitra
**Plan:** [PLAN.md](PLAN.md) · **Scope:** [SCOPE.md](SCOPE.md) · **Decisions:** [DECISIONS.md](DECISIONS.md) ·
**Lessons:** [LESSONS.md](LESSONS.md) · **Open errors:** [ERROR_LOG.md](ERROR_LOG.md)

## Next
The next unticked items in [PLAN.md](PLAN.md), M0:
1. You: free RAM to >= 11-12 GB (U-006). `python bench/preflight.py --model qwen3.5:4b` must say "ready".
   On 2026-10-25 the Research Desk backend (9.6 GB) was stopped, but free RAM was still 2.7 GB of 23.6 GB.
   Next biggest: Edge 5.0 GB (42 processes), Chrome 2.1 GB, ChatGPT app 2.1 GB, Edge WebView 1.3 GB, WSL 0.5 GB.
   Close all three apps (or reboot and open nothing else) before running the screen.
2. Model screen (D-014): one model at a time, about 45 min in total, results saved to `results/model_screen.json`:
   `python bench/model_screen.py --models qwen3.5:2b llama3.2:3b qwen3.5:4b qwen2.5-coder:7b llama3.1:8b qwen3:8b granite4.1:8b rnj-1:8b ministral-3:8b lfm2.5:8b deepseek-r1:8b gemma4:e4b qwen3.5:latest`
   Optional: pull `qwen3:4b` (2507 thinking version, ~2.5 GB) first and add it. Pick one small (<= 5B) and one mid
   (7-10B) model; record them in EVALS.md and DECISIONS.md.
3. Open question: run a bench-owned Ollama server on a separate port with `OLLAMA_CONTEXT_LENGTH=65536`, leaving
   the normal one on 11434 untouched.
4. Prompt overhead of each stock agent at 64K context (Ollama's own minimum for these agents), then baselines on the
   two chosen models: `python bench/run.py --agent bench/configs/<agent>.toml --model <model>`. The agent configs are
   not yet tried end to end.
5. Kill check 1, then release v0.0 + post 1 (lock file of tested versions first)

To restart Research Desk afterwards: in `portfolio/04-local-deep-research-vertical`, run
`uv run langgraph dev --no-browser --no-reload --port 2025`.

## Bench tools
- `bench/bench.py` (tasks, grading, validate) · `bench/proxy.py` (logs every model call) ·
  `bench/preflight.py` (refuses unready runs) · `bench/run.py` (one agent x tasks, records in `results/runs/`) ·
  `bench/model_screen.py` (12 native tool-call cases per model, plus speed and GPU fit at 32K/64K)
- Stock agents installed: Claude Code 2.1.310, Codex 0.162.1, OpenCode 1.17.8, dsh 0.1.5-rc.1, Aider 0.86.2
  (uv tool, Python 3.12), deepagents-code 0.2.1 (uv tool, Python 3.14, Ollama extra)

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
