---
phase: 15-sync-depth-data-layer-and-superadmin-controls
plan: "03"
subsystem: reviews/sync
tags: [service, tdd, backfill, date-filter]
dependency_graph:
  requires: ["15-02"]
  provides: [start_date param in _persist_page, start_date param in fetch_and_persist_reviews, BKFL-01, BKFL-02, BKFL-03]
  affects: [apps/reviews/services/sync.py, apps/reviews/tests/test_sync_service.py]
tech_stack:
  added: []
  patterns: [timedelta date filter in persist loop, execution-time start_date computation, keyword-arg threading]
key_files:
  created: []
  modified:
    - apps/reviews/services/sync.py
    - apps/reviews/tests/test_sync_service.py
decisions:
  - "start_date computed at execution time inside fetch_and_persist_reviews, not at enqueue time — uses already-fetched shop instance (no second DB query)"
  - "Date filter applied in _persist_page after normalisation and google_review_id check — skipped rows omitted from rev_ids so _soft_delete_absent purges out-of-window rows"
  - "run_initial_backfill remains a one-liner delegating to fetch_and_persist_reviews(trigger='initial') — no Shop double-fetch"
  - "Incremental and manual triggers receive start_date=None by default — no behavior change"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-05-15"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 15 Plan 03: Sync Depth Date Filter Summary

Threaded an optional `start_date: datetime | None` parameter through `_persist_page` and `fetch_and_persist_reviews` in `apps/reviews/services/sync.py`. When `trigger == "initial"`, `start_date` is derived from `shop.sync_depth` at execution time — ONE_YEAR→365 days, TWO_YEARS→730 days, ALL_TIME→None. `_persist_page` skips any normalised review whose `review_create_time < start_date`. Incremental and manual triggers are unaffected.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add start_date param to _persist_page and fetch_and_persist_reviews | ad93536 | apps/reviews/services/sync.py |
| 2 | Add BKFL-01/02/03 + incremental-regression tests | 05cf081 | apps/reviews/tests/test_sync_service.py |

## What Was Built

### _persist_page changes (apps/reviews/services/sync.py, line 109)

New signature:
```python
def _persist_page(
    *,
    shop: Shop,
    api_reviews: list[dict[str, Any]],
    start_date: datetime | None = None,
) -> tuple[int, set[str], set[str]]:
```

Date filter inserted at line ~133, after `_normalise_review` and after the `if not norm["google_review_id"]: continue` guard, before `rev_ids.add(...)`:
```python
if start_date is not None and norm["review_create_time"] < start_date:
    continue
```

### fetch_and_persist_reviews changes (apps/reviews/services/sync.py, line 270)

New signature:
```python
def fetch_and_persist_reviews(
    *,
    shop_id: int,
    trigger: str = "incremental",
    start_date: datetime | None = None,
) -> dict[str, Any]:
```

start_date computation (inserted after Shop.objects.select_related fetch, before connection_status check):
```python
if trigger == "initial" and start_date is None:
    if shop.sync_depth == Shop.SyncDepth.ONE_YEAR:
        start_date = dj_timezone.now() - timedelta(days=365)
    elif shop.sync_depth == Shop.SyncDepth.TWO_YEARS:
        start_date = dj_timezone.now() - timedelta(days=730)
    # ALL_TIME → start_date stays None (no filter)
```

### _persist_page call site updated (line 392)

```python
persisted, ids, new_ids = _persist_page(
    shop=shop, api_reviews=page_reviews, start_date=start_date
)
```

### run_initial_backfill unchanged

```python
def run_initial_backfill(*, shop_id: int) -> dict[str, Any]:
    """Initial backfill — same engine, trigger="initial"."""
    return fetch_and_persist_reviews(shop_id=shop_id, trigger="initial")
```
No double-fetch of Shop — start_date computation happens inside fetch_and_persist_reviews using the Shop instance already fetched there.

### GBP mock fixture used in new tests

The existing `patched_dependencies` fixture (defined at top of test file) — patches `_refresh_access_token`, `distributed_lock`, `write_progress_snapshot`, `clear_progress_snapshot`, `increment_google_token_bucket`, `token_bucket_depleted`, `emit_progress_event`, and `enrich_review_task.delay`. New tests use `patch.object(sync_mod, "list_reviews", return_value=page)` inline (same pattern as all prior tests).

New helper `_build_gbp_review(google_review_id: str, days_old: int)` generates a GBP dict with timezone-aware `createTime` set to `now() - timedelta(days=days_old)`.

## Test Results

- `pytest apps/reviews/tests/test_sync_service.py` — **20 passed** (16 pre-existing + 4 new)
- `pytest apps/reviews/tests/` — **117 passed, 0 failures**

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. This plan modifies a service function to apply an in-memory date filter on data already fetched from the GBP API. No new endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- [x] `apps/reviews/services/sync.py` line 113 contains `start_date: datetime | None = None` (_persist_page)
- [x] `apps/reviews/services/sync.py` line 280 contains `start_date: datetime | None = None` (fetch_and_persist_reviews)
- [x] `apps/reviews/services/sync.py` contains `timedelta(days=365)` and `timedelta(days=730)`
- [x] `apps/reviews/services/sync.py` contains `Shop.SyncDepth.ONE_YEAR` and `Shop.SyncDepth.TWO_YEARS`
- [x] `apps/reviews/services/sync.py` contains `start_date is not None and norm["review_create_time"] < start_date`
- [x] Only one _persist_page call inside fetch_and_persist_reviews (line 392), passes `start_date=start_date`
- [x] `run_initial_backfill` is still a one-liner (no Shop double-fetch)
- [x] `apps/reviews/tests/test_sync_service.py` contains all four new test functions
- [x] Commits `ad93536` and `05cf081` exist in git log
