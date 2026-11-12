---
phase: 29-credits-ledger-foundation
plan: 03
subsystem: database
tags: [django, credits, pricing, selectors, filtered-relation, coalesce, pytest]

requires:
  - phase: 29-credits-ledger-foundation
    provides: "Plans 01/02: models, period seam, factories, append-only ledger, pg_concurrency harness"
provides:
  - "credit_cost(text): the single pure pricing function (0/1/2/3, tiers from settings, open top tier)"
  - "CreditBalanceView + get_shop_credit_balance: frozen single-shop virtual balance read"
  - "annotate_credit_state: one-query Shop list annotation (credit_allocated/bonus/consumed/remaining/materialized)"
  - "CLAUDE.md section 3 lists apps/credits"
  - "Phase 29 gates: full suite, coverage, mypy strict, migrations, Postgres concurrency"
affects: [30-reserve-commit-refund, 31-lapse-reaper, 32-superadmin-allocation, 33-credits-ui]

actuals:
  tokens: 14000
  tasks: 3
  commits: 7
plan_head_before: d7683c65e4ca27fa81404ea54a37bc41976f0ebf
plan_head_after: ca7f8e698a5c680be8c46e8b93993686df2363de

tech-stack:
  added: []
  patterns:
    - "FilteredRelation on the current period + Coalesce over the org's live allocation for virtual balances (no row created on read)"
    - "Function-level import of Shop in the credits selector keeps credits a leaf at module scope"
    - "Source-scan settings test pins the tiers setting to exactly credit_cost.py and base.py"

key-files:
  created:
    - apps/credits/services/credit_cost.py
    - apps/credits/selectors/__init__.py
    - apps/credits/selectors/balances.py
    - apps/credits/tests/test_credit_cost.py
    - apps/credits/tests/test_settings.py
    - apps/credits/tests/test_selectors.py
  modified:
    - CLAUDE.md
    - apps/credits/tests/test_models.py

key-decisions:
  - "FilteredRelation (not Subquery) for the list annotation; query-count tests assert exactly 1 query for 2 and 20 shops"
  - "credit_cost returns 0 only for empty/whitespace input and otherwise falls back to the last tier on malformed config (stays total, never raises)"
  - "Selectors are unscoped primitives; tenant/Staff scoping is Phase 32/33 endpoint work (T-29-19 transferred)"

patterns-established:
  - "Reads never write: tests assert unchanged row counts and no INSERT/UPDATE/DELETE in captured SQL"

requirements-completed: [CRED-04, CRED-05]

coverage:
  - id: D1
    description: "credit_cost returns 0 for None/empty/whitespace-only (incl. NBSP, U+3000), and 1/2/3 at boundaries 1,100,101,500,501,10000,10001; trims before counting; emoji count per code point; tiers read at call time"
    requirement: CRED-04
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_credit_cost.py (19 tests, no DB access)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Tier config shape (ascending bounded, open top tier, positive int costs), TTL == 5, support email, and single-source scan of the tiers setting"
    requirement: CRED-04
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_settings.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "get_shop_credit_balance: live org fallback, other-month row ignored, materialised row wins, frozen view, renews_on, inactive shops, 1-2 queries, Shop.DoesNotExist, never writes"
    requirement: CRED-05
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_selectors.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "annotate_credit_state: correct values, filterable, exactly 1 query for 2 and 20 shops, one row per shop with order preserved, per-org fallback across two orgs, never writes"
    requirement: CRED-05
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_selectors.py (also 126 passed on throwaway PostgreSQL 14)"
        status: pass
    human_judgment: false
  - id: D5
    description: "CI backend-pg job green after push"
    verification: []
    human_judgment: true
    rationale: "Requires a push and a GitHub Actions run; verified locally on PostgreSQL 14 only"

duration: 35min
completed: 2026-11-11
status: complete
---

# Phase 29 Plan 03: credit_cost and Virtual-Balance Selectors Summary

**One pure `credit_cost(text)` (0/1/2/3 from settings tiers, code-point length, open top tier) plus never-writing balance selectors (`get_shop_credit_balance`, one-query `annotate_credit_state` via FilteredRelation + Coalesce), closing Phase 29 with the CLAUDE.md section 3 update and the ORM audit**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-11-11
- **Tasks:** 3 (Tasks 1 and 2 TDD, Task 3 gate)
- **Files modified:** 8 (plus 2 planning files)

## Accomplishments

- `credit_cost` is total and pure: `len((text or "").strip())` in code points, 0 means not chargeable, tiers read from `settings.REVIEWBEE_CREDIT_TIERS` at call time. Boundaries 1/100/101/500/501/10000/10001, whitespace (ASCII, NBSP, U+3000), emoji, ZWJ, flag and ZWSP behaviours are all proven. Tests carry no `django_db` mark, so any DB access would error.
- A settings test pins the tier shape and a source scan asserts only `credit_cost.py` and `config/settings/base.py` mention the tiers setting (price shown equals price charged, T-29-17/18).
- `get_shop_credit_balance` returns a frozen `CreditBalanceView`; with no current-month row it reports the organisation's live allocation as allocated and remaining (unmaterialised), uses 1 query with a row and 2 without, and ignores `is_active`.
- `annotate_credit_state` adds five annotations in exactly 1 query for 2 or 20 shops, with one row per shop, preserved order, and per-org fallback. Both selectors are proven never to write.
- CLAUDE.md section 3 now lists `credits/` (7 inserted lines, 0 deleted).

## Task Commits

1. **Task 1: credit_cost (TDD)** - RED `2f55271` (test), GREEN `618dd08` (feat)
2. **Task 2: balance selectors (TDD)** - RED `93c60ed` (test), GREEN `ba0f2ef` (feat)
3. **Task 3: phase gate** - `3001533` (fix, PG-only test brittleness from Plan 02), `ca7f8e6` (docs, CLAUDE.md section 3)

Note: the measured `commits: 7` includes one foreign commit (`548cdd7 docs(phase-30)`, made by a concurrent session); 6 commits are this plan's.

**Plan metadata:** committed separately (docs: complete plan).

### TDD Gate Compliance

- Task 1 RED: `2f55271`. `gsd_run check tdd-red-evidence` on the real pytest JUnit XML: `RED_EVIDENCE_OK`, `target_test_failed`. A stub `credit_cost` returning 0 was included so RED failed on assertions (16 failing), not on import. Semantic assessment: boundary, emoji, call-time-settings and single-source tests failed on the planned behaviour; the zero-input tests passed against the stub (regression locks). GREEN `618dd08`; no refactor.
- Task 2 RED: `93c60ed`. `RED_EVIDENCE_OK`, `target_test_failed`, 16 failing. The stub returned a zero `CreditBalanceView` and the unannotated queryset, so failures were behavioural (wrong values, `AttributeError: no attribute credit_remaining`). GREEN `ba0f2ef`; no refactor.

## orm-performance-auditor

The Agent tool was not available to this executor, so the auditor's checklist was walked inline over `models.py`, `migrations/0001_initial.py`, `organisations` model + migration 0003, `selectors/balances.py`, `services/allocation.py` and `admin.py`. No blocker findings; no schema change (0001 not regenerated).

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | `shop`/`organisation` FKs on both models use `db_index=False` | Accepted: unique `(shop, year, month)`, `(organisation, year, month)`, `(shop, created_at)` and `(organisation, created_at)` lead with them, so PROTECT-delete lookups and joins are indexed |
| 2 | `review`, `ai_usage_log`, `actor`, `shop_credit_balance` FKs keep default `db_index=True` | Accepted: needed for SET_NULL / PROTECT cascade scans and ledger-by-balance reads |
| 3 | Current-period FilteredRelation join | Accepted: rides the unique `(shop, year, month)` index, max one match, no fan-out |
| 4 | Lapse scan (Phase 31) by `(period_year, period_month)` across all orgs is not covered by an index leading with period | Accepted/deferred to Phase 31: table is shops x months (small); add an index there only if the scan design needs it |
| 5 | RESERVED reaper scan | Accepted: partial index `credit_tx_reserved_idx (status, created_at) WHERE status='RESERVED'` matches the query shape |
| 6 | History reads by `created_at` | Accepted: `(shop, created_at)` and `(organisation, created_at)` indexes |
| 7 | Admin N+1 | Accepted: `list_select_related` + `raw_id_fields`; changelist query count is constant (test_admin) |
| 8 | Selector list path N+1 | Accepted: `annotate_credit_state` proven 1 query for 2 and 20 shops |
| 9 | Migrations: reversible, no RunPython; org 0003 adds a CHECK (table scan under lock) | Accepted: round trip verified in Plan 01; organisations is a small table |
| 10 | `balance.organisation` is denormalised from `shop.organisation` with no DB constraint | Accepted: always set from the Shop row in `ensure_balance` (tenant-safe by construction) |
| 11 | Selector SQL on PostgreSQL (boolean ExpressionWrapper, Coalesce) only exercised on SQLite by default | Fixed by verification: `apps/credits` run on PostgreSQL 14, 126 passed |

## Decisions Made

- FilteredRelation chosen over Subquery (RESEARCH A7); the query-count test is the arbiter.
- `get_shop_credit_balance` imports `Shop` at function level (RESEARCH A6); `Shop.DoesNotExist` for an unknown shop (A-CRED05).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in test] PostgreSQL reports a different CHECK name for allocated = -1**
- **Found during:** Task 3 (running all of `apps/credits` on the throwaway PostgreSQL, beyond the plan's pg_concurrency-only command)
- **Issue:** Plan 02's `test_negative_values_are_rejected_when_credits_go_below_zero[values1]` asserted `credit_balance_nonneg`, but `allocated=-1` also violates `credit_balance_no_overspend`, and PostgreSQL does not guarantee which CHECK it names first. SQLite passed; PostgreSQL failed.
- **Fix:** parametrised the expected constraint pattern; the ambiguous case accepts either name.
- **Files modified:** apps/credits/tests/test_models.py
- **Commit:** 3001533

**2. [Rule 3 - Blocking] Tooling**
- RED needed stubs (as in Plans 01/02) so RED did not fail on import; ruff format rewrote escaped NBSP/U+3000/U+200B test literals into raw characters (RUF001), so the tests build them with `chr(...)`; `annotate_credit_state` assigns to an annotated local to satisfy mypy `no-any-return`; the first `mypy .` run crashed on a corrupt incremental cache, so it was re-run with `--cache-dir=/dev/null`.

**Total deviations:** 2 (1 test bug, 1 tooling). **Impact:** none on scope or behaviour.

## Verification Results (real output)

- `pytest --cov=apps --cov-fail-under=85`: **1340 passed, 5 skipped**, total coverage **89.08%** ("Required test coverage of 85% reached"). `apps/credits/selectors/balances.py` 100%, `admin.py` 100%, `models.py` 98%. The 5 skips are the 3 pg_concurrency tests plus 2 pre-existing skips.
- `mypy --cache-dir=/dev/null .`: "Success: no issues found in 329 source files".
- `makemigrations --check --dry-run` (config.settings.test): "No changes detected".
- `manage.py check --deploy` under `config.settings.test`: exit 0 with 21 security warnings (W009/W012/W016 etc.). These are expected for test settings and are not errors; it was NOT run against production settings (no production env available).
- PostgreSQL 14 throwaway cluster (port 54329, `createdb reviewmaster` first): `REQUIRE_PG=1 pytest --ds=config.settings.test_pg -m pg_concurrency`: **3 passed**, 0 skipped. Additionally `pytest --ds=config.settings.test_pg apps/credits`: **126 passed**. Cluster stopped and removed (`pgrep` confirmed no postgres on 54329).
- Acceptance greps: `def credit_cost` 1; `settings.REVIEWBEE_CREDIT_TIERS` 2; boundary-number grep 17; `django_db` in test_credit_cost 0; `frozen=True` 1; `FilteredRelation` 2; `output_field=` 5; module-level cross-app imports 0; `CaptureQueriesContext` 6; CLAUDE.md `git diff --numstat 1aca7f3` = 7 added / 0 deleted.
- Not run: GitHub Actions `CI / backend-pg` (needs a push; local PostgreSQL 14 vs CI 16). Manual post-push check remains per VALIDATION.md.

## Issues Encountered

None blocking. A transient hang came from mistakenly sourcing a reference `.md` as a shell script; it was killed, and no files were affected.

## Known Stubs

None.

## Threat Flags

None. T-29-17, T-29-18, T-29-20 and T-29-21 mitigations are implemented and tested; T-29-19 (unscoped selectors) is transferred to the Phase 32/33 endpoints with `tenant-security-auditor`, as planned.

## User Setup Required

None.

## Next Phase Readiness

- Phase 29 is complete locally. Phase 30 can price with `credit_cost`, read balances with the selectors and settle via `ledger.transition_status`.
- After pushing, confirm `CI / backend-pg` is green with all pg tests passing and none skipped.

## Self-Check: PASSED

- Files verified present: credit_cost.py, selectors/__init__.py, selectors/balances.py, tests/test_credit_cost.py, tests/test_settings.py, tests/test_selectors.py
- Commits verified in history: 2f55271, 618dd08, 93c60ed, ba0f2ef, 3001533, ca7f8e6

---
*Phase: 29-credits-ledger-foundation*
*Completed: 2026-11-11*
