---
phase: 32-superadmin-credit-controls
plan: 01
subsystem: credits
tags: [django, drf, credits, organisations, audit-log, select-for-update, bulk-create]
status: complete

requires:
  - phase: 29-credits-ledger-foundation
    provides: ShopCreditBalance, CreditTransaction, ensure_balance, virtual-balance selectors
  - phase: 31-credit-lapse-and-renewal
    provides: lapse/reaper behaviour preserved unchanged
provides:
  - set-based materialise_org_balances / raise_zero_balances (D-20)
  - org_has_current_month_allocation (D-18) and org_current_month_allocation_expression (D-21)
  - atomic update_organisation(actor=...) with CRED-06 branch and organisation.credits.set audit
  - create_organisation(monthly_credit_allocation=0)
  - API fields monthly_credit_allocation / current_month_credit_allocation on organisation list/detail
  - OrganisationAdmin read-only monthly_credit_allocation (D-22)
affects: [32-02, 32-03, 32-04, 32-05, 33-credit-visibility]

actuals:
  tokens: 12200
  tasks: 3
  commits: 3
plan_head_before: 2250e5537c2ce6182529c4257187ef04d787c673
plan_head_after: eafd4fe06550a50cbec0c880060152c941510650

tech-stack:
  added: []
  patterns:
    - "Org-edit path materialises current-month balances with bulk_create(ignore_conflicts=True) + re-select, fixed query count, before the org field save"
    - "Old value read from the org row locked with select_for_update(of=('self',)), never from the passed instance"
    - "Organisation-queryset Subquery over ShopCreditBalance (related_name='+') for current-month allocation"

key-files:
  created:
    - apps/credits/tests/test_org_allocation.py
    - apps/organisations/tests/test_admin.py
  modified:
    - apps/credits/services/allocation.py
    - apps/credits/selectors/balances.py
    - apps/organisations/services/organisations.py
    - apps/organisations/selectors/organisations.py
    - apps/organisations/serializers.py
    - apps/organisations/views.py
    - apps/organisations/admin.py
    - apps/organisations/tests/test_views.py

key-decisions:
  - "organisation.credits.set uses entity_type 'organisation', entity_id str(org.pk); before_data {monthly_credit_allocation}; after_data {monthly_credit_allocation, effective, shops_touched, period_year, period_month}"
  - "create_organisation audits only when the initial value is > 0 (default 0 is not a change)"
  - "D-18 immediate only when old == 0 AND no current-month row has allocated_credits > 0; everything else materialises at the old value and reports next_month"
  - "D-15 'pending' is derived as current_month_credit_allocation != monthly_credit_allocation (read only)"

requirements-completed: [CRED-01, CRED-06, CSUP-02]

duration: ~30 min
completed: 2026-11-11
---

# Phase 32 Plan 01: Org allocation write path (CRED-01 / CRED-06) Summary

Superadmin PATCH/POST of an organisation's monthly credits per shop, with set-based current-month materialisation at the old value on mid-month changes, an atomic locked-row update, and one `organisation.credits.set` audit row per real change.

## Accomplishments

- **Tracer (end to end):** a Superadmin PATCH 100 -> 50 leaves every shop (active and inactive) at 100 this month, saves 50, writes INITIAL_ALLOCATION and `shop.credits.allocated` rows only for shops that lacked a row (the existing row with consumed 7 is untouched), writes one `organisation.credits.set` row with the acting Superadmin, and the list returns `monthly_credit_allocation` 50 and `current_month_credit_allocation` 100.
- **Set-based helpers (D-20):** `materialise_org_balances` and `raise_zero_balances` produce the same rows, ledger and audit shapes as looping `ensure_balance`, proven by an equivalence test, with constant query counts (5 vs 50 shops; 2 vs 10 zero rows).
- **CRED-06 timing matrix:** 0 -> N immediate (no rows created; bonus-created zero rows raised with one INITIAL and keeping their bonus), D-18 deferral after 100 -> 0 -> 50, N -> 0 keeps N this month, next-month rollover, idempotency, stale-instance safety, and full rollback when the audit write fails.
- **CRED-01 / CSUP-02 / D-22:** create field (0..10000, default 0, audited only when > 0), 400 on out-of-range/non-integer, 403 for Org Admin (own org) and Staff, 401/403 anonymous, editable when the org is DISABLED, Django admin shows the field read-only.
- **Query ceilings:** API list stays <= 7 queries and the selector <= 3 with the Subquery annotation, including data with current-month rows on two organisations.

## Task Commits

1. Task 1 (tracer): `6318da1` feat(32-01): materialise shop balances at the old value on mid-month allocation change
2. Task 2: `bc4cc2e` test(32-01): CRED-06 proof matrix for org-edit materialisation
3. Task 3: `eafd4fe` feat(32-01): organisation create accepts credit allocation; admin read-only; PATCH access tests

## Verification (real output)

- `.venv/bin/pytest apps/ -q -o addopts="" -p no:warnings`: **1521 passed, 18 skipped** (skips are the Postgres-only `pg_concurrency` tests and other pre-existing skips)
- `.venv/bin/pytest apps/credits apps/organisations -q --no-cov`: all passed, no failures (11 skipped pg_concurrency)
- `test_org_allocation.py`: 15 test functions (16 cases), all pass
- `.venv/bin/mypy apps/credits apps/organisations`: Success, no issues in 58 files
- `.venv/bin/ruff check` and `ruff format --check` on both apps: clean
- `makemigrations --check --dry-run` (test settings): "No changes detected"
- Pre-commit hooks (ruff, mypy, bandit, missing-migrations, gitleaks) passed on all three commits
- Source-scan invariants: `cas_status(` count in allocation.py is 0; no `apps.reviews` import in non-test credits code
- Not run: Postgres-backed `pg_concurrency` tests (no Postgres/docker per instructions; they belong to Plan 32-05), `tenant-security-auditor` / `orm-performance-auditor` subagents (not in this plan's tasks)

## Deviations from Plan

None to the plan's behaviour. Two ordering notes, no rule-triggering deviation:

- The `create_organisation(monthly_credit_allocation=...)` service change and its audit write landed in the Task 1 commit (they sit in the same file as `update_organisation`); the create serializer field, admin change and their tests landed in Task 3 as planned, so create never received an unexpected kwarg.
- Task 2 is tests-only: the Task 1 production code passed every behaviour on first run, so no GREEN fix commit was needed. The module-level imports in `organisations.py` created no import cycle (verified), so no function-level imports were used.

**Total deviations:** 0 auto-fixed. **Impact:** none.

## Threat Surface

T-32-01..T-32-08 mitigated as planned (Superadmin-only viewset with 403/401 tests; `_UPDATABLE_FIELDS` whitelist plus 0..10000 serializer bound; locked-row old value with stale-instance test; helpers run before the field save with a rollback test; admin read-only; audit row per real change; constant-query helpers; ids and integers only in audit and log lines). No new threat flags.

## Known Stubs

None.

## Next Phase Readiness

Ready for Plan 32-02 (frontend field and hint consuming `monthly_credit_allocation` / `current_month_credit_allocation`) and 32-03 (bonus service built on the same org-row -> balance-row lock order). The `organisation.credits.set` payload shape is now persisted history that Phase 33's Activity Log will render.

## Self-Check: PASSED

- Files exist: allocation.py, balances.py, organisations service/selector/serializers/views/admin, test_org_allocation.py, test_admin.py, test_views.py
- Commits `6318da1`, `bc4cc2e`, `eafd4fe` are ancestors of HEAD
- All task acceptance greps match the plan's expectations
