# Scope: Mitra

**Agreed:** 2026-10-24 (planning only, no code yet) · **Starting code:** [prashanth-ds-ml/local-codex](https://github.com/prashanth-ds-ml/local-codex)

## The thesis
Most everyday AI work can run on the machine you already own. Use a frontier model only when a check proves the local
answer was not good enough.

Today's coding agents (Claude Code, Codex, OpenCode, Aider, Deep Agents) connect to Ollama, but they are built for
frontier models: 20-33K tokens of fixed prompt, many tools, strict tool-call formats and no retry on a malformed call.
On a small model on a laptop GPU they break. Nobody has published a controlled test that keeps a small model fixed and
changes only the agent. This project runs that test and builds the agent that wins it.

## The one question v0.x answers
> On an 8 GB consumer GPU, how much everyday coding work can a small model do when the agent is built for it, and does
> test-gated escalation to a frontier model cut cost without hurting the success rate?

The answer is published either way. A clear "no" with good method is still a result.

## In scope for v0.x (about 4 weeks)
| Part | What it is |
|---|---|
| Benchmark | ~20 planted-bug and small-feature tasks on a demo service + a small slice of a public benchmark; visible and hidden tests |
| Baselines | Stock Claude Code (via Ollama), Codex `--oss`, Aider, `deepagents-cli` on the same model, same context, same machine |
| Harness (`mitra solve`) | Prompt + tools under ~3K tokens; 5 tools (read, search, `str_replace`, run_tests, finish); tolerant tool-call parsing with one retry; step limit; fresh round with a short handoff report after a failed test run; rollback when it gives up |
| Escalation (one rung) | Local fails the tests after N rounds → frontier model gets the handoff report, not the whole chat |
| Meter | Tokens, ₹ and GPU Wh (`nvidia-smi`) per task |
| Write-up | README results table, demo video, CASE_STUDY.md, one article |

Five headline numbers: % of tasks solved locally, pass rate vs stock agents on the same model, prompt overhead,
frontier ₹ saved, Wh per solved task.

## Idea to test: local brief for frontier models (D-008, not core)
Local review and debug agents do the reading and digging (run tests, grep, `git bisect`, parse logs, rank suspects) and
write a short brief: verbatim failing output, `file:line` references, raw excerpts and hypotheses with confidence. The
frontier model gets the brief instead of exploring the repo itself, and may still read files when the brief is not
enough. The same brief is the escalation handoff. Measured, not assumed: frontier tokens, ₹, fix rate and time, with and
without the brief.

## Kill rule (decided before building)
At M0: if stock agents already pass most tasks on the small model, or at M2 Mitra does not beat them clearly,
stop building features and publish "what I found".

## Core vs the rest (impact scoring, 2026-10-24)
Core = high impact for the portfolio now and for Vipplav later, and part of phase 1.

| Candidate | Portfolio | Vipplav | Place |
|---|---|---|---|
| Harness built for small models (`solve`) | High | Medium | **Core** (M1) |
| Same-model comparison vs stock agents | Very high | Medium | **Core** (M2) |
| Test-gated escalation + ₹/Wh meter | High | High | **Core** (M3) |
| Bigtool ops pack (200 APIs) | High (FDE) | High | Phase 2, M5 |
| Data pack (recompute check) | Medium | High | Phase 2, M6 |
| MCP server mode | Medium | High | Phase 2, M7 |
| Debug brief | Medium-high | Medium | Experiment E1 (M8) |
| Learning from escalations | High if it works | High if it works | Experiment E2 (M8) |
| Escalation ladder / budget / doctor | Low-medium | Medium | Later |
| Usage audit | Medium | Medium | Later |
| Review brief | Low (crowded) | Low | Later / maybe never |
| Docs/PDF pack | Low (Open WebUI) | Low | Later / maybe never |

## Ideas to test (D-011)
New ideas land here first, with a one-line impact guess. They move into PLAN.md only after the impact score is agreed.
- ~~I-1 Record/replay~~, ~~I-2 Tuning / held-out split~~, ~~I-3 Procedure vs knowledge split~~: moved into PLAN.md (M1, M0+M2, M1) on 2026-10-24 (D-013).
- **I-4 deepseek-harness as a baseline agent** in the comparison (it supports custom OpenAI-compatible routes).
  Impact: one more data point; it is a developer preview, so setup may cost time.

## Out of scope
Chat UI, IDE plugin, our own PDF app, email writing (local models already do it fine), project scaffolding, web agent.

## Honest limits (from the senior review, 2026-10-24)
- Small models solve far fewer real-repo tasks than frontier ones; expect "20-40% locally", not "most".
- Local is slower; for paid professionals time can cost more than tokens.
- Cheap cloud models keep getting cheaper, so ₹ saved may be small. The lasting arguments are privacy, offline use
  and data residency. Energy is measured, never claimed.
- Answer checking is strong only where tests or recomputation exist.
- Our own benchmark will be questioned: publish every config and include a public-benchmark slice.

## Where ideas come from
| Source | What we take |
|---|---|
| local-codex | Fix-loop shape, safe `execute()`, change sets with before/after, `.env` blocking |
| deepseek-harness (used) | `str_replace` editor; read-before-edit with stale-file check; repeat-tool reminder; bounded model retry; fresh rounds with a bounded handoff (`tool-ralph`); spill full output to a file + head/tail; AGENTS.md byte budget; stable prefix for KV-cache reuse; "what the model sees" docs per feature; record/replay and fault-injection test servers |
| deepseek-harness (skipped) | Plan mode (needs a human each time), auto-review (experimental, costs tokens), summarizing compaction (an extra model call; fresh rounds do the job), agent teams, worktrees (a temp copy is enough), Windows ACL sandbox (reference for E-003 only) |
| Harness² (used) | Tuning / held-out split; one-change-at-a-time tuning kept only if more tasks pass; procedure vs knowledge split (INV/DOM); preflight before runs; run completion marker + config fingerprint; infra failures kept apart from agent failures; trajectories saved for failure analysis |
| Harness² (later, E2) | Automatic propose → probe → keep loop; lesson format cue / lesson / evidence / confidence; fallback to the base setup when a proposal is invalid |
| Harness² (skipped) | Blind selector (our tests decide), full budget ledger (overkill at our scale) |
| Uber Debug Assist | Collect evidence with code before the first model call; narrow investigators (for a later `debug` command) |
| LangChain Deep Agents | Filesystem offload, summarization and subagent middleware, with our own short prompts |
| langgraph-bigtool | Tool retrieval (later) |
