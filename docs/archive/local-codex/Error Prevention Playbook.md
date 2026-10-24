---
title: Error Prevention Playbook
tags: [quality, regressions, routing, docs, playbook]
aliases: [Regression Playbook, Error Patterns]
---

# Error Prevention Playbook

This document captures the recurring error patterns we have already seen in CodeMitra, how they were resolved, and what engineering rules should prevent them from coming back.

Use it after every notable bug fix:

1. record the failure in concrete user-facing terms
2. write the real root cause, not just the symptom
3. record the fix
4. add the regression test or workflow test that should stop recurrence
5. check whether docs or help text also need updating

---

## Why this exists

CodeMitra is a terminal product with:

- natural-language routing
- explicit plan / approval modes
- multiple tool and agent paths
- session state
- operator-facing docs and help text

That means many bugs are not isolated function bugs. They are **interaction bugs** between heuristics, orchestration, UX, and documentation.

---

## Current recurring error patterns

## 1. Overlapping natural-language routing rules

### Failure shape

A user asks for a concrete action, but CodeMitra routes to the wrong intent.

Examples already seen:

- simple `.venv` creation routed into brainstorm + plan
- `lets build a simple snakegame in this folder` routed into current-folder inspection

### Root cause

The routing layer in `app/main.py` uses overlapping phrase lists and regex heuristics:

- `_is_simple_change_request()`
- `_should_plan_first()`
- `_is_current_folder_request()`
- `_is_project_summary_request()`
- `_classify_intent()`

When these heuristics are too broad, generic phrases such as `this folder` or `understand` can hijack build/change requests.

### Resolution pattern

- narrow overly broad hint lists
- prioritize concrete action detection before explain-style detection
- add deterministic fast paths for trivial actions
- add transcript-level regression tests for the exact wording that failed

### Prevention rule

Never add a broad natural-language hint without also checking:

1. what action prompts it may accidentally match
2. whether it should be gated by intent or verb class
3. whether a transcript test is needed for conflicting phrasings

---

## 2. Incomplete soft-prefix normalization

### Failure shape

Two prompts mean the same thing, but one works and the polite/natural variant fails.

Examples already seen:

- `create a .venv in this folder`
- `can you create a .venv in this folder`
- `can you make .venv for this folder`
- `ok lets build ...`

### Root cause

Routing originally depended too much on exact sentence starts. Prefixes like:

- `can you`
- `lets`
- `ok`
- `great`

changed the detected intent even though the request meaning was unchanged.

### Resolution pattern

- centralize prefix stripping in `_strip_soft_prefixes()`
- strip prefixes repeatedly, not only once
- reuse the same normalization across routing helpers

### Prevention rule

When adding a new routing heuristic, test it against:

- direct phrasing
- polite phrasing
- conversational phrasing
- multi-prefix phrasing

If only the shortest phrasing is covered, the heuristic is incomplete.

---

## 3. Missing fast-path variants for trivial tasks

### Failure shape

A one-step task still goes through:

1. main router LLM
2. agent LLM
3. summarizer LLM

This makes simple requests feel slow and fragile.

Examples already seen:

- `.venv` creation
- simple file or folder creation
- install dependencies in current folder

### Root cause

The system originally had a strong complex-task path, but no strong deterministic path for trivial requests. Small wording differences also caused fast-path misses.

### Resolution pattern

- add `_extract_simple_change_action()`
- execute direct tool calls via `filesystem.run_direct()`
- limit the fast lane to clearly single-step operations
- keep the same permission and undo-aware tool layer underneath

### Prevention rule

For every new trivial capability, define:

- the direct-action parser
- the exact tool call
- the “do not fast-path” conditions
- at least one transcript regression for a natural-language variant

---

## 4. Documentation drift

### Failure shape

Docs remain internally inconsistent after the product changes.

Examples already seen:

- README reported `404` passing tests
- `docs/Home.md` reported `337`
- `docs/Testing Strategy.md` reported `337`

### Root cause

Behavior and tests changed faster than the shared docs baseline was updated.

### Resolution pattern

- update all baseline references in the same change when workflow behavior shifts
- prefer one authoritative baseline phrase across docs
- treat stale docs as quality bugs, not cosmetic issues

### Prevention rule

After changes that affect capability or test totals, search docs for:

- old test counts
- old command descriptions
- old capability claims
- old workflow status labels

If the code changed and the docs did not, the task is not fully complete.

---

## 5. REPL-centric orchestration drift

### Failure shape

Behavior becomes hard to reason about because too much routing and execution logic lives in `app/main.py`.

### Root cause

`app/main.py` owns too many concerns:

- startup UX
- intent classification
- slash command handling
- agent invocation
- session orchestration
- resource reporting

This makes interaction regressions easier to introduce.

### Resolution pattern

- keep extracting deterministic helpers
- isolate direct paths from generic LLM orchestration
- move reusable workflow logic into narrower modules when practical

### Prevention rule

If a fix requires touching multiple unrelated branches in `app/main.py`, consider whether the underlying behavior should be extracted into a dedicated helper/module instead.

---

## Required regression checklist after bug fixes

When fixing a bug in CodeMitra, check all of these:

1. **Unit/helper coverage** — the exact helper decision should be tested
2. **Transcript coverage** — the actual user phrasing should be tested
3. **Conflicting phrasing coverage** — nearby intents should be tested too
4. **Docs coverage** — help text, README, and docs baseline checked if relevant
5. **Fast-path check** — if the task is trivial, confirm it does not accidentally use the heavy orchestration path

---

## Recommended future audit focus

The highest-risk areas to keep auditing are:

1. routing phrases that share common English words
2. current-folder / understand / explain heuristics
3. simple task fast-path coverage
4. slash-command/help-text drift
5. large `app/main.py` changes that mix UX, routing, and execution updates

---

## Current baseline after the latest fixes

- direct fast path exists for trivial setup tasks
- `.venv` phrasing variants are covered by regression tests
- build requests mentioning `this folder` no longer route to folder inspection
- reclaimable process cleanup now covers local AI and user-owned GPU processes
- validated suite: **425 passing tests**
