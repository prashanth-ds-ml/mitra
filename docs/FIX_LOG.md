# Fix log

What we changed, one entry per fix, newest first. Every fix points to the error it closes ([ERROR_LOG.md](ERROR_LOG.md))
and the test that proves it. A fix that did not work stays here marked `reverted` with the reason, so it is not tried
again.

## Index

| ID | Date | Fixes | Title | Files | Regression test | Result |
|---|---|---|---|---|---|---|
| F-047 | 2026-11-08 | E-047 | (a) `/mode` only for `/mode` or `/mode …`; (b) connection errors (10054/10061, reset, refused) → wait up to 90 s for Ollama, retry the step once, friendly hints otherwise; (c) `test_summary` finds pytest's result line; (d) `reserve_space_for_menu=0` | `app/main.py`, `app/core/chat.py`, `app/core/tools.py`, `app/ui/input.py` | `tests/test_e047_night.py` | works |
| F-046 | 2026-11-07 | E-046 | `config.compact_threshold`: 80% of num_ctx by default (`auto_compact_threshold = 0`), a number in mitra.toml only caps it lower; `/context 128k|256k|auto` changes the size live (new LLM, threshold, memory-fit line) and is kept per model in `~/.mitra/context.json`; `context_for_model` reads it first; mitra.toml `num_ctx` still wins. Known cost: compaction re-reads the whole history as a new prompt, now up to ~205K on the 256K 9B (measured in I-7 step M) | `app/config.py`, `app/main.py` | `tests/test_context_choice.py` (5) | works |
| F-044 | 2026-11-07 | E-044 | `ChatSession._turn` catches Ollama's tool-call parse error, records `bad_tool_call`, shows a `Retry` line and tells the model nothing was run and to write in parts (write_file ~100 lines, then edit_file to add the rest); at most 2 per turn, other errors still raise | `app/core/chat.py` | `tests/test_chat_bad_tool_call.py` (4) | works |
| F-043 | 2026-11-07 | E-043 | `app/fit.py`: RAM need from Ollama's `/api/ps` (already loaded), else the measured table (EVALS 2026-11-07), else an estimate; other loaded models count as freed; verdict ok (>= 3 GB left) / tight / no; when not ok, the biggest programs grouped by name (system, Ollama and Mitra's own terminal never listed; python/node split by what they run) plus a smaller model or half the context. One line under the startup header (never blocks) and a Memory fit section in `/doctor` | `app/fit.py`, `app/main.py` | `tests/test_fit.py` (15) | works |
| F-042 | 2026-11-06 | E-042 | `ChatSession.turn` writes `turn_end` with `interrupted=True` on any exception, then re-raises; the analyzer adds an `interrupted` pattern and counts old turns with a start and no end (except a file's last turn) | `app/core/chat.py`, `app/core/analyze.py` | `test_chat_records_a_turn_that_is_interrupted`, `test_interrupted_turns_are_counted_with_or_without_an_end_record` | works |
| F-041 | 2026-11-06 | E-041 | `ShellResult.still_running` (timed out, no traceback/error in the output): the model is told `[STILL RUNNING] ... not a crash, tell the user the command`, it does not count as a failure for the guard, and the screen shows `still running after Ns, no errors` | `app/agents/shell.py`, `app/main.py`, `app/ui/render.py` | `test_a_program_still_running_at_the_timeout_is_not_a_failure` | works |
| F-040 | 2026-11-06 | E-040 | Operators are looked for only outside quotes (`_mask_quotes`, same length, so split positions map back); pipe/redirect refusal uses the same check | `app/agents/shell.py` | `test_separators_inside_quotes_are_part_of_the_argument` | works |
| F-039 | 2026-11-06 | E-039 | Every `subprocess.run` in app/ has a timeout (git 60 s, venv 300 s, pip install 900 s); the main.py git helpers treat a timeout as no repo / no output | `app/agents/filesystem.py`, `app/main.py` | `test_every_subprocess_call_in_app_has_a_timeout`, `test_git_helpers_survive_a_hung_git` | works |
| F-038 | 2026-11-06 | E-038 | Tool texts capped at 300 chars (`MAX_TOOL_CHARS`); CI checks the worst-case harness against the budget | `app/core/harness.py`, `tests/test_prompt_budget.py` | `test_a_full_harness_stays_under_budget` | works |
| F-037 | 2026-11-06 | E-037 | `mitra solve --max-steps` defaults to 0 = the harness setting; `run_plan` defaults to None | `app/main.py`, `app/core/cli.py`, `app/core/loop.py` | `test_solve_uses_the_harness_step_limit_when_none_is_given` | works |
| F-036 | 2026-11-06 | E-036 | (a) `analyze(files, harness_version=)`: improve looks only at records made with the current version; benchmark records are included and the candidate's carry the next version; (b) a model error stops the A/B as `bench_error`; (c) proposer unloaded after proposing (`keep_alive 0`), free-RAM check for the biggest model (`--force` to skip); (d) one limit `MAX_TOOL_CHARS` for parse and save; (e) record paths deduped, pytest via run_command is a test run, examples name the project | `app/core/analyze.py`, `app/core/improve.py`, `app/core/dashboard.py`, `app/main.py` | `tests/test_analyze.py`, `tests/test_improve.py` (8 new) | works |
| F-035 | 2026-11-06 | E-035 | `bench.grade(..., python=)` grades with the Python the workspace's tests use (`project_python`); an infra error in grading stops the A/B as `bench_error` and changes nothing | `bench/bench.py`, `app/core/improve.py` | `test_a_broken_grader_stops_the_ab_and_changes_nothing` | works |
| F-034 | 2026-11-06 | E-034 | A module loaded with `importlib.util` is registered in `sys.modules` before it runs (dataclasses look their module up there); unit tests had replaced the bench with a stub, so only the live run caught it | `app/core/improve.py` | `test_the_real_bench_loads_and_has_a_tune_half` | works |
| F-033 | 2026-11-06 | E-033 | `cd X && cmd` / `;` chains run part by part (cd only inside the workspace), `/c/...` paths converted, pipes/redirects refused with a reason; repeat guard: shell commands are repeats unless a file changed, failures counted by the real result; failed commands show their last output line | `app/agents/shell.py`, `app/agents/limits.py`, `app/ui/render.py`, core loop + chat | `tests/test_shell_chains.py` | works |
| F-032 | 2026-11-06 | E-032 | `_model_command_args`: a model command's `python` is `project_python()` | `app/agents/shell.py` | `test_model_python_command_uses_the_projects_python` | works |
| F-031 | 2026-11-06 | E-031 | Inline code is never covered by trust (always asks); new `make_dir` tool | `app/main.py`, `app/core/tools.py` | `test_inline_code_asks_even_when_the_program_is_trusted` | works |
| F-030 | 2026-11-06 | E-030 | New files as a card (header, syntax colours, line numbers, 20 lines + honest fold), edits as numbered hunks with 2 lines of context, one result line after approval; Yes / Yes to all / No with a reason | `app/ui/files.py`, `app/core/chat.py`, `app/main.py` | `tests/test_display_fixes.py` | works |
| F-029 | 2026-11-06 | E-029 | health_check skips the reinstall while `mitra.exe` is running; repair = `uv pip install --python <tool python> -e .` | `scripts/health_check.py` | live check passed after repair | works |
| F-028 | 2026-11-06 | E-028 | `project_python()`: the project's .venv, then `python` on PATH if it has pytest, then Mitra's own Python (pytest added to Mitra's dependencies) | `app/core/tools.py`, `pyproject.toml` | `test_tests_run_with_the_projects_python` | works |
| F-027 | 2026-11-06 | E-027 | `/commit` refuses when nothing is staged and runs plain `git commit -m` (no `git add -A`, no push) with timeouts; the drafted message comes from `git diff --cached`; a cancelled menu or empty typed message does not commit | `app/main.py` (`_cmd_commit`, `_generate_commit_message`) | `tests/test_commit_command.py` | works |
| F-026 | 2026-11-06 | E-026 | `RepeatGuard`: `run_tests` and `run_command` are never repeats; any successful write clears the repeat memory | `app/agents/limits.py` | `test_repeat_guard_allows_rerunning_tests_and_rereading_after_an_edit` | works |
| F-025 | 2026-11-06 | E-025 | `ctx_used` = prompt tokens of the latest model call; status line shows it against num_ctx; auto-compact, `/status`, `/context` and `/compact` use it | `app/main.py` | `test_context_use_is_the_latest_prompt_not_the_sum_of_calls` | works |
| F-024 | 2026-11-06 | E-024 | `search_sources.py`: Wikipedia, Hugging Face, GitHub, arXiv and the Ollama library in parallel (no key), DuckDuckGo first and skipped after one failure, short-name fallback; `fetch_url` reads the README of Hugging Face and GitHub pages; a stopped search makes one final no-tools call for the answer; failed calls add a note instead of replacing the answer | `app/agents/search_sources.py`, `app/agents/web.py` | `tests/test_web_search.py` | works |
| F-023 | 2026-11-06 | E-023 | `RepeatGuard` in the web, reader and file agents: an identical call is not rerun (the model is told the result will not change); the agent stops after 3 refused repeats or 3 failures of one tool in a row and says why ("may be offline" for search) | `app/agents/limits.py`, `web.py`, `reader.py`, `filesystem.py` | `test_web_agent_stops_when_search_keeps_failing` | works |
| F-022 | 2026-11-06 | E-005 | Skill paths stored as posix and read from either form; one PowerShell path style in run hints (`_ps_path`); status-line folder from either path style; native paths for file actions; Linux CI blocking | `app/skills.py`, `app/main.py`, `app/ui/status.py`, CI | Linux CI + `tests/test_review_fixes.py` | works |
| F-021 | 2026-11-06 | E-022 | `IntentRouter._lead_intent`: the first verb after polite openers decides (fix, plan, test, review, refactor, document); test keywords match whole words | `app/routing.py` | `test_leading_verb_routes_the_request` | works |
| F-020 | 2026-11-06 | E-021 | `_split_command` strips one pair of outer quotes per argument on Windows | `app/agents/shell.py` | `test_split_command_strips_outer_quotes_on_windows` | works |
| F-019 | 2026-11-06 | E-003 | File and shell path checks refuse when no workspace is set; inline code from the model (`-c`, `-e`, `-Command`) runs only after approval | `app/agents/filesystem.py`, `app/agents/shell.py` | `tests/test_review_fixes.py` | works |
| F-018 | 2026-11-06 | E-002 | File, reader, web and shell agent loops stop after 20 model calls with a clear message | `app/agents/limits.py` + 4 agents | `tests/test_review_fixes.py` | works |
| F-017 | 2026-11-06 | E-001 | `edit_file` and the markdown writers count as code changes in the repair loop | `app/langgraph_workflows.py` | `test_edit_file_counts_as_a_code_change` | works |
| F-016 | 2026-11-06 | E-020 | `execute_plan` prints `● Plan` and its result; an empty follow-up prints "Empty reply" plus the tool's result; every mention of a removed command reworded | `app/main.py`, `app/memory.py`, `app/agents/planner.py`, `app/agents/session.py` | `test_no_text_mentions_removed_commands` | works |
| F-015 | 2026-11-06 | E-019 | Questions route to explain; "no coding" / "just brainstorm" route to brainstorm (nothing written); router matches "plan" as a whole word; a relative path starting with the workspace's folder name is not nested | `app/main.py`, `app/routing.py`, `app/agents/filesystem.py` | `TestQuestionsAreAnswered`, `TestWorkspaceNameIsNotNested` | works |
| F-014 | 2026-11-06 | E-018 | `coerce_tool_args` writes object/list `content` as formatted JSON; `safe_invoke` turns any tool exception into a `✗ Invalid call to <tool>: ...` result the model can correct; used by the file, reader and web agents | `app/agents/filesystem.py`, `app/agents/reader.py`, `app/agents/web.py` | `TestBadToolArguments` | works |
| F-013 | 2026-11-06 | E-017 | Startup = header box only (remembered model, loaded items in the header); command replies as plain markdown; approvals as an inline arrow-key menu with a coloured diff; framed input | `app/main.py`, `app/ui/menu.py`, `app/ui/header.py`, `app/ui/status.py`, `app/config.py` | `tests/test_ui.py` (8 new) | works |
| F-012 | 2026-11-06 | E-016 | `get_local_llm(reasoning="auto")` turns thinking on for models with the `thinking` capability; an empty reply prints an error line | `app/llm.py`, `app/main.py` | `test_thinking_models_get_reasoning_on_so_thinking_is_not_dropped` | works |
| F-011 | 2026-11-05 | E-015 | Role models default to the picked model; unknown slash commands answered locally; no cloud-key prompt | `app/config.py`, `app/agents/registry.py`, `app/main.py` | `test_no_role_defaults_to_a_model_the_user_may_not_have` | works |
| F-010 | 2026-11-05 | E-014 | `execute(typed_by_user=True)`: user's shell (PowerShell / sh), no allow-list, policy or confirm; still workspace-only with a timeout | `app/agents/shell.py`, `app/main.py` | `TestTypedByUser` | works |
| F-009 | 2026-11-05 | E-013 | Strip quotes from tokens after the Windows split | `app/mcp.py` | `test_resolve_expands_workspace_env_commands_and_env` | works |
| F-008 | 2026-11-05 | E-012 | New MCP client on the official SDK (stdio + HTTP, long-lived sessions, timeouts, approvals, masking, trimming, call log); built-in file tools read locally; custom server removed | `app/mcp.py`, `app/agents/filesystem.py`, `app/main.py`, `app/config.py` | `tests/test_mcp.py` | works |
| F-007 | 2026-10-26 | E-011 | Count only generation endpoints; overhead = first call with tools (`sends_tools = false` for Aider); proxy reads Responses API | `bench/run.py`, `bench/proxy.py`, `bench/configs/aider.toml` | `test_summarize_counts_only_generation_calls` + 2 | works |
| F-006 | 2026-10-26 | E-010 | Create every `{home}/...` folder named in an agent config before launch | `bench/run.py` | `test_per_run_config_dirs_exist` | works |
| F-005 | 2026-10-26 | E-009 | A loaded model needs only the 3 GB headroom | `bench/preflight.py` | `test_loaded_model_needs_only_headroom` | works |
| F-004 | 2026-10-26 | E-008 | Screen at 32K context; a case with too few prompt tokens is void, not a model failure | `bench/model_screen.py` | `test_cut_prompt_is_void_not_a_pass` | works (C09 now 18,069 tokens, passes on both models) |
| F-001 | 2026-10-24 | E-004 | Remove stray brainstorm code from `_cmd_recommend` | `app/main.py` | CI lint gate (F82) | works |
| F-002 | 2026-10-24 | E-006 | Bench Python first on the agent PATH | `bench/run.py` | `test_agent_python_is_the_grader_python` | works |
| F-003 | 2026-10-24 | E-007 | Stage all files before diffing against the start commit | `bench/run.py` | `test_agent_python_is_the_grader_python` (checks a created file appears) | works |

## Entry template

```markdown
### F-0nn: <short title>

- **Date:** YYYY-MM-DD · **Fixes:** E-nnn · **Milestone:** M<n> · **Commit:** <sha>
- **Result:** works | partial | reverted (reason)

**Change:** what changed and why this approach.
**Files:** `path:line`, ...
**Regression test:** test name; fails before the fix, passes after (say how this was checked).
**Tried and rejected:** other fixes attempted and why they failed (so nobody tries them again).
**Lesson:** L-nnn added or updated, or "none".
```

## Entries

### F-027: `/commit` commits staged changes only (E-027)

- **Date:** 2026-11-06 · **Fixes:** E-026 · **Milestone:** M2
- **Result:** works

**Change:** `_cmd_commit` checks `git diff --cached --quiet` first and refuses with a hint when nothing is staged, then
runs `git commit -m <message>` itself (120 s timeout) instead of the `git_commit` tool, which stages everything.
`_generate_commit_message` reads `git diff --cached` directly (30 s timeout), so an empty diff means no draft. Only
"Yes" uses the draft; "type my own" with an empty message, or a cancelled menu, commits nothing. The `git_commit` tool
itself is unchanged (the agents rely on it).
**Files:** `app/main.py` (`_cmd_commit`, `_generate_commit_message`)
**Regression test:** `tests/test_commit_command.py` (9 tests, real git in a temp repo, every subprocess command
recorded); 7 failed before the fix, all pass after.
**Tried and rejected:** none.
**Lesson:** L-034.

### F-016: No silent turns; no removed commands in replies (E-020)
**Change:** the plan tool shows a tool line and the first part of its result; when the model writes nothing after a
tool, Mitra prints "Empty reply" and the tool's own result. Replies that named `/plan`, `/next`, `/hibernate`,
`/search`, `/understand`, `/prd`, `/brainstorm` now say what to ask Mitra instead.
**Test:** a scan of `app/` for removed commands in backticks (found 11 before the fix), and the unapproved-plan reply.

### F-015: Questions get answers; no nested project copies (E-019)
**Change:** `_classify_intent` checks, before any build or plan route: `_forbids_changes` ("no coding", "no
implementation", "just brainstorm", ...) -> brainstorm; `_is_question` (ends with "?" or starts with what/why/how/is/
status/..., but not "can you"/"please") -> explain. `IntentRouter._is_plan_request` uses whole words. `_resolve_path`
drops a first path part equal to the workspace folder name when no such subfolder exists.
**Test:** the user's real messages from the trace are test cases (2 questions, 2 "no coding" requests); path tests for
the nested case and for a real same-named subfolder.

### F-014: Tool errors go back to the model (E-018)
**Change:** `coerce_tool_args` fixes the common shape mistake (JSON content sent as an object is written as indented
JSON). `safe_invoke` wraps every tool call in the file, reader and web agents: a validation error or a crash becomes a
tool result starting with `✗ Invalid call to <tool>`, with the first lines of the error and "call it again", so the
loop continues and the model can retry.
**Test:** `TestBadToolArguments` (3): dict content written as JSON, wrong argument type returned as an error, a raising
tool returned as an error. All 3 fail with the old code.

### F-013: One interface, matching the mock (E-017)
**Change:** startup goes straight to the header box: the model comes from `mitra.toml`, else the last one used
(`~/.mitra/last_model`), else qwen3.5:4b; the picker appears only if none is installed. What was loaded (instruction
files, memory, plan) is one row in the header. The Session Snapshot box, the GPU line and the API-key note are gone.
17 boxed command replies are now plain markdown (`_say`). `radiolist_dialog` is replaced by `ui.menu.choose`: a tool
line, the detail with a coloured diff, the question, then an inline arrow-key menu (number keys work too; esc
cancels). The input has a rule above and below it, then the status line. `/model use <name>` sets the next start's
model.
Second pass the same day: the remaining boxes went too (14 more command replies, the error box, the compact summary, `/help`, the commit-message helper, and the agents' own panels: reviewer, web, session, reader, file and shell results, the planner's step boxes). The plan keeps one accent box, as in the mock.
**Test:** 8 tests in `tests/test_ui.py`; the real menu driven with simulated keys (down, down, up, enter -> 2nd
option; "3" -> 3rd; enter -> default).

### F-012: Thinking is captured and shown (E-016)
**Change:** `get_local_llm` asks Ollama `/api/show` for the model's capabilities and passes `reasoning=True` to
thinking models, so reasoning arrives in `reasoning_content` and the thinking line counts it. Models without the
capability keep their default (Ollama rejects `think` for them). An empty answer now prints "Empty reply" instead of
nothing.
**Test:** 2 tests in `tests/test_llm.py`. Live: same question, `qwen3.5:4b`: "Thought for 32s · 2.0K tokens", then the
answer streamed (was 116 s, nothing shown).

### F-011: No hard-coded models (E-015)
**Change:** every role in `agent_models` defaults to empty, which resolves to the model picked at startup; `mitra.toml`
can still set one per role. Unknown slash commands print "Unknown command" instead of reaching the model. The startup
cloud-key prompt is gone (a key in config still works).
**Test:** `test_no_role_defaults_to_a_model_the_user_may_not_have`; 3 tests that pinned `qwen3:14b` updated.

### F-010: Typed commands run in the user's shell (E-014)
**Change:** `shell.execute(..., typed_by_user=True)` from `! <command>`: runs through PowerShell (Windows) or `$SHELL`
without the allow-list, policy, mode or confirm step, still only inside the workspace and under the timeout.
Model-run commands are unchanged.
**Test:** `TestTypedByUser` (5). A first attempt edited the matching lines in `start_background` instead of `execute`
(the same code appears twice); the tests caught it before commit (L-025).

### F-009: Windows quotes in env commands (E-013)
**Change:** after `shlex.split(posix=False)`, remove one pair of matching quotes around a token.
**Test:** `test_resolve_expands_workspace_env_commands_and_env` failed before (FileNotFoundError), passes after.
**Tried and rejected:** `posix=True` on Windows (breaks backslashes in paths).

### F-008: MCP client rewritten on the official SDK (E-012)
**Change:** `app/mcp.py` rewritten on `mcp` 2.3.0: standard `mcpServers` config (defaults, `~/.mitra/mcp.json`,
project `.mitra/mcp.json` behind `/mcp trust`), one long-lived session per server in a background loop, timeouts on
start and on every call, `allow`/`ask` patterns (write tools refused without approval), secrets masked in results and
logs, results over 6,000 characters trimmed with the full text saved. The model gets two tools, `mcp_find` and
`mcp_call`. `read_file` and `list_directory` no longer go through MCP. `app/mcp_servers/` and the `mcp_servers` key in
`mitra.toml` are gone.
**Test:** `tests/test_mcp.py` (25), new `TestMcpTools` in `tests/test_filesystem.py`. Full suite: 640 passed.
**Tried and rejected:** `langchain-mcp-adapters` (would put every server's full tool list in the prompt; we want our
own short descriptions and the 2-tool interface). Not measured yet: real servers (see STATUS).

### F-004: Long-prompt case checks that its prompt arrived whole

- **Date:** 2026-10-26 · **Fixes:** E-008 · **Milestone:** M0 · **Result:** works

**Change:** `SCREEN_CTX` 16384 → 32768; `Case.min_prompt_tokens` (C09: 10,000). If Ollama reports fewer prompt tokens,
the case is recorded as `infra: prompt cut ...` and counted in `void_cases`, never as a pass or a model failure.
**Files:** `bench/model_screen.py`
**Regression test:** `test_cut_prompt_is_void_not_a_pass`: a right answer with 710 prompt tokens must be void (fails
before the fix: it scored as a pass). Live: C09 now 18,069 prompt tokens and passes on qwen3.5:4b and qwen3.5:9b.
**Tried and rejected:** none.
**Lesson:** L-022.

### F-001: Remove stray brainstorm code from `_cmd_recommend`

- **Date:** 2026-10-24 · **Fixes:** E-004 · **Milestone:** M0 · **Result:** works

**Change:** deleted the 7 unreachable-intent lines after the advisor's apply/skip branch; `_cmd_brainstorm` (the real
copy) is unchanged.
**Files:** `app/main.py` (end of `_cmd_recommend`)
**Regression test:** `ruff check .` with rules E9/F63/F7/F82 in `pyproject.toml`, run in CI; it reported F821 before the
fix and passes after. Full suite: 561 passed.
**Tried and rejected:** none.
**Lesson:** L-018.
