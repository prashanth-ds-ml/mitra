# Fix log

What we changed, one entry per fix, newest first. Every fix points to the error it closes ([ERROR_LOG.md](ERROR_LOG.md))
and the test that proves it. A fix that did not work stays here marked `reverted` with the reason, so it is not tried
again.

## Index

| ID | Date | Fixes | Title | Files | Regression test | Result |
|---|---|---|---|---|---|---|
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
