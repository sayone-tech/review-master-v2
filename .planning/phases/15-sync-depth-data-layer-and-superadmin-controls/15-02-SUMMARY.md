---
phase: 15-sync-depth-data-layer-and-superadmin-controls
plan: "02"
subsystem: shops
tags: [model, migration, serializer, tdd]
dependency_graph:
  requires: []
  provides: [Shop.SyncDepth, shop.sync_depth field, ShopReadSerializer.sync_depth]
  affects: [apps/shops/models.py, apps/shops/serializers.py, apps/shops/migrations/0008_shop_sync_depth.py]
tech_stack:
  added: []
  patterns: [TextChoices inner class, AddField migration, read_only_fields serializer pattern]
key_files:
  created:
    - apps/shops/migrations/0008_shop_sync_depth.py
  modified:
    - apps/shops/models.py
    - apps/shops/serializers.py
    - apps/shops/tests/test_models.py
    - apps/shops/tests/test_services.py
    - apps/shops/tests/test_views.py
decisions:
  - "sync_depth has no db_index (low cardinality, not used for filtering per RESEARCH)"
  - "sync_depth is read_only in ShopReadSerializer (Phase 16 adds ShopCreateSerializer selector)"
  - "ShopUpdateSerializer not modified (sync_depth not updatable; set at create time only)"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-05-15"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 15 Plan 02: Shop sync_depth Field Summary

Added `Shop.SyncDepth` TextChoices and `sync_depth` CharField (default `TWO_YEARS`) to the Shop model, created migration 0008, and exposed the field in `ShopReadSerializer` so all shop list and detail API endpoints return it.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add SyncDepth TextChoices + sync_depth field + migration + model test | 3c387fc | apps/shops/models.py, 0008_shop_sync_depth.py, test_models.py |
| 2 | Expose sync_depth via ShopReadSerializer + service default test + view test | 9cdcb10 | apps/shops/serializers.py, test_services.py, test_views.py |

## What Was Built

### Shop.SyncDepth (Python path: `apps.shops.models.Shop.SyncDepth`)

Inner TextChoices class placed immediately after `ConnectionStatus` in `class Shop`:

- `ONE_YEAR = "ONE_YEAR", "Last 1 year"`
- `TWO_YEARS = "TWO_YEARS", "Last 2 years"`
- `ALL_TIME = "ALL_TIME", "All time"`

### sync_depth field

`models.CharField(max_length=10, choices=SyncDepth.choices, default=SyncDepth.TWO_YEARS)` — placed after `connection_status`. No `db_index` (low cardinality; not used for filtering).

### Migration

File: `apps/shops/migrations/0008_shop_sync_depth.py`
Operation: `AddField` with `default="TWO_YEARS"` — all existing Shop rows receive the default; no data migration needed.
Dependencies: `("shops", "0007_recurring_review_targets")`

### ShopReadSerializer changes

`sync_depth` added to `Meta.fields` (adjacent to `connection_status`) and to `read_only_fields`. `ShopCreateSerializer` and `ShopUpdateSerializer` are untouched — Phase 16 will add the create-time selector when `allow_custom_sync_depth` is enabled.

### API context for Plan 04

- **Shop list URL:** `/api/v1/shops/` — returns `results[]` with `sync_depth` string
- **Shop detail URL:** `/api/v1/shops/{id}/` — returns `sync_depth` string
- **Auth client fixture used in test_views.py:** `org_and_admin` (creates an `ORG_ADMIN` user and `APIClient().force_authenticate`)
- **Valid values returned by API:** `"ONE_YEAR"` | `"TWO_YEARS"` | `"ALL_TIME"`

## Test Results

- `pytest apps/shops/tests/` — **118 passed, 0 failures**
- `python manage.py makemigrations --check --dry-run` — No changes detected

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. This plan adds a read-only string field with a static default. No new endpoints, auth paths, file access patterns, or schema changes at trust boundaries.

## Self-Check: PASSED

- [x] `apps/shops/models.py` contains `class SyncDepth(models.TextChoices)`
- [x] `apps/shops/models.py` contains `ONE_YEAR = "ONE_YEAR"` and `ALL_TIME = "ALL_TIME"`
- [x] `apps/shops/models.py` contains `sync_depth = models.CharField` with `default=SyncDepth.TWO_YEARS`
- [x] `apps/shops/migrations/0008_shop_sync_depth.py` exists and contains `AddField`
- [x] `apps/shops/serializers.py` contains `"sync_depth"`
- [x] `apps/shops/tests/test_models.py` contains `test_shop_sync_depth_choices_present`, `test_shop_sync_depth_defaults_to_two_years`
- [x] `apps/shops/tests/test_services.py` contains `test_create_shop_defaults_sync_depth_to_two_years`
- [x] `apps/shops/tests/test_views.py` contains `test_shop_list_includes_sync_depth`, `test_shop_detail_includes_sync_depth`
- [x] Commits `3c387fc` and `9cdcb10` exist in git log
