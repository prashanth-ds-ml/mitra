# Scope: Mitra

**v2 agreed:** 2026-11-05 (goal reframed, D-017) · **v1:** 2026-10-24, kept in [archive/SCOPE-v1-2026-10-24.md](archive/SCOPE-v1-2026-10-24.md) ·
**Starting code:** [prashanth-ds-ml/local-codex](https://github.com/prashanth-ds-ml/local-codex)

## The goal
A proper coding assistant for my own projects that runs on my local models: I chat with it in the terminal and it reads,
edits and tests code (like Claude Code, but built for small models). Mitra's thinking, planning and building all run on
local models (D-025); for bigger features it writes its own plan and builds it unattended on my GPU while I do other
work. Claude Code is only the fallback when Mitra is stuck. The aim is to build more and more complex features locally
and spend far fewer Claude subscription tokens. Practice and test projects live in a separate repo, `mitra-playground`
(D-027).
Later, Mitra's own work becomes the data for a personal coding model fine-tuned to what I build.

## Why a new agent
Today's coding agents (Claude Code, Codex, OpenCode, Aider, Deep Agents) connect to Ollama, but they are built for
frontier models: a large fixed prompt (measured 2026-10-26 with clean configs: 2.7K-12.2K tokens; reports with user
plugins and MCP servers cite 20-33K), many tools, strict tool-call formats and no retry on a malformed call. On a small
model on a laptop GPU they break. Small models also struggle to design a complex system, so Mitra plans in small tested
steps, uses the 9B with thinking on for planning, and climbs a difficulty ladder of practice projects to find (and push)
its limit.

## The questions
1. Given a feature split into small tested tasks, how many does a local model finish unattended?
2. How far up the playground ladder (snake game -> portfolio site -> API + database -> AI app -> full system) can Mitra
   go with local models only, and what share of my real tasks can I hand it?
3. Does Mitra get better with use (lessons, Harness² tuning, later a fine-tune)?

The answers are published either way.

## How it works
**Everyday work:** run `mitra` in a project and ask in plain words ("add a test for X", "why does Y fail?"). It finds
the code, shows each diff, asks before edits and commands, and runs the tests.

**Bigger features:**
1. **Plan (Mitra, local 9B with thinking).** I describe a feature. Mitra writes a plan: design, then small tasks, each with the files,
   the expected behaviour and the test that proves it is done.
2. **Build (Mitra, unattended).** Mitra works through the tasks on a feature branch, one commit per task. It uses its own
   tools plus MCP tools (Serena for code navigation, Context7 for library docs). A task is done only when its test passes.
3. **Stuck → needs help.** A task that keeps failing gets a short brief (failing output, `file:line`, what was tried) and
   Mitra moves on.
4. **Report.** When I come back: done, failed, diffs, time.
5. **Review (me; Claude Code only as fallback).** I check the diffs; stuck tasks I split for Mitra or hand to
   Claude Code.
6. **Lessons.** Review comments and failure analysis become lessons in Mitra's skills file, kept only if they make more tuning tasks pass.
7. **Data.** Every run is saved with who wrote each part, for the fine-tune later.

## In scope
| Part | What it is |
|---|---|
| Benchmark | Single tasks (planted bugs, small features) on the demo service + a public-benchmark slice, and **feature tasks** (a plan + tests) from the demo service and my own projects; visible and hidden tests; tuning and held-out halves |
| Baselines | Stock agents on the same model, context and machine (M0) |
| `mitra solve` | One task: prompt + tools under ~3K tokens, 5 built-in tools, tolerant tool-call parsing, fresh rounds, rollback |
| Terminal assistant | `mitra`: chat in the terminal, diffs shown and approved, slash commands, resumable sessions; reuses local-codex's terminal app (D-023) |
| Plan + runner | Plan format Mitra writes (`/plan`, local); `mitra run` works through it unattended on a branch, with a RAM guard and a report |
| MCP tools | Serena and Context7, loaded through a tool registry (only the tool needed goes into the prompt) |
| Model settings | Context 32K / 64K / 128K (with Ollama KV-cache `q8_0`), thinking off / on with a budget; picked by measurement |
| Harness² tuning | Per-model prompt and skill tuning on the tuning half, reported on the held-out half |
| Review + lessons | Batch review by me (Claude Code only as fallback); lessons capped at ~1K tokens, kept only if they help |
| Meter | Share of tasks and features done fully locally, Claude tokens spent on fallbacks, local tokens, wall time; GPU Wh as a side note |
| Playground | Separate repo `mitra-playground`: a ladder of practice projects, each with a plan and tests; AI apps there may call OpenRouter / NVIDIA APIs at runtime (D-026, D-027) |
| Training log + fine-tune | Mitra-only passing runs + licensed public data → QLoRA fine-tune of the small model, kept only if it wins on held-out tasks |

## Training data rules (D-022)
- Only Mitra's own passing code and steps, plus public coding data with a clear licence. **No Claude fixes or responses.**
- A task description written by Claude is kept as the input only; the model trains on Mitra's code and steps.
- Every run records who wrote each part (Mitra, Claude, me). A task Claude fixed is left out.
- OpenRouter / NVIDIA model outputs (from the playground apps) are not training data.
- `.env` files, keys and personal data are scrubbed before anything is saved for training.
- Fine-tune only after a few hundred passing runs, and keep it only if it beats base model + lessons on held-out tasks.

## Kill rule
- M0: if stock agents already pass most tasks on the small model, the best one becomes the engine behind Mitra's
  terminal app, plan runner, review and lessons.
- M4: if Mitra's loop does not clearly beat stock agents, same.

## Ideas to test (D-011)
New ideas land here first, with a one-line impact guess. They move into PLAN.md only after we agree.
- **I-4 deepseek-harness as a baseline agent** (custom OpenAI-compatible routes). Impact: one more data point; developer
  preview, setup may cost time.
- **I-5 Bigger mixture-of-experts model overnight** (partly on CPU, 8 GB GPU + 24 GB RAM). Impact: may handle harder
  tasks; slow and RAM-tight. Test after the baselines.

## Later (not milestones)
Bigtool ops pack (~200 fake APIs), data pack, Mitra as an MCP server, debug-brief experiment, escalation ladder,
`mitra doctor`, usage audit.

## Out of scope
Client or company offer (for now), web chat UI, IDE plugin (maybe after v1.0), API key for a frontier model inside Mitra, PDF app, email writing, project scaffolding, web agent.

## Honest limits
- Small models are weak at designing complex systems; local planning is the riskiest part. Expect about half the
  planned tasks done at first, and lower rungs of the ladder before higher ones.
- Long context helps small models less than it seems (they lose the middle); thinking costs time (8K thinking tokens
  ≈ 1.5 min per step on the 4B, ≈ 7 min on the 9B).
- RAM: the 9B realistically runs only when the laptop is idle (overnight).
- Projects with few tests get less out of Mitra: the test is the safety net.
- A fine-tune may not beat base model + good harness; the held-out test decides.
- Our own benchmark will be questioned: publish every config and include a public-benchmark slice.

## Where ideas come from
| Source | What we take |
|---|---|
| local-codex | Fix-loop shape, safe `execute()`, change sets with before/after, `.env` blocking |
| deepseek-harness (used) | `str_replace` editor; read-before-edit with stale-file check; repeat-tool reminder; bounded model retry; fresh rounds with a bounded handoff (`tool-ralph`); spill full output to a file + head/tail; AGENTS.md byte budget; stable prefix for KV-cache reuse; "what the model sees" docs per feature; record/replay and fault-injection test servers |
| deepseek-harness (skipped) | Plan mode (needs a human each time), auto-review (experimental, costs tokens), summarizing compaction (an extra model call; fresh rounds do the job), agent teams, worktrees (a temp copy is enough), Windows ACL sandbox (reference for E-003 only) |
| Harness² (used) | Tuning / held-out split; one-change-at-a-time tuning kept only if more tasks pass; procedure vs knowledge split (INV/DOM); preflight before runs; run completion marker + config fingerprint; infra failures kept apart from agent failures; trajectories saved for failure analysis; tuning loop run in WSL in M4 (Codex executor pointed at local Ollama) |
| Harness² (skipped) | Blind selector (our tests decide), full budget ledger (overkill at our scale) |
| Serena, Context7 (MCP) | Code navigation by symbol and up-to-date library docs, so the small model reads less and guesses less |
| Uber Debug Assist | Collect evidence with code before the first model call (the "needs help" brief) |
| LangChain Deep Agents | Filesystem offload, summarization and subagent middleware, with our own short prompts |
| langgraph-bigtool | Tool registry: retrieve the tool, don't list them all |
