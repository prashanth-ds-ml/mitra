---
title: Workflow Simplification
tags: [strategy, workflow, ux, planning]
aliases: [Simple Workflows First, Basic Workflows First]
---

# Workflow Simplification

This note captures the current product direction: keep the tool narrow, reliable, and easy to explain before expanding the agent surface.

## Guiding rule

- one command
- one purpose
- one obvious success path
- one obvious failure path

## Start with simple workflows

Prioritize these operator flows first:

1. `understand` to gather the smallest useful project context
2. `prd` to draft and revise a markdown PRD the user can review live
3. `status` and `config` for introspection
4. `plan` for a single clean planning flow
5. `next` for deterministic step execution
6. `fix` for a bounded repair loop
7. `review` for diff inspection
8. `mcp` as an inspection surface, not the primary runtime path

## Keep the agents narrow

Only expand the agents that support the above flows:

- planner: turn a goal into a safe plan
- understand: ask focused questions before drafting a PRD
- prd: turn understanding notes into a reviewable PRD
- filesystem: do local file work only
- shell: run approved commands only
- reviewer: summarize diffs and flag issues
- session and memory: record what happened
- one graph-backed repair path, not a full graph-first redesign

## Understand / PRD contract

When the assistant helps shape a project, it should follow this sequence:

1. accept the user's idea
2. ask only the minimum set of focused questions needed to remove ambiguity
3. save the answers into `.codemitra/understand.md`
4. draft `PRD.md`
5. let the user revise the PRD through prompting

The PRD should be the first reviewable artifact the user can inspect in real time.

## Brainstorming contract

When the assistant brainstorms a new project, it should collect only the minimum useful inputs:

- platform
- language or stack
- must-have features
- non-goals

Then it should stop unless a real blocker remains.

## What to freeze for now

- avoid adding new workflow families before the core ones are stable
- avoid mixing browser, backend, and desktop stacks in a single default plan
- avoid turning aliases into separate product surfaces
- avoid adding orchestration complexity that does not change reliability

## Recommended sequence

1. understand
2. plan
3. next
4. fix
5. review
6. docs

Only after those are reliable should the tool expand further.
