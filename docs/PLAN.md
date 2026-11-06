# Plan: checklist

Tick items as they are done (`[x]`) with the date, e.g. `[x] ... (2026-10-28)`. Scope and reasons are in
[SCOPE.md](SCOPE.md); decisions in [DECISIONS.md](DECISIONS.md). No dates or weeks: the next unticked item is the work.
Every milestone ends with the "Every release" list at the bottom (public release + LinkedIn post).
Plan v2 (2026-11-05, D-017); v1 is in [archive/PLAN-v1-2026-10-24.md](archive/PLAN-v1-2026-10-24.md).

**Rule for new ideas (D-011):** a new idea goes into "Ideas to test" in SCOPE.md, never straight into this plan.

**Progress:** Before starting 4/4 · M0-M7 0/8

---

## Before starting
- [x] Name decided: Mitra (D-006) (2026-10-24)
- [x] Repo decided: new repo `prashanth-ds-ml/mitra`, local folder `portfolio/05-mitra` (D-007) (2026-10-24)
- [x] GPU, VRAM and power cap written in STATUS.md (2026-10-24)
- [x] "Go on M0" given (2026-10-24)

---

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
- [ ] **Kill check 1:** if stock agents already pass most tasks, the best one becomes the builder (SCOPE kill rule)
- [ ] Release v0.0 + post: "Why coding agents break on your laptop" (prompt-overhead chart)

## M1 Core agent loop + `mitra solve` (one task, built for small models)
The same loop runs the terminal assistant (M2), the plan runner (M3) and the benchmark.
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
- [ ] Model settings in config: context length, KV-cache type (`q8_0` option on the bench server), thinking on/off and thinking budget (D-020)
- [ ] Fresh round after a failed test run, with a short handoff note (status, evidence, next step) (dsh `tool-ralph`)
- [ ] Rollback when rounds run out
- [ ] Every run saved with authorship per part (Mitra / Claude / me) and secrets scrubbed, so it can become training data later (D-022)
- [ ] Record/replay: recorded model replies replay in tests without Ollama (I-1, dsh `llm-replay`)
- [ ] Fault tests: a scripted fake model returns malformed tool calls, empty replies, stalls and errors; harness must recover or fail cleanly (dsh `llm-mock-server`)
- [ ] Unit tests for every part above
- [ ] Release v0.1 + post: "Cutting the agent prompt from ~12K to ~3K tokens"

## M2 Terminal assistant (`mitra`)
- [x] Code renamed CodeMitra -> Mitra (files, config, `.mitra/`, banner); 615 tests pass (2026-11-05)
Design, ability list and what happens to local-codex's code: [M2_PLAN.md](M2_PLAN.md).
- [x] MCP SDK choice: official `mcp` 2.3.0, tested on Windows against a stdio server (D-030, F-008) (2026-11-05)
- [x] Commands outside the v1 list removed (60 -> 20 commands, `/reset` -> `/clear`, `/thinking` -> `/think`, `! <cmd>` for shell, unknown commands answered locally); unused modules removed; `main.py` 6,077 -> 4,567 lines (2026-11-05)
- [ ] `main.py` split into a REPL shell + `app/commands/`; tests for every kept command
- [ ] Chat on the M1 loop: explain with `file:line`, find, edit, run, fix loop
- [ ] Modes: ask each time / auto-edit / plan only (read-only); diff approval screen
- [ ] `/undo` (last change, whole session), `/diff`, `/commit` (drafted message, you approve, never pushes)
- [ ] Session saved per project, `/resume`, fresh round with a handoff note when context fills
- [x] Terminal interface part 1 (D-031, 2026-11-06): `app/ui/` with the Phosphor theme, live streamed answers (markdown per finished block), a thinking line with timer and token count, one line per tool step (no panels), status line (model, mode, ctx %, tokens, folder, branch; warns at 80%), turn footer
- [x] Startup screen (D-031, 2026-11-06): one-line title instead of the big banner, compact model picker, header box (model, context, GPU, folder, MCP servers) + tips
- [x] Inline arrow-key approval menu with coloured diff; command replies without boxes; startup straight to the header (D-034) (2026-11-06)
- [ ] Terminal interface part 2: `/` menu with descriptions, `@` files, saved history, shift+tab modes, esc to stop
- [ ] `/model`, `/context`, `/think`; prompt tokens and context use in the status line, warning before the limit
- [ ] Project notes (AGENTS.md / CLAUDE.md) within the byte budget; skills loaded on demand (FastAPI, LangGraph, Next.js, uv on Windows)
- [x] Model picker and `/model list` show only compatible models: chat + native tool calling, >= 1.5B parameters, >= 32K context; `mitra models --all` shows the rest and why (2026-11-05)
- [ ] `/doctor`: free RAM, GPU/VRAM, Ollama up, model loaded, context really applied (first version 2026-11-05: resources + permissions + MCP)
- [x] MCP client (D-028): stdio + Streamable HTTP, standard `mcpServers` config (`.mitra/mcp.json`), `/mcp` list / on / off / test / import (from Claude Code) / trust / call (2026-11-05)
- [x] MCP safety: read tools free, every write tool asks (even in auto-edit), refused when no one can approve, secrets masked in results and logs, every call logged and timed, big results trimmed (2026-11-05)
- [ ] Day-one servers started and tested on Windows with real packages: git, GitHub, Context7, filesystem, Semgrep (configured as defaults 2026-11-05; first real start needs the user's OK to download them); versions pinned after
- [ ] local-codex parts not in the v1 list archived (git history), per M2_PLAN.md
- [ ] Fresh-clone install on Windows; Linux CI blocking
- [ ] Used for a week on small real tasks in my projects; problems logged in ERROR_LOG and fixed
- [ ] Release v0.2 + post: "A coding assistant that actually works on a 4B model"

## M3 Local planning + unattended runner
- [ ] Plan format (one Markdown file): feature, design notes, tasks with files, expected behaviour, test command, order
- [ ] `/plan`: Mitra writes a plan in that format with the local 9B (thinking on); I can edit it before running (D-025)
- [ ] Plan check: every task has a test command and files; a plan that fails the check is rewritten before running
- [ ] `mitra run plan.md` (also `/run` inside the terminal app): works through tasks on a feature branch, one commit per task, never touches `main`
- [ ] Stuck task (rounds used up) → "needs help" brief (failing output, `file:line`, what was tried); runner moves on; tasks that depend on it are skipped
- [ ] RAM guard: pauses when free RAM drops below the preflight rule, resumes when it recovers
- [ ] Stop and resume: a killed run picks up at the next unfinished task
- [ ] Report when done: tasks done / needs help, diffs, time, local tokens
- [ ] Tested on playground levels 1-2 (snake, second game) and one small real feature in one of my projects
- [ ] Release v0.3 + post: "My laptop built a feature while I was at work"

## M4 Comparison: settings, MCP, Harness²
- [ ] Benchmark grown to ~20 single tasks + feature tasks from the `mitra-playground` ladder (levels 1-6) and my projects + a small public-benchmark slice
- [ ] `mitra bench` reruns everything; results JSON committed
- [ ] Settings sweep on the tuning half: context 32K / 64K / 128K, thinking off / on; best setting per model kept, reported on held-out
- [ ] Tool registry (`find_tool`) over every connected MCP server: short descriptions of our own, only the 1-2 tools a step needs go into the prompt
- [ ] More servers through the registry: Serena, GitHub (test repo, scoped token), SQLite/Postgres (read-only SQL by default), Docker, AWS (LocalStack, or a read-only IAM profile)
- [ ] Research Desk MCP server added to project 04: `search_library`, `get_report` (read-only)
- [ ] Ops sandbox = playground level 07: Docker Compose (demo API, seeded Postgres, LocalStack), test GitHub repo, planted problems with checkable answers
- [ ] MCP comparison on the same model and tasks: all tools in the prompt vs registry vs core only (pass rate, right-tool rate, prompt tokens, time, blocked unsafe calls)
- [ ] Harness² tuning in WSL (Codex executor pointed at local Ollama) on the tuning half; three columns: stock, stock + Harness², Mitra
- [ ] Failure analysis from trajectories: every failed run labelled (broken tool call, wrong file, gave up, loop, timeout, test tampering, infra); counts in EVALS.md
- [ ] EVALS.md: method, every config, every result
- [ ] **Kill check 2:** if Mitra does not clearly beat stock agents, the best stock agent becomes the builder engine behind Mitra's terminal app
- [ ] Release v0.4 + posts: the comparison table; "One laptop, a 9B model, 6 real MCP servers: an incident solved end to end"

## M5 Review + lessons loop
- [ ] Review view in the terminal app: report + diffs per run; I accept, reject with a comment, or split a "needs help" task
- [ ] Fallback: a "needs help" brief I can paste into Claude Code; its tokens are counted
- [ ] Review comments and failure labels turned into lesson proposals for Mitra's skills file
- [ ] A lesson is kept only if more tuning tasks pass; reported on held-out; I see each one
- [ ] Lessons file capped at ~1K tokens; lessons that stop helping are dropped
- [ ] Meter: share of tasks and features done fully locally; Claude tokens spent on fallbacks (from Claude Code session logs)
- [ ] Release v0.5 + post: "How far up the ladder a 9B model climbs on its own"

## M6 Daily use + v1.0
- [ ] Used on my own projects for real features; every run saved to the training log
- [ ] Weekly numbers in PROGRESS_LOG: tasks done locally, needs help, Claude fallback tokens, lessons kept, highest ladder level passed
- [ ] README rebuilt around the results; quick start tested from a fresh clone
- [ ] 2-minute demo video
- [ ] CASE_STUDY.md (one page) + PROGRESS_LOG.md complete
- [ ] Article (LinkedIn / blog): method, results, honest limits
- [ ] Release v1.0 + post: the article

## M7 Personal fine-tune (only with enough data)
- [ ] Dataset builder: Mitra-only passing runs (authorship filter), secret scrub, dedupe, train / held-out split by project and date
- [ ] Licensed public coding data mixed in (licence of each source written in EVALS.md)
- [ ] Gate: a few hundred passing runs before the first training run
- [ ] QLoRA fine-tune of the small model locally (e.g. Unsloth); 9B only if a short rented GPU is needed
- [ ] Compare on held-out: base + lessons vs fine-tuned + lessons; keep the fine-tune only if it wins
- [ ] Release + post

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
