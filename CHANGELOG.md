# Changelog

All notable changes, newest first. Versions follow the milestones in [docs/PLAN.md](docs/PLAN.md).

## [Unreleased]

## [0.2.2] - 2026-11-10 · Mitra asks before using Kaggle (D-064)
- At every start: one check (key valid, phone verified, hours left) and one of five cases: no key → offer to
  connect; key works but not decided → "Use it? when I need it (default) / start now / later / no"; decided →
  one line or a background start; a problem → one line with the fix; already running → the status line.
- `/kaggle use now|when-needed|never` and `mitra kaggle use ...`; `/kaggle` shows the setting.
- 'when-needed' starts Kaggle on the first write work without asking again; 'Later' asks again the next day.

## [0.2.1] - 2026-11-10
- Fixed: the memory line suggested closing Windows' own `MemCompression` (E-068).

## [0.2.0] - 2026-11-10 · Kaggle and laptop, seamlessly (D-062, docs/BACKENDS.md)
- Status line shows where the model runs and the Kaggle hours left (`☁ kaggle · … · 28.1 h left` / `💻 laptop`).
- Read work (plan mode, planner, reviewer) on the laptop, write work on Kaggle; switches between turns.
- Kaggle ends (idle, time limit, quota, tunnel): laptop model (quietly smaller if RAM is short), a report of what
  was done in `.mitra/reports/`, and Mitra stops; also when it ended while Mitra was closed, and mid-turn.
- A long chat is compacted before moving to the laptop's smaller context.
- Write work with no Kaggle running: start it in the background (asked once per session).
- First start: Mitra offers to connect a free Kaggle GPU (guided).

## [0.1.2] - 2026-11-10
- Fixed: after a Kaggle run stopped by itself, `mitra` said "no compatible local Ollama models"; it now says the Kaggle GPU has stopped and uses this machine (E-067).

## [0.1.1] - 2026-11-10
- `mitra kaggle setup <token>`: Kaggle's Settings → API now gives a token string (saved to ~/.kaggle/access_token); a downloaded kaggle.json still works (`mitra kaggle setup` finds it).
- No more 15-line Kaggle library sign-in help printed twice: Mitra's own short steps only.
- README Kaggle steps follow the current Kaggle Settings page.

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
