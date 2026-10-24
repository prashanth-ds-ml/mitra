---
title: Plan UX Deep Dive
tags: [product, ux, routing, benchmark, analysis]
aliases: [Implementation Plan Deep Dive, Plan-First Analysis]
---

# Plan UX Deep Dive

## Why this doc exists

This document cross-checks CodeMitra's current product docs and code against public signals from Antigravity CLI and GitHub Copilot CLI, with one specific question in mind:

**How should CodeMitra show an implementation plan before starting work without becoming slow, heavy, or annoying on simple tasks?**

It is written from three lenses at once:

1. product leader
2. senior developer
3. expert CLI designer

---

## Executive summary

CodeMitra is **directionally right** and **interactionally uneven**.

The strong news:

- the product already believes in plan-first, approval-first, diff-first behavior
- the docs clearly position trust and explicitness as the desired UX
- the code already contains a direct fast path for trivial setup actions
- the testing docs already recognize that routing quality is a product problem, not just a helper-function problem

The weak news:

- CodeMitra still relies on broad natural-language heuristics to decide when to fast-path, when to plan, and when to route into heavier agent flows
- simple tasks remain a known regression class in the docs themselves
- the plan experience exists, but it is not yet the clean, obvious, first-class trust surface it should be
- `app/main.py` still carries too much routing and orchestration responsibility, which increases drift and regression risk

The most important conclusion is this:

> **The problem is not that CodeMitra plans too much. The problem is that it does not yet separate trivial work, bounded implementation work, and open-ended agentic work cleanly enough.**

That is where Antigravity and Copilot are useful reference points. The winning pattern is not "always plan first." The winning pattern is:

1. **instant action for deterministic one-step tasks**
2. **visible implementation plan for multi-step work**
3. **explicit approval and progress tracking for long or risky execution**

CodeMitra should adopt that separation more explicitly.

---

## What our own docs already say

### 1. The product intent is already correct

The repo already states the right target behavior in multiple places:

- `docs\Product Blueprint.md` says CodeMitra should show a short plan before acting on non-trivial work and ask before risky actions (`docs\Product Blueprint.md:137-140`)
- the same doc defines planning as a saved, approvable workflow with `/plan approve`, `/plan next`, `/plan run`, and `/resume` support (`docs\Product Blueprint.md:216-234`)
- `docs\Vision.md` says the product should "plan visibly before acting" and make background work and plan progress explicit (`docs\Vision.md:100-109`)
- `README.md` positions CodeMitra as "chat-first" but with direct fast paths for trivial setup tasks before escalating into plan or agent flows (`README.md:17-19`)
- `docs\Home.md` says the product favors **plan-first and approval-first UX** over hidden automation (`docs\Home.md:74-81`)

So from a product-strategy perspective, CodeMitra is not confused about the goal.

### 2. The repo already knows simple tasks are a weakness

This is the most important internal finding.

The project docs already record the exact class of failure the user called out:

- `docs\Error Prevention Playbook.md` lists recurring regressions where concrete actions route incorrectly, including simple `.venv` creation and basic build prompts (`docs\Error Prevention Playbook.md:35-74`)
- the same doc explicitly calls out **missing fast-path variants for trivial tasks** and says small wording differences made simple requests feel slow and fragile (`docs\Error Prevention Playbook.md:120-157`)
- `docs\Testing Strategy.md` explains that transcript-driven bugs happen when actionable setup work routes into brainstorm or planning instead of execution (`docs\Testing Strategy.md:28-37`)
- the testing doc also defines this as a permanent regression class and calls for transcript coverage around exact user phrasing (`docs\Testing Strategy.md:78-117`, `docs\Testing Strategy.md:246-260`)

This matters because it confirms the problem is not anecdotal. The repo has already observed and documented it.

---

## What the code says about the current behavior

### 1. The current routing split is real, but narrow

CodeMitra does have a meaningful fast lane.

`_SIMPLE_CHANGE_PATTERNS` currently recognizes only a small deterministic set of trivial actions: folder creation, directory creation, file creation, and `.venv` creation (`app\main.py:486-490`).

That is a good start, but it is narrower than the product promise implied by the docs and README.

### 2. The planning heuristic is broad

The plan trigger still depends on broad keyword heuristics:

- action starts such as `build`, `create`, `make`, `implement`, `fix`, `debug`, `remove`, and `delete` (`app\main.py:303-307`)
- complexity hints such as `with`, `project`, `app`, `workflow`, `tests`, `module`, `folder`, `directories`, and `throughout` (`app\main.py:308-312`)

Then `_classify_intent()` routes:

1. cleanup requests to `change`
2. simple change requests to `change`
3. all remaining plan-first matches to `plan` (`app\main.py:1192-1197`)

This design is understandable, but it means the system still relies heavily on wording shape rather than on an explicit task model.

### 3. The current plan UX is functionally present, but thin

The mechanics exist:

- `_confirm_plan_start()` asks whether to begin with step 1 or pause after planning (`app\main.py:2414-2430`)
- `/plan` generates a plan, writes `.codemitra\plan.md`, renders it, and points the user to `/plan approve` and `/plan next` (`app\main.py:3696-3704`)

This is good baseline functionality.

But from a UX perspective, it is still more like a command flow than a polished trust surface. The missing piece is not capability; it is **clarity, gradation, and confidence signaling**.

---

## External cross-check

## 1. Antigravity CLI

The most reliable public source available here is the Antigravity CLI repo itself.

Its README emphasizes:

- permissioned edits: "makes edits with your permission"
- multi-step reasoning
- multi-file editing
- tool calling
- persistent history
- a shared core agent engine between CLI and GUI
- shared settings and permissions
- session export from terminal to GUI

Source: `google-antigravity/antigravity-cli` `README.md`

Its changelog reinforces that the product invests in:

- `/diff` as a first-class surface
- sandbox-aware permission modes
- plugin discovery
- status-bar visibility
- subagent execution tuning
- project discovery robustness

Source: `google-antigravity/antigravity-cli` `CHANGELOG.md`

### Product lesson from Antigravity

The main Antigravity lesson is **not** "copy the GUI linkage" or "copy the cloud runtime."

The deeper lesson is this:

> **The terminal surface feels stronger when it is a thin, confident operator shell over a coherent runtime.**

That is why plan, permissions, diff, history, status, and plugins feel like one system instead of separate features.

For CodeMitra, the relevant takeaway is:

- make implementation planning a first-class operator object
- keep it connected to approvals, execution, diff, resume, and review
- avoid treating planning as a side path that exists only when `/plan` is explicitly invoked

## 2. GitHub Copilot CLI

Copilot CLI's official docs are much more explicit on this point.

GitHub documents a dedicated **plan mode** where Copilot:

- analyzes the request
- asks clarifying questions
- builds a structured implementation plan
- does this **before writing any code**

Source: `docs.github.com/copilot/concepts/agents/about-copilot-cli`

GitHub's CLI README also states a simple trust rule:

> **Preview every action before execution — nothing happens without your explicit approval.**

Source: `github/copilot-cli` `README.md`

### Product lesson from Copilot CLI

Copilot makes an important separation that CodeMitra should copy more clearly:

1. **planning mode** is about scope clarity and implementation structure
2. **approval controls** are about tool and write safety

Those are related, but they are not the same thing.

Today CodeMitra has both concepts, but they still feel somewhat blended. The result is that the system can feel heavier than necessary on small asks and less intentionally "planful" than desired on larger ones.

---

## Analysis from three lenses

## 1. Product leader lens

### What is working

CodeMitra already has a strong strategic shape:

- local-first and offline by default
- trust-oriented workflow
- visible operator controls
- a differentiated beginner-friendly `/create` workflow
- hardware-aware local model guidance

That is not commodity positioning. It is coherent.

### What is at risk

The main product risk is **trust erosion through inconsistency**, not missing capability.

When a simple task feels over-routed, the user concludes:

- the tool is slower than it should be
- the tool is less reliable than the UI claims
- the system may not understand task scale

That is dangerous because CodeMitra's brand is not "autonomous magic." Its brand is **thoughtful local control**.

If the product feels heavy on easy tasks, users stop trusting it on hard tasks too.

### What should be copied from Antigravity-style thinking

Copy:

- plan as a visible object, not just a background decision
- permissions and status as always-on operator surfaces
- diff and progress as integral parts of the same workflow
- tighter runtime coherence between plan, execute, review, and resume

Do **not** copy blindly:

- cloud-centered assumptions
- product complexity that weakens the local-first story
- heavyweight orchestration for tasks that should be one keystroke away

### Strategic recommendation

CodeMitra should explicitly define three product lanes:

| Lane | User expectation | CodeMitra behavior |
|---|---|---|
| Instant lane | "Just do the simple thing" | direct deterministic execution with normal approval guardrails |
| Plan lane | "Think through the implementation before coding" | show structured implementation plan, then approve or edit |
| Agent lane | "Carry this complex task through multiple steps" | plan + progress + checkpoints + resume + review |

That single framing would make the product much easier to understand and much easier to improve.

## 2. Senior developer lens

### Root cause of the "simple task struggle"

The core issue is not model quality first. It is control-flow architecture.

The repo already documents three interacting causes:

1. overlapping natural-language routing rules
2. incomplete soft-prefix normalization
3. missing fast-path variants for trivial tasks

Sources:

- `docs\Error Prevention Playbook.md:35-157`
- `docs\Testing Strategy.md:28-37`

In code terms, the current stack still depends on:

- regex fast paths for a narrow set of trivial actions
- keyword-based plan heuristics for everything else
- large REPL-centric orchestration in `app\main.py`

That combination works, but it is fragile.

### The architectural smell

`app\main.py` is still carrying too many responsibilities:

- routing
- UX decisions
- slash command handling
- execution transitions
- plan lifecycle glue
- session orchestration

The playbook already calls this out directly as **REPL-centric orchestration drift** (`docs\Error Prevention Playbook.md:195-222`).

That means routing bugs are likely to keep recurring unless the task model becomes more explicit.

### What should change technically

#### A. Replace keyword-only planning decisions with task-shape classification

Instead of only asking "does this sound like a plan-worthy sentence?", ask:

1. Is this single-step or multi-step?
2. Is it deterministic or exploratory?
3. Is it reversible and low-risk or broad and risky?
4. Does it imply multiple files, commands, or validation steps?

That produces better lanes than string matching alone.

#### B. Expand deterministic fast paths

The direct path should cover more than:

- folder creation
- file creation
- `.venv` creation

It should likely include small bounded tasks such as:

- install one known package
- add one config file from a known template
- run one safe project command
- rename one file within the workspace
- scaffold one small artifact using a fixed recipe

#### C. Move "implementation plan" into a typed workflow object

A plan should not just be markdown plus approval state.

It should carry:

- goal
- task class
- planned files
- planned commands
- validation steps
- risk level
- approval state
- active step
- execution history

The markdown file can remain the user-facing artifact, but the runtime should reason over a structured object.

#### D. Make misroutes measurable

CodeMitra should record lightweight local counters for:

- fast-path hits
- fast-path misses
- plan triggered automatically
- user rejected plan and asked for direct action
- user interrupted because task was too simple for planning

Without this, the same class of routing issues will keep being fixed reactively.

## 3. Expert CLI designer lens

### What the current UX gets right

- explicit modes
- visible command surface
- real plan controls
- diff/review/fix/undo operator vocabulary
- local memory and resume concepts

This is already above many local tools.

### What still feels off

The current interaction can still leave the user asking:

- Why did this route to planning instead of just doing it?
- Why did this use the heavy path for something small?
- What exactly will happen if I approve this?
- Am I approving a plan, a command, a file edit, or all three?

Those are UX taxonomy problems.

### Recommended target interaction model

#### 1. For trivial tasks

Show one compact action preview, not a plan.

Example:

```text
Action preview
- Create `.venv` in current folder
- No other files will be changed

Proceed? [Yes] [No]
```

#### 2. For bounded implementation work

Show a short implementation plan before any edits.

Example:

```text
Implementation plan
1. Inspect auth flow and failing tests
2. Patch login validation logic
3. Update or add regression tests
4. Run pytest -q

Planned files: app/auth.py, tests/test_auth.py
Validation: pytest -q

[Approve plan] [Run step 1 only] [Edit plan] [Cancel]
```

#### 3. For larger agentic work

Show the plan plus execution posture.

Example:

```text
Implementation plan ready
- 6 steps
- 4 expected file edits
- 2 validation commands
- resumable

Execution mode: step-by-step
[Approve and start] [Approve but pause] [Edit plan] [Cancel]
```

### CLI design principle

The interface should answer these four questions immediately:

1. **What lane am I in?**
2. **Why did the system choose this lane?**
3. **What exactly will happen next?**
4. **How do I stay in control?**

CodeMitra has the pieces. It still needs the choreography.

---

## Recommended roadmap

## P0 - fix the product feel

1. **Introduce explicit task lanes** in the runtime: instant, plan, agent
2. **Show implementation plan automatically for bounded multi-step work**
3. **Keep trivial tasks out of plan mode by default**
4. **Explain lane choice in one sentence** when auto-routing
5. **Unify plan approval wording** so users know whether they are approving strategy, execution, or a specific tool action

## P1 - reduce regression risk

1. expand deterministic fast-path coverage
2. add transcript tests for "simple but phrased naturally" prompts
3. extract routing and workflow state out of `app\main.py`
4. track local metrics on misroutes and overrides
5. make the plan object structured in code, not just rendered markdown

## P2 - strengthen the operator shell

1. add richer plan summaries: files, commands, validation, risks
2. add editable plan refinement before approval
3. deepen resume so it restores not just step state but plan intent and pending approvals
4. tie `/diff`, `/review`, and `/fix` more tightly into approved plan execution
5. keep growing plugin and future MCP surfaces around the same workflow object

---

## What CodeMitra should do next

If the goal is to improve product quality fastest, the next move should **not** be another broad feature layer.

It should be:

1. **make implementation-plan preview the default for bounded multi-step work**
2. **make trivial task execution faster and more deterministic**
3. **make the boundary between those two paths obvious to the user**

That change would improve:

- trust
- perceived intelligence
- speed on easy tasks
- predictability on hard tasks
- competitiveness against plan-forward terminal tools

And it would do so without giving up CodeMitra's core identity:

- local-first
- explicit
- safe
- beginner-friendly
- extensible

---

## Bottom line

From a product leader lens, CodeMitra already has the right philosophy.

From a senior developer lens, the current weakness is routing and workflow architecture, not missing ambition.

From an expert CLI designer lens, the highest-value fix is to make **plan preview a crisp, intentional middle lane** between direct action and full agentic execution.

That is the Antigravity-style lesson worth borrowing most aggressively.

---

## Sources

### Internal

- `README.md`
- `docs\Home.md`
- `docs\Product Blueprint.md`
- `docs\Vision.md`
- `docs\Testing Strategy.md`
- `docs\Error Prevention Playbook.md`
- `app\main.py`

### External

- `google-antigravity/antigravity-cli` `README.md`
- `google-antigravity/antigravity-cli` `CHANGELOG.md`
- GitHub Docs: `About GitHub Copilot CLI`
- `github/copilot-cli` `README.md`
