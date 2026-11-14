# Case study: CodeMitra

One page for outside readers (recruiters, clients, engineers). Written at M4 (v1.0); updated only when results change
materially. Details live in [PROGRESS_LOG.md](PROGRESS_LOG.md) and [EVALS.md](EVALS.md).

## Problem
(Coding agents are built for frontier models; on a small local model they break. Evidence from M0.)

## Approach
(Harness built for small models; test-gated escalation; cost meter.)

## Results
(Headline numbers from EVALS.md.)

## What did not work
(Honest list.)

## Lessons
(Top 3-5 from LESSONS.md that other engineers can use.)

## What's next
(Phase 2 items chosen by impact.)

## Sprint log

### 2026-11-12 to 11-14 · from a yes-loop to a one-command friends release (v0.8.0, v0.8.1)
- **Trigger:** the user pasted a game PRD; CodeMitra answered "Should I create all the initial files now?" and the
  user said yes six times: the same question, word for word (E-125). The next 22-turn session found six trust
  faults (E-126): "fix it" stuck in a read-only phase (5 turns of "apply it manually"), another project's tests
  reporting green, false "fixed" / "running successfully", drift to the wrong project, a 524 reported as "Kaggle
  ended".
- **What worked:** reading the user's real records turn by turn; tests built from the real turns (44 for E-126);
  replaying the real conversation, which reproduced the bug where a clean test case could not (old logic started work
  1 of 3 times); replaying the new claim check over the 22 live answers (12 caught).
- **What did not:** E-125's first fix passed 7 tests and never fired live: real answers end in **bold** questions
  and add a line after them (L-049). A blanket rename rule missed `Mitra` after `
`; heredoc and sed edits mangled
  backslashes again (use Edit). A stale `~/.codemitra` from July nearly replaced the real 322 MB home in the
  rename (caught, moved aside).
- **Built:** feedback on every turn from the next message + one key (D-079: 11 unhappy + 13 happy labelled on 169
  old turns with no action); the rename back to CodeMitra (D-080, folders moved with nothing lost); shared sessions,
  light and scrubbed, to a private logs repo (D-081: 0 leaks on all 27 real sessions); one-command setup (D-083,
  end-to-end on a fresh Windows clone).
- **Direction set by the user (D-082):** CodeMitra must learn by itself first; a frontier coach comes in only when it
  is measurably stuck, and then only guides.

