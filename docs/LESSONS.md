# Lessons

Rules learned the hard way, so the same mistake is not made twice. Read the relevant ones before starting work.
Each lesson links the error that taught it. Seeded from Research Desk (project 04, `R-E-nnn` = its ERROR_LOG), the
local-codex review and this project's planning. Add a lesson whenever an error could happen again somewhere else.

| ID | Area | Rule | Learned from |
|---|---|---|---|
| L-001 | Ollama | Set the context length explicitly (`OLLAMA_CONTEXT_LENGTH`); the 4K default drops the start of long prompts with no error. Log prompt tokens on every call | Research for 05 (agents breaking on local models) |
| L-002 | Ollama | A dead or unreachable model must fail loudly. Empty output is an error, never a pass | R-E-005 |
| L-003 | Timeouts | Every model call and subprocess gets a timeout; stream with a runaway guard | Project 04 1.5 h hang |
| L-004 | State | No per-run state in module globals; pass a run object | R-E-004; local-codex `_config`, `_guard`, `_active_change_set` |
| L-005 | Small models | Cap thinking and test with thinking on and off; thinking at temperature 0 may never finish | R-E-014, R-E-021 |
| L-006 | Small models | Prefer scoring or ranking to yes/no judgments; small models reject almost everything on yes/no | R-E-015 |
| L-007 | Ollama | Batch requests; one huge request (hundreds of embeddings) can crash the runner | R-E-018 |
| L-008 | Machine | Ollama maps ~8 GB of RAM on Windows; check free RAM >= 11-12 GB, one model loaded at a time | R-E-022 |
| L-009 | Env | After installing into the shared venv run `uv pip check`; mismatched package pairs break startup | R-E-016 |
| L-010 | Release | Test a fresh clone before every release; check ignore rules with `git check-ignore -v` | Research Desk v0.3 (a hidden ignore rule kept a whole page out of git) |
| L-011 | Paths | Create a directory before `cd`/clone into it and verify where files landed; a failed `cd` put a clone in the wrong project | 05 planning session, 2026-10-24 |
| L-012 | Tests | Test every member of a set, not one example: `edit_file` was missing from `mutating_tools` and tests only used `create_file` | local-codex `app/langgraph_workflows.py:55` |
| L-013 | Loops | Every agent loop has a step limit and a repeat-call guard | local-codex `while True` loops (`filesystem.py:958` and others) |
| L-014 | Safety | Checking only the program name allows anything (`python -c ...`); path checks must fail closed when no workspace is set | local-codex `shell.py:407`, `shell.py:207` |
| L-015 | LangGraph | Cancelling a run does not stop a running sync node; use a cooperative stop flag | Project 04 close-out |
| L-016 | Planning | An idea is not a decision. New ideas go to "Ideas to test"; never record one as agreed without the user saying so | 05 planning, D-008 |
| L-017 | Tooling | Long nested heredocs fail in the Bash tool; use Write/Edit. Never print `.env` unfiltered | Project 04 |
| L-018 | Lint | Gate CI on syntax errors and undefined names (`ruff` E9/F63/F7/F82) from day 1; it finds crashes no test covers | E-004 |
| L-019 | Portability | Build paths with `pathlib`, store them relative with `/`, never assume PowerShell; run CI on Linux and Windows from the first commit | E-005 |

## Template
`| L-0nn | <area> | <the rule, one or two lines, written as an instruction> | <E-nnn / F-nnn / source> |`
