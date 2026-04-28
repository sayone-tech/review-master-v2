---
phase: 07-regions
plan: 01
subsystem: api
tags: [django, drf, regions, viewset, serializers, services, selectors]

# Dependency graph
requires:
  - phase: 06-org-admin-shell
    provides: TenantScopedViewSet, IsOrgScoped, IsOrgAdmin, org_stub_view, org_admin_required
provides:
  - RegionHasShopsError exception with shop_count payload
  - create_region, update_region, delete_region service functions
  - list_regions selector
  - RegionReadSerializer, RegionCreateSerializer, RegionUpdateSerializer
  - RegionViewSet at /api/v1/regions/ (list, create, partial_update, destroy)
  - region_list template view at /admin/org/regions/
  - templates/regions/region_list.html mounting #region-modals-root and #region-table-root
affects: [07-regions-plan-02, 07-regions-plan-03, 08-shops]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-serializer pattern: RegionCreateSerializer/RegionUpdateSerializer for input, RegionReadSerializer for output"
    - "perform_create/perform_update overrides return Region instance (not None) for response body control"
    - "IntegrityError caught in viewset perform_* methods and re-raised as ValidationError with field key"
    - "RegionHasShopsError raised in service layer, caught in viewset destroy() and returned as 409"

key-files:
  created:
    - apps/regions/exceptions.py
    - apps/regions/services/__init__.py
    - apps/regions/services/regions.py
    - apps/regions/selectors/__init__.py
    - apps/regions/selectors/regions.py
    - apps/regions/serializers.py
    - apps/regions/views.py
    - templates/regions/region_list.html
  modified:
    - apps/regions/tests/factories.py
    - apps/organisations/urls.py
    - config/urls.py

key-decisions:
  - "RegionFactory.region_id uses RGN{n:03d} (no hyphen) — matches [A-Z0-9]{2,10} UniqueConstraint"
  - "perform_create/perform_update override return Region directly (not None) — avoids create/update needing to re-fetch"
  - "create/update overrides on ViewSet return RegionReadSerializer output — 201/200 body includes id and created_at"
  - "organisation null check in perform_create raises ValidationError (not AttributeError) — safe guard for org-less ORG_ADMIN edge case"
  - "EN DASH in validation strings replaced with HYPHEN-MINUS — passes ruff RUF001"

patterns-established:
  - "Regions ViewSet: GenericViewSet + explicit mixins (no ModelViewSet) — only list/create/partial_update/destroy exposed"
  - "TenantScopedViewSet auto-filters queryset by organisation_id — no per-view filter needed"
  - "Service layer raises domain exceptions (RegionHasShopsError); viewset translates to HTTP 409"

requirements-completed: [RGN-01, RGN-03, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02]

# Metrics
duration: 3min
completed: 2026-04-28
---

# Phase 7 Plan 1: Regions Backend Summary

**DRF RegionViewSet with service/selector layer, typed RegionHasShopsError exception, two-input-serializer pattern, and region_list template view wired to /admin/org/regions/**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-28T07:13:19Z
- **Completed:** 2026-04-28T07:16:22Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Complete backend layer for Regions CRUD: exceptions, services, selectors, serializers, ViewSet, template view
- RegionFactory hyphen bug fixed (RGN-000 -> RGN000), preventing 400 validation errors in API tests
- RegionViewSet at /api/v1/regions/ with org-scoped queryset, IntegrityError->400 and RegionHasShopsError->409 handling

## Task Commits

Each task was committed atomically:

1. **Task 7-01-01: Fix RegionFactory and create service/selector/exception scaffolding** - `a0f1791` (feat)
2. **Task 7-01-02: Serializers, ViewSet, template view, URLs, template** - `d27293b` (feat)

## Files Created/Modified

- `apps/regions/tests/factories.py` - Fixed region_id sequence from RGN-{n} to RGN{n:03d}
- `apps/regions/exceptions.py` - RegionHasShopsError with shop_count payload
- `apps/regions/services/__init__.py` - Empty init
- `apps/regions/services/regions.py` - create_region, update_region, delete_region with @transaction.atomic
- `apps/regions/selectors/__init__.py` - Empty init
- `apps/regions/selectors/regions.py` - list_regions(organisation_id) returning org-filtered queryset
- `apps/regions/serializers.py` - RegionReadSerializer (ModelSerializer), RegionCreateSerializer, RegionUpdateSerializer
- `apps/regions/views.py` - region_list template view + RegionViewSet with custom create/update/destroy
- `apps/organisations/urls.py` - Replaced org_stub_view for /admin/org/regions/ with region_list (name org_regions kept)
- `config/urls.py` - Registered RegionViewSet on router at api/v1/regions
- `templates/regions/region_list.html` - Template extending base_org.html with #region-modals-root and conditional #region-table-root

## Decisions Made

- `RegionFactory.region_id` uses `RGN{n:03d}` (no hyphen) — matches `[A-Z0-9]{2,10}` UniqueConstraint; old format `RGN-000` would fail regex validation on every POST
- `perform_create`/`perform_update` return `Region` directly (not `None`) so the overridden `create()`/`update()` methods can immediately wrap in `RegionReadSerializer` without a DB re-fetch
- Added explicit `isinstance(user, User)` check with organisation null guard in `perform_create` — raises ValidationError instead of AttributeError for org-less ORG_ADMIN edge case
- Replaced EN DASH (`–`) in validation error strings with HYPHEN-MINUS (`-`) to pass ruff RUF001

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type error: organisation parameter type too loose**
- **Found during:** Task 7-01-01 (pre-commit hook)
- **Issue:** `create_region(*, organisation: object, ...)` triggered mypy `misc` error — `object` is incompatible with `Organisation | Combinable` expected by Django's FK assignment
- **Fix:** Changed parameter type to `Organisation` and added `from apps.organisations.models import Organisation` import
- **Files modified:** `apps/regions/services/regions.py`
- **Verification:** mypy passed in next commit attempt
- **Committed in:** `a0f1791` (Task 7-01-01 commit)

**2. [Rule 1 - Bug] Fixed ruff violations in serializers and views**
- **Found during:** Task 7-01-02 (pre-commit hook)
- **Issue:** RUF012 (mutable class attrs without ClassVar), RUF001 (EN DASH in strings), B904 (raise without `from exc` in except clause)
- **Fix:** Added `ClassVar` annotations in Meta class, replaced EN DASH with HYPHEN-MINUS, added `from exc` to all re-raises in except blocks
- **Files modified:** `apps/regions/serializers.py`, `apps/regions/views.py`
- **Verification:** ruff check passed in next commit attempt
- **Committed in:** `d27293b` (Task 7-01-02 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs caught by pre-commit hooks)
**Impact on plan:** Both fixes necessary for type safety and linting compliance. No scope creep.

## Issues Encountered

None beyond the auto-fixed pre-commit failures above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (API tests) can now import all required files without compilation errors
- Plan 03 (React frontend) can rely on: RegionReadSerializer shape, /api/v1/regions/ endpoints, region_list.html template mounts
- No blockers for Plan 02

---
*Phase: 07-regions*
*Completed: 2026-04-28*
