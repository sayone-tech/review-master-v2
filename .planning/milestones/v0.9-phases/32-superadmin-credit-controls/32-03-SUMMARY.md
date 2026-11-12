---
phase: 32-superadmin-credit-controls
plan: 03
subsystem: credits
tags: [django, drf, credits, superadmin, bonus, audit-log, select-for-update, throttling, openapi]
status: complete

requires:
  - phase: 29-credits-ledger-foundation
    provides: ShopCreditBalance, CreditTransaction, ensure_balance, annotate_credit_state
  - phase: 32-superadmin-credit-controls (plan 01)
    provides: org_current_month_allocation_expression, organisation-row -> balance-row lock order
provides:
  - allocate_bonus service and BonusResult (CSUP-01)
  - POST /api/v1/superadmin/shops/{shop_id}/credits/bonus/
  - GET /api/v1/superadmin/organisations/{org_id}/credits/shops/
  - PeriodMismatchError, ShopNotAvailableError
  - list_org_shop_credits, get_org_allocation_per_shop read-only selectors
  - throttle scopes superadmin_credits_read (120/minute) and superadmin_credits_write (30/minute)
  - AuditLog action shop.credits.bonus_allocated
affects: [32-04, 32-05, 33-credit-visibility]

actuals:
  tokens: 21000
  tasks: 3
  commits: 3
plan_head_before: 14bdd184a6481187d4e096a0e85363d7d02d22cf
plan_head_after: a393b1ef0b3cfe231e7a2eeb791cb31c9e00e502

tech-stack:
  added: []
  patterns:
    - "Superadmin-only non-tenant APIView with IsAuthenticated + IsSuperadmin and ScopedRateThrottle"
    - "Service reads the period once, refuses a stale echo with a read-only 409 carrying the fresh balance, then writes in one atomic"
    - "Paginated list view appends header fields (period, allocation_per_shop) to get_paginated_response data"

key-files:
  created:
    - apps/credits/services/bonus.py
    - apps/credits/selectors/shop_credits.py
    - apps/credits/serializers.py
    - apps/credits/views.py
    - apps/credits/api_urls.py
    - apps/credits/tests/test_bonus.py
    - apps/credits/tests/test_views.py
  modified:
    - apps/credits/exceptions.py
    - config/urls.py
    - config/settings/base.py

key-decisions:
  - "Bonus order: period echo check (409, read-only) -> availability check (404) -> one atomic: organisation-row lock -> ensure_balance -> balance-row lock -> F() increment with explicit updated_at -> BONUS_ALLOCATION ledger -> AuditLog"
  - "Reason text lives only in CreditTransaction.note (trimmed, NULL when blank); AuditLog carries has_reason boolean only"
  - "No cumulative cap on bonus (D-10); amount bound 1..10000 per request in both serializer and service"
  - "Shop list page size fixed at 10 with no client size parameter; ordered by name then pk for stable paging"

requirements-completed: [CSUP-01, CSUP-02]

duration: ~25 min
completed: 2026-11-11
---

# Phase 32 Plan 03: Superadmin bonus top-up and shop credit list Summary

Superadmin-only API that tops up a shop's current-month credits atomically (balance F() increment + BONUS_ALLOCATION ledger + audit row, stale-period 409 with fresh balance, 404 for unavailable shops) and lists an organisation's active shops with virtual or materialised balances, paged and never writing.

## Accomplishments

- **Tracer (CSUP-01):** a Superadmin POST of 50 on a never-used shop of a 100-allocation organisation returns 201 `{shop_id, period, allocated 100, bonus 50, consumed 0, remaining 150, transaction_id}`, creating one balance, one INITIAL_ALLOCATION (+100), one BONUS_ALLOCATION (+50, COMMITTED, actor, note) and one `shop.credits.bonus_allocated` audit row with the exact key sets; the ledger reconciles.
- **Edge matrix:** 409 `period_mismatch` for previous, future and rolled-over months with no writes and the fresh (virtual) balance in the body; 404 `shop_unavailable` for inactive, unknown and DELETED-organisation shops; DISABLED organisations accepted (D-03); 400 per offending field; boundaries 1 and 10000 and two 10000 allocations succeed (D-10); blank/whitespace/omitted reason stores NULL note and `has_reason` false; reason text never reaches audit data; 0-allocation organisations get a zero row without INITIAL, and a later 0 -> 50 edit raises it (remaining 59); 403 for Org Admin (own organisation) and Staff, 401/403 anonymous; 429 on the write throttle.
- **Shop list (CSUP-01):** `{count, next, previous, period, allocation_per_shop, results}`, 10 per page, active shops only, name-then-id order, case-insensitive search, virtual balances for unmaterialised shops, `allocation_per_shop` via the same D-21 expression as the organisation list; no INSERT/UPDATE/DELETE issued; query count identical for 2 and 12 shops (<= 4); 404 `organisation_not_found` for deleted/unknown organisations; same 403 matrix.
- **OpenAPI:** both endpoints appear in the drf-spectacular schema.

## Task Commits

1. Task 1 (tracer): `71eec10` feat(32-03): Superadmin bonus top-up endpoint with atomic ledger and audit write
2. Task 2: `1e36fdd` test(32-03): bonus edge matrix for period, availability, validation, reason, roles and throttle
3. Task 3: `a393b1e` feat(32-03): Superadmin organisation shop credit list with search, pagination and virtual balances

## Verification (real output)

- `.venv/bin/pytest apps/credits -q --no-cov`: all passed (11 pg_concurrency skipped on SQLite); `test_bonus.py` + `test_views.py` run together in Task 2 had 32 tests passing, before the 10 list tests were added
- `.venv/bin/pytest apps/ -q -o addopts="" -p no:warnings`: **1563 passed, 18 skipped**
- `.venv/bin/mypy apps/credits config`: Success, no issues found in 57 source files
- `.venv/bin/ruff check apps/credits config` and `ruff format --check`: clean
- `manage.py spectacular --validate` (test settings): exit 0; schema contains both paths; the generator log has no Error or Warning entry for `CreditShopListView` or `BonusAllocationView` (the log holds 10 `Error [` and 7 `Warning [` lines from other apps, none mentioning credits)
- Query-count tests: shop list identical query count for 2 and 12 shops, ceiling <= 4 (passes)
- Source-scan invariants: `cas_status(` count in bonus.py is 0; no non-test `apps.reviews` import under apps/credits
- Pre-commit hooks (ruff, mypy, bandit, missing-migrations, gitleaks) passed on all three commits
- Not run: Postgres-backed `pg_concurrency` tests (no Postgres/docker; they belong to Plan 32-05), `tenant-security-auditor` / `orm-performance-auditor` subagents (not in this plan's tasks)

## Deviations from Plan

None - plan executed exactly as written. Notes without rule-triggering deviation:

- Task 3's selector and view code were written after Task 2 as planned; the list `CreditShopRowSerializer`, `CreditShopListResponseSerializer` and the other schema serializers were already created in Task 1's `serializers.py` (the plan lists them there), so Task 3's commit touched `serializers.py` only through formatting.
- The plan's Task 3 selector uses function-level imports of `Shop` and `Organisation` (matching `balances.py`); `bonus.py` imports them at module level and no import cycle appeared.
- `tdd="true"` on Task 2: the Task 1 production code satisfied every behaviour on the first run, so Task 2 is a tests-only commit with no separate GREEN fix.

**Total deviations:** 0. **Impact:** none.

## Threat Surface

T-32-12..T-32-21 mitigated as planned: Superadmin-only permission on both views with 403/401 tests asserting no writes; organisation derived from the Shop row, never the request; period echo checked before any write (409 path read-only, rollover test); organisation-row -> balance-row lock order inside one atomic; reason text only in `CreditTransaction.note`, absent from audit data and logs; availability check before the atomic; scoped throttles with a 429 test; list pagination fixed at 10. T-32-19 (replay) accepted as planned. Concurrent Postgres proofs remain with Plan 32-05. No new threat flags.

## Known Stubs

None.

## Next Phase Readiness

The response contract in the plan's interfaces block is implemented verbatim for Plan 32-04 (frontend) and Plan 32-05 (cross-check and Postgres concurrency tests). The `shop.credits.bonus_allocated` audit payload is now persisted history that Phase 33's Activity Log will render.

## Self-Check: PASSED

- Files exist: bonus.py, shop_credits.py, serializers.py, views.py, api_urls.py, test_bonus.py, test_views.py, exceptions.py changes
- Commits `71eec10`, `1e36fdd`, `a393b1e` are ancestors of HEAD (3 commits measured from `14bdd18`)
- All task acceptance greps match the plan's expectations
