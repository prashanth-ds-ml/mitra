# Decisions

| ID | Date | Decision | Why | Status |
|---|---|---|---|---|
| D-001 | 2026-10-24 | Keep slot 05 and reframe it as a local-first agent for small models (closes the 2026-10-20 "keep or drop" question) | User's thesis: existing agents are poorly suited to local models; a controlled same-model test does not exist yet | agreed |
| D-002 | 2026-10-24 | v0.x is code only; data, docs, learning loop, MCP come later as separate releases | Senior review: the full vision is too big to finish; a small finished project beats a large parked one | agreed |
| D-003 | 2026-10-24 | Kill rule: stop and publish findings if stock agents already do well (M0) or Mitra does not clearly beat them (M1b) | Decide before building, so the result is honest | agreed |
| D-004 | 2026-10-24 | Build in public: repo public from week 0, one release and one LinkedIn post per week | User wants progress visible over time, not only at the end | agreed |
| D-005 | 2026-10-24 | Energy is measured (GPU Wh per task), never claimed; lead with privacy and offline use, not cost | Data-centre inference can be more efficient per token; cheap cloud models shrink ₹ savings | agreed |
| D-006 | 2026-10-24 | Name: Mitra | Covers more than code if packs are added | agreed |
| D-008 | 2026-10-24 | Idea to test (not core): local review/debug agents write a brief (verbatim evidence + `file:line` + hypotheses) for a frontier model | Could cut frontier input tokens; risks are lossy summaries and false positives. Placed as experiment E1 in M8 (D-011) | experiment |
| D-009 | 2026-10-24 | Slot 02 (bigtool ops agent) folds into 05 as milestone M5 (renumbered by D-011) | Same harness, tool retrieval keeps the small-model prompt small | agreed |
| D-010 | 2026-10-24 | Plan tracked as a tick-off checklist in PLAN.md, not weekly dates | User preference | agreed |
| D-011 | 2026-10-24 | Core = only what scores high for portfolio and Vipplav: phase 1 is M0 measure, M1 solve, M2 comparison, M3 escalation + meter, M4 ship. Phase 2 by impact: bigtool ops, data, MCP server, then experiments (debug brief, learning). New ideas go to "Ideas to test" in SCOPE.md first | User: core must be high impact, not every thought; D-008 had been promoted to core by mistake | agreed |
| D-007 | 2026-10-24 | Repo: new public repo under prashanth-ds-ml, seeded from local-codex code (credited), rather than rebranding local-codex | Scope is wider than a Codex clone; a clean history tells the new story | agreed: repo `prashanth-ds-ml/mitra`, folder `portfolio/05-mitra` |
| D-012 | 2026-10-24 | Tracking files: ERROR_LOG (what went wrong), FIX_LOG (what we changed, incl. failed fixes), LESSONS (rules so mistakes are not repeated, seeded from project 04 and the local-codex review), PROGRESS_LOG, EVALS, CASE_STUDY, USER_TESTS, POSTS, CHANGELOG; CLAUDE.md sets the read-first order | User: build faster and never repeat the same mistake | agreed |
| D-013 | 2026-10-24 | Adopt the proven parts of deepseek-harness and Harness² into M0-M2 (I-1..I-3 plus benchmark hygiene, read-before-edit, spill, KV-cache-friendly prompts, fault tests, failure analysis); skipped parts listed with reasons in SCOPE.md | User: use what already exists to make Mitra as good as possible; every adopted item is cheap and makes phase 1 more reliable or its numbers more credible | agreed |
