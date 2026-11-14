# The first two weeks (from 2026-11-08)

Goal: by the end, CodeMitra **records everything that matters**, has the **small tools that stop the mistakes we saw**,
can **plan a project by itself** (with your approval) and **re-plan a step that fails**, and the dashboard shows
**two weeks of real use** to judge it by. Item numbers are PLAN.md "Next up"; the why is in
[SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md).

Why this order: planning is the key differentiator (Level 01 with a given plan: 71/72; free-form brick breaker:
crash loops, same model), and every day without full recording loses data. The vault (B) comes right after.

## Week 1: record everything, small tools, start the data
| # | What | Who | Done when |
|---|---|---|---|
| 1 | Push the local commits (backup + CI on GitHub), after your OK | me | both repos pushed, CI green or failures logged |
| 2 | **Item 0**: code version, machine state, your corrections (diffs), declines, untraced calls, crashes, `/good` `/bad`, prompt + load time | me | unit tests; a live turn shows every new row; dashboard shows them |
| 3 | **Dashboard**: trends day by day; by CodeMitra version; by project / model / kind of task; first-try success, time to green | me | page shows trends from the store; "not enough data" where thin |
| 4 | **A1-A3**: `append_file`, `check_code`, `run_tests(path / -k)` + the crash-on-start hint | me | unit tests; prompt budget passes |
| 5 | E-045: make the flaky MCP start test reliable | me | passes 5 runs in a row on a busy machine |
| 6 | **Restart CodeMitra after each update; use it daily on small real tasks with tests; mark turns 👍/👎** | **you** | turns with marks appear on the dashboard |
| 7 | A6 adaptive thinking + the Level 01 benchmark (9B and 4B, on vs adaptive) | me + **night, your OK** | result in EVALS, default chosen by the numbers |

## Week 2: CodeMitra plans by itself
| # | What | Who | Done when |
|---|---|---|---|
| 8 | **`/plan`** (C13): CodeMitra writes plan.md (tasks, files, a test per task) with the 9B, thinking on; you approve or edit | me | unit tests on the format; a live plan for a small game |
| 9 | **Plan check** (C14): every task has a test, and each test **fails before** its task and **passes after** | me | a fake test (passes on empty code) is caught |
| 10 | **Re-plan a failing step** (part of C16): retry with the error, then split the step or fix an earlier one, then "needs help" | me | a fixture where a step is too big gets split and passes |
| 11 | Write levels **02 (arcade)** and **03b (DB design)**: plan, visible + hidden tests, reference | me (no GPU) | `check_level.py` passes; reference passes hidden tests |
| 12 | **Planner experiment**: level 02 with the hand-written plan vs **CodeMitra's own plan** (hidden tests decide) | night | result in EVALS: how good CodeMitra's plans are |
| 13 | **Planning numbers on the dashboard**: tasks passed first try, re-plans, needs help, plan edited by you before approval | me | shown per kind of project |
| 14 | **Two-week review** together: trends, first-try success, time to green, corrections, planner result; decide context size (E23) and what comes next (vault B or runner C15-16) | **us** | decisions in DECISIONS.md |

## Every day (both weeks)
- You: restart after updates, use CodeMitra, mark turns, tell me what felt slow or wrong.
- Me: every bug → ERROR_LOG → fix → FIX_LOG with a test; STATUS at the end of each session; no new ideas into the
  plan without your OK (SCOPE "Ideas to test").
- Nights: only one model run at a time; free RAM checked first (the start check says what to close).

## Not in these two weeks
Vault (B8-B12), runner tools and unattended runs (C15-C16 except re-plan), levels 03/04/06, tool sets, overnight
self-improve, Serena trial, experience recall (I-13, still being thought through), training (M7).
