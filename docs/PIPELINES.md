# Pipelines with LangGraph + bigtool tool retrieval (I-19, plan 2026-11-08)

Status: **plan for discussion; nothing built.** User: "can we use langchain or langgraph to start integrating big
tool and adding proper loops or pipelines that mitra can follow to increase its effectiveness along with self
improve". Ties together the phases design ([PHASES_AND_ROLES.md](PHASES_AND_ROLES.md)), overnight mode
([OVERNIGHT_MODE.md](OVERNIGHT_MODE.md)) and the bigtool idea (references/langgraph-bigtool; ROADMAP project 02).

## Where it fits, and where not
- **History:** Mitra used LangGraph before (a fix workflow) and removed it in M1. The trouble then was hand-offs the
  *model* decided between agents (E-019, E-020, E-022), not LangGraph.
- **Keep** Mitra's proven inner tool loop (one model, tools, guard, records, traces) as it is, as a node.
- **Use LangGraph for the outer pipeline**, with every edge decided by code (tests pass / fail / attempts), never by
  the model. What it adds that we lack today:
  - **checkpoints** (SQLite): a night run killed, crashed or interrupted by a reboot resumes at the next unfinished
    step (M3 "stop and resume");
  - **interrupts**: the evening "approve the plan" pause is a built-in step, not custom code;
  - **one visible flow per pipeline**, the same graph for chat `/run`, `mitra night` and tests; streaming of events
    to the terminal and the dashboard.
- Already available: langchain-core + langchain-ollama (Mitra uses them); langgraph 1.2.12 in the shared venv
  (Research Desk). To add to Mitra's own environment: `langgraph`, `langgraph-checkpoint-sqlite`, pinned.

## The pipelines (one graph each)
| Pipeline | Nodes (phases) | Edges (code decides) |
|---|---|---|
| **build-from-PRD** (overnight, `/run`) | prd → plan → plan check → [approve] → per task: tester → builder → (debugger) → reviewer → next task → deploy → report | tests pass → next; fail → debugger; 2 failed rounds → planner re-plan; still stuck → needs help, skip dependants; time / RAM limit → report |
| **fix** (`/fix`) | run command → debugger loop → verify | passes → done; N rounds → needs help |
| **review** (`/review`, final review) | diff → reviewer (planner model) → findings | findings → back to builder (bounded) or report |
| **improve** (`mitra improve`, night leftovers) | analyze patterns → propose (planner) → A/B on the bench → keep / revert | more hidden tests pass at ≤120% tokens → keep; else revert |
| **experiment** (screens, levels, nights) | setup → run → judge → registry entry ([EXPERIMENTS.md](EXPERIMENTS.md)) | — |
Each node switches the role (D-052 routing: model, context, tools, MCP, thinking) on entry, so models only swap at
node boundaries; the recorder and traces stay the same (one history per task, rows say which node / role).

## bigtool: retrieve the tools a step needs
- Core tools for the phase are always bound (D-052 tool sets). The long tail (MCP tools: dozens per server, later
  game / web / db tool sets) goes into a **registry**; a `find_tool` step retrieves the top 3-5 for the step.
- `langgraph-bigtool` supports a custom retrieval function: **BM25 / keyword first** (no embedding model, so no
  second model competing with the 9B for memory). Embeddings (`qwen3-embedding:0.6b`, installed) only if an
  experiment shows a gain and memory allows.
- This replaces today's keyword `mcp_find` ranking with one registry over Mitra tools + MCP tools (PLAN 21).

## How it helps effectiveness and self-improvement
- Effectiveness: small focused steps with the right model and tools; nothing lost on a crash (resume); the plan
  approved before work starts; debugging and review as real steps, not hopes.
- Self-improvement: every node is recorded with its role, inputs and outcome, so the dashboard and `mitra improve`
  see *which step* fails (planner? tester? builder?) and the improve pipeline itself is a graph with the A/B gate.

## Risks
- More dependency weight and a framework to learn (pin versions; one adapter module, the inner loop untouched).
- Hand-off bugs again: avoided by code-decided edges and one history; unit tests per edge.
- Debugging a graph: the records already say node + role; `langgraph dev` can show runs locally if wanted.

## Proposed order
1. Decide this plan (the phase loop 14e is the moment: build it as a LangGraph StateGraph instead of plain code).
2. build-from-PRD graph with SQLite checkpoints + approval interrupt, using today's inner loop and role routing;
   `mitra night` / `/run` call the graph. Resume tested by killing a run mid-task.
3. bigtool registry with BM25 retrieval for MCP tools (and the later tool sets).
4. fix, review, improve and experiment graphs.

## Experiment to decide it (#12 in EXPERIMENTS.md)
Level 01 and level 02 with today's `run_plan` vs the graph pipeline (same model): pass rate must not drop; resume
after a kill must work; time and steps compared. bigtool: right-tool rate and prompt tokens with retrieval vs all
tools bound (with the MCP comparison in M4).
