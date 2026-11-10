# Changelog

All notable changes, newest first. Versions follow the milestones in [docs/PLAN.md](docs/PLAN.md).

## [Unreleased]

## [0.5.1] - 2026-11-10 · brainstorming and reviews about your code (D-068 step 2b)
- "brainstorm ideas to make the game harder", "review game.py", "pros and cons of …" read the code first
  (explainer); ideas come as 3-5 options with trade-offs, and "go with option 2" builds the one you pick.
- "update the plan with …" / "add a task to plan.md" edit the plan in place instead of planning a feature.

## [0.5.0] - 2026-11-10 · questions about code (D-068 step 2)
- A question about the project ("explain the game logic", "where is the API defined?") gets read-only tools
  (list_files, search, read_file) and 6 steps; the last step has no tools, so there is always an answer, with
  path:line references. A vague one may be answered with up to 2 short questions. Live: 8-22 s on a small project.
- Recorded per question: steps used, budget hit, files read, files cited, line references, asked back.

## [0.4.0] - 2026-11-10 · everyday chat + records for self-improvement (D-068, docs/BUILD_ORDER.md)
- Small talk, writing (mails, messages, summaries, rewrites, translations, "make it shorter" after one) and general
  questions are sorted without a model and answered in one call with no tools and thinking off. Live on mimo-v2.6:9b:
  "hi" 1.0 s, a team mail 3.1 s, first word 0.3-0.5 s.
- `~/.mitra/me.md` (name, signature, tone, stack; created on the first start) and `.mitra/notes.md`, read every turn.
- `/copy`: the last answer to the clipboard.
- Thinking off by default; on only for the planner and the debugger.
- Every turn records its kind, path, machine, thinking, notes version and time to the first word; quiet signals
  (asked again, stopped, `/undo`, `/copy`); plan-first and "where did we stop" are counted as turns.

## [0.3.0] - 2026-11-10 · plan first, then small steps (D-065, docs/PLAN_FIRST.md)
- "Where did we stop?" answered from Mitra's records (resume brief, also in the prompt), no model call.
- Requests sorted without a model: resume / question / small / big; `/plan <task>`, `/do <task>`.
- Bigger changes: a short runnable plan from a small context pack (file tree + outlines), Go / Change / Save /
  Cancel, steps run one at a time with fresh context and their own test, failed steps re-planned once,
  `.mitra/resume.md` written.
- Large files read without a range give an outline first.
- Fixed: slash commands were stored as project-memory topics (a model chased `/logs/...` paths); wrong paths
  now suggest the real file; `run_command` states its rules; Python warning blocks folded on screen.

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
