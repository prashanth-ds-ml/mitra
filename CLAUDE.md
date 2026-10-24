# Mitra: rules for working in this repo

Portfolio project 05. A local-first coding agent built for small models: checked by tests, escalating to a frontier
model only when the check fails. Built in public, one release + one LinkedIn post per milestone.

## Read first, every session (in this order)
1. `docs/STATUS.md`: where things stand and the next unticked item
2. `docs/LESSONS.md`: rules learned the hard way; check the ones that touch today's work
3. `docs/PLAN.md`: the checklist; work only on the next unticked items
4. `docs/ERROR_LOG.md` open entries, if today's work touches them
Reference: `docs/SCOPE.md` (what and why), `docs/DECISIONS.md` (append-only), `docs/EVALS.md`

## Working rules
- Discuss before implementing. A new milestone starts only on the user's explicit go.
- Build only the current milestone. New ideas (yours or the user's) go to "Ideas to test" in SCOPE.md, never straight
  into PLAN.md; they become milestones only after the impact score is agreed (D-011).
- Keep it simple: no extra process, documents or stages the plan does not need.
- Before fixing a bug, search ERROR_LOG.md and LESSONS.md for the same symptom.
- Every bug, failed test or review finding → ERROR_LOG entry (E-nnn) → fix → FIX_LOG entry (F-nnn) with the regression
  test that fails without the fix. If it could happen again elsewhere, add or update a LESSONS entry (L-nnn).
- Record every benchmark result in EVALS.md, whatever it shows. Numbers in README must match `results/`.
- Test everything you can yourself (unit tests, live Ollama runs, benchmark, fresh clone, secret scan). Only
  person-only checks go to USER_TESTS.md.
- End of every working session: update STATUS.md. End of every milestone: run the "Every release" list in PLAN.md,
  add a PROGRESS_LOG row, update CHANGELOG, draft the post in POSTS.md, show the release check to the user before
  anything is pushed or published.

## Non-negotiables
- The fixed prompt + tool descriptions stay under the budget in SCOPE.md (~3K tokens); CI checks it.
- Every model call and every subprocess has a timeout. No silent truncation: context sizes set and logged.
- A failed or empty model reply is an error, never a pass.
- Per-run state lives in a run object, not module globals.
- Hidden tests decide pass/fail; the agent never sees or edits them (hashed).
- Every stock-agent config used in a comparison is committed under `bench/configs/`.
- Energy and ₹ are measured, never claimed.

## Machine and tooling
- Python: shared root venv `../../.venv` (uv); install with `uv pip`, then `uv pip check`.
- 8 GB GPU + 24 GB RAM; one model loaded at a time; free RAM >= 11-12 GB before model runs.
- Ollama: set `OLLAMA_CONTEXT_LENGTH` (default 4K truncates silently); `num_ctx` may be ignored on `/v1`.
- GitHub: push only as `prashanth-ds-ml` (`gh auth switch -u prashanth-ds-ml`).
- Use absolute paths; create a directory before `cd`/clone into it and verify where files landed.
- Long nested heredocs in the Bash tool fail; use Write/Edit. Never print `.env` files unfiltered.
- The original local-codex checkout is read-only for us; copy code from it, never edit it.
