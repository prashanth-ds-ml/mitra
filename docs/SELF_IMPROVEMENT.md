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

## 8. Open questions (for the brainstorm)
1. `/good` makes an untested turn usable for training, or only tested turns ever count?
2. Trends by day, by week, or both?
3. Your corrections are stored as diffs of your code (scrubbed of secrets, local only). OK, or only "file X was
   changed, N lines"?
4. Auto-start `mitra dashboard` at login: yes / no?
5. Anything else you want to see trending (e.g. per project, per kind of task: game / site / DB / app)?
