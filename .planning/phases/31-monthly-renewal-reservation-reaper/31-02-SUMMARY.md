---
phase: 31-monthly-renewal-reservation-reaper
plan: 02
subsystem: credits
tags: [celery-beat, django, credits, reaper, ledger, audit-log, sentry, runbook]

requires:
  - phase: 30-metered-ai-reply-generation
    provides: refund_reservation CAS primitive and the single late-commit policy
  - phase: 31-monthly-renewal-reservation-reaper (plan 01)
    provides: lapse_balance, lapsed_at marker, credits Beat/task scaffolding
provides:
  - Every-10-minute Beat seed credits_reap_stale_reservations (migration 0004, reversible)
  - list_stale_reservations selector (1 query, credit_tx_reserved_idx predicate and order)
  - reap_stale_reservations service (CAS-only per-row refund, D-08 re-lapse, ids-only observability)
  - reap_stale_reservations_task (default queue, no autoretry) and REVIEWBEE_CREDIT_REAPER_BATCH_SIZE
  - age_reservation test helper
  - CLAUDE.md section 3 / 12.5 and the credits runbook cover both Phase 31 schedules
affects: [31-03 postgres concurrency tests, 32/33 credit UI]

actuals:
  tokens: 8500
  tasks: 3
  commits: 3
plan_head_before: e21e7268b4f560b1a6e19fb482eab05bf7d0bb69
plan_head_after: 2b9813fea4a800c80d694fcff8b5dc5ec214c95c

tech-stack:
  added: []
  patterns:
    - "CAS-only reaper: no outer transaction, no skip_locked pre-select; refund_reservation owns the per-row atomic and CAS"
    - "Per-row failure isolation with ids-only Sentry error; SoftTimeLimitExceeded re-raised"
    - "Re-lapse of touched past-period balances delegated to lapse_balance, which re-checks RESERVED rows under its lock"

key-files:
  created:
    - apps/credits/selectors/reservations.py
    - apps/credits/services/reaper.py
    - apps/credits/migrations/0004_beat_credit_reaper.py
    - apps/credits/tests/test_reaper.py
  modified:
    - apps/credits/tasks.py
    - config/settings/base.py
    - apps/credits/tests/helpers.py
    - apps/credits/tests/test_tasks.py
    - apps/credits/tests/test_settings.py
    - CLAUDE.md
    - docs/sre/v0.9-credits-rollout.md

key-decisions:
  - "Reaper is CAS-only (no skip_locked pre-select, no outer atomic): a loser of the race blocks on the winner's row lock and matches 0 rows"
  - "Bare @shared_task with no autoretry: idempotent, per-row isolated, reruns in 10 minutes"
  - "Beat seed is its own migration 0004 so no PeriodicTask ever points at an unregistered task; reverse never deletes the shared 10-minute IntervalSchedule"
  - "A refund that cannot apply (RuntimeError) is a Sentry error with tx_id and balance_id only; the row stays RESERVED and the balance stays unlapsed"

patterns-established:
  - "age_reservation uses models.QuerySet.update to backdate append-only ledger rows in tests"

requirements-completed: [CREN-03, CREN-01]

duration: about 12 min
completed: 2026-11-11
status: complete
---

# Phase 31 Plan 02: Reservation Reaper Summary

**Celery Beat every-10-minutes reaper that refunds RESERVED credit rows older than the 5-minute TTL through Phase 30's `refund_reservation` CAS (reason `reaped_stale`), then lapses the past-month balances it freed; ids-only logs and Sentry, bounded oldest-first batches, and operator docs for both Phase 31 schedules.**

## Performance

- **Duration:** about 12 min (start about 14:13Z, end 14:26Z)
- **Tasks:** 3 (1 tracer, 1 TDD-style test task, 1 docs task)
- **Files:** 11 (4 created, 7 modified)

## Accomplishments

- Tracer: migration 0004 seeds `credits_reap_stale_reservations` (interval 10 minutes, default queue, enabled, no crontab) pointing at a registered default-routed task. `reap_stale_reservations_task.delay().get()` refunds the 6-minute-old reservation, leaves the 4-minute-old one RESERVED, writes one `shop.credits.refunded` audit row (reason `reaped_stale`, actor NULL), one WARNING log, one Sentry warning `credits.reaper.reaped count=1`, and returns `{reaped: 1, skipped: 0, errored: 0, lapsed_after: 0}`.
- Edge cases pinned (14 reaper tests): TTL boundary, second run writes nothing, committed and refunded rows never selected, lost CAS counts as skipped, batch cap of 2 reaps oldest first and the newest on the next run, D-08 re-lapse (-12 LAPSED row, `consumed` 0, `lapsed_at` set) with current-month balances untouched, a past balance still holding a fresh RESERVED row stays unlapsed, D-09 refund failure (errored 1, row stays RESERVED, earlier refund kept, ids-only Sentry error), unexpected-exception isolation, `SoftTimeLimitExceeded` re-raised, no Sentry message when idle, month straddle (sweep skips held, reaper refunds and lapses, late commit is a free draft, one LAPSED row, ledger reconciles).
- No review text anywhere: the SECRET sentinel never appears in caplog, Sentry call arguments or any AuditLog `after_data`.
- Selector: exactly 1 query for 2 and for 5 stale rows.
- Docs: CLAUDE.md section 3 layout and section 12.5 Beat table (now 6 rows); runbook section "Monthly lapse and reservation reaper (Phase 31)" with schedules, settings, Beat restart, manual runs, `refund_failed` poison-row behaviour, up-to-24h held-balance lapse delay, and the 00:30 UTC alert handed to the deployment owner; stale "until Phase 31" wording removed.

## Task Commits

1. **Task 1 (tracer): reservation reaper via Beat** - `f780ca9` (feat)
2. **Task 2: reaper edge-case tests** - `ef54ba6` (test)
3. **Task 3: CLAUDE.md and runbook** - `2b9813f` (docs)

**Plan metadata:** committed separately (docs: complete plan).

## Decisions Made

See key-decisions. The CAS-only choice supersedes the ROADMAP note mentioning skip_locked (CONTEXT D-10 left it to the planner) and is recorded in the `reaper.py` module docstring.

## Deviations from Plan

None - plan executed exactly as written.

Notes, not deviations:
- Task 2 is marked `tdd="true"`, but the reaper was already implemented by the Task 1 tracer, so the Task 2 tests passed on first run (no RED phase, and no production fix was needed). To show the tests are not vacuous I mutated the service three ways and confirmed each was caught, then reverted with `git checkout`: dropping `touched.add` failed the D-08 re-lapse and straddle tests; dropping the `refund_failed` Sentry call failed the D-09 test; removing the `SoftTimeLimitExceeded` re-raise failed the re-raise test. (A first attempt with BSD `sed` did not apply and was discarded; the real mutations used Python.)
- One ruff import-order fix in `test_tasks.py` was applied before the Task 1 commit.

**Total deviations:** 0.

## Issues Encountered

None.

## Verification Results (real output)

- `.venv/bin/pytest apps/ -q -o addopts=""` -> `1491 passed, 14 skipped` (skips include the `pg_concurrency` tests that need Postgres)
- `.venv/bin/pytest apps/credits apps/reviews/tests/test_views.py -q --no-cov -o addopts=""` -> `292 passed, 7 skipped`
- `.venv/bin/pytest apps/credits/tests/test_reaper.py apps/credits/tests/test_settings.py` -> `29 passed`; tracer run (`test_reaper.py` + `test_tasks.py`) -> `7 passed`
- `makemigrations --check --dry-run` -> `No changes detected`
- Migrate / migrate `credits 0003` / re-migrate one-liner -> `CREDITS_REAPER_MIGRATION_REVERSIBLE` (`recover_stuck_syncs` kept its shared interval)
- `.venv/bin/mypy apps/credits` -> `Success: no issues found in 37 source files`; `ruff check` and `ruff format --check` clean; pre-commit hooks passed on all three commits
- Acceptance greps: `reason="reaped_stale"` 1; `transaction.atomic` in reaper.py 0; `select_for_update` 0 in reaper and selector; route line 1; batch setting 2 mentions in base.py; `credits_reap_stale_reservations` in 0004: 2; `def age_reservation` 1; migrations count 5; reviews-import invariant 0; `cas_status(` in reaper.py 0; `def test_` in test_reaper.py 14; `refund_failed` in tests 1; no diff to `consumption.py` / `lapse.py`.
- Docs: CLAUDE.md diff is 11 additions, 2 deletions; the four required CLAUDE.md greps each print 1; the four runbook greps each print 2; `DOCS_CLEAN` printed; the Phase 31 heading is present.

**Not run:** nothing against a real PostgreSQL (the overlapping-reapers and reaper-vs-late-commit proofs are Plan 31-03); `make test` (Docker unavailable, local `.venv` used); the manual "Beat picks up seeded schedules" and "00:30 UTC alert" checks are documented, not executed (they need a deployed environment). Query counts are SQLite figures.

## Known Stubs

None.

## Threat Flags

None. All new surface (system Beat job, refund and lapse writes, Sentry messages) is covered by T-31-10..T-31-16.

## Next Phase Readiness

Ready for 31-03 (Postgres concurrency proofs): the reaper's race with `commit_reservation` and with a second reaper relies on `refund_reservation`'s CAS, which is exactly what those tests should exercise on real PostgreSQL.

## Self-Check: PASSED

All created files exist on disk; commits `f780ca9`, `ef54ba6`, `2b9813f` are ancestors of HEAD; `git rev-list --count` from the plan base gives 3 (matches `actuals.commits`).

---
*Phase: 31-monthly-renewal-reservation-reaper*
*Completed: 2026-11-11*
