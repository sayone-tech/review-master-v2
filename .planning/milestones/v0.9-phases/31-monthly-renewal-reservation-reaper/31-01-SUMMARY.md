---
phase: 31-monthly-renewal-reservation-reaper
plan: 01
subsystem: credits
tags: [celery-beat, django, credits, lapse, ledger, audit-log, postgres-partial-index]

requires:
  - phase: 29-credit-balances-ledger
    provides: ShopCreditBalance, append-only CreditTransaction, ensure_balance, periods helpers
  - phase: 30-metered-ai-reply-generation
    provides: reserve/commit/refund consumption service and the _settle_lost_race late-commit policy
provides:
  - ShopCreditBalance.lapsed_at marker + partial index credit_bal_unlapsed_idx (migration 0002)
  - Daily 00:05 UTC Beat seed credits_lapse_expired_balances (migration 0003)
  - lapse_balance / lapse_past_balances service and list_unlapsed_past_balance_ids selector
  - lapse_expired_credit_balances_task (default queue, no autoretry)
  - _settle_lost_race reads lapsed_at instead of LAPSED ledger rows
  - CREN-02 contract pinned by tests (new month = live allocation, bonus 0)
affects: [31-02 reaper (calls lapse_balance after refunding), 31-03 postgres concurrency tests, 32/33 credit UI]

actuals:
  tokens: 11000
  tasks: 3
  commits: 3
plan_head_before: 4f9bb0259878b853faa3a8b8032073146d5e74a4
plan_head_after: 1e1c5b90370209e604066cb047bff40ea11aec71

tech-stack:
  added: []
  patterns:
    - "pk-keyset sweep (pk > after_pk, chunked) so held/unlapsed rows cannot loop the sweep"
    - "per-balance transaction.atomic + select_for_update(skip_locked=True, of=self) re-checking every predicate under the lock"
    - "done-marker column (lapsed_at) rather than ledger-row existence as the idempotency flag"

key-files:
  created:
    - apps/credits/migrations/0002_shopcreditbalance_lapsed_at.py
    - apps/credits/migrations/0003_beat_credit_lapse.py
    - apps/credits/selectors/lapse.py
    - apps/credits/services/lapse.py
    - apps/credits/tasks.py
    - apps/credits/tests/test_lapse.py
    - apps/credits/tests/test_tasks.py
    - apps/credits/tests/test_renewal.py
  modified:
    - apps/credits/models.py
    - apps/credits/services/consumption.py
    - config/settings/base.py
    - apps/credits/tests/test_consumption.py
    - apps/credits/tests/test_models.py
    - apps/credits/tests/test_settings.py

key-decisions:
  - "lapsed_at is the only done-flag; zero-remaining balances are marked with no LAPSED row and no AuditLog row (D-02)"
  - "Partial index credit_bal_unlapsed_idx on (period_year, period_month) WHERE lapsed_at IS NULL, no column index (D-01)"
  - "Lapse task uses bare @shared_task with no autoretry: idempotent fleet sweep with per-balance error isolation"
  - "_settle_lost_race switched (not OR-ed) from the LAPSED-row lookup to the lapsed_at marker"
  - "lapse_balance query count pinned at 7 on SQLite (includes SAVEPOINT/RELEASE), identical for 1 and 6 ledger rows"

patterns-established:
  - "System sweeps take org/shop ids from the locked row, never from arguments"
  - "Past-period guard lives inside the locked query as well as the selector"

requirements-completed: [CREN-01, CREN-02]

duration: 10min
completed: 2026-11-11
status: complete
---

# Phase 31 Plan 01: Monthly Renewal and Lapse Summary

**Daily 00:05 UTC Celery Beat lapse sweep that writes one LAPSED ledger row plus a `shop.credits.lapsed` audit row per past-month balance with credits left, guarded by a `lapsed_at` marker, held-reservation skipping and pk-keyset paging; CREN-02 pinned by tests.**

## Performance

- **Duration:** about 10 min
- **Completed:** 2026-11-11T14:19Z
- **Tasks:** 3
- **Files modified:** 14 (8 created, 6 modified)

## Accomplishments

- Tracer: Beat seed -> registered default-queue task -> `lapse_past_balances` -> locked `lapse_balance` -> LAPSED row + AuditLog + `lapsed_at`, proven end to end through `lapse_expired_credit_balances_task.delay().get()`.
- Sweep safety proven by unit tests: zero remaining, held reservation (skipped, then lapses after commit), catch-up of 1/2/13-month-old balances, December to January, current/future guard, inactive shops, two-tenant integrity, keyset termination at chunk size 1, per-balance failure isolation (including the stray LAPSED IntegrityError), SoftTimeLimitExceeded re-raise.
- Query ceilings: selection is exactly 1 query for 2 or 5 balances; `lapse_balance` is 7 queries on SQLite for both 1 and 6 ledger rows.
- Phase 30's late commit now honours the marker, so a zero-remaining lapse (no LAPSED row) is still a free draft.
- CREN-02: no production change; five tests pin new-month-from-live-allocation with bonus 0, including the not-yet-lapsed and December/January cases.

## Task Commits

1. **Task 1 (tracer): daily lapse sweep via Beat with lapsed_at marker** - `724de41` (feat)
2. **Task 2: late commit honours lapsed_at; sweep edge-case tests** - `b49853d` (feat)
3. **Task 3: CREN-02 renewal tests** - `1e1c5b9` (test)

**Plan metadata:** committed separately (docs: complete plan).

## Files Created/Modified

- `apps/credits/models.py` - `lapsed_at` field, `credit_bal_unlapsed_idx` partial index, docstring note
- `apps/credits/migrations/0002_shopcreditbalance_lapsed_at.py` - schema (AddField + AddIndex)
- `apps/credits/migrations/0003_beat_credit_lapse.py` - reversible Beat seed
- `apps/credits/selectors/lapse.py` - keyset selection of unlapsed past balance ids (1 query)
- `apps/credits/services/lapse.py` - `LapseOutcome`, `LapseSummary`, `lapse_balance`, `lapse_past_balances`
- `apps/credits/tasks.py` - thin Celery wrapper
- `apps/credits/services/consumption.py` - `_settle_lost_race` reads `lapsed_at`
- `config/settings/base.py` - `REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE` and the default-queue route
- tests: `test_lapse.py`, `test_tasks.py`, `test_renewal.py` (new); `test_consumption.py`, `test_models.py`, `test_settings.py` (edited)

## Decisions Made

- Switched rather than OR-ed the late-commit lookup to the marker: the lapse service writes marker and LAPSED row in one atomic, and the marker also covers zero-remaining lapses.
- No autoretry on the task (documented in its docstring) because a blanket retry would re-run a whole idempotent sweep and hide real failures.
- 7-query pin for `lapse_balance` includes the SQLite savepoint statements; it is a fixed-per-balance ceiling, not a Postgres figure.

## Deviations from Plan

None - plan executed exactly as written. Two small notes: the `lapsed_at` model comment avoids the literal index name so the acceptance grep for `credit_bal_unlapsed_idx` in models.py prints exactly 1; `makemigrations` also added `organisations`/`shops` dependencies to migration 0002 automatically (generated, not hand-edited).

**Total deviations:** 0. **Impact on plan:** none.

## Issues Encountered

None. TDD note: the marker-only late-commit test was confirmed RED against the old `consumption.py` (the LAPSED-row lookup) before the change; the "marked lapsed with a LAPSED row" test also passes on old code by design, since both signals are present.

## Verification Results (real output)

- `.venv/bin/pytest apps/ -q -o addopts=""` -> `1472 passed, 14 skipped` (skips include the 7 `pg_concurrency` tests that need Postgres)
- `.venv/bin/pytest apps/credits apps/reviews/tests/test_views.py -o addopts=""` -> `268 passed, 7 skipped`
- `makemigrations --check --dry-run` -> `No changes detected`
- Migrate / migrate back to `credits 0001` / re-migrate one-liner -> `CREDITS_LAPSE_MIGRATIONS_REVERSIBLE` (SQLite in-memory; column and PeriodicTask both removed and re-created)
- `.venv/bin/mypy apps/credits` -> `Success: no issues found in 34 source files`; `ruff check` and `ruff format --check` on `apps/credits config` clean; pre-commit hooks passed on each commit
- Acceptance greps: `credit_bal_unlapsed_idx` models.py 1, migration 0002 1; `skip_locked=True` in lapse.py 1; route line 1; chunk-size setting present; `credits_lapse_expired_balances` in 0003: 3; migrations count 4; reviews-import invariant 0; `Type.LAPSED` in consumption.py 0; `lapsed_at__isnull=False` 1; `cas_status(` in lapse.py 0; `allocation.py` / `balances.py` untouched.

**Not run:** nothing against a real PostgreSQL (the overlapping-sweep proof is Plan 31-03); `make test` (Docker unavailable, local `.venv` used). Query counts are SQLite figures.

## Known Stubs

None.

## Threat Flags

None. All new surface (system Beat job, ledger and audit writes) is covered by T-31-01..T-31-08.

## Next Phase Readiness

Ready for 31-02: `lapse_balance` is the callable the reaper uses after refunding (D-08), and the `0004_beat_credit_reaper` migration should depend on `0003_beat_credit_lapse`. `credits/tasks.py` and the `CELERY_TASK_ROUTES` comment block are the places to add the reaper task and route.

## Self-Check: PASSED

All created files exist; commits `724de41`, `b49853d`, `1e1c5b9` are ancestors of HEAD; `git rev-list --count` from the plan base gives 3 (matches `actuals.commits`).

---
*Phase: 31-monthly-renewal-reservation-reaper*
*Completed: 2026-11-11*
