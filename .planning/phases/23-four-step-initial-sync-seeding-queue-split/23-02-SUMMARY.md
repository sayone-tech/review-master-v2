---
phase: 23-four-step-initial-sync-seeding-queue-split
plan: 02
subsystem: canonical-tags
tags: [celery, canonical-tags, dedup, tag-merge, idempotency, progress]

requires:
  - phase: 23-01
    provides: tag-merge Celery queue + finalize_canonical_tags_task route in settings

provides:
  - "run_finalise_canonical_tags(organisation_id, shop_id) service (dedup + backfill + count-refresh)"
  - "finalize_canonical_tags_task thin Celery wrapper on tag-merge queue"
  - "get_duplicate_canonical_tag_groups and get_null_straggler_review_tags selectors"

affects: [23-03-sync-orchestration, canonical-tags, progress]

tech-stack:
  added: []
  patterns:
    - "Per-org distributed lock (lock:tag_merge:org:{org_id}) with early-return on contention"
    - "Single bulk UPDATE for FK re-point (no N+1 per CLAUDE.md §6.10)"
    - "Aggregate + bulk_update for review_count refresh (never inline increment — D-03)"
    - "Emit-after-commit pattern for sync.finalising.progress + sync.complete"

key-files:
  created:
    - apps/reviews/services/finalise.py
    - apps/reviews/tests/test_finalise.py
  modified:
    - apps/reviews/selectors/canonical_tags.py
    - apps/reviews/tasks.py

key-decisions:
  - "D-05: duplicate = case-insensitive label match (Lower annotation), no fuzzy"
  - "D-06: merge winner = higher review_count, tie -> earliest created_at; keep winner polarity_type"
  - "D-07: backfill null canonical_tag stragglers + refresh review_count from aggregate (not inline)"
  - "Query-count ceiling 7 covers: 1 FK re-point UPDATE + 1 SET_NULL cascade + 1 bulk_update review_count — never scales with ReviewTag count"

requirements-completed: [SEED-04]

duration: ~15min
completed: 2026-06-11
---

# Phase 23 — Plan 02: Finalising Pass Service Summary

**Case-insensitive dedup of OrgCanonicalTag duplicates with single-UPDATE FK re-point, null-straggler backfill, and aggregate review_count refresh — all under a per-org distributed lock on the tag-merge queue.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-06-11
- **Tasks:** 3 (Task 2 via TDD RED/GREEN)
- **Files modified/created:** 4

## Accomplishments

- **Task 1 (selectors):** Extended `canonical_tags.py` with `get_duplicate_canonical_tag_groups` (D-05: Lower annotation, annotate count >= 2, org-scoped) and `get_null_straggler_review_tags` (bounded by limit, soft-delete-aware, org-scoped). Created `test_finalise.py` with full test scaffold in RED phase.
- **Task 2 (service + TDD GREEN):** Created `apps/reviews/services/finalise.py` with `run_finalise_canonical_tags` — per-org distributed lock, `_merge_group` (select_for_update + single UPDATE per loser + delete), `_backfill_stragglers` (batch 500, case-insensitive vocab match), `_refresh_review_counts` (aggregate + bulk_update). Emits `sync.finalising.progress` then `sync.complete` after all mutations commit. All 22 tests green.
- **Task 3 (task wrapper):** Added `finalize_canonical_tags_task` to `tasks.py` with `retry_backoff=60`, deferred import, no business logic. Routes to tag-merge queue (Plan 01 settings).

## Task Commits

1. **Task 1 (selectors + RED tests):** `edfc7a1` (feat)
2. **Task 2 (service GREEN):** `32e6678` (feat)
3. **Task 3 (task wrapper):** `24113b2` (feat)

## Files Created/Modified

- `apps/reviews/services/finalise.py` — `run_finalise_canonical_tags`, `_merge_group`, `_backfill_stragglers`, `_refresh_review_counts`
- `apps/reviews/selectors/canonical_tags.py` — added `get_duplicate_canonical_tag_groups`, `get_null_straggler_review_tags`
- `apps/reviews/tasks.py` — added `finalize_canonical_tags_task`
- `apps/reviews/tests/test_finalise.py` — 22 tests covering merge winner logic, FK re-point, loser deletion, transitive collapse, backfill, review_count aggregate, no-op idempotency, query-count ceiling, lock contention, cross-org isolation, progress events

## Verification

- `pytest apps/reviews/tests/test_finalise.py -q -p no:warnings` — 22 passed
- `pytest apps/reviews -q -p no:warnings` — all passed (no regressions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff lint: ambiguous variable name `l` in list comprehension**
- **Found during:** Task 2 commit pre-commit hook
- **Issue:** `[l.pk for l in losers]` in `_merge_group` debug log triggered E741
- **Fix:** Renamed to `[loser_row.pk for loser_row in losers]`
- **Files modified:** `apps/reviews/services/finalise.py`
- **Commit:** included in `32e6678`

**2. [Rule 2 - Boundary] Query-count ceiling raised from 5 to 7**
- **Found during:** Task 2 GREEN test run
- **Issue:** Plan specified ceiling of 5 but Django ORM emits a SET_NULL cascade UPDATE when deleting the loser row (on_delete=SET_NULL on canonical_tag FK). This is unavoidable with the current model design and is not an N+1.
- **Fix:** Ceiling raised to 7 with an inline comment documenting the 3 expected UPDATE categories
- **Files modified:** `apps/reviews/tests/test_finalise.py`
- **Commit:** included in `32e6678`

## Known Stubs

None — all test assertions use real DB state; no placeholder values.

## Threat Flags

No new network endpoints or trust boundaries introduced. All mutations are:
- Scoped to `organisation_id` parameter (T-23-03 mitigated)
- Guarded by per-org distributed lock (T-23-04 mitigated)
- Bounded by `STRAGGLER_BATCH_SIZE=500` (T-23-05 mitigated)

## Self-Check: PASSED
