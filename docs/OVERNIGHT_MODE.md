# Overnight mode: PRD → running app on localhost, unattended (I-16, brainstorm 2026-11-07)

Status: **design for discussion; nothing built.** User: "a mode where mitra has full access to do anything in the
project workspace and build the project and deploy in localhost for testing and demo ... follow a prd ... over
night for 3 to 4 hrs ... we try not to give any instruction, we let it self improve and fix itself".

It completes M3 (unattended runner, D-025) and the C block of PLAN "Next up", plus the pieces below.

## A night, end to end
| When | Who | What |
|---|---|---|
| Evening (~10 min) | you + Mitra | discuss the idea; `/prd` writes `PRD.md` (or bring your own); Mitra writes `plan.md` from it; you approve the plan (2 min, recommended); `mitra overnight PRD.md --hours 4` |
| 0 Preflight | Mitra (you still there) | 9B at 256K fits? (else what to close); disk; git repo + branch `mitra/overnight-<date>`; project venv; keep Windows awake; time budget set |
| 1 Plan | Mitra | thinking on: tasks with files and a test each, ending with "app runs on localhost and answers"; plan check (red-then-green); skipped if you approved a plan already |
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

## One model all night: qwen3.5:latest (9B) at 256K (user, 2026-11-07)
- **No model switching**: the 9B stays loaded the whole night (no reloads), at **256K = its maximum native context**
  (262,144; going beyond needs RoPE scaling and loses quality, so not done). Slow is fine at night.
- Speed: ~8 tok/s measured at 256K (12 GB, 43% GPU); with other apps closed it should be at least that. A step with
  thinking ~60-120 s → **~120-200 model steps in 3-4 h**.
- Long nights: compaction at ~205K (E-046), a handoff after the second compaction (I-9), so the context stays clean.
- **The memory check happens before you leave**: at the evening start Mitra checks the 9B at 256K fits comfortably
  and, if not, says what to close (D-040) while you are there. During the night nothing is switched: if RAM gets
  critical Mitra pauses, and stops cleanly if it does not recover. Disk is checked the same way.
- Laptop: Mitra keeps Windows awake during the run; plugged in; the GPU power cap still applies.
- To measure once, not a default: KV cache `q4_0` instead of `q8_0` (more of the model on the GPU, faster; may cost
  quality): one benchmark night before deciding.

## Fixing itself, no instructions
Retry with the error → re-plan the step (split it, or fix an earlier step) → "needs help", skip it and the tasks that
depend on it, keep going. Every decision is recorded (records + traces), so the morning shows what it tried.

## Self-improvement: separate from the build
No rule changes in the middle of a build (it would make the run unreliable and unjudgeable). The night records
everything; if time is left after the build, `mitra improve` may run on the night's failure patterns with the usual
benchmark gate. Next nights then start with the improved harness, and the dashboard compares nights per version.

## What fits in 3-4 hours (honest)
One model, the 9B at 256K, ~8 tok/s; a step ~60-120 s with thinking → **~120-200 model steps a night**. Enough for a small-to-medium project
(arcade game, portfolio site, small FastAPI + SQLite app with tests). A large product needs several nights with
handoffs, or a plan of plans. The plan is the weak spot: approving it before bed is the best insurance.

## New pieces (beyond the C block)
1. `/prd`: Mitra writes a PRD from the discussion (goals, features, out of scope, acceptance = tests, how to run it).
2. Overnight profile: full access inside the project, the limits above, kill switch, time budget.
3. Keep-awake during the run.
4. Evening memory/disk check for the 9B at 256K; pause/stop on critical RAM at night (no switching).
5. Deploy step with a health check (needs `start_program`, `setup_env`, `http_request`).
6. Morning report (+ dashboard view per night: tasks done, needs help, time, tokens, demo URL).

## First trials
1. Level 02 (arcade game) from a PRD, hidden tests decide (also the planner experiment, 14c).
2. One of your real ideas, small first.

## Decisions (user agreed to the defaults, 2026-11-07)
| Question | Default |
|---|---|
| Plan | **You approve it before you sleep** (2 min). If not approved in time, Mitra runs on its own plan and the report says so |
| Network at night | **Package installs and web search allowed, inside the project only** (project venv / node_modules; every install listed in the report); nothing else: no push, no uploads |
| After the build | **The app stays running on localhost** for the morning demo; the report gives the link and the stop/restart command; nothing is left running if the build failed |
| Leftover time | **Stop when the build is done**; no `mitra improve` during a night at first (the night's failures are recorded for the next day) |
| Time budget | **Until done, at most 4 hours** (`--hours` changes it per night) |

## Better-looking demos (user agreed, 2026-11-07)
1. **Design-kit skill** (not an MCP): a light CSS framework (e.g. Pico.css or Tailwind via CDN), colour and spacing
   tokens, 3-4 page layouts (landing, dashboard, form, game screen); Mitra fills in a proven design instead of
   inventing one. Offline, plain HTML, the default style for overnight builds.
2. **Visual self-check**: Playwright + `screenshot` (qwen3.5 has vision) before "done", and in the overnight deploy step.
3. **shadcn/ui MCP** (official, local, free) for React / Next.js web apps, when those start (level 06, real apps).
4. **Not used:** Figma Dev Mode MCP (user: no, 2026-11-07, D-047), 21st.dev Magic (API key, cloud; breaks
   local-only); local image generation (does not fit next to the 9B on 8 GB).
Names and terms of each server checked before adding.

## Open questions (answered above)
1. Approve the plan before you sleep (recommended), or fully hands-off from the PRD?
2. At night: allow package installs into the project and web search, or offline only?
3. After the build: leave the app running for the morning demo, or stop it and print the command?
4. Leftover time: `mitra improve` on the night's failures, or stop when the build is done?
5. Time budget: fixed (3-4 h), or "until done or N hours"?
