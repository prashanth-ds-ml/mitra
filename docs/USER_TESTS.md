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

## 2026-11-10 · Kaggle remote (D-060)

Needs your Kaggle account and a real session; tested here only with the local Ollama behind the proxy.

- [ ] Kaggle: phone verified; Settings shows the weekly GPU quota (write it in STATUS)
- [ ] Import `remote/kaggle/mitra_kaggle_server.ipynb`, GPU T4 x2 + Internet on, Run All: it prints `mitra remote set ...` within ~6 min; the load line says "fully on GPU" at 262144
- [ ] Laptop: paste the line, start `mitra`: header `remote GPU`, `☁ runs on kaggle at 256K`; a chat reply streams
- [ ] `/run` a small plan on it; `mitra remote off` afterwards; stop the Kaggle session

## 2026-11-10 · `/free` (D-059)

Closing real programs needs you: automated tests use stand-ins and never close anything.

- [ ] `/free` lists Edge, Code, Chrome, Claude ... with sizes; Edge and Chrome are pre-ticked, Code and Claude are not
- [ ] space / 1-9 tick, enter closes: Edge closes like ✕ and reopens its tabs next time
- [ ] a program with a save prompt stays open: Mitra asks before forcing; "No" leaves it open
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
