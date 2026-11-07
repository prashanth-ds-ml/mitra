# Self-improvement: how Mitra gets better as you use it (design, brainstorm 2026-11-07)

Status: **design notes from the 2026-11-07 discussions; nothing in "missing" is built.** The build order is in
PLAN.md "Next up" (item 0 first). Related plans: [DASHBOARD_PLAN.md](DASHBOARD_PLAN.md) (built, D-041/D-042),
[SESSION_GAINS_PLAN.md](SESSION_GAINS_PLAN.md) (I-7), [HANDOFF_VAULT_PLAN.md](HANDOFF_VAULT_PLAN.md) (I-9, I-10).

## 1. The loop
```
 use ─► 1 record ─► 2 judge ─► 3 find patterns ─► 4 propose a fix ─► 5 test the fix ─► 6 keep or undo
  ▲                                                                                         │
  └──────────── 7 remember (project facts, lessons) · 8 train (fine-tune, later) ◄──────────┘
```
Rule for every stage: **measured, never claimed**. A change counts as an improvement only when the numbers after it
are better on enough turns (20+) or on hidden tests.

## 2. Each stage: what we have, what is missing, how it helps

| Stage | Have (2026-11-07) | Missing | How it helps |
|---|---|---|---|
| 1 Record | step records; full traces with thinking (new sessions); central never-delete store; turn outcome; model + context per turn | Mitra code version, machine state, prompt-processing time, wrap-up / compaction / failed calls, crashes (item 0, A5) | every result tied to *which Mitra* under *which conditions*: fair before/after |
| 2 Judge | inferred: tests passed/failed, stopped by you, tool failures, retries | **your verdict** (`/good` `/bad`, A4), **your corrections**, **declined edits** (item 0) | ground truth: "answered" does not mean "right" |
| 3 Find patterns | `analyze.py` failure patterns (missing files, no tests after code, interrupted, ...) | patterns from your marks and corrections; "check_code would have caught this" (A2) | fix what hurts you most first |
| 4 Propose | `mitra improve`: local 9B proposes one rule / tool text / limit for the top pattern | proposals from real-session patterns (E24) | fixes aimed at your real problems |
| 5 Test | A/B on the bench tune half; kept only if more hidden tests pass at <=120% tokens | more levels per kind (D17-20), night runs (D22, your OK) | proven on many tasks before it reaches you |
| 6 Keep / undo | versioned harness, `mitra harness revert N` | auto-suggested undo when real-session numbers get worse after a change (E24) | bad "improvements" do not stay |
| 7 Remember | `.mitra/context.md` (hidden from Obsidian); compaction summaries lost | the vault: facts, `remember` / `recall`, summaries, handoffs (B8-B12) | no relearning the same project every session |
| 8 Train | `mitra report --export-training` | usable turns (needs use + marks), before/after pairs (S3), fine-tune (M7) | the model itself gets better at your work |

Weakest stage today: **2 (judge)**, then **7 (remember)** and the **volume** behind 4, 5 and 8.

## 3. Found 2026-11-07: the running session was on old code
The chat started at 19:18; the store and traces (D-041) were committed at 19:52. That session kept writing its
normal record (merged into the store by hand, 40 lines) but no traces and no outcomes. **A restart (`exit`, then
`mitra`) loads the new code** (checked: the `mitra` command imports this repo). Until the code version is
recorded (item 0), the dashboard cannot split sessions before and after such a change.

## 4. Item 0: record everything that helps self-improvement (design)
Small additions to what is already recorded; each has a dashboard view (section 6).

| Signal | How it is captured | Row |
|---|---|---|
| **Mitra code version** | short git commit of the Mitra repo (+ `-dirty` if uncommitted changes), read once per process with a timeout | `code_version` on `turn_start` / `start` and in trace calls |
| **Machine state** | at session start: model, context, memory-fit verdict, free RAM, free VRAM; per turn: free RAM (cheap) | `session` row; `ram_free_gb` on `turn_start` |
| **Your corrections** | at the end of each turn Mitra keeps the content it left in the files it changed; at the next turn start it compares; a file you changed in between is a correction, saved with a short diff (scrubbed, capped) | `user_edit` (author `user`, `of_turn` = the turn it corrects) |
| **Declined edits / commands** | where an edit approval is refused (`_before_write`) and where a command is declined (`ShellResult.denied`), with your reason if given | `declined` (author `user`, tool, path or command, reason) |
| **Calls not traced yet** | the wrap-up call at a step limit, the compaction call, and failed calls (E-044 parse errors, model errors: input saved, reply empty, error text) | trace `call` with `error` / `purpose` (`wrap_up`, `compact`) |
| **Crashes** | the chat's error handler also writes a row (error + last traceback lines), not only `.mitra/errors.log` | `crash` |
| **Prompt-processing time** (A5) | from Ollama's reply metadata: prompt tokens processed, prompt time, generation time, **load time** (shows model reloads) | on each trace `call` |
| **Your verdict** (A4) | `/good [note]`, `/bad [why]` on the last turn; the last one counts | `feedback` (author `user`, `of_turn`, verdict, note) |

Rules:
- Rows written by you (`user_edit`, `declined`, `feedback`) attach to the turn they judge and **do not** make that
  turn "written by someone else" for training (D-022 is about Claude output, not your judgment).
- Training data: `/bad` and corrected turns are out (kept as "before" for future before/after pairs, S3);
  `/good` turns are usable even without tests (open question 1).
- Nothing is sent anywhere; the store keeps it all (D-041).

## 5. Trends: how Mitra changes with use
Two views, both from the store:

**a) By day (or week), usage and health over time** - one row per metric, a small line per metric, the latest
value and the change since the first week:

| Metric | Shows |
|---|---|
| sessions, turns, model steps, tool calls | how much Mitra is used |
| tokens in / out per turn, context used (median, max) | cost and context pressure |
| steps per turn, seconds per turn, tok/s, prompt-processing seconds, model reloads | speed |
| tool failures per turn, retries per turn, crashes | robustness |
| tests passed share, finished share (not stopped / interrupted) | results |
| 👍 / 👎, your corrections per turn, declined per turn | your judgment |
| usable training turns (cumulative) | progress to the fine-tune (target 300) |

**b) By Mitra version (and harness version), is it improving** - the same metrics per version, so a code change or
a learned rule shows as a before/after. "Not enough data" under 20 turns.

Small inline SVG lines (no chart library), so the page stays one local file.

## 6. Dashboard: what each view adds
Existing: Sessions, Tools, Models, Is Mitra improving (by harness version), Training data, Problems, Learned rules,
Improve attempts, Harness history, Playground results.

To add (with item 0, A4, A5 and trends):
- **Trends** (section 5a) at the top.
- **Is Mitra improving** grouped by **Mitra version · harness version**, with 👍/👎, corrections, declines, tokens
  and tok/s columns (section 5b).
- **Sessions**: machine state on each session line; 👍/👎, corrections and declines on each turn; a project filter;
  all sessions listed (folded), not only the newest 40.
- **Your corrections and declined edits**: per session, with the diff or reason.
- **Crashes**: time, error, session.
- **Models**: prompt-processing seconds and model reloads.
- **What Mitra learned**: each rule with its effect since it was added (failures per turn before → after).

## 7. The dashboard link
- Live: **`http://127.0.0.1:8765/`**, always the same, while `mitra dashboard` runs (Refresh button). If the port is
  taken it says so; `--port` picks another.
- File: **`C:\Users\prash\.mitra\dashboard.html`**, always the same, rebuilt when a Mitra session ends.
- Option (not decided): start `mitra dashboard` at Windows login (a scheduled task, a few MB of RAM).

## 10. Breaking work down is the key differentiator (user, 2026-11-07)
Evidence: the same 4B scored 71/72 on Level 01 with a good plan and tests, and looped on crashes free-form
(brick breaker). Four parts, all needed:
1. **A good plan** (the weakest spot for a small model): you approve it; plan templates per kind of project from
   levels that passed (experience recall, I-13); a plan of plans for big projects.
2. **Small steps**: each task fits one short context (a few files, one test).
3. **Every step checked**: red-then-green (the test fails before, passes after), so "done" is proven.
4. **Recovery**: retry with the error, then re-plan the step (split it, or fix an earlier one), then "needs help".
Today: 2-4 partly work (`run_plan`, tests decide, fresh rounds). Missing: the planner (`/plan`, plan check) and
re-planning, now first after item 0 and A1-A5 ([FIRST_TWO_WEEKS.md](FIRST_TWO_WEEKS.md)). Measured per kind of
project: tasks passed first try, re-plans, needs help, plan edited by you before approval, and the planner
experiment (hand-written plan vs Mitra's own plan on the same level).

## 11. More users (brainstorm 2026-11-07): I-14, I-15 in SCOPE
- A friend's sessions: export on his machine, import into your store under his name; explicit consent, incl. for
  training. The version and machine fields from item 0 keep mixed data comparable.
- A shared knowledge base: only general, reviewed, benchmark-passed lessons; personal and project memory stays in
  each person's vault. Pooled verified turns reach the training target faster, with consent.

## 9. Does the model's reasoning improve with use? And training on usage (brainstorm 2026-11-07)
**The model's own reasoning does not change with use**: Ollama runs fixed weights. What improves with use is
everything around it, so its *effective* reasoning (model + what it is told) gets better:
1. the harness (learned rules, tool texts, limits from `mitra improve`);
2. memory (project facts, handoffs, lessons in the vault);
3. when it thinks (adaptive thinking, E2);
4. **experience recall (new idea, I-13):** for a task like one solved before (tests passed or 👍, not corrected),
   a short "how it was solved" note is put in the prompt. Learning from examples, no training; uses the vault;
5. a better base model when one comes out (model screen, one command to switch).

**Training on usage data (M7, rules in SCOPE / D-022): yes, planned.**
- Data: only verified turns (tests passed or 👍, no corrections, all Mitra, traced), with the thinking.
- Methods: fine-tune on its own verified trajectories (rejection-sampling fine-tuning / STaR style) + learning
  what to avoid from 👍/👎 (KTO, which needs no matched pairs) and before/after pairs (DPO, S3).
- Then: GGUF into Ollama as a new model, model screen + playground hidden tests vs the base model; **kept only if
  it wins on held-out tasks**.
- Limits: mostly teaches behaviour (tool choice, your style, fewer format mistakes); deep reasoning gains need far
  more data than a few hundred turns. The 4B fits a QLoRA run on the 8 GB GPU with sequences cut to ~4-8K tokens;
  the 9B on long traces likely needs a rented GPU (to decide later; D-025 local-only is about running Mitra).
  Training on its own outputs can amplify mistakes, hence verified turns only and the held-out test. Check the
  Qwen licence before training (believed Apache 2.0).
- What to do now: restart Mitra after updates, use it on tasks with tests, mark turns 👍/👎: every verified turn
  becomes a training example.

## 8. Answers (user, 2026-11-07)
| # | Question | Answer |
|---|---|---|
| 1 | `/good` on an untested turn | **Usable for training**, marked `untested` in the export so a training run can leave such turns out or give them less weight |
| 2 | Trends | **Day by day** |
| 3 | Your corrections | **Store the diffs**: capped ~4K chars per file, secrets scrubbed, never for `.env`-like or binary files, local only (the diff is the "after" half of a before/after pair) |
| 4 | Dashboard start | **Only when you run `mitra dashboard`** (no auto-start at login) |
| 5 | More trends | By **project**, **model**, **kind of task** (game / site / DB / app / other, from the project's files); two headline numbers: **first-try success** (tests pass, no correction from you) and **time to green** (first code edit to tests passing) |
| 6 | Experience recall (I-13) | **Open, think it through**: how "similar" is judged, stale solutions, a wrong lesson repeated, token budget |
| 7 | Training and domain reasoning | Corrected together: Research Desk MCP + the vault add **knowledge and context** (better in the domain from day one, no change to the model); training on verified usage changes **behaviour in the domain** (stack, conventions, tool choice, fewer repeat mistakes: a narrow reasoning gain); much harder tasks than the base model can do are not expected from a 4B/9B and a few hundred examples: they come from `/plan` breaking work into tested steps. Knowledge + behaviour + structure together; held-out domain tests show what each adds |

## 9. Does the model's reasoning improve with use? And training on usage (brainstorm 2026-11-07)
**The model's own reasoning does not change with use**: Ollama runs fixed weights. What improves with use is
everything around it, so its *effective* reasoning (model + what it is told) gets better:
1. the harness (learned rules, tool texts, limits from `mitra improve`);
2. memory (project facts, handoffs, lessons in the vault);
3. when it thinks (adaptive thinking, E2);
4. **experience recall (new idea, I-13):** for a task like one solved before (tests passed or 👍, not corrected),
   a short "how it was solved" note is put in the prompt. Learning from examples, no training; uses the vault;
5. a better base model when one comes out (model screen, one command to switch).

**Training on usage data (M7, rules in SCOPE / D-022): yes, planned.**
- Data: only verified turns (tests passed or 👍, no corrections, all Mitra, traced), with the thinking.
- Methods: fine-tune on its own verified trajectories (rejection-sampling fine-tuning / STaR style) + learning
  what to avoid from 👍/👎 (KTO, which needs no matched pairs) and before/after pairs (DPO, S3).
- Then: GGUF into Ollama as a new model, model screen + playground hidden tests vs the base model; **kept only if
  it wins on held-out tasks**.
- Limits: mostly teaches behaviour (tool choice, your style, fewer format mistakes); deep reasoning gains need far
  more data than a few hundred turns. The 4B fits a QLoRA run on the 8 GB GPU with sequences cut to ~4-8K tokens;
  the 9B on long traces likely needs a rented GPU (to decide later; D-025 local-only is about running Mitra).
  Training on its own outputs can amplify mistakes, hence verified turns only and the held-out test. Check the
  Qwen licence before training (believed Apache 2.0).
- What to do now: restart Mitra after updates, use it on tasks with tests, mark turns 👍/👎: every verified turn
  becomes a training example.

## 8. Open questions (for the brainstorm)
1. `/good` makes an untested turn usable for training, or only tested turns ever count?
2. Trends by day, by week, or both?
3. Your corrections are stored as diffs of your code (scrubbed of secrets, local only). OK, or only "file X was
   changed, N lines"?
4. Auto-start `mitra dashboard` at login: yes / no?
5. Anything else you want to see trending (e.g. per project, per kind of task: game / site / DB / app)?
6. Experience recall (I-13): worth planning, and before or after the vault?
7. Training: 4B locally first, and is a rented GPU for the 9B acceptable later?
