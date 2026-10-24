# Routing Intelligence Audit

Date: 2026-07-01

## Overview

This document captures the routing-intelligence audit discussed in the current conversation. The goal was to review the CodeMitra repository and evaluate how well it supports the ten routing layers described in the request:

1. Intent Router
2. Project Router
3. Context Router
4. Workflow Router
5. Tool Router
6. Model Router
7. Risk Router
8. Clarification Router
9. Loop Router
10. Next-Step Router

The audit focused on the existing implementation in the repository and identified gaps, strengths, and recommended next steps.

## Executive Summary

| Router | Status | Quality | Gap Severity |
|---|---|---|---|
| Intent Router | Partial | Basic | High |
| Project Router | Missing | None | Critical |
| Context Router | Partial | Basic | High |
| Workflow Router | Partial | Good | Medium |
| Tool Router | Partial | Good | Medium |
| Model Router | Partial | Good | Medium |
| Risk Router | Partial | Basic | High |
| Clarification Router | Partial | Good | Medium |
| Loop Router | Partial | Basic | High |
| Next-Step Router | Partial | Good | Medium |

Overall assessment: routing intelligence is currently heuristic and mostly embedded in the main application flow rather than implemented as a layered router system with explicit state contracts.

## Repository Areas Reviewed

The audit examined the following areas:

- `app/main.py`
- `app/prompts.py`
- `app/config.py`
- `app/llm.py`
- `app/workflows.py`
- `app/langgraph_workflows.py`
- `app/advisor.py`
- `app/policy.py`
- `app/agents/planner.py`
- `app/agents/brainstorm.py`
- `app/agents/filesystem.py`
- `app/agents/shell.py`

## Router-by-Router Audit

### 1. Intent Router

**Requirement**

Classify user requests into intents such as:

- plan
- build
- fix
- review
- test
- document
- explain
- refactor
- scaffold
- continue

**Current status**

Partial implementation exists in `app/main.py`.

**What exists**

A heuristic intent classifier exists through `_classify_intent()` and related helpers. It handles categories such as:

- chat
- slash
- brainstorm
- run-help
- change
- plan
- explain
- run

**What is missing**

- No explicit 10-way intent taxonomy
- No model-based classification
- No confidence scoring
- No structured outputs for downstream routers
- No first-class `continue` intent handling beyond simple string checks

**Assessment**

Basic but fragile. Useful for simple requests, but not robust enough for a true routing layer.

### 2. Project Router

**Requirement**

Detect the project type and use that to adapt workflows, folder structures, tests, and best practices. Examples include:

- react
- fastapi
- python
- langgraph
- rag
- mongodb
- docker
- huggingface
- full-stack

**Current status**

Missing.

**What exists**

The repository has project-root detection and some project state detection, but not real project-type classification.

**What is missing**

- No project-type classifier
- No stack-aware scaffolding logic
- No mapping from detected project type to workflow templates or test strategy

**Assessment**

Critical gap. This is one of the biggest missing pieces in the routing stack.

### 3. Context Router

**Requirement**

Read only the relevant context for the task and suppress irrelevant files such as:

- `node_modules`
- `dist`
- `.env`
- large files

**Current status**

Partial implementation.

**What exists**

- Some workspace inspection helpers exist in `app/main.py`
- The brainstorm flow includes project context
- The system has some exclusion logic for obvious noise directories

**What is missing**

- No true selective context retrieval
- No intent-aware context selection
- No ranking of likely-relevant files
- No dependency/file-graph-based context narrowing
- No robust exclusion of secrets and large files at runtime

**Assessment**

Basic support exists, but the system still does not really “read just enough.”

### 4. Workflow Router

**Requirement**

Route requests into structured execution paths depending on intent.

**Current status**

Partial implementation.

**What exists**

- `app/workflows.py` defines bounded workflow contracts and limits
- `app/langgraph_workflows.py` contains a fix workflow graph
- `app/main.py` contains handlers for start/next/build/fix/review/test workflows
- `app/agents/planner.py` supports plan execution and step handoff

**What is missing**

- No full end-to-end workflow graph for all requested routes
- No explicit `/fix -> reproduce -> inspect -> patch -> test -> review` pipeline as a first-class router
- No full `/start -> plan -> prd -> order -> task -> build -> test -> review` chain wired end-to-end
- `/docs` and other workflows remain partial or implicit

**Assessment**

Good foundation, but not yet a comprehensive workflow router.

### 5. Tool Router

**Requirement**

Restrict tools by workflow phase and task type.

**Current status**

Partial implementation.

**What exists**

- `app/agents/filesystem.py` defines safe tools and destructive tools
- `app/policy.py` provides a deny-first policy engine
- `app/agents/shell.py` includes command allowlists and shell gating
- Session modes (`read-only`, `plan`, `approve`, `auto`) provide coarse-grained tool control

**What is missing**

- No per-phase tool matrix for plan/build/review/test/document flows
- No dynamic tool injection based on the current workflow state
- No specific tool restrictions for `/plan`, `/build`, `/review`, etc.

**Assessment**

The permission model is strong, but not yet expressed as a dedicated routing component.

### 6. Model Router

**Requirement**

Choose a model based on the task, such as planning, coding, review, docs, and small edits.

**Current status**

Partial implementation.

**What exists**

- `app/config.py` includes per-agent model defaults
- `app/advisor.py` scores installed models for chat/code/agent roles
- `app/llm.py` supports different model clients

**What is missing**

- The per-agent model defaults are not fully wired into runtime execution
- The advisor output is not used to dynamically route tasks to the best model
- No task-to-model routing layer at runtime

**Assessment**

There is a good foundation, but the model decision process is not yet truly dynamic.

### 7. Risk Router

**Requirement**

Classify actions by risk level and determine approval needs.

**Current status**

Partial implementation.

**What exists**

- Policy engine in `app/policy.py`
- Destructive-operation confirmation in filesystem and shell flows
- Session-mode gating for unsafe actions

**What is missing**

- No explicit low/medium/high risk taxonomy
- No pre-action risk classification
- No special handling for dangerous operations such as git reset, git push, `.env` edits, or database migrations
- Approval logic is coarse rather than risk-aware

**Assessment**

A risk-aware safety layer exists in fragments, but not as a first-class router.

### 8. Clarification Router

**Requirement**

Decide whether to ask the user for clarification or to proceed autonomously.

**Current status**

Partial implementation.

**What exists**

- `app/agents/brainstorm.py` provides an iterative Q&A flow
- The main application uses planning heuristics to trigger clarification before large tasks

**What is missing**

- No explicit confidence-based decision model
- No rule-based detection for conflicting requirements or overly broad scope
- No structured ask-vs-proceed decision process

**Assessment**

Good foundation. This layer is one of the more mature parts of the system.

### 9. Loop Router

**Requirement**

Control iteration loops such as build -> test -> fix -> test -> review.

**Current status**

Partial implementation.

**What exists**

- `app/langgraph_workflows.py` contains a fix loop graph
- `app/workflows.py` defines workflow limits and bounds

**What is missing**

- No same-error detection
- No dependency-change detection
- No automatic stop conditions for repeated failures
- No broader build/test/review loop beyond the fix workflow

**Assessment**

The loop concept exists, but it is still narrow and not yet robust enough for an adaptive routing loop.

### 10. Next-Step Router

**Requirement**

After each action, decide what should happen next.

**Current status**

Partial implementation.

**What exists**

- The main app contains some branch logic after actions and plan execution
- The fix workflow routes between test and repair nodes

**What is missing**

- No unified next-action policy engine
- No automatic transitions like test passed -> review, review passed -> docs
- No persistent next-step state across turns or sessions

**Assessment**

This is present in fragments, but not as a formal router.

## Biggest Gaps

The largest missing pieces are:

1. Project Router
2. A unified Context Router
3. Risk Router
4. Structured state output for routing decisions

## Recommended V1 Build Order

The following is the recommended first implementation order for a practical V1 routing layer:

1. Intent Router
2. Project Router
3. Context Router
4. Risk Router
5. Loop Router
6. Model Router

This set is sufficient to make the system feel significantly more intelligent without overbuilding the first version.

## Suggested V1 Routing Output Structure

A useful first version should produce structured routing state such as:

```yaml
intent: build
project_type: react
workflow: task_execution_loop
mode: collaborator
model: qwen2.5-coder:14b
context_files:
  - package.json
  - src/App.jsx
allowed_tools:
  - read_file
  - edit_file
  - run_command
risk_level: medium
approval_required:
  - npm install
  - delete_file
stop_conditions:
  - max_iterations: 5
  - tests_passed: true
next_action: build_task
```

## Conclusion

The repository already has good building blocks for routing intelligence:

- workflow control abstractions
- policy-based tool restrictions
- plan execution and brainstorming flows
- model inventory and selection support

However, those pieces are not yet composed into a unified routing system. The system still behaves more like a set of heuristics in a large orchestrator than a layered routing engine.

The most important next step is to introduce a dedicated router layer that produces structured routing decisions and feeds those decisions into the workflow, tool, model, safety, and clarification subsystems.
