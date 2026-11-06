# Fix log

What we changed, one entry per fix, newest first. Every fix points to the error it closes ([ERROR_LOG.md](ERROR_LOG.md))
and the test that proves it. A fix that did not work stays here marked `reverted` with the reason, so it is not tried
again.

## Index

| ID | Date | Fixes | Title | Files | Regression test | Result |
|---|---|---|---|---|---|---|
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
