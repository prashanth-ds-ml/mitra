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

(none yet)

## Result template

```markdown
### <date> · <milestone> · <what was measured>
- **Commit:** <sha> · **Models:** ... · **Agents:** ... · **Runs:** N
- **Table:** ...
- **What it means:** one paragraph, including what did not work.
- **Kept / dropped:** for experiments.
```
