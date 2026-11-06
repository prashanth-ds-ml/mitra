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

## Results

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
