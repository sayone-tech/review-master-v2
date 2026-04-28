---
phase: 07-regions
plan: "02"
subsystem: testing
tags: [pytest, factory-boy, django-rest-framework, coverage]

# Dependency graph
requires:
  - phase: 07-regions-01
    provides: RegionViewSet, services, selectors, serializers, exceptions, RegionFactory

provides:
  - Full pytest test suite for regions app (services, selectors, ViewSet, query ceiling, cross-tenant)
  - apps/regions/tests/test_services.py
  - apps/regions/tests/test_selectors.py
  - apps/regions/tests/test_views.py
  - apps/regions/tests/conftest.py
  - Bug fix: region_list.html missing {% load django_vite %}

affects:
  - 08-shops (cross-app dependency: ShopFactory used in delete-guard tests)
  - CI pipeline (coverage threshold verified at 98.67%)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "pytest conftest.py re-exports shared fixtures from apps.common.tests.fixtures for app-scoped auto-discovery"
    - "two_orgs_two_admins fixture returns dict — use ['org_a'] / ['admin_a'] key access"
    - "@transaction.atomic no-op = SAVEPOINT + RELEASE SAVEPOINT (2 queries inside test's outer transaction)"

key-files:
  created:
    - apps/regions/tests/test_services.py
    - apps/regions/tests/test_selectors.py
    - apps/regions/tests/test_views.py
    - apps/regions/tests/conftest.py
  modified:
    - templates/regions/region_list.html

key-decisions:
  - "07-02: test_no_save_when_no_changes asserts 2 queries (SAVEPOINT + RELEASE) not 0 — @transaction.atomic overhead inside test outer transaction"
  - "07-02: two_orgs_two_admins fixture returns dict, not tuple — tests use ['org_a'] key access"
  - "07-02: ShopFactory imported directly (exists in Phase 6 shops app) — no pytest.skip needed"
  - "07-02: conftest.py created in apps/regions/tests/ to re-export assert_query_ceiling and two_orgs_two_admins"

patterns-established:
  - "Per-app conftest.py re-exports shared fixtures — enables auto-discovery without global conftest pollution"

requirements-completed: [RGN-01, RGN-02, RGN-03, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02]

# Metrics
duration: 6min
completed: "2026-04-28"
---

# Phase 7 Plan 2: API Tests — Services, Selectors, ViewSet, Query Ceiling, Cross-Tenant Summary

**pytest suite with 36 tests at 98.67% coverage: service unit tests, selector isolation tests, ViewSet API tests (list/create/patch/delete), query-count ceiling at 5 queries, cross-tenant IDOR guard, and template view assertions**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-28T07:17:00Z
- **Completed:** 2026-04-28T07:23:08Z
- **Tasks:** 2
- **Files modified:** 5 (4 created, 1 template fixed)

## Accomplishments

- 14 service + selector unit tests: create/update/delete with error paths, cross-org isolation, creation order, inactive regions
- 22 ViewSet API tests: list, create validation (6 cases), duplicate ID, patch, delete guard (409), query ceiling (5 queries with 20 regions), cross-tenant IDOR, template empty/populated states
- Coverage 98.67% on apps/regions/ — exceeds 85% CI threshold

## Task Commits

1. **Task 7-02-01: Service and selector unit tests** - `90f5304` (test)
2. **Task 7-02-02: ViewSet API tests + conftest + template fix** - `cef625f` (test)

## Files Created/Modified

- `apps/regions/tests/test_services.py` - TestCreateRegion, TestUpdateRegion, TestDeleteRegion (14 tests)
- `apps/regions/tests/test_selectors.py` - TestListRegions: cross-org isolation, creation order, empty, inactive (4 tests)
- `apps/regions/tests/test_views.py` - Full ViewSet API tests + template view tests (22 tests)
- `apps/regions/tests/conftest.py` - Re-exports assert_query_ceiling + two_orgs_two_admins for auto-discovery
- `templates/regions/region_list.html` - Added missing `{% load django_vite %}` (bug fix)

## Decisions Made

- `test_no_save_when_no_changes` asserts `django_assert_num_queries(2)` not `(0)` — `@transaction.atomic` issues SAVEPOINT + RELEASE SAVEPOINT inside the test's outer transaction even when no SQL UPDATE is issued
- `two_orgs_two_admins` returns a dict (`{"org_a": ..., "admin_a": ...}`), not a positional tuple — test uses key access
- ShopFactory available from Phase 6 shops app — imported directly without `pytest.skip` guard
- `conftest.py` created for regions/tests — follows the pattern established in apps/organisations/tests/conftest.py and apps/common/tests/conftest.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing `{% load django_vite %}` in region_list.html**
- **Found during:** Task 7-02-02 (template view tests)
- **Issue:** `region_list.html` uses `{% vite_asset 'region-management' %}` in `extra_js` block but has no `{% load django_vite %}` — causes `TemplateSyntaxError: Invalid block tag 'vite_asset'` at render time
- **Fix:** Added `django_vite` to the existing `{% load static %}` → `{% load static django_vite %}`
- **Files modified:** `templates/regions/region_list.html`
- **Verification:** `test_region_list_template_empty_state` and `test_region_list_template_with_regions` pass
- **Committed in:** `cef625f` (Task 7-02-02 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Template would crash in production without this fix. No scope creep.

## Issues Encountered

- Ruff lint: `SIM105` — replaced `try/except/pass` with `contextlib.suppress()` in service test
- Ruff lint: `RUF059` — prefixed unused `admin` with `_admin` in two list tests
- Ruff lint: `F841` — removed unused `org_a` assignment in cross-tenant isolation test
- All lint issues resolved before final commit; pre-commit hooks passed cleanly

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 36 region tests pass (98.67% coverage)
- delete-guard tests use ShopFactory from Phase 6 shops app — confirmed working
- Plan 03 (React UI) can proceed: template view confirmed to render region-modals-root and region-table-root conditionally

---
*Phase: 07-regions*
*Completed: 2026-04-28*
