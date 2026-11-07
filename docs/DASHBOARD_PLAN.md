# Dashboard plan (I-6, finalized 2026-11-07)

Status: **built 2026-11-07 (D-041), steps 0-5 done, step 6 waiting for your look at the page.** Checklist in PLAN.md.
Change from the plan: no separate `--import` flag; every build merges old records into the store (append-only, 0.1 s).

## Why
One page that answers four questions from Mitra's own records:
1. **What did Mitra do?** Each session as a timeline: your message → model steps → tool calls → test results.
2. **How does it use its tools?** Calls, failures and time per tool (core tools, shell, web, MCP servers).
3. **Is it improving itself?** Results per harness version over time, and every `mitra improve` attempt.
4. **Is the training data piling up?** How many runs are usable for the fine-tune (D-022), and why the rest are not.

Not in scope: a live server, editing anything from the page, cloud anything, charts made for posts (later).

## Decisions (user, 2026-11-07)
| Question | Decision |
|---|---|
| Who is it for | You first (understanding + debugging); a screenshot may go in a post later |
| Form | Static page (`~/.mitra/dashboard.html`), **rebuilt automatically when a session ends**, plus `/report` in the chat to rebuild and open it now. No server, no new dependency |
| Never lose data | **All history accumulates and is never deleted.** Every run is copied into a central append-only store `~/.mitra/data/` (records + traces); the page reads only from there, so deleting a project or its `.mitra/` loses nothing. The 8 existing record files are imported once |
| Traces | **Everything + thinking**: full input messages, reply, tool calls, thinking, timings; secrets scrubbed |
| "Improving" means | **Both**: playground hidden-test pass rate per harness version, and real-session signals (stops, retries, tool failures, steps per turn) |
| Which projects | **Every folder Mitra ran in**: Mitra notes each project folder it starts in (`~/.mitra/projects.json`); the store holds all of them, labelled by project |

## What exists
- `app/core/dashboard.py`: static page with playground results, problem patterns, learned rules, improve attempts,
  harness history. Rebuilt by hand with `mitra report --html`.
- `app/core/loop.py` `Recorder`: JSONL per run in `<project>/.mitra/runs/`, kinds `turn_start/turn_end`, `model`,
  `tool`, `tests`, `bad_tool_call`, `stopped`, `compact`, `rollback`, ...; `author` on every row; secrets scrubbed.
- 8 record files, 0.4 MB so far: the data is thin, so the page must work well with little data.

**Gaps for training data:** text is cut (model 4,000 / tool 3,000 / user 2,000 chars); the system prompt, tool specs and
the exact messages the model saw are not saved; a model step is not linked to whether its tests later passed.

## Steps
Each step is small, tested, and usable on its own.

### Step 0: Central store (never lose data)
- `~/.mitra/data/runs/<project-slug>/<run>.jsonl` (+ `traces/`): the Recorder writes each row to the project's
  `.mitra/runs/` **and** to the store (append-only; Mitra never deletes or rewrites a stored file).
- `~/.mitra/projects.json`: every folder Mitra started in (path, first/last seen).
- `mitra report --import`: one-time (and safe to repeat) copy of existing records from all known folders and the
  playground into the store; files already there are skipped by content hash.
- `/doctor` shows the store size and where it is (it is one folder, easy to back up).
- **Done when:** a test deletes a project's `.mitra/` and the dashboard still shows its sessions; importing twice
  adds nothing; the 8 existing files are in the store.

### Step 1: Recorder v2, full traces (training data)
- Next to each run record, `traces/<run>.jsonl`: per model call the full input messages, the full reply (text,
  thinking, tool calls), model, num_ctx, harness version, timings. No length cuts. Secrets scrubbed as today.
- The system prompt and tool specs are saved once per run in `traces/<run>.prompt.json` and referenced by hash, not
  repeated per call.
- `turn_end` gets `outcome`: tests passed / failed / none run, stopped by you, error, so every step can be labelled.
- Traces go to the central store too (step 0). A setting `save_traces = true` (default on); size in `/doctor`.
- **Done when:** unit tests show a full turn can be rebuilt from its trace (same messages the model got); a
  secret in a tool output never reaches a trace; a live chat writes a trace that `mitra report` reads.

### Step 2: Session timeline
- Page section "Sessions": newest first; each session opens to its turns; each turn shows steps as rows
  (model step, tool + args summary, ok/✗, seconds, tokens), retries (`bad_tool_call`), stops and test results.
- Long outputs folded (click to open), so the page stays readable.
- **Done when:** the brick-breaker session from 2026-11-07 shows its List → Read → cut-off tool call in order;
  a test feeds a recorded session and checks the rows.

### Step 3: Tools and models
- Table per tool (and per MCP server): calls, failure rate, median and worst time, most common error.
- Per model: sessions, tok/s, average context use vs num_ctx, memory fit seen at start (D-040).
- **Done when:** numbers match a hand count on a fixture of two sessions.

### Step 4: Is it improving
- Per harness version: playground pass rate (hidden tests), and from real sessions: turns finished without a stop,
  tool failures per turn, retries per turn, steps per turn. A small inline SVG line per signal (no chart library).
- Improve attempts (exists) linked to the version they created.
- Honest note on the page when a version has too few turns to judge (fewer than 20 turns: "not enough data").
- **Done when:** a fixture with two harness versions shows the right trend and the "not enough data" note.

### Step 5: Training data
- Counts: traced runs, usable runs (finished, tests passed, author = mitra, no scrub hits left), and why the rest are
  out (failed, stopped, no tests, other author, missing trace). Progress toward the SCOPE target (a few hundred
  passing runs before any fine-tune).
- `mitra report --export-training out.jsonl`: usable runs only, in chat format (messages + tool calls). Nothing
  is sent anywhere.
- **Done when:** a fixture with mixed runs exports only the usable ones; D-022 rules (no Claude output) checked by test.

### Step 6: Auto-rebuild + release check
- The page is rebuilt from the store when a chat session ends (exit or ctrl+c; a failed rebuild never blocks the
  exit), and by `/report` in the chat (rebuild + open) or `mitra report --html`. Health check gets a dashboard step.
- EVALS/STATUS/FIX_LOG updated; the user looks at the page with real data before it is pushed.

## Order and size
Steps 0 and 1 first: they are the only ones that change what is saved, and every day without them loses data.
Steps 2-5 only read the store, in that order (2 is the most useful while testing); 6 last. Roughly one working
session per step.

## Risks
- Trace size: about 1-5 MB per long session at 256K, kept forever by decision. Mitigation: prompt saved once per run,
  size shown in `/doctor`; a few hundred sessions is still well under a few GB. Nothing is deleted automatically.
- One copy on one disk: `~/.mitra/data/` is a single folder; backing it up (e.g. to a drive or a private repo) is
  your call and not automated.
- Secrets in full tool output: the same scrubber as run records, plus a test with planted secrets.
- Little data: every section says "not enough data yet" instead of drawing a misleading trend.
