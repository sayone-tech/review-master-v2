---
phase: 23
plan: "03"
subsystem: reviews/enrichment
tags: [celery, openai, rate-limiting, token-bucket, queue-routing, websocket, snapshot]
dependency_graph:
  requires: [23-01, 23-02]
  provides: [token-bucket-guard, sync-complete-decoupled, ai-enrichment-low-routing, 4step-snapshot-passthrough]
  affects: [apps/reviews/services/enrichment.py, apps/reviews/tasks.py, apps/reviews/selectors/sync_progress.py]
tech_stack:
  added: []
  patterns:
    - skip_rate_limit_guard kwarg for seed-path double-count prevention
    - sync.complete ownership moved to finalise.py (D-02)
    - apply_async with explicit queue= override at call site (D-09)
key_files:
  created: []
  modified:
    - apps/reviews/services/enrichment.py
    - apps/reviews/tasks.py
    - apps/reviews/selectors/sync_progress.py
    - apps/reviews/tests/test_tasks.py
    - apps/reviews/tests/test_enrichment_service.py
    - apps/reviews/tests/test_enrichment_progress.py
    - apps/reviews/tests/test_progress_service.py
    - apps/reviews/tests/test_consumers.py
    - apps/common/tests/test_celery_config.py
    - apps/notifications/tests/test_dispatch.py
decisions:
  - "skip_rate_limit_guard=True on seed path: seed loop pre-acquires token via _wait_for_openai_token, calling guard again would double-count (Blocker 2 / D-08)"
  - "sync.complete decoupled from enrichment: _emit_enrichment_progress no longer sets status=success or calls _dispatch_sync_complete_notifications; ownership moved to run_finalise_canonical_tags (D-02)"
  - "enrich_review_task default route changed to ai-enrichment-low; seed path overrides to ai-enrichment-high at call site via apply_async (D-09)"
  - "get_progress_snapshot returns snapshot verbatim — no key filtering — so 4-step keys pass through to reconnecting consumers (SEED-01)"
metrics:
  duration: "~90 minutes (across two sessions)"
  completed: "2026-06-11"
  tasks: 4
  files_changed: 10
---

# Phase 23 Plan 03: Token-Bucket Guard, sync.complete Decoupling, Queue Routing, and 4-Step Snapshot Pass-Through Summary

**One-liner:** Wires the OpenAI per-org token bucket into `enrich_review` with a `skip_rate_limit_guard` bypass for the seed path, decouples `sync.complete` ownership from enrichment to the finalise stage, routes retry dispatch to `ai-enrichment-low`, and confirms the 4-step progress snapshot passes verbatim through the consumer.

## Tasks Completed

| # | Task | Commit(s) | Notes |
|---|------|-----------|-------|
| 1 | Four-phase `run_initial_backfill` orchestrator | 4883e66 (RED), 68a8123 (GREEN) | Merged at base; Task 1 was pre-merged |
| 2 | `skip_rate_limit_guard` + sync.complete decoupling | 687c0d6 (RED), 2665324 (GREEN) | TDD pattern |
| 3 | Queue routing: retry to `ai-enrichment-low`, backfill time limits | 24f5d4b | `initial_backfill_task` gets soft_time_limit=540, time_limit=600 |
| 4 | 4-step snapshot pass-through (sync_progress.py + consumer reconnect) | 87ab638 | Docstring + tests confirm SEED-01 |
| — | Rule 1 auto-fixes (test suite) | 25d4d1a | 5 test files updated for D-02/D-09 behavioral changes |

## Key Design Decisions

### D-08: skip_rate_limit_guard bypass for seed path

The seed loop (`sync.py`) calls `_wait_for_openai_token(organisation_id=...)` before dispatching each seed enrichment. This already increments the per-org OpenAI token bucket. If `enrich_review` also ran the bucket guard, it would double-decrement on the seed path AND crash (the bucket would appear depleted because the seed loop already claimed the token).

Fix: `enrich_review(*, review_id, skip_rate_limit_guard=False)`. Seed path passes `skip_rate_limit_guard=True`. Bulk/incremental Celery path uses the default `False`, hits the guard normally, and Celery's `autoretry_for` handles bucket-depleted retries.

### D-02: sync.complete moved from enrichment to finalise

Previously, `_emit_enrichment_progress` emitted `sync.complete` when `enriched >= fetched`. This was racey (stale snapshot reads caused multi-fire) and architecturally wrong for the 4-step sync where a "finalising" phase follows enrichment. Phase 23 moves sync.complete ownership to `run_finalise_canonical_tags` in `finalise.py`.

Result: `_emit_enrichment_progress` always writes `status="enriching"` and never calls `_dispatch_sync_complete_notifications` or `claim_sync_complete`.

### D-09: Queue routing via apply_async override

`CELERY_TASK_ROUTES` sets `enrich_review_task` default to `"ai-enrichment-low"`. Callers that need higher priority override via `apply_async(args=[...], queue="ai-enrichment-high")` at the call site. The route table is the fallback; it does not constrain per-call overrides.

### SEED-01: Snapshot pass-through

`get_progress_snapshot` delegates to `read_progress_snapshot` and returns the dict verbatim. No key allowlist. This means Phase 23 4-step keys (`step`, `vocab_enriched`, `vocab_total`, `finalising_processed`, `finalising_total`) reach reconnecting consumers unchanged, repainting the modal correctly on reconnect.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_enrichment_service.py fixture did not mock new token-bucket functions**
- **Found during:** Post-Task 2 full suite run (21 tests failing)
- **Issue:** `no_progress_snapshot` autouse fixture did not mock `openai_token_bucket_depleted` and `increment_openai_token_bucket`, causing `NotImplementedError` from the test Redis backend
- **Fix:** Expanded fixture to patch both functions at `enrichment_mod` namespace
- **Files modified:** `apps/reviews/tests/test_enrichment_service.py`
- **Commit:** 25d4d1a

**2. [Rule 1 - Bug] test_enrichment_progress.py tested removed sync.complete-from-enrichment behavior**
- **Found during:** Post-Task 2 full suite run (2 tests failing)
- **Issue:** Two tests (`test_emit_enrichment_progress_fires_sync_complete_when_caught_up`, `test_sync_complete_dispatched_exactly_once_under_concurrent_enrichments`) asserted the old Phase 12 behavior that Phase 23 D-02 intentionally removed
- **Fix:** Rewrote tests to assert new contract: sync.complete is never emitted from `_emit_enrichment_progress`, status stays `"enriching"` even when `enriched >= fetched`
- **Files modified:** `apps/reviews/tests/test_enrichment_progress.py`
- **Commit:** 25d4d1a

**3. [Rule 1 - Bug] test_celery_config.py asserted old ai-enrichment queue name**
- **Found during:** Post-Task 3 full suite run
- **Issue:** Test asserted `enrich_review_task` route was `"ai-enrichment"` but Task 3 changed it to `"ai-enrichment-low"`
- **Fix:** Updated assertion to `"ai-enrichment-low"` with Phase 23 D-09 comment
- **Files modified:** `apps/common/tests/test_celery_config.py`
- **Commit:** 25d4d1a

**4. [Rule 1 - Bug] test_dispatch.py patched .delay but sync.py uses .apply_async**
- **Found during:** Post-Task 3 full suite run
- **Issue:** `test_sync_dispatches_new_review_notification_per_new_row` mocked `enrich_review_task.delay` to suppress task execution. Phase 23 changed sync.py to dispatch via `.apply_async()`. With `CELERY_TASK_ALWAYS_EAGER=True`, the unpatched `.apply_async()` executed the task which hit Redis and raised `NotImplementedError`
- **Fix:** Changed mock target to `enrich_review_task.apply_async`
- **Files modified:** `apps/notifications/tests/test_dispatch.py`
- **Commit:** 25d4d1a

**5. [Rule 1 - Bug] test_dispatch.py enrichment flow test did not mock token-bucket functions**
- **Found during:** Post-Task 2 full suite run
- **Issue:** `test_promote_then_dispatch_via_enrichment_flow` called `enrich_review` directly without mocking `openai_token_bucket_depleted` and `increment_openai_token_bucket`
- **Fix:** Added `patch.object(enrichment_mod, "openai_token_bucket_depleted", return_value=False)` and `patch.object(enrichment_mod, "increment_openai_token_bucket")` to the test's context manager
- **Files modified:** `apps/notifications/tests/test_dispatch.py`
- **Commit:** 25d4d1a

## Test Coverage

All 1128 tests pass (2 skipped, 0 failures) after fixes.

Key test additions:
- `test_enrich_review_bulk_path_raises_when_bucket_depleted` — verifies guard raises `OpenAITransientError` for Celery retry
- `test_enrich_review_bulk_path_increments_bucket_when_not_depleted` — verifies bucket incremented on normal path
- `test_enrich_review_seed_path_skips_rate_limit_guard` — verifies `skip_rate_limit_guard=True` bypasses guard entirely
- `test_emit_enrichment_progress_does_not_emit_sync_complete_when_enriched_gte_fetched` — Phase 23 D-02 contract
- `test_sync_complete_never_dispatched_from_emit_enrichment_progress` — spam regression guard (D-02 version)
- `test_retry_failed_enrichments_dispatches_to_ai_enrichment_low` — D-09 queue routing
- `test_initial_backfill_task_has_time_limits` — soft/hard limit coverage
- `test_read_progress_snapshot_passes_through_4step_keys` — SEED-01 round-trip
- `test_reconnect_snapshot_carries_4step_keys` — SEED-01 consumer end-to-end

## Known Stubs

None.

## Threat Flags

None — this plan modifies internal rate-limiting logic and test infrastructure only. No new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- `apps/reviews/services/enrichment.py` — exists with `skip_rate_limit_guard` kwarg
- `apps/reviews/tasks.py` — exists with `ai-enrichment-low` dispatch and time limits
- `apps/reviews/selectors/sync_progress.py` — exists with 4-step docstring
- All commits exist: 687c0d6, 2665324, 24f5d4b, 87ab638, 25d4d1a
- Full suite: 1128 passed, 0 failed
