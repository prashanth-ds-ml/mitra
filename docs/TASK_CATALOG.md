# Task catalog: what Mitra must do well, by priority (D-067)

The measuring stick for Mitra. Every task here becomes a drill or a level with checks Mitra never sees (hidden
tests, evaluation thresholds, browser or SQL checks) in `mitra-playground`, and is run on a schedule. A change to
Mitra is good only if it moves these numbers.

## Purpose (agreed 2026-11-10)

- **For personal use** (the user is an AI engineer), later adaptable to other kinds of engineer through profile packs
  (full-stack, DevOps, frontend, database developer).
- **Mitra's own brain does the work:** small open models with a growing harness, run on free GPU time (Kaggle now,
  Modal later) or the laptop. It thinks, plans, tests, fixes, runs and (with your OK) deploys.
- **Primary target: small and medium tasks, done properly and correctly.** For big tasks Mitra does the pieces
  handed to it (by you or by Claude Code).
- **A coach** (Claude or another big model) reviews Mitra's work periodically and writes a report with harness
  improvements; Mitra tests each one and keeps only what helps (Harness²-style). Over time it needs the coach less.
- **Learns from its user:** corrections, approvals, 👍/👎, your own code and recurring tasks, kept locally and editable.

## Definitions

| Size | Scope | Flow | Your involvement |
|---|---|---|---|
| **Small** | 1-2 files, under ~50 changed lines | done directly | none (checks green → done; `/undo` available) |
| **Medium** | 2-6 files, ~50-300 lines, maybe a new module | a short plan (2-4 steps) | one "Go" on the plan |
| **Big** | many files / long-running (fine-tune, full system) | planned by you or a coach | Mitra does the assigned pieces |

**Correct** means: the task's own checks pass (including hidden ones); nothing that passed before breaks; it did
what you meant; it says honestly when it could not finish.

## Catalog

Priority: **P1** first batch (build the checks and measure now) · **P2** next · **P3** later.
Status: ✓ exists in mitra-playground · ○ planned in the playground ladder · new = not yet anywhere.

| Area | Task | How Mitra proves it did it right | Size | Priority | Status |
|---|---|---|---|---|---|
| Everyday code | Fix a failing test; add a flag; rename; add a test; explain a function (drills on existing code) | the given tests pass; nothing else breaks; explanations checked by questions | small | **P1** | new |
| AI engineering | Clean or transform a dataset (pandas) | output schema and row checks on a sample | small | **P1** | new |
| AI engineering | Write or extend an evaluation script (metrics over outputs and references) | tests on known examples, score report generated | small-medium | **P1** | new |
| Games | Brick breaker features (pause menu, high scores, levels, sound) | hidden tests per feature; the game still runs | small-medium | **P1** | new (from the real project) |
| Back end / API | Add or fix an endpoint (FastAPI) | API tests, including error cases | small | **P1** | new |
| Database | Design a schema from a spec (tables, keys, constraints, indexes) | SQL checks: constraints reject bad data; required queries return the right rows | medium | **P1** | ○ level 03b |
| Games | Snake (logic + browser canvas) | 17 visible + 55 hidden tests | medium | **P1** (re-run as the starting score) | ✓ level 01 |
| AI engineering | Prompt / template work: variables, few-shot examples, output parsing | tests on fixed inputs; parsing never crashes on bad output | small | P2 | new |
| AI engineering | Turn a notebook into a module with tests | the tests pass; the notebook's outputs match | medium | P2 | new |
| AI engineering | RAG: ingest, chunk, embed, retrieve; fix bad retrieval | retrieval accuracy on a small question set ≥ threshold | medium | P2 | new |
| AI engineering | Benchmark models (speed, quality) | a results table, the same numbers on re-run | small-medium | P2 | new |
| AI applications | LLM app piece: a chain, a tool or structured output | tests with a fake LLM, plus one real call | small-medium | P2 | new |
| AI applications | Chatbot with memory over an API (Claude, Hugging Face, OpenRouter, ...) | conversation tests with a fake LLM; one real multi-turn call works | medium | P2 | ○ level 05 |
| AI applications | Tool-using agent (2-3 functions, e.g. search + calculator) | the right tools are called for scripted questions; answers correct | medium | P2 | new |
| AI applications | AI feature in an app (summarise, classify, extract) behind an endpoint | endpoint tests; output matches the schema; handles API errors | medium | P2 | new |
| Database | Write or fix a query; add an index for a slow query | correct results on seeded data; the plan uses the index | small | P2 | new |
| Database | Migration: add or change a column without losing data | data survives; old and new code paths pass | small-medium | P2 | new |
| Back end / API | API + database service (CRUD, validation, pagination) | full API test suite on SQLite, then Postgres | medium | P2 | ○ level 04 |
| Serving & deploy | Wrap a model or pipeline in FastAPI + Docker | the endpoint answers on a sample request | medium | P2 | new |
| Serving & deploy | Deploy to Hugging Face Spaces or Modal | the public URL answers a health check (asks you first) | medium | P3 | new |
| AI engineering | LoRA fine-tune on Kaggle and compare with the base model | training finishes; eval better than the base, or an honest "it wasn't" | medium-big | P3 | new |
| Games | A new small game from a spec (puzzle or platformer) | hidden tests on the game rules; the game starts | medium-big | P3 | ○ level 02 |
| Front end | A page or component (portfolio site, form, dashboard) | browser checks with Playwright: renders, form works, no console errors | medium | P3 | ○ level 03 |
| DevOps | Dockerfile / Compose for an app | builds; the app answers inside the container | small-medium | P3 | new |
| DevOps | CI workflow (tests on push) | the workflow passes on a test repo | small | P3 | new |
| DevOps | Fix an incident (failing service, bad config) across real tools | the planted problem is found and fixed; the health check passes | medium-big | P3 | ○ level 07 |
| Full stack | Small full system: front end + API + DB + AI feature | end-to-end test across all parts | big | P3 | ○ level 06 |

Notes:
- Real API calls (Claude, Hugging Face, OpenRouter) only in one final check per task; everything else uses a fake
  LLM, so runs are free and repeatable.
- Each task is tagged with its size and area, so results read like "small 90% · medium 60% · AI engineering 40%".
- Who writes the checks: Claude (Claude Code) writes each task with hidden checks and a reference solution that
  proves they pass, as for level 01.

## First batch (P1)

15 drills (5 on game code, 5 on Python / data / AI code, 5 on API / DB code) · the dataset clean-up · the evaluation
script · brick-breaker features · the endpoint fix · the schema design (03b) · level 01 re-run as the starting score.

## Still to clarify (in this order)

Settled 2026-11-10 in [BUILD_ORDER.md](BUILD_ORDER.md) (D-068): 1 (flow), 2 (coach by hand first), 5 (what we freeze). Open: 3, 4.


1. **How one task flows end to end** for you: where you hand it over (chat, a task file, Claude Code), what you
   approve, where it runs, how it reports back.
2. **The coach loop** (defaults proposed 2026-11-10: weekly + `/coach` + queued alerts; Claude via `claude -p`;
   compact digest; at most 5 improvements; each tested before it is kept).
3. **The harness parts per role**: which are fixed in code, which the coach may change.
4. **Profile pack format** (AI engineer first).
5. **What we freeze** while building this.
