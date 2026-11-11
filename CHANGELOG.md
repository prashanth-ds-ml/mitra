# Changelog

All notable changes, newest first. Versions follow the milestones in [docs/PLAN.md](docs/PLAN.md).

## [Unreleased]
- **Four conversation misses fixed (E-101):** small talk no longer brings up the project; "I am thinking" gets a
  question back; ideas about the project's code read the code first (3-5 options tied to file:line); continuing an
  earlier conversation stays on that topic; summaries keep names, numbers and dates as written.
- **Formatted answers, your messages in amber (D-076):** Mitra formats every answer (bold, code, steps, tables, short headings); mails stay plain. What you type is amber, so your side of the conversation stands out; code blocks use Phosphor colours.
- **Self-improvement in two layers (D-075):** Mitra runs one learning round by itself in the background when you leave with 3+ new signals (/bad, "I said …", rephrasing) and shows what it learned at the next start, with the undo; `mitra coach` has Claude review your recorded conversations and queues its suggested rules for that round, where `mitra score` decides. The header reminds you when a review is due.
- **A quiet start after Kaggle ended (E-107):** one line ("Kaggle ended while Mitra was closed · last session 111 min, 30 turns, no files changed · report in .mitra/reports/") instead of the whole last session; a report during a session shows the last 8 turns, one fact per line. Kaggle starts when you ask for work, never for a hello.
- **Talk on the laptop, work on Kaggle (D-074):** while Kaggle is up, plain conversation is answered by the laptop model (kept loaded); reading code, web look-ups, changes and plans run on Kaggle. A conversation too long for the laptop's context stays on Kaggle whole, never cut.
- **From your live session (E-102..E-105):** asking Mitra to find or pull information now searches the web (a new look-up phase); Mitra knows what it is and what it can already do; "I said ... why aren't you following" counts as a correction for `mitra improve --chat`; reports written at start-up no longer claim a failed summary. `mitra score` behaviour set: 14 cases (look-up, knows itself, already has it, your pick then mine).
- **`mitra improve --chat` (D-073):** Mitra learns one conversation rule from the failed `mitra score` cases and
  your `/bad` / rephrase / interrupt / undo signals, scores the quick set with and without it, and keeps it only if
  it passes at least 2 more cases with no category lower. `--rounds N`, `--dry-run`; undo with `mitra harness revert`.

## [0.7.0] - 2026-11-11 · One Mitra (D-071) + qwen3.5 as the model (D-072)
- **qwen3.5:latest is Mitra's model** (chat, all roles, Kaggle at 256K); mimo turned conversation into builds.
- **One conversational loop** behind `architecture = "one"` or `"phased"` in mitra.toml: the model decides whether
  to talk, look or change (phased: decide first with no file tools, then act in that phase with only its tools).
  The router stays the default until the A/B decides (EVALS).
- **Conversation memory as threads** (~/.mitra/threads): said / decided / open per discussion, written at exit.
- **Every model call has an output cap (8,192 tokens) and a runaway guard;** an empty answer is asked for once.
- `mitra score`: a *behaviour* category (10 cases), `--arch router|one|phased`, `--ctx`.

## [0.6.4] - 2026-11-11
- Long answers no longer vanish while they are written: a long list, table or code block scrolls normally.
- While Mitra works, a footer under the answer shows the time, the live speed and this machine (CPU, RAM, GPU).

## [0.6.3] - 2026-11-11 · the status line shows this machine
- Right side of the status line: the last answer's speed (tok/s, from Ollama's own timing), CPU, RAM free, GPU
  memory / load / temperature; sampled every 2 s in the background. Orange only when you should act: a much
  slower answer than this machine's best (spilled to the CPU), RAM below 2 GB or below what the model needs, a
  GPU at 85 C or more. A shorter block on narrow terminals, none on very narrow ones.
- The token count left the status line (no cost, no limit on a local model); ctx % stays (D-070).

## [0.6.2] - 2026-11-11
- `mitra score` (or any `mitra <command>`) typed in the chat now says to run it in another terminal, instead of being explained as a question.

## [0.6.1] - 2026-11-11 · deep dive: code review of steps 0-3 + debugging on real records
- Follow-ups keep their tools: "still not working", "try again", "no, use pytest" after a fix; "why?" after
  a code question reads the code. "run the tests", "commit the changes", "the tests are failing" work with
  tools; "write a prd" / "rewrite this paragraph" are writing; "rename X" is a small change.
- `/plan` never gets an old discussion; "can you fix X? think it through" fixes it.
- `thinking = "on"|"off"` in mitra.toml wins again; your notes are no longer sent twice.
- `mitra report` no longer counts planned or "where did we stop" turns as empty answers.
- Test and dev workspaces never reach your ~/.mitra store; a timed-out score case stops for real.
- 10 review findings + 3 from debugging: E-083..E-095.

## [0.6.0] - 2026-11-11 · `mitra score`: the measuring set (D-068 step 3) + fixes from a live session
- `mitra score` runs the measuring set and keeps one row per run in results/scores.jsonl: sorting (no model),
  writing, explain, ideas/review, small and medium coding tasks (hidden tests). `--quick` skips the coding
  tasks, `--remote` runs on Kaggle, `--validate` checks the set, `--history` shows past scores. First: sorting 46/46 · writing 0/3 · explain 4/4 · ideas 1/2 (15 min, 2026-11-11 01:03).
- Talking an idea through ("can we brainstorm on this", "i feel ...") is answered, not planned; "ok lets build
  it" then plans it with the discussion.
- The planner streams, so the Kaggle tunnel no longer cuts it after 120 s (Cloudflare 524).
- The Kaggle-ended report no longer names an old night run.
- A mail to your manager "for a family function" is writing, not code.

## [0.5.1] - 2026-11-10 · brainstorming and reviews about your code (D-068 step 2b)
- "brainstorm ideas to make the game harder", "review game.py", "pros and cons of …" read the code first
  (explainer); ideas come as 3-5 options with trade-offs, and "go with option 2" builds the one you pick.
- "update the plan with …" / "add a task to plan.md" edit the plan in place instead of planning a feature.

## [0.5.0] - 2026-11-10 · questions about code (D-068 step 2)
- A question about the project ("explain the game logic", "where is the API defined?") gets read-only tools
  (list_files, search, read_file) and 6 steps; the last step has no tools, so there is always an answer, with
  path:line references. A vague one may be answered with up to 2 short questions. Live: 8-22 s on a small project.
- Recorded per question: steps used, budget hit, files read, files cited, line references, asked back.

## [0.4.0] - 2026-11-10 · everyday chat + records for self-improvement (D-068, docs/BUILD_ORDER.md)
- Small talk, writing (mails, messages, summaries, rewrites, translations, "make it shorter" after one) and general
  questions are sorted without a model and answered in one call with no tools and thinking off. Live on mimo-v2.6:9b:
  "hi" 1.0 s, a team mail 3.1 s, first word 0.3-0.5 s.
- `~/.mitra/me.md` (name, signature, tone, stack; created on the first start) and `.mitra/notes.md`, read every turn.
- `/copy`: the last answer to the clipboard.
- Thinking off by default; on only for the planner and the debugger.
- Every turn records its kind, path, machine, thinking, notes version and time to the first word; quiet signals
  (asked again, stopped, `/undo`, `/copy`); plan-first and "where did we stop" are counted as turns.

## [0.3.0] - 2026-11-10 · plan first, then small steps (D-065, docs/PLAN_FIRST.md)
- "Where did we stop?" answered from Mitra's records (resume brief, also in the prompt), no model call.
- Requests sorted without a model: resume / question / small / big; `/plan <task>`, `/do <task>`.
- Bigger changes: a short runnable plan from a small context pack (file tree + outlines), Go / Change / Save /
  Cancel, steps run one at a time with fresh context and their own test, failed steps re-planned once,
  `.mitra/resume.md` written.
- Large files read without a range give an outline first.
- Fixed: slash commands were stored as project-memory topics (a model chased `/logs/...` paths); wrong paths
  now suggest the real file; `run_command` states its rules; Python warning blocks folded on screen.

## [0.2.2] - 2026-11-10 · Mitra asks before using Kaggle (D-064)
- At every start: one check (key valid, phone verified, hours left) and one of five cases: no key → offer to
  connect; key works but not decided → "Use it? when I need it (default) / start now / later / no"; decided →
  one line or a background start; a problem → one line with the fix; already running → the status line.
- `/kaggle use now|when-needed|never` and `mitra kaggle use ...`; `/kaggle` shows the setting.
- 'when-needed' starts Kaggle on the first write work without asking again; 'Later' asks again the next day.

## [0.2.1] - 2026-11-10
- Fixed: the memory line suggested closing Windows' own `MemCompression` (E-068).

## [0.2.0] - 2026-11-10 · Kaggle and laptop, seamlessly (D-062, docs/BACKENDS.md)
- Status line shows where the model runs and the Kaggle hours left (`☁ kaggle · … · 28.1 h left` / `💻 laptop`).
- Read work (plan mode, planner, reviewer) on the laptop, write work on Kaggle; switches between turns.
- Kaggle ends (idle, time limit, quota, tunnel): laptop model (quietly smaller if RAM is short), a report of what
  was done in `.mitra/reports/`, and Mitra stops; also when it ended while Mitra was closed, and mid-turn.
- A long chat is compacted before moving to the laptop's smaller context.
- Write work with no Kaggle running: start it in the background (asked once per session).
- First start: Mitra offers to connect a free Kaggle GPU (guided).

## [0.1.2] - 2026-11-10
- Fixed: after a Kaggle run stopped by itself, `mitra` said "no compatible local Ollama models"; it now says the Kaggle GPU has stopped and uses this machine (E-067).

## [0.1.1] - 2026-11-10
- `mitra kaggle setup <token>`: Kaggle's Settings → API now gives a token string (saved to ~/.kaggle/access_token); a downloaded kaggle.json still works (`mitra kaggle setup` finds it).
- No more 15-line Kaggle library sign-in help printed twice: Mitra's own short steps only.
- README Kaggle steps follow the current Kaggle Settings page.

## [0.1.0] - 2026-11-10 · colleague preview
First version for other people to try on their own projects.
- Terminal chat on local models (Ollama): reads code, edits with your approval, runs tests and fixes failures;
  `/undo`, ask / auto-edit / plan modes, role routing (`/role`), live `/model use` and `/context`.
- Unattended plans: `/plan template`, `/plan check`, `/run plan.md <hours>` (background night runs, report).
- `/free`: tick big programs, Mitra closes them to make RAM room for the model (D-059).
- Kaggle GPU: `mitra kaggle setup|start|stop|status` and `/kaggle`, your free weekly hours at 256K context, no browser
  (D-060, D-061); `mitra remote` for any remote Ollama.
- Local dashboard (`mitra dashboard`), `/good` `/bad` feedback, everything recorded only in `~/.mitra/`.
- Deep-dive review fixes E-050..E-066 (see docs/FIX_LOG.md).
- README rewritten for first-time users; feedback and bug issue forms; dependencies pinned to tested versions.

- Project docs: scope, checklist plan, decisions, error/fix/lesson logs, progress log, evals, case study, posts.
- Imported local-codex code (561 tests passing); package renamed to `mitra` (`mitra` and `codemitra` commands).
- CI: tests on Linux and Windows, lint gate for syntax errors and undefined names, gitleaks secret scan.
- Fixed: model-advisor command crashed after finishing (E-004).
- Benchmark v0: fake payments SDK, demo shop service, 10 validated tasks with hidden tests (`bench/bench.py`).
- Bench tooling: logging proxy, preflight, run recorder with completion markers (`bench/proxy.py`, `bench/preflight.py`, `bench/run.py`).
