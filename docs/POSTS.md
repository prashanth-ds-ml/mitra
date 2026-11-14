# Posts (building in public)

One LinkedIn post per release. Draft here first; after posting, add the link and what people said (questions and
requests become candidates for "Ideas to test" in SCOPE.md).

## Template
1. Hook: one number or chart
2. What I tried (2-3 lines)
3. What happened, including what failed
4. One lesson other engineers can use
5. Link to the release + what's next
One image, ~200 words, no hype words.

## Index

| # | Release | Title | Status | Link | Notable feedback |
|---|---|---|---|---|---|
| 1 | v0.0 | Why coding agents break on your laptop | planned | - | - |
| 2 | v0.1 | Cutting the agent prompt from ~12K to ~3K tokens | planned | - | - |
| 3 | v0.2 | Same model, five agents: the table | planned | - | - |
| 4 | v0.3 | % solved on my GPU, and what the cloud cost for the rest | planned | - | - |
| 5 | v1.0 | Article: method, results, honest limits | planned | - | - |

## Drafts

### v0.8.0 · draft (2026-11-14) · "I pasted a game spec and my assistant asked me 'should I start?' six times"

I pasted a full game spec into CodeMitra, my coding assistant for small local models, and said "yes".
It answered "Should I create all the initial files now?". I said yes six more times. Same question, word for word.

What happened: before acting, the 9B model decides "talk or work?". It kept choosing "talk", and once its question
sat in the history, it copied it. The fix is not a better prompt: when the assistant offered work and you say yes,
the harness starts that work; a repeated answer is not accepted.

The next session (22 turns building the game) found six more faults: "fix it" stuck in read-only mode, another
project's tests reporting green, "fixed" when nothing changed. Each is now a test built from the real turn.

Lesson: my first fix passed 7 tests and never fired live, because real answers end in **bold** questions.
Build a fix's tests from the model's real output, then replay the session that found it.

Also new: the assistant reads your next message as feedback ("why don't you…" = it went wrong), so every turn is
labelled without asking. And it is called CodeMitra again.

v0.8.0: github.com/prashanth-ds-ml/codemitra · next: friends' sessions as the test set.
