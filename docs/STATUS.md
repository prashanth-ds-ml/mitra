# Status

**Now:** first overnight build (brick breaker, 2026-11-08) + experiments registry next · **Last updated:** 2026-11-08 · **Repo:** https://github.com/prashanth-ds-ml/codemitra
**Plan:** [PLAN.md](PLAN.md) · **Scope:** [SCOPE.md](SCOPE.md) · **Decisions:** [DECISIONS.md](DECISIONS.md) ·
**Lessons:** [LESSONS.md](LESSONS.md) · **Open errors:** [ERROR_LOG.md](ERROR_LOG.md)

## Next session starts here (handoff 2026-11-08)
0000000000000000000000000000000. **2026-11-14, v0.8.0 ready, NOT published:** every doc, file name and help line says CodeMitra (the playground too); fresh clone installs and passes 1,068 tests; secret scan clean (one fake test token); README has "Upgrading from Mitra" and the + / - feedback. **Waiting for the user's go** on: GitHub rename (mitra → codemitra, mitra-playground → codemitra-playground), description + topics, milestone M1 title, push + tag v0.8.0 + release notes; local folder renames (05-mitra, mitra-stable, mitra-playground) with the uv tool reinstall.
000000000000000000000000000000. **2026-11-14, D-080 renamed to CodeMitra:** the command is `codemitra`; your ~/.mitra and each project's .mitra/ move to the new names on the first `codemitra` run (nothing lost). Records keep their format. **Not done yet (with v0.8.0):** GitHub repo rename, local folder rename (05-mitra, mitra-stable), push and tag. Older entries below say Mitra.
00000000000000000000000000000. **2026-11-14, D-079 feedback on every turn (1,058 tests):** your next message is the verdict on the last answer (unhappy / happy, recorded by itself), `+` / `-` on the empty prompt rates with one key, a rare "worked?" hint after changes, and a 1-5 key at exit. Over your 169 recorded turns it would have labelled 11 unhappy + 13 happy with no action from you. **Next:** the self-improvement plan (fair test at temperature 0 with 3-run regression check, replay cases from real failures, held-out half, "same mistake twice" number) and the shared-logs repo, both as plans in SELF_IMPROVEMENT.md for your approval.
0000000000000000000000000000. **2026-11-14, E-126 fixed (1,032 tests + 44 new):** your 22-turn Neon Chomp session on d7f9bc1 showed six faults: change requests stuck in a read-only look ("apply it manually" on 5 turns), brick-breaker's tests standing in for neon_chomp's, false "fixed" / "running successfully", the E-125 go-ahead never firing (bold questions), drift to brick-breaker, a 524 ended as "Kaggle ended". All six fixed with tests from the real turns; replayed through the new claim check, 12 of the 22 live answers would have been caught. **Not done:** a live score after these fixes (Kaggle had ended, laptop RAM 5.5 GB free). **Next:** you restart CodeMitra (stable copy) and give it the Neon Chomp controls bug as the live check (USER_TESTS).
000000000000000000000000000. **2026-11-13, E-125 fixed (not committed yet, 989 tests):** your Neon Chomp PRD in mitra-try got the same "Should I create all the initial files now?" six times while you said yes: each turn ended after the decide call, which only talked. Now a short yes to work CodeMitra offered starts that work at once (no decide call), a repeated answer gets one more decide call that is told your answer, a pasted spec/PRD is planned, and a PRD is no longer sorted as writing. Behaviour set now 15 cases (B15_yes_after_offer). Also on 11-12 (13 commits, not pushed, this file had not caught up): D-078 Phase 1 (tests after every change, honest partner, E-109..E-115), 1d about-you / outside-tech (E-116..E-119), step 6 /bad → held-out case (E-120), step 5 `codemitra practice` (MBPP+, HumanEval+, Spider; first run 13/20 → 18/20 after E-124). **Your stable copy** (`mitra-stable`) is still at 1208270, without this fix. **Next:** commit E-125, move the stable copy forward, you restart CodeMitra and paste the PRD again (or `/plan build Neon Chomp from the PRD`).
00000000000000000000000000. **2026-11-11 evening, pushed (6 commits after v0.7.0, 917 tests):** E-101 four behaviour misses fixed by prompt; D-073 `codemitra improve --chat`; E-102..E-105 from your live session (look_up phase for the web, ABOUT_CODEMITRA self-knowledge, "I said ..." is a correction signal, no false summary line); D-074 talk on the laptop, work on Kaggle (only when the conversation fits the laptop's context); E-107 a quiet start after Kaggle ended, Kaggle starts on work only; D-075 two self-improvement layers (layer 1: a round by itself at exit after 3+ new signals; layer 2: `codemitra coach` via claude -p, its rules queued for layer 1). Behaviour set 14 cases. AlphaCodium ideas I-27..I-30 in SCOPE. **Not done:** the live quick score of these fixes (GPU was busy), a live improve round, the version bump, E-106 (budget check misses the phased prompt). **Next:** you use CodeMitra (`/bad <why>` on wrong answers); `codemitra coach` when the header reminds you; the quick score when the GPU is free; then step 4/5 (the coach's code fixes match them: background app start, tests after every edit, no "fixed" without a passing run, plan validation, a turn time budget).
0000000000000000000000000. **2026-11-11, session closed** (v0.7.0 pushed, 1e811cc, 882 tests). Your ~/.codemitra now uses qwen3.5:latest (chat, planner, builder; 64K on the laptop). Self-improvement is not automatic yet (SELF_IMPROVEMENT.md section 12). **Next session starts with the user's choice:** (a) fix the 4 rule-type behaviour misses directly, or (b) wire `codemitra improve` to `codemitra score` + conversation signals first; then grow the behaviour set to the 15 scenarios, the full coding score (qwen vs mimo), step 4. User first: restart CodeMitra, try USER_TESTS v0.7.0.
000000000000000000000000. **2026-11-11, v0.7.0: One CodeMitra (D-071) + qwen3.5 (D-072)**: the phased loop is the default (decide first with no file tools, then look / change / plan); qwen3.5:latest is the model everywhere (laptop 64K, Kaggle 256K); threads memory; runaway guard, output cap, empty-answer nudge. A/B (qwen, 64K): phased 13/19 in 8.3 min > router 12/19 > one 11/19 (EVALS). **Next:** (1) the 4 remaining behaviour misses (small talk mentions the project; memory case adds the snake; brainstorm about the code should look; summary date); (2) grow the behaviour set toward the 15 scenarios; (3) the full `codemitra score` with the 10 coding tasks, qwen vs mimo; (4) step 4. User: restart CodeMitra, chat, `exit` once so threads get written.
00000000000000000000000. **2026-11-11, v0.6.4**: long answers no longer vanish while written (E-097); a working footer shows time, speed and this machine during a turn; the Claude Code-style screen parked as I-26. **Next (from the user's live session, pending their go):** (1) project review path: read everything, run the tests, write REVIEW.md, change nothing; (2) the explainer may run tests (it states unverified numbers from stale files: "36/37", "~20 tests"); (3) it re-reads the same file several times in one turn; (4) "what should we work on next" questions; then the full `codemitra score` baseline and step 4.
0000000000000000000000. **2026-11-11, v0.6.2-v0.6.3**: `codemitra <command>` typed in the chat gets a "run it in another terminal" hint (E-096); the status line shows this machine (speed, CPU, RAM free, GPU) and no token count (D-070). Pending your answer: the project review path (read everything, run tests, write REVIEW.md?) and thinking for reviews.
000000000000000000000. **2026-11-11, v0.6.1: deep dive on steps 0-3** (code review + debugging on your real records): 13 issues fixed (E-083..E-095): follow-ups keep their tools, "run/commit/failing" use the loop, codemitra.toml thinking wins, notes sent once, report has no false empty answers, dev/test workspaces never reach ~/.codemitra (10 folders moved to ~/.codemitra/data/dev-runs). Sorting set 54/54. **Next: unchanged: (1) full `codemitra score` baseline, (2) step 4.** Open: E-081 the chat's model stream has no read timeout.
00000000000000000000. **2026-11-11, v0.6.0: D-068 step 3 built: `codemitra score`** (D-069). Starting score (mimo, laptop): quick sorting 46/46 · writing 0/3 · explain 4/4 · ideas 1/2 (15 min, 2026-11-11 01:03); full not run yet. Live fixes from the user's session (E-078..E-080): talking an idea through → answered, "build it" → planned with the discussion; planner streams (Kaggle 524); report names no old night. **Next: (1) the full baseline with the coding tasks: `codemitra score` (1-3 h, laptop, e.g. overnight); (2) step 4, tolerant shell + clear test results** (score before/after). User: re-try the brainstorm on Kaggle; `codemitra score --remote` once on Kaggle.
0000000000000000000. **2026-11-10, v0.5.1: step 2b**: brainstorm / review / opinions about the project → explainer; "go with option 2" → builds; "update the plan …" → edits plan.md. 819 tests. Next: step 3 (measuring set) — scope to agree: add explain / brainstorm / review / sorting checks to it.
000000000000000000. **2026-11-10, v0.5.0: D-068 step 2 the explainer built**: a question about the code gets read-only tools, 6 steps, the last without tools (always an answer); recorded: steps, budget hit, files read, files cited, line refs, asked. Live: snake 8-22 s; CodeMitra's own code: one right (3 steps), one wrong file (6 steps). 817 tests. **Next: step 3, the measuring set + `codemitra score`.** User: ask CodeMitra about one of your projects (USER_TESTS).
00000000000000000. **2026-11-10, v0.4.0: D-068 step 1 everyday chat built**: chat / writing / general take one call, no tools, thinking off (live: mail 3.1 s, first word < 0.5 s); `~/.codemitra/me.md` + `.codemitra/notes.md` every turn; `/copy`; thinking on only for planner and debugger. 808 tests. **Next: step 2, the explainer** (questions about code: read only, 6 steps, must answer). User: restart CodeMitra, check me.md, try a mail (USER_TESTS).
0000000000000000. **2026-11-10, build order agreed (D-068, [BUILD_ORDER.md](BUILD_ORDER.md)); step 0 built**: every turn records request kind, path (loop / plan_first / resume_brief), backend, thinking, notes version, time to first word; signals rephrase / interrupt / undo (copy comes with step 1); plan-first requests are numbered turns with choice, rounds, steps passed; insights split by path / request / backend. 800 tests pass. **Next: step 1, everyday chat** (mail, writing, general; one call, no tools, thinking off; me.md + notes; /copy). Restart CodeMitra to pick up the code.
000000000000000. **2026-11-10, v0.3.0: plan first, then small steps (D-065, PLAN_FIRST.md)**: P0-P5 built; next: the user tries a big request live (plan → Go) and "where did we stop".
00000000000000. **2026-11-10, v0.2.2: CodeMitra asks before using Kaggle (D-064)**, five start-up cases + `/kaggle use`; 11 driven chat tests. The user's own first start will ask (case 2).
0000000000000. **2026-11-10, v0.2.0 published (D-062 B0-B6)**; the user's friend now clones and tests setup + Kaggle (bring their feedback/issues here). Later phase: Modal (D-063, I-24); Kaggle benchmark of CodeMitra's tasks with the AI credits (I-25).
000000000000. **2026-11-10, next: Kaggle/laptop switching** ([BACKENDS.md](BACKENDS.md), D-062): build order B0-B7 written, going through it with the user step by step; v0.1.2 (E-067 start-up fallback) pushed.
00000000000. **2026-11-10, PUBLISHED v0.1.0 + v0.1.1** (pushed as prashanth-ds-ml; tags v0.1.0, v0.1.1; v0.1.0 GitHub release is up; the v0.1.1 release page was blocked by the permission check: the user creates it with gh). v0.1.1: `codemitra kaggle setup <token>` for Kaggle's newer token, no library sign-in noise. Fresh clone from GitHub installs `mitra 0.1.1`. CI v0.1.0 green. Next: colleagues' feedback (issues labelled feedback), then fixes from it.
0000000000. **2026-11-10, v0.1.0 colleague preview ready locally**: README for first-time users, issue forms (feedback, bug), pinned deps, fresh-clone install checked, secret scan clean. Waiting for the user's go to push + tag v0.1.0 + GitHub release; then colleagues clone and send feedback (issues labelled `feedback`).
000000000. **2026-11-10: first live `codemitra kaggle start` worked** (user's laptop, no browser): queued → install → download → mimo 14.5 GB at 262144, fully on GPU → tunnel → ready; `codemitra kaggle status` ✓ answering, 1.3 h used of 30. Next: chat + `/kaggle stop` live check, then the laptop-vs-Kaggle brick-breaker experiment.
00000000. **2026-11-10, `codemitra kaggle start|stop|status` + `/kaggle` (D-061)**: no browser needed. Live-checked read-only on the user's account (username, quota 1.1 h of 30, reset Sat 05:30). The manual notebook run worked (mimo 14.5 GB 100% on GPU at 256K, 37.6 tok/s). Next: the tool reinstall (kaggle package) with CodeMitra closed, then a live `codemitra kaggle start`.
0000000. **2026-11-10, Kaggle remote built (D-060)**: `remote/kaggle/README.md` has the steps; live-tested here with the local Ollama behind the proxy (404 without token, models + facts + 256K + ☁ line through it). Next: the user runs the notebook (USER_TESTS D-060), then the laptop-vs-Kaggle brick-breaker experiment.
000000. **2026-11-10, `/free` built (D-059)** while the user's CodeMitra was open (no /run until it restarts, L-041): exit and start CodeMitra again, then `/free`. USER_TESTS has the 4 checks.
00000. **2026-11-10, restart point:** models set (D-057, D-058: mimo-v2.6:9b at 128K for chat, planner, builder; reviewer deepseek-r1:8b). The `codemitra` tool is editable (uv tool, points at this repo): just exit CodeMitra and start it again, no reinstall (E-029). After the restart: header shows mimo-v2.6:9b 128K and commit 350c372+; free RAM >= ~6 GB first (close Edge tabs); ask CodeMitra to rewrite mitra-try/brick-breaker/plan.md (the check now names T1-T5 folder paths once). Ideas waiting for the user: I-21 `/free` (name + when), I-22 Magnitude dropped by the user. Then UI polish pass A.
0000. **2026-11-09 deep dive (code review of the 22 unpushed commits + own debugging, 1 main + 1 sub agent):** 13 issues fixed, each with a regression test that fails without it (E-053..E-064, E-045; F-rows in FIX_LOG; L-042, L-043); 691 tests pass. Open: E-048 (in UI polish), and a decision for the user: `/run` builds with the chat's model, not the builder role (D-051 mimo-v2.6:9b, unscreened). Next unchanged: restart CodeMitra, rewrite brick-breaker/plan.md, UI polish pass A.
000. **2026-11-09: E-050, E-051, E-052 fixed** (CodeMitra was not running; F-050..F-052, 6 new tests). Chat `run_plan` now uses the /run plan check, runs in the plan's folder, always `python -m pytest -q`, and runs an unchanged plan once per turn; `/run plan.md 4.` drops the final period; `/good` `/bad` after a `/run` judge that night and name what they marked. **Next: restart CodeMitra**, ask it to rewrite mitra-try/brick-breaker/plan.md, then PLAN block "M2 UI polish" pass A (one item at a time).
00. **Later 2026-11-08 (docs only, no code: CodeMitra was running):** the user's mitra-try session ran CodeMitra 83f6245
   while E-049 (6a64ae6) was committed, so the chat's old plan check said ✓ and the night's new one refused (L-041).
   **Restart CodeMitra first.** Then, with CodeMitra stopped, build in order: E-050 (chat `run_plan` skips the check, wrong
   folder, model's test command, re-runs), E-051 (trailing `.` in args), E-052 (`/good`/`/bad` turn), then the
   [PLAN block "M2 UI polish"](PLAN.md) (D-056, all 40 items, one at a time, passes A → B → C). Restart CodeMitra after
   each batch so the changes show. mitra-try/brick-breaker/plan.md still fails the new check (T1 needs itself,
   `brick-breaker/` paths, bare pytest): ask CodeMitra to rewrite it after the restart.
0. 02:00 note: the user's first `/run` attempts ran an old CodeMitra in mitra-try with a plan that had 0 tasks
   (a CodeMitra-written test document, not the `### T1:` format): nothing ran. Fixed (D-054): plan check, background
   run, live view in the chat, `/night`. Verified with a real 1-minute background run in brick-breaker-night
   (cleaned up afterwards: branch deleted, project back on master).
1. **Read the night:** `C:\Users\prash\projects\brick-breaker-night\NIGHT_REPORT.md` (started by the user with
   `/run C:\Users\prash\projects\brick-breaker-night\plan.md 4`, qwen3.5:latest 256K, CodeMitra writes its own tests).
   Score it with the hidden judge (`brick-breaker-night-judge\JUDGE.md`, 25 tests, proven against a reference
   kept out of the project); compare with CodeMitra's own tests (test quality). Look at the night in the dashboard.
2. **PLAN block X** ([EXPERIMENTS.md](EXPERIMENTS.md), I-20): first registry entry, `codemitra judge`, Experiments
   section on the dashboard, model screen re-run (qwen3.5 / mimo-v2.6:9b / deepseek-r1:8b --think on), E-048.
3. **Decide I-19** ([PIPELINES.md](PIPELINES.md)): the phase loop (14e) as a LangGraph pipeline with checkpoints +
   approval interrupt + bigtool (BM25) retrieval; then week 2 of [FIRST_TWO_WEEKS.md](FIRST_TWO_WEEKS.md)
   (`/plan`, plan check, re-plan, planner experiment).
- Still open: A6 adaptive thinking (+ its benchmark night), E-045 flaky MCP test, push (several local commits; the user has not said push yet), memory clean-up offer (WSL, Research Desk server).
- Machine: Ollama 0.40.15 (flash attention + q8_0 KV); models qwen3.5:4b/latest, mimo-v2.6:9b, deepseek-r1:8b.

## Next
2026-11-08 night: A1-A3 + E4 built (append_file, check_code also after every .py write, run_tests targets, crash
hint); E-047 fixed (/model vs /mode, lost Ollama → wait + retry, real pytest summary, no input gap); overnight
stopgap `codemitra night` / `/run` (D-053). First night: C:\Users\prash\projects\brick-breaker-night (plan.md,
tests-first, CodeMitra writes tests; hidden judge in brick-breaker-night-judge). Ollama updated to 0.40.15 by the user;
mimo-v2.6:9b downloaded; model screen re-run stopped so the brick-breaker night gets the machine (user chose); re-run tomorrow (daytime). A6 adaptive
thinking and E-045 still open.

2026-11-08, role routing (D-052): `/role [name]` swaps model, max context, tools, MCP servers and thinking live;
`/model use` switches without a restart; defaults deepseek-r1:8b (planner, reviewer) and mimo-v2.6:9b (tester,
builder, debugger, deployer), falling back to the chat model until installed; builder cannot edit tests/; filesystem
MCP off; header shows roles / learning / dashboard. Downloads of deepseek-r1:8b and mimo-v2.6:9b running; the
model screen (14f) runs when they finish. Phase loop itself (planner → tester → builder ...) still to build.

2026-11-07 night, dashboard reworked after looking at it (headless Edge screenshots): most useful first
(headline with counts, trend tiles, improving per version, your judgment, where it works, sessions, tools/models,
training, then self-improvement internals with problem patterns folded); compact tables (no cut-off columns); real
tool times only (no idle gaps); output tokens instead of summed context; sessions split at each CodeMitra start;
"not recorded (older)" labels.

2026-11-07 night, item 0 built (D-044): code version, machine state, Ollama prompt/load time, your corrections
(diffs), declines, /good /bad, wrap-up / compaction / failed calls traced, crash rows; dashboard: trends day by day,
per CodeMitra version, by project / model / kind, first try, time to green, your judgment, crashes, project filter.
Live: streamed replies keep Ollama's timings (4B: load 7.6 s). No chat has run on the new code yet (0 traces):
the user waits to start. Pushed both repos earlier (11 + 1 commits). Brainstorm: I-14 friend's data, I-15 shared
knowledge base (SCOPE).

2026-11-07 late, brainstorm documented (no code): [SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md) (loop, what we
have / miss, item 0 recording design, trends, dashboard views, link); PLAN "Next up" item 0 first; the user's
running chat (started 19:18) was on pre-D-041 code: records merged by hand, restart needed for traces. The user
asked to keep brainstorming and documenting before building.

2026-11-07, MCP next steps added to PLAN M4 (no code): Serena on/off trial on a playground level, Playwright
when the first web project starts, Research Desk MCP as planned. Other candidates noted in chat (DuckDB, ABDM docs,
Docker) are not planned yet.

2026-11-07, E-046 (committed locally): compaction now at 80% of the context (was a fixed 120K, so 256K was half
unused); `/context 128k|256k|auto` switches the size live, kept per model. I-7 plan (+ step M: prompt-processing time)
and I-8 (one explore sub-agent, after M) waiting for the go; no sub-agents otherwise (user, 2026-11-07).

2026-11-07, dashboard I-6 / D-041 (committed locally, not pushed):
- Central append-only store `~/.codemitra/data/` (records + traces, every folder CodeMitra ran in, never deleted); full traces
  with thinking; turn outcomes; page `~/.codemitra/dashboard.html` with sessions, tools/MCP, models, improvement per harness
  version, training data; rebuilt on session end and by `/report`; `codemitra report --export-training`.
- Live on real data: 8 sessions / 31 turns imported, build 2.1 s; run_command failed 19/20 (mostly real game bugs, plus
  pre-E-040/E-041 cases); 0 usable training turns yet (all records predate traces).
- D-042: `codemitra dashboard` serves it on http://127.0.0.1:8765/ with a Refresh button (live check: page 25 ms
  from cache, Refresh 0.5 s).
- Next: the user looks at the page (PLAN I-6 step 6), then push. E-045 (flaky MCP start timeout under load) open.

2026-11-07 (D-039, D-040 pushed; E-044 committed locally):
- E-044: a cut-off Qwen3.5 tool call (Ollama `XML syntax error ... unexpected EOF`) no longer crashes the turn: the
  model is told and retries in parts (max 2). Seen live on "make a detailed report" (one 5.2K-token call, 3m20s).
- D-039: flash attention + q8_0 KV in Ollama; the 9B (`qwen3.5:latest`) runs at 256K (12 GB, 43% GPU); last model set
  to it.
- D-040 / E-043: memory check at every start (`app/fit.py`): one line ✓/⚠/✗, and when not comfortable the programs
  to close and a smaller option; also in `/doctor`. 15 tests; 570 pass. Live: ✗ with 6.3 GB free (VS Code 2.1 GB, a
  `pt_train.py` job 1.9 GB listed).

2026-11-06 night, self-improvement (D-038):
- Step 0 (E-033): shell chains / cd / Git Bash paths; guard counts real failures; failed commands show why.
- Step 1: harness settings (`app/core/harness.py`, `codemitra harness`), used by solve, plans and chat.
- Step 2: `codemitra report` (failure patterns from `.codemitra/runs/**/*.jsonl`, `app/core/analyze.py`) and
  `codemitra report --html` (dashboard at `~/.codemitra/dashboard.html`, `app/core/dashboard.py`). Level runs now keep their
  records in `codemitra-playground/.codemitra/runs/level-*`. First report: Level 01 run, 28 calls, 4 tool errors (reading
  paths that do not exist yet).
- Step 3: `codemitra improve` (`app/core/improve.py`): local proposer (9B by default, needs ~11 GB free RAM; `--proposer
  qwen3.5:4b` otherwise) suggests one rule / tool text / limit for the top pattern; the builder solves the bench tune
  half with the current and the proposed harness; kept only if more pass (hidden tests) at <=120% prompt tokens.
  Attempts in `~/.codemitra/harness/attempts.jsonl` and on the dashboard. Live dry run (4B proposer): "verify file
  existence with list_files before reading or editing" for the tool_error pattern, 10 s.
- Deep dive (E-036..E-039): improve looks only at the current harness version's records, model errors and broken
  grading stop the A/B, proposer unloaded + free-RAM check, worst-case harness within the prompt budget, harness
  step limit applies to `codemitra solve`, every subprocess has a timeout; health check has a self-improve step.
- Live session 2026-11-06 (brick breaker in mitra-try, user playing): E-040 (quote-blind chain split) and E-041
  (a running game reported as failed) fixed; chat prompt: project questions are answered from the files, not the web.
  Open: CodeMitra has no way to start a program and leave it running for the user (games, servers); pip installs went
  to the user Python, not a project venv.
- Next: step 4 overnight runs (needs the user's ok to create a scheduled task); more run records from real sessions.

2026-11-06 evening (all pushed; 431 tests; Windows + Linux CI green):
- **M1 core loop** (`app/core/`): one loop, 7 tools, tests decide done; `codemitra solve "task"` and `codemitra solve --plan plan.md`
  (task by task until each task's "Done when" test passes). Live: fizzbuzz solved in 4 steps / 12 s.
- **The chat runs on it** (D-037): every message is one agent loop until the model answers (tools: core + shell, web,
  MCP, run_plan); ask / auto-edit / plan modes; `/fix` = the loop until the command passes. Live: the user's
  "plan, implement, test, fix, repeat" message -> 10 steps, failing test fixed, all tests pass.
- **Old engine removed**: router, planner/brainstorm/reader/subagent/registry, file/shell/web agent loops, LangGraph
  fix workflow, work modes, plugins, advisor, cloud builders (-5,212 app lines, -2,805 test lines).
- **Level 01** (codemitra-playground): plan + 17 visible + 55 hidden tests + reference; `scripts/run_level.py`.
  Waiting on the user's ok to run CodeMitra on it.
- 4B and 9B at 128K (D-036); context use = latest prompt size (E-025).

2026-11-06, terminal assistant session (all pushed; 645 tests; Windows **and Linux** CI green, Linux blocking again):
- **Interface (D-031..D-035):** `app/ui/` with the Phosphor theme, live streaming, thinking line, one line per tool
  step, inline arrow-key approvals with coloured diffs, startup straight to the header (remembered model), framed
  input + status line, multi-line input (shift+enter), saved history, `/` and `@` menus, paste folding, esc to stop
  with type-ahead, shift+tab modes (ask / auto-edit / plan), title + bell notifications, folded output + ctrl+o.
  Mock: https://claude.ai/artifact/DgT44qmxc48rG9n3LB6hiR. Person-only key checks: USER_TESTS.md (2026-11-06).
- **Models (D-032, D-033):** only official qwen3.5 tags with 4B+ are listed; context measured on this machine:
  4B at 64K (100% GPU, 82 tok/s), 9B at 128K (47% GPU, 10 tok/s). EVALS 2026-11-06.
- **Bugs fixed:** E-016 (thinking dropped), E-017 (old/new interface mixed), E-018 (bad tool args crashed a turn),
  E-019 (questions started builds; nested project copies), E-020 (silent turns; removed commands in replies),
  E-021 (Windows quotes), E-022 (keyword routing), and the old review findings E-001, E-002, E-003, E-005.
- **Playground:** leftovers from CodeMitra's runs moved out (backup in the session scratchpad); `.codemitra/` ignored.

**Next decision (user):** go for M1, the core loop that can run plan -> implement -> test -> fix on a playground
level; it replaces the keyword router and the planner/file/shell agent hand-offs that caused E-019, E-020, E-022.
Level 01 needs its `plan.md` and tests written first (no level content exists yet). Still waiting on the user's OK:
starting the real MCP servers (downloads + GitHub token). M0 baselines still need ~10 GB free RAM.

Earlier:
2026-11-05: code renamed to Mitra (920ee63); MCP client on the official SDK with day-one servers (8a91474, D-030):
git, GitHub (remote HTTP, token from `gh auth token -u prashanth-ds-ml` via `~/.codemitra/mcp.json`), Context7,
filesystem, Semgrep on; fetch, AWS docs, Serena off. 640 tests pass (Windows CI green; Linux has the same 8 E-005
failures as before). **Not yet done:** starting the real servers (`python -m app.main mcp test <name>` from this
folder) needs the user's OK, because it downloads the packages (`uvx`/`npx`) and sends the GitHub token to GitHub's
MCP endpoint. Pin their versions after the first good start.

M2 design written: [M2_PLAN.md](M2_PLAN.md) (D-028 MCP). Models stay qwen3.5:4b + 9b (D-029).

Plan v2 agreed 2026-11-05 (D-017..D-027): terminal coding assistant on local models (M2); CodeMitra plans and builds
locally, unattended (M3); Claude Code only as a fallback; practice ladder in a separate repo `codemitra-playground`;
MCP + Harness² in M4; fine-tune last (M7). Old scope and plan in `docs/archive/`. GitHub milestones and tracking issues renamed to M0-M7 (old M8 closed).
Practice ladder repo created: https://github.com/prashanth-ds-ml/codemitra-playground (public; skeleton, plan format v0,
`scripts/check_level.py`, CI green). Both repos push as prashanth-ds-ml via a repo-local credential helper.

The next unticked items in [PLAN.md](PLAN.md), M0:
1. Baseline runs: 5 stock agents x qwen3.5:4b and qwen3.5:9b on the 10 tasks. Start the bench server first
   (`python bench/ollama_server.py`, port 11435), then per agent and model:
   `python bench/run.py --agent bench/configs/<agent>.toml --model <model>`. At ~1-15 min per run this is several hours;
   the 9B runs need ~9.6 GB free RAM by the preflight rule (it worked at 6 GB with 3.2 GB lowest, see EVALS).
2. Kill check 1 (together), then release v0.0 + post 1 (lock file of tested versions first; release check shown to you)

Done 2026-10-26: model check, prompt overhead, 64K context setup (see EVALS.md). A Med360 overnight experiment was
running on this machine (uses a remote vLLM, not the GPU); RAM was ~6 GB free.

Session closed 2026-10-26: the bench Ollama server is **not running**. Claude Code stopped it while the session was
idle because the machine ran critically low on memory (nothing lost; all results were already pushed). Before the
baselines: free RAM first (U-006: close Edge, Chrome, the ChatGPT app, or reboot), then start the server and let
preflight check RAM.

To restart Research Desk afterwards: in `portfolio/04-local-deep-research-vertical`, run
`uv run langgraph dev --no-browser --no-reload --port 2025`.

## Bench tools
- `bench/bench.py` (tasks, grading, validate) · `bench/proxy.py` (logs every model call) ·
  `bench/preflight.py` (refuses unready runs) · `bench/run.py` (one agent x tasks, records in `results/runs/`) ·
  `bench/model_screen.py` (12 native tool-call cases per model, plus speed and GPU fit at 32K/64K) ·
  `bench/ollama_server.py` (bench Ollama on 11435: 64K context, one model, one request; D-016) ·
  `run.py --overhead` (stops an agent after its first work call and records its prompt cost)
- Stock agents installed: Claude Code 2.1.310, Codex 0.162.1, OpenCode 1.17.8, dsh 0.1.5-rc.1, Aider 0.86.2
  (uv tool, Python 3.12), deepagents-code 0.2.1 (uv tool, Python 3.14, Ollama extra,
  `--with colorama`: without it its local server crashes on Windows)

## Machine
- GPU: NVIDIA GeForce RTX 5050 Laptop, 8 GB (8151 MiB), driver 610.47; `nvidia-smi` power limit N/A (default 80 W)
- RAM: 24 GB · Ollama 0.40.8 · Python 3.12 (shared root `.venv`)

## Notes
- local-codex was imported from its public GitHub version (commit dd93fa6). Its own docs, AGENTS.md, CODEMITRA.md,
  skills.md and codemitra.toml are in `docs/archive/local-codex/` (history, not instructions).
- The package is not installed into the shared venv (a top-level `app` package would clash with other projects); run
  tests from this folder with `../../.venv/Scripts/python.exe -m pytest`.
- `requirements.txt` (old pins) was dropped; a lock file from the tested versions is due before the v0.0 release.
- Shared venv has an unrelated pre-existing conflict (`langgraph-api` vs `opentelemetry-exporter-prometheus`).

## Where things are
| File | What it tracks |
|---|---|
| `CLAUDE.md` | Rules for working in this repo; read-first order |
| `docs/PLAN.md` | The checklist; tick items with dates |
| `docs/SCOPE.md` | What and why, impact scoring, ideas to test, honest limits |
| `docs/DECISIONS.md` | D-numbered decisions (append-only) |
| `docs/ERROR_LOG.md` | What went wrong (E-nnn) |
| `docs/FIX_LOG.md` | What we changed (F-nnn), incl. fixes that failed |
| `docs/LESSONS.md` | Rules learned so mistakes are not repeated (L-nnn) |
| `docs/PROGRESS_LOG.md` | Timeline + scoreboard |
| `docs/EVALS.md` | Benchmark method and every result |
| `docs/CASE_STUDY.md` | One-page story (written at v1.0) |
| `docs/USER_TESTS.md` | Only the checks that need you |
| `docs/POSTS.md` | LinkedIn drafts, links, feedback |
| `CHANGELOG.md` | Changes per release |
