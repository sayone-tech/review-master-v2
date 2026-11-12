---
phase: 29-credits-ledger-foundation
plan: 04
subsystem: database
tags: [django, credits, ledger, append-only, gap-closure, pytest]

requires:
  - phase: 29-credits-ledger-foundation
    provides: "Plan 02 append-only guards (CreditTransactionQuerySet, guarded save/delete, cas_status)"
provides:
  - "CreditTransaction.save forces INSERT on the adding path (reused-pk rewrite closed, WR-01)"
  - "CreditTransactionQuerySet.bulk_create rejects update_conflicts=True (upsert rewrite closed, WR-02)"
  - "Regression tests for both bypasses plus a plain-bulk_create still-inserts test"
affects: [30-reserve-commit-refund, 31-lapse-reaper]

actuals:
  tokens: 2400
  tasks: 2
  commits: 4
plan_head_before: 54c9aa69a3e91fc37a2b8a30cc0121343accb7ab
plan_head_after: e8488178fa366673fcb92d2e1eef33f813be1711

tech-stack:
  added: []
  patterns:
    - "Force force_insert=True on the adding path of an append-only model's save()"
    - "Reject upsert kwargs (update_conflicts) in the append-only QuerySet.bulk_create override"

key-files:
  created: []
  modified:
    - apps/credits/models.py
    - apps/credits/managers.py
    - apps/credits/tests/test_append_only.py

key-decisions:
  - "bulk_create override only rejects update_conflicts; ignore_conflicts and plain inserts stay untouched so Phase 30/31 writes keep working"
  - "force_insert is set unconditionally on the adding path (overrides any caller value) since an adding ledger row must only ever INSERT"

requirements-completed: [CRED-03]

coverage:
  - id: D1
    description: "New CreditTransaction instance with an existing pk raises IntegrityError and leaves the stored row unchanged (WR-01)"
    requirement: CRED-03
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_append_only.py#test_save_raises_integrity_error_when_new_instance_reuses_existing_pk"
        status: pass
    human_judgment: false
  - id: D2
    description: "bulk_create(update_conflicts=True) raises AppendOnlyViolation before SQL and plain bulk_create still inserts (WR-02)"
    requirement: CRED-03
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_append_only.py#test_bulk_create_raises_when_update_conflicts_requested"
        status: pass
      - kind: unit
        ref: "apps/credits/tests/test_append_only.py#test_bulk_create_inserts_rows_when_update_conflicts_not_requested"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-11-11
status: complete
---

# Phase 29 Plan 04: Ledger Append-Only Gap Closure Summary

**Closed the two ORM bypasses of the append-only credit ledger: save() now force-inserts new instances (reused-pk rewrite) and QuerySet.bulk_create rejects update_conflicts upserts.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-11-11T13:07Z
- **Tasks:** 2 (each RED then GREEN)
- **Files modified:** 3

## Accomplishments
- WR-01: `CreditTransaction.save()` sets `force_insert=True` on the adding path, so an in-memory instance carrying an existing pk raises `IntegrityError` instead of Django's UPDATE-then-INSERT silently rewriting the committed row.
- WR-02: `CreditTransactionQuerySet.bulk_create` raises `AppendOnlyViolation` when `update_conflicts` is truthy, before any SQL runs; plain `bulk_create` (and `ignore_conflicts`) is unaffected.
- Three regression tests added; the existing cas_status source-scan test and pg_concurrency tests are unchanged and still pass (pg tests skip on SQLite as designed).

## TDD Gate Compliance

- **RED (Task 1):** `test_save_raises_integrity_error_when_new_instance_reuses_existing_pk` failed with `DID NOT RAISE IntegrityError` on the planned assertion (row silently rewritten). Semantic assessment: target test executed and failed for the intended reason.
- **RED (Task 2):** `test_bulk_create_raises_when_update_conflicts_requested` failed with `DID NOT RAISE AppendOnlyViolation` (upsert executed); the companion plain-insert test passed, as intended.
- **GREEN:** both fixes make the target tests pass; full credits suite green.
- No REFACTOR commits needed.

## Task Commits

1. **Task 1 RED** - `3dd1968` (test)
2. **Task 1 GREEN** - `d866fe0` (fix) - force insert on adding path
3. **Task 2 RED** - `8a1779a` (test)
4. **Task 2 GREEN** - `e848817` (fix) - reject update_conflicts

## Files Created/Modified
- `apps/credits/models.py` - `save()` adding path forces `force_insert=True`
- `apps/credits/managers.py` - `bulk_create` override rejecting `update_conflicts`; docstring updated
- `apps/credits/tests/test_append_only.py` - three regression tests

## Decisions Made
- Only `update_conflicts` is rejected in `bulk_create`; `ignore_conflicts` and plain inserts remain allowed for Phase 30 reservations and Phase 31 bulk LAPSED writes.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Out-of-scope findings (WR-03, IN-01..IN-06) were intentionally left open per the plan.

## Verification Results
- `.venv/bin/pytest apps/credits -q --no-cov`: 126 passed, 3 skipped (pg_concurrency, requires PostgreSQL)
- `.venv/bin/pytest apps/ -q`: 1343 passed, 5 skipped
- `.venv/bin/mypy apps/credits`: Success, no issues found in 26 source files
- `.venv/bin/ruff check apps/credits`: All checks passed; `ruff format --check`: 26 files already formatted
- Pre-commit hooks (ruff, mypy, bandit, gitleaks, missing-migrations) passed on every commit, no `--no-verify`

## Threat Model
- T-29-22 (save reused-pk rewrite): mitigated, regression test asserts IntegrityError and unchanged row.
- T-29-23 (bulk_create upsert): mitigated, regression test asserts AppendOnlyViolation and unchanged row.

## Known Stubs
None.

## Next Phase Readiness
Ledger guard is complete for D-05; Phase 29 re-verification can pass the two previously failed must-haves.

## Self-Check: PASSED

- FOUND: apps/credits/models.py, apps/credits/managers.py, apps/credits/tests/test_append_only.py
- FOUND commits: 3dd1968, d866fe0, 8a1779a, e848817

---
*Phase: 29-credits-ledger-foundation*
*Completed: 2026-11-11*
