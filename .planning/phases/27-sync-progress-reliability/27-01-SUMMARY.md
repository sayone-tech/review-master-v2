---
phase: 27-sync-progress-reliability
plan: "01"
subsystem: reviews
tags: [sync-progress, finalise-gate, security, celery, redis, drf]
dependency_graph:
  requires: []
  provides: [SYNC-REL-01-backend, SYNC-REL-02]
  affects: [apps/reviews/views.py, apps/reviews/services/finalise.py, apps/reviews/services/sync.py, apps/reviews/tasks.py]
tech_stack:
  added: []
  patterns: [scoped-rate-throttle, bounded-self-reschedule, org-shop-scope-mirror]
key_files:
  created: []
  modified:
    - apps/reviews/views.py
    - apps/reviews/tests/test_views.py
    - apps/reviews/services/finalise.py
    - apps/reviews/services/sync.py
    - apps/reviews/tasks.py
    - apps/reviews/tests/test_finalise.py
    - config/settings/base.py
    - config/urls.py
decisions:
  - "Snapshot endpoint returns 404 for both cross-tenant denial AND no snapshot (T-27-03 existence-disclosure avoidance)"
  - "Gate lives inside the per-org lock so two workers cannot both re-dispatch simultaneously (T-27-06)"
  - "finalize_canonical_tags_task.apply_async patched via apps.reviews.tasks import path in tests (lazy import inside service)"
metrics:
  duration: "~45 minutes"
  completed: "2026-06-24"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 8
---

# Phase 27 Plan 01: Sync Progress Reliability — Backend Summary

**One-liner:** Org+shop-scoped Redis snapshot GET endpoint (throttled, §13.4 auth mirrored) + bounded self-reschedule completion gate in `finalize_canonical_tags_task` replacing the fixed-countdown heuristic.

## Tasks Completed

| Task | Commit | Files |
|------|--------|-------|
| 1: Add org+shop-scoped GET snapshot endpoint (SYNC-REL-01) | `c88e2c6` | views.py, test_views.py, config/settings/base.py, config/urls.py |
| 2: Completion-gate finalise via bounded self-reschedule (SYNC-REL-02) | `7abf540` | finalise.py, sync.py, tasks.py, test_finalise.py |

## What Was Built

### Task 1 — SYNC-REL-01 (D-01)

`GET /api/v1/reviews/sync-progress/{shop_id}/`

- `SyncProgressSnapshotView(APIView)` in `apps/reviews/views.py`
- Auth mirrors `SyncProgressConsumer._user_can_access_shop` (§13.4):
  - `IsAuthenticated` required (T-27-02)
  - `shop.organisation_id` must match caller's `organisation_id`
  - `STAFF_ADMIN`: must have `StaffAccessScope` SHOP or REGION scope
- Returns 404 for BOTH cross-tenant denial AND absent snapshot (T-27-03 existence-disclosure avoidance — consistent denial shape)
- Single `read_progress_snapshot(shop_id=...)` Redis GET — no extra DB queries beyond the shop scope check (T-27-04)
- `ScopedRateThrottle` with `throttle_scope="sync_progress"` (default 120/minute via `SYNC_PROGRESS_THROTTLE_RATE`)
- No new WebSocket consumer (§13.2 — HTTP fallback only)

New settings in `config/settings/base.py`:
- `SYNC_PROGRESS_THROTTLE_RATE` (default `"120/minute"`)
- `FINALISE_GATE_COUNTDOWN_SECONDS` (default `20`)
- `FINALISE_GATE_MAX_ATTEMPTS` (default `30`)

### Task 2 — SYNC-REL-02 (D-03/D-04)

Completion gate in `run_finalise_canonical_tags` (`apps/reviews/services/finalise.py`):

- Gate runs INSIDE the per-org `lock:tag_merge:org:{org_id}` lock (T-27-06)
- Queries `Review.objects.filter(shop_id=shop_id, enrichment_status__in=[PENDING, IN_PROGRESS]).exists()` — single indexed query
- If non-terminal AND `attempt < FINALISE_GATE_MAX_ATTEMPTS`: re-dispatches `finalize_canonical_tags_task` on `tag-merge` queue with `countdown=FINALISE_GATE_COUNTDOWN_SECONDS`; returns `{"rescheduled": True}` without running dedup/backfill/count-refresh
- IN_PROGRESS counts as "still working" (D-03 discretion)
- At `FINALISE_GATE_MAX_ATTEMPTS`, proceeds anyway (T-27-05 — sync always completes)
- `finalize_canonical_tags_task` accepts `attempt: int = 1` kwarg (thin wrapper, §12.3)
- `sync.py` Phase 4 dispatch: removed the `_finalise_countdown` heuristic (`max(300, min(1200, ...))`) — replaced with initial dispatch at `FINALISE_GATE_COUNTDOWN_SECONDS`; deferred-chord comment updated to record self-reschedule as the chosen mechanism (D-04)

## Tests

**Task 1 (6 new tests in test_views.py):**
- `test_sync_progress_returns_snapshot_for_owner_org` — 200 + snapshot dict
- `test_sync_progress_returns_404_when_no_snapshot` — 404 when Redis key absent
- `test_sync_progress_cross_tenant_denied` — org B cannot read org A's shop (T-27-01)
- `test_sync_progress_staff_out_of_scope_denied` — Staff without scope denied
- `test_sync_progress_staff_in_scope_allowed` — Staff with SHOP scope gets 200
- `test_sync_progress_unauthenticated_denied` — anonymous gets 401/403

**Task 2 (5 new tests in TestFinaliseGate class in test_finalise.py):**
- `test_gate_redispatches_while_reviews_pending` — re-dispatch while PENDING, no dedup/backfill
- `test_gate_redispatches_while_reviews_in_progress` — IN_PROGRESS also re-dispatches
- `test_gate_proceeds_when_all_reviews_terminal` — finalise runs when all SUCCESS/FAILED
- `test_gate_bounded_cap_proceeds_despite_pending` — proceeds at max attempts (T-27-05)
- `test_gate_lock_behaviour_unchanged` — skipped-on-lock idempotency preserved

Total: 81 tests pass (49 in test_views.py + 32 in test_finalise.py).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both features fully wired.

## Threat Flags

No new threat surface beyond what the plan's threat model covers. The endpoint and gate implementation mitigate T-27-01 through T-27-06 as designed.

## Self-Check: PASSED

- `apps/reviews/views.py` — SyncProgressSnapshotView present
- `apps/reviews/services/finalise.py` — completion gate present, `attempt` kwarg added
- `apps/reviews/services/sync.py` — `_finalise_countdown` heuristic removed
- `apps/reviews/tasks.py` — `attempt` kwarg accepted and forwarded to service
- `config/urls.py` — `/api/v1/reviews/sync-progress/<int:shop_id>/` registered
- `config/settings/base.py` — `SYNC_PROGRESS_THROTTLE_RATE`, `FINALISE_GATE_COUNTDOWN_SECONDS`, `FINALISE_GATE_MAX_ATTEMPTS` present; `sync_progress` in `DEFAULT_THROTTLE_RATES`
- Commit `c88e2c6` exists: feat(27-01): add org+shop-scoped GET sync progress snapshot endpoint
- Commit `7abf540` exists: feat(27-01): add completion-gate finalise via bounded self-reschedule
- `pytest apps/reviews/tests/test_views.py apps/reviews/tests/test_finalise.py` → 81 passed
- `python manage.py makemigrations --check --dry-run` → No changes detected (no model changes)
