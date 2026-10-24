---
title: Understand and PRD Workflow
tags: [codemitra, workflow, prd, understand]
aliases: [PRD Workflow, Understand Workflow]
---

# Understand and PRD Workflow

This workflow is the first user-facing path for turning an idea into a reviewable product document.

## Purpose

Use this when a user has an idea and wants CodeMitra to ask the right questions before writing a PRD.

## Commands

- `/understand <idea>` asks focused questions and saves the result to `.codemitra/understand.md`
- `/prd <idea>` drafts `PRD.md` from the idea and understanding notes
- `/prd update <notes>` revises the current PRD from prompt feedback

## Expected flow

1. User shares an idea
2. CodeMitra asks a few specific questions
3. CodeMitra saves the understanding notes
4. CodeMitra drafts a markdown PRD
5. User reviews the PRD and gives change feedback
6. CodeMitra updates the PRD from that feedback

## Output files

- `.codemitra/understand.md`
- `.codemitra/prd.md`
- `PRD.md`

## Design rule

Keep the flow simple enough that the user can test it live and correct it through prompting without needing a separate planning ceremony first.
