---
phase: 33-credit-visibility-staff-scoping
plan: 04
subsystem: api
tags: [django, drf, credits, staff-scoping, throttling, drf-spectacular, tenant-isolation]

requires:
  - phase: 33-credit-visibility-staff-scoping
    provides: get_accessible_shop_for_credits (plan 33-01)
  - phase: 29-credit-balances
    provides: get_shop_credit_balance virtual balance (never writes)
provides:
  - GET /api/v1/shops/{shop_id}/credits/ (ShopCreditsView, IsOrgScoped, no-store, 404 shop_not_found)
  - period_label(period) server-owned month label
  - ShopCreditsSerializer and shop_credits 120/minute throttle scope
  - SCOPE-01 table-driven negative sweep with a route-coverage guard
affects: [33-06, 33-07]

actuals:
  tokens: 45000
  tasks: 3
  commits: 3

plan_head_before: 681748025469b57efe3e6e72525a55493bd9841d
plan_head_after: f6e2e63d6ec7eedd73c3fe0b45cf169d98c6fe21

tech-stack:
  added: []
  patterns:
    - "Function-level import of apps.shops selector inside the credits view keeps the credits -> shops edge out of module scope"
    - "Table-driven negative sweep with a guard helper that returns route names lacking a row"

key-files:
  created:
    - apps/credits/tests/test_shop_credits_view.py
    - apps/credits/tests/test_scope_sweep.py
  modified:
    - apps/credits/services/periods.py
    - apps/credits/serializers.py
    - apps/credits/views.py
    - apps/credits/api_urls.py
    - config/settings/base.py
    - apps/credits/tests/test_periods.py
    - apps/credits/tests/test_settings.py

key-decisions:
  - "ShopCreditsView is an APIView in apps/credits at the tenant path /api/v1/shops/<int:shop_id>/credits/; the router's detail regex does not match it so no collision (route-resolution test)"
  - "request.user is cast to User for the shared selector (IsOrgScoped guarantees an authenticated user) to satisfy mypy"
  - "All out-of-scope, cross-org and unknown shops return the identical 404 body {code: shop_not_found}"

patterns-established:
  - "Read endpoints over virtual balances call only get_shop_credit_balance with current_period() read once, and assert row counts unchanged in tests"

requirements-completed: [CVIS-01, SCOPE-01]

coverage:
  - id: D1
    description: "Staff/Org Admin read a shop's current-month credits (virtual balance, period label, renewal date, total, is_enabled) with Cache-Control no-store and no writes"
    requirement: CVIS-01
    verification:
      - kind: integration
        ref: "apps/credits/tests/test_shop_credits_view.py#test_staff_reads_in_scope_shop_credits_and_gets_404_out_of_scope"
        status: pass
      - kind: integration
        ref: "apps/credits/tests/test_shop_credits_view.py#test_never_writes_rows_for_any_role_or_materialisation_state"
        status: pass
    human_judgment: false
  - id: D2
    description: "Calendar owned by the server: month label from English names, December rolls to January renewal"
    requirement: CVIS-01
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_periods.py#test_period_label_is_english_month_name_and_year"
        status: pass
      - kind: integration
        ref: "apps/credits/tests/test_shop_credits_view.py#test_returns_december_period_and_january_renewal_when_last_second_of_year"
        status: pass
    human_judgment: false
  - id: D3
    description: "Credits GET refuses out-of-scope Staff, cross-org Org Admin, unknown ids (404), Superadmin (403), anonymous; throttled at shop_credits; query count <= 5"
    requirement: SCOPE-01
    verification:
      - kind: integration
        ref: "apps/credits/tests/test_shop_credits_view.py (negative matrix, throttle, query ceiling)"
        status: pass
    human_judgment: false
  - id: D4
    description: "SCOPE-01 sweep over every credit route, the reviews credit-cost/generate-reply endpoints and Staff Shops list/retrieve, plus a guard failing on uncovered new routes"
    requirement: SCOPE-01
    verification:
      - kind: integration
        ref: "apps/credits/tests/test_scope_sweep.py"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-11-12
status: complete
---

# Phase 33 Plan 04: Shop credits read and SCOPE-01 sweep Summary

**Tenant- and Staff-scoped, never-writing, no-store GET /api/v1/shops/{id}/credits/ with a server-owned period label and renewal date, backed by a table-driven SCOPE-01 negative sweep over every credit route.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-11-12
- **Tasks:** 3
- **Files modified:** 9 (723 insertions, 5 deletions)

## Accomplishments
- `ShopCreditsView` returns `{shop_id, period, period_label, renews_on, allocated, bonus, consumed, remaining, total, is_enabled}` with `Cache-Control: no-store`; unmaterialised shops show the organisation's live allocation and no ShopCreditBalance, CreditTransaction or AuditLog row is written.
- Access goes through the shared `get_accessible_shop_for_credits`, so list, retrieve and credits GET cannot disagree; every unknown, cross-organisation or out-of-scope shop returns the same 404 body.
- `period_label` uses hard-coded English month names; December 2026 rolls to a 2027-01-01 renewal.
- `shop_credits` throttle scope at 120/minute, 429 proven; route resolves without colliding with the ShopViewSet; query count <= 5 for Org Admin and Staff, materialised or not.
- `test_scope_sweep.py`: 17 parametrised refusal cases plus 2 guard tests (guard proven to detect an uncovered route name).

## Task Commits

1. **Task 1: Tracer, Staff reads in-scope shop credits, 404 out of scope** - `085f714` (feat)
2. **Task 2: Credits GET matrix (calendar, shapes, roles, throttle, route, queries)** - `17a8f27` (test)
3. **Task 3: SCOPE-01 sweep with route-coverage guard** - `f6e2e63` (test)

**Plan metadata:** docs(33-04) commit following this summary.

## Files Created/Modified
- `apps/credits/services/periods.py` - `period_label`
- `apps/credits/serializers.py` - `ShopCreditsSerializer`
- `apps/credits/views.py` - `ShopCreditsView`
- `apps/credits/api_urls.py` - `shop-credits` route
- `config/settings/base.py` - `shop_credits` throttle rate
- `apps/credits/tests/test_shop_credits_view.py`, `test_scope_sweep.py` (new); `test_periods.py`, `test_settings.py` (extended)

## Decisions Made
- Kept the view in `apps/credits` with a function-level selector import (credits -> shops edge stays out of module scope; `apps.reviews` import invariant still 0).
- Cast `request.user` to `User` for typing rather than weakening the selector signature.

## Deviations from Plan

None - plan executed exactly as written. (Task 2 is marked tdd but the implementation already existed from the Task 1 tracer, so the matrix tests were written against it and all passed first run; no production change was needed in Task 2.)

## Issues Encountered
- mypy flagged `request.user` as `User | AnonymousUser` on first run of Task 1; resolved with a `cast`.
- OpenAPI generator: the new path `/api/v1/shops/{shop_id}/credits/` is present in the schema and no Error/Warning line names ShopCredits or the path. The generator's total output is 7 Warning lines and 11 Error lines, all pre-existing in other apps.
- The SCOPE-01 sweep found no scoping gaps: every case matched current behaviour, nothing to hand to Plan 33-07's tenant-security-auditor.

## User Setup Required
None - no external service configuration required.

## Verification
- `pytest apps/credits apps/shops`: green (pg_concurrency skipped on SQLite)
- mypy, ruff check, ruff format on `apps/credits config`: clean; pre-commit hooks passed on all commits
- `makemigrations --check --dry-run`: no changes
- Invariant: no `apps.reviews` import under `apps/credits` (non-test): 0

## Next Phase Readiness
Plan 33-06 can consume the frozen contract (`GET /api/v1/shops/{id}/credits/`, 404 `shop_not_found`, no-store). Plan 33-07 can reuse the sweep as the SCOPE-01 evidence.

---
*Phase: 33-credit-visibility-staff-scoping*
*Completed: 2026-11-12*

## Self-Check: PASSED
