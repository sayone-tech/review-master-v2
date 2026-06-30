# Phase 23: Four-Step Initial Sync, Seeding & Queue Split - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-10
**Phase:** 23-four-step-initial-sync-seeding-queue-split
**Areas discussed:** 4-step mapping & seed UX, Seed selection & size, Finalising dedup behavior, Global rate limiter scope

---

## 4-step mapping & seed UX

| Option | Description | Selected |
|--------|-------------|----------|
| Seed=Building, Bulk=AI Enrichment | 'Building Tag Vocabulary' = sequential seed of first N; 'AI Enrichment' = parallel bulk of the rest; both real GPT enrichment, no review enriched twice | ✓ (Claude) |
| Building is a distinct pre-pass | Separate vocabulary-only pass, then AI Enrichment re-enriches ALL reviews | |
| Cosmetic 4 labels | One internal flow; 4 labels advanced by overall % | |

**User's choice:** Delegated to Claude — "you decide the better approach".
**Notes:** Chose the faithful mapping (fewest GPT calls, no double-enrichment). → CONTEXT D-01/D-02.

---

## Seed selection & size

| Option | Description | Selected |
|--------|-------------|----------|
| Newest-first, 50, configurable | Seed from 50 most recent reviews; `SEED_PHASE_SIZE` default 50 | ✓ (Claude) |
| Oldest-first, 50, configurable | Seed from 50 oldest, chronological | |
| Fetch-order, 50, configurable | Seed from Google's return order | |

**User's choice:** Delegated to Claude — "you decide the better approach".
**Notes:** Newest = most representative of current tag patterns; configurable per D-02 precedent. → CONTEXT D-03/D-04.

---

## Finalising dedup behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Merge + refresh count (higher review_count wins) | Case-insensitive label merge, higher-count winner (tie→earliest), backfill stragglers, refresh review_count cache, on tag-merge queue | ✓ (Claude) |
| Merge, keep first-created winner | Same, but first-created always wins | |
| Backfill only, defer merge | Only backfill nulls + refresh count; defer merging to Phase 25 | |

**User's choice:** Delegated to Claude — "you decide the best approach".
**Notes:** Honors SEED-04's string-match merge and resolves the Phase 22 D-03 review_count-cache deferral. → CONTEXT D-05/D-06/D-07.

---

## Global rate limiter scope

| Option | Description | Selected |
|--------|-------------|----------|
| Build Redis token bucket now | Cross-worker global limiter (~500/min) via `rate:openai:*`; per-worker stays secondary | ✓ (Claude) |
| Defer global limiter further | Queue split only; keep per-worker; revisit on TPM errors | |
| Build it, opt-in via setting | Global limiter behind an off-by-default setting | |

**User's choice:** Delegated to Claude — "you decide the best approach".
**Notes:** D-06 (Phase 22) explicitly deferred the global limiter to THIS phase; parallel bulk enrichment makes it load-bearing → always-on. → CONTEXT D-08/D-09/D-10.

---

## Claude's Discretion

All four discussed areas were delegated to Claude. Decisions recorded as LOCKED in CONTEXT.md (D-01..D-10), grounded in Phase 22 precedent (D-02/D-03/D-06) and ROADMAP success criteria. Additional discretion items (event/type schema, high/low routing mechanism, token-bucket internals, review_count cache-vs-aggregate) noted under "Claude's Discretion" in CONTEXT.md.

## Deferred Ideas

- Fuzzy/semantic duplicate merging (beyond case-insensitive) — Phase 25.
- Weekly polarity auto-reclassification + visibility — Phase 24.
- Org Admin Tags page (rename/merge UI), dashboard polarity split — Phase 25.
- Superadmin data reset — Phase 26.
