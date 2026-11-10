# Changelog

All notable changes, newest first. Versions follow the milestones in [docs/PLAN.md](docs/PLAN.md).

## [Unreleased]

## [0.1.0] - 2026-11-10 · colleague preview
First version for other people to try on their own projects.
- Terminal chat on local models (Ollama): reads code, edits with your approval, runs tests and fixes failures;
  `/undo`, ask / auto-edit / plan modes, role routing (`/role`), live `/model use` and `/context`.
- Unattended plans: `/plan template`, `/plan check`, `/run plan.md <hours>` (background night runs, report).
- `/free`: tick big programs, Mitra closes them to make RAM room for the model (D-059).
- Kaggle GPU: `mitra kaggle setup|start|stop|status` and `/kaggle`, your free weekly hours at 256K context, no browser
  (D-060, D-061); `mitra remote` for any remote Ollama.
- Local dashboard (`mitra dashboard`), `/good` `/bad` feedback, everything recorded only in `~/.mitra/`.
- Deep-dive review fixes E-050..E-066 (see docs/FIX_LOG.md).
- README rewritten for first-time users; feedback and bug issue forms; dependencies pinned to tested versions.

- Project docs: scope, checklist plan, decisions, error/fix/lesson logs, progress log, evals, case study, posts.
- Imported local-codex code (561 tests passing); package renamed to `mitra` (`mitra` and `codemitra` commands).
- CI: tests on Linux and Windows, lint gate for syntax errors and undefined names, gitleaks secret scan.
- Fixed: model-advisor command crashed after finishing (E-004).
- Benchmark v0: fake payments SDK, demo shop service, 10 validated tasks with hidden tests (`bench/bench.py`).
- Bench tooling: logging proxy, preflight, run recorder with completion markers (`bench/proxy.py`, `bench/preflight.py`, `bench/run.py`).
