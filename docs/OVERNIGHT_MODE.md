# Overnight mode: PRD → running app on localhost, unattended (I-16, brainstorm 2026-11-07)

Status: **design for discussion; nothing built.** User: "a mode where mitra has full access to do anything in the
project workspace and build the project and deploy in localhost for testing and demo ... follow a prd ... over
night for 3 to 4 hrs ... we try not to give any instruction, we let it self improve and fix itself".

It completes M3 (unattended runner, D-025) and the C block of PLAN "Next up", plus the pieces below.

## A night, end to end
| When | Who | What |
|---|---|---|
| Evening (~10 min) | you + Mitra | discuss the idea; `/prd` writes `PRD.md` (or bring your own); Mitra writes `plan.md` from it; you approve the plan (2 min, recommended); `mitra overnight PRD.md --hours 4` |
| 0 Preflight | Mitra | free RAM / VRAM / disk → model and context; git repo + branch `mitra/overnight-<date>`; project venv; keep Windows awake; time budget set |
| 1 Plan | Mitra | 9B, thinking on: tasks with files and a test each, ending with "app runs on localhost and answers"; plan check (red-then-green); skipped if you approved a plan already |
| 2 Build | Mitra | task by task: code → tests → fix → re-plan the step when stuck → "needs help" and skip after N rounds; one commit per task |
| 3 Deploy | Mitra | start the app on a free port, health check (HTTP 200 / process alive / smoke test); leave it running for the demo or stop it and print the command |
| 4 Report | Mitra | morning report (and a handoff in the vault once B exists): tasks done / needs help, tests, demo URL, time, tokens, dashboard link |
| Morning | you | open the demo, read the report, mark the run 👍/👎, decide the next night |

## Full access, inside the project only
- Edits and commands run without approval, **only inside the project folder**, on its own branch, commit per task:
  everything can be undone.
- Packages only into the project's own venv / `node_modules`; never the system Python.
- Never: `git push`, deleting outside the folder, system settings, credential stores; every command has a timeout.
- Kill switch: `.mitra/STOP` file or ctrl+c; automatic stop at the time budget or critical RAM.

## Flexible with free resources
- Before the run and at every step: free RAM, VRAM and disk.
- Model choice: plenty free → 9B 256K; less → 9B 128K; tight → 4B. Default **"9B plans, 4B builds"**: the 9B writes
  the plan and does re-plans, the 4B (~3x faster) does most of the coding; one model loaded at a time, each switch
  ~10-20 s.
- If RAM drops (an app opened, a leak): smaller context or the 4B, or pause until it recovers (the M3 RAM guard).
- Disk: check free space for traces, venv and builds; stop cleanly when low.
- Laptop: Mitra keeps Windows awake during the run; plugged in; the GPU power cap still applies.

## Fixing itself, no instructions
Retry with the error → re-plan the step (split it, or fix an earlier step) → "needs help", skip it and the tasks that
depend on it, keep going. Every decision is recorded (records + traces), so the morning shows what it tried.

## Self-improvement: separate from the build
No rule changes in the middle of a build (it would make the run unreliable and unjudgeable). The night records
everything; if time is left after the build, `mitra improve` may run on the night's failure patterns with the usual
benchmark gate. Next nights then start with the improved harness, and the dashboard compares nights per version.

## What fits in 3-4 hours (honest)
9B ~8 tok/s, 4B ~27 tok/s; a step ~30-90 s → **~150-300 model steps a night**. Enough for a small-to-medium project
(arcade game, portfolio site, small FastAPI + SQLite app with tests). A large product needs several nights with
handoffs, or a plan of plans. The plan is the weak spot: approving it before bed is the best insurance.

## New pieces (beyond the C block)
1. `/prd`: Mitra writes a PRD from the discussion (goals, features, out of scope, acceptance = tests, how to run it).
2. Overnight profile: full access inside the project, the limits above, kill switch, time budget.
3. Keep-awake during the run.
4. Resource-adaptive model and context choice, with "9B plans, 4B builds".
5. Deploy step with a health check (needs `start_program`, `setup_env`, `http_request`).
6. Morning report (+ dashboard view per night: tasks done, needs help, time, tokens, demo URL).

## First trials
1. Level 02 (arcade game) from a PRD, hidden tests decide (also the planner experiment, 14c).
2. One of your real ideas, small first.

## Open questions
1. Approve the plan before you sleep (recommended), or fully hands-off from the PRD?
2. At night: allow package installs into the project and web search, or offline only?
3. After the build: leave the app running for the morning demo, or stop it and print the command?
4. Leftover time: `mitra improve` on the night's failures, or stop when the build is done?
5. Time budget: fixed (3-4 h), or "until done or N hours"?
