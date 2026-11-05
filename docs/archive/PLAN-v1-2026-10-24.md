# Plan: checklist

Tick items as they are done (`[x]`) with the date, e.g. `[x] ... (2026-10-28)`. Scope and reasons are in
[SCOPE.md](SCOPE.md); decisions in [DECISIONS.md](DECISIONS.md). No dates or weeks: the next unticked item is the work.
Every milestone ends with the "Every release" list at the bottom (public release + LinkedIn post).

**Rule for new ideas (D-011):** a new idea goes into "Ideas to test" in SCOPE.md, never straight into this plan. It
becomes a milestone only after its impact score is agreed.

**Progress:** Before starting 4/4 · Phase 1 0/5 · Phase 2 0/4 · Phase 3 0/3

---

## Before starting
- [x] Name decided: Mitra (D-006) (2026-10-24)
- [x] Repo decided: new repo `prashanth-ds-ml/mitra`, local folder `portfolio/05-mitra` (D-007) (2026-10-24)
- [x] GPU, VRAM and power cap written in STATUS.md (2026-10-24)
- [x] "Go on M0" given (2026-10-24)

---

# Phase 1: core portfolio project
The one question: how much everyday coding work can a small local model do with an agent built for it, and does
test-gated escalation to a frontier model cut cost without hurting the success rate?

## M0 Repo + measure the problem
- [x] Public repo created under prashanth-ds-ml, MIT licence, local-codex code imported with credit (2026-10-24)
- [x] local-codex test suite runs green in the root `.venv` (`uv pip`): 561 passed (2026-10-24)
- [x] README v0: pitch, "building in public", link to this checklist, empty results table (2026-10-24)
- [x] CI on every push (tests + lint), secret scan, `.gitignore` checked; Windows blocking, Linux informational until E-005 (2026-10-24)
- [x] GitHub milestones M0-M8 and tracking issues (checklist stays in this file) (2026-10-24)
- [x] Demo service built: small FastAPI app on a fake payments SDK (paise ints, Result type, cursors, idempotency keys, rate limits, a deprecated method) (2026-10-24)
- [x] Benchmark v0: 10 tasks (7 bugs, 3 features), visible and hidden tests, test files hashed (2026-10-24)
- [x] Reference solutions pass every task; the unsolved repo fails every task (`bench.py validate`, 17 harness tests) (2026-10-24)
- [x] Benchmark split into a tuning half and a held-out half, fixed before any tuning (I-2, Harness²): 5 + 5, no shared fix across halves (2026-10-24)
- [x] Bench preflight: Ollama up, model pulled, context length set, free RAM/GPU checked; refuses to run otherwise (Harness² `preflight`) (`bench/preflight.py`, 2026-10-24)
- [x] Run records: each run saves its trajectory (JSONL), result and a config fingerprint (agent version, model tag, prompt hash); a run counts only when the runner marks it complete; reruns skip completed runs (Harness² `runmark`) (`bench/run.py` + `bench/proxy.py`, 2026-10-24)
- [x] Infra failures (dead Ollama, auth, crash, wall timeout) recorded separately from agent failures, never scored as a zero (2026-10-24)
- [x] Models picked from published tool-calling benchmarks: qwen3.5:4b and qwen3.5:9b (D-015, 2026-10-26)
- [x] Model check on the two picks: native tool calls via Ollama, speed, GPU fit at 32K/64K (`bench/model_screen.py`): 4B 9/12, 81 tok/s, fits; 9B 11/12, 20 tok/s, 64% on GPU at 64K (EVALS, 2026-10-26)
- [x] Prompt overhead measured for each stock agent (Claude Code, Codex, OpenCode, Aider, deepagents-code): 2.7K-12.2K tokens on the first work call (`run.py --overhead`, EVALS, 2026-10-26)
- [x] Ollama context set correctly for each (`OLLAMA_CONTEXT_LENGTH`); configs saved in `bench/configs/`: bench server at 64K (D-016), preflight checks the loaded context; Aider sets its own `num_ctx` (stock behaviour, kept) (2026-10-26)
- [ ] Baseline runs: stock agents × qwen3.5:4b and qwen3.5:9b on benchmark v0; raw results in `results/`
- [ ] **Kill check 1:** if stock agents already pass most tasks, write that up and stop
- [ ] Release v0.0 + post: "Why coding agents break on your laptop" (prompt-overhead chart)

## M1 `mitra solve`: harness built for small models
- [ ] Built on LangGraph (already in local-codex); LangChain / Deep Agents middleware used only where it fits the prompt budget, with our own short prompts
- [ ] Headless command `mitra solve "task" --test "pytest ..." --json` (exit 0/1)
- [ ] Prompt + tool descriptions under ~3K tokens, checked in CI
- [ ] Procedure vs knowledge split: system prompt says only how to work; SDK quirks and project facts are skills loaded on demand (I-3, Harness² INV/DOM)
- [ ] AGENTS.md loaded with a byte budget; most specific file kept, broader files dropped first (dsh `agent-instructions`)
- [ ] `docs/MODEL_VIEW.md`: for every feature, the exact text the model sees and its token cost (dsh "Model Experience" convention)
- [ ] 5 tools: read, search, `str_replace` (forgiving match), run_tests, finish
- [ ] Read before edit, and reject an edit if the file changed since it was read; the error tells the model to re-read (dsh `fs-observation-policy`)
- [ ] Tolerant tool-call parsing (native or JSON in text) + one retry with the error message
- [ ] Model-call retry on transport errors (bounded, logged); empty reply = error (dsh `llm-retry`, L-002)
- [ ] Step limit and repeat-call guard with a reminder at 3 repeats, stop at the limit (dsh `repeat-tool-reminder`; fixes E-002)
- [ ] Fix E-001: `edit_file` added to mutating tools; test covers every tool in the set
- [ ] Fix E-003: commands and edits confined to the task workspace; path checks fail closed
- [ ] Fix E-005: paths via `pathlib` and stored relative with `/`; no PowerShell assumptions; Linux CI job blocking again
- [ ] Tests run in a temp copy with a timeout; full output saved to a file, model sees head/tail + the path (dsh `spill-policy`)
- [ ] Stable prompt prefix, append-only history inside a round, so Ollama reuses its prompt cache; prompt-eval time logged (dsh "KV cache effect")
- [ ] Prompt tokens and context use logged on every call; warning before the context limit (L-001)
- [ ] Fresh round after a failed test run, with a short handoff note (status, evidence, next step) (dsh `tool-ralph`)
- [ ] Rollback when rounds run out
- [ ] Record/replay: recorded model replies replay in tests without Ollama (I-1, dsh `llm-replay`)
- [ ] Fault tests: a scripted fake model returns malformed tool calls, empty replies, stalls and errors; harness must recover or fail cleanly (dsh `llm-mock-server`)
- [ ] Unit tests for every part above
- [ ] Release v0.1 + post: "Cutting the agent prompt from ~12K to ~3K tokens"

## M2 Same-model comparison
- [ ] Benchmark grown to ~20 tasks + a small public-benchmark slice
- [ ] `mitra bench` reruns everything; results JSON committed
- [ ] Table per agent × model: pass rate, prompt overhead, broken tool calls, turns, time
- [ ] Per-model instructions tuned on the tuning half only (Harness² lite, by hand: change one thing, keep it only if more tuning tasks pass); reported on the held-out half (I-2)
- [ ] Failure analysis from trajectories: every failed run labelled (broken tool call, wrong file, gave up, loop, timeout, test tampering, infra); counts in EVALS.md
- [ ] EVALS.md: method, every config, every result
- [ ] **Kill check 2:** if Mitra does not clearly beat stock agents, publish findings and stop
- [ ] Release v0.2 + post: the comparison table

## M3 Test-gated escalation + cost meter
- [ ] Local fails the tests after N rounds → frontier model gets the handoff note + failing output (not the whole chat)
- [ ] Frontier model choice and API key via config; works with no key (local only)
- [ ] Meter per task: local tokens, frontier tokens, ₹, GPU Wh (`nvidia-smi`), wall time
- [ ] Experiment on the same tasks: frontier only vs local first + escalation (pass rate, ₹, Wh, time)
- [ ] Release v0.3 + post: "% solved on my GPU, and what the cloud cost for the rest"

## M4 Ship v1.0 (portfolio version)
- [ ] README rebuilt around the results; quick start tested from a fresh clone
- [ ] 2-minute demo video
- [ ] CASE_STUDY.md (one page) + PROGRESS_LOG.md complete
- [ ] Article (LinkedIn / blog): method, results, honest limits
- [ ] Portfolio updated: ROADMAP.md, GitHub pin, LinkedIn Featured
- [ ] Release v1.0 + post: the article

---

# Phase 2: extensions, by impact score (only if phase 1 numbers are good)

## M5 Bigtool ops pack (former slot 02)
- [ ] Tool registry with `find_tool(query)` (BM25 first; local embeddings only if BM25 misses)
- [ ] Ops pack: ~200 fake internal APIs (billing, inventory, ticketing) + task set with checks
- [ ] Experiment: all tools in prompt vs retrieval vs core only (pass rate, prompt tokens, wrong-tool calls, retrieval hit rate)
- [ ] MCP servers connected through the registry
- [ ] Release + post

## M6 Data pack
- [ ] Analysis tasks: the model writes a plan or code, the engine computes
- [ ] Verifier recomputes every number (shared idea with Aryabhatta 07)
- [ ] Benchmark of analysis questions with known answers; local vs escalation numbers
- [ ] Release + post

## M7 MCP server mode
- [ ] Mitra exposed as an MCP server (`mitra_solve`, later the data pack)
- [ ] Claude Code / Codex hand routine tasks to the local model; frontier tokens saved measured
- [ ] Release + post

## M8 Experiments (each kept only if the numbers support it)
- [ ] E1 Debug brief: code-only evidence (stack trace, logs, diffs, `git bisect`) + local investigators → brief; frontier fixes from bug report only vs brief; compare fix rate, tokens, ₹, time
- [ ] E2 Learning from escalations: lesson/skill proposed when frontier fixes what local could not; kept only if held-out tasks improve; you review each one; chart of escalation rate over time
- [ ] Each experiment: result written in EVALS.md (kept or dropped) + post

## Later (built only if users ask; not milestones)
- [ ] Escalation ladder (tiny local → stronger local → cheap cloud → frontier → ask you) + monthly ₹ budget
- [ ] `mitra doctor`: GPU/RAM check, model and context picks, Ollama 4K-default warning
- [ ] "What could have been local?" usage audit
- [ ] Review brief (crowded space: CodeRabbit, BugBot)
- [ ] Docs/PDF pack with checked citations (Open WebUI already covers plain PDF chat)

---

# Phase 3: Vipplav offer
- [ ] Conversations with 5-10 engineering leads / SME owners (start during phase 2)
- [ ] Offer chosen from: AI cost and privacy audit · local AI box for a team · "make your agent reliable on your data"
- [ ] 3 teams agree to a paid pilot (until then it stays a portfolio project)

---

## Every release (copy into the release issue)
- [ ] All automatable tests run and pass; fresh clone works
- [ ] Secret scan clean, versions pinned, no personal paths
- [ ] README results table matches `results/`
- [ ] CHANGELOG.md, git tag, GitHub release notes
- [ ] PROGRESS_LOG.md row, STATUS.md updated, this checklist ticked
- [ ] Release check shown to you before publishing
- [ ] LinkedIn post: hook number → what I tried → what happened (incl. failures) → one lesson → link + what's next; one image, ~200 words, no hype words

## Repo rules
- Public from M0; README top says "building in public" and links this checklist
- Every number reproducible with one command; every agent config published
- `good first issue` label for benchmark tasks
- Docs: STATUS, PROGRESS_LOG, DECISIONS, EVALS, CASE_STUDY, USER_TESTS (same pattern as Research Desk)
