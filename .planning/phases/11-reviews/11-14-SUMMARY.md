---
phase: 11-reviews
plan: "14"
subsystem: api
tags: [django, celery, redis, auditlog, token-bucket, google-sync]

# Dependency graph
requires:
  - phase: 11-reviews
    provides: sync.py pagination loop, progress.py token_bucket_depleted helper, AuditLog model

provides:
  - token_bucket_depleted() gating inside fetch_and_persist_reviews pagination loop (SYNC-09 closed)
  - review.fetched AuditLog row per persisted page with {page, count, trigger} payload (SYNC-10 closed)

affects: [11-VERIFICATION.md, sync service consumers, audit reporting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Rate-limit guard before fetch: token_bucket_depleted() checked BEFORE increment and list_reviews call — prevents silent over-counting when halting"
    - "Per-page audit trail: AuditLog(entity_type='review', action='review.fetched') written after each _persist_page success"
    - "Clean exit on depletion: loop breaks with logger.warning; function completes normally (soft-delete + sync.completed) — no exception raised, no Celery retry triggered"

key-files:
  created: []
  modified:
    - apps/reviews/services/sync.py
    - apps/reviews/tests/test_sync_service.py

key-decisions:
  - "token_bucket_depleted() is the FIRST check in while-True loop — placed before increment_google_token_bucket() to avoid counting a fetch that never happens"
  - "Depletion does NOT raise an exception — returns partial summary so Celery marks task SUCCESS and the next Beat tick is the natural retry mechanism"
  - "review.fetched AuditLog uses entity_type='review' (not 'shop_sync') — keeps page-level fetch events distinct from sync lifecycle events"
  - "patched_dependencies fixture extended with token_bucket_depleted=False — prevents existing tests from hitting real Redis via the newly-imported helper"

patterns-established:
  - "Depletion gate pattern: check rate-limit bucket at top of pagination loop before any API call or counter increment"

requirements-completed:
  - SYNC-09
  - SYNC-10

# Metrics
duration: 3min
completed: 2026-05-02
---

# Phase 11 Plan 14: Sync Gap Closures Summary

**token_bucket_depleted() gates the GBP pagination loop and review.fetched AuditLog is written per persisted page, closing SYNC-09 and SYNC-10 verification gaps**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-02T06:08:30Z
- **Completed:** 2026-05-02T06:11:56Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Wired `token_bucket_depleted()` as the first check in the `while True:` pagination loop in `fetch_and_persist_reviews` — bucket depletion now halts the loop cleanly with a warning log before any API call is made
- Added `AuditLog(entity_type="review", action="review.fetched")` write after each `_persist_page` call with `after_data={"page": page_count, "count": persisted, "trigger": trigger}`
- Added `token_bucket_depleted` to the `patched_dependencies` fixture (returns `False` by default) and two new regression tests covering both gap closures — all 11 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire token_bucket_depleted + review.fetched AuditLog in sync.py** - `d30b24b` (feat)
2. **Task 2: Add regression tests for review.fetched audit + bucket depletion halt** - `ec3fbfc` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `apps/reviews/services/sync.py` - Added `token_bucket_depleted` import + depletion gate in pagination loop + `AuditLog` write per page
- `apps/reviews/tests/test_sync_service.py` - Extended `patched_dependencies` fixture + added `test_review_fetched_audit_logged` + `test_pagination_halts_when_bucket_depleted`

## Decisions Made
- `token_bucket_depleted()` is checked BEFORE `increment_google_token_bucket()` in the loop — prevents incrementing the counter for a fetch call that never happens
- Depletion does NOT raise — the loop breaks cleanly, `_soft_delete_absent` and `sync.completed` audit still run if any pages were fetched; this keeps Celery from retrying the task unnecessarily
- `review.fetched` uses `entity_type="review"` to distinguish per-page fetch events from `entity_type="shop_sync"` lifecycle events (`sync.started`, `sync.completed`, `sync.failed`)
- `patched_dependencies` now patches `token_bucket_depleted` to `False` — necessary because the function calls Redis via `get_redis_connection`, which raises `NotImplementedError` in test settings using `locmem` cache

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended patched_dependencies fixture to patch token_bucket_depleted**
- **Found during:** Task 2 (running new tests)
- **Issue:** `patched_dependencies` fixture did not patch `token_bucket_depleted`, causing existing tests to call the real Redis implementation which raises `NotImplementedError` with `locmem` cache backend in test settings
- **Fix:** Added `patch.object(sync_mod, "token_bucket_depleted", return_value=False)` to the fixture's `with` block
- **Files modified:** apps/reviews/tests/test_sync_service.py
- **Verification:** All 11 tests pass including the 9 pre-existing ones
- **Committed in:** ec3fbfc (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Necessary for test correctness. No scope creep.

## Issues Encountered
- First commit attempt for Task 2 failed due to mypy pre-commit hook modifying the staged file; resolved by re-staging and re-committing (second attempt passed all hooks)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SYNC-09 and SYNC-10 verification gaps are now closed
- `fetch_and_persist_reviews` has a complete audit trail: `sync.started` + N x `review.fetched` (per page) + `sync.completed` or `sync.failed`
- Rate-limit safety: GBP pagination halts cleanly on bucket depletion; next Beat tick retries automatically

---
*Phase: 11-reviews*
*Completed: 2026-05-02*
