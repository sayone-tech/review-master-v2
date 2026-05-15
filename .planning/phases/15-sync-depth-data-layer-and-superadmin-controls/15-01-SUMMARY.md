---
phase: 15-sync-depth-data-layer-and-superadmin-controls
plan: "01"
subsystem: api
tags: [django, drf, postgresql, migrations, boolean-field]

# Dependency graph
requires:
  - phase: 14-dashboard
    provides: Existing Organisation model + serializers + services pattern

provides:
  - Organisation.allow_custom_sync_depth BooleanField(default=False) with migration 0002
  - create_organisation service accepts allow_custom_sync_depth kwarg
  - update_organisation supports toggling via _UPDATABLE_FIELDS
  - All four serializers (List/Detail/Create/Update) expose allow_custom_sync_depth
  - API endpoints POST/PATCH/GET org return the field

affects:
  - 15-02 (Shop sync_depth field depends on this org flag being in place)
  - 16 (Org Admin shop creation selector checks organisation.allow_custom_sync_depth)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - BooleanField with default=False for feature-flag style org-level toggles
    - _UPDATABLE_FIELDS frozenset controls which fields update_organisation accepts

key-files:
  created:
    - apps/organisations/migrations/0002_organisation_allow_custom_sync_depth.py
  modified:
    - apps/organisations/models.py
    - apps/organisations/services/organisations.py
    - apps/organisations/serializers.py
    - apps/organisations/tests/test_models.py
    - apps/organisations/tests/test_services.py
    - apps/organisations/tests/test_views.py

key-decisions:
  - "No db_index on allow_custom_sync_depth — boolean low cardinality, never used in filtering"
  - "OrganisationDetailSerializer inherits from OrganisationListSerializer so field propagates automatically"
  - "create_organisation returns (org, raw_token) tuple — allow_custom_sync_depth added as keyword-only param after number_of_stores"
  - "Auth-client fixture name used in tests: api_client_superadmin (confirmed from conftest.py)"

patterns-established:
  - "Boolean org feature flags: BooleanField(default=False) + in _UPDATABLE_FIELDS + serializer Meta.fields"

requirements-completed: [SYNC-01, SYNC-02, SYNC-03]

# Metrics
duration: 12min
completed: 2026-05-15
---

# Phase 15 Plan 01: Sync Depth Data Layer and Superadmin Controls Summary

**`allow_custom_sync_depth` BooleanField added to Organisation model with migration 0002, propagated through create/update services and all four DRF serializers so Superadmins can set and read it via `/api/v1/organisations/`**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-15T10:55:00Z
- **Completed:** 2026-05-15T11:07:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Migration 0002 adds `allow_custom_sync_depth = BooleanField(default=False)` to existing org rows without a data migration
- Service layer: `create_organisation` accepts `allow_custom_sync_depth` kwarg; `_UPDATABLE_FIELDS` includes it for toggle via `update_organisation`
- All four serializers expose the field: `OrganisationListSerializer`, `OrganisationDetailSerializer` (inherits), `OrganisationCreateSerializer`, `OrganisationUpdateSerializer`
- 9 new tests covering model defaults, service create/update, and all four API operations (list, detail, create, patch)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add allow_custom_sync_depth field + migration + model test** - `e223f1e` (feat)
2. **Task 2: Wire allow_custom_sync_depth through services + serializers + tests** - `378fbe7` (feat)

_Note: TDD tasks had test (RED) written first, then implementation (GREEN). Both tasks committed after GREEN passed._

## Files Created/Modified
- `apps/organisations/models.py` - Added `allow_custom_sync_depth = models.BooleanField(default=False)` after `number_of_stores`
- `apps/organisations/migrations/0002_organisation_allow_custom_sync_depth.py` - AddField migration with dependency on `0001_initial`
- `apps/organisations/services/organisations.py` - Added param to `create_organisation`; added field to `_UPDATABLE_FIELDS`
- `apps/organisations/serializers.py` - Added field to List, Create, and Update serializer `Meta.fields`
- `apps/organisations/tests/test_models.py` - Two new tests for default=False and explicit True
- `apps/organisations/tests/test_services.py` - Three new tests for service create/update
- `apps/organisations/tests/test_views.py` - Four new API tests for list/detail/create/patch

## Decisions Made
- No `db_index` on `allow_custom_sync_depth` — boolean low cardinality, never used in queryset filtering per RESEARCH anti-patterns
- `OrganisationDetailSerializer` inherits from `OrganisationListSerializer` — field propagates automatically without an explicit change
- Auth-client fixture confirmed as `api_client_superadmin` (from `apps/organisations/tests/conftest.py`)
- `OrgType.RETAIL` is the correct org type choice value used in service tests

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- Ruff formatter reformatted `serializers.py` inline field lists into multi-line format on first commit attempt. Re-staged the auto-formatted file and committed successfully.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- `Organisation.allow_custom_sync_depth` is live in migration and API — Phase 15 Plan 02 (Shop `sync_depth` field) and Phase 16 (Org Admin shop creation selector) can depend on this field
- The `api_client_superadmin` fixture name is confirmed for downstream plans referencing the Superadmin API client

---
*Phase: 15-sync-depth-data-layer-and-superadmin-controls*
*Completed: 2026-05-15*
