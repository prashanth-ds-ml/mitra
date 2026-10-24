# Evals

Method and every result, whatever it shows. Raw results live in `results/` and are rerun with one command
(`mitra bench`, from M2). Each result section names the git commit, models, agent configs and machine state.

## Method (filled in at M0)
- **Benchmark:** tasks, how they are made, visible vs hidden tests, how test files are protected
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
