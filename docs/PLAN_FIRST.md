# Plan first, then small steps (D-065)

Small models have little context and compute. CodeMitra should not let them explore their way to an answer; it should
hand them the right small context and have them work in small, planned, checked steps.

Seen 2026-11-10 (mitra-try, "hi mitra where did we last stop"): 13 tool calls and no answer. Seven went to made-up
`/logs/brick-breaker/...` paths (project memory listed the slash command `/logs` as a topic), three whole files were
read (286 + 402 + 267 lines) for a question CodeMitra's own records answer, a `| tail` was refused, and a pytest warning
page filled the screen. The user stopped it.

**Status 2026-11-10: P0-P5 built and tested (unit + driven chat tests), v0.3.0.**

## The flow

1. **Sort the request** (no model call):
   - *where did we stop / status / history* → answered from the **resume brief** (P1);
   - *a question about the code* → answered with the **context pack** (P2);
   - *a small change* (one clear edit) → done directly, as before;
   - *a bigger change* → **plan first** (P4). `/plan <task>` and `/do <task>` override the sorting.
2. **Plan, and discuss it** (read work: on the laptop when Kaggle is in use). The planner gets the context pack and
   writes 3-7 small steps in the runnable plan format (`### T1:` … `- Done when:` …), checked by `plans.check_text`.
   You see it: **Go** · **Change it** (say what; the planner revises) · **Save** (for `/run` later) · **Cancel**.
   In ask mode CodeMitra waits for Go; in auto mode it shows the plan and starts (the user's "go with defaults").
3. **Do the steps one at a time, each with a fresh small context** (the existing plan runner: each task is solved
   with only the plan's notes, the task and its files, until its Done-when check passes). A step that still fails
   is re-planned once (only that step), then it is your call.
4. **Wrap up and remember**: a short summary and `.codemitra/resume.md` (plan, steps done, next step, failing checks):
   the next "where did we stop" is instant and right.

## Build order

### P0. Quick fixes from the session
- Slash commands and `!` commands are no longer stored as "topics" in project memory; existing ones are ignored
  when the memory is loaded.
- "outside the workspace" / "not a file" errors suggest the real path when one matches (`brick-breaker/plan.md`).
- The shell rules (one command, no pipes or `cd`, `python -m pytest`) are in `run_command`'s description.
- Python warning blocks (`...Warning: ...`, `warnings.warn(...)`) are folded in the tool output shown on screen.

### P1. Resume brief
- `app/core/resume.py`: last session's requests and outcomes, `.codemitra/resume.md` (P5), the latest Kaggle-ended
  report, plan / night progress, `git log -5`, `git status`. Put in the system prompt at start (short, capped), and
  used directly to answer "where did we stop".

### P2. Context pack
- `read_file` on a large file without a range returns an **outline** (classes / functions with line numbers) plus
  the first lines, and says how to read a part; the project's file tree and outlines feed the planner.

### P3. Sorting the request
- `app/core/intent.py`: rules (no model call) → resume | question | small | big; `/plan <task>` forces a plan,
  `/do <task>` skips it.

### P4. Planner + discussion
- `app/core/planner.py`: one planner call with the context pack and the plan template; the plan check feeds
  problems back once; the menu Go / Change / Save / Cancel; plans saved in `.codemitra/plans/`.

### P5. Steps, checks, re-plan, wrap-up
- Runs the plan with the existing runner (fresh context per step, Done-when check, rollback of a failed step; no
  new git branch in the chat); failed steps re-planned once; summary; `.codemitra/resume.md` written.

Each step: tests that fail without it; the full suite; then the next step. Released together as v0.3.0.
