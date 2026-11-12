# Build order: must-have first, with the data for self-improvement from day 1 (D-068)

Agreed 2026-11-10. Replaces the build order in BEHAVIOUR.md section 6 (the behaviour itself stays the design).

**Goal of Phase A:** a daily assistant (mail, conversation, questions about code) that does small changes correctly,
runs medium tasks with a plan, says honestly when it cannot, has a score that shows whether it improves, and a weekly
loop where a coach (Claude, by hand at first) makes it better with every change tested.

**Self-improvement needs three things before any automation:** something that mostly works (steps 1-5), a score
(step 3) and a place for lessons (steps 1 and 6). Everything Mitra does is recorded from step 0 on, so Phase B has
weeks of data when it starts.

**Already recorded before step 0:** every session, turn and step in a central store; model-call traces (speed,
context, reloads); `/good` `/bad`; your corrections, declines, crashes; harness version per turn; training export.

Template per step: **What we build · What Mitra does after it · Why · Done when · What it records**.

---

## Phase A: must-have

### Step 0. Richer records (the base for self-improvement)
**✓ Built 2026-11-10** (`app/core/signals.py`, chat / main / insights; `tests/test_step0_records.py`).
- **Build:** every turn records its request kind and path (`chat` loop, `plan_first`, `resume_brief`, later the new
  paths), where it ran (laptop / remote), whether thinking was on, a version of your notes (`me.md` + project notes),
  the time to the first word. Quiet signs of what you thought are recorded as `signal` rows: you re-asked the same
  thing (rephrase), pressed ctrl+c (interrupt), `/undo`, `/copy` (step 1); your edits were already recorded. The plan
  path records your choice (go / change / save / cancel) and how many rounds it took.
- **Mitra after:** nothing visible; the dashboard data can be split by path.
- **Why:** a coach can only improve what it can see: without these we cannot tell if a bad week came from sorting,
  the role, the model or Kaggle.
- **Done when:** tests show each new field in a record; old records still load; `insights.breakdown(by="path")` works.
- **Records:** this step is the records.

### Step 1. Everyday chat (mail, conversation, daily work)
**✓ Built 2026-11-10** (`intent.py` chat/writing/general, `ChatSession.reply`, `signals.notes_text`, `/copy`, thinking table; `tests/test_step1_everyday.py`). Live on mimo-v2.6:9b (laptop, 32K): "hi" 1.0 s, mail 3.1 s, "make it shorter" 2.4 s, LoRA vs QLoRA 8.7 s; first word 0.3-0.5 s (the old loop with thinking: 4.1 s to the first word, 14.3 s). Open: it signed "Thanks," instead of the exact "Regards," (step 3 writing checks will measure it).
- **Build:** sorting gains `chat / writing / general` (mail, message, reply, draft, summarise, rewrite, translate →
  writing); these take a one-call path with no tools and thinking off; thinking off by default, on only for planner
  and debugger; `~/.mitra/me.md` (name, signature, tone, stack, "use uv") + `.mitra/notes.md` per project, both read
  every turn and edited by hand; `/copy` copies the last answer.
- **Mitra after:** "hi" answers at once with where we stopped; "draft a mail to the team about the Kaggle setup" gives
  a mail in your style in under 15 s and "shorter" / "more formal" refines it; summarise / rewrite / translate pasted
  text; general questions answered directly.
- **Why:** fixes "hi mitra" (19 steps) and the 5-minute thinking; makes Mitra useful every day, not only for code.
- **Done when:** driven chat tests: "hi" → 1 call, 0 tools; a mail → 1 call with your signature; a code request is
  still sorted as code.
- **Records:** kind and path per turn, `/copy` (you used it), rephrase (you did not like it).

### Step 2. Questions about code (explainer)
**✓ Built 2026-11-10** (`ChatSession.explain`: list_files / search / read_file only, `explain_max_steps` = 6, the last step without tools; `tests/test_step2_explain.py`). The 2 questions are asked in the answer, not by an `ask_user` tool (simpler for a small model). Live on mimo-v2.6:9b: the snake level, 4 questions in 8-22 s, 2-4 steps, files cited, nothing changed; Mitra's own code: request sorting right in 3 steps (21 s); "Kaggle stops mid-turn" used all 6 steps (38 s) and answered, but read the wrong file (kaggle.py, not chat.py/main.py): a wrong-place answer the step 3 set must catch.
**2b (2026-11-10, v0.5.1):** brainstorming, reviews and opinions about the project go to the explainer too (ideas: 3-5 options with trade-offs, then a pick); "go with option 2" then builds it; "update the plan with …" edits plan.md in place. Live: brainstorm 50 s (6 steps, 8 ideas, some misread), review 44 s (2 steps, one wrong point).
- **Build:** an explainer role: read only (outline, search, read a part), 6 steps, must end with `answer`; `ask_user`
  for at most 2 questions when it truly cannot start.
- **Mitra after:** "explain the game logic" answered in under a minute with file:line references and no edits.
- **Why:** questions are the most common daily request and today they wander.
- **Done when:** driven test: no write tools offered, ≤ 6 steps, an answer always.
- **Records:** steps used, budget hit or not, files cited.

### Step 3. The measuring set and the starting score
**✓ Built 2026-11-11** (D-069: `score/`, `app/core/score.py`, `mitra score`; `tests/test_step3_score.py`). `mitra score --validate`: every reference passes, every start state fails. Starting score on mimo-v2.6:9b (laptop): quick sorting 46/46 · writing 0/3 · explain 4/4 · ideas 1/2 (15 min, 2026-11-11 01:03); full not run yet. Kaggle: `mitra score --remote` (not run yet).
- **Build:** 10 tasks in mitra-playground with hidden checks and a reference solution (written by Claude): 5 drills on
  your own code, 2 brick-breaker features, the endpoint fix, the dataset clean-up, the evaluation script; plus 3
  writing checks (key facts present, signature, length). `mitra score` runs them and appends to
  `results/scores.jsonl` with the Mitra version, harness version, notes version, model and machine.
- **Mitra after:** nothing visible; you get a number: "small 4/7 · medium 1/3 · writing 3/3".
- **Why:** the judge of every later change (mine or the coach's), and the "before" for steps 4-5.
- **Done when:** every reference solution passes its checks; `mitra score` runs on the laptop and on Kaggle.
- **Records:** the score history, the coach's main input.

### Step 3b. One Mitra: one conversational loop instead of routed paths (D-071)
**✓ Built 2026-11-11 (v0.7.0):** behaviour category (10 cases), `--arch router|one|phased`, one Mitra, the phased loop (decide with only look_at_code / make_change / propose_plan, then act with that phase's tools), threads, runaway guard + 8,192-token cap + empty-answer nudge; qwen3.5:latest replaces mimo (D-072). A/B on the laptop at 64K with qwen3.5: **phased 13/19 (8.3 min)**, router 12/19 (13.1 min), one 11/19 (8.6 min); mimo's best was 11/19 in 25 min. Phased is the default. Still failing: small talk mentions the project folder, the memory case adds the snake game, brainstorms about the code do not look first, a summary date slip.
- **Build:** (1) a *behaviour* category in `mitra score` (talk turns use no tools, stay short, no report headings,
  ask back when you are deciding; code questions read the right file; a change request changes it) and every score
  case run through the chat's own entry, so the architecture is a switch; baseline of today's router.
  (2) One Mitra behind a switch (`architecture = "one"`): one prompt ("your thinking partner and coder: talk
  naturally, use tools only when the answer needs your files or you asked for a change"), all tools, thinking off,
  the last step always answers, a lighter context (your notes + a short "where we are", no night runs or stale
  plans every turn). Fixed rules stay only where they are faster or exact: /commands, `mitra ...` typed in the chat,
  "where did we stop". (3) Conversation memory as threads: what was said, decided and left open per discussion;
  ideas in a global store, project work in the project; the relevant thread loaded per turn.
  (4) A/B on the same score, laptop and Kaggle; the winner becomes the default; the losing paths are deleted.
- **Mitra after:** you talk with it like with Claude; it looks at the code only when that is needed; "let's continue
  the web app idea" works in a new session.
- **Why:** the user's live sessions (2026-11-11): every substantial reply was a 190-320 word report with 3-8 headings;
  conversation went to the code reader; ideas were forgotten. Root causes R1-R7 (STATUS 2026-11-11). One loop is also
  simpler to self-improve: one prompt and one harness to tune instead of six paths.
- **Done when:** the behaviour category runs on both architectures; the A/B result is in EVALS.md; the default is set
  by the score, not by opinion.
- **Records:** architecture per turn (path "one"), tool calls per talk turn, reply length and headings, threads used.

### Step 4. Tolerant shell and clear test results
- **Build:** `run_command` quietly handles `| tail/head`, `2>&1`, `cd x &&`, bare `pytest` instead of refusing;
  `run_tests` returns each failure as name, file:line, error and a few lines of context.
- **Mitra after:** fewer wasted steps; it fixes the right line more often.
- **Why:** these were the most common tool errors in the records.
- **Done when:** unit tests for each form; the drill score does not drop.
- **Records:** which normalisation fired; tool error rate before and after.

### Step 5. The small-change path
- **Build:** build → code runs syntax, the task's test and all tests → debug at most 2 rounds → honest report (what
  changed, the checks, what is left).
- **Mitra after:** "add a pause key to brick breaker" ends green with a report, or "I could not: here is why; this
  may suit Claude Code".
- **Why:** the primary target: small tasks done correctly, never a false "done".
- **Done when:** the small-task score beats the step 3 starting score.
- **Records:** debug rounds used, final check result, honest stop vs success.

### Step 6. Medium tasks live + the first coach session by hand
- **Build:** fixes from the first live plan-first run; `docs/COACH.md` (the weekly checklist Claude follows);
  `~/.mitra/lessons.md` (cue, lesson, evidence, confidence; Harness² style); each harness change kept only if the
  score holds or rises.
- **Mitra after:** a medium task runs end to end (plan → Go → steps → report); after week 1 its first tested lessons.
- **Why:** closes the self-improvement loop by hand before building the automation.
- **Done when:** one real medium task done; the first coach session kept at least one change, with the score.
- **Records:** coach reports, lessons with evidence, score before and after each change.

---

## Phase B: automate self-improvement (after 2-3 weeks of Phase A data)

| # | What | Built from |
|---|---|---|
| B1 | `mitra coach`: digest from the records, Claude via `claude -p`, automatic A/B on the score | step 0 records, step 3 scores, COACH.md |
| B2 | Learn from your corrections: proposes `me.md` / notes lines, you approve | rephrase and correction signals |
| B3 | AI-engineer profile pack (skills: eval, RAG, LoRA) | tasks where scores stay low |
| B4 | `mitra do tasks/x.md`; pieces handed over from Claude Code | |
| B5 | Tester / builder split, checkpoint per step, continue after a crash | medium-task failures |
| B6 | Direct MCP tools per role (git, context7), then the Serena trial | measured on the score |
| B7 | Reviewer with semgrep, deployer, Modal, other profiles | |

## Agreed order (D-077, 2026-11-12)

Local first: everything works on the laptop with no internet; Kaggle when online and a job needs it. The numbers in
brackets are the must-haves in D-077 each item serves. Steps 4-5 above are items 2-4 here.

| # | Item | Serves | Status |
|---|---|---|---|
| 1 | No claim without a source: the decide step's query runs (E-109), "confirmed"/"tests pass" checked against the turn's tool results (E-110), honest "offline" | 3, 6 | done 2026-11-12 |
| 1b | Partner basics (D-078, must-have 13): no opening praise, agree only with a reason; "deep dive" = at least 3 queries and 4-5 pages with a bigger budget | 13 | done 2026-11-12 |
| 1c | Honest self-description: ABOUT_MITRA also says what Mitra cannot do yet, kept in step with this table | 7 | done 2026-11-12 |
| 2 | Tests after every change, retry with the failing output | 5 | done 2026-11-12: `auto_test_rounds` 3 |
| 3 | No "done" without a passing test in the same turn | 6 | done 2026-11-12 |
| 4 | Read before edit; no accidental whole-file overwrite | 4 | done: read-before-edit existed (tools.py); 2026-11-12 write_file refuses to shrink a 20+ line file to under half |
| 5 | Coding practice set (`mitra practice`): Python (MBPP+, newer LiveCodeBench) and SQL (Spider subset on SQLite) first, MongoDB later with our own tasks (user 2026-11-12); hidden tests judge, Mitra writes its own tests; split learn / held out | 10 | |
| 6 | Your real failures (/bad) become score cases | 10 | |
| 7 | Honest keep/drop gate: re-run the cases that changed, no new failures, held-out set | 11 | |
| 8 | Threads add, never overwrite | 12 | |
| 9 | Better signals: the 4B reads your next message against a checklist; optional per-session rating at exit | 9 | |
| 10 | General web search: SearXNG on Kaggle (one-cell engine test first) | 7 | |
| 11 | Knows its tools and limits; installed package docs first | 7 | |
| 12 | Read files outside the project, read-only, asks first | 4 | |
| 13 | Kaggle crash-safety, stream timeout (E-081), fast offline detection | 2, 3 | |

Later: night runs on the practice set with a morning report; friends' feedback (scrubbed export/import file); Kiwix
offline docs (refreshed monthly); lessons from verified work; test anchors; tests first; loop detection; veto a rule
before use; project map; 4B + 9B together; docs MCP; diff view; the coach on a schedule; fine-tuning last (D-021).

## Frozen until Phase A is done
New subsystems, new MCP servers, new backends, profile packs, dashboard work, UI polish beyond what a step needs.

## Defaults agreed (2026-11-10)
- Clarifying questions: at most 2, only when it truly cannot start.
- Too hard: try within the budget, then stop honestly and suggest Claude Code.
- Learning from you: `me.md` and project notes you edit by hand; reading your own commits later.
- `me.md` seeded with your name, mail signature, tone (concise), stack (Python, LangChain, Ollama, FastAPI), "use uv".
- Step order: the score (step 3) after the chat and explainer paths, before any code-path change.
