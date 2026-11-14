# Tests only you can do

Everything automatable is run by Claude. This list is only what needs a person: your eyes, your accounts, your
machine or your judgment. Updated every release.

| ID | Milestone | What to do | Why it needs you | Status |
|---|---|---|---|---|
| U-001 | Before starting | Write the GPU model, VRAM and current power cap in STATUS.md | Your machine settings | done by Claude via `nvidia-smi` (2026-10-24) |
| U-002 | M0 | Log in to the stock agents used as baselines | Your accounts | not needed: all five run on Ollama without a login (2026-10-26) |
| U-003 | M0 | Approve the release check, then the first push and the v0.0 post | Publishing is your call | open |
| U-004 | M4 | Record the 2-minute demo video | Your voice and screen | open |
| U-005 | M4 | Fresh-eyes read of README and CASE_STUDY | Needs someone who did not write them | open |
| U-006 | M0 | Free RAM before model runs: close Edge, Chrome and the ChatGPT app, or reboot and open nothing else | Your apps and tabs | open again: done 2026-10-26 for the model check (~6 GB free), but the idle bench server was then stopped for low memory; needed before the baselines |

## 2026-11-14 · v0.8.1 for friends (D-081, D-083)

- [ ] A friend (or a spare Windows user account) clones and runs `setup.ps1`: Ollama, the model, Kaggle guidance,
      "Ready" at the end, without your help
- [ ] The Kaggle step with a new account: the page opens, the pasted token signs in, the hours show
- [ ] After the friend's invite: `codemitra share --push` lands in people/<name>/ of codemitra-logs; then
      `codemitra share --pull` on your side and `codemitra dashboard` shows it
- [ ] `exit` with at-exit = ask: "share this session?" appears; `y` pushes, any other key skips

## 2026-11-14 · Feedback on every turn (D-079)

- [ ] After an answer, press `+` (or `-`) on the empty prompt: "Turn N … marked 👍" at once, no Enter
- [ ] `+1 for this` typed as a message still types normally (only a first key on an empty prompt rates)
- [ ] After a turn that changed files: a dim "worked? + yes · − no" line (not after every turn)
- [ ] `exit` after 3+ turns: "rate this session 1–5"; a digit is noted, any other key skips
- [ ] Say "why dont you do that" after an answer: `codemitra coach` / the records show it as unhappy for that turn

## 2026-11-14 · Neon Chomp live check (E-125, E-126)

Restart CodeMitra in mitra-try (header: the new commit). On Kaggle or the laptop.
- [ ] "i cant move the orb in neon chomp, check the keyboard controls and fix them" → it changes files (no "apply it
      manually"), and the tests that run are neon_chomp's (`in neon_chomp/`), not brick-breaker's
- [ ] It answers a bold "Should I …?" with work when you say "yes", without asking again
- [ ] No "fixed" / "running successfully" while a test fails; if one slips through, the next answer corrects it
- [ ] It stays on neon_chomp (never reads brick-breaker files unless you name it)
- [ ] `python neon_chomp.py` in neon_chomp/: the arrows and WASD move the orb

## 2026-11-11 · Two self-improvement layers (D-075)

- [ ] `codemitra coach`: the report lands in ~/.codemitra/coach/ with findings from your sessions; rules it suggests show as queued
- [ ] Use CodeMitra, mark 3 wrong answers with `/bad <why>`, exit: "learning in the background" appears
- [ ] ~20 min later, start CodeMitra: "learned since last time: …" (or nothing if the rule was dropped); `codemitra harness`

## 2026-11-11 · Behaviour fixes + `codemitra improve --chat` (E-101, D-073)

- [ ] Restart CodeMitra. "good what about you" after "hi": no project talk; "i am thinking mitra": ends with a question
- [ ] "brainstorm ideas to make <your game> harder": it reads the code first, 3-5 ideas with file:line
- [ ] A wrong answer: `/bad <why>` (this is evidence for `codemitra improve --chat`)
- [ ] With CodeMitra closed: `codemitra improve --chat --dry-run` shows the evidence count and one proposed rule
- [ ] When the GPU is free (~20 min): `codemitra improve --chat`, then `codemitra harness` shows any kept rule

## 2026-11-11 · One CodeMitra + qwen3.5 (v0.7.0)

- [ ] Restart CodeMitra: the header shows qwen3.5:latest; "hi", "i am thinking…", "either X or Y" get short replies, no file reading
- [ ] "how does the paddle move?" reads the code and cites file:line; "make … " changes and tests it
- [ ] "build a feedback web app" shows a plan and asks before building
- [ ] Talk about an idea, type `exit` ("remembering this conversation"), restart, "let's continue the … idea"
- [ ] `codemitra kaggle start`: qwen3.5:latest at 256K, fully on the GPU

## 2026-11-11 · The status line (v0.6.3)

- [ ] Restart CodeMitra: bottom right shows CPU · RAM free · GPU; after an answer also tok/s
- [ ] Open Chrome tabs until RAM is low: RAM turns orange; a slow answer turns tok/s orange

## 2026-11-11 · `codemitra score` and talking ideas through (D-068 step 3, v0.6.0)

- [ ] Restart CodeMitra; "can we brainstorm on <an idea>" answers (no plan); then "ok lets build it" plans it with what you discussed
- [ ] Plan-first on Kaggle no longer fails with error 524
- [ ] `codemitra score --quick` on the laptop; once on Kaggle: `codemitra kaggle start`, then `codemitra score --remote`

## 2026-11-10 · Questions about code (D-068 step 2, v0.5.0)

- [ ] In one of your projects ask "explain how X works": an answer in under a minute with file:line, no edits
- [ ] A follow-up ("and where is Y?") builds on what it read
- [ ] A hard question: it stops at 6 steps and still answers, saying what it could not check

## 2026-11-10 · Everyday chat (D-068 step 1, v0.4.0)

- [ ] Check `~/.codemitra/me.md` (seeded with your name, signature, tone, stack): change anything that is not you
- [ ] "hi" answers at once, no tools
- [ ] "draft a mail to …" gives a mail in your voice, signed as you, nothing invented; "make it shorter" refines it
- [ ] `/copy`, then paste into your mail app: the text arrives intact
- [ ] A code request ("fix the failing test in …") still works with tools as before

## 2026-11-10 · Plan first (D-065, v0.3.0)

- [ ] "where did we last stop": the brief appears at once (no tool calls)
- [ ] A big request (e.g. "add a pause menu and a high score file"): a plan, then Go builds it step by step
- [ ] Change it: say what to change; the plan is redone; Save: `/run <name>.plan.md 4` works
- [ ] Reading a big file shows an outline, then the model reads only a part

## 2026-11-10 · Kaggle start-up question (D-064, v0.2.2)

- [ ] Your next start (key set, not decided): asked once, "Yes, when I need it" pre-selected; then one ready line
- [ ] Friend's first start (no key): "Use a free Kaggle GPU? Yes, guide me / Later / No"
- [ ] `/kaggle use now`: Kaggle starts in the background; `/kaggle` shows the setting

## 2026-11-10 · Kaggle/laptop switching (D-062, v0.2.0)

- [ ] Status line shows `☁ kaggle · … h left` on Kaggle and `💻 laptop` after `/kaggle stop`
- [ ] shift+tab to plan mode: next message runs on the laptop (one ☁/💻 line); back: on Kaggle
- [ ] Stop the Kaggle run from kaggle.com while CodeMitra works: report in `.codemitra/reports/`, your message back in the box
- [ ] Write work with Kaggle off: asked once; Yes starts it in the background and the status line shows progress
- [ ] Fresh machine (empty ~/.codemitra): first start offers Kaggle; Yes opens the settings page and takes the token

## 2026-11-10 · `codemitra kaggle` (D-061)

- [ ] With CodeMitra closed: `uv tool install --reinstall -e C:\Users\prash\projects\langchain\portfolio\05-mitra` (adds the kaggle package)
- [ ] `codemitra kaggle status`: your hours (used / 30 / reset)
- [ ] `codemitra kaggle start`: stages, then ready within ~8 min; `codemitra` header says remote GPU and shows the hours line
- [ ] In the chat: `/kaggle stop` switches back to this machine; Kaggle shows the run ended; `/kaggle start` switches live
- [ ] Leave it unused 30+ min: the run ends by itself

## 2026-11-10 · Kaggle remote (D-060)

Needs your Kaggle account and a real session; tested here only with the local Ollama behind the proxy.

- [ ] Kaggle: phone verified; Settings shows the weekly GPU quota (write it in STATUS)
- [ ] Import `remote/kaggle/codemitra_kaggle_server.ipynb`, GPU T4 x2 + Internet on, Run All: it prints `codemitra remote set ...` within ~6 min; the load line says "fully on GPU" at 262144
- [ ] Laptop: paste the line, start `codemitra`: header `remote GPU`, `☁ runs on kaggle at 256K`; a chat reply streams
- [ ] `/run` a small plan on it; `codemitra remote off` afterwards; stop the Kaggle session

## 2026-11-10 · `/free` (D-059)

Closing real programs needs you: automated tests use stand-ins and never close anything.

- [ ] `/free` lists Edge, Code, Chrome, Claude ... with sizes; Edge and Chrome are pre-ticked, Code and Claude are not
- [ ] space / 1-9 tick, enter closes: Edge closes like ✕ and reopens its tabs next time
- [ ] a program with a save prompt stays open: CodeMitra asks before forcing; "No" leaves it open
- [ ] the last line shows GB freed and a new ✓/⚠/✗, and the model then loads

## 2026-11-06 · Terminal keys (D-035)

Real Windows Terminal, `python -m app.main`. Automated tests drive the same key bindings through a simulated input;
these need a real console and a person.

- [ ] Shift+enter makes a new line; enter sends; alt+enter and ctrl+j also make a new line
- [ ] ↑↓ move between lines in a multi-line prompt; at the top line ↑ shows the previous prompt (also after a restart)
- [ ] Ctrl+←/→ jump words; ctrl+backspace deletes a word; ctrl+r finds an earlier prompt
- [ ] Typing `/` opens the command menu with descriptions; `@ga` offers `snake/game.py`
- [ ] Pasting 40+ lines shows `[pasted text #1: N lines]`; the model receives the full text
- [ ] Esc while the model writes stops it and keeps the partial answer; text typed meanwhile is in the next prompt
- [ ] Shift+tab changes the mode in the status line (ask → auto-edit → plan)
- [ ] A command with long output shows 10 lines and `+N lines (ctrl+o)`; ctrl+o prints the rest
- [ ] An approval rings the bell / flashes the taskbar and the tab title says "waiting for you"
- [ ] Ctrl+l clears the screen; ctrl+c clears the input; ctrl+c twice on an empty line quits
