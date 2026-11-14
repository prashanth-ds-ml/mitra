# Obsidian memory + handoff plan (I-10, I-9, draft 2026-11-07)

Status: **plan finalized with the user 2026-11-07, waiting for the go to build.** Nothing is built. User's ask: "use obsidian as central part of mitra to
handle files and memory ... a pop up when the context is full with multiple compactions and its safe to start a
fresh session and continue ... mitra should automatically write a handoff report that mitra can read and
understand easily".

## What exists today
- Memory per project in `.codemitra/`: `context.md` (topics), `plan.md`, `activity.md`, `session_log.md`,
  `memory.sqlite`; loaded into the system prompt at start. **Obsidian ignores dot-folders**, so none of this shows
  in Obsidian, even though `C:\Users\prash\projects` is already one of your 11 vaults.
- Compaction (E-046): at 80% of the context the whole history is summarised by the model into one message. A
  second compaction summarises a summary, so detail is lost each time; at 256K it also re-reads ~205K tokens.
- `codemitra solve` already has a handoff for fresh rounds (`loop.handoff_note`): task, files changed, last test
  result, next step. The chat has none.
- Raw data: every record and trace in the central store (D-041). That stays the source of truth.

---

## I-9: Handoff report + "start fresh" pop-up

### When (checked at the end of a turn, never in the middle of one)
- the **second compaction** of a session is about to happen (instead of compacting again), or
- right after a compaction the prompt is **still over half** the context (the summary itself is too big), or
- `/handoff` at any time.

### What happens
1. CodeMitra **writes the handoff report first**, so nothing is lost even if you ignore the pop-up.
2. The pop-up, in the terminal (a framed box + the bell + the window title, like "ready" today):
   ```
   ╭─ Context is full (2 compactions) · safe to start fresh ─────────────────╮
   │ Handoff written: CodeMitra/handoffs/2026-11-07-1420-brick-breaker.md         │
   │ ✓ no turn running  ✓ all changes saved on disk  ✗ tests: 2 failing        │
   │ Enter = fresh session from the handoff · c = continue here · v = view    │
   ╰─────────────────────────────────────────────────────────────────────────╯
   ```
   "Safe" = no turn or approval pending and every change is on disk. Failing tests do not block it; the box says so.
3. **Fresh session** in the same window: the history is replaced by the system prompt + the handoff, a new run
   record is started and linked to the old one (`continues: <file>`). Nothing is deleted.
4. Next time you start `codemitra` in that folder: "Handoff from 14:20 found: continue from it? (Enter / n)".

### The report: facts from records, a few lines from the model
Built mostly **from what was recorded**, not from the model's memory, so it is right even when the model is weak:

| Section | Source |
|---|---|
| Frontmatter: project, time, model, context, harness version, session file, compactions, tests status | records |
| Goal: what you asked this session (your messages, short) | `turn_start` rows |
| Done: files changed with +/- lines | edit journals |
| Tests: last command and result, failing test names | last `run_tests` / tool output |
| Open problems: last errors, refused or failed tools, stops | records |
| Next steps (max 5) and things learned about the project (max 5) | **the model**, one short call |
| Where to look: `file:line` of the recent edits | journals |
| How to continue: test command, how to run the program | project note / records |

Kept under ~1,500 tokens, so the fresh session starts small and fast. Plain Markdown with frontmatter: readable by
you, by CodeMitra, and by Obsidian.

### Done when
- Unit tests: the trigger rules; a report from a fixture session has every section with the right facts;
  under the token budget; `continues:` link in the new record; the start-up question.
- Live: a playground session at `/context 32k` (so it fills quickly) triggers the pop-up; the fresh session
  continues the task and its tests pass. Recorded in EVALS.

---

## I-10: Obsidian as the center of CodeMitra's memory and context (user, 2026-11-07)
User: "i want obsidian to be one of the central tool to handle mitra memory and context related issues".

**Everything CodeMitra remembers or carries between turns and sessions lives in the vault**: project facts, session
summaries, compaction summaries, handoffs, lessons, plans. **Code stays in the projects**, handled by the file
tools. CodeMitra needs no Obsidian plugin and Obsidian need not be running: the vault is a folder of Markdown with
frontmatter and `[[links]]`; CodeMitra reads and writes it directly, and you see the same notes in Obsidian (graph,
backlinks, search, edits). If you edit a note in Obsidian, CodeMitra reads your version next time.

### What moves into the vault
| Today | In the vault |
|---|---|
| `.codemitra/context.md`, `session_log.md`, `activity.md` (hidden in Obsidian) | `projects/<project>.md` (facts) + `sessions/<date>-<project>.md` |
| compaction summary (only in memory, then lost) | appended to the session note, so every compaction is kept and readable |
| no chat handoff | `handoffs/<date>-<project>.md` (I-9) |
| `.codemitra/plan.md` | `plans/<project>-<name>.md` (the plan runner reads it from there) |
| harness rules in `~/.codemitra/harness.toml` | mirrored to `lessons.md` with why and when (the toml stays the source for the harness) |
| raw records + traces | **stay** in `~/.codemitra/data` (machine data for the dashboard and training) |

### How context is built from the vault
- **At start:** the project note + the latest handoff (if any) + the lessons that apply, within a fixed token budget
  (~2K); `[[links]]` in them are not followed automatically, so the budget holds.
- **During a session, three memory tools for the model** (about 120 prompt tokens, within the 3K budget):
  - `recall(query)`: search the vault's CodeMitra notes (titles, headings, frontmatter, text) and return the best
    short matches with their note name;
  - `remember(fact)`: add one line to the project note's "Learned" section (shown to you, deduplicated);
  - `read_note(name)`: read one note in full.
- **Compaction and handoff** write to the vault first, then shrink the chat, so nothing said in a session is lost.

### Layout (a `CodeMitra/` folder in a vault)
```
CodeMitra/
  Home.md                         index: projects, latest handoffs, what CodeMitra learned
  projects/brick-breaker.md       how to run / test, stack, facts learned, links to its handoffs + sessions
  handoffs/2026-11-07-1420-brick-breaker.md
  sessions/2026-11-07-brick-breaker.md   short summary per session (goal, outcome, files), links the handoff
  lessons.md                      the harness rules from codemitra improve, with why and when added
```

### Rules
- CodeMitra writes **only inside `CodeMitra/`**; it never edits your other notes. Writes are append-or-section edits with
  a backup of the previous version in `CodeMitra/.history/` (hidden from Obsidian), so a bad write can be undone.
- Your edits win: CodeMitra never overwrites a note you changed since it last wrote it; it appends instead.
- One-time import of each project's existing `.codemitra/context.md`, `session_log.md` and `plan.md` into the vault.
- No vault set → today's `.codemitra/` files keep working (fallback, so CodeMitra never breaks without Obsidian).
- `/doctor` shows the vault path and note counts; `/vault` opens the project note in Obsidian
  (`obsidian://open?vault=...&file=...`).
- Later, optional: `recall` over your other notes too (design docs, ideas), read-only. Off by default.

### Done when
- Unit tests: notes written with valid frontmatter and links; nothing written outside `CodeMitra/`; your edited note
  is appended to, not overwritten; startup context within budget; `recall`, `remember`, `read_note` work and stay
  inside the vault; the import moves old `.codemitra/` memory once; no-vault fallback works.
- Prompt budget test passes with the three new tools.
- Live: a session on mitra-try learns a fact with `remember`, a fresh session finds it with `recall`.
- You open the vault in Obsidian and see projects, sessions, handoffs and lessons linked (person-only, USER_TESTS).

---

## Order (vault-first, since it is now the center)
1. Vault basics: path setting, `CodeMitra/` layout, safe write (backup, your edits win), import of old `.codemitra/` memory.
2. Startup context from the vault + `recall` / `remember` / `read_note`.
3. Compaction summaries saved to the session note.
4. I-9 handoff + pop-up, writing into `handoffs/`.
5. Plans and lessons in the vault.
Each step is usable on its own; I-7 (session gains) does not touch these and can come before or after.

## Decisions (user, 2026-11-07)
| Question | Decision |
|---|---|
| Role of Obsidian | **Central** for memory and context (I-10 above); code stays in the projects |
| Vault | **A new dedicated vault**, `C:\Users\prash\MitraVault` (setting `vault_path`; CodeMitra creates it with the `CodeMitra/` layout; you open it in Obsidian once as a vault) |
| Fresh session | **Pop-up, you choose**: Enter = fresh from the handoff · c = continue here · v = view |
| Trigger | **At the 2nd compaction**, or when one compaction still leaves the prompt over half full; `/handoff` any time |
| recall scope | **Only CodeMitra's own notes** for now; your other notes are never read (can be turned on later) |
