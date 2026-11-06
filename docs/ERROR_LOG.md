# Error log

What went wrong: every bug, failed test, broken run and review finding, one entry each, newest first. What we changed
to fix it goes in [FIX_LOG.md](FIX_LOG.md). An entry is `closed` only when the fix is in and a regression test exists
that fails without it. Before fixing anything, search this file and [LESSONS.md](LESSONS.md) for the same symptom.

## Index

| ID | Date | Milestone | Severity | Found by | Title | Status | Fix |
|---|---|---|---|---|---|---|---|
| E-016 | 2026-11-06 | M2 | High | Claude (live UI check) | qwen3.5 replies looked frozen: langchain-ollama drops a thinking model's reasoning when `reasoning` is unset, so a plain question ran 116 s / 8.2K tokens with nothing on screen and no answer shown | closed | F-012 |
| E-015 | 2026-11-05 | M2 | High | user (terminal test) | A bare `/run` went to the model, which used `qwen3:14b` (hard-coded role default the user does not have): 404. Startup also asked for an Ollama cloud key though Mitra is local-only | closed | F-011 |
| E-014 | 2026-11-05 | M2 | High | user (terminal test) | `! mkdir snake_game` refused: "command 'mkdir' denied by policy" (default policy ends with deny `*`; `mkdir` is also a shell built-in) | closed | F-010 |
| E-013 | 2026-11-05 | M2 | Medium | new test | `env_commands` with a quoted path failed on Windows: non-POSIX split kept the quotes | closed | F-009 |
| E-012 | 2026-11-05 | M2 | High | code review | local-codex MCP client could not talk to real MCP servers (`Content-Length` framing; MCP stdio is one JSON message per line), started a process per call, had no read timeout; built-in `read_file`/`list_directory` went through it | closed | F-008 |
| E-011 | 2026-10-26 | M0 | High | live run (Aider overhead) | Bench counted lookups (`POST /api/show`) as model calls and took the first call (OpenCode's title call, 0 tools) as the work call; Codex's Responses-API requests showed 0 messages and 0 system chars | closed | F-007 |
| E-010 | 2026-10-26 | M0 | High | live run (Codex overhead) | Codex exited at once: per-run `CODEX_HOME` folder was never created | closed | F-006 |
| E-009 | 2026-10-26 | M0 | Medium | live run (second agent in a row) | Preflight blocked every run after the first: the loaded model's RAM was counted again as needed | closed | F-005 |
| E-008 | 2026-10-26 | M0 | High | live run (token count check) | Model screen long-prompt case (C09) was silently cut by Ollama: 17K-token prompt at num_ctx 16K, so the model never saw the task and the case scored as a model failure | closed | F-004 |
| E-007 | 2026-10-24 | M0 | Medium | runner test | `diff.patch` missed files the agent created (`git diff` ignores untracked files) | closed | F-003 |
| E-006 | 2026-10-24 | M0 | High | config review | In agent workspaces `python` was the system Python 3.10 without pytest/FastAPI: every agent would have failed to run tests | closed | F-002 |
| E-005 | 2026-10-24 | M0 | Medium | CI (Linux) | local-codex is Windows-only: 8 tests fail on Linux (backslash paths, PowerShell commands, skill paths) | open (fix in M1); Linux CI non-blocking | - |
| E-004 | 2026-10-24 | M0 | Medium | lint (F821) on import | Model-advisor command crashes after finishing: stray copy of brainstorm code with undefined `raw`, `llm` | closed | F-001 |
| E-003 | 2026-10-24 | review | Medium | local-codex review | Shell allowlist checks only the program name; path checks pass when no workspace is set | open (fix in M1) | - |
| E-002 | 2026-10-24 | review | Medium | local-codex review | Agent loops run `while True` with no step limit | open (fix in M1) | - |
| E-001 | 2026-10-24 | review | High | local-codex review | Repair loop stops early: `edit_file` missing from `mutating_tools` | open (fix in M1) | - |

## Entry template

```markdown
### E-0nn: <short title>

- **Date found:** YYYY-MM-DD · **Milestone:** M<n> · **Severity:** Critical | High | Medium | Low
- **Found by:** unit test | benchmark | live run | review | demo | user
- **Status:** open | fixing | closed | worked around | won't fix (reason)

**What happened:** observed vs expected; exact error text; input that triggers it.
**Root cause:** why, not just where.
**Fix:** F-nnn (see FIX_LOG.md).
**Regression test:** test name that now guards it.
**Lesson?** L-nnn added or updated, or "none (one-off)".
```

## Entries

### E-016: Thinking models showed nothing while they thought

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** Claude, live check of the new streaming UI
- **Status:** closed

**What happened:** with `qwen3.5:4b`, a 3-bullet question took 116 s and 8.2K output tokens; the thinking timer showed
0 thinking tokens and no answer text appeared.
**Root cause:** langchain-ollama 1.1.0 with `reasoning=None` does not ask Ollama to separate thinking and does not
keep it, so the reasoning was neither shown nor counted; Mitra also printed nothing for an empty reply.
**Fix:** F-012.
**Regression test:** `test_thinking_models_get_reasoning_on_so_thinking_is_not_dropped`,
`test_non_thinking_models_keep_their_default` (tests/test_llm.py).
**Lesson?** L-026.

### E-015: Unknown slash command went to the model, which used a model the user does not have

- **Date found:** 2026-11-05 · **Milestone:** M2 · **Severity:** High · **Found by:** user, first terminal test
- **Status:** closed

**What happened:** typing `/run` (no argument) fell through to the chat model; routing picked the `planner` role,
whose default model was `qwen3:14b`, not installed: `model 'qwen3:14b' not found (status code: 404)`. Startup also
prompted for an Ollama cloud API key every time.
**Root cause:** local-codex hard-coded per-role models (`qwen3:14b`, `qwen2.5-coder:14b`, `qwen2.5-coder:7b`) in
`config.py` and `agents/registry.py`; unknown slash commands had no handler; the cloud-key prompt predates D-025.
**Fix:** F-011.
**Regression test:** `test_no_role_defaults_to_a_model_the_user_may_not_have`, `test_load_exposes_default_agent_model_mapping`,
`TestSlashCommands`.
**Lesson?** L-025.

### E-014: Commands the user typed with `!` were blocked by the model's allow-list

- **Date found:** 2026-11-05 · **Milestone:** M2 · **Severity:** High · **Found by:** user, first terminal test
- **Status:** closed

**What happened:** `! mkdir snake_game` printed `Permission denied: command 'mkdir' denied by policy`.
**Root cause:** typed commands went through the same allow-list and deny-first policy as model-run commands, and
were split and started without a shell, so built-ins like `mkdir` could not run anyway.
**Fix:** F-010.
**Regression test:** `TestTypedByUser` in `tests/test_shell.py` (5 tests, incl. the model path still blocked).
**Lesson?** L-025.

### E-013: Quoted path in `env_commands` not found on Windows

- **Date found:** 2026-11-05 · **Milestone:** M2 · **Severity:** Medium · **Found by:** `test_resolve_expands_workspace_env_commands_and_env`
- **Status:** closed

**What happened:** an env command like `"C:\...\python.exe" -c "..."` failed with `FileNotFoundError`.
**Root cause:** `shlex.split(..., posix=False)` keeps the surrounding quotes in each token.
**Fix:** F-009.
**Regression test:** `test_resolve_expands_workspace_env_commands_and_env`.
**Lesson?** L-019 (portability) covers it.

### E-012: local-codex MCP client could not reach real MCP servers

- **Date found:** 2026-11-05 · **Milestone:** M2 · **Severity:** High · **Found by:** code review before connecting servers
- **Status:** closed

**What happened:** `app/mcp.py` framed messages with `Content-Length` headers (the LSP style), so it only worked with
its own `app/mcp_servers/filesystem.py`. It also started a new process for every tool call, and its blocking `readline`
had no timeout. Built-in `read_file` and `list_directory` were routed through it, so every file read started a process.
**Root cause:** hand-written protocol code, tested only against its own server.
**Fix:** F-008.
**Regression test:** `tests/test_mcp.py` (25 tests against a fake server built with the official SDK, including
timeouts), `TestReadFile.test_reads_locally_without_starting_an_mcp_server`.
**Lesson?** L-024.

### E-011: Lookups counted as model calls; title call taken as the work call; Codex requests unread

- **Date found:** 2026-10-26 · **Milestone:** M0 · **Severity:** High · **Found by:** first live overhead runs
- **Status:** closed

**What happened:** Aider's only logged call was `POST /api/show` (model info), yet it counted as a model call, so a run
that never generated would not be flagged infra. OpenCode's first call was a 588-token title request with 0 tools, which
the overhead measure reported as its prompt cost. Codex's `/v1/responses` requests use `input` and `instructions`, which
the proxy did not read.
**Root cause:** "model call" was defined as "a POST whose body parses"; the fake agent in the tests only sent `/api/chat`.
**Fix:** F-007.
**Regression test:** `test_summarize_counts_only_generation_calls`, `test_only_lookups_is_infra`,
`test_proxy_reads_responses_api_requests`.
**Lesson?** L-023.

### E-010: Codex exited at once; its per-run config folder did not exist

- **Date found:** 2026-10-26 · **Milestone:** M0 · **Severity:** High · **Found by:** first live overhead run
- **Status:** closed

**What happened:** `Error finding codex home: CODEX_HOME points to ...\home/codex, but that path does not exist`.
**Root cause:** configs point `CODEX_HOME`, `CLAUDE_CONFIG_DIR` and `XDG_*` at `{home}/...`; only `{home}` was created.
Claude Code and OpenCode create theirs, Codex does not.
**Fix:** F-006.
**Regression test:** `test_per_run_config_dirs_exist`.
**Lesson?** L-023.

### E-009: Preflight counted a loaded model's RAM twice

- **Date found:** 2026-10-26 · **Milestone:** M0 · **Severity:** Medium · **Found by:** second agent run in a row
- **Status:** closed

**What happened:** `free RAM 5.5 GB < 6.2 GB needed for qwen3.5:4b` while qwen3.5:4b was already loaded.
**Root cause:** the new RAM rule (model file + 3 GB) did not allow for the model already holding its memory.
**Fix:** F-005.
**Regression test:** `test_loaded_model_needs_only_headroom`.
**Lesson?** none (one-off).

### E-008: Model screen's long-prompt case was silently cut by Ollama

- **Date found:** 2026-10-26 · **Milestone:** M0 · **Severity:** High · **Found by:** live run (prompt tokens looked wrong)
- **Status:** closed

**What happened:** on qwen3.5:4b, C09 ("same exact edit inside a long prompt") reported 710 prompt tokens, fewer than
C04 (765), which holds a subset of its messages. The model answered `read_file` and the case scored as a model failure.
**Root cause:** the filler is ~17K tokens (the comment said ~10K; never measured) and the screen ran at `num_ctx` 16384.
Ollama drops the oldest messages to fit, with no error, so the task message was gone. The L-001 failure, inside our own
tool.
**Fix:** F-004.
**Regression test:** `test_cut_prompt_is_void_not_a_pass` (tests/test_bench_model_screen.py).
**Lesson?** L-022.

### E-005: local-codex is Windows-only

- **Date found:** 2026-10-24 · **Milestone:** M0 · **Severity:** Medium · **Found by:** first CI run on Linux · **Status:** open (fix in M1)

**What happened:** 553 passed, 8 failed on ubuntu-latest (all pass on Windows): skill bodies not found
(`Could not read skills\05-rag-pipeline\SKILL.md`), run hints mix `\` and `/`, intent routing returns Windows paths
(`tests/test_main_ux.py`, `tests/test_skills.py`).
**Root cause:** paths built and stored as Windows strings; PowerShell assumed for run commands.
**Fix:** - (M1 rewrite uses `pathlib` relative paths and POSIX-safe commands). Until then the Linux CI job is non-blocking.
**Regression test:** the Linux CI job becomes blocking again when fixed.
**Lesson?** L-019.

### E-004: Model-advisor command crashes after finishing

- **Date found:** 2026-10-24 · **Milestone:** M0 · **Severity:** Medium · **Found by:** lint (ruff F821) when importing local-codex · **Status:** closed

**What happened:** `_cmd_recommend` in `app/main.py` ended with 7 lines copied from the start of `_cmd_brainstorm`
(`topic = raw.strip()[11:]...`). They ran after every advisor run and raised `NameError: raw`. No test covered the command.
**Root cause:** a paste left in the wrong function; the original repo had no lint gate for undefined names.
**Fix:** F-001.
**Regression test:** CI lint gate `ruff check` with F82 (undefined names) fails without the fix.
**Lesson?** L-018 (lint gate for undefined names from day 1).

### E-003: Shell allowlist checks only the program name; path checks pass when no workspace is set

- **Date found:** 2026-10-24 · **Milestone:** review · **Severity:** Medium · **Found by:** local-codex review · **Status:** open (fix in M1)

**What happened:** `shell.py:407` allows a command if `pathlib.Path(parts[0]).name` is on the list; `python`, `pip`,
`node` and `npx` are on it, so `python -c "<anything>"` passes. `shell.py:207` and `filesystem.py:96` skip the path check
when no workspace is set.
**Root cause:** allowlist designed for convenience, not containment; fail-open default.
**Fix:** -
**Regression test:** -
**Lesson?** L-014

### E-002: Agent loops run `while True` with no step limit

- **Date found:** 2026-10-24 · **Milestone:** review · **Severity:** Medium · **Found by:** local-codex review · **Status:** open (fix in M1)

**What happened:** `filesystem.py:958`, `shell.py:645`, `reader.py:456`, `web.py:244` loop until the model stops calling
tools. A small model that repeats a call never stops.
**Root cause:** loops written for models that end on their own.
**Fix:** -
**Regression test:** -
**Lesson?** L-013

### E-001: Repair loop stops early: `edit_file` missing from `mutating_tools`

- **Date found:** 2026-10-24 · **Milestone:** review · **Severity:** High · **Found by:** local-codex review · **Status:** open (fix in M1)

**What happened:** `app/langgraph_workflows.py:55` lists `create_file`, `move_file`, `delete_file`, `delete_folder`,
`create_folder` but not `edit_file`. A repair that only edits files counts as "no code changes", so the loop stops.
**Root cause:** set maintained by hand; tests (`tests/test_langgraph_workflows.py:34,106`) only use `create_file`.
**Fix:** -
**Regression test:** -
**Lesson?** L-012
