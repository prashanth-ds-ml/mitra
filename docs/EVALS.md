# Evals

Method and every result, whatever it shows. Raw results live in `results/` and are rerun with one command
(`mitra bench`, from M2). Each result section names the git commit, models, agent configs and machine state.

## Method
- **Benchmark v0 (2026-10-24):** `bench/base` is a small FastAPI shop (`shop/`) on a fake internal payments SDK
  (`paysdk/`: integer paise, `Result` type, idempotency keys, raised rate limits, cursor pagination, a deprecated
  method). Each task in `bench/tasks/` is a ticket-style prompt plus exact find/replace "breaks" applied to the correct
  base: 7 planted bugs and 3 removed features. The agent's workspace = base + breaks + one visible repro test.
- **Grading:** in a separate copy of the workspace, the hidden tests (edge cases the prompt implies but the visible test
  does not check) are added and the whole suite runs. Pass = every test passes and no protected test file (base tests,
  visible tests) changed; hashes come from the task source, never the workspace. Hidden tests are never in the
  workspace. A pytest exit code other than 0/1 is recorded as an infra error, not an agent failure.
- **Validity:** `python bench/bench.py validate` proves, for every task, that the start state fails and the reference
  solution (the base code) passes; `tests/test_bench.py` runs it in CI with tamper and isolation checks.
- **Split:** tune = T01 T03 T05 T07 T09; held-out = T02 T04 T06 T08 T10. No fix is shared across the halves
  (e.g. the two charge-list bugs were merged into one held-out task). Tuning uses only the tune half.

| Task | Split | Kind | Trap it tests |
|---|---|---|---|
| T01 | tune | bug | float rupees lose paise; fix must use `Money.from_rupees` (hidden test rejects 3 decimals) |
| T02 | heldout | bug | stops after the first page; must follow `next_cursor` |
| T03 | tune | bug | `Result` used without checking `.ok`; must map the SDK error code to 409 |
| T04 | heldout | bug | no retry on raised `RateLimited`; must wait `retry_after`, 4 attempts max |
| T05 | tune | bug | idempotency key changes per attempt; must be stable per order |
| T06 | heldout | feature | new endpoint with exact response shape, 404 and unpaid cases |
| T07 | tune | bug | `CurrencyMismatch` uncaught; 422 and the order must not be saved |
| T08 | heldout | bug | double pay; 409 without calling the provider |
| T09 | tune | feature | order limit with an inclusive boundary |
| T10 | heldout | feature | refund the rest, including "nothing left" |

- **Agents compared and their configs:** `bench/configs/`
- **Models:** exact Ollama tags and quantisation
- **Machine:** GPU, VRAM, power cap, RAM, Ollama version, context length
- **Metrics:** pass rate, fixed prompt tokens, broken tool calls, turns, wall time; from M3: frontier tokens, ₹, GPU Wh
- **Rules:** same tasks, same model, same context and timeout for every agent; runs repeated N times; failures kept

## The measuring set (D-068 step 3, D-069): `mitra score`

Every run appends a row to `results/scores.jsonl` (versions, model, machine, every case).

| Date | Mitra | Model | Machine | Score | Failed |
|---|---|---|---|---|---|
| 2026-11-11 01:03 | 0.5.1 | mimo-v2.6:9b | laptop | sorting 46/46 · writing 0/3 · explain 4/4 · ideas 1/2 | W1_team_mail: signature not exactly: Regards, / Prashanth; W2_leave_mail: signature not exactly: Regards, / Prashanth; W3_summary: missing: 1 February; I1_harder: 10 options (want 3-5) |
| 2026-11-11 10:22 | 0.6.0 | mimo-v2.6:9b | laptop | writing 1/1 · explain 1/1 (only W1_team_mail, X4_wall: live check after the deep dive) | none |

## One Mitra A/B (D-071, D-072): router vs one loop vs decide-then-act, mimo vs qwen3.5

Laptop (RTX 5050 8 GB). Same quick set: behaviour 10 · writing 3 · explain 4 · ideas 2 (+ sorting, no model).

| Date | Architecture | Model | Context | Score | Model cases | Time | Failed |
|---|---|---|---|---|---|---|---|
| 2026-11-11 14:37 | router | mimo-v2.6:9b | 32K | sorting 54/54 · behaviour 5/10 · writing 1/3 · explain 2/4 · ideas 0/2 | **8/19** | 32 min | B2_thinking: empty answer; B4_deciding: used tools to talk: list_files, search, read_file, read_file; B5_think_with_me: missing fact: (?i)rat(e|ing); B6_general: report-style: 2 headings; B10_remembers: should not match: (?i)\bsnake\b; W2_leave_mail: signature not exactly: Regards, / Prashanth; W3_summary: missing: 1 Feb; X2_grow: missing fact: score; X4_wall: wrong claim: (?i)wraps? around|bounces?|teleport; I1_harder: empty answer; R1_review: empty answer |
| 2026-11-11 14:57 | one | mimo-v2.6:9b | 32K | sorting 54/54 · behaviour 6/10 · writing 0/3 · explain 2/4 · ideas 1/2 | **9/19** | 20 min | B5_think_with_me: empty answer; B6_general: report-style: 2 headings; B7_look_grow: answered about the code without reading it; B10_remembers: empty answer; W1_team_mail: signature not exactly: Regards, / Prashanth; W2_leave_mail: signature not exactly: Regards, / Prashanth; W3_summary: missing: 1 Feb; X2_grow: did not cite snake/game.py; X4_wall: did not cite snake/game.py; I1_harder: did not cite snake/game.py or web/index.html or snake/api.py |
| 2026-11-11 15:51 | one | mimo-v2.6:9b | 32K | sorting 54/54 · behaviour 6/10 · writing 1/3 · explain 3/4 · ideas 1/2 | **11/19** | 25 min | B4_deciding: TimeoutError: timed out after 600 s (no answer from the model); B5_think_with_me: empty answer; B6_general: too long for a conversation: 202 words (max 180); B10_remembers: should not match: (?i)\bsnake\b; W2_leave_mail: signature not exactly: Regards, / Prashanth; W3_summary: missing: 1 Feb; X4_wall: wrong claim: (?i)wraps? around|bounces?|teleport; I1_harder: did not cite snake/game.py or web/index.html or snake/api.py |
| 2026-11-11 16:05 | one | qwen3.5:latest | 32K | sorting 54/54 · behaviour 5/10 · writing 2/3 · explain 0/4 · ideas 1/2 | **8/19** | 5 min | B3_how_are_you: should not match: (?i)\bsnake\b; B5_think_with_me: report-style: 3 headings; B6_general: report-style: 2 headings; B9_change: empty answer; B10_remembers: should not match: (?i)\bsnake\b; W3_summary: should not match: (?i)^(here is|here.s|sure); X1_game_logic: missing fact: score; X2_grow: did not cite snake/game.py; X3_bad_direction: did not cite snake/api.py; X4_wall: wrong claim: (?i)wraps? around|bounces?|teleport; I1_harder: empty answer |
| 2026-11-11 16:28 | phased | qwen3.5:latest | 64K | sorting 54/54 · behaviour 7/10 · writing 2/3 · explain 3/4 · ideas 1/2 | **13/19** | 8 min | B2_thinking: did not ask back (you were deciding); B3_how_are_you: should not match: (?i)\bsnake\b; B10_remembers: should not match: (?i)\bsnake\b; W3_summary: missing: 1 Feb; X2_grow: missing fact: score; I1_harder: did not cite snake/game.py or web/index.html or snake/api.py |
| 2026-11-11 16:37 | one | qwen3.5:latest | 64K | sorting 54/54 · behaviour 7/10 · writing 2/3 · explain 1/4 · ideas 1/2 | **11/19** | 9 min | B7_look_grow: did not cite snake/game.py; B8_look_api: did not cite snake/api.py (cited snake/game.py); B10_remembers: used tools to talk: read_file, read_file, read_file; W3_summary: missing: two; X2_grow: missing fact: score; X3_bad_direction: did not cite snake/api.py (cited snake/game.py); X4_wall: wrong claim: (?i)wraps? around|bounces?|teleport; I1_harder: did not cite snake/game.py or web/index.html or snake/api.py |
| 2026-11-11 16:50 | router | qwen3.5:latest | 64K | sorting 54/54 · behaviour 5/10 · writing 2/3 · explain 4/4 · ideas 1/2 | **12/19** | 13 min | B2_thinking: too long for a conversation: 61 words (max 60); B4_deciding: empty answer; B5_think_with_me: report-style: 4 headings; B6_general: report-style: 3 headings; B10_remembers: should not match: (?i)\bsnake\b; W3_summary: missing: two; I1_harder: did not cite snake/game.py or web/index.html or snake/api.py |

## Phase 1 baseline: the noise of the quick score (D-078)

Laptop (RTX 5050 8 GB), qwen3.5:latest, phased, 64K, commit bdff454 (D-077 #1 in), harness v0, the same code three
times in a row, 2026-11-12. Quick set: behaviour 14 · writing 3 · explain 4 · ideas 2 = 23 model cases (+ sorting 54).

| Run | Time | Score | Model cases |
|---|---|---|---|
| 1 (15:12) | 11.6 min | sorting 54/54 · behaviour 11/14 · writing 2/3 · explain 4/4 · ideas 1/2 | **18/23** |
| 2 (15:25) | 12.7 min | sorting 54/54 · behaviour 10/14 · writing 2/3 · explain 4/4 · ideas 1/2 | **17/23** |
| 3 (15:39) | 13.8 min | sorting 54/54 · behaviour 11/14 · writing 3/3 · explain 4/4 · ideas 1/2 | **19/23** |

- **Noise:** the total moved by up to 2 (17-19) on unchanged code, and **6 of 23 cases (26%) changed result** at
  least once across the three runs: B2_thinking, B6_general, B7_look_grow, B10_remembers, B12_knows_itself,
  W3_summary. Always failing: I1_harder (does not cite the project files). Always passing: explain 4/4, R1_review.
- **What it means:** a gain or loss of 2 on one run is inside the noise, so the D-073 gate (keep at +2 on one run) is
  close to a coin toss, as the research said; Phase 3 step 7 (re-run what changed, held-out set) is needed. For
  Phase 1, a change counts as a regression only if a case that passed in all three baseline runs now fails, or the
  total falls below 17.
- **Against before #1** (2026-11-11 16:28, behaviour on the old 10-case set 7/10): no case that worked broke.

**Phase 1 check** (commit 1aeb15c: tests after every change, no "done" without a pass, write guard, partner basics,
honest self-description), 2026-11-12 16:59: sorting 54/54 · behaviour 10/14 · writing 2/3 · explain 4/4 · ideas 1/2
= **17/23**, inside the baseline's 17-19; **no regression** (no case that passed in all three baseline runs fails).
Failed: B6_general (185 words, too long), B9_change (changed nothing), B12_knows_itself (no "Kaggle"), W3_summary
(opened with "Here is"), I1_harder (no file cited). B9 had failed in all three baseline runs: its record showed the
model looked first, then could not switch to the change phase (E-114, fixed in F-106 after this run).

**1d + step 6 check, and an explain drift** (2026-11-12 evening): quick score 20:08 = 17/23, but X2_grow and X4_wall
(passing in all four earlier runs) failed. X4 was a scoring bug (E-121: the denial "doesn't wrap around" counted as
the claim). X2 and later runs: correct answers citing "Line 39" with no file. Explain-only runs that evening:
current code with the 1d line 7/12 passed, without it 5/12, and **the Phase 1 commit itself (1aeb15c, explain 4/4 at
16:59) 7/12**: not a code change. Same model digest and Ollama settings; free RAM had fallen from ~10 GB (morning) to
3-4 GB and only 5.5 of 7.7 GB of the model sat on the GPU. Conclusion: explain drifts with machine conditions on
this laptop; a regression check compares runs made under the same conditions only. Phase 3 starts with a fresh
baseline (after a restart), never mixing morning and evening runs.

## Coding practice (D-078 step 5, `mitra practice`)

Laptop (RTX 5050 8 GB), qwen3.5:latest, phased, 128K. 20 tasks (the fixed first 20), Python from MBPP+/HumanEval+,
SQL from Spider; hidden checks decide.

| Date | Code | Passed | Python | SQL | Held out | Misread | Time | Failures |
|---|---|---|---|---|---|---|---|---|
| 2026-11-12 22:06 | d2d139d | **13/20** | 8/12 | 5/8 | 5/9 | 1 | 41 min | 2× "couldn't create the files" (E-124), 1× answered in chat with no query.sql (E-124), 1× extra column (Spider column strictness), 1× wrong rows, 1× misread (mbpp/432, an edge case its own test missed), 1× 600 s with no answer from the model (E-081) |

Run by the user on an evening machine (not a fresh baseline). 10 tasks had no own tests (all 8 SQL, 2 Python that never
wrote a file).

## Results

### 2026-11-06 · M1 · First `mitra improve` runs (self-improvement step 3, smoke test)
- **Model:** builder qwen3.5:4b at 128K; proposer qwen3.5:4b (the 9B needs ~11 GB free RAM, 7.8 GB was free).
- **Setup:** `mitra improve --proposer qwen3.5:4b --tasks T01 --max-steps 20`, scratch `MITRA_HOME` (the real
  harness untouched). Run records: the Level 01 run (6 tasks, 28 calls); top pattern `tool_error` 4x (reads of paths
  that did not exist yet).
- **Proposal:** rule "Always verify file existence with list_files before attempting to read or edit it."
- **Run 1 (invalid):** current 0/1, proposal 0/1: grading ran in the tool's own Python without fastapi (E-035).
- **Run 2:** current T01 fail (6 steps, 27,357 prompt tokens), proposal T01 fail (8 steps, 28,077) -> **dropped**.
  Both runs passed the visible tests; the hidden test `test_more_than_two_decimals_rejected` failed: the fix removed
  the `try/except` that turns a bad amount into an error response.
- **Reading:** the loop works end to end; one task is far too few to decide anything. The real A/B needs the whole tune
  half (5 tasks) and more run records from real sessions.

### 2026-10-26 · M0 · Prompt overhead of each stock agent
- **Commit:** see PROGRESS_LOG · **Model:** qwen3.5:4b (token counts are Ollama's own, Qwen3.5 tokenizer and template)
- **Setup:** `python bench/run.py --agent bench/configs/<agent>.toml --model qwen3.5:4b --overhead`: each agent gets task
  T01 in a fresh workspace with a clean config folder (no user plugins, skills or MCP servers) and is stopped after its
  first answered call that carries tools (Aider sends none, so its first call). Bench server at 64K (D-016). Raw logs in
  `results/overhead/`.
- **Table:**

| Agent | Version | Prompt tokens, first work call | Tools | Tool definitions (chars) | System prompt (chars) | Notes |
|---|---|---|---|---|---|---|
| Claude Code | 2.1.310 | 12,200 | 14 | 34,458 | 14,622 | |
| deepagents-code | 0.2.1 | 12,230 | 14 | 14,367 | 35,650 | needed `colorama` added to its install to start on Windows |
| OpenCode | 1.17.8 | 11,847 | 9 | 20,325 | 25,893 | sends a title call first: 588 prompt tokens, then 8,866 thinking/output tokens (~2 min) before work starts |
| Codex | 0.162.1 | 4,621 | 8 | 18,784 | 0 | system text sent as a message in the Responses API, so not counted separately |
| Aider | 0.86.2 | 2,714 | 0 | 0 | 1,203 | edits as text blocks, no tools; sets its own `num_ctx` (11,369 here), overriding the server's 64K |

- **What it means:** three of five agents spend ~12K tokens, three times Ollama's 4K default context, before reading
  any code; at the default they would be silently cut (L-001). With clean configs the overhead is lower than the
  20-33K figures reported for setups with plugins and MCP servers, so README and SCOPE now quote our numbers. Prompt
  size alone does not prove these agents fail on small models; the baselines (next) decide that. Mitra's target stays
  ~3K (post 2 is now "~12K to ~3K").

### 2026-10-26 · M0 · Model check on the two picks (D-015)
- **Commit:** see PROGRESS_LOG · **Models:** qwen3.5:4b (Q4_K_M, 3.4 GB), qwen3.5:9b (`qwen3.5:latest`, Q4_K_M, 6.6 GB)
- **Setup:** `bench/model_screen.py`, native `/api/chat` tool calls, 12 cases, num_ctx 32K, temperature 0, seed 0, thinking on
  (Ollama default); bench Ollama server (D-016); RTX 5050 Laptop 8 GB; raw output `results/model_screen.json`
- **Table:**

| Model | Cases passed | Generation tok/s | Prompt tok/s | On GPU at 32K | On GPU at 64K | Failed cases |
|---|---|---|---|---|---|---|
| qwen3.5:4b | 9/12 | 81.4 | 3,143 | 100% | 100% (5.0 GB) | C05 read the test file, not the file in the traceback; C06 searched instead of editing; C07 answered in text instead of calling finish |
| qwen3.5:9b | 11/12 | 19.6 | 1,402 | 76% | 64.5% (8.1 GB) | C12 read payments.py instead of the SDK file the search pointed to |

- **What it means:** both models make native tool calls through Ollama (no calls written as text) and both did the exact
  `str_replace` edit inside an 18K-token prompt. The 9B makes better choices (11 vs 9) but does not fit the 8 GB GPU even
  at 32K, so it generates about 4x slower; at 64K a third of it runs on the CPU. The 4B fits fully at 64K. Both stay in
  the baselines; speed per solved task decides which is the practical default. A first run of this check was wrong:
  C09's prompt was cut by Ollama at 16K context (E-008).

### 2026-11-06 · M2 · Context size vs GPU fit and speed (D-033)

Machine: 8 GB GPU (about 5.4 GB usable by Ollama), 24 GB RAM, about 8 GB RAM free. Ollama native API, `think` off,
model loaded with `num_ctx` set, size read from `/api/ps`; speed = 200 generated tokens, temperature 0.
Scripts: `ctx_probe.py`, `speed_probe.py` (session scratchpad, to be moved to `bench/` with M0).

| Model | num_ctx | Loaded size | On GPU | Generation |
|---|---|---|---|---|
| qwen3.5:4b | 32K | 3.93 GB | 100% | |
| qwen3.5:4b | 64K | 4.99 GB | 100% | 82.5 tok/s |
| qwen3.5:4b | 80K | 6.25 GB | 87% | |
| qwen3.5:4b | 96K | 6.87 GB | 79% | |
| qwen3.5:4b | 112K | 7.68 GB | 71% | |
| qwen3.5:4b | 128K | 8.30 GB | 65% | 24.2 tok/s |
| qwen3.5:4b | 256K | 13.30 GB | 38% | (needs more RAM than is free) |
| qwen3.5 9B (`latest`) | 16K | 6.14 GB | 84% | |
| qwen3.5 9B | 32K | 6.74 GB | 78% | 20.6 tok/s |
| qwen3.5 9B | 48K | 7.43 GB | 70% | |
| qwen3.5 9B | 64K | 8.05 GB | 65% | 13.4 tok/s |
| qwen3.5 9B | 128K | 10.55 GB | 47% | 9.6 tok/s |

**Reading:** the 4B stays fully on the GPU up to 64K; past that it spills and slows about 3.4x. The 9B never fits the
GPU, so its largest context that fits in RAM (128K) costs little extra speed (13.4 to 9.6 tok/s). Chosen: 4B at 64K,
9B at 128K (user, 2026-11-06). Prompt-processing speed at full context is not measured yet.

### 2026-11-07 · M2 · Compressed context memory: flash attention + q8_0 KV cache (D-039)

Same machine and method as above (`ctx_probe.py`, 200 tokens, `think` off), Ollama 0.40.13 with the user-level
settings `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0` (were unset).

| Model | num_ctx | Loaded size | On GPU | Generation |
|---|---|---|---|---|
| qwen3.5:4b | 128K | 6.7 GB (was 8.30) | 87% (was 65%) | 27.0 tok/s (was 24.2) |
| qwen3.5:4b | 256K | 10 GB | 52% | 14.7 tok/s |
| qwen3.5 9B (`latest`) | 128K | 9.5 GB (was 10.55) | 58% (was 47%) | 10.8 tok/s (was 9.6) |
| qwen3.5 9B | 192K | 11 GB | 49% | 8.9 tok/s |
| qwen3.5 9B | 256K | 12 GB | 43% | 8.0 tok/s |

**Reading:** the 9B now loads at its full 256K context (it did not fit in RAM before), at a cost of about 25% speed
against 128K. Free RAM with the 9B loaded at 256K was about 1.1 GB, so other heavy apps should be closed during runs.
The 4B gains GPU share but still spills at 128K, so its speed barely moves. Chosen: 9B at 256K, 4B stays at 128K
(user, 2026-11-07). Answer quality with the q8_0 cache is not measured yet; the next Level 01 run on each model checks it.

### 2026-11-06 · M1 · First playground run: level 01 (snake), Mitra core loop

`python scripts/run_level.py levels/01-snake --builder mitra --model qwen3.5:4b --max-steps 30` (mitra-playground),
commit a5cf5c7 + 97041d3, qwen3.5:4b at 128K, thinking auto, plan run task by task (`mitra solve --plan`).

| Task | Model calls | Tool calls | Result |
|---|---|---|---|
| T1 state | 5 | 6 | passed (4 tests) |
| T2 moves | 6 | 7 | passed (4) |
| T3 food | 4 | 5 | passed (2) |
| T4 game over | 4 | 5 | passed (2) |
| T5 API | 3 | 5 | passed (3) |
| T6 web page | 6 | 9 | passed (2) |

Total 428 s. Visible tests 17/17; visible + hidden 71/72: **not passed**. The miss:
`test_food_never_lands_on_the_snake[0]`: in `step()` the model calls `place_food()` before inserting the new head,
so the new food can be placed on the cell the head is moving into (1 of 40 seeds). No fresh rounds, rollbacks,
text tool calls or model errors were needed. Result file: mitra-playground `results/01-snake/20261106-1950-*.json`.

## Result template

```markdown
### <date> · <milestone> · <what was measured>
- **Commit:** <sha> · **Models:** ... · **Agents:** ... · **Runs:** N
- **Table:** ...
- **What it means:** one paragraph, including what did not work.
- **Kept / dropped:** for experiments.
```

## 2026-11-08 Model screen for the roles (D-051): first attempt void
- **Run:** `bench/model_screen.py --models deepseek-r1:8b qwen3.5:latest --ollama :11434` (12 tool-call cases).
- **Result: void, not a model result.** Ollama was updated mid-run (0.40.13 → 0.40.15, needed by mimo-v2.6:9b), so
  cases from deepseek C04 and all of qwen3.5:latest failed with "connection refused" (marked infra by the screen).
- **Signal to check:** before the update, deepseek-r1:8b's C01-C03 each hit the 600 s limit (thinking by default, no
  think setting sent; a stuck "Stopping…" 9B may have held memory). The screen now takes `--think on|off` so each
  model is tested the way its role runs it; re-run started on a fresh Ollama (builders: qwen3.5:latest, mimo-v2.6:9b;
  planner: deepseek-r1:8b with thinking on).

