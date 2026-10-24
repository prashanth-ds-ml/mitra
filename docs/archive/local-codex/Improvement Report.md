---
title: Improvement Report
tags: [analysis, improvement, architecture, ux]
aliases: [Whole Tool Improvement Report, Tool Improvement Analysis]
---

# Improvement Report

This document captures the improvement analysis for the whole tool, not just one feature slice.

## Summary

CodeMitra is functionally strong:

- local-first Ollama usage is real
- workflow execution is bounded and traceable
- filesystem and shell guardrails are effective
- the CLI exposes a large, useful operator surface
- the test suite is broad and currently green

The main opportunity now is consolidation. The tool has grown fast enough that the primary risk is not missing capability; it is drift between code, docs, command aliases, and orchestration styles.

## What Is Working

- Ollama is used as a real runtime backend through `ChatOllama` and the local HTTP probe.
- The workflow engine persists execution state and blocks on iteration and scope limits.
- The fix loop now has a real LangGraph-backed path without replacing the existing workflow engine.
- MCP is local-first and still falls back to the direct Python tools.
- Tests cover the operator journeys rather than only helper functions.

## Highest-Value Improvements

### 1. Consolidate the docs story

The repo has both a historical roadmap and an active phased rollout plan. That is fine, but the distinction must stay explicit.

Current risk:

- readers may follow the wrong document
- counts and state snapshots can drift
- command names and phase labels can diverge between docs

Recommended action:

- keep `docs/Phased Rollout.md` as the active execution plan
- keep `docs/Roadmap.md` as the historical or product-level phase record
- ensure the landing pages point to the correct document for each use case

### 2. Split the CLI router

`app/main.py` is doing too much. It owns command routing, workflow orchestration, status surfaces, review/fix flows, and operator UX.

Current risk:

- refactors become hard to reason about
- small changes can affect unrelated commands
- tests need to cover a lot of hidden branching in one file

Recommended action:

- move command groups into dedicated modules
- keep `main.py` as a thin router and bootstrapper
- preserve the current behavior while moving code out incrementally

### 3. Tighten the LangGraph integration

LangGraph is now used, but only for the fix workflow.

Current risk:

- the graph is rebuilt on each invocation
- the state carries live objects instead of a serializable state contract
- resume/checkpoint benefits are not yet being used

Recommended action:

- cache the compiled graph
- narrow the graph state shape
- add a second graph-backed workflow only after the fix flow is stable

### 4. Reduce operator-surface duplication

The repo supports `agent <command>` plus many slash aliases.

Current risk:

- documentation and examples can drift
- the canonical interface becomes ambiguous
- help text has to explain multiple equivalent entry points

Recommended action:

- keep one canonical command form in docs
- treat slash forms as compatibility aliases only
- avoid adding new aliases unless they solve a real migration problem

### 5. Add small end-to-end smoke tests

The suite is broad, but a couple of smoke tests would be useful at the top of the stack.

Recommended action:

- one smoke test for `agent start`
- one smoke test for `/fix`
- one smoke test for `/mcp`

These should be lightweight and prove the CLI glue still matches the workflow layer.

## Current Documentation Drift

- `README.md` and some docs previously referenced outdated test counts.
- The landing docs should reflect the current test baseline instead of historical numbers.
- The tech stack narrative needed to be updated once LangGraph started doing real work.

## Immediate Backlog

Priority order:

1. Cache the LangGraph fix graph.
2. Split `main.py` into thinner command modules.
3. Reconcile README and docs with the current test baseline.
4. Add end-to-end smoke tests for the main operator flows.
5. Extend LangGraph only when another workflow clearly benefits from it.

## References

- [[Phased Rollout]]
- [[Roadmap]]
- [[Architecture]]
- [[Testing Strategy]]
- [[Tech Stack]]

