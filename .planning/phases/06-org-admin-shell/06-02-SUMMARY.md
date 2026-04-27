---
phase: 06-org-admin-shell
plan: 02
subsystem: auth
tags: [django, drf, rbac, multi-tenant, permissions, testing, django-sequences]

# Dependency graph
requires:
  - phase: 06-01
    provides: "User model with Role enum, organisation FK, InvitationToken, StaffAccessScope"
provides:
  - "IsOrgAdmin DRF permission class + org_admin_required template decorator (apps/accounts/permissions.py)"
  - "IsOrgScoped DRF permission with mandatory has_object_permission IDOR prevention (apps/common/permissions.py)"
  - "TenantScopedViewSet base class for all Phase 7-9 Org/Staff Admin viewsets (apps/common/viewsets.py)"
  - "two_orgs_two_admins + assert_query_ceiling reusable test fixtures (apps/common/tests/fixtures.py)"
  - "Cross-tenant isolation test scaffold proving dashboard scoping (apps/common/tests/test_isolation.py)"
  - "django-sequences Django 6 compatibility smoke test PASSED (apps/common/tests/test_sequences_smoke.py)"
affects: [07-regions, 08-shops, 09-team, all-org-admin-viewsets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IsOrgScoped.has_object_permission override pattern — mandatory for all detail/mutation endpoints"
    - "TenantScopedViewSet super().get_queryset().filter(organisation_id=...) auto-scoping pattern"
    - "org_admin_required decorator returns HttpResponseForbidden (403) not redirect for wrong-role users"
    - "assert_query_ceiling fixture pattern for fixed-ceiling query count assertions in tests"
    - "two_orgs_two_admins fixture for cross-tenant isolation test scaffolding"

key-files:
  created:
    - apps/common/permissions.py
    - apps/common/viewsets.py
    - apps/common/tests/conftest.py
    - apps/common/tests/fixtures.py
    - apps/common/tests/test_permissions.py
    - apps/common/tests/test_viewsets.py
    - apps/common/tests/test_isolation.py
    - apps/common/tests/test_sequences_smoke.py
  modified:
    - apps/accounts/permissions.py
    - apps/accounts/tests/test_permissions.py

key-decisions:
  - "IsOrgScoped lives in apps/common (not apps/accounts) because it is cross-cutting and role-agnostic across ORG_ADMIN and STAFF_ADMIN"
  - "org_admin_required returns HttpResponseForbidden (not redirect) for wrong-role users — prevents silent 302 masking auth failures"
  - "TenantScopedViewSet returns qs.none() when user has no organisation_id — prevents accidental full-table exposure"
  - "django-sequences HIGH compatibility prediction CONFIRMED: smoke test passed against Django 6 + test DB"
  - "Phase 7-9 tests should import from apps.common.tests.fixtures (explicit) not conftest (which only covers common/tests/)"

patterns-established:
  - "Permission composition for Org Admin views: IsOrgAdmin (DRF) or IsOrgAdmin & IsOrgScoped (detail/mutation)"
  - "Permission composition for Staff Admin views: IsOrgScoped (covers both roles with org)"
  - "All Org/Staff Admin viewsets inherit TenantScopedViewSet as base; Superadmin viewsets must NOT"
  - "Cross-tenant isolation tests use two_orgs_two_admins fixture from apps.common.tests.fixtures"

requirements-completed: [XMOD-05]

# Metrics
duration: 6min
completed: 2026-04-27
---

# Phase 6 Plan 02: Multi-Tenant Security Foundation Summary

**IsOrgAdmin/IsOrgScoped permission classes + TenantScopedViewSet with IDOR-prevention has_object_permission, plus shared test fixtures and confirmed django-sequences Django 6 compatibility**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-27T11:15:30Z
- **Completed:** 2026-04-27T11:21:30Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Multi-tenant security foundation: IsOrgAdmin (DRF + template decorator), IsOrgScoped (with critical has_object_permission override), and TenantScopedViewSet — all 21 unit tests pass
- Shared test fixtures `two_orgs_two_admins` and `assert_query_ceiling` in `apps/common/tests/fixtures.py` with cross-tenant isolation tests proving org_a admin cannot see org_b's organisation in dashboard context
- django-sequences compatibility smoke test PASSED — HIGH-confidence prediction confirmed, SequenceCounter fallback model also verified available

## Task Commits

Each task was committed atomically:

1. **Task 1: IsOrgAdmin, IsOrgScoped, TenantScopedViewSet** - `ec95f3d` (feat)
2. **Task 2: Shared fixtures, isolation scaffold, sequences smoke test** - `6a2cb12` (feat)

## Files Created/Modified

- `apps/accounts/permissions.py` - Added IsOrgAdmin DRF permission + org_admin_required template decorator (returns 403, not redirect)
- `apps/accounts/tests/test_permissions.py` - Added 7 new tests for IsOrgAdmin and org_admin_required decorator
- `apps/common/permissions.py` - New: IsOrgScoped with has_permission + has_object_permission for IDOR prevention
- `apps/common/viewsets.py` - New: TenantScopedViewSet base class filtering by organisation_id
- `apps/common/tests/test_permissions.py` - New: 7 tests for IsOrgScoped including object-level checks
- `apps/common/tests/test_viewsets.py` - New: 2 tests for TenantScopedViewSet filtering behaviour
- `apps/common/tests/fixtures.py` - New: two_orgs_two_admins + assert_query_ceiling reusable fixtures
- `apps/common/tests/conftest.py` - New: auto-discovery re-export for common/tests directory
- `apps/common/tests/test_isolation.py` - New: 4 cross-tenant isolation scaffold tests (XMOD-05)
- `apps/common/tests/test_sequences_smoke.py` - New: 2 django-sequences compatibility smoke tests

## Decisions Made

- IsOrgScoped lives in `apps/common` (not `apps/accounts`) because it is cross-cutting and applies to both ORG_ADMIN and STAFF_ADMIN roles
- `org_admin_required` returns `HttpResponseForbidden` not a redirect for wrong-role authenticated users — prevents silent 302 masking auth failures in template views
- `TenantScopedViewSet.get_queryset()` returns `qs.none()` when `user.organisation_id is None` — safe default prevents accidental full-table exposure
- django-sequences HIGH compatibility prediction CONFIRMED: `get_next_value()` returns sequential integers against Django 6 + test DB; SequenceCounter fallback is ready but not needed
- Phase 7-9 tests must explicitly `from apps.common.tests.fixtures import two_orgs_two_admins, assert_query_ceiling` — conftest only auto-discovers within `apps/common/tests/`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type errors in org_admin_required and TenantScopedViewSet**
- **Found during:** Task 1 (commit attempt via pre-commit hook)
- **Issue:** `return view_func(...)` typed as Any; `GenericViewSet` missing type parameter
- **Fix:** Added proper Callable type annotation to `org_admin_required`; used `GenericViewSet[Any]` for TenantScopedViewSet
- **Files modified:** apps/accounts/permissions.py, apps/common/viewsets.py
- **Verification:** mypy hook passes with no errors
- **Committed in:** ec95f3d (Task 1 commit)

**2. [Rule 1 - Bug] Fixed ruff F811 and PT018 linting errors in test files**
- **Found during:** Task 2 (commit attempt via pre-commit hook)
- **Issue:** test_isolation.py imported fixtures directly causing F811 redefinition; test_sequences_smoke.py had compound assertions (PT018)
- **Fix:** Removed explicit fixture imports from test_isolation.py (conftest auto-discovers them); split compound assertions into separate assert statements
- **Files modified:** apps/common/tests/test_isolation.py, apps/common/tests/test_sequences_smoke.py
- **Verification:** ruff check passes, all 6 tests still pass
- **Committed in:** 6a2cb12 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — type and linting fixes)
**Impact on plan:** Purely correctness fixes, no scope creep. All plan objectives delivered as specified.

## Issues Encountered

- Pre-existing test failure in `apps/common/tests/test_components.py::test_empty_state_renders_icon_title_desc_cta` (unrelated to this plan, was already failing before execution). Logged as out-of-scope per scope boundary rule.

## Sequences Smoke Test Result

**PASSED** — django-sequences 3.0 HIGH compatibility prediction CONFIRMED.

- `get_next_value("phase6_smoke_test")` returned sequential integers (first=1, second=2) against Django 6 + test DB
- SequenceCounter fallback model is available and verified (can be activated in Phase 7 if needed)
- Phase 7 can use django-sequences as the primary region_id generation mechanism with full confidence

## Permission Class Reference for Phase 7-9

| Class | Location | Use when |
|-------|----------|----------|
| `IsOrgAdmin` | `apps.accounts.permissions` | DRF viewsets restricted to Org Admin only |
| `IsOrgScoped` | `apps.common.permissions` | DRF viewsets shared between Org Admin and Staff Admin |
| `IsOrgAdmin & IsOrgScoped` | compose both | Detail/mutation endpoints needing full IDOR protection |
| `org_admin_required` | `apps.accounts.permissions` | Template view decorator for Org Admin only pages |
| `TenantScopedViewSet` | `apps.common.viewsets` | Base class for ALL Org/Staff Admin DRF viewsets |

**Test fixture import path for Phase 7-9:**
```python
from apps.common.tests.fixtures import two_orgs_two_admins, assert_query_ceiling
```

## Next Phase Readiness

- Multi-tenant security layer complete; all Phase 7-9 Org/Staff Admin viewsets can inherit `TenantScopedViewSet` and compose `IsOrgAdmin`/`IsOrgScoped`
- Cross-tenant isolation test pattern established; Phase 7-9 will add per-resource tests using `two_orgs_two_admins`
- django-sequences confirmed compatible; Phase 7 Regions service can use `get_next_value()` for region_id generation without fallback activation
- No blockers for Phase 7

---
*Phase: 06-org-admin-shell*
*Completed: 2026-04-27*
