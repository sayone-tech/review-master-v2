---
phase: 12-ai-enrichment-pipeline
plan: "06"
subsystem: reviews
tags: [enrichment, sync, websocket, celery-beat, migration]
dependency_graph:
  requires: ["12-04"]
  provides: ["sync-to-enrichment wiring", "enrichment progress events", "beat retry schedule"]
  affects: ["apps/reviews/services/sync.py", "apps/reviews/services/enrichment.py", "apps/reviews/tasks.py"]
tech_stack:
  added: []
  patterns: ["lazy-import circular-avoidance", "post-transaction event emission", "beat seed migration"]
key_files:
  created:
    - apps/reviews/tests/test_enrichment_progress.py
    - apps/reviews/migrations/0005_periodic_tasks_seed_retry_failed_enrichments.py
  modified:
    - apps/reviews/services/sync.py
    - apps/reviews/services/enrichment.py
    - apps/reviews/tests/test_sync_service.py
    - apps/reviews/tests/test_enrichment_service.py
decisions:
  - "Function-local import of enrich_review_task in sync.py: tasks.py imports run_incremental_sync/run_initial_backfill from sync.py, so a top-level import of enrich_review_task in sync.py creates a circular dependency. Local import inside the page loop resolves this."
  - "Test patching targets source modules (apps.reviews.services.progress and apps.reviews.services.sync) not the enrichment module namespace, because lazy imports don't create module-level attributes."
  - "autouse no_progress_snapshot fixture in test_enrichment_service.py suppresses Redis reads from _emit_enrichment_progress so Plan 04 tests remain focused on DB state."
  - "patched_dependencies fixture in test_sync_service.py now patches enrich_review_task.delay to prevent eager Celery task execution (CELERY_TASK_ALWAYS_EAGER=True) in sync-focused tests."
metrics:
  duration: 7m
  completed: "2026-05-02"
  tasks: 3
  files: 6
---

# Phase 12 Plan 06: Sync-to-Enrichment Wiring and Progress Events Summary

Wire enrich_review_task dispatch inline after each page upsert, move sync.complete ownership to the enrichment service, add sync.enrichment.progress emission on every successful enrichment, and seed the retry_failed_enrichments Beat schedule.

## What Was Built

### Task 1: Wire enrich_review_task.delay into fetch_and_persist_reviews

After each page upsert in `fetch_and_persist_reviews`, the service now queries for review IDs with `enrichment_status=PENDING` in the page's `google_review_id` set and dispatches `enrich_review_task.delay(review_id)` for each.

The `sync.complete` WebSocket emission that previously fired after the fetch loop was removed entirely. The success-path `write_progress_snapshot(status="success")` and the `sync.completed` AuditLog entry remain unchanged — only the WebSocket event was removed.

**Circular import resolution:** `tasks.py` imports `run_incremental_sync` and `run_initial_backfill` from `sync.py`. Adding a top-level `from apps.reviews.tasks import enrich_review_task` in `sync.py` creates a circular dependency. A function-local import inside the page loop resolves this cleanly.

### Task 2: _emit_enrichment_progress in enrichment service

New helper `_emit_enrichment_progress(*, review)` added to `enrichment.py`:
- Reads Redis snapshot via `read_progress_snapshot`. If `None` (incremental sync with no live modal), returns silently.
- Increments the `enriched` counter, updates `status` to `"enriching"` or `"success"`, writes snapshot back.
- Emits `sync.enrichment.progress` with `{type, shop_id, enriched, fetched}`.
- When `enriched >= fetched` and `fetched > 0`, additionally emits `sync.complete` — this is the SOLE source of `sync.complete` in Phase 12.

`_persist_success` calls `_emit_enrichment_progress(review=review)` as its final action, AFTER the `with transaction.atomic():` block closes. Emitting inside a transaction is an anti-pattern (rolled-back state could send events).

Both `read_progress_snapshot`/`write_progress_snapshot` and `emit_progress_event` are imported lazily inside `_emit_enrichment_progress` to avoid creating another circular dependency chain.

### Task 3: Beat seed migration 0005

Created `apps/reviews/migrations/0005_periodic_tasks_seed_retry_failed_enrichments.py` following the pattern from `0002_periodic_tasks_seed.py`. Seeds a `PeriodicTask` named `"retry_failed_enrichments"` for `apps.reviews.tasks.retry_failed_enrichments_task`, with `IntervalSchedule(every=6, period="hours")` on the `ai-enrichment` queue. The task body (created in Plan 04) re-attempts FAILED reviews where `enrichment_version < 3`.

`IntervalSchedule` (fixed offset) was chosen over `CrontabSchedule` (time-of-day) because the retry cadence is "every N hours", not "at a specific clock time".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] patched_dependencies fixture needed enrich_review_task.delay patch**
- **Found during:** Task 1 test execution
- **Issue:** With `CELERY_TASK_ALWAYS_EAGER=True`, calling `enrich_review_task.delay()` in `fetch_and_persist_reviews` caused all existing sync tests to fail because the task ran synchronously and tried to access Redis (which is not available in tests).
- **Fix:** Added `patch("apps.reviews.tasks.enrich_review_task.delay")` to the `patched_dependencies` fixture so existing sync-focused tests continue working without needing to verify enrichment dispatch.
- **Files modified:** `apps/reviews/tests/test_sync_service.py`

**2. [Rule 3 - Blocking] Test patching for lazy imports required source-module targets**
- **Found during:** Task 2 test execution
- **Issue:** The plan specified patching `apps.reviews.services.enrichment.read_progress_snapshot`, but since `_emit_enrichment_progress` uses lazy imports, these attributes don't exist in the enrichment module namespace.
- **Fix:** Tests patch at source modules: `apps.reviews.services.progress.read_progress_snapshot` and `apps.reviews.services.sync.emit_progress_event`. Tests use capture functions (`side_effect=_capture_*`) instead of `call_args_list` attribute access, which avoids mock keyword argument inspection issues.
- **Files modified:** `apps/reviews/tests/test_enrichment_progress.py`

**3. [Rule 3 - Blocking] Existing enrichment service tests broke after _persist_success change**
- **Found during:** Task 2 regression check
- **Issue:** `_persist_success` now calls `_emit_enrichment_progress`, which reads from Redis. The existing Plan 04 enrichment service tests had no Redis mock and started raising `NotImplementedError`.
- **Fix:** Added `autouse=True` fixture `no_progress_snapshot` to `test_enrichment_service.py` that patches `read_progress_snapshot` to return `None`, making `_emit_enrichment_progress` return silently without hitting Redis.
- **Files modified:** `apps/reviews/tests/test_enrichment_service.py`

## Self-Check: PASSED

All artifacts verified present:
- apps/reviews/services/sync.py — FOUND
- apps/reviews/services/enrichment.py — FOUND
- apps/reviews/tests/test_sync_service.py — FOUND
- apps/reviews/tests/test_enrichment_progress.py — FOUND
- apps/reviews/migrations/0005_periodic_tasks_seed_retry_failed_enrichments.py — FOUND

All task commits verified:
- d7a2cd7 (Task 1: sync wiring + sync.complete removal) — FOUND
- 3448d2e (Task 2: _emit_enrichment_progress + tests) — FOUND
- f30cd84 (Task 3: Beat seed migration) — FOUND

Test results: 96 passed across all reviews tests
