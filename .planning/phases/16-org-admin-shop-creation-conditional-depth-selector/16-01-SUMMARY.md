---
phase: "16"
plan: "01"
subsystem: shops/reviews
tags: [sync-depth, serializer, service, template-context, incremental-sync]
dependency_graph:
  requires: [phase-15-sync-depth-model]
  provides: [sync-depth-api-acceptance, allow-custom-sync-depth-bootstrap, incremental-sync-date-filter]
  affects: [shop-creation-api, shop-list-template, review-sync-service]
tech_stack:
  added: []
  patterns: [drf-choice-field, json-script-bootstrap, service-kwarg-extension]
key_files:
  created: []
  modified:
    - apps/shops/serializers.py
    - apps/shops/services/shops.py
    - apps/shops/views.py
    - apps/shops/tests/test_services.py
    - apps/shops/tests/test_views.py
    - templates/shops/shop_list.html
    - apps/reviews/services/sync.py
    - apps/reviews/tests/test_sync_service.py
decisions:
  - "sync_depth placed before connection_status in create_shop() signature per pitfall 1"
  - "incremental sync date floor applies to all triggers (not just initial) per plan requirement"
  - "existing test_incremental_sync_unaffected_by_sync_depth replaced with new behavior tests"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-18"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 8
---

# Phase 16 Plan 01: Conditional Depth Selector Backend Summary

**One-liner:** ShopCreateSerializer ChoiceField + create_shop() kwarg + shop_list context injection + incremental sync date floor for all triggers.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add sync_depth to ShopCreateSerializer and extend create_shop() | 09b2412 | serializers.py, services/shops.py, test_services.py, test_views.py |
| 2 | Inject allow_custom_sync_depth into shop_list context + template | 4f2418c | views.py, shop_list.html, test_views.py |
| 3 | Apply sync_depth date floor to incremental syncs | 245bf87 | sync.py, test_sync_service.py |

## What Was Built

### Task 1: ShopCreateSerializer sync_depth + create_shop() extension
- Added `sync_depth = serializers.ChoiceField(choices=Shop.SyncDepth.choices, required=False, default=Shop.SyncDepth.TWO_YEARS)` to `ShopCreateSerializer`
- Added `sync_depth: str = Shop.SyncDepth.TWO_YEARS` parameter to `create_shop()` before `connection_status`
- Added `sync_depth=sync_depth` to `Shop.objects.create()` call
- The `**data` splat in `ShopViewSet.perform_create` automatically passes the validated value through
- 8 tests pass: 2 service tests (ONE_YEAR, ALL_TIME persistence), 3 API tests (accepts ONE_YEAR, rejects INVALID→400, defaults to TWO_YEARS)

### Task 2: shop_list view context + template bootstrap tag
- Added `"allow_custom_sync_depth": org.allow_custom_sync_depth` to the `shop_list` view `render()` context dict
- Added `{{ allow_custom_sync_depth|json_script:"shop-org-data" }}` to `templates/shops/shop_list.html` on the line immediately after `shop-regions-data`
- Boolean value passed directly (not via `|yesno`) so `json_script` serialises to JSON `true`/`false`
- 2 view context tests pass: `allow_custom_sync_depth=False` org → context value `False`; `allow_custom_sync_depth=True` org → context value `True`

### Task 3: Incremental sync date floor
- Changed guard in `fetch_and_persist_reviews()` from `if trigger == "initial" and start_date is None:` to `if start_date is None:`
- Date floor now applies for all triggers (initial, incremental, manual)
- Removed the Phase 15 test `test_incremental_sync_unaffected_by_sync_depth` (which asserted old behavior) and replaced with 3 new tests
- 4 incremental sync tests pass; 3 initial backfill tests continue to pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Behavior Update] Updated existing `test_incremental_sync_unaffected_by_sync_depth` test**
- **Found during:** Task 3
- **Issue:** Phase 15 had a test asserting incremental sync does NOT apply date filter. Phase 16 changes this behavior.
- **Fix:** Replaced the old test body with 3 new tests covering ONE_YEAR, ALL_TIME, and TWO_YEARS incremental sync filter behaviors.
- **Files modified:** `apps/reviews/tests/test_sync_service.py`
- **Commit:** 245bf87

## Known Stubs

None — all changes are fully wired with real data flowing through.

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced. The `allow_custom_sync_depth` boolean flows through Django's built-in `json_script` filter (XSS-safe). The `sync_depth` field is validated by DRF `ChoiceField` and rejects invalid values with 400.

## Self-Check: PASSED

Files confirmed present:
- apps/shops/serializers.py — contains `sync_depth = serializers.ChoiceField(`
- apps/shops/services/shops.py — contains `sync_depth: str = Shop.SyncDepth.TWO_YEARS,`
- apps/shops/views.py — contains `"allow_custom_sync_depth": org.allow_custom_sync_depth,`
- templates/shops/shop_list.html — contains `{{ allow_custom_sync_depth|json_script:"shop-org-data" }}`
- apps/reviews/services/sync.py — guard changed to `if start_date is None:`

Commits confirmed:
- 09b2412 — Task 1
- 4f2418c — Task 2
- 245bf87 — Task 3

Full test suite: `pytest apps/shops/tests/ apps/reviews/tests/test_sync_service.py` → 147 passed
