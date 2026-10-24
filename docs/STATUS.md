# Status

**Now:** M0 in progress · **Last updated:** 2026-10-24 · **Repo:** https://github.com/prashanth-ds-ml/mitra
**Plan:** [PLAN.md](PLAN.md) · **Scope:** [SCOPE.md](SCOPE.md) · **Decisions:** [DECISIONS.md](DECISIONS.md) ·
**Lessons:** [LESSONS.md](LESSONS.md) · **Open errors:** [ERROR_LOG.md](ERROR_LOG.md)

## Next
The next unticked items in [PLAN.md](PLAN.md), M0:
1. You: free RAM to >= 11-12 GB (close heavy apps; `python bench/preflight.py --model qwen3.5:4b` must say "ready")
2. Prompt overhead of each stock agent at 64K context (Ollama's own minimum for these agents), then baselines on
   qwen3.5:4b and qwen3:8b: `python bench/run.py --agent bench/configs/<agent>.toml --model <model>`
3. Kill check 1, then release v0.0 + post 1 (lock file of tested versions first)

## Bench tools
- `bench/bench.py` (tasks, grading, validate) · `bench/proxy.py` (logs every model call) ·
  `bench/preflight.py` (refuses unready runs) · `bench/run.py` (one agent x tasks, records in `results/runs/`)
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
