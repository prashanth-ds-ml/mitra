# Experiments: what we test, how it shows, how it improves CodeMitra (plan, 2026-11-08)

Status: **plan; nothing of the registry or the dashboard section is built.** The experiments themselves are listed in
PLAN.md "Next up"; this file is how their results are kept and shown.

## Why
Today results live in different places (EVALS.md text, `results/*.json`, NIGHT_REPORT.md, the hidden judge's
pytest output). The dashboard shows sessions and trends, but not the experiments' answers. Every default CodeMitra uses
(model per role, thinking, context, Serena) should point to the experiment that chose it.

## The registry: one file per experiment run
`results/experiments/<date>-<id>.json` (in the CodeMitra repo, committed; plus a copy in the central store):
```json
{
  "id": "night-brick-breaker-01",
  "question": "Can CodeMitra build a game unattended from a plan, writing its own tests?",
  "kind": "night | screen | level | planner | ab | improve",
  "date": "2026-11-08",
  "setup": {"model": "qwen3.5:latest", "num_ctx": 262144, "thinking": "auto", "mitra": "c889be8",
            "harness": 0, "plan": "brick-breaker-night/plan.md", "hours": 4},
  "metrics": {"tasks_passed": 0, "tasks_total": 7, "own_tests": "…", "judge": "…/25", "minutes": 0,
              "steps": 0, "reloads": 0, "crashes": 0, "needs_help": []},
  "compare_with": ["night-brick-breaker-02"],
  "verdict": "short text, written after looking at the numbers",
  "decision": "D-0xx or empty"
}
```
Written automatically where possible: `codemitra night` writes the night's entry (from its result + NIGHT_REPORT),
`codemitra judge` (new, small) runs a hidden judge and adds the score, `bench/model_screen.py` and
`scripts/run_level.py` write theirs. The verdict and decision are filled in by us after looking.

## The dashboard section "Experiments"
- A table: date · experiment · question · setup (model, context, thinking, CodeMitra version) · headline numbers ·
  verdict · decision link.
- Side-by-side comparisons for experiments that name each other (`compare_with`): night A vs night B, qwen3.5 vs
  mimo vs deepseek, thinking on vs adaptive, Serena on vs off; better numbers marked.
- Each night links to its sessions (the existing Sessions view, filtered to that project and time) and its report.
- "What chose this default": for every role / setting, the experiment and decision behind it.

## The planned experiments
| # | Experiment | Answers | Writes |
|---|---|---|---|
| 1 | Brick-breaker night (2026-11-08) | unattended build from a plan; CodeMitra's own tests vs the hidden judge (test quality) | night + judge |
| 2 | Model screen | tool calls, speed, GPU fit: qwen3.5 / mimo-v2.6:9b / deepseek-r1:8b (re-run; first attempt void) | screen |
| 3 | Builder comparison | mimo vs qwen3.5 on Level 01 (hidden tests) | level |
| 4 | Planner eval | deepseek-r1:8b vs qwen3.5 plans (plan check, red-then-green) | planner |
| 5 | Planner vs hand-written plan (14c) | quality of CodeMitra's own plans, level 02 | level |
| 6 | Nights A/B (D-048) | 9B only vs deepseek plans + mimo builds, same PRD | night × 2 |
| 7 | Adaptive thinking (A6) | always-on vs adaptive: time, pass rate | level × 2 |
| 8 | Serena on/off | tokens, time, right-tool rate, pass rate | level × 2 |
| 9 | KV `q4_0` (optional) | speed vs quality | screen / level |
| 10 | `codemitra improve` A/B (built) | a proposed rule kept only if more hidden tests pass | improve (exists) |
| 11 | Daily use (observation) | first try, time to green, your fixes, 👍/👎 over time | the trends (exist) |
| 12 | Pipeline in LangGraph vs `run_plan` ([PIPELINES.md](PIPELINES.md)) | same pass rate? resume after a kill works? bigtool retrieval vs all tools | level × 2 |

## How they improve CodeMitra
- Defaults by data: role models (2-4, 6), thinking (7), context (11 → E1), Serena (8), KV cache (9).
- What to fix: every run feeds the failure patterns `codemitra improve` works on; nights show where it gets stuck alone.
- Proof: every change compared per CodeMitra version / harness version; hidden tests or 20+ turns decide.
- Test quality: own tests vs hidden judge (1) tells whether the tester phase is needed and how strict it must be.
- Training data: verified turns (tests passed, judge passed, 👍) accumulate for the fine-tune.

## Build steps (first job after the brick-breaker night)
1. Score night 1 with the judge; write its registry entry (by hand the first time, it shapes the format).
2. `codemitra judge <judge-tests-folder>` + `codemitra night` writing entries automatically.
3. Dashboard "Experiments" section (table, comparisons, "what chose this default").
4. Model screen re-run (2) writing its entry.
