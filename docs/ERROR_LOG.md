# Error log

What went wrong: every bug, failed test, broken run and review finding, one entry each, newest first. What we changed
to fix it goes in [FIX_LOG.md](FIX_LOG.md). An entry is `closed` only when the fix is in and a regression test exists
that fails without it. Before fixing anything, search this file and [LESSONS.md](LESSONS.md) for the same symptom.

## Index

| ID | Date | Milestone | Severity | Found by | Title | Status | Fix |
|---|---|---|---|---|---|---|---|
| E-120 | 2026-11-12 | D-073, D-075 | High | review while building D-078 step 6 | `improve_chat.conversation_signals` and `coach.turns_since` matched a /bad (or signal) to its turn by turn number over the whole day's file, but turn numbers restart in every session: a /bad on turn 3 of the second session got the text of turn 3 of the first. `mitra improve` and the coach digest have been reading mismatched evidence whenever a day had more than one session | closed | F-110 |
| E-119 | 2026-11-12 | D-071 phased | Low | user's live session on the Phase 1 code | A WhatsApp message draft got a "Subject:" line and **bold** (WhatsApp shows the stars): every message was drafted like a mail | closed | F-108 |
| E-118 | 2026-11-12 | D-078 1b | Medium | user's live session on the Phase 1 code (/bad: "i thought it would directly do websearch and consolidate") | "Can you do a deep dive on the model once again" was answered "Would you like me to search?": the deep-dive push (F-104) only worked inside the look-up phase, not on the decision to look | closed | F-109 |
| E-117 | 2026-11-12 | D-071 phased | Medium | user's live session on the Phase 1 code (/bad: "i asked about the model but now its talking about mitra") | "Tell me about the model we are using as your brain Qwen3.5" chose look_at_code and searched the project for "qwen": a general technology question went to the project's files | closed | F-108 |
| E-116 | 2026-11-12 | D-071 phased | Medium | user's live session on the Phase 1 code (/bad: "we are expecting to see what can do and cant do") | "Can you tell me about you in detail" chose look_at_code, read the project's plan and night report and described itself from them ("test-first approach"); ABOUT_MITRA in the prompt was not used. The rule "a message that names something in this project needs look_at_code" caught "you" | closed | F-108 |
| E-115 | 2026-11-12 | D-078 #3 | Low | live B9 re-run after F-106 | The claim check flagged "Done." in "Done. I changed snake/game.py:13 ... The project has no tests, so this change is untested.": it judged each sentence alone, so an honest caveat in another sentence did not count | closed | F-107 |
| E-114 | 2026-11-12 | D-071 phased | High | Phase 1 score (B9_change, failing in all 3 baseline runs too) | "Make the snake start 4 cells long": the model chose look_at_code to find the line, found snake/game.py:13, then called make_change inside the look phase and got "make_change is not available to the chat role"; it answered "I can't directly edit files with my current tools. You'll need to manually change line 13". A phase could not hand over to the next, so any change request where the model looked first could never change anything (and the D-078 #2 test-after-change never ran) | closed | F-106 |
| E-113 | 2026-11-12 | D-071 phased | Medium | user's live session (turn 10, "i feel it can beeter") | Asked what it can do, Mitra said "What I Can Do Perfectly Now … I validate changes with tests before applying them" and "You mark /good and /bad, I learn from it": tests do not run by themselves yet and a mark changes nothing until `mitra improve` keeps a rule. ABOUT_MITRA listed only abilities, so the model filled the gaps optimistically | closed | F-105 |
| E-112 | 2026-11-12 | D-071 phased | Medium | user's live session (turn 6 /bad "you are still missing some", turn 7 /bad) | "Can you do a deep dive into web" got 1 search and 2 pages, then an answer: the look-up phase had the same 6-step budget and "open the 1-3 best results" note as a quick question; the user had to ask three times | closed | F-104 |
| E-111 | 2026-11-12 | D-071 phased | Low | user's live session | "You're absolutely right!" opened 5 of 10 answers, including answers to complaints it then repeated the mistake on | closed | F-103 |
| E-110 | 2026-11-12 | D-071 phased | High | user's live session ("no evidence or I dont know if you pulled the facts") | Answers claimed checks no tool result backed: "✅ What I Could Verify: Confirmed that India's DPDP Rules require compliance by May 2027" (that search never ran, E-109; the date came from the user's own file) and "Found ScrapUncle and Recykal are established players" (the search returned one arXiv paper on steel scrap). The only guards were prompt lines ("Never state a number you did not check") that a 9B ignores; nothing in the score or the coach could see it | closed | F-102 |
| E-109 | 2026-11-12 | D-071 phased | High | records review of the user's live session 2026-11-11 | The decide step called `web_search` ("DPDP Act India SME compliance deadline 2027 penalties"); the switch mapped it to the look-up phase, answered the call with "ok: web search" without running it (chat.py), and the phase started fresh, so the query was dropped while the model had been told "ok". Five other searches ran; the answer then "confirmed" the dropped one | closed | F-101 |
| E-108 | 2026-11-11 | v0.6.1 deep dive | High | CI (red since v0.7.0, found at the push) | Windows CI: the store mirrored no test records (store, dashboard, insights tests failed): `mirror_path` compared the resolved home with an unresolved `gettempdir()`, which on the runner is the 8.3 name C:/Users/RUNNER~1/..., so every test workspace looked like a dev run and was skipped. Local runs passed (no short name for this user) | closed | F-100 |
| E-107 | 2026-11-11 | D-062 B3, D-074 | Medium | user ("why we are showing like this") | Start-up after Kaggle ended while Mitra was closed printed the whole mid-session report: every turn of the last session (30 lines, all "answered"), "Files changed (none)", "Mitra stopped here and waits for you"; Kaggle was named three times ("not answering" above the header, the report, "Kaggle ready"); "Why" and "Now on" ran together; your own "1." made nested list numbers; "this session 111 min" for a session that was over. Also: 'when-needed' started Kaggle on the first talk turn ("hi"), against D-074 | closed | F-099 |
| E-106 | 2026-11-11 | D-071 phased | Low | review | The prompt budget check (scripts/model_view.py, CI) measures the router's CHAT_PROMPT, not the default phased prompt (~1,000 tokens with ABOUT_MITRA and the phase switches: under the 3K budget, but unchecked) | open | - |
| E-105 | 2026-11-11 | D-062 B3 | Low | user's live session | Every Kaggle-ended report written at start-up said "the laptop model could not write a summary": none is tried there (the conversation is gone) | closed | F-098 |
| E-104 | 2026-11-11 | D-073 | Medium | user's live session | "i said you to pick and tell me with a reason right why are not following that mitra" was not a signal: the rephrase check only knew no / wrong / try again; `mitra improve --chat` never saw the correction | closed | F-097 |
| E-103 | 2026-11-11 | D-071 phased | Medium | user's live session | Mitra did not know itself: "do you know about you?" -> "I don't have a fixed identity"; planning its own features it proposed ones it has (tools, MCP, Kaggle, tests, learning from feedback) | closed | F-096 |
| E-102 | 2026-11-11 | D-071 phased | High | user's live session | "can you pull information on self improving coding agents" was answered from memory (generic RL claims): the phased decide step had no phase with web_search / fetch_url | closed | F-095 |
| E-101 | 2026-11-11 | D-071 phased | Medium | v0.7.0 A/B (EVALS) | Four rule-type behaviour misses with qwen phased: small talk mentions the folder's project (B3); a continued thread drifts to the folder's project (B10); no question back when you are thinking (B2); a brainstorm about the code answers without reading it (I1) | closed (live re-score pending) | F-094 |
| E-081 | 2026-11-11 | D-068 step 3 | High | first live `mitra score --quick` | The run hung for 12+ min in R1_review step 2: the model stream never returned (it was running over the Kaggle tunnel, E-082, which stalled; the chat's model stream has no read timeout) | fixed for scoring (F-080); a stream read timeout in the chat: open | F-080 |
| E-100 | 2026-11-11 | D-068 step 3b A/B | High | score records | With thinking off, mimo sometimes thought invisibly until the output cap (8,192 tokens, ~6 min) and answered nothing: most failures of both arms | closed | F-093 |
| E-099 | 2026-11-11 | D-068 step 3b A/B | High | Ollama log | No output cap: one looping call generated 18,400 tokens for 36 minutes and every later request queued behind it; a timed-out score case did not stop its stream | closed | F-092 |
| E-098 | 2026-11-11 | D-068 step 3b | Medium | `mitra score` (routing through the chat's entry) | The router sorted the dataset clean-up task ("lowercase the email; drop rows whose email is empty") as a mail: no tools, nothing changed | superseded by D-071 (no router) | - |
| E-097 | 2026-11-11 | live (user) | Medium | chat | Long answers vanished while they were written: a block with no blank line (a long list or table) is drawn in the live area, which Rich crops to the screen height, so its top disappeared until the block ended; and the status line is gone during a turn (by design: it exists only while Mitra waits) | closed | F-090 |
| E-096 | 2026-11-11 | live (user) | Low | chat | `mitra score` typed in the chat (meant for the terminal) was sorted as a question and the explainer read brick-breaker's files on Kaggle | closed | F-089 |
| E-095 | 2026-11-11 | D-068 steps 0-3 | High | deep dive (insights on real records) | Dev checks put temp workspaces into your central store: 5 "snake-*" and 3 "tmp*" projects (my live-check scripts) and 2 files in _other from a test whose hung thread wrote after the test ended; the dashboard and the coach would read them as your sessions | closed | F-088 |
| E-094 | 2026-11-11 | D-068 steps 0-3 | Medium | deep dive (`mitra report` on real records) | Plan-first and "where did we stop" turns (no answer text by design) and esc stops were counted as the model's empty answers, which the coach would read as failures | closed | F-087 |
| E-093 | 2026-11-11 | D-068 steps 0-3 | High | deep dive (sweep of everyday phrases) | Follow-ups lost their tools: "still not working" / "try again" / "no, use pytest" after a fix went to the one-call reply path; "why?" after a code question did not read the code; "run the tests", "commit the changes", "the tests are failing, can you check" and "i need a script that ..." went to the read-only explainer; "rename X in the game" and "rewrite this paragraph: ..." / "write a prd" were planned as features | closed | F-086 |
| E-092 | 2026-11-11 | D-068 steps 0-3 | Medium | review | With every role set to thinking on/off, `thinking = "on"` in mitra.toml changed nothing, silently | closed | F-085 |
| E-091 | 2026-11-11 | D-068 steps 0-3 | Low | review | Your notes were sent twice on the reply and explain paths (system prompt + every turn, ~2K characters) | closed | F-084 |
| E-090 | 2026-11-11 | D-068 steps 0-3 | Low | review | `with_discussion` listed Mitra's own notes ("[Mitra stopped the tools ...]") as things you said | closed | F-082 |
| E-089 | 2026-11-11 | D-068 steps 0-3 | Low | review | `cited_files` stripped every leading dot: `.github/...` and `.env.example` were never cited; the same file could be listed twice in files_read | closed | F-082 |
| E-088 | 2026-11-11 | D-068 steps 0-3 | Low | review | A bare "no" (to "shall I also add tests?") was recorded as a rephrase signal | closed | F-082 |
| E-087 | 2026-11-11 | D-068 steps 0-3 | Medium | review | A timed-out score case kept calling the model and running tools in a deleted workspace while the next case ran | closed | F-083 |
| E-086 | 2026-11-11 | D-068 steps 0-3 | Medium | review | "where is the score stored?" was sorted general (one call, no tools): the model answered about your code without reading it | closed | F-082 |
| E-085 | 2026-11-11 | D-068 steps 0-3 | Medium | review | "add levels, add a scoreboard ... then update the readme" was sorted small (the plan/readme rule ignored several change verbs), so plan-first was skipped | closed | F-082 |
| E-084 | 2026-11-11 | D-068 steps 0-3 | High | review | "can you fix the crash in game.py? think it through" went to the read-only explainer (the discussion rule only stepped aside when the change verb came first) | closed | F-082 |
| E-083 | 2026-11-11 | D-068 steps 0-3 | High | review | `/plan <task>` typed after a question got the old discussion attached by `with_discussion` (talked_first ignored force_kind): the plan could be about the wrong thing | closed | F-082 |
| E-082 | 2026-11-11 | D-068 step 3 | High | live score header said "laptop · 256K" | `mitra score` without --remote ran on the user's active Kaggle session: config.load points at the remote, and the score used it (labelled laptop, at 256K) | closed | F-081 |
| E-080 | 2026-11-11 | live (user, Kaggle) | Low | Kaggle-ended report | The report named an old finished night run: "Night run: finished · plan.md · 4176 min of up to 4.0 h" (minutes since it started, days ago) | closed | F-079 |
| E-079 | 2026-11-11 | live (user, Kaggle) | High | plan-first on Kaggle | The planner failed with Cloudflare error 524: one non-streamed call sent nothing for 120 s, so the tunnel closed it | closed | F-078 |
| E-078 | 2026-11-11 | live (user) | High | sorting | Talking an idea through went to plan-first: "i want you to build a web app ... can we brainstrom on this" and "i feel ... once we get a base model i want to setup a web application ..." were planned as builds (a poor plan with a model the user never asked for); and "ok lets build it" would have planned from those four words only | closed | F-077 |
| E-077 | 2026-11-11 | D-068 step 3 | Low | own test | `score.run(results=RESULTS)` bound the path at import, so a test patching RESULTS wrote a row to the real results/scores.jsonl (removed) | closed | F-076 |
| E-076 | 2026-11-11 | D-068 step 3 | Medium | `mitra score --validate` | "write an email to my manager asking for leave ... for a family function" was not sorted as writing ("function" read as code) | closed | F-075 |
| E-075 | 2026-11-10 | D-068 step 2 | Medium | user question + sorting check | Talking about the project beyond "how does it work" went to the wrong path: "brainstorm ideas to make the game harder" and "suggest improvements for the api" took the no-tools everyday path (no files read); "update the plan with a level system" was planned as a new feature; "go with option 2" after Mitra's ideas was answered without tools | closed | F-074 |
| E-074 | 2026-11-10 | D-068 step 2 | Low | live check (snake, mimo-v2.6:9b) | The explainer's record missed files an answer named without a line ("**Board** (`snake/game.py`)"): `files_cited` was [] for a 4-file answer | closed | F-073 |
| E-073 | 2026-11-10 | D-068 step 2 | Low | live check (snake, mimo-v2.6:9b) | A follow-up question's record listed every file read in earlier turns (`files_read` scanned the whole history) | closed | F-072 |
| E-072 | 2026-11-10 | D-068 step 1 | Low | full test run | `tests/test_kaggle.py::test_the_librarys_own_sign_in_help_is_not_printed` (and one more) failed once in a full run while the clipboard was being checked from the same shell; passed alone and in the next full run (809 passed). Not reproduced: watching | open | - |
| E-071 | 2026-11-10 | D-068 step 1 | Medium | live check (mimo-v2.6:9b) | Mails from the reply path were signed "Thanks, Mitra" (the model is called Mitra in the system prompt) and added claims the user never gave ("use the paid option or request a larger allocation") | closed | F-071 |
| E-070 | 2026-11-10 | D-068 step 1 | Medium | live check (clipboard read back) | `/copy` put an invisible U+FEFF byte-order mark at the start of the copied text: `str.encode("utf-16")` adds one and clip.exe keeps it | closed | F-070 |
| E-069 | 2026-11-10 | D-068 step 0 | Medium | driven chat test (before commit) | A plan-first request whose planner failed crashed the chat: the new plan-path record passed `reason` twice to the recorder (`TypeError: got multiple values for keyword argument 'reason'`) | closed | F-069 |
| E-068 | 2026-11-10 | M2 | Medium | user's start (pasted) | The memory line suggested closing `MemCompression 1.8 GB`: newer Windows names its memory-compression process `MemCompression`, the never-close list only had "memory compression" | closed | F-068 |
| E-067 | 2026-11-10 | M4 | High | user's session (pasted) | After the Kaggle run stopped by itself (30 min unused, as designed), `mitra` said "No compatible local Ollama models found" and quit: the remote setting still pointed at the dead tunnel, so the model list came back empty; local Ollama was fine | closed | F-067 |
| E-066 | 2026-11-10 | M4 | Low | fresh-clone test (v0.1.0 prep) | Started without a real terminal (piped input, an IDE output pane, Git Bash without a console), the chat died with a 60-line prompt_toolkit traceback (`NoConsoleScreenBufferError`) after the header; also the no-API-key Kaggle message ended with a stray `(1)` | closed | F-066 |
| E-065 | 2026-11-10 | M4 | High | user's tool reinstall (live) | `mitra kaggle status` said "the `kaggle` package is missing" after the reinstall: kaggle 2.2.5 imports `six` without declaring it, so the fresh tool env could not load it (the dev venv happened to have six); the message hid the real import error | closed | F-065 |
| E-064 | 2026-11-09 | M3 | High | deep dive (Claude, own F-050) | F-050 gave a plan in a subfolder its own Workspace with its own journal, so `/undo` and the corrections check missed every file the plan run changed | closed | F-064 |
| E-063 | 2026-11-09 | M3 | Low | deep dive (live check of mitra-try/brick-breaker/plan.md) | The plan check repeated one problem per task (5 copies of the folder-prefix message for T1-T5) and stopped listing after 5, so other problems were hidden | closed | F-063 |
| E-062 | 2026-11-09 | M3 | Medium | deep dive (live `mitra night` run, output piped) | `mitra night ... > night.log` crashed with `UnicodeEncodeError: 'charmap' codec can't encode character '✗'` before anything ran: redirected output on Windows is cp1252 (`/run` was safe: it sets PYTHONIOENCODING) | closed | F-062 |
| E-061 | 2026-11-09 | M2 | Medium | code review (deep dive) | Two context rules: `/context auto` used `config.context_for_model` (measured 128K for a 4B) while startup, `/role` and `mitra solve` use `roles.context_for` (the model's maximum, D-052), so the same setting gave 128K now and 256K after a restart | closed | F-061 |
| E-060 | 2026-11-09 | M1 | Medium | code review (deep dive) | `append_file` skipped the syntax check write_file and edit_file get (only plan files were checked), so a long .py file finished by appending (the E-044 advice) was never checked | closed | F-060 |
| E-059 | 2026-11-09 | M1 | Low | code review (deep dive) | `crash_hint` treated Windows standard-library frames (`...\Python312\Lib\json\decoder.py`) as project frames and pointed the model at decoder.py instead of the project line | closed | F-059 |
| E-058 | 2026-11-09 | M5 | High | code review (deep dive) | `training()` / `export_training()` matched traces to turns by turn number only, across the whole daily chat file; with sessions split per Mitra start (turns restart at 1), turn 1 of two sessions got the same calls: duplicate or wrong training examples | closed | F-058 |
| E-057 | 2026-11-09 | M5 | Medium | code review (deep dive) | Any change to a file Mitra left was recorded as your correction, also when a `/run` night changed it: the turn dropped out of the training data and the dashboard's "your fixes" grew | closed | F-057 |
| E-056 | 2026-11-09 | M5 | Medium | code review (deep dive) | A `/good` / `/bad` on a night (F-052, `of_night`, no turn) was written but dropped by `insights.sessions()`: it never reached the dashboard | closed | F-056 |
| E-055 | 2026-11-09 | M2 | High | code review (deep dive) | Role tool sets were only a filter on the tool list sent to the model; `ChatSession._run` ran any tool the model named, so a reviewer could still write files or run commands | closed | F-055 |
| E-054 | 2026-11-09 | M2 | High | code review (deep dive) | `/model use X` saved X as the last model, but mitra.toml `local_model` and a saved chat-role choice win over it in `roles.resolve`, so the switch could silently do nothing | closed | F-054 |
| E-053 | 2026-11-09 | M3 | High | code review (deep dive) | At the time limit `mitra night` killed only the solve process: no rollback ran, the cut-off task's half-written files stayed, its pytest/game children kept running, and NIGHT_REPORT said the changes "were rolled back" | closed | F-053 |
| E-052 | 2026-11-08 | M2 | Medium | user's session (pasted, mitra-try) | `/good` and `/bad` always said "Turn 1": slash commands and `/run` nights do not start a chat turn, so the 👎 on three empty nights landed on the plan-writing turn the user had marked 👍 | closed | F-052 |
| E-051 | 2026-11-08 | M2 | Low | user's session (pasted, mitra-try) | A trailing period was kept as part of the arguments: `/run plan.md 4.` ran with "up to 4. h", `/plan check brick-breaker/plan.md.` answered "plan.md. is runnable" | closed | F-051 |
| E-050 | 2026-11-08 | M3 | High | user's session (pasted, mitra-try) | The chat `run_plan` tool ("can you run the plan") bypasses the plan check (built a plan where T1 needed itself: all tasks skipped), runs in the session folder instead of the plan's folder (no git branch, "not a git repository"), takes the model's test command (`pytest brick-breaker/...` → WinError 2), and nothing stops the model re-running the same unchanged plan 3-4 times in one turn | closed | F-050 |
| E-049 | 2026-11-08 | M3 | High | user's first /run of a Mitra-written plan | The plan check said ✓ but every task was skipped ("T1 skipped: needs T1"): T1 needed itself; Done-when commands chained with && (the runner splits on spaces), bare `pytest`, and paths starting with the plan's own folder (`brick-breaker/tests/...` while /run runs inside brick-breaker). A run that finished in seconds was shown as "stopped right away"; the repo had no commit, so no per-task commits | closed | F-049 |
| E-048 | 2026-11-08 | M2 | Low | user's session (pasted, tall terminal) | A large empty block between the input line and the status line: prompt_toolkit draws `bottom_toolbar` at the bottom of the terminal, so the gap grows with the window height (E-047's `reserve_space_for_menu=0` did not cover it). Fix idea: show the status line inside the prompt (above the input) instead of as a bottom toolbar | open | |
| E-047 | 2026-11-08 | M2 | High | user's session (pasted) | (a) `/model` answered "Unknown mode: l": `/mode` matched with startswith ran first; (b) the Ollama update dropped the connection mid-turn: raw "WinError 10054 ... Unexpected error", turn lost; (c) run_tests summary was pytest's last line, a deprecation warning ("FAILED: warnings.warn(...)"), misleading the model and the user; (d) 7 empty lines under the input (prompt_toolkit reserves space for the menu) | closed | F-047 |
| E-046 | 2026-11-07 | M2 | Medium | review of the chat flow | Compaction started at a fixed 120K tokens (`auto_compact_threshold = 120000`, min with 80% of num_ctx), so at 256K (D-039) the chat never used more than ~half the context; the memory reserved for the rest was wasted and kept most of the 9B off the GPU | closed | F-046 |
| E-045 | 2026-11-07 | M2 | Low | full test run, machine busy (Ollama + a training job) | `test_timeout_is_reported_and_the_server_keeps_working`: the fake MCP server did not start within its 2 s timeout ("unhandled errors in a TaskGroup"), so the test sees a start failure instead of a call timeout. Fails on 6a3d32b too (not the dashboard change); passed earlier the same day | closed | F-045 |
| E-044 | 2026-11-07 | M1 | High | live session (mitra-try, 9B at 256K, "make a detailed report") | The model wrote one ~5,200-token tool call for 3m20s and ended it before it was closed; Ollama's Qwen3.5 parser failed (`XML syntax error on line 173: unexpected EOF`, ollama.ResponseError) and the whole turn stopped with "Unexpected error"; the model was never told | closed | F-044 |
| E-043 | 2026-11-07 | M1 | Medium | user, after switching to qwen3.5:latest at 256K | Mitra started the 9B at 256K (12 GB loaded, ~6.8 GB of it in RAM) with only 7 GB RAM free and said nothing; the user could not tell whether it would run or what to close | closed | F-043 |
| E-042 | 2026-11-06 | M1 | Medium | live session (brick breaker, turns 6-7) | Turns the user stopped with esc left no `turn_end` record (KeyboardInterrupt went past the recorder), so the analyzer could not see them; being stopped by the user is a key self-improvement signal | closed | F-042 |
| E-041 | 2026-11-06 | M1 | High | live session (brick breaker, mitra-try, turn 4) | The game ran fine but was reported `Exit code 1 [TIMEOUT] FAILED` when the command limit stopped its window; the model kept trying to fix a working game (`timeout 5 && python x.py &`, `python -c ...`) until the guard stopped the turn | closed | F-041 |
| E-040 | 2026-11-06 | M1 | High | live session (brick breaker, mitra-try, turn 4) | `python -c "import pygame; print('ok')"` was split at the `;` inside the quotes and ran as `import pygame && print(...)`: a correct command failed 4 times and the guard stopped the turn (my E-033 chain split ignored quotes) | closed | F-040 |
| E-039 | 2026-11-06 | M1 | Medium | deep dive | Some subprocess calls had no timeout (8 in `app/agents/filesystem.py`: git, venv, pip; 2 git helpers in `app/main.py`), against the CLAUDE.md non-negotiable; a hung git would freeze the chat | closed | F-039 |
| E-038 | 2026-11-06 | M1 | Medium | deep dive | A full harness (12 rules + every tool text) would put the chat prompt at about 3,199 tokens, over the 3,000 budget; the CI budget check only measured the built-in prompt | closed | F-038 |
| E-037 | 2026-11-06 | M1 | Low | deep dive | The harness `solve_max_steps` limit never applied: `mitra solve` passed 40 and `run_plan` 30 as fixed defaults | closed | F-037 |
| E-036 | 2026-11-06 | M1 | High | deep dive (self-improvement) | `mitra improve` review findings: (a) it always analysed every old record, so after a kept change it would keep proposing for the same old problem; (b) a failed model call (Ollama down) counted as the model failing a task; (c) the 9B proposer stayed loaded while the 4B builder loaded, with no free-RAM check; (d) a tool text up to 600 chars was tested but saved cut to 400; (e) overlapping search folders could count a record twice; pytest run through `run_command` counted as a tool error; examples named `.mitra` instead of the project | closed | F-036 |
| E-035 | 2026-11-06 | M1 | High | own live test (`mitra improve --tasks T01`) | Every benchmark task graded as failed although the visible tests passed: `bench.grade` ran pytest with `sys.executable` (the `mitra` tool's Python, no fastapi), and `evaluate` ignored the grader's infra error, so the A/B compared 0/1 vs 0/1 | closed | F-035 |
| E-034 | 2026-11-06 | M1 | Medium | own live test (`mitra improve --dry-run`) | `mitra improve` crashed at start: `AttributeError: 'NoneType' object has no attribute '__dict__'` in dataclasses, loading `bench/bench.py` by path | closed | F-034 |
| E-033 | 2026-11-06 | M1 | High | user session (brick breaker, pasted) | The same `cd .../brick-breaker && python -m pytest ...` ran 30+ times (455K tokens, 12 min) until the step limit: chains and `cd` cannot run without a shell, Git Bash paths are not Windows paths, the repeat guard exempted shell commands and missed their failures, and the screen showed only `failed · exit 1` | closed | F-033 |
| E-032 | 2026-11-06 | M1 | High | user session (brick breaker) | A model's `run_command python ...` found Mitra's own Python inside the installed command (Windows searches the parent's folder first): `No module named pytest` | closed | F-032 |
| E-031 | 2026-11-06 | M1 | High | user session (brick breaker) | `python -c "import os; os.makedirs(...)"` ran without asking because `python` had been trusted in that folder: trust by program name let inline code through in ask mode | closed | F-031 |
| E-030 | 2026-11-06 | M2 | Medium | user session (brick breaker) | A 154-line new file was shown as an 80-line diff ending "… 1 more lines": two cut-offs stacked; new files shown as `+` diff lines, printed twice | closed | F-030 |
| E-029 | 2026-11-06 | M1 | High | Claude (own mistake) | `uv tool install --reinstall` while the user had `mitra` open: Windows locked the tool's python.exe, uv had already deleted the tool's packages, so new `mitra` launches failed with `No module named 'app'` | closed | F-029 |
| E-028 | 2026-11-06 | M1 | High | health check (live run step) | Installed as the `mitra` command, run_tests used Mitra's private Python: `No module named pytest`, so every test run in a user's project failed | closed | F-028 |
| E-027 | 2026-11-06 | M2 | High | Claude (review of `/commit`) | `/commit` committed unstaged and untracked files: it used the `git_commit` tool, which runs `git add -A` first; with nothing staged, `--generate` drafted a message from "(no diff)" and committed everything | closed | F-027 |
| E-026 | 2026-11-06 | M1 | High | Claude (test for fresh rounds) | The repeat guard refused the 3rd `run_tests` (always called with `{}`) and re-reading a file after editing it, so a normal fix loop (change, test, change, test) was stopped as "kept repeating" | closed | F-026 |
| E-025 | 2026-11-06 | M2 | High | user ("why is it stopped after the compaction") | The chat compacted at "193,304 tokens" on a 64K model: context use was the sum of every call's tokens, not the size of the latest prompt; the same turn ended after the old file agent hit its 20-call limit and wrote 4 files into `levels/01-snake/` | closed | F-025 |
| E-024 | 2026-11-06 | M2 | High | user ("its mitra job") | Mitra could not research anything: its only search was DuckDuckGo's HTML page, which times out from this machine; a stopped search gave no answer; one failed call replaced the whole answer with an error line | closed | F-024 |
| E-023 | 2026-11-06 | M2 | High | user (terminal test) | "search about 3.5+ series models": the web agent ran 100+ `search_web` calls, most with the identical query, while every search timed out | closed | F-023 |
| E-022 | 2026-11-06 | M2 | Medium | user (terminal test) | "can you make a clean plan for Level 01 ... 3. test ..." was routed as a test request; "fix the failing test" too; "latest" counted as "test" | closed | F-021 |
| E-021 | 2026-11-06 | M2 | Medium | Claude (E-003 test) | On Windows the command splitter kept quote marks: `python -c "print(42)"` ran the literal string and printed nothing; quoted program paths failed the allow-list | closed | F-020 |
| E-020 | 2026-11-06 | M2 | High | user (terminal test) | "make a clean plan for Level 01 ... plan, implement, test, fix, repeat" showed two thinking lines and nothing else: the model called `execute_plan`, got "not approved, use `/plan approve`" (a removed command), then wrote an empty follow-up, which Mitra did not report | closed | F-016 |
| E-019 | 2026-11-06 | M2 | High | user (errors.log review) | Questions and "no coding" requests started builds: "whats the plan now" became a plan goal and ran twice; "plan ... no coding" wrote code; files went to a nested `mitra-playground/mitra-playground/` | closed | F-015 |
| E-018 | 2026-11-06 | M2 | High | user (errors.log) | A plan step crashed the whole turn: qwen3.5:4b called `create_file` with `content` as a JSON object (a game config), pydantic rejected it, and the exception escaped the tool loop | closed | F-014 |
| E-017 | 2026-11-06 | M2 | Medium | user (terminal test) | Old and new interface mixed: model picker, GPU emoji line, "Session Snapshot" box (stale "compact at 120,000"), API-key note, cyan boxes for command replies and a full-screen blue dialog for approvals, around the new header | closed | F-013 |
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
| E-005 | 2026-10-24 | M0 | Medium | CI (Linux) | local-codex is Windows-only: 8 tests fail on Linux (backslash paths, PowerShell commands, skill paths) | closed | F-022 |
| E-004 | 2026-10-24 | M0 | Medium | lint (F821) on import | Model-advisor command crashes after finishing: stray copy of brainstorm code with undefined `raw`, `llm` | closed | F-001 |
| E-003 | 2026-10-24 | review | Medium | local-codex review | Shell allowlist checks only the program name; path checks pass when no workspace is set | closed | F-019 |
| E-002 | 2026-10-24 | review | Medium | local-codex review | Agent loops run `while True` with no step limit | closed | F-018 |
| E-001 | 2026-10-24 | review | High | local-codex review | Repair loop stops early: `edit_file` missing from `mutating_tools` | closed | F-017 |

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

### E-033: One failing shell command, 30 times

- **Date found:** 2026-11-06 · **Milestone:** M1 · **Severity:** High · **Found by:** user, brick-breaker session (pasted screen)
- **Status:** closed

**What happened:** after writing the game, Mitra alternated two commands
(`cd /c/Users/.../brick-breaker && python -m pytest ...` and the same from the repo root) 30+ times, each
`failed · exit 1`, then told the user tests failed "due to workspace path restrictions". 40 model calls, 455.6K
prompt tokens, 719 s.
**Root cause:** (1) model commands run without a shell, so `cd X && ...` can never work; (2) `/c/...` is a Git Bash
path; (3) the repeat guard exempted `run_command` (E-026 fix) and only counted outputs starting with ✗ as failures;
(4) `shell_done` hid the error, so neither the user nor a reader of the screen could see why.
**Fix:** F-033.
**Regression test:** `tests/test_shell_chains.py` (10).
**Lesson?** L-036.

### E-032: The shell's `python` was Mitra's own Python

- **Date found:** 2026-11-06 · **Milestone:** M1 · **Severity:** High · **Found by:** user's brick-breaker session (activity log)
- **Status:** closed

**What happened:** `run_command("python -m pytest -v tests/")` failed with `No module named pytest` from the uv tool's
Python. **Root cause:** commands start with CreateProcess, which on Windows looks for `python` in the parent's folder
before PATH; E-028 fixed only run_tests. **Fix:** F-032. **Regression test:** `test_model_python_command_uses_the_projects_python`.

### E-031: "Trusted" let inline code run without asking

- **Date found:** 2026-11-06 · **Milestone:** M1 · **Severity:** High · **Found by:** user's brick-breaker session
- **Status:** closed

**What happened:** after `mkdir` was refused, the model ran `python -c "import os; os.makedirs(...)"`; it ran with
"Trusted `python`" and no prompt. **Root cause:** trust is stored per program name; the E-003 inline-code rule only
applied in auto mode. **Fix:** F-031 (and a `make_dir` tool, so the model does not need the shell for folders).
**Regression test:** `test_inline_code_asks_even_when_the_program_is_trusted`, `test_make_dir_creates_folders_inside_the_workspace`.

### E-030: File approvals were a wall of `+` lines with a wrong count

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** Medium · **Found by:** user, brick-breaker session
- **Status:** closed

**What happened:** each new file appeared as a unified diff (`--- a/ +++ b/ @@ -0,0 +1,154 @@`, every line `+`), cut
at 80 lines with "… 1 more lines", then repeated as `● Write <file>`. **Root cause:** `diff_text` cut at 80 lines and
added its own note, then `detail_block` cut again at 80 and counted only that note. **Fix:** F-030.
**Regression test:** `test_new_file_card_has_header_numbers_and_an_honest_fold`, `test_edit_view_shows_numbered_change_with_context`.

### E-029: Reinstalling the command under an open session broke it

- **Date found:** 2026-11-06 · **Milestone:** M1 · **Severity:** High · **Found by:** Claude, own mistake
- **Status:** closed

**What happened:** to add pytest to Mitra's dependencies I ran `uv tool install --editable . --reinstall` while the
user's `mitra` session (started 19:55) was open. uv deleted the tool's `Lib/site-packages`, then failed to remove
`Scripts/` (`Access is denied`, python.exe in use). New launches failed; the open session could have failed on its
next lazy import.
**Root cause:** reinstall removes the whole tool environment first; on Windows a running interpreter locks its exe.
**Fix:** F-029. Repaired by installing into the existing environment
(`uv pip install --python <tool>/Scripts/python.exe -e .`); `mitra --version` and the live check passed after.
**Regression test:** `scripts/health_check.py` skips the reinstall while `mitra.exe` is running.
**Lesson?** L-035.

### E-028: Tests ran with Mitra's own Python, not the project's

- **Date found:** 2026-11-06 · **Milestone:** M1 · **Severity:** High · **Found by:** `scripts/health_check.py`, first full run
- **Status:** closed

**What happened:** the live step (`mitra solve` from a temp folder) stopped after 15 steps: every `run_tests` said
`No module named pytest` from the tool's own `python.exe`.
**Root cause:** run_tests replaced `python` with `sys.executable`; that was the shared venv while Mitra ran from
source, but the tool's private venv once installed with `uv tool install`.
**Fix:** F-028.
**Regression test:** `test_tests_run_with_the_projects_python`; the health check's live step (passed after the fix:
4 steps, 26 s).
**Lesson?** L-035.

### E-027: `/commit` committed files the user had not staged

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** Claude, review of `/commit`
- **Status:** closed

**What happened:** `/commit` is documented as "Commit staged changes ... never pushes", but `_cmd_commit` called
`filesystem.git_commit`, which runs `git add -A` before `git commit`, so unstaged edits and untracked files (scratch
files, `.env` if not ignored) went into the commit. With nothing staged, `/commit --generate` still asked the model:
the `git_diff` tool replies "✓ git diff\n(no diff)", and the check looked for "no changes". A cancelled menu fell
through to "type your own message". The git calls had no timeout. It never pushed.
**Root cause:** a tool written for the agents (stage everything, then commit) reused for a user command with a
different promise; no test ran `/commit` against a real repo.
**Fix:** F-027.
**Regression test:** `tests/test_commit_command.py`.
**Lesson?** L-034.
### E-026: The repeat guard stopped normal fix loops

- **Date found:** 2026-11-06 · **Milestone:** M1 · **Severity:** High · **Found by:** Claude, writing the fresh-round test
- **Status:** closed

**What happened:** a scripted loop of write, run_tests, search, run_tests, list, run_tests ended "stopped": the third
`run_tests` was refused as a repeat because its arguments are always `{}`.
**Root cause:** the guard (E-023) treated any identical call as pointless, but tests and commands are meant to be
re-run after changes, and a file's content changes after an edit.
**Fix:** F-026.
**Regression test:** `test_repeat_guard_allows_rerunning_tests_and_rereading_after_an_edit`,
`test_fresh_round_after_repeated_failures_keeps_files_and_hands_off`.
**Lesson?** -

### E-025: Context use counted every call; compaction fired far too early

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** user, chat in mitra-playground
- **Status:** closed

**What happened:** after "so step 1 is done...??" the old file agent stopped at its 20-call limit (E-002 fix) while
writing the game; the turn ended with "Let me split this into smaller steps:" and Mitra auto-compacted with
`usage_tokens_before: 193304` although the 4B context was 64K. The agent had written `config.py`,
`food_generator.py`, `input_handler.py`, `main.py` into the level definition folder `levels/01-snake/`.
**Root cause:** `sess_in + sess_out` adds up the input of every model call, and every call resends the whole history,
so the number grows much faster than the context really fills. The status line's "ctx %" and the auto-compact check
both used it. (The 20-call stop and the writes are the old chat path, replaced by the core loop in M1 stage 2.)
**Fix:** F-025. The 4 stray files were moved out of the level folder (backup in the session scratchpad).
**Regression test:** `test_context_use_is_the_latest_prompt_not_the_sum_of_calls`.
**Lesson?** L-033.

### E-024: Mitra's web search did not work

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** user, after E-023 ("its mitra job, what is the point of it if you do it")
- **Status:** closed

**What happened:** `search_web` only scraped DuckDuckGo, which times out from this machine on every endpoint (duckduckgo.com,
html., lite.). Bing answers automated requests with unrelated pages; Mojeek returns a captcha. When the repeat guard
stopped the loop, the user got only "Stopped" and no answer; `_finalize_summary` replaced the model's answer with
"Completed part of the web request, but hit N errors" whenever any call had failed.
**Root cause:** one scraped search page as the only source; no final answer after a stop; errors overrode answers.
**Fix:** F-024.
**Regression test:** `tests/test_web_search.py` (6). Live, qwen3.5:4b, "search about the Qwen 3.5 and newer Qwen
series models": 1 search + 4 reads (Hugging Face model cards, Ollama, GitHub), a sourced answer in 30 s; before the
fix it ran 100+ failing searches with no answer.
**Lesson?** L-032.

### E-023: The same failing search, over and over

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** user, terminal test
- **Status:** closed

**What happened:** the web agent called `search_web` more than 100 times; after narrowing the query a few times,
qwen3.5:4b repeated `Qwen model specifications` about 80 times. Every call returned `✗ Web search failed: <urlopen
error timed out>` (DuckDuckGo's HTML page is not reachable from this machine right now).
**Root cause:** E-002 (no step limit; the user's session still ran code from before that fix, so it never stopped);
and nothing stopped identical repeats or a tool that fails every time, so even with the 20-call limit the model
could spend all 20 calls on the same failed search.
**Fix:** F-023 (on top of F-018's 20-call limit).
**Regression test:** `test_web_agent_stops_when_search_keeps_failing` (the user's session), `test_identical_calls_are_not_rerun_and_then_stop`,
`test_repeat_guard_resets_failures_after_a_success`.
**Lesson?** L-031.

### E-022: The router picked the first keyword it checked, anywhere in the message

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** Medium · **Found by:** user, terminal test (with E-020)
- **Status:** closed

**What happened:** "can you make a clean plan for Level 01 ... 3. test" -> `test` ("Preparing a verification step");
"fix the failing test in test_game.py" -> `test`.
**Root cause:** the keyword checks run in a fixed order (test before fix, plan, ...) and match substrings anywhere.
**Fix:** F-021.
**Regression test:** `test_leading_verb_routes_the_request` (6 cases incl. the user's message),
`test_words_containing_test_are_not_test_requests`.
**Lesson?** L-029 (same class as E-019).

### E-021: Windows command splitting kept the quotes

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** Medium · **Found by:** Claude, writing the E-003 test
- **Status:** closed

**What happened:** `shell.execute('python -c "print(42)"')` exited 0 with no output; `"C:/x y/python.exe" -m pytest`
was refused as `'python.exe"' is not in the allowed commands list`.
**Root cause:** `shlex.split(posix=False)` (used on Windows so backslashes survive) keeps quote characters in the
arguments.
**Fix:** F-020.
**Regression test:** `test_split_command_strips_outer_quotes_on_windows`.
**Lesson?** -

### E-020: A turn ended with nothing on screen

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** user, terminal test (sent twice)
- **Status:** closed

**What happened:** the request was routed as `test` (it contains "test"), shown as "Preparing a verification step";
the chat model called the `execute_plan` tool with no approved plan; the tool answered "Use `/plan approve` first,
then `/plan next`" (commands removed on 2026-11-05); the follow-up model call returned no text, and Mitra printed only
the token footer. The reply reached `.mitra/activity.md` but never the screen.
**Root cause:** the `execute_plan` branch printed no tool line, an empty follow-up was not treated as an error (only an
empty first reply was), and 11 messages still named removed commands.
**Fix:** F-016.
**Regression test:** `test_no_text_mentions_removed_commands` (scans `app/` for removed commands in backticks),
`test_unapproved_plan_reply_names_no_command`.
**Lesson?** L-030.

### E-019: Questions started builds; files written to a nested copy of the project

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** user, reviewing errors.log with Claude
- **Status:** closed

**What happened (mitra-playground, from `.mitra/execution_trace.jsonl`):**
1. "ok lets start with snake game ... plan for the game first, no coding" created a level with `assert True` tests and
   a `start/main.py` that does not parse, under `mitra-playground/mitra-playground/levels/01-snake/`.
2. "whats the plan now" was saved as the plan goal and started a PlanWorkflow (13:24, again 14:12), which wrote
   `snake_game_project/`, `ARCHITECTURE.md`, `DESIGN.md`, `PLAN.md` in the repo root.
**Root cause:** the regex intent router matched the substring "plan" anywhere (also inside "explain") and had no idea of
a question or of "no coding"; the file tools joined a relative path that began with the workspace's own folder name onto
the workspace.
**Fix:** F-015. The leftovers were moved out of the playground (backup in the session scratchpad); `.mitra/` is now
ignored by the playground repo.
**Regression test:** `TestQuestionsAreAnswered`, `TestWorkspaceNameIsNotNested` in `tests/test_main_ux.py`.
**Lesson?** L-029. The regex router itself is removed in the M1 loop rewrite; this is the stopgap.

### E-018: Bad tool arguments crashed the turn

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** High · **Found by:** user, `.mitra/errors.log` in mitra-playground
- **Status:** closed

**What happened:** during a plan run, `filesystem.run` -> `create_file` raised
`ValidationError: content: Input should be a valid string [input_value={'game': {'screen_width': ..., 'color': [255, 0, 0]}}]`.
The error went up to the chat loop, which printed "Error" and stopped the plan.
**Root cause:** tool calls were run with `fn.invoke(args)` and no error handling, so any wrong argument type from the
model ended the turn instead of going back to it as a tool result. Small models often send JSON file content as an
object.
**Fix:** F-014.
**Regression test:** `TestBadToolArguments` in `tests/test_filesystem.py` (3 tests; all fail without the fix).
**Lesson?** L-028.

### E-017: Old and new terminal interface mixed

- **Date found:** 2026-11-06 · **Milestone:** M2 · **Severity:** Medium · **Found by:** user, terminal test against the mock
- **Status:** closed

**What happened:** startup showed the model picker, a GPU line with an emoji, four "loaded" notes, a "Session
Snapshot" box with an out-of-date compact threshold, and "No Ollama API key provided" before the new header. Command
replies were still cyan boxes, and the plan approval opened a full-screen blue `radiolist_dialog`.
**Root cause:** part 1 added the new output (`app/ui/`) for the chat turn only; every other print path kept its old
panel or dialog. Nobody compared the whole session against the mock.
**Fix:** F-013.
**Regression test:** `test_startup_shows_no_banner`, `test_startup_model_uses_the_last_model_without_asking`,
`test_approval_shows_tool_line_coloured_diff_and_question`, menu tests in `tests/test_ui.py`.
**Lesson?** L-027.

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

- **Date found:** 2026-10-24 · **Milestone:** M0 · **Severity:** Medium · **Found by:** first CI run on Linux · **Status:** closed (2026-11-06)

**What happened:** 553 passed, 8 failed on ubuntu-latest (all pass on Windows): skill bodies not found
(`Could not read skills\05-rag-pipeline\SKILL.md`), run hints mix `\` and `/`, intent routing returns Windows paths
(`tests/test_main_ux.py`, `tests/test_skills.py`).
**Root cause:** paths built and stored as Windows strings; PowerShell assumed for run commands.
**Fix:** F-022 (fixed now instead of waiting for M1). The Linux CI job is blocking again.
**Regression test:** the 8 Linux failures pass; `tests/test_review_fixes.py` E-005 section; Linux CI blocking.
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

- **Date found:** 2026-10-24 · **Milestone:** review · **Severity:** Medium · **Found by:** local-codex review · **Status:** closed (2026-11-06)

**What happened:** `shell.py:407` allows a command if `pathlib.Path(parts[0]).name` is on the list; `python`, `pip`,
`node` and `npx` are on it, so `python -c "<anything>"` passes. `shell.py:207` and `filesystem.py:96` skip the path check
when no workspace is set.
**Root cause:** allowlist designed for convenience, not containment; fail-open default.
**Fix:** F-019.
**Regression test:** `test_review_fixes.py`: no-workspace refusals, inline code refused / approved, detection.
**Lesson?** L-014

### E-002: Agent loops run `while True` with no step limit

- **Date found:** 2026-10-24 · **Milestone:** review · **Severity:** Medium · **Found by:** local-codex review · **Status:** closed (2026-11-06)

**What happened:** `filesystem.py:958`, `shell.py:645`, `reader.py:456`, `web.py:244` loop until the model stops calling
tools. A small model that repeats a call never stops.
**Root cause:** loops written for models that end on their own.
**Fix:** F-018.
**Regression test:** `test_review_fixes.py`: each of the 4 agents stops after 20 calls.
**Lesson?** L-013

### E-001: Repair loop stops early: `edit_file` missing from `mutating_tools`

- **Date found:** 2026-10-24 · **Milestone:** review · **Severity:** High · **Found by:** local-codex review · **Status:** closed (2026-11-06)

**What happened:** `app/langgraph_workflows.py:55` lists `create_file`, `move_file`, `delete_file`, `delete_folder`,
`create_folder` but not `edit_file`. A repair that only edits files counts as "no code changes", so the loop stops.
**Root cause:** set maintained by hand; tests (`tests/test_langgraph_workflows.py:34,106`) only use `create_file`.
**Fix:** F-017.
**Regression test:** `test_edit_file_counts_as_a_code_change`.
**Lesson?** L-012
