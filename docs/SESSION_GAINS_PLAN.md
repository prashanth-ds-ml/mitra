# Session gains plan (I-7, draft 2026-11-07)

Status: **plan only, waiting for the user's go.** Four small changes that make every session better, picked by the
user from the 2026-11-07 ideas list: S1, E4, E3 (small, every session) and E2 (speed for the 9B).
Moves into PLAN.md on the go (D-011).

Each change is measured on the dashboard (D-041) before and after; the prompt stays under the 3K budget (now
1,133 tokens for the chat, 670 for solve).

## Order
E3 → E4 → S1 → M → E2. The first four are about one short session together; E2 needs a benchmark run.

---

## E3: write long files in parts
**Problem (E-044):** the 9B wrote one 5,200-token tool call for 3m20s and ended it before closing; Ollama could not
parse it. The retry note helps after the fact; this avoids it.

**Change**
- New tool `append_file(path, content)`: adds `content` to the end of a file written or read this turn. Same rules
  as `write_file`: inside the workspace, journalled for `/undo`, approval in ask mode (the card shows only the
  added lines; "yes to all" covers the rest of the turn). In the chat and in `codemitra solve`.
- One prompt line: "Write a file longer than ~150 lines in parts: write_file with the first part, then
  append_file for the rest."
- The E-044 retry note says "use append_file" instead of the edit_file trick.

**Done when**
- Unit tests: append to a new file, to a read file, refused outside the workspace and for a file not read or
  written; `/undo` removes the appended part; the approval card shows only the added lines.
- The prompt budget test still passes.
- Live: "write a 400-line report to REPORT.md" on the 9B completes in parts with no parse error (recorded in EVALS).

## E4: check a program loads before running it
**Problem (dashboard 2026-11-07):** `run_command` failed 19 of 20 times in the brick-breaker sessions, mostly the
game crashing on start (`NameError`, `UnboundLocalError`, `AttributeError`) - bugs a quick check finds first.

**Change**
- One prompt line: "Before starting a program that keeps running (a game, a server, a window), check it loads
  (run_tests, or `python -c \"import <module>\"`) and fix what fails first."
- In code, not only the prompt (small models skip rules): when `run_command` runs a program that exits within
  seconds with a traceback, the tool result ends with: "It crashed on start (line N: <error>). Fix this before
  running it again; a test for it would catch it next time." The guard counts it as a failure, as now.

**Done when**
- Unit tests: a script that crashes on start gets the hint with the right line and error; a program still
  running at the time limit (E-041) and a normal non-zero exit without a traceback do not.
- Prompt budget test passes.
- Dashboard: `run_command` failure rate is tracked per harness version (exists); judged after 20+ turns.

## S1: `/good` and `/bad <why>`
**Problem:** "improving" is now only inferred from stops and failures. Your own judgment is the strongest signal
and is not recorded anywhere.

**Change**
- `/good [note]` and `/bad [why]` mark the **last turn**. Saved as a `feedback` row (turn, verdict, note) in the
  same run record, so it reaches the store and survives with it. Repeating changes the verdict (the last one counts).
- Effects:
  - Training data: `/bad` turns are always out ("you marked it bad"); `/good` turns are usable even without tests
    (a good answer or explanation is worth learning from), still only if all CodeMitra and traced.
  - Dashboard: 👍/👎 and the note on each turn; per harness version a good/bad count; a `marked_bad` pattern
    with your notes as examples, so `codemitra improve` sees them.
- `/help` lists both; nothing is asked after a turn (no nagging).
- Your feedback row is yours (author `user`) but does not count as "written by someone else" for the turn.

**Done when**
- Unit tests: verdict recorded for the last turn; changed by a second use; no turn yet → a clear message; `/bad`
  removes a passing turn from the export, `/good` adds an untested one; author rule as above.
- Dashboard test: the marks and the pattern show on the page.

## E2: think only when it helps
**Problem:** thinking is on for every step. On the 9B a thinking step takes minutes; most steps are routine
(read the file just found, run the tests just written).

**Change**
- A setting `thinking = "adaptive"` (new default for models that can think; `"on"` and `"off"` keep today's
  behaviour). With adaptive, each model call gets thinking **on** when:
  - it is the first step of a turn (understanding the request), or
  - the step before failed (a tool error, failing tests, a refused or cut-off call), or
  - the mode is plan, or the user asked for a plan;
  and **off** for the routine steps after a successful tool call.
- Implemented per call (`stream(..., reasoning=on/off)`, Ollama's `think`), no second model.
- The trace of every call records whether thinking was on, so the dashboard can compare.
- `/think on|off|adaptive` switches it for the session; the status line shows it.

**Done when**
- Unit tests: the policy gives on/off as listed for each case; the flag reaches the model call; `/think` switches it.
- **Benchmark (the real test):** Level 01 (codemitra-playground) with the 9B, `thinking = on` vs `adaptive`: pass rate
  (hidden tests), build time, tokens. Kept as the default only if the pass rate is not lower. Same for the 4B.
  Recorded in EVALS, whatever it shows. Needs free RAM (close heavy apps; the start check says how much).

---

## M: measure prompt processing (added 2026-11-07, user agreed)
- Every trace call also saves Ollama's prompt-processing time and the number of prompt tokens it had to process
  (`prompt_eval_duration`, `prompt_eval_count` from the reply metadata), so the dashboard shows how much time goes
  to re-reading the history versus writing the answer. This decides whether a sub-agent (I-8) would cost more than
  it saves. **Done when:** a unit test sees both fields in a trace; the Models table shows median prompt seconds.

## Risks
- **Adaptive thinking makes worse choices on routine steps.** Mitigation: thinking comes back on after any failure;
  the benchmark decides the default.
- **append_file used for everything** (many tiny parts, slower). Mitigation: the prompt says "longer than ~150
  lines"; the dashboard shows calls per tool.
- **/good, /bad rarely used.** It costs nothing when unused; the other signals still work.

## Open questions
1. `/good` makes an untested turn usable for training. OK, or only tested turns ever?
2. Adaptive thinking as the default for **both** models, or the 9B only?
3. The E2 benchmark (Level 01, 9B and 4B, both settings) takes a few hours of the laptop: OK to run it, e.g.
   overnight?
