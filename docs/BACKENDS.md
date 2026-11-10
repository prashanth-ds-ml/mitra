# Kaggle and laptop: switching without friction (D-062)

Goal: you never have to think about where the model runs. Kaggle when it is up and the work needs it, the laptop
otherwise; one plain line whenever Mitra switches; never a lost turn or a confusing error.
Brainstorm and the user's answers: 2026-11-10. This page is the build order; each step is built, tested and shown to
the user before the next one starts.

## Agreed (the user's answers)

1. **Kaggle stops** (while you are away, or in the middle of a turn): Mitra switches to the laptop model, writes a
   detailed report of what was done, and **stops**. No automatic continuation, no automatic Kaggle restart.
2. **Read work on the laptop, write work on Kaggle.** Note: Kaggle counts session time, not requests, so this saves
   hours only because Kaggle then only needs to run while there is write work (the 30 min idle stop ends it after).
3. **Laptop short of RAM:** quietly use a smaller model (the report and the status line say which).
4. **New users:** offered to connect Kaggle at the very first start (guided, about 2 minutes).

## Still to decide (asked before the step that needs it)

- **a.** (B5) Write work and Kaggle is not running: ask "Start Kaggle for this?" each time, or start it in the
  background and keep working on the laptop until it is ready?
- **b.** (B5) In the normal modes the chat role does both reading and writing in one turn, and a turn cannot change
  machine half way. Proposal: route by **mode and role**, not by guessing the message: plan mode and the planner /
  reviewer roles = laptop; ask / auto-edit with the chat, builder, tester, debugger roles = Kaggle when it is up.

**Status 2026-11-10: B0-B6 built and tested (unit + 6 driven chat tests), v0.2.0.** Defaults taken by the user's "go with your defaults": a = ask once per session, start in the background; b = route by mode and role.

## Build order

Each step: what it does · where · done when (tests that fail without it + a live check).

### B0. One place that knows where the model runs
- `app/backend.py`: the current backend (`laptop` / `kaggle`), the remote's health (last answer, checked every 60 s
  in a background thread, only status calls so it never counts as Kaggle use), hours left (cached, refreshed every
  10 min), and `use(...)` which swaps model, context and URL in one go (today this is spread over `remote.apply`,
  `unapply`, `_apply_role` and `/kaggle`).
- Done when: unit tests for state changes and the health check (fake remote up / down / flapping); the existing
  `/kaggle` and start-up code use it; no behaviour change yet.
- Size: small. Everything after builds on it.

### B1. Status line: where am I, how many hours
- Status line and header: `☁ kaggle · mimo 256K · 28.1 h left` or `💻 laptop · mimo 128K`; amber under 1 h left,
  red when the remote stops answering.
- Where: `app/ui/status.py`, `app/ui/header.py`, `app/main.py`.
- Done when: rendering tests for both backends and the warnings; live: start on Kaggle, see the line; stop it, see
  the line change within a minute.

### B2. Laptop model that fits, quietly
- A fallback list, default from what is installed, e.g. `mimo-v2.6:9b @128K → qwen3.5:4b @64K`; the first that
  passes the memory check (`fit.check` ok or tight) is used; no question asked. Setting `laptop_models` in
  mitra.toml to change it.
- Where: `app/backend.py`, `app/fit.py`.
- Done when: tests with fake memory figures (plenty → first, short → second, nothing fits → smallest with a ✗ line);
  live: with ~4 GB free it picks the 4B without asking.

### B3. Kaggle ended: laptop, report, stop
- Detected at three points: (1) start-up (it ended while Mitra was closed: report on the last session from the
  records), (2) the health check between turns, (3) a failed model call in the middle of a turn (one quick retry for a
  tunnel blip first, then give up on Kaggle).
- Then: switch to the laptop model (B2), write `.mitra/reports/kaggle-ended-<time>.md` and show it, end the turn
  cleanly (recorded as `kaggle_ended`, not as a failure of the model), and wait for you.
- The report: **facts from Mitra's own records** (what you asked, files changed with `/undo` available, last test
  result, plan / night progress, Kaggle time used this session, hours left) + **a short summary by the laptop model**
  (done, half done, suggested next step). Night runs (`mitra solve`) do the same: report, stop.
- Where: new `app/core/handoff.py` (report), `app/core/chat.py` (a `RemoteGone` error from the model call),
  `app/main.py`, `app/core/cli.py`.
- Done when: tests: Kaggle dies before a turn / mid-turn / at start-up → laptop model in use, report file with the
  facts, turn stopped, nothing lost from the chat history; live: `mitra kaggle stop` from another terminal while a
  turn runs.

### B4. Context guard when moving to the smaller context
- Before the first call on the laptop: if the conversation is larger than ~80% of the laptop context, compact it
  first (the existing compaction), and say so.
- Where: `app/main.py` (the compaction already there), `app/backend.py`.
- Done when: test with a 200K-token history moving from 256K to 128K → compacted, the next call fits.

### B5. Read on the laptop, write on Kaggle
- Routing by mode and role (decision b): plan mode, planner, reviewer → laptop; chat (ask / auto-edit), builder,
  tester, debugger, `/run` nights → Kaggle when it is up, laptop otherwise. Switches happen between turns only
  (B4 guards the context). Write work with Kaggle not running → decision a.
- Where: `app/backend.py`, `app/core/roles.py`, `app/main.py`.
- Done when: tests per mode / role with Kaggle up and down; live: shift+tab to plan mode → `💻 laptop`, back →
  `☁ kaggle`.

### B6. First start: offer Kaggle
- First `mitra` on a machine (no `~/.mitra/onboarded`): one menu: *Yes, guide me* (opens kaggle.com/settings in the
  browser, says what to click, waits for the pasted token, runs `kaggle setup`, offers `kaggle start`) · *Later*
  (`/kaggle setup` any time) · *No, this machine only* (never asked again).
- Where: `app/main.py`, `app/kaggle.py`.
- Done when: tests for the three answers and a bad token; live: fresh-clone install with an empty Mitra home.

### B7. Release
- README (the switching, the first-start offer), CHANGELOG, USER_TESTS, all tests, fresh clone from GitHub,
  push as v0.2.0 for the colleagues.

## Later (not this round)
- Tunnel self-repair: the notebook restarts a dead tunnel; Mitra reads the new address from the Kaggle log.
- Night runs that carry on on the laptop instead of stopping (B3 stops them for now, as agreed).
- Quota guard that stops Kaggle cleanly before the hours run out (B1 only warns).
