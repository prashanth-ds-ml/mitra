# Routing Intelligence Implementation Order

Date: 2026-07-01

## Goal

Turn the routing-intelligence audit into a practical implementation plan for CodeMitra. The work should introduce a layered routing system that is explicit, testable, and safe while preserving the current workflow and agent architecture.

## Guiding Principles

1. Build the routing system in layers rather than as one large monolithic prompt.
2. Keep the first version small and useful.
3. Make routing decisions explicit and structured.
4. Prefer safe defaults over aggressive automation.
5. Reuse existing workflow, policy, and planner infrastructure where possible.

## Recommended Implementation Order

### Phase 0 — Foundation and Contracts

**Objective**

Create the core routing abstractions so the rest of the system can plug into them.

**Deliverables**

- A routing state data structure (for example: `RoutingDecision` or a dict-like contract)
- A routing engine interface that can produce a structured decision
- A simple registry of router modules
- A single place where the main app can read and apply the routing decision

**Why first**

Without a shared routing contract, every router remains disconnected and hard to evolve.

**Scope**

- Define the router output schema
- Define the router input schema
- Add a central routing service or module
- Add a minimal test harness for routing decisions

### Phase 1 — Intent Router

**Objective**

Classify incoming requests into a clear intent taxonomy.

**Target intents**

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

**Deliverables**

- A dedicated intent router module
- A structured output such as:

```yaml
intent: build
confidence: 0.91
reason: keyword and context match
```

- Fallback handling when the classifier is uncertain

**Why second**

Intent is the entry point for almost every other router. Once intent is explicit, the system can route to the correct workflow.

**Scope**

- Replace the current heuristic `_classify_intent()` logic with a dedicated router
- Add confidence scoring
- Add fallback behavior for unclear requests
- Add tests for common prompts

### Phase 2 — Project Router

**Objective**

Detect the project stack and use that knowledge to adapt routing behavior.

**Target project types**

- react
- fastapi
- python
- langgraph
- rag
- mongodb
- docker
- huggingface
- full-stack

**Deliverables**

- A project-type detection module
- Project-type heuristics based on repository files and structure
- A mapping from project type to defaults such as:
  - common entrypoints
  - test strategy
  - workflow templates
  - recommended tools

**Why third**

This is the biggest missing router and unlocks stack-aware behavior.

**Scope**

- Detect project type from files such as `package.json`, `pyproject.toml`, `requirements.txt`, `Dockerfile`, `src/`, `app/`, `tests/`, and framework-specific files
- Populate routing state with `project_type`
- Make project type influence workflow selection and context loading

### Phase 3 — Context Router

**Objective**

Select the smallest useful context set for the current task.

**Deliverables**

- A context selection module that chooses files and snippets based on intent and project type
- Context filtering to ignore large or risky files by default
- A prioritization strategy for likely relevant files

**Why fourth**

A smart system should not read everything. This phase improves both quality and performance.

**Scope**

- Choose relevant files based on intent
- Exclude noise such as `.env`, caches, build artifacts, and large generated files
- Prefer top-level config, entrypoints, relevant modules, and tests
- Keep a concise context summary for each task

### Phase 4 — Risk Router

**Objective**

Make safety decisions explicit and predictable.

**Deliverables**

- A low/medium/high risk classifier
- Approval requirements tied to the computed risk level
- A policy layer that maps risk to actions such as allow, ask, deny

**Why fifth**

Safety needs to be part of the routing decision from the beginning so the system doesn’t act recklessly.

**Scope**

- Classify actions such as read, edit, create, delete, install, run tests, docker build, git commit, git push, migration, and `.env` changes
- Add rules for approval requirements and destructive actions
- Tie this into the existing policy engine

### Phase 5 — Workflow Router

**Objective**

Map intents and routing decisions into concrete execution paths.

**Deliverables**

- A workflow-selection module
- Routing definitions for common paths such as:
  - build
  - fix
  - review
  - test
  - docs
  - continue
- A structure that can feed into the existing planner and LangGraph workflow system

**Why sixth**

Once intent, project type, context, and risk are known, the system can choose a workflow safely and consistently.

**Scope**

- Implement workflow mapping for the main intents
- Connect the chosen workflow to the current planner and workflow engine
- Preserve existing slash-command behavior while moving logic behind the router

### Phase 6 — Loop Router

**Objective**

Make the execution loop more adaptive and bounded.

**Deliverables**

- Retry controls for build/test/fix loops
- Stop conditions for repeated failure, scope drift, dependency changes, and max attempts
- A loop state object or policy

**Why seventh**

This improves reliability and prevents the system from thrashing during failures.

**Scope**

- Add same-error detection
- Detect repeated failures by fingerprinting the error output
- Stop when changes exceed safe limits
- Add support for a more general build → test → fix → review loop

### Phase 7 — Tool Router

**Objective**

Expose the correct tools per workflow phase.

**Deliverables**

- A tool-selection layer based on workflow phase and risk level
- A default tool matrix for:
  - plan
  - build
  - fix
  - review
  - docs
- Clear enforcement of the selected tool set

**Why eighth**

Tool availability should follow the current routing decision rather than be globally exposed.

**Scope**

- Restrict the set of tools exposed to the agent in different phases
- Prevent write tools during review and planning phases
- Use the existing permission and policy layer as enforcement

### Phase 8 — Model Router

**Objective**

Use model selection as part of routing instead of relying on a single default model.

**Deliverables**

- A model-routing module
- Task-to-model mapping for planning, code generation, small edits, review, and docs
- Runtime model selection based on context and workflow phase

**Why ninth**

Model routing improves quality and cost-efficiency and is already partially scaffolded.

**Scope**

- Route planning requests to a stronger reasoning model
- Route small edits to a lighter coding model
- Route review tasks to a review-oriented model
- Connect the existing model-advisor logic to routing decisions

### Phase 9 — Clarification Router and Next-Step Router

**Objective**

Add better ask-vs-proceed behavior and next-action selection.

**Deliverables**

- A clarification decision module
- A next-step router that decides the next action after each completed step
- Better messaging when the request is too broad or high-risk

**Why last**

These layers depend on the earlier routing information and are most useful once the core routers exist.

**Scope**

- Decide when to ask the user for clarification
- Decide when to proceed automatically
- Route to next steps such as build, review, docs, or final summary

## Suggested Delivery Milestones

### Milestone 1 — Routing Contract + Intent Router

**Outcome**

The system can classify a request and produce a structured routing decision.

### Milestone 2 — Project + Context + Risk Routers

**Outcome**

The system can choose relevant context and decide whether it is safe to act.

### Milestone 3 — Workflow + Loop + Tool Routers

**Outcome**

The system can execute a full task loop safely with the right tools and stopping conditions.

### Milestone 4 — Model + Clarification + Next-Step Routers

**Outcome**

The system becomes adaptive, safe, and more autonomous in day-to-day usage.

## Example Implementation Slice

A first slice could implement only the following:

- Intent Router
- Project Router
- Context Router
- Risk Router
- Workflow Router

This would already make the assistant feel significantly smarter while keeping the first version manageable.

## Recommended Order Summary

1. Routing contracts and shared state
2. Intent Router
3. Project Router
4. Context Router
5. Risk Router
6. Workflow Router
7. Loop Router
8. Tool Router
9. Model Router
10. Clarification Router
11. Next-Step Router

## Final Recommendation

Start with the first five phases. That is the best V1 path because it delivers the biggest user-visible improvement with the least complexity.
