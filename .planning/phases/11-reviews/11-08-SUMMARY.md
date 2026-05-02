---
phase: "11"
plan: "08"
subsystem: reviews
tags: [celery, oauth, sync, progress, frontend, shops]
dependency_graph:
  requires: [11-04, 11-06]
  provides: [OAuth->sync backfill dispatch, open_progress_shop_id passthrough, /shops/syncing/ endpoint, frontend ?open_progress= redirect]
  affects: [11-12]
tech_stack:
  added: []
  patterns: [Celery task dispatch from ViewSet, per-action permission override, Redis key existence check]
key_files:
  created: []
  modified:
    - apps/integrations/google/oauth.py
    - apps/shops/serializers.py
    - apps/shops/services/shops.py
    - apps/shops/views.py
    - apps/shops/tests/test_views.py
    - apps/integrations/google/tests/test_oauth.py
    - apps/shops/tests/test_services.py
    - frontend/src/widgets/shop-management/types.ts
    - frontend/src/widgets/shop-management/CreateShopModal.tsx
    - frontend/src/widgets/shop-management/ShopModals.tsx
decisions:
  - "syncing endpoint uses IsOrgScoped (not IsOrgAdmin) — Staff Admins need to check sync progress for their accessible shops"
  - "BLE001/S112 noqa on per-shop Redis exception — Redis failure for a single shop must not abort the entire syncing list"
  - "Task dispatch wrapped in try/except in perform_create — dispatch failure logs a warning but does not block shop creation (task will be retried by Beat)"
  - "Redirect uses window.location.href (not router.push) — Plan 12 mounts fresh and reads ?open_progress= from URL on component init"
metrics:
  duration_minutes: 6
  tasks_completed: 2
  files_modified: 10
  completed_date: "2026-05-02"
key_decisions:
  - "syncing endpoint uses IsOrgScoped (not IsOrgAdmin) — Staff Admins need to check sync progress for their accessible shops"
  - "BLE001/S112 noqa on per-shop Redis exception — Redis failure for a single shop must not abort the entire syncing list"
  - "Task dispatch wrapped in try/except in perform_create — dispatch failure logs a warning but does not block shop creation"
  - "Redirect uses window.location.href (not router.push) — Plan 12 mounts fresh and reads ?open_progress= from URL"
---

# Phase 11 Plan 08: OAuth -> Sync Pipeline Wiring Summary

**One-liner:** OAuth-to-backfill pipeline wired end-to-end — GBP resource names persisted, Celery backfill dispatched on create/reconnect, /shops/syncing/ endpoint, frontend redirects with ?open_progress= for ProgressModal auto-open.

## What Was Built

### End-to-End Trigger Flow

```
OAuth callback → ShopViewSet.create
  → create_shop(google_account_name, google_location_name, ...)
  → initial_backfill_task.delay(shop_id=shop.pk)
  → Response includes open_progress_shop_id
→ CreateShopModal receives open_progress_shop_id
  → window.location.href = /admin/org/shops/?open_progress={shopId}
→ Plan 12 ProgressModal bootstrap reads ?open_progress= from URL
  → ProgressModal opens for that shop
  → WebSocket connects to SyncProgressConsumer
  → Live sync progress updates stream to UI
```

### Task 1: GBP Resource Names (oauth.py + serializers + service)

- `list_business_locations` now includes `account_name` and `location_name` in each listing dict
- Full GBP resource path constructed: if `loc.name` starts with `"accounts/"` it is used as-is; otherwise `{account_name}/{loc.name}` is built
- `ShopCreateSerializer` accepts optional `google_account_name` and `google_location_name` fields (allow_blank, default `""`)
- `create_shop()` signature extended to persist both fields on the Shop row

### Task 2: ShopViewSet Wiring

**Backend:**
- `perform_create`: dispatches `initial_backfill_task.delay(shop_id=shop.pk)` after successful GOOGLE_OAUTH shop creation; failure is logged but non-blocking
- `create`: response dict includes `open_progress_shop_id = shop.pk` for GOOGLE_OAUTH shops
- `reconnect`: dispatches `initial_backfill_task.delay(shop_id=shop.pk)` and includes `open_progress_shop_id` in response
- New `GET /api/v1/shops/syncing/` action: iterates org shops, checks Redis `sync:progress:{shop_id}` key existence, returns `{count, shops:[{shop_id, shop_name}]}`
- `syncing` action uses `IsOrgScoped` permission (not `IsOrgAdmin`) so Staff Admins can check progress for their accessible shops

**Frontend:**
- `ShopRow` type extended with `open_progress_shop_id?: number | null`
- `CreateShopModal.handleSubmit`: on success, if `open_progress_shop_id` is present redirects to `/admin/org/shops/?open_progress={shopId}`; otherwise `window.location.reload()`
- `ShopModals.handleReconnectComplete`: same redirect contract for reconnect flow

## API Additions

| Method | URL | Auth | Response |
|--------|-----|------|----------|
| GET | /api/v1/shops/syncing/ | IsOrgScoped | `{count: int, shops: [{shop_id, shop_name}]}` |

Existing endpoints extended:
- POST /api/v1/shops/ — response now includes `open_progress_shop_id` for GOOGLE_OAUTH shops
- POST /api/v1/shops/{id}/reconnect/ — response now includes `open_progress_shop_id`

## Tests Added

- `test_create_shop_dispatches_initial_backfill_task` — verifies task dispatch + open_progress_shop_id in response
- `test_shops_syncing_endpoint_returns_shops_with_redis_key` — mocked Redis, only shops with key returned
- `test_shops_syncing_staff_filters_to_accessible_shops` — StaffAccessScope filtering verified
- `test_listings_include_account_name_and_location_name` — OAuth listing includes GBP resource names
- `test_listing_location_name_already_full_path_not_duplicated` — full path not double-prefixed
- `test_create_shop_stores_google_account_name` — persisted on Shop row
- `test_create_shop_defaults_empty_strings_when_not_provided` — backward-compatible default

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written, with one minor adaptation:

**1. [Rule 2 - Missing Critical Functionality] syncing endpoint permission**
- **Found during:** Task 2 (Staff test failing with 403)
- **Issue:** Plan specified `IsOrgAdmin` but `syncing` endpoint must be accessible to Staff Admins too (they need to see sync progress for their shops)
- **Fix:** Action-level `permission_classes=[IsOrgScoped]` override — `IsOrgScoped` allows both `ORG_ADMIN` and `STAFF_ADMIN` with an organisation
- **Files modified:** `apps/shops/views.py`
- **Commit:** 50cc89d

## Self-Check: PASSED

All key files confirmed present. Both task commits (e73c3b0, 50cc89d) verified in git history.
