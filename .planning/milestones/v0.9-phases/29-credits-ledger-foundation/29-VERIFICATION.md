---
phase: 29-credits-ledger-foundation
verified: 2026-11-11T15:10:00Z
status: human_needed
score: 15/15 must-haves verified
covered_files:
  - ".github/workflows/ci.yml"
  - ".planning/phases/29-credits-ledger-foundation/29-01-PLAN.md"
  - ".planning/phases/29-credits-ledger-foundation/29-01-SUMMARY.md"
  - ".planning/phases/29-credits-ledger-foundation/29-02-PLAN.md"
  - ".planning/phases/29-credits-ledger-foundation/29-02-SUMMARY.md"
  - ".planning/phases/29-credits-ledger-foundation/29-03-PLAN.md"
  - ".planning/phases/29-credits-ledger-foundation/29-03-SUMMARY.md"
  - ".planning/phases/29-credits-ledger-foundation/29-04-PLAN.md"
  - ".planning/phases/29-credits-ledger-foundation/29-04-SUMMARY.md"
  - "CLAUDE.md"
  - "Makefile"
  - "apps/credits/admin.py"
  - "apps/credits/apps.py"
  - "apps/credits/exceptions.py"
  - "apps/credits/managers.py"
  - "apps/credits/migrations/0001_initial.py"
  - "apps/credits/models.py"
  - "apps/credits/selectors/balances.py"
  - "apps/credits/services/allocation.py"
  - "apps/credits/services/credit_cost.py"
  - "apps/credits/services/ledger.py"
  - "apps/credits/services/periods.py"
  - "apps/credits/tests/test_append_only.py"
  - "apps/organisations/migrations/0003_organisation_monthly_credit_allocation.py"
  - "apps/organisations/models.py"
  - "config/settings/base.py"
  - "config/settings/test.py"
  - "config/settings/test_pg.py"
  - "conftest.py"
  - "pyproject.toml"
covered_digest: "v4:sha256:9fa28e19e62a8f8e66ea99746fe006a5426765720518bc7e3f59d4c0c5d0c235"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 13/15
  gaps_closed:
    - "WR-02 (positional form): bulk_create(objs, None, False, True, [...], [...]) now raises AppendOnlyViolation (explicit Django signature on CreditTransactionQuerySet.bulk_create, commit 4181236)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Push feat/v0.9-ai-reply-credits and confirm the GitHub Actions backend-pg job (postgres:16-alpine) goes green with all 3 pg_concurrency tests passing and 0 skipped"
    expected: "Job runs `pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs` with REQUIRE_PG=1; 3 passed; the existing backend-test (SQLite, 85% gate) job is also still green"
    why_human: "The workflow has never executed (branch unpushed). Workflow YAML syntax, service-container health check, `uv sync --frozen` and PG16 behaviour cannot be proven from the local tree. The 3 pg_concurrency tests have only run on a throwaway local PostgreSQL 14 cluster (earlier verification); they skip off-Postgres, so this re-verification did not re-run them."
audit_acknowledged:
  milestone: v0.9
  at: 2026-11-12
  status: human_needed
---

# Phase 29: Credits Ledger Foundation Verification Report

**Phase Goal:** Every shop has a trustworthy monthly AI-reply credit balance and an append-only ledger whose rules the database enforces. One authoritative function prices each review, and real-Postgres concurrency tests run in CI. This is the contract every later credit feature builds on.
**Verified:** 2026-11-11
**Status:** human_needed
**Re-verification:** Yes, second re-verification, after commits 4ab64ec (RED test) and 4181236 (fix)

## Re-verification summary

The single remaining gap (positional `update_conflicts` on `bulk_create`) is closed. `git diff 4181236~2 HEAD --stat` confirms only two files changed since the previous report: `apps/credits/managers.py` and `apps/credits/tests/test_append_only.py`. All other previously verified items are carried forward.

I read `managers.py` directly. `CreditTransactionQuerySet.bulk_create` now declares Django's full signature `(objs, batch_size=None, ignore_conflicts=False, update_conflicts=False, update_fields=None, unique_fields=None)`, raises `AppendOnlyViolation` on any truthy `update_conflicts` before delegating, and delegates to `super()` by keyword (without `update_conflicts`). So the guard sees the argument however it is spelled.

I re-tested every write path with a throwaway test file (`apps/credits/tests/test_zz_throwaway.py`, 8 tests, all passed, file deleted afterwards; `git status` shows only `29-VERIFICATION.md` modified and the pre-existing untracked `.planning/state.json`):

| Write-path attempt (current code, SQLite) | Result |
|---|---|
| `bulk_create([clone], None, False, True, ["credits_delta"], ["id"])` (positional, full) | AppendOnlyViolation, row stays -1. CLOSED |
| `bulk_create([clone], None, False, True)` (positional, short) | AppendOnlyViolation, row unchanged |
| `bulk_create([clone], update_conflicts=True, update_fields=..., unique_fields=...)` (keyword) | AppendOnlyViolation, row unchanged |
| mixed: `bulk_create([clone], 10, ignore_conflicts=False, update_conflicts=True, ...)` | AppendOnlyViolation |
| via `.objects.all()`, `.objects.filter(pk=...)`, and the related manager `balance.transactions.bulk_create(...)` | AppendOnlyViolation each; row unchanged |
| `bulk_create([clone], ignore_conflicts=True)` and positional `(…, None, True)` on an existing pk | no-op, row unchanged (DO NOTHING, not a rewrite) |
| `save()` with reused pk: plain, `force_insert=False`, `force_update=True`, `update_fields=[...]`, positional `save(False, False, None, None)` | each raises; row unchanged |
| `.filter().update()`, `.filter().delete()`, `instance.delete()`, `bulk_update`, `update_or_create` on an existing pk, `save()` with a changed field | AppendOnlyViolation; row unchanged |
| plain `bulk_create` of new rows (default, and with positional `batch_size`) | inserts (count +4). Phase 30/31 insert paths unaffected |

Residual, accepted by design (D-05 raw-SQL carve-out): bypassing the model layer entirely (raw SQL, `models.QuerySet.bulk_create(qs, ...)` called explicitly on the base class, or the private `_base_manager`) is not guarded in Python. The DB CHECK/unique constraints still bound the damage. This was the stated scope of D-05 from the start and is not a gap against CRED-03's "no update/delete path" as it is used in the codebase (all public ORM paths).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | First credit operation creates exactly one balance seeded from org allocation, one INITIAL_ALLOCATION row + one `shop.credits.allocated` AuditLog (none for allocation 0); concurrent first uses yield one row | VERIFIED | Carried forward: `services/allocation.py` unchanged; credits suite passes; PG14 race test passed in an earlier verification |
| SC2a | DB rejects duplicate `(shop, year, month)` balance and consumed < 0 or > allocated + bonus | VERIFIED | Constraints in `models.py`/`0001_initial.py` unchanged; `makemigrations --check`: No changes detected |
| SC2b | Ledger rows have no update/delete path except named status-transition functions | VERIFIED | All public ORM write paths re-tested (table above): update, delete, bulk_update, update_or_create, reused-pk save, bulk_create(update_conflicts) in keyword and positional spellings, via manager, queryset and related manager |
| SC2c | Admin shows both models read-only | VERIFIED | `admin.py` unchanged; `test_admin.py` passes |
| SC3 | Reading a balance never writes; no row means full org allocation | VERIFIED | `selectors/balances.py` unchanged; selector tests pass |
| SC4 | Cost 1/2/3 by trimmed length, one pure function, settings tiers, open top tier | VERIFIED | `credit_cost.py` unchanged; boundary tests pass |
| SC5 | Postgres CI job runs `pg_concurrency` tests; marker registered under `--strict-markers` | PRESENT, NOT YET EXECUTED (human item) | `ci.yml` runs `pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs`; no diff to CI/conftest/settings; never run on GitHub |
| P1-a..d | `ensure_balance` idempotent, org derived from shop; org allocation field + CHECK; full CreditTransaction schema and constraints | VERIFIED | `makemigrations --check` clean; no schema change |
| P2-a | Status moves only RESERVED to COMMITTED/REFUNDED via CAS | VERIFIED | `save()` non-adding branch and `ledger.py` unchanged; tests pass |
| P2-b | `assert_ledger_reconciles` helper | VERIFIED | unchanged, tested |
| P3-a/b | `CreditBalanceView`, selectors, CLAUDE.md lists `apps/credits`, mypy strict, migrations clean | VERIFIED | `mypy apps/credits`: Success, no issues in 26 source files. Coverage not re-measured (delta is one method plus one test; earlier figure 99.04%) |
| 29-04 T1 | Reused-pk `save()` forces insert, raises, row unchanged | VERIFIED | re-tested (5 variants) |
| 29-04 T2 | `bulk_create(update_conflicts=True)` raises AppendOnlyViolation before SQL, rows unchanged | VERIFIED | keyword and positional forms both raise; row unchanged (new regression test `test_bulk_create_raises_when_update_conflicts_passed_positionally` is real: asserts exception and unchanged `credits_delta == -1`) |
| 29-04 T3 | Plain `create()` / `bulk_create()` still insert | VERIFIED | re-tested; existing test passes |
| 29-04 T4 | All existing credits tests still pass unchanged | VERIFIED | `pytest apps/credits -q --no-cov -o addopts=""`: 127 passed, 3 skipped (pg_concurrency off-Postgres, by design) |
| Proh. | No PII in ledger/AuditLog; backend-pg cannot pass vacuously; no cost logic outside `credit_cost.py` | VERIFIED | unchanged since earlier verification |

**Score:** 15/15 verified in code (SC5's CI execution is carried as the human item). 0 behavior-unverified.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `apps/credits/managers.py` | VERIFIED | Explicit Django signature; truthy `update_conflicts` rejected before SQL; delegates by keyword. Wired: Django resolves `CreditTransaction.objects`, `.all()`, `.filter()` and the related manager to this queryset (verified by the tests above) |
| `apps/credits/models.py` | VERIFIED | adding-path `save()` forces insert. Dead positional-args branch (IN-01) left, info only |
| `apps/credits/tests/test_append_only.py` | VERIFIED | positional-spelling regression test present and substantive |
| Remaining Phase 29 artifacts | VERIFIED | no diff since earlier verification |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| `CreditTransaction.save` (adding) | Django `Model.save(force_insert=True)` | WIRED | reused pk collides on the PK |
| `CreditTransactionQuerySet.bulk_create` | callers via manager / queryset / related manager | WIRED | override invoked for every spelling tested |
| `ci.yml::backend-pg` | `config/settings/test_pg.py` | WIRED (unexecuted) | see human item |
| Phase 29 services/selectors | production callers | ORPHANED by design | callers arrive in Phases 30-33 |

### Data-Flow Trace (Level 4)

Unchanged and unaffected: `get_shop_credit_balance` and `annotate_credit_state` still flow from real DB rows / org allocation.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Credits suite | `.venv/bin/pytest apps/credits -q --no-cov -o addopts=""` | 127 passed, 3 skipped | PASS |
| Typecheck | `.venv/bin/mypy apps/credits` | no issues in 26 source files | PASS |
| Migrations in sync | `manage.py makemigrations --check --dry-run` | No changes detected | PASS |
| Ledger write-path matrix | throwaway test file (8 tests), deleted | 8 passed | PASS |
| pg_concurrency tests | not re-run | skip off-Postgres; no Postgres started per constraints | NOT RE-RUN (carried: 3 passed on PG14 earlier) |

### Probe Execution

No `probe-*.sh` declared or present. Step 7c: SKIPPED.

### Requirements Coverage

All five Phase 29 IDs appear in PLAN frontmatter (29-01: CRED-02, CQA-01; 29-02: CRED-02, CRED-03, CQA-01; 29-03: CRED-04, CRED-05; 29-04: CRED-03) and in REQUIREMENTS.md; no orphaned requirements.

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| CRED-02 | 29-01, 29-02 | SATISFIED | lazy per-month balance, DB uniqueness and CHECKs, tests |
| CRED-03 | 29-02, 29-04 | SATISFIED | append-only across all public ORM paths, CAS status transitions, read-only admin |
| CRED-04 | 29-03 | SATISFIED | single pure `credit_cost`, settings tiers, boundary tests |
| CRED-05 | 29-03 | SATISFIED | virtual balance, no writes, full-allocation fallback |
| CQA-01 | 29-01, 29-02 | SATISFIED for Phase 29 scope, CI run pending | job + marker + first-use and CAS race tests exist; REQUIREMENTS.md notes the CCON-02 and CREN-03 tests land in Phases 30/31 |

Bookkeeping note: `.planning/REQUIREMENTS.md` still marks CRED-02/04/05 and CQA-01 as `[ ]`/"Gaps Found" while CRED-03 is `[x]`. Update the traceability table when closing the phase (CQA-01 only after the CI run is green).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/credits/models.py` | ~205-207 | dead positional-args branch in non-adding `save()` (IN-01) | Info | none |
| `selectors/balances.py`, `services/allocation.py`, `credit_cost.py` | - | WR-03, IN-03, IN-04 | Info | out of must-have scope, `open` in 29-REVIEW-DISPOSITION.md |
| `apps/credits/managers.py`, `models.py`, `tests/test_append_only.py` | - | TBD/FIXME/XXX/TODO/HACK | none found | - |

### Human Verification Required

#### 1. First GitHub Actions run of `backend-pg`

**Test:** Push the branch and open or update the PR; watch the `backend-pg` job on `postgres:16-alpine`.
**Expected:** 3 `pg_concurrency` tests pass, 0 skipped, job green; `backend-test` (SQLite, 85% gate) and the other jobs still green.
**Why human:** The workflow has never executed. Locally the 3 tests were only proven on PostgreSQL 14 earlier and were not re-run here. GitHub-side wiring (YAML, service-container health check, `uv sync --frozen`) and PG16 itself remain unproven. This is the CQA-01 "real-Postgres concurrency tests run in CI" claim.

### Gaps Summary

No code gaps remain. The positional `update_conflicts` hole is closed by an explicit-signature override with a genuine regression test, and a full write-path matrix (positional and keyword `bulk_create(update_conflicts)`, reused-pk `save()`, update/delete/bulk_update/update_or_create, plain `bulk_create`) behaves as required. The credits suite (127 passed, 3 skipped), mypy strict and migration checks are clean. The phase is `human_needed` solely because the CI job, the delivery mechanism for CQA-01, has never run on GitHub Actions.

---

_Verified: 2026-11-11_
_Verifier: Claude (gsd-verifier)_
