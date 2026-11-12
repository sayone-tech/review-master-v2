---
phase: 29-credits-ledger-foundation
plan: 02
subsystem: database
tags: [django, postgres, credits, ledger, append-only, cas, admin, pytest]

requires:
  - phase: 29-credits-ledger-foundation
    provides: "Plan 01 models (ShopCreditBalance, CreditTransaction), factories, pg_concurrency harness"
provides:
  - "AppendOnlyViolation / InvalidStatusTransition exceptions"
  - "CreditTransactionQuerySet: update/delete/bulk_update blocked, cas_status escape hatch"
  - "CreditTransaction.ALLOWED_STATUS_TRANSITIONS + guarded save()/delete()"
  - "ledger.transition_status: single conditional UPDATE status CAS (RESERVED -> COMMITTED/REFUNDED)"
  - "Read-only Django admin for both credit models"
  - "assert_ledger_reconciles test helper for Phase 30"
affects: [30-reserve-commit-refund, 31-lapse-reaper, 32-superadmin-allocation, 33-credits-ui]

actuals:
  tokens: 8400
  tasks: 2
  commits: 3
plan_head_before: 4b1f4fb2ee0120c9afb304935183c784190259da
plan_head_after: bc21cab192fcfe985414c3de017d60154c32b201

tech-stack:
  added: []
  patterns:
    - "Append-only model via QuerySet override (update/delete raise) with a single named CAS escape hatch"
    - "Instance save(update_fields=['status']) routed through the same CAS so stale instances fail closed"
    - "Read-only admin: has_add/change/delete_permission False, view pages kept"

key-files:
  created:
    - apps/credits/exceptions.py
    - apps/credits/managers.py
    - apps/credits/services/ledger.py
    - apps/credits/admin.py
    - apps/credits/tests/helpers.py
    - apps/credits/tests/test_append_only.py
    - apps/credits/tests/test_models.py
    - apps/credits/tests/test_admin.py
  modified:
    - apps/credits/models.py
    - apps/credits/tests/test_pg_concurrency.py

key-decisions:
  - "No migration: the custom manager is not serialized (use_in_migrations False); makemigrations --check stays clean"
  - "bulk_update is blocked transitively because it routes through QuerySet.update"
  - "Admin permission methods are duplicated per model (not a shared base) to match the plan's acceptance count and the ShopAuditLogAdmin precedent"

patterns-established:
  - "cas_status is the only sanctioned write path; a source-scan test pins its callers to managers.py, models.py and services/ledger.py"

requirements-completed: [CRED-02, CRED-03, CQA-01]

coverage:
  - id: D1
    description: "Ledger rows cannot be updated or deleted via QuerySet.update/delete, bulk_update, instance.delete or non-status save; create and bulk_create still insert"
    requirement: CRED-03
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_append_only.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "transition_status allows only RESERVED -> COMMITTED/REFUNDED, returns True then False on repeat, False for a missing row; status-only save and stale instances go through the same CAS"
    requirement: CRED-03
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_append_only.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "8 threads on real PostgreSQL settling one RESERVED row yield exactly one winner and the stored status equals the winner's target"
    requirement: CQA-01
    verification:
      - kind: integration
        ref: "apps/credits/tests/test_pg_concurrency.py#test_cas_transition_succeeds_once_when_n_threads_settle_same_reservation (throwaway PostgreSQL 14, 3 passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Balance and ledger DB invariants (unique period, nonneg, overspend, month range, partial uniques, delta sign, only-CONSUMPTION-reserved) reject bad writes, with named CHECK assertions; D-02 delete rules and D-04 meta proven"
    requirement: CRED-02
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_models.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both credit models are view-only in Django admin for a superuser (200 on list/view; 403 on add, change POST, delete) with a constant changelist query count"
    requirement: CRED-03
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_admin.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "assert_ledger_reconciles passes when consumed equals live CONSUMPTION sum and raises otherwise"
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_models.py#test_reconcile_passes_when_consumed_matches_live_consumption_rows"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-11-11
status: complete
---

# Phase 29 Plan 02: Append-only Ledger and Status CAS Summary

**CreditTransaction is append-only in the app layer (QuerySet update/delete/bulk_update and instance delete raise), with a single RESERVED -> COMMITTED/REFUNDED status CAS (`ledger.transition_status`) proven single-winner on real Postgres, plus read-only admin and full DB-invariant tests**

## Performance

- **Duration:** ~22 min
- **Completed:** 2026-11-11T11:54Z
- **Tasks:** 2 (Task 1 TDD, Task 2 auto)
- **Files modified:** 10 (795 insertions, 1 deletion)

## Accomplishments

- `CreditTransactionQuerySet` blocks `update`, `delete` and (transitively) `bulk_update` with `AppendOnlyViolation`; `create`/`bulk_create` still insert. `cas_status` calls the base `QuerySet.update` as the only escape hatch.
- `CreditTransaction.save()` allows inserts and `save(update_fields=["status"])` only; the latter validates `(RESERVED, target)` against `ALLOWED_STATUS_TRANSITIONS` and runs the CAS, raising `InvalidStatusTransition` for disallowed, already-settled or stale instances. `delete()` raises.
- `ledger.transition_status` is the thin named primitive: validates the pair, then one conditional UPDATE judged by rowcount. No reserve/commit/refund (Phase 30 scope).
- Source-scan test pins the `cas_status(` callers to exactly managers.py, models.py and services/ledger.py.
- Every CRED-02 / D-07 constraint has a failing-write test (named CHECK assertions; IntegrityError-only for uniques); D-02 delete rules (SET_NULL survival, PROTECT) and D-04 meta proven.
- Read-only admin for both models; changelist query count constant for 2 vs 10 rows.
- `assert_ledger_reconciles` test helper ready for Phase 30.

## Task Commits

1. **Task 1: append-only ledger + status CAS (TDD)**
   - RED: `66b5854` (test) - 16 of 19 tests failing on behavior assertions
   - GREEN: `e8a8b93` (feat)
2. **Task 2: DB invariants, reconciliation helper, read-only admin** - `bc21cab` (feat)

**Plan metadata:** committed separately (docs: complete plan).

### TDD Gate Compliance

- RED: `test(29-02)` commit `66b5854`. Evidence from the real pytest JUnit XML validated with `gsd_run check tdd-red-evidence`: `RED_EVIDENCE_OK`, reason `target_test_failed`, 19 tests, 16 failing, 3 passing (the pass-already tests are create/bulk_create and the 2 pre-existing behaviors of the stub). Semantic assessment: the first attempt failed at collection with `ModuleNotFoundError` for `apps.credits.exceptions`, which is INVALID_RED; I added `exceptions.py` and a `transition_status` stub returning False so the tests import and then fail on the planned assertions (e.g. QuerySet.update "DID NOT RAISE", the caller source-scan showing an empty set). Those scaffolding files are in the RED commit.
- GREEN: `e8a8b93` follows RED. REFACTOR: none.
- Task 1's concurrency test was authored in RED but is skipped on SQLite; it was proven in GREEN on Postgres.

## Decisions Made

- Admin permission methods are written out per model rather than shared via a base class, to match the plan's explicit acceptance count (6) and the existing `ShopAuditLogAdmin` style.
- Followed the plan and CONTEXT D-02, D-04..D-07 otherwise.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in test] bulk_update test needed its own savepoint**
- **Found during:** Task 1 GREEN
- **Issue:** Django's `bulk_update` opens `atomic(savepoint=False)`, so raising inside it marks the surrounding test transaction as needing rollback and the follow-up status read failed with `TransactionManagementError`.
- **Fix:** Wrapped the call in `pytest.raises(AppendOnlyViolation), transaction.atomic()`. The production behavior (exception propagates, caller's transaction rolls back) is the fail-closed outcome.
- **Files modified:** apps/credits/tests/test_append_only.py
- **Committed in:** e8a8b93

**2. [Rule 3 - Blocking] RED required scaffolding to be valid**
- See TDD Gate Compliance above: `exceptions.py` and a `transition_status` stub were added in the RED commit so the RED run was not an import failure.

**3. [Rule 3 - Blocking] Lint/type**
- `managers.py`: the TYPE_CHECKING import needs `# noqa: F401` (used only in a string forward reference); the two `# type: ignore[override]` comments the plan implied were unused under mypy strict and were removed.

**Total deviations:** 3 minor (1 test bug, 2 blocking tooling). **Impact:** none on scope or behavior.

## Verification Results (real output)

- `pytest apps/credits -q --no-cov -rs` on SQLite: all pass; 3 skipped (the pg_concurrency tests, "requires PostgreSQL").
- Full repo suite `pytest -q --no-cov`: all pass, no failures.
- **Postgres ran locally**: throwaway PostgreSQL 14 cluster (Homebrew `initdb`/`pg_ctl`, port 54329, `createdb reviewmaster` first), `REQUIRE_PG=1 pytest --ds=config.settings.test_pg -m pg_concurrency`: "3 passed" (vendor check, first-use race, CAS race), 0 skipped.
- `makemigrations --check --dry-run`: "No changes detected" (no migration in this plan).
- `mypy apps/credits`: no issues in 20 files; `ruff check` / `ruff format --check`: clean; pre-commit hooks ran on every commit (no `--no-verify`).
- Acceptance greps: exceptions 2 classes; `def cas_status` 1; `def transition_status` 1; no reserve/commit/refund defs; `has_*_permission` 6; `admin.register` 2; named CHECK assertions 5; ProtectedError 3.
- Not run: the GitHub Actions `backend-pg` job (needs a push; local is PostgreSQL 14 vs CI 16).

## Issues Encountered

None blocking.

## Known Stubs

None.

## Threat Flags

None. T-29-10, T-29-11, T-29-12, T-29-14 and T-29-15 mitigations implemented and tested; T-29-13 (raw SQL / `_raw_delete`) remains accepted per the plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03 (credit_cost, selectors) can build on the same models; Phase 30 can call `ledger.transition_status` and compose it with the guarded balance `F()` update, using `assert_ledger_reconciles` in tests.
- After pushing, confirm `CI / backend-pg` is green with all 3 pg tests passing.

## Self-Check: PASSED

- Files verified present: exceptions.py, managers.py, services/ledger.py, admin.py, tests/helpers.py, tests/test_append_only.py, tests/test_models.py, tests/test_admin.py (all under apps/credits)
- Commits verified in history: 66b5854, e8a8b93, bc21cab

---
*Phase: 29-credits-ledger-foundation*
*Completed: 2026-11-11*
