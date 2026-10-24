---
title: Phased Rollout
tags: [roadmap, rollout, implementation, execution]
aliases: [Layered Rollout, Execution Plan, Local Agentic Coding Tool Plan]
---

# Phased Rollout

This document is the active execution plan for future CodeMitra work.

It is not a greenfield design doc. It is a control document for building the next version of the product in a stricter sequence while keeping the current repo.

Use this document when deciding:

- what we build next
- what we deliberately do not build yet
- whether a proposed task fits the current phase
- whether an existing implementation is good enough to count for the active phase

For the current shipped system, use [[Architecture]], [[Multi-Agent System]], and [[Testing Strategy]].

For historical milestones and already-landed work, use [[Roadmap]].

---

## Active status

- **Current active phase:** `Phase 10 (complete)`
- **Next target phase:** `Maintenance`
- **Deferred by default:** `Phase 2+`
- **Repo strategy:** reuse what already works, reshape only where the active phase requires it, do not rewrite for aesthetics

Phase 9 is now closed in this repo. Keep the local-first MCP profile layer stable while working on the demo polish phase.
Phase 10 is now closed in this repo. The portfolio demo packs live under `docs/demo_flows/`.

---

## Core build rules

1. Build in layers.
2. Finish the lower layer before expanding the upper layer.
3. Prefer additive changes over rewrites.
4. Reuse existing code if it satisfies the active phase.
5. Refactor only when current structure blocks the active phase.
6. Do not add unrelated features while "cleaning up" a layer.
7. Every phase needs explicit completion criteria and tests.

---

## Canonical interface

The canonical CLI form for this plan is:

```bash
agent <command>
```

Examples:

```bash
agent status
agent config
agent models
agent start "Build a simple snake game using React"
```

Slash-style commands may exist as compatibility aliases:

```bash
agent /status
agent /start "Build a simple snake game using React"
```

Rule:

- docs and implementation should treat `agent <command>` as the stable interface
- slash commands are allowed for operator familiarity and backwards compatibility

---

## Storage compatibility decision

The current repo already uses `.codemitra/`.

This rollout keeps `.codemitra/` as the real storage root for now.

When the plan refers to `.agent/`, interpret it as the conceptual storage layer, not a mandatory immediate rename.

Rule:

- do not rename `.codemitra/` during early phases unless there is a strong migration reason
- if a later rename is desired, do it as an explicit compatibility phase with migration rules

---

## Architecture boundaries

Each phase owns a different concern.

| Phase | Primary concern | What should live there |
|---|---|---|
| 0 | foundation | CLI surface, config, root detection, logging, Ollama client |
| 1 | tools | filesystem, shell, git, markdown helpers, guardrails |
| 2 | traceability | logs, execution traces, memory store, task board, decisions |
| 3 | orchestration | workflow contracts, loop control, stop conditions, bounded execution |
| 4 | agents | planner/coder/tester/reviewer/docs behavior on top of tools and workflows |
| 5+ | operator UX and acceleration | commands, modes, skills, playbooks, MCP, demo polish |

Rule:

- if a change mixes multiple boundaries, split it unless the coupling is unavoidable

---

## Non-goals

These are explicit non-goals unless a later phase says otherwise:

- no MCP-first redesign
- no cloud-first architecture
- no new specialist agents before workflow contracts stabilize
- no large terminal UX redesign beyond what the active phase needs
- no broad repo cleanup unrelated to the active phase
- no replacing working subsystems just to match a cleaner ideal model

---

## Phase dependencies

The dependency chain is strict:

```text
Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4
Phase 4 -> Phase 5 -> Phase 6 -> Phase 7 -> Phase 8
Phase 8 -> Phase 9 -> Phase 10
```

Implications:

- command surfaces should not sprawl before tools are stable
- agents should not expand before workflow contracts exist
- MCP should not start before local tool contracts are stable
- playbooks should not expand before commands and workflows are reliable

---

## How existing code maps to this plan

The repo already contains more capability than the early phases describe.

That does not invalidate the plan. It changes how we execute it.

### Already present in some form

- Phase 0 pieces: Typer CLI, config loading, Rich output, Ollama client access, logging-like behavior
- Phase 1 pieces: filesystem and shell tooling, approvals, workspace restrictions
- Phase 2 pieces: `.codemitra/` memory files, session tracking, activity/context/plan storage
- Phase 3 pieces: bounded workflow contract now exists across planning, repair, and review loops
- Phase 4 pieces: multiple specialized agents already exist

### What is still missing from the phased model

- cleaner lower-layer boundaries
- clearer canonical command surface
- explicit phase-level completion gates
- a more deliberate workflow contract before more upper-layer expansion
- a single execution reference instead of feature growth by momentum

### Working rule for this repo

- if an existing capability satisfies the active phase, keep it
- if it partially satisfies the active phase, tighten it
- if it conflicts with the active phase, reshape only the minimum required area

---

## Success metrics

These are engineering control metrics, not product vanity metrics.

### Cross-phase metrics

- every phase has focused tests for its public surface
- phase docs and CLI behavior stay aligned
- no later-phase feature is added without being mapped to a phase

### Early-phase metrics

- Phase 0: basic commands succeed deterministically and fail clearly
- Phase 1: tools are bounded to workspace and enforce guardrails
- Phase 2: every important action is traceable
- Phase 3: workflow loops are bounded and reproducible
- Phase 4: agents operate through workflow/tool contracts rather than ad hoc behavior

---

## Phase template

Each phase below uses the same structure:

- `Goal`
- `In scope`
- `Out of scope`
- `Deliverables`
- `CLI surface`
- `Guardrails`
- `Done when`
- `Tests required`

---

## Phase 0: Foundation

**Goal:** Establish the minimum CLI and runtime foundation.

### In scope

- Typer CLI
- config loader
- project root detector
- Rich terminal output
- Ollama model caller
- logging system
- direct status/config/models command surface

### Out of scope

- general-purpose file editing tools
- workflow loops
- agent coordination
- advanced memory and tracing
- MCP integration

### Deliverables

```text
Typer CLI
Config loader
Project root detector
Rich terminal output
Ollama model caller
Logging system
```

### CLI surface

Canonical:

```bash
agent status
agent config
agent models
```

Compatibility aliases allowed:

```bash
agent /status
agent /config
agent /models
```

### Guardrails

- commands must work from nested directories by resolving project root
- config lookup must be deterministic
- Ollama failures must produce clear operator-facing messages
- logging must not require external services

### Done when

- `agent status` shows workspace and Ollama reachability
- `agent config` shows resolved config layers or effective config
- `agent models` lists local Ollama models or reports a clear empty/unavailable state
- project root detection works from nested paths
- the CLI can communicate with Ollama in a minimal, verifiable way

### Tests required

- root detection tests
- config resolution tests
- Ollama client/probe tests
- CLI command tests for `status`, `config`, and `models`

### Repo checklist

Use this checklist against the current repository before declaring Phase 0 closed.

| Item | Current repo status | Action |
|---|---|---|
| `agent` CLI entrypoint exists | Present in `pyproject.toml` | Keep |
| Canonical `agent status` command exists | Present | Keep |
| Canonical `agent config` command exists | Present | Keep |
| Canonical `agent models` command exists | Present | Keep |
| Slash compatibility aliases exist | Present for `/status`, `/config`, `/models` | Keep |
| Project root detection works from nested paths | Present via `detect_project_root()` | Keep |
| Config lookup is deterministic from project root | Present via `load()` and layered paths | Keep |
| Minimal Ollama reachability check exists | Present via `probe_ollama()` | Keep |
| Rich output exists for the Phase 0 commands | Present | Keep |
| Basic file logging exists for direct CLI commands | Present via `setup_logging()` | Keep |
| CLI help and docs prefer `agent <command>` as canonical | Partial | Tighten docs and examples over time |
| Phase 0 behavior is clearly isolated from later chat/agent surfaces | Partial | Tighten boundaries, do not rewrite |
| Phase 0 tests exist | Present | Keep and extend only if Phase 0 surface changes |

### Phase 0 close-out rule for this repo

Phase 0 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- the `Partial` items are documented and understood, even if not fully refactored
- no new Phase 2+ feature is added under the banner of "finishing Phase 0"

### What not to do while closing Phase 0

- do not refactor the whole interactive chat loop
- do not rename `.codemitra/`
- do not redesign slash-command UX
- do not start tool-layer expansion that belongs to Phase 1
- do not start workflow-engine work that belongs to Phase 3

---

## Phase 1: Core tools

**Goal:** Create the tool layer that any later workflow or agent can rely on.

### In scope

- file listing and reading
- search and text lookup
- file creation and writing
- edit/update operations
- shell command execution
- git status and diff helpers
- markdown file helpers
- core safety checks

### Out of scope

- persistent memory store
- workflow engine
- multi-agent orchestration
- playbooks
- MCP wrappers

### Deliverables

```text
list_files
read_file
search_text
create_file
edit_file
write_file
run_command
git_status
git_diff
create_markdown_file
update_markdown_file
```

### CLI/API surface

- direct internal tool contracts with stable inputs and outputs
- optional CLI inspection commands are acceptable, but the main deliverable is the tool layer itself

### Guardrails

```text
Only project folder
Block .env/secrets
Ask before delete
Ask before install
Ask before docker
Ask before destructive command
```

### Done when

- each tool has a clear contract
- tools cannot escape the allowed workspace
- sensitive files are blocked or redacted according to policy
- destructive or risky actions require explicit approval
- git helpers return deterministic operator-friendly output

### Tests required

- path restriction tests
- secret blocking tests
- create/edit/write tests
- shell approval tests
- git helper tests

### Repo checklist

Use this checklist against the current repository before declaring Phase 1 closed.

| Item | Current repo status | Action |
|---|---|---|
| `create_file` exists | Present | Keep |
| `read_file` exists | Present | Keep |
| `list_directory` exists | Present | Keep |
| `search_text` exists | Present | Keep |
| `edit_file` exists | Present | Keep |
| `run_command` exists | Present | Keep |
| `git_status` exists | Present | Keep |
| `git_diff` exists | Present | Keep |
| markdown helper tools exist | Present via `create_markdown_file` and `update_markdown_file` | Keep |
| tools stay inside workspace | Present via permission guard | Keep |
| secret-like files are blocked | Present for `.env` and `secret*` paths | Keep |
| delete operations require approval | Present | Keep |
| install operations require stronger explicit guardrail behavior | Partial | Tighten separately without expanding scope |
| docker-specific approval behavior exists | Missing | Defer unless Phase 1 shell scope requires it |
| tool contracts are documented in the phased plan | Present | Keep |

### Phase 1 close-out rule for this repo

Phase 1 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- the `Partial` and `Missing` items are consciously deferred or tightened with narrow changes
- new tools are not added casually without being mapped back to the planned tool layer

### What not to do while closing Phase 1

- do not expand into workflow orchestration that belongs to Phase 3
- do not add new specialist agents under the banner of tool work
- do not redesign the full shell subsystem if a narrow guardrail change is enough
- do not introduce MCP wrappers before the local tool layer is stable

---

## Phase 2: Logs and memory

**Goal:** Make important actions traceable and recoverable.

### In scope

- session logs
- execution trace
- decisions log
- error log
- task board
- user profile
- durable memory store

### Out of scope

- rich agent autonomy
- workflow graph complexity
- advanced playbooks
- MCP integration

### Deliverables

Conceptual target:

```text
.agent/session_log.md
.agent/execution_trace.jsonl
.agent/decisions.md
.agent/errors.md
.agent/task_board.md
.agent/user_profile.yaml
.agent/memory.sqlite
```

Current repo compatibility target:

```text
.codemitra/...
```

### What must be logged

```text
Prompts
Tool calls
Files changed
Commands run
Errors
Fix attempts
Tests
Decisions
```

### Guardrails

- traces must be append-safe
- logs must remain local-first
- logging should not silently break the main flow
- naming can stay `.codemitra/` until a real migration is justified

### Done when

- an operator can reconstruct what happened from stored artifacts
- file changes and commands have trace records
- failures and decisions are written in a human-readable form
- session state survives process restarts at the required phase level

### Tests required

- log creation tests
- append/update tests
- persistence and reload tests
- error logging tests

### Repo checklist

Use this checklist against the current repository before declaring Phase 2 closed.

| Item | Current repo status | Action |
|---|---|---|
| `activity.md` exists | Present | Keep |
| `session_log.md` exists | Present | Keep |
| `context.md` exists | Present | Keep |
| `plan.md` exists | Present | Keep |
| `brainstorm.md` exists | Present | Keep |
| `execution_trace.jsonl` exists | Present | Keep |
| `decisions.md` exists | Present | Keep |
| `errors.md` exists | Present | Keep |
| `task_board.md` exists | Present | Keep |
| `user_profile.yaml` exists | Present | Keep |
| `memory.sqlite` exists | Present | Keep |
| activity writes are traceable | Present | Keep |
| file change sets produce trace records | Present | Keep |
| errors are captured in human-readable form and trace form | Present | Keep |
| decision logging helper exists | Present | Keep |
| task board helper exists | Present | Keep |

### Phase 2 close-out rule for this repo

Phase 2 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- the trace artifacts are append-safe and local-only
- current higher-level flows keep writing useful artifacts without requiring a redesign

### What not to do while closing Phase 2

- do not redesign the whole memory model just to match a future ideal
- do not replace markdown files with SQLite-only storage
- do not move into workflow graph work that belongs to Phase 3
- do not add broad agent autonomy under the banner of traceability

---

## Phase 3: Workflow engine

**Goal:** Introduce controlled, bounded execution loops.

### In scope

- workflow contracts
- bounded loop execution
- stop conditions
- test/fix/review sequencing
- scope control
- iteration limits

### Out of scope

- more specialist agents
- broad command expansion
- project playbooks
- MCP integration

### Deliverables

```text
PlanWorkflow
PRDWorkflow
OrderWorkflow
TaskWorkflow
BuildWorkflow
FixWorkflow
TestWorkflow
ReviewWorkflow
DocsWorkflow
NextWorkflow
```

Main loop:

```text
build -> test -> fix -> test -> review -> done
```

### Guardrails

```yaml
max_iterations: 5
max_files_changed: 6
max_lines_changed: 300
require_tests: true
stop_on_scope_change: true
```

### Done when

- workflows run through explicit step contracts
- execution cannot loop indefinitely
- scope change stops the flow instead of drifting silently
- workflow output is inspectable and testable

### Tests required

- iteration-bound tests
- stop-on-scope-change tests
- build/test/fix loop tests
- workflow state transition tests

### Repo checklist

Use this checklist against the current repository before declaring Phase 3 closed.

| Item | Current repo status | Action |
|---|---|---|
| Explicit workflow contract exists outside the chat loop | Present via `app/workflows.py` | Keep |
| Plan execution runs through the workflow contract | Present | Keep |
| `/fix` repair loop runs through the workflow contract | Present | Keep |
| Iteration limits are explicit and persisted | Present | Keep |
| Scope-change limits for file and line churn exist | Present | Keep |
| Workflow state is written to session metadata | Present via `workflow_execution` | Keep |
| Workflow transitions are traceable in `execution_trace.jsonl` | Present | Keep |
| Review/test sequencing is fully unified under one engine | Present via `FixWorkflow` and `ReviewWorkflow` | Keep |

### Phase 3 close-out rule for this repo

Phase 3 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- loops that modify code are bounded by one shared workflow contract rather than ad hoc counters

### What not to do while closing Phase 3

- do not add more specialist agents under the banner of workflow work
- do not jump to LangGraph graph complexity before the local workflow contract is stable
- do not expand command surface area that belongs to Phase 5
- do not route stable local behavior through MCP just to match a future architecture

---

## Phase 4: Agents

**Goal:** Put agent behavior on top of stable workflows and tools.

### In scope

- planner agent
- PRD agent
- task agent
- coder agent
- tester agent
- reviewer agent
- docs agent
- decision agent

### Out of scope

- broad operator UX expansion
- template packs
- playbook catalog
- MCP ecosystem growth

### Deliverables

```text
Planner Agent
PRD Agent
Task Agent
Coder Agent
Tester Agent
Reviewer Agent
Docs Agent
Decision Agent
```

Model mapping target:

```yaml
planner: qwen3:14b
prd: qwen3:14b
task: qwen3:14b
coder: qwen2.5-coder:14b
tester: qwen2.5-coder:7b
reviewer: qwen3:14b
docs: qwen2.5-coder:7b
```

### Guardrails

- agents must use stable tool/workflow contracts
- role prompts should not encode hidden side effects
- agent behavior should stay bounded by workflow limits

### Done when

- agents can plan, build, test, review, and document through the workflow layer
- role boundaries are understandable
- model-role mapping is explicit and configurable

### Tests required

- agent routing tests
- role behavior tests
- workflow integration tests
- model mapping/config tests

### Repo checklist

Use this checklist against the current repository before declaring Phase 4 closed.

| Item | Current repo status | Action |
|---|---|---|
| Explicit Phase 4 agent-role registry exists | Present via `app/agents/registry.py` | Keep |
| Role boundaries are documented in code, not only implied by `main.py` | Present | Keep |
| Model-role mapping is explicit and configurable | Present via `agent_models` config | Keep |
| Planner behavior runs through workflow contracts | Present | Keep |
| Reviewer behavior runs through workflow contracts | Present | Keep |
| Build/test/fix behavior is assigned to bounded agent roles | Present via `coder` and `tester` role mapping | Keep |
| Status surface can show the resolved agent-role model map | Present | Keep |
| New agent work avoids bypassing workflows | Present as a Phase 4 guardrail | Keep |

### Phase 4 close-out rule for this repo

Phase 4 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- agent roles stay explicit and configurable instead of being re-embedded into ad hoc runtime wiring
- later command or playbook work reuses these role boundaries instead of inventing parallel role systems

### What not to do while closing Phase 4

- do not add broad new command UX that belongs to Phase 5
- do not add playbooks or templates under the banner of agent work
- do not introduce MCP-backed agents before local role wiring is stable
- do not create hidden side-effect prompts that bypass workflow limits

---

## Phase 5: Commands

**Goal:** Expose the workflow system through simple operator commands.

### In scope

```text
start
plan
prd
order
task
build
fix
test
review
docs
next
status
logs
```

### Out of scope

- mode proliferation beyond what commands need
- project playbook expansion
- MCP-first command surfaces

### CLI surface

Canonical:

```bash
agent start "Build a simple snake game using React"
```

Compatibility aliases allowed:

```bash
agent /start "Build a simple snake game using React"
```

### Done when

- one prompt can enter a structured workflow
- commands map cleanly to workflow contracts
- status and logs surface the right execution state

### Tests required

- command parsing tests
- command-to-workflow routing tests
- operator status/log tests

### Repo checklist

Use this checklist against the current repository before declaring Phase 5 closed.

| Item | Current repo status | Action |
|---|---|---|
| Canonical `agent start` command exists | Present | Keep |
| Canonical `agent next` command exists | Present | Keep |
| Canonical `agent build` command exists | Present | Keep |
| Canonical `agent test` command exists | Present | Keep |
| Canonical `agent logs` command exists | Present | Keep |
| Slash compatibility aliases exist for the Phase 5 commands | Present | Keep |
| Command surfaces map to workflow/tool contracts instead of duplicate orchestration | Present | Keep |
| `.codemitra` artifacts are inspectable through a stable command surface | Present via `agent logs` | Keep |
| Advanced commands like `prd`, `order`, `task`, and `docs` are only added when backed by stable behavior | Deferred intentionally | Keep deferred until behavior is real |

### Phase 5 close-out rule for this repo

Phase 5 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- command names become the primary operator interface for the already-stable workflows
- deferred commands are not added as thin marketing aliases without distinct behavior

### What not to do while closing Phase 5

- do not invent command families that bypass the workflow layer
- do not add mode-specific behavior that belongs to Phase 6
- do not add playbook-driven shortcuts that belong to Phase 8
- do not make MCP a prerequisite for any command in this phase

---

## Phase 6: Work modes

**Goal:** Support distinct engineering collaboration styles without changing the core workflow engine.

### Deliverables

```text
builder
collaborator
mentor
architect
reviewer
debugger
product
```

### Done when

- the same workflow can run with different response and decision styles
- mode differences are explicit rather than accidental

### Repo checklist

| Item | Current repo status | Action |
|---|---|---|
| Canonical work modes are defined in config and CLI defaults | Present via `work_mode` | Keep |
| `agent start`, `agent next`, and `agent build` can accept a work mode | Present via `--mode` | Keep |
| The interactive prompt shows the active session mode and work mode | Present in the prompt label | Keep |
| `agent status` reports the active work mode and style summary | Present | Keep |
| Workflow planning and routing receive the selected work mode | Present in planner prompts | Keep |

### Phase 6 close-out rule for this repo

Phase 6 should be treated as complete when:

- the configured work mode is visible in the prompt and status output
- command-level overrides for work mode keep the workflow behavior explicit
- planner routing and plan generation receive the same mode context

### What not to do while closing Phase 6

- do not add mode families that are only names without behavior
- do not let work mode mutate session safety rules
- do not rename session mode into work mode or vice versa

---

## Phase 7: Templates and skills

**Goal:** Make outputs more consistent and reusable.

### Deliverables

```text
skills/
├── coding.md
├── debugging.md
├── review.md
├── testing.md
├── markdown.md
├── react.md
├── fastapi.md
├── langgraph.md
├── rag.md
├── docker.md
└── huggingface.md
```

```text
templates/
├── prd.md
├── implementation_order.md
├── task.md
├── review.md
├── debug.md
├── README.md
└── setup.md
```

### Done when

- repeated outputs become structurally consistent
- project-specific guidance can be reused without re-prompting everything

---

### Repo checklist

| Item | Current repo status | Action |
|---|---|---|
| Canonical general-purpose skills exist as markdown playbooks | Present under `skills/` | Keep |
| The repo contains reusable template files for PRDs, tasks, reviews, debug, and setup | Present under `templates/` | Keep |
| Skills are discovered from workspace-local markdown files | Present via `app/skills.py` | Keep |
| The builder and docs can point users to the reusable template pack | Present in docs and repository layout | Keep |

### Phase 7 close-out rule for this repo

Phase 7 should be treated as complete when:

- reusable skill playbooks exist in the repo and are discoverable
- the template pack is present and stable
- repeated outputs can follow the same structure without re-inventing format each time

### What not to do while closing Phase 7

- do not replace markdown skills with a new runtime model yet
- do not make templates depend on MCP or external services
- do not remove the existing numbered skill pack while adding canonical aliases

----

## Phase 8: Project playbooks

**Goal:** Accelerate common project types.

### In scope

- constrained playbook discovery
- `agent playbooks`
- `agent start --playbook <name>`
- playbook-to-workflow seeding

### Out of scope

- MCP-backed project starters
- arbitrary prompt packs that bypass workflows
- broad template-engine expansion

### Deliverables

```text
react-demo
simple-game
fastapi-api
rag-app
langgraph-agent
huggingface-demo
docker-service
full-stack-ai-app
```

### CLI surface

Canonical:

```bash
agent playbooks
agent start --playbook simple-game "Build a memory card game"
```

Compatibility aliases allowed:

```bash
agent /playbooks
agent /start --playbook simple-game "Build a memory card game"
```

### Guardrails

- playbooks must stay workspace-local and markdown-based
- playbooks must seed workflows instead of bypassing them
- playbooks should stay constrained to common project types
- playbook selection must fail clearly when the name is unknown

### Done when

- the system can start common project patterns from a constrained playbook
- playbooks compose with workflows instead of bypassing them

### Tests required

- discovery tests for the playbook registry
- CLI tests for `playbooks`
- CLI tests for `start --playbook`

### Repo checklist

Use this checklist against the current repository before declaring Phase 8 closed.

| Item | Current repo status | Action |
|---|---|---|
| Canonical `agent playbooks` command exists | Present | Keep |
| `agent start --playbook <name>` works for local playbooks | Present | Keep |
| Slash compatibility aliases exist for playbook commands | Present | Keep |
| The playbook catalog is workspace-local markdown | Present under `playbooks/` | Keep |
| Playbook discovery stays constrained to workspace roots | Present | Keep |
| Playbook selection feeds the existing workflow layer | Present | Keep |
| Playbook coverage includes the common starter project types in this plan | Present | Keep |

### Phase 8 close-out rule for this repo

Phase 8 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- playbooks can seed a workflow without replacing the workflow layer
- no playbook behavior is added that quietly bypasses the command/workflow contracts

### What not to do while closing Phase 8

- do not introduce MCP just to load playbooks
- do not turn playbooks into a second workflow engine
- do not add a generic templating system under the banner of project starters
- do not broaden the playbook catalog beyond the constrained starter set without a reason

---

## Phase 9: MCP integration

**Goal:** Add MCP after the local tool and workflow core is stable.

### In scope

- local-first MCP profile registry
- MCP status and inspection surface
- filesystem, git, sqlite, and context7 profiles
- direct local tool fallback
- filesystem read/list routing through MCP when enabled

### Out of scope

- hard dependency on an MCP client library
- replacing stable direct tools with MCP-only execution
- broad plugin or marketplace expansion
- remote-first transport assumptions

### Deliverables

```text
Filesystem MCP
Git MCP
SQLite MCP
Context7 MCP
```

### CLI surface

Canonical:

```bash
agent mcp
```

Compatibility aliases allowed:

```bash
agent /mcp
```

### Guardrails

- keep direct local tools as fallback
- do not replace stable local behavior just to route through MCP
- keep MCP support local-first and inspectable
- prefer profile/config wiring before adding transport complexity

### Tests required

- config tests for default MCP profiles
- registry tests for MCP profile formatting and lookup
- CLI tests for `mcp`
- status tests should surface MCP readiness

### Repo checklist

Use this checklist against the current repository before declaring Phase 9 closed.

| Item | Current repo status | Action |
|---|---|---|
| Canonical `agent mcp` command exists | Present | Keep |
| Slash compatibility alias exists for MCP | Present | Keep |
| Default MCP profiles are local-first and inspectable | Present | Keep |
| `filesystem`, `git`, `sqlite`, and `context7` are represented | Present | Keep |
| Direct local tools remain the fallback path | Present | Keep |
| Filesystem read/list can route through MCP when enabled | Present | Keep |
| Status output mentions MCP readiness | Present | Keep |
| MCP wiring does not require a network dependency to run the repo | Present | Keep |

### Phase 9 close-out rule for this repo

Phase 9 should be treated as complete when:

- the checklist items marked `Keep` remain stable
- MCP exists as a local-first profile and status surface
- no new MCP work replaces the existing local tool path

### What not to do while closing Phase 9

- do not make MCP a prerequisite for basic CLI operation
- do not switch built-in tools off just because MCP profiles exist
- do not add transport complexity before the profile layer is stable
- do not treat remote servers as the default runtime

### Done when

- MCP adds capability without becoming a prerequisite for the core product

---

## Phase 10: Demo polish

**Goal:** Produce portfolio-ready end-to-end demo flows.

### Demo flows

```bash
agent start "Build a simple snake game using React"
agent start "Build a local RAG app using FastAPI and Ollama"
agent start "Build a Pomodoro timer using React"
```

### Final outputs

```text
Working app
Passing build
PRD.md
PRD.pdf
IMPLEMENTATION_ORDER.md
README.md
Session logs
Decision journal
```

The committed demo packs keep the markdown sources stable; the PDF export is the generated version of the same PRD when a demo run needs it.

### Done when

- the demo flows are repeatable
- the output artifacts are coherent and complete
- the product can be shown without manual explanation of internal gaps

### Repo checklist

Use this checklist against the current repository before declaring Phase 10 closed.

| Item | Current repo status | Action |
|---|---|---|
| Demo packs exist for the three showcase flows | Present under `docs/demo_flows/` | Keep |
| Each demo pack contains PRD, implementation order, README, session log, and decision journal | Present | Keep |
| Demo prompts are explicitly documented in the rollout plan | Present | Keep |
| Phase 10 output artifacts are coherent enough for portfolio use | Present | Keep |

### Phase 10 close-out rule for this repo

Phase 10 should be treated as complete when:

- the showcase demo packs remain present and stable
- the final-output structure is documented and repeatable
- no new infrastructure is required just to explain or run the demos

---

## Recommended build order

Primary build sequence:

```text
Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4
```

After the system becomes usable:

```text
Phase 5 -> Phase 6 -> Phase 7 -> Phase 8
```

Then:

```text
Phase 9 -> Phase 10
```

Rule:

- do not start with MCP
- build the tool and workflow core first
- phase 8 should stay additive: playbooks seed work, they do not replace the workflow model

---

## Immediate operating rule

Unless there is a clear blocker, current work should stay within:

```text
Phase 0 -> Phase 9
```

Anything outside those layers needs an explicit reason.
