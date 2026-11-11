# Fix log

What we changed, one entry per fix, newest first. Every fix points to the error it closes ([ERROR_LOG.md](ERROR_LOG.md))
and the test that proves it. A fix that did not work stays here marked `reverted` with the reason, so it is not tried
again.

## Index

| ID | Date | Fixes | Title | Files | Regression test | Result |
|---|---|---|---|---|---|---|
| F-090 | 2026-11-11 | E-097 | A block taller than the screen is printed for good as it grows (only the line being written stays live; a cut code fence is closed and reopened); a footer under the live part while Mitra works: working Ns · live tok/s · CPU · RAM free · GPU · esc to stop. The full Claude Code-style screen is parked as I-26 | `app/ui/stream.py`, `app/ui/sysmon.py`, `app/main.py` | `tests/test_stream_overflow.py::test_while_it_is_written_the_top_of_a_long_list_is_already_on_screen_for_good` (fails without the fix) + 6 more | works |
| F-089 | 2026-11-11 | E-096 | `intent.terminal_command`: `mitra <command> ...` typed in the chat gets a hint (run it in another terminal; for score: --remote = Kaggle, plain = laptop), no model call, recorded as path cli_hint | `app/core/intent.py`, `app/main.py` | `tests/test_live_20261111.py` (2 tests) | works |
| F-088 | 2026-11-11 | E-095 | A record in the system temp folder is never mirrored to the store (unless Mitra's home is itself there, as in tests); the hung-thread test joins its threads; the 10 polluting folders were moved to ~/.mitra/data/dev-runs (not deleted) | `app/core/store.py`, `tests/test_step3_score.py` | `tests/test_live_20261111.py::test_a_workspace_in_the_temp_folder_is_never_mirrored_to_your_store` | works |
| F-087 | 2026-11-11 | E-094 | The analyzer skips plan_first / resume_brief turns and esc stops for empty_answer | `app/core/analyze.py` | `tests/test_live_20261111.py::test_planned_and_resume_turns_are_not_empty_answers` | works |
| F-086 | 2026-11-11 | E-093 | `intent.py`: FOLLOW_UP keeps the working kind (small → small, question → question); FAILING → small; HOW_TO → question/general; NEED ("i need a script") is a change; run / commit / rename / delete / move / revert / install / push alone are small; documents (prd, spec, blog, paragraph ...) are writing; an app / tool / bot is code, not writing | `app/core/intent.py` | `tests/test_live_20261111.py::test_the_sweep_of_everyday_follow_ups_is_sorted_right` + 8 cases in score/sorting.toml | works |
| F-085 | 2026-11-11 | E-092 | `roles.thinking_for`: your explicit mitra.toml `thinking` on/off wins for every role; otherwise the table | `app/core/roles.py`, `app/main.py` | `tests/test_live_20261111.py::test_your_mitra_toml_thinking_wins_over_the_role_table` | works |
| F-084 | 2026-11-11 | E-091 | The reply and explain paths send your notes again only when they changed since the start | `app/main.py` (`_fresh_notes`) | `tests/test_step1_everyday.py` (end to end: the mail prompt still has your signature) | works |
| F-083 | 2026-11-11 | E-087 | A ChatSession can be cancelled: it stops before its next model call or tool and makes no wrap-up call; a score case that times out cancels its session | `app/core/chat.py`, `app/core/score.py` | `tests/test_step3_score.py::test_a_timed_out_turn_stops_before_its_next_tool` | works |
| F-082 | 2026-11-11 | E-083..E-086, E-088..E-090 | By the code review (--fix): /plan never gets the discussion; the discussion rule steps aside for "please / can you / and / then + change verb"; the plan/readme rule needs exactly one change verb; PROJECT_WORDS gain defined / implemented / stored / handled / configured ...; a bare no/nope is not a rephrase; cited_files strips only a leading ./ and checks root paths directly; with_discussion skips Mitra's own notes | `app/main.py`, `app/core/intent.py`, `signals.py`, `chat.py`, `planner.py` | `tests/test_live_20261111.py` + score/sorting.toml (54 cases) | works |
| F-081 | 2026-11-11 | E-082 | `mitra score` uses this machine's Ollama and context (the settings config.load kept in `_local`) unless --remote | `app/main.py` | `tests/test_step3_score.py::test_the_score_runs_on_the_laptop_while_kaggle_is_active_unless_remote` | works |
| F-080 | 2026-11-11 | E-081 | Every score case runs under a time limit (writing 5 min, explain/ideas 10, small 30, medium 45); a case that times out or crashes fails with the reason and the run goes on | `app/core/score.py` | `tests/test_step3_score.py::test_a_hung_model_fails_its_case_and_the_run_goes_on` | works |
| F-079 | 2026-11-11 | E-080 | `handoff.night_for_report`: only a night still running or started in this Kaggle session; a finished one shows no minutes | `app/core/handoff.py`, `app/main.py` | `tests/test_live_20261111.py::test_the_kaggle_report_names_only_a_night_from_this_session` | works |
| F-078 | 2026-11-11 | E-079 | The planner streams its answer (bytes flow while it writes), still inside its timeout | `app/core/planner.py` | `tests/test_live_20261111.py::test_the_planner_streams_so_the_tunnel_never_waits_120_s_for_a_first_byte` | works (live re-check on Kaggle: user) |
| F-077 | 2026-11-11 | E-078 | `intent.py`: brainstorm / discuss / think through / thoughts on, and musings ("i feel", "once we", "what if") after a discussion → talked through (general; question if it names the code), unless it says build it / go ahead; "ok lets build it" after a discussion → plan first, and the planner gets the discussion (`planner.with_discussion`: your last 4 messages + Mitra's last answer) | `app/core/intent.py`, `app/core/planner.py`, `app/main.py` | `tests/test_live_20261111.py` (5 tests) + 4 sorting cases in score/sorting.toml | works |
| F-076 | 2026-11-11 | E-077 | `results`/`history` default to None and read RESULTS at call time | `app/core/score.py` | `tests/test_step3_score.py::test_mitra_score_command_sorting_and_history` | works |
| F-075 | 2026-11-11 | E-076 | A mail to a person ("to my manager", "to the team", ...) is writing even if a code word appears; "a reply endpoint" (noun + code word) stays code | `app/core/intent.py` | score/sorting.toml (2 cases) | works |
| F-074 | 2026-11-10 | E-075 | `intent.py`: ideas that name the project → question (explainer), otherwise general; edits to the plan/README/notes → small (edited in place) unless they also say build/implement; picking an option after a question ("go with option 2", "the first idea") → small; a follow-up that points back ("what is option 2 exactly?") stays a question. The explainer's note covers reviews (good / risky / change) and ideas (3-5 options with trade-offs, then a pick) | `app/core/intent.py`, `app/core/chat.py` | `tests/test_step2_explain.py::test_ideas_reviews_and_plan_edits_about_the_project_are_sorted_right` | works (live: brainstorm + review answered, nothing changed; quality uneven: 8 ideas not 3-5, one wrong review point → step 3 measures) |
| F-073 | 2026-11-10 | E-074 | `cited_files` takes any file name in the answer that exists in the project (with or without :line; one walk of the tree, skipping .git/.venv/node_modules); `line_refs` records whether it gave lines | `app/core/chat.py` | `tests/test_step2_explain.py::test_cited_files_keeps_only_files_that_exist` | works (live re-run: 4 files cited) |
| F-072 | 2026-11-10 | E-073 | `files_read` counts only the messages of this turn | `app/core/chat.py` | `tests/test_step2_explain.py::test_a_follow_up_records_only_its_own_reads` | works |
| F-071 | 2026-11-10 | E-071 | The writing instruction says: drafting FOR the user, as the user, never sign as Mitra; the signature copied exactly from the notes; only facts the user gave, [placeholder] for the rest. Live re-run: signed as Prashanth, nothing invented, mail 7.4 s → 3.1 s (shorter) | `app/core/chat.py` (REPLY_NOTES) | live re-run (scratchpad live_step1.py); the step 3 writing checks will measure it on every run | works (still "Thanks," for "Regards,") |
| F-070 | 2026-11-10 | E-070 | `utf-16-le` (no mark); short ASCII and Hindi text read back exactly | `app/ui/clipboard.py` | `tests/test_step1_everyday.py::test_clipboard_sends_utf16_without_a_byte_order_mark` | works |
| F-069 | 2026-11-10 | E-069 | `note_request` merges the path's extra fields into the turn_end row instead of passing them twice | `app/core/chat.py` | `tests/test_step0_records.py::test_a_planner_error_reason_does_not_clash_with_the_record_fields`; `tests/test_backend_chat.py::test_switching_between_kaggle_and_the_laptop` | works (800 passed) |
| F-068 | 2026-11-10 | E-068 | `memcompression` added to `fit._NEVER`; live list on the user's machine no longer shows it | `app/fit.py` | `tests/test_free.py::test_windows_memory_compression_is_never_offered` | works |
| F-067 | 2026-11-10 | E-067 | `remote.check_alive` at chat and `mitra solve` start: a remote that does not answer is not used (settings restored to this machine) with a plain message; a dead Kaggle address is forgotten (new URL every session), another remote stays set. Live: the user's dead Kaggle remote → local Ollama, 5 models listed | `app/remote.py`, `app/main.py`, `app/core/cli.py` | `tests/test_e067_dead_remote.py` (4, fail without the fix) | works |
| F-066 | 2026-11-10 | E-066 | `main()` turns `NoConsoleScreenBufferError` into one line (other errors still raise); the Kaggle key message drops a bare exit code | `app/main.py`, `app/kaggle.py` | `tests/test_e066_console.py` (2), `tests/test_kaggle.py::test_no_api_key_gives_the_steps_without_noise` | works |
| F-065 | 2026-11-10 | E-065 | `six` added to Mitra's dependencies; the KaggleError names the real import error | `pyproject.toml`, `app/kaggle.py` | `tests/test_kaggle.py` (2) | works: installed `mitra kaggle status` shows the quota |
| F-064 | 2026-11-09 | E-064 | The plan folder's Workspace shares the turn's journal (absolute paths) | `app/core/chat.py` | `tests/test_review_a.py::test_a_plan_in_a_subfolder_shares_the_turn_journal` | works |
| F-063 | 2026-11-09 | E-063 | `plans.check_text` names each per-task problem once with all its tasks (`T1, T2, T3: paths ...`); self-needs listed after | `app/core/plans.py` | `tests/test_review_a.py::test_the_same_plan_problem_is_named_once_with_its_tasks` | works |
| F-062 | 2026-11-09 | E-062 | `_utf8_streams()` at import: stdout/stderr that are not UTF-8 (a file or pipe on Windows) are reconfigured to UTF-8 with `errors="replace"`. Live: `mitra night <bad plan> > night.log` now writes the ✗ message | `app/main.py` | `tests/test_review_a.py::test_redirected_output_takes_any_character` | works |
| F-061 | 2026-11-09 | E-061 | `roles.choose_context(model, text, cfg)` parses, saves and returns `roles.context_for` (the rule startup and /role use); `/context` calls it | `app/core/roles.py`, `app/main.py` | `tests/test_review_a.py::test_context_auto_gives_the_same_size_as_a_restart` | works |
| F-060 | 2026-11-09 | E-060 | `append_file` returns `syntax_note(rel, text)` on the whole file, like write_file (plans still get the /run check through it) | `app/core/tools.py` | `tests/test_review_b.py::test_e060_*` (2) | works |
| F-059 | 2026-11-09 | E-059 | `_LIBRARY_FRAME` regex skips site-/dist-packages, `python*\Lib\`, `/lib/python`, `<frozen`; a project's own `lib/` still counts | `app/core/tools.py` | `tests/test_review_b.py::test_e059_*` (2) | works |
| F-058 | 2026-11-09 | E-058 | `insights._sessions_with_calls`: a trace call belongs to a turn by number and time window (its session's start to the next session's start); `training()` and `export_training()` use it | `app/core/insights.py` | `tests/test_review_b.py::test_e058_*` (2) | works |
| F-057 | 2026-11-09 | E-057 | `ChatSession.night_started(plan, started)` (called by /run) stops watching files under the night's project for corrections, and sets `last_night` (E-052) | `app/core/chat.py`, `app/main.py` | `tests/test_review_a.py::test_files_a_night_will_change_are_not_counted_as_your_corrections` | works |
| F-056 | 2026-11-09 | E-056 | `Session.night_marks` keeps night verdicts; the dashboard counts them in 👍/👎 ("n on night runs") and lists them with your marks | `app/core/insights.py`, `app/core/dashboard.py` | `tests/test_review_b.py::test_e056_night_marks_reach_the_session_and_the_dashboard` | works |
| F-055 | 2026-11-09 | E-055 | `ChatSession._run` refuses a tool outside the role's set before running it | `app/core/chat.py` | `tests/test_review_a.py::test_a_role_cannot_run_a_tool_outside_its_set` | works |
| F-054 | 2026-11-09 | E-054 | `roles.use_for_chat(model)` saves the last model and the chat role's choice; `/model use` calls it and warns when mitra.toml `[roles] chat` still wins | `app/core/roles.py`, `app/main.py` | `tests/test_review_a.py::test_model_use_beats_local_model_in_mitra_toml` | works |
| F-053 | 2026-11-09 | E-053 | At the limit `night.kill_tree` stops the whole tree (Windows `taskkill /T /F`; POSIX own session + `killpg`), then `save_cut_off` puts the unfinished work in `git stash` (`.mitra` and NIGHT_REPORT.md excluded); the report says where the work is, never "rolled back" | `app/core/night.py` | `tests/test_review_b.py::test_e053_*` (4, incl. a real grandchild killed + stash) | works |
| F-045 | 2026-11-09 | E-045 | The MCP session read timeout is `max(timeout_s, connect_timeout_s)`: the tool-call timeout no longer caps server start (initialize / list_tools); calls keep their own `wait_for(timeout_s)` | `app/mcp.py` | `tests/test_mcp.py::test_slow_server_start_is_not_capped_by_the_call_timeout` | works |
| F-052 | 2026-11-09 | E-052 | `/run` tells the session a night started (`ChatSession.last_night`); `/good` / `/bad` then judge that night (feedback row with `of_night`, `of_turn` empty) until the next chat turn; a turn verdict names the turn and the start of your message (`Turn 1 ("write a plan…") marked 👎 bad`) | `app/core/chat.py`, `app/main.py` | `tests/test_e051_e052.py` | works |
| F-051 | 2026-11-09 | E-051 | `_strip_sentence_dot`: a slash command's final `.` is dropped before parsing (`/run plan.md 4.` → 4 h); `..` and chat messages untouched | `app/main.py` | `tests/test_e051_e052.py` | works |
| F-050 | 2026-11-09 | E-050 | Chat `run_plan` uses the /run plan check (`plans.check_text`, problems go back to the model to fix the plan), runs in the plan's folder (its own Workspace: git branch, task commits, records in `<plan folder>/.mitra/runs/plan`), always `python -m pytest -q` (the `test_command` argument is gone from the tool), and an unchanged plan runs once per turn (a changed plan or a new turn runs again) | `app/core/chat.py` | `tests/test_chat_core.py` (3 new, fail without the fix) | works |
| F-049 | 2026-11-08 | E-049 | `plans.check_text(text, folder)`: self-needs and circles, one command per task (no && ; |), `python -m pytest` not bare `pytest`, paths relative to the plan's folder; all problems listed (to Mitra at write time, to the user in /run and /plan check); a fast finish shows the report, not an error; /run notes a repo without commits | `app/core/plans.py`, `app/core/night.py`, `app/main.py` | `tests/test_plans.py` (4 new) | works |
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
