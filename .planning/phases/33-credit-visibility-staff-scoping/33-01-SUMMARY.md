---
phase: 33-credit-visibility-staff-scoping
plan: 01
subsystem: api
tags: [django, drf, staff-scoping, credits, selectors, json_script]

requires:
  - phase: 29-credit-balances
    provides: annotate_credit_state virtual balance annotation
  - phase: 30-credit-consumption
    provides: apps.credits must not import apps.reviews dependency rule
provides:
  - restrict_to_staff_scope shared Staff rule (role-keyed)
  - list_shops(user=, with_credits=, period=) with one-query credit annotation
  - get_accessible_shop_for_credits single-shop credits access gate
  - ShopReadSerializer credits_allocated/bonus/remaining/total fields
  - Staff-scoped ShopViewSet retrieve (D-17)
  - credit-contact json_script bootstrap on the Shops page
affects: [33-04, 33-05, 33-06, 33-07]

actuals:
  tokens: 28000
  tasks: 3
  commits: 3

plan_head_before: 9d339eb03155d125ac728a02c9cdc5355f52a31f
plan_head_after: 09e499dd06891d2102376fcf4e32874bf4670d3d

tech-stack:
  added: []
  patterns:
    - "Role-keyed Staff scoping (never id-list truthiness) shared by list, retrieve and credits GET"
    - "Optional serializer fields default to None for un-annotated rows"

key-files:
  created: []
  modified:
    - apps/shops/selectors/shops.py
    - apps/shops/serializers.py
    - apps/shops/views.py
    - templates/shops/shop_list.html
    - apps/shops/tests/test_selectors.py
    - apps/shops/tests/test_views.py

key-decisions:
  - "User imported at module level in apps/shops/selectors/shops.py (no import cycle arose), so no TYPE_CHECKING fallback was needed"
  - "get_accessible_shop_for_credits lives in apps/shops (not apps/credits) and is built on list_shops so it shares the exact Staff rule"
  - "Flat credits_* fields rather than a nested object"

requirements-completed: [SCOPE-01, CVIS-02, CVIS-04]

coverage:
  - id: D1
    description: "Staff GET /api/v1/shops/ returns only in-scope shops (empty scope -> empty, foreign-org region never leaks) with virtual credit fields and no writes"
    requirement: SCOPE-01
    verification:
      - kind: integration
        ref: "apps/shops/tests/test_views.py#test_staff_list_returns_only_in_scope_shops_with_credit_fields"
        status: pass
      - kind: unit
        ref: "apps/shops/tests/test_selectors.py#TestListShopsScopeMatrix"
        status: pass
    human_judgment: false
  - id: D2
    description: "Staff retrieve of an out-of-scope shop is 404; Org Admin retrieve unchanged; shared get_accessible_shop_for_credits gate"
    requirement: SCOPE-01
    verification:
      - kind: integration
        ref: "apps/shops/tests/test_views.py#TestShopsStaffScopeRetrieveAndCounts"
        status: pass
      - kind: unit
        ref: "apps/shops/tests/test_selectors.py#TestGetAccessibleShopForCredits"
        status: pass
    human_judgment: false
  - id: D3
    description: "Shops list credit annotation uses a fixed query count (1 selector query; equal 1-vs-20 API counts, <=7) for Org Admin and Staff"
    requirement: CVIS-02
    verification:
      - kind: unit
        ref: "apps/shops/tests/test_selectors.py#test_issues_one_query_when_credits_enabled_for_org_admin"
        status: pass
      - kind: integration
        ref: "apps/shops/tests/test_views.py#test_list_query_count_is_equal_for_1_and_20_shops_when_credits_enabled"
        status: pass
    human_judgment: false
  - id: D4
    description: "Shops page bootstraps credit-contact (organisation name + support email), escaped by json_script, page remains Org-Admin-only"
    requirement: CVIS-04
    verification:
      - kind: integration
        ref: "apps/shops/tests/test_views.py#TestShopListCreditContactBootstrap"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-11-12
status: complete
---

# Phase 33 Plan 01: Staff-scoped Shops API with virtual credit fields Summary

**Role-keyed Staff scoping on the Shops list and retrieve, with one-query virtual credit balances on every row and a credit-contact bootstrap for the Buy More modal.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-11-11T19:13:00Z
- **Completed:** 2026-11-11T19:21:32Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- `restrict_to_staff_scope` filters on `role == STAFF_ADMIN`, so a Staff user with no `StaffAccessScope` rows gets an empty list instead of the whole organisation, and a foreign-organisation region scope never leaks because the organisation filter is applied first.
- `list_shops` gained optional `user`, `with_credits`, `period`; with credits it adds one LEFT JOIN annotation (1 query for 1 or 20 shops); the team page call is unchanged.
- `ShopReadSerializer` exposes `credits_allocated`, `credits_bonus`, `credits_remaining`, `credits_total`, null on un-annotated rows (retrieve/create/update/activate/deactivate).
- `ShopViewSet.get_queryset` applies the Staff rule after the tenant filter, so retrieve is 404 for out-of-scope Staff (D-17).
- `get_accessible_shop_for_credits` is the single access gate for Plan 33-04's credits GET.
- The Shops page renders credits in `shop-data` and a `credit-contact` json_script (D-13..D-15); `@org_admin_required` untouched (D-18).

## Task Commits

1. **Task 1: Tracer, Staff list with credits** - `094ce35` (feat)
2. **Task 2: Scope matrix, Staff retrieve, shared access selector, query count** - `169dc48` (feat)
3. **Task 3: Shops page credits + credit-contact bootstrap** - `09e499d` (feat)

**Plan metadata:** see docs(33-01) commit following this summary.

## Files Created/Modified
- `apps/shops/selectors/shops.py` - restrict_to_staff_scope, widened list_shops, get_accessible_shop_for_credits
- `apps/shops/serializers.py` - four credit fields
- `apps/shops/views.py` - get_queryset Staff scoping, list/shop_list wiring, credit_contact context
- `templates/shops/shop_list.html` - credit-contact json_script
- `apps/shops/tests/test_selectors.py`, `apps/shops/tests/test_views.py` - tracer, scope matrix, query counts, bootstrap tests

## Decisions Made
- Imported `User` at module level in the selector; no cycle occurred, so the TYPE_CHECKING fallback was unnecessary.
- Kept the access selector in `apps/shops` to preserve the invariant that `apps/credits` never imports `apps.reviews` (grep still 0).
- SCOPE-01 behaviour change (Staff incl. JWT mobile clients stop seeing out-of-scope shops) was pre-approved (research option b).

## Deviations from Plan

None - plan executed exactly as written. (Query-count API tests pass `?page_size=100` so 20 shops fit one page; a test detail, not a code change.)

## Issues Encountered
None.

## Verification
- `pytest apps/shops apps/organisations apps/credits apps/reviews`: green
- mypy, ruff check, ruff format on `apps/shops`: clean; pre-commit hooks passed on all three commits
- `makemigrations --check --dry-run`: no changes
- Invariant: no `apps.reviews` import under `apps/credits` (non-test): 0

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Plans 33-04 (credits GET using `get_accessible_shop_for_credits`) and 33-06 (UI consuming the four credit fields and `credit-contact`) can build on the frozen contract.

---
*Phase: 33-credit-visibility-staff-scoping*
*Completed: 2026-11-12*

## Self-Check: PASSED
