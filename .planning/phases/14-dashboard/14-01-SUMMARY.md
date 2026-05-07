---
phase: 14-dashboard
plan: "01"
subsystem: dashboard
tags: [dashboard, filters, cache, indexes, security]
dependency_graph:
  requires: [apps.reviews.selectors.reviews.get_accessible_shop_ids, apps.shops.models.Shop]
  provides: [apps.dashboard.filters.DashboardFilterParams, apps.dashboard.filters.validate_filter_params, apps.dashboard.services.cache.dashboard_cache_key]
  affects: [apps.reviews.models.Review]
tech_stack:
  added: []
  patterns: [frozen-dataclass, services-selectors, scope-aware-cache-key, composite-indexes]
key_files:
  created:
    - apps/dashboard/__init__.py
    - apps/dashboard/apps.py
    - apps/dashboard/filters.py
    - apps/dashboard/services/__init__.py
    - apps/dashboard/services/cache.py
    - apps/dashboard/tests/__init__.py
    - apps/dashboard/tests/conftest.py
    - apps/dashboard/tests/test_filters.py
    - apps/reviews/migrations/0006_dashboard_indexes.py
  modified:
    - apps/reviews/models.py
    - apps/reviews/tests/test_models.py
    - config/settings/base.py
decisions:
  - validate_filter_params handles ORG_ADMIN by querying all active org shops directly, since get_accessible_shop_ids only resolves StaffAccessScope entries
  - filter_hash includes shop_ids list to enforce cross-user cache isolation (DASH-C1)
metrics:
  duration_minutes: 2
  completed_date: "2026-05-07"
  tasks_completed: 3
  files_changed: 13
---

# Phase 14 Plan 01: Dashboard Foundation — Filters, Cache, Indexes Summary

**One-liner:** Frozen `DashboardFilterParams` dataclass with scope-aware `filter_hash()`, `validate_filter_params()` enforcing 403/400 security boundaries, scope-aware cache key helpers, and three composite indexes on Review for dashboard query plans.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create apps/dashboard/ skeleton, register in INSTALLED_APPS | becb91e | apps/dashboard/*, config/settings/base.py |
| 2 | Implement DashboardFilterParams + validate_filter_params() with security tests | 256c56e | apps/dashboard/filters.py, tests/test_filters.py, tests/conftest.py |
| 3 | Implement services/cache.py + Review composite-index migration + index sanity test | 27e6dd3 | apps/dashboard/services/cache.py, apps/reviews/migrations/0006_dashboard_indexes.py, apps/reviews/models.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed get_accessible_shop_ids call signature mismatch**
- **Found during:** Task 2
- **Issue:** Plan specified `get_accessible_shop_ids(user=user)` but the selector signature is `get_accessible_shop_ids(user_id: int)`.
- **Fix:** Call `get_accessible_shop_ids(user_id=user.id)` instead.
- **Files modified:** apps/dashboard/filters.py
- **Commit:** 256c56e

**2. [Rule 2 - Missing critical functionality] ORG_ADMIN accessible shops handling**
- **Found during:** Task 2
- **Issue:** `get_accessible_shop_ids` only resolves `StaffAccessScope` entries; for ORG_ADMIN users it returns an empty list, causing all shop filters to fail as "out of scope".
- **Fix:** Added `_get_all_org_shop_ids()` helper; `validate_filter_params` branches on `user.role == STAFF_ADMIN` vs ORG_ADMIN.
- **Files modified:** apps/dashboard/filters.py
- **Commit:** 256c56e

## Verification Results

- `pytest apps/dashboard/ apps/reviews/tests/test_models.py::test_review_meta_indexes` — 6 passed
- `python manage.py check` — no issues
- `python manage.py makemigrations --check --dry-run` — no missing migrations
- `grep -q "apps.dashboard" config/settings/base.py` — passes

## Self-Check: PASSED

All expected files exist and all task commits verified.
