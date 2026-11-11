---
phase: 29-credits-ledger-foundation
plan: 01
subsystem: database
tags: [django, postgres, credits, ledger, constraints, pytest, github-actions]

requires:
  - phase: 28
    provides: none (leaf app; builds on Organisation, Shop, AuditLog, AiUsageLog, Review models)
provides:
  - Organisation.monthly_credit_allocation (own migration 0003, CHECK 0..10000)
  - apps.credits app with ShopCreditBalance and CreditTransaction full schema + DB constraints (credits/0001)
  - services.periods (Period, utc_now, current_period, next_period_start)
  - services.allocation.ensure_balance (lazy, race-safe first-use creation)
  - REVIEWBEE_CREDIT_TIERS / RESERVATION_TTL_MINUTES / SUPPORT_EMAIL settings
  - Postgres CI harness (pg_concurrency marker, REQUIRE_PG guard, test_pg settings, backend-pg job, make test-pg)
  - ShopCreditBalanceFactory / CreditTransactionFactory
affects: [30-reserve-commit-refund, 31-lapse-reaper, 32-superadmin-allocation, 33-credits-ui]

actuals:
  tokens: 10100
  tasks: 3
  commits: 5
plan_head_before: 9be22e689e041639f243dd9e56d82a292650effc
plan_head_after: 078cbfbf44d126e08a9181abd234ed11c74fad25

tech-stack:
  added: []
  patterns:
    - "get_or_create inside transaction.atomic as the race-safe lazy-creation primitive; the DB unique index picks the winner"
    - "pg_concurrency marker + root conftest auto-skip off PostgreSQL + REQUIRE_PG exit-3 guard against vacuous green"
    - "Credits app references other apps only via string FKs (leaf bounded context)"

key-files:
  created:
    - apps/credits/models.py
    - apps/credits/migrations/0001_initial.py
    - apps/credits/services/periods.py
    - apps/credits/services/allocation.py
    - apps/credits/tests/factories.py
    - apps/credits/tests/conftest.py
    - apps/credits/tests/test_allocation.py
    - apps/credits/tests/test_periods.py
    - apps/credits/tests/test_pg_concurrency.py
    - apps/organisations/migrations/0003_organisation_monthly_credit_allocation.py
    - config/settings/test_pg.py
  modified:
    - apps/organisations/models.py
    - config/settings/base.py
    - config/settings/test.py
    - conftest.py
    - pyproject.toml
    - .github/workflows/ci.yml
    - Makefile

key-decisions:
  - "Organisation.monthly_credit_allocation is IntegerField (not PositiveIntegerField) to avoid the Coalesce mixed-type FieldError in later selectors"
  - "FK delete rules per D-02: PROTECT on balance.shop, tx.shop_credit_balance and denormalised shop/organisation; SET_NULL on review, actor, ai_usage_log"
  - "shop/organisation FKs on both models use db_index=False because composite/unique indexes already lead with them"
  - "ensure_balance takes no organisation parameter; it is derived from the Shop row (tenant safety)"

patterns-established:
  - "Zero allocation writes the balance row only: no INITIAL ledger row, no AuditLog row"
  - "System events (lazy allocation) use actor=None in both ledger and AuditLog; after_data limited to period_year, period_month, allocated_credits"

requirements-completed: [CRED-02, CQA-01]

coverage:
  - id: D1
    description: "First ensure_balance for a shop/UTC month creates one balance seeded from the org allocation, plus one INITIAL_ALLOCATION row and one system AuditLog row when allocation > 0; only the balance when 0"
    requirement: CRED-02
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_allocation.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "UTC period seam: Nov 30 23:59:59 / Dec 1 00:00:00 boundaries, IST conversion, naive rejection, December rollover in next_period_start"
    requirement: CRED-02
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_periods.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "8 concurrent first uses on real PostgreSQL yield one balance, one INITIAL row, one AuditLog row, exactly one created=True and no errors"
    requirement: CQA-01
    verification:
      - kind: integration
        ref: "apps/credits/tests/test_pg_concurrency.py#test_first_use_creates_one_balance_and_one_initial_when_n_threads_race (throwaway PostgreSQL 14, 2 passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "backend-pg GitHub Actions job (postgres:16) is green with at least one test run and none skipped"
    requirement: CQA-01
    verification: []
    human_judgment: true
    rationale: "Can only be confirmed after the branch is pushed and CI runs; locally verified on PostgreSQL 14 only"
  - id: D5
    description: "DB constraints (unique, non-negative, overspend, month range, partial uniques, delta sign, only-CONSUMPTION-reserved) exist in the migration"
    requirement: CRED-02
    verification:
      - kind: other
        ref: "grep of credits/0001_initial.py for all 9 constraint/index names; migrate/zero/migrate round-trip"
        status: pass
    human_judgment: true
    rationale: "Constraint enforcement tests (negative cases per engine) are scoped to Plan 02; this plan proves they are declared and migrate reversibly"

duration: 9min
completed: 2026-11-11
status: complete
---

# Phase 29 Plan 01: Credits Ledger Foundation (tracer slice) Summary

**Lazy per-shop monthly credit balance (`ensure_balance`) with full constraint-backed ledger schema, UTC period seam, and a `backend-pg` CI job that proves the first-use race on real PostgreSQL**

## Performance

- **Duration:** ~9 min
- **Completed:** 2026-11-11T11:46Z
- **Tasks:** 3 (tracer, TDD auto, auto)
- **Files modified:** 23 (820 insertions, 1 deletion)

## Accomplishments

- `Organisation.monthly_credit_allocation` shipped in its own migration (0003) with DB CHECK 0..10000; no serializer, service or admin changes (no API exposure until Phase 32).
- `apps/credits` with `ShopCreditBalance` and `CreditTransaction` full schema in one migration, including forward nullable FKs (review, actor, ai_usage_log) and `note`, all D-02 delete rules, and all D-07 constraints/indexes. Migration round-trips (credits zero, organisations 0002, forward again).
- `ensure_balance(shop_id=..., period=None)` creates the balance via `get_or_create` in `transaction.atomic()`, seeded from the shop's organisation live allocation; with allocation > 0 it writes one INITIAL_ALLOCATION row and one `shop.credits.allocated` AuditLog row (actor=None, after_data keys exactly period_year, period_month, allocated_credits).
- `periods.next_period_start` added test-first; boundary suite covers month edges, IST, naive rejection, December rollover and the `utc_now` patch seam.
- Postgres harness: `pg_concurrency` marker, root `conftest.py` collection hook (auto-skip off PG; `REQUIRE_PG=1` exits 3), `config/settings/test_pg.py`, `backend-pg` CI job, `make test-pg`, and the 8-thread first-use race test.

## Task Commits

1. **Task 1: tracer, first credit use creates the shop's month balance** - `b2c7fd9` (feat)
2. **Task 2: period boundaries + factories (TDD)**
   - RED: `8888b4b` (test) - next_period_start tests fail with AttributeError
   - GREEN: `81e0df6` (feat) - next_period_start implemented
3. **Task 3: Postgres CI harness and first-use race test** - `078cbfb` (chore)

Note: `0f6f8fa docs(30): capture phase context` also landed on the branch during execution. It is not part of this plan's work but is included in the measured `commits: 5` count (4 plan commits + 1 foreign docs commit).

**Plan metadata:** committed separately (docs: complete plan).

### TDD Gate Compliance

- RED: `test(29-01)` commit `8888b4b`. Evidence validated with `gsd_run check tdd-red-evidence` (JUnit XML from the actual pytest run): `RED_EVIDENCE_OK`, reason `target_test_failed`, 7 tests, 2 failing (both `next_period_start` tests, on `AttributeError: module ... has no attribute 'next_period_start'`). Semantic assessment: the target tests executed and failed on the planned missing behavior, not on import/collection/fixture faults (the tests reference the function via the module attribute inside the test body so collection succeeds). The 5 other tests (current_period boundaries, prebuilt-balance test) passed at RED because that behavior was already delivered by the tracer; they are regression locks, not RED targets.
- GREEN: `feat(29-01)` commit `81e0df6` follows RED. REFACTOR: none needed.

## Decisions Made

- IntegerField for the org allocation (Coalesce mixed-type avoidance); `db_index=False` on balance/ledger shop and organisation FKs because composite indexes lead with them.
- Otherwise followed the plan and CONTEXT D-01..D-07, D-10, D-14 as specified.

## Deviations from Plan

None - plan executed exactly as written. Two minor observations, not deviations:
- `makemigrations` added a `swappable_dependency(AUTH_USER_MODEL)` to organisations 0003 alongside the planned dependency on 0002; harmless and consistent with 0001.
- Task 1 did not need its own tracer-gate checkpoint: `HUMAN_VERIFY_MODE` is end-of-phase with an automated-only verify, and the tracer's verify commands were re-run clean (all five passed) before expansion.

## Verification Results (real output)

- `pytest apps/credits apps/organisations apps/shops` on SQLite: all pass, 2 skipped (the pg_concurrency tests, reason "pg_concurrency requires PostgreSQL (use `make test-pg`)"). Full repo suite also passes with no failures.
- `makemigrations --check --dry-run`: "No changes detected". Migration round-trip: `MIGRATIONS_REVERSIBLE`.
- `mypy apps/credits apps/organisations`: no issues; `ruff check` / `ruff format --check`: clean; pre-commit hooks passed on every commit (no `--no-verify`).
- `REQUIRE_PG=1 pytest apps/credits` on SQLite: exit status 3 (guard works).
- `pytest --markers` lists `pg_concurrency`; CI YAML check printed `CI_JOBS_OK` (backend-pg on postgres:16 with `config.settings.test_pg` and `REQUIRE_PG=1`; backend-test still has `--cov-fail-under=85`); `make -n test-pg` references `config.settings.test_pg`.
- **Postgres-backed tests DID run locally**: a throwaway PostgreSQL 14 cluster (Homebrew `initdb`/`pg_ctl`, port 54329) ran `pytest --ds=config.settings.test_pg -m pg_concurrency` with `REQUIRE_PG=1`: "2 passed in 1.82s", 0 skipped. Note: the plan's command did not create the `reviewmaster` database first; I ran `createdb` on the throwaway cluster before the test run (pytest-django then creates `test_reviewmaster`).
- Not yet verified: the GitHub Actions `backend-pg` job itself (needs a push; locally PostgreSQL 14 vs CI 16).

## Issues Encountered

None blocking.

## Known Stubs

None.

## Threat Flags

None - no new network endpoints, auth paths or trust-boundary schema beyond the plan's threat model (T-29-01..T-29-09 mitigations implemented as specified; T-29-02 constraint-enforcement tests belong to Plan 02).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (append-only guards, ledger.transition_status, admin, constraint tests) and Plan 03 (credit_cost, selectors) can build on the models, factories and period seam.
- After pushing, confirm `CI / backend-pg` is green with at least 1 test passed and none skipped (manual, per VALIDATION).

## Self-Check: PASSED

- Files verified present: apps/credits/models.py, migrations/0001_initial.py, services/periods.py, services/allocation.py, tests/factories.py, tests/conftest.py, tests/test_allocation.py, tests/test_periods.py, tests/test_pg_concurrency.py, apps/organisations/migrations/0003_organisation_monthly_credit_allocation.py, config/settings/test_pg.py
- Commits verified in history: b2c7fd9, 8888b4b, 81e0df6, 078cbfb

---
*Phase: 29-credits-ledger-foundation*
*Completed: 2026-11-11*
