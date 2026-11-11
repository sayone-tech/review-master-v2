---
phase: 31-monthly-renewal-reservation-reaper
plan: 03
subsystem: credits
tags: [postgres, concurrency, pg_concurrency, reaper, lapse, ledger, phase-gate]

requires:
  - phase: 31-monthly-renewal-reservation-reaper (plans 01, 02)
    provides: lapse_balance / lapse_past_balances, reap_stale_reservations, age_reservation helper
  - phase: 30-metered-ai-reply-generation
    provides: refund_reservation CAS and the single late-commit policy
provides:
  - Four pg_concurrency tests proving the reaper and lapse sweep are race-safe on real PostgreSQL
  - One cross-tenant reaper audit-attribution unit test (tenant-security review finding)
  - Phase 31 gate results and inline auditor dispositions
  - 31-VALIDATION.md refreshed and signed off locally (nyquist_compliant true)
affects: [32 superadmin credit controls, 33 credit UI, /gsd-verify-work 31]

actuals:
  tokens: 5400
  tasks: 3
  commits: 3
plan_head_before: 69696fec3f8d2c163093b55bc3bf76c94ff4a00a
plan_head_after: 3c0c8a36e7238d3cd6e4613cfc4a5320c4d8738e

tech-stack:
  added: []
  patterns:
    - "Barrier-gated thread races with a per-round committer delay (odd rounds 3 ms, even rounds none) so both race outcomes occur in every run while either winner is accepted"
    - "Past-period straddle test: commit, reaper and sweep race on one balance, then one final sweep; outcome-conditional assertions"

key-files:
  created: []
  modified:
    - apps/credits/tests/test_pg_concurrency.py
    - apps/credits/tests/test_reaper.py
    - .planning/phases/31-monthly-renewal-reservation-reaper/31-VALIDATION.md

key-decisions:
  - "Race tests accept either winner but force both orderings per run via a small committer delay on odd rounds; an undelayed race alone gave 10/0 or 1/9 skewed splits and left one branch unproven"
  - "No production code changed: every race passed against the Plan 31-01/31-02 services"

requirements-completed: [CREN-03, CREN-01]

duration: 8 min
completed: 2026-11-11
status: complete
---

# Phase 31 Plan 03: Postgres Concurrency Proofs and Phase Gate Summary

**Four real-PostgreSQL race tests show the reaper never double-refunds or refunds a committed reservation, overlapping sweeps write exactly one LAPSED row per balance, and a month-straddling reservation settles before its balance lapses; all local Phase 31 gates are green.**

## Performance

- **Duration:** 8 min (Plans 31-01/02 not included)
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files:** 3 modified, 0 created

## Accomplishments

- Tracer (CREN-03, CQA-01): `test_reaper_and_late_commit_settle_each_reservation_once_when_racing`. The real `reap_stale_reservations` races `commit_reservation` behind a `Barrier(2)` over 10 sequential rounds. Observed split with the final delay scheme: **5 committed / 5 refunded in each of three runs**. Committed rounds: zero `shop.credits.refunded` rows, reaper reaped 0. Refunded rounds: one refund row with reason `reaped_stale`, reaper reaped 1, commit outcome `rededucted`, one COMMITTED `late_commit` row. Afterwards every review has exactly one COMMITTED CONSUMPTION row, `consumed_credits == 10`, ledger reconciles, no reaper errors.
- Overlapping reapers (D-10): 4 threads over 12 stale reservations on 2 shops: reaped sums to exactly 12, errored 0, every row REFUNDED with exactly one refund audit row, both balances at 0 consumed, ledgers reconcile.
- Overlapping sweeps (D-06, D-07): 6 threads over 5 balances with credits left, 1 fully used, 1 held, plus current-month balances: one LAPSED row and one `shop.credits.lapsed` row per credited balance with the exact delta, fully used marked with no rows, held stays unlapsed, current-month untouched; lapsed sums to 5, lapsed_zero to 1, errored 0.
- Past-period straddle (SC4, D-07, D-08): 6 rounds of commit + reaper + sweep on a previous-month balance (allocated 10, consumed 3, one stale RESERVED -3), then a final sweep. Observed splits over the final runs of this test: committed/free_draft of 4/2, 3/3, 4/2 (earlier runs: 5/1, 6/0, 3/3, 2/4, 5/1). Every round: exactly one LAPSED row and one lapsed audit row, `lapsed_at` set, ledger reconciles, no deadlock, no `late_commit` row. A past-month late commit is always `free_draft` (never `rededucted`), as `_settle_lost_race` specifies.
- Mutation check (non-vacuity): removing the `lapsed_at` guard and `skip_locked` from `lapse_balance` made the overlapping-sweep test fail on Postgres (the `credit_tx_one_lapse_per_balance` unique constraint also fired, a database backstop). Reverted with `git checkout`.

## Task Commits

1. **Task 1 (tracer): reaper vs late commit on Postgres** - `cfdcbce` (test)
2. **Task 2: overlapping reapers, sweeps and straddle** - `5c93048` (test)
3. **Task 3: phase gate, cross-tenant reaper test, VALIDATION sign-off** - `3c0c8a3` (test)

**Plan metadata:** committed separately (docs: complete plan).

## Phase Gate Reviews (inline)

The Agent tool was not available to this executor, so each auditor's checklist was walked inline over the real files and the findings recorded here.

### orm-performance-auditor

- **Index decision:** `credit_bal_unlapsed_idx` partial index on `(period_year, period_month) WHERE lapsed_at IS NULL`, no column index on `lapsed_at`. Accepted: the unlapsed set is one row per active shop plus stragglers while the table grows by shops x months; the selector predicate is exactly that partial set. Matches `credit_tx_reserved_idx`.
- **Reaper predicate/order (A1):** `status = 'RESERVED' AND transaction_type = 'CONSUMPTION' AND created_at < cutoff ORDER BY created_at, pk`. Django's psycopg3 backend uses client-side binding by default (no `server_side_binding` in settings), so the status literal is inlined and the partial index predicate applies; the pk tiebreak is a trivial sort of the small partial set. Accepted. Not measured with EXPLAIN (tables are tiny on the throwaway cluster and the plan would be a seq scan regardless).
- **Lock scope:** `select_for_update(skip_locked=True, of=("self",))` on a single table with `.values()`; `of` is redundant but harmless. Accepted.
- **Balance marker update:** sets `updated_at` explicitly (QuerySet.update bypasses auto_now). Accepted.
- **Query ceilings:** selectors are single-query (1 query for 2 and for 5 rows, tested); `lapse_balance` is a fixed 7 queries on SQLite for 1 and 6 ledger rows; the reaper does a constant number of queries per row (about 5) bounded by `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE` (500). That is a bounded write loop, not a read N+1. Accepted.
- **Migrations 0002-0004:** AddField nullable without default (metadata-only on PostgreSQL), AddIndex non-concurrent on a small table (brief write lock, accepted), schema migration separate from the two data migrations, all reversible (`PHASE31_MIGRATIONS_REVERSIBLE` printed; 0004 reverse never deletes the shared 10-minute IntervalSchedule). Accepted, no blockers.
- **Lock-order analysis:** refund locks the tx row then updates the balance; lapse locks the balance and only reads tx rows, and only proceeds when no RESERVED row exists. No cycle; confirmed by the three-way race running without deadlock in every round.

### code-reviewer

- Tasks are thin wrappers with lazy imports and a recorded no-autoretry rationale (section 12.3 deviation documented in both docstrings). Accepted.
- Services/selectors split respected; no business logic in tasks; settings read at call time; no outer `transaction.atomic` in the reaper; `SoftTimeLimitExceeded` re-raised in both loops and ordered before `except Exception`. Accepted.
- Logs and Sentry carry ids and ints only; `logger.exception` on unexpected errors can only echo database error text (ids). Accepted.
- mypy strict clean on all 342 files, ruff clean.
- Observation (accepted): a poison RESERVED row (refund `RuntimeError`) re-raises a Sentry error every 10 minutes by design; documented in the runbook so operators expect it.
- No blockers.

### tenant-security-auditor

- Organisation and shop ids on every LAPSED and `shop.credits.lapsed` row come from the locked balance's `.values()`; refund audit rows come from `_read_tx` on the ledger row; neither job takes ids from arguments. Tasks take no arguments and are Beat-only. Accepted.
- Neither job reads review text (selectors return ids and `credits_delta` only); tests assert a SECRET sentinel never appears in logs, Sentry or AuditLog. Accepted.
- No new endpoint, serializer, permission or Channels surface; the selectors and services are imported only by the credits tasks and each other. Accepted.
- **Finding (fixed):** reaper tests only used one organisation, so cross-tenant attribution of the refund audit rows was unproven. Added `test_reaper_attributes_refund_audit_rows_to_each_reservations_own_organisation` (two organisations, each refund row carries its own organisation id and balance). Lapse already had a two-tenant integrity test from Plan 31-01.
- No blockers remain.

## Decisions Made

See key-decisions. No production code changed.

## Deviations from Plan

**1. [Rule 2 - Missing critical test] Cross-tenant reaper attribution test** - Found during: Task 3 (tenant-security-auditor walk). Issue: tenant isolation of the reaper's audit rows was unproven. Fix: one unit test in `apps/credits/tests/test_reaper.py`. Commit `3c0c8a3`.

**2. [Test design] Committer delay in the tracer** - Found during: Task 1. The plan's undelayed barrier race produced a degenerate 10 committed / 0 refunded split on Postgres, so the reaper-wins branch (the point of the test) was never exercised. Odd rounds now delay the committer 3 ms; assertions still accept either winner. Same commit `cfdcbce`.

Notes, not deviations: the three race tests of Task 2 were written together with the tracer and split into the Task 1 and Task 2 commits afterwards; the plan's Task 1 acceptance of "13 passed" was met on the split Task 1 file (13 passed, 0 skipped).

**Total deviations:** 2 (one added test, one test-design adjustment). **Impact:** none on production code.

## Issues Encountered

None. One shell hiccup: a BSD `sed -i` call failed and short-circuited an `export`, so one batch of pytest invocations ran without the database URL and errored on connection; that was not a test failure and was re-run correctly.

## Verification Results (real output)

- **pg_concurrency on throwaway PostgreSQL 14.20** (local Homebrew, not CI's 16; temp cluster under the scratchpad, port 54339, `REQUIRE_PG=1 --ds=config.settings.test_pg -m pg_concurrency`): Task 1 state **13 passed, 0 skipped**; final state **16 passed, 0 skipped**, three consecutive runs each (`1493 deselected`). The plan's "12 existing" tests are 7 in `apps/credits/tests/test_pg_concurrency.py` and 5 in `apps/reviews/tests/test_pg_reply_concurrency.py`.
- SQLite: `apps/credits/tests/test_pg_concurrency.py` -> 11 skipped, none failed or errored.
- Full suite `.venv/bin/pytest apps/ -q -o addopts=""` -> **1492 passed, 18 skipped** (the 18 are all Postgres-only tests).
- `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` -> required coverage met, **89.57%** total; `credits/selectors/lapse.py` 100%, `selectors/reservations.py` 100%, `services/lapse.py` 99%, `services/reaper.py` 90%.
- `mypy .` -> no issues in 342 files; `ruff check .` and `ruff format --check .` clean.
- `makemigrations --check --dry-run` -> No changes detected.
- `check --deploy` (test settings, as the plan's verify specifies) -> exit 0 with 21 warnings (security W009/W012/W016 are test-settings artefacts; drf_spectacular W002 are pre-existing serializer-guess warnings in other apps). Not run against production settings.
- Reversibility one-liner -> `PHASE31_MIGRATIONS_REVERSIBLE`.
- Acceptance greps: migrations count 5; reviews-import invariant 0; `pg_concurrency` marker count 11; `lapse_past_balances` in the PG file 4; `assert_ledger_reconciles` 8.
- Postgres stopped with `pg_ctl -m fast stop`, data directory deleted, `pgrep` shows no postgres processes; no background commands were started.

**Not run:** CI `backend-pg` on PostgreSQL 16 (needs a push); Beat pickup of both schedules after a deploy; the 00:30 UTC lapse alert (deployment owner handoff, T-31-20); the optional `feature-impact` and `security-checklist` skills; EXPLAIN on the reaper predicate.

## Known Stubs

None.

## Threat Flags

None. T-31-17 and T-31-18 are mitigated by the four Postgres races and the bounded-join `_run_threads` helper; T-31-19 by the recorded auditor dispositions; T-31-20 is transferred to the deployment owner per the runbook.

## Next Phase Readiness

Phase 31 plans are complete. For `/gsd-verify-work 31`: confirm CI `backend-pg` ran all 16 `pg_concurrency` tests with none skipped, confirm Beat shows `credits_lapse_expired_balances` and `credits_reap_stale_reservations` after deploy and restart, and confirm the deployment owner has the 00:30 UTC lapse alert.

## Self-Check: PASSED

Modified files exist; commits `cfdcbce`, `5c93048`, `3c0c8a3` are ancestors of HEAD; `git rev-list --count` from the plan base gives 3 (matches `actuals.commits`).

---
*Phase: 31-monthly-renewal-reservation-reaper*
*Completed: 2026-11-11*
