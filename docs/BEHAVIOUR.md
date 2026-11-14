# CodeMitra's ideal behaviour (D-066)

One sentence: **code decides the phase; each phase is one role with a narrow job, only its own tools, a budget, a
thinking setting and the right machine; code gathers the context and runs the checks; "done" means green.**
No sub-agents (D-037, D-049): one loop that changes role per phase.

Why (2026-11-10 session): "hi mitra" became a 19-step investigation (230K tokens, no answer); "explain the game
logic" thought for 5 minutes. Every message ran as `chat` with every tool, thinking on, 40 steps.

## 1. Every request takes a fixed path (decided by code, no model call)

| Request | Path |
|---|---|
| Small talk ("hi", "thanks", "ok") | **reply** (no tools) + the "where we stopped" brief |
| Where did we stop / status | the **brief** from CodeMitra's records, no model call |
| Question ("explain…", "how does…") | **explain** (read only, 6 steps) → answer |
| Fix a bug ("test X fails", "error …") | code runs the tests → **debug** → code checks → **report** |
| Small change (one clear edit) | **build** → code checks → **debug** if red (2 rounds) → **report** |
| Bigger change | **plan** → code checks the plan → **you: Go / Change / Save / Cancel** → per task: **test** → **build** → **debug** → checkpoint → final checks → **review** → **report** |
| Unclear request | **ask** 1-2 questions first (explainer or planner) |
| Run it / check the UI (later) | **deploy**: start the app, check it answers / looks right |

`/plan <task>` forces planning, `/do <task>` skips it. Auto mode: the plan is shown and starts.

## 2. Roles: job, tools, MCP, thinking, budget, machine

MCP tools are given **directly** by name to the roles that need them (not through `mcp_find` / `mcp_call`, which a
small model rarely uses well). `*` = only when the project needs it (section 4).

| Role | Job | CodeMitra tools | MCP tools | Thinking | Budget | Runs on |
|---|---|---|---|---|---|---|
| chat | small talk; general requests | none for small talk; everything incl. `mcp_find`/`mcp_call`, `run_plan` for unsorted requests | all enabled (via find/call) | off | 1 call (small talk) | laptop |
| explainer | answer questions about the code | `list_files`, `read_file` (outline), `search`, `web_search`, `fetch_url`, `answer`, `ask_user` | Serena (find symbol, overview, references), git (log, blame), context7, MarkItDown*, research-desk*, PostgreSQL/SQLite* (read-only) | off | 6 steps, then must `answer` | laptop |
| planner | request → 2-6 small tasks | `ask_user`, `web_search`, `fetch_url` (code hands it the project map) | context7, GitHub* (read), MarkItDown*, research-desk* | on | 2 calls | laptop |
| tester | write the task's test first | `read_file`, `search`, `write_file`/`edit_file`/`append_file`/`make_dir` **in tests/ only**, `run_tests` | context7, Playwright* | on | 8 steps | Kaggle when up |
| builder | make the task's test pass | `read_file`, `search`, `write_file`, `edit_file`, `append_file`, `make_dir`, `check_code`, `run_tests`, `run_command` (tolerant), `finish` (tests/ read-only) | Serena (symbol edits), context7, shadcn* | off | 15 steps per task | Kaggle when up |
| debugger | make red green | `read_file`, `search`, `edit_file`, `check_code`, `run_tests` (structured), `run_command`, `finish` | Serena, git (diff, log), PostgreSQL/SQLite* (read-only), Playwright* | on | 10 steps × 2 rounds, then back to the planner | Kaggle when up |
| reviewer | read the final diff; report problems (never edits) | `read_file`, `search`, `answer` | git (diff); **semgrep is run by code** in the final checks | on | 2 calls | laptop |
| deployer (later) | start the app, check it works | `run_command`, `run_tests`, `answer` | Playwright*, Docker* | off | 8 steps | laptop |
| reporter | summary + `.codemitra/resume.md` | none (code gives it the facts) | none | off | 1 call | laptop |

When a budget runs out the role must answer or report what it has; it never loops. Each role's prompt holds only
its own tools (CI checks the prompt budget per role).

## 3. What code does (so the model does not have to)

- **Sorts the request and picks the phase.** The model never decides "now I will investigate".
- **Gathers the context:** the "where we stopped" brief, the project map (files, outlines; Serena when on), the
  relevant files, the failing test's output. Each phase gets a fixed context budget; never whole large files.
- **Runs the checks:** syntax after every write, the task's test, all tests, semgrep at the end. Done = green.
- **Normalises the model's mistakes instead of refusing:** `2>&1`, `| tail -N`, `| head -N`, `cd x &&`, bare
  `pytest`, wrong paths (suggests the real file). Structured test failures (name, file:line, error).
- **Checkpoints:** a commit per finished task on a work branch; after any stop (Kaggle, crash, ctrl+c) the plan
  continues from the first unfinished task.
- **Places each phase on its machine:** read work on the laptop, write work on Kaggle when it is up (D-062);
  quietly smaller laptop model when RAM is short; Kaggle ended → laptop + report + stop.
- **Records everything** (traces, outcomes, your corrections, `/good` `/bad`) for the dashboard and self-improvement.

## 4. Tools and MCP servers: the full list

### CodeMitra's own tools
| Tool | Status |
|---|---|
| `list_files`, `read_file` (outline for large files), `search`, `make_dir`, `write_file`, `edit_file`, `append_file`, `check_code`, `run_tests`, `run_command`, `web_search`, `fetch_url`, `finish` | have; `run_command` becomes tolerant, `run_tests` structured |
| `mcp_find`, `mcp_call` | have; chat role only |
| `run_plan` | have; chat role only (code runs plans in the plan path) |
| `answer` | new: ends a read-only role's turn with its answer |
| `ask_user` | new: 1-2 clarifying questions |
| `find_symbol`, `symbols_overview`, `replace_symbol` | new, from Serena (trial); a light own version on the Python parser if Serena loses |

### MCP servers
| Server | Roles | When |
|---|---|---|
| git | explainer, debugger, reviewer | on (any code) |
| context7 | explainer, planner, tester, builder | on (needs Node) |
| Serena | explainer, builder, debugger | trial on a playground level (on vs off); on by default if it wins |
| semgrep | run by code in the final checks | on |
| GitHub / GitLab | planner (read-only) | project has that remote; needs a login |
| Playwright | tester, debugger, deployer | project has a web front-end; with the deploy path |
| MarkItDown | explainer, planner | project has PDFs / Word / slides |
| PostgreSQL / SQLite | explainer, debugger (read-only) | project uses that database |
| shadcn | builder | web project using shadcn/ui |
| research-desk | explainer, planner | your Research Desk (project 04) runs as an MCP server |
| Docker | deployer | later, with the deploy path |
| AWS docs / LocalStack | none by default | ops work only (PLAN M4) |
| Chrome DevTools | none (Playwright first) | maybe later |
| **Never:** filesystem, fetch, memory, sequential thinking, time (duplicate CodeMitra's own tools or add nothing for a small model); Redis, Sentry, Cloudflare, Postman (production / infrastructure, not CodeMitra's job) | | |

Per-project offer: on the first start in a project CodeMitra looks at it (remote, `package.json`, database libraries,
documents) and offers the matching servers once; `/mcp` changes it any time.

## 5. What you see

- One status line: where it runs (☁ kaggle / 💻 laptop), model, context, hours left.
- A live checklist for plans: `✓ T1  ✓ T2  ▶ T3 test  · T4`.
- One line per phase change ("explaining: read only", "building T2", "checks: 12 passed"), not walls of output.
- At the end: what changed, the checks, what is next (also in `.codemitra/resume.md`); `/undo` always works.

## 6. Build order

**Replaced by [BUILD_ORDER.md](BUILD_ORDER.md) (D-068).** Kept below for reference.


1. `app/core/behaviour.py`: this file's role table (jobs, tools, direct MCP tools, thinking, budget, machine) as the
   one source of truth; roles.py and the routing read it.
2. Small talk, question and where-we-stopped paths; tolerant `run_command`, structured `run_tests`, `answer`,
   `ask_user`; thinking policy.
3. Fix-a-bug and small-change paths: build → code checks → debug × 2 → report.
4. Bigger-change path: tester / builder split, checkpoint per task and continue from task k, final checks with
   semgrep, review, report.
5. Direct MCP tools per role + the per-project offer; the Serena trial (asks before its first download).
6. Driven chat tests for every path; then the proof run: 5 brick-breaker tasks on Kaggle, hidden tests.
Later: deploy path with Playwright / Docker, Chrome DevTools if needed, the MCP registry in `/mcp`.
