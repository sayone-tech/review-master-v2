---
phase: 29-credits-ledger-foundation
verified: 2026-11-11T12:30:00Z
status: gaps_found
score: 13/15 must-haves verified
covered_files:
  - ".github/workflows/ci.yml"
  - ".planning/phases/29-credits-ledger-foundation/29-01-PLAN.md"
  - ".planning/phases/29-credits-ledger-foundation/29-01-SUMMARY.md"
  - ".planning/phases/29-credits-ledger-foundation/29-02-PLAN.md"
  - ".planning/phases/29-credits-ledger-foundation/29-02-SUMMARY.md"
  - ".planning/phases/29-credits-ledger-foundation/29-03-PLAN.md"
  - ".planning/phases/29-credits-ledger-foundation/29-03-SUMMARY.md"
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
  - "apps/organisations/migrations/0003_organisation_monthly_credit_allocation.py"
  - "apps/organisations/models.py"
  - "config/settings/base.py"
  - "config/settings/test.py"
  - "config/settings/test_pg.py"
  - "conftest.py"
  - "pyproject.toml"
covered_digest: "v4:sha256:4cab20cf2a76fc2b7b8421854e5da876921e3247b97e68f9fe62044dde308122"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "CreditTransaction rows cannot be changed or removed through QuerySet.update(), QuerySet.delete(), bulk_update(), instance.delete(), or instance.save() of any field other than status; each raises AppendOnlyViolation (29-02 truth 1; CRED-03 'no update/delete path exists'; ROADMAP SC2)"
    status: partial
    reason: "Two ORM insert-path escape hatches rewrite committed ledger rows without raising. WR-01: CreditTransaction(pk=<existing>, ..., created_at=...).save() has _state.adding=True, so save() delegates to super().save() with no force_insert; Django issues UPDATE first and overwrites the row. WR-02: CreditTransaction.objects.bulk_create([...], update_conflicts=True, unique_fields=['id'], update_fields=[...]) emits INSERT .. ON CONFLICT DO UPDATE and never touches the guarded update(). Both were reproduced by the verifier on SQLite (a RESERVED row with delta -2 became COMMITTED with delta -99 via save(), and delta -77 via bulk_create). Neither path is covered by a test."
    artifacts:
      - path: "apps/credits/models.py"
        issue: "save() lines ~195-197: the _state.adding branch forwards to super().save() without force_insert=True"
      - path: "apps/credits/managers.py"
        issue: "CreditTransactionQuerySet does not override bulk_create; update_conflicts=True is an unguarded rewrite path"
    missing:
      - "In CreditTransaction.save(): when self._state.adding, set kwargs['force_insert'] = True before super().save() (and drop the dead positional-args branch, IN-01)"
      - "Override CreditTransactionQuerySet.bulk_create to raise AppendOnlyViolation when update_conflicts (or ignore_conflicts, optionally) is truthy"
      - "Add tests: CreditTransaction(pk=existing.pk, created_at=...).save() raises IntegrityError/AppendOnlyViolation and leaves the row unchanged; bulk_create(update_conflicts=True) raises AppendOnlyViolation"
human_verification:
  - test: "Push feat/v0.9-ai-reply-credits and confirm the GitHub Actions backend-pg job (postgres:16-alpine) goes green with all 3 pg_concurrency tests passing and 0 skipped"
    expected: "Job runs `pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs` with REQUIRE_PG=1; 3 passed; the existing backend-test (SQLite, 85% gate) job is also still green"
    why_human: "The workflow has never executed (branch not pushed). Workflow YAML syntax, service-container health check, `uv sync --frozen`, and PG16 behaviour cannot be proven from the local tree. The verifier did run the same 3 tests, and the full credits suite (126 tests), against a throwaway local PostgreSQL 14 cluster: all passed."
---

# Phase 29: Credits Ledger Foundation Verification Report

**Phase Goal:** Every shop has a trustworthy monthly AI-reply credit balance and an append-only ledger whose rules the database enforces. One authoritative function prices each review, and real-Postgres concurrency tests run in CI. This is the contract every later credit feature builds on.
**Verified:** 2026-11-11
**Status:** gaps_found
**Re-verification:** No, initial verification

## Verdict on the code-review findings (WR-01, WR-02)

**WR-01 and WR-02 are a real, small gap against the stated must-haves, not mere acceptable residual risk.** I reproduced both myself (throwaway tests, since deleted): a committed RESERVED ledger row had its `credits_delta` and `status` rewritten through each path with no exception.

Why D-05 does not excuse them:

- D-05 accepted the **absence of a Postgres trigger** (so raw SQL, `QuerySet.update` via `models.QuerySet.update(...)`, `_base_manager`, and other non-ORM paths are known, accepted residual risk). It did not accept holes in the ORM-level guards it itself specified. D-05 explicitly lists "`save()` on an existing row rejects any change other than `status`" and "a custom QuerySet blocks `update()`". WR-01 defeats the first bullet through a documented ORM API, and WR-02 defeats the second by a different SQL verb.
- The plan truth reads "instance.save() of any field other than status ... raises AppendOnlyViolation", and ROADMAP SC2 / CRED-03 read "no update or delete path exists". Both are falsified by a reproducible call.
- Mitigating context, which keeps this at warning-level severity and not a phase-blocking defect: neither path can be hit accidentally. WR-01 needs a hand-built instance with an explicit existing pk and an explicit `created_at`; WR-02 needs `update_conflicts=True` plus `unique_fields`. No Phase 29 code, and no Phase 30/31 code described in the plan, uses either. The DB CHECK constraints (delta sign, non-consumption-must-be-COMMITTED, balance non-negative / no-overspend) still hold on both paths.
- Fix cost is about 10 lines plus 2 tests (`force_insert=True`; a `bulk_create` override). Closing it now is cheaper than carrying an unguarded rewrite path into Phase 30, which is the first phase to write CONSUMPTION rows in bulk and under concurrency. Recommended: close via `/gsd-plan-phase --gaps` (or a quick fix) before Phase 30 execution.

WR-03 (selector/`ensure_balance` with a non-current `period`) is outside the must-haves: CRED-05 and the plan truths are about the current period, the default argument. Advisory only.

## Goal Achievement

### Observable Truths (ROADMAP success criteria, then plan must-haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | First credit operation creates exactly one balance row seeded from org allocation, one INITIAL_ALLOCATION row + one `shop.credits.allocated` AuditLog row (none for allocation 0); N concurrent first uses on Postgres yield one row and one INITIAL | VERIFIED | `allocation.py::ensure_balance`: `get_or_create` inside `atomic`, INITIAL + AuditLog only `if created and allocation > 0`, `actor=None`, after_data holds only year/month/allocated. `test_allocation.py` passes. `test_first_use_creates_one_balance_and_one_initial_when_n_threads_race` (8 threads, Barrier) passed on PG14 in the verifier's own run. |
| SC2a | DB rejects a second balance for `(shop, year, month)` and any balance with consumed < 0 or > allocated + bonus | VERIFIED | `models.py` constraints `credit_balance_shop_period_uniq`, `credit_balance_nonneg`, `credit_balance_no_overspend`, `credit_balance_month_range`; present in `0001_initial.py`; `test_models.py` passes on SQLite and PG14. |
| SC2b | Ledger rows have no update/delete path except named status-transition functions | FAILED (see gap, warning-level) | `update()`, `delete()`, `bulk_update()`, `instance.delete()`, in-place `save()` of loaded rows are all guarded and tested. But `save()` of a hand-built pk-bearing instance (WR-01) and `bulk_create(update_conflicts=True)` (WR-02) rewrite rows. Reproduced. |
| SC2c | Admin shows both models read-only | VERIFIED | `admin.py`: `has_add/change/delete_permission` return False on both; `test_admin.py` (200 on list/view, 403 on add/change/delete, constant query count) passes. |
| SC3 | Reading a balance (single or list) never writes; no row -> full org allocation, not 0 | VERIFIED | `selectors/balances.py`: `get_shop_credit_balance` uses `.values().first()` plus Shop read; `annotate_credit_state` uses `FilteredRelation` + `Coalesce`. `test_selectors.py` asserts no INSERT/UPDATE/DELETE SQL, unchanged row counts, 1 query for 2 and 20 shops. Passes. |
| SC4 | Cost 1/2/3 for trimmed length 1-100/101-500/501+, one pure function, settings thresholds, open top tier; boundary tests | VERIFIED | `credit_cost.py` is the only consumer of `settings.REVIEWBEE_CREDIT_TIERS` in non-test code (grep); `base.py` tiers `[(100,1),(500,2),(None,3)]`; `test_credit_cost.py` + `test_settings.py` pass (0,1,100,101,500,501,10000,10001, emoji, whitespace, NBSP, U+3000). |
| SC5 | Every PR runs a Postgres CI job executing all `pg_concurrency` tests; marker registered under `--strict-markers` | PRESENT, NOT YET EXECUTED (human item) | `ci.yml` `backend-pg` job (postgres:16-alpine, health check, `--ds=config.settings.test_pg -m pg_concurrency`, `REQUIRE_PG=1`); marker registered in `pyproject.toml`; `conftest.py` skips off-PG and `pytest.exit(returncode=3)` under `REQUIRE_PG`; `make test-pg` exists. Job has never run on GitHub. |
| P1-a | `ensure_balance` idempotent; org derived from shop; no organisation parameter | VERIFIED | `allocation.py` signature `(shop_id, period)`; org read via `Shop.objects...values_list(organisation_id, organisation__monthly_credit_allocation)`. |
| P1-b | `Organisation.monthly_credit_allocation` NOT NULL default 0, CHECK 0..10000, own migration | VERIFIED | `organisations/migrations/0003_...py` contains the field and `org_monthly_credit_allocation_range`. `makemigrations --check`: No changes detected. |
| P1-c | Full CreditTransaction schema incl. nullable review/actor/ai_usage_log FKs, note <=255; FK delete rules per D-02 | VERIFIED | `models.py`: PROTECT on shop/balance/org, SET_NULL on review/actor/ai_usage_log; `test_models.py` covers ProtectedError and SET_NULL survival. |
| P1-d | Ledger DB constraints/indexes (partial unique INITIAL/LAPSED, reserved partial index, delta-sign, only-CONSUMPTION-may-be-non-COMMITTED) | VERIFIED | All present in `models.py` Meta and `0001_initial.py`; tests pass on SQLite and PG14. |
| P2-a | Status moves only RESERVED -> COMMITTED/REFUNDED via CAS; repeat returns True then False; nonexistent id returns False; 8-thread PG race has exactly one winner | VERIFIED | `ledger.py::transition_status` + `managers.py::cas_status`; `test_append_only.py` and `test_cas_transition_succeeds_once_when_n_threads_settle_same_reservation` pass (PG14). Only `ledger.py` and `models.py::save` call `cas_status` (grep). |
| P2-b | `assert_ledger_reconciles` helper | VERIFIED | `tests/helpers.py` exists and is tested. |
| P3-a | `get_shop_credit_balance` frozen `CreditBalanceView`, query-count bounds, `renews_on`, inactive shops computed normally | VERIFIED | `balances.py` frozen slots dataclass; no `is_active` filtering; tests pass. |
| P3-b | CLAUDE.md section 3 lists `apps/credits`; full suite + coverage >= 85%, mypy strict, makemigrations clean | VERIFIED | CLAUDE.md line 125. Verifier: `apps/credits` 126 tests pass on SQLite and on PG14, credits-package coverage 99.04%, `mypy apps/credits`: no issues in 26 files, `makemigrations --check`: no changes. (Full-repo ~89% coverage taken from the executor summary; not re-run by the verifier.) |
| Proh. | No PII in ledger / AuditLog; backend-pg cannot pass vacuously; no cost logic outside `credit_cost.py` | VERIFIED | AuditLog `after_data` = year/month/allocated only; `REQUIRE_PG` hard-exit(3) in `conftest.py`; cost logic only in `credit_cost.py`. |

**Score:** 13/15 truths verified (SC2b failed; SC5 not yet executed in CI, human item). 0 behavior-unverified.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `apps/credits/models.py` | VERIFIED with gap | Full schema + constraints; `save()` guard has WR-01 hole |
| `apps/credits/managers.py` | VERIFIED with gap | Guards update/delete; `bulk_create(update_conflicts)` open (WR-02) |
| `apps/credits/services/{periods,allocation,ledger,credit_cost}.py` | VERIFIED | Substantive, wired, 91-100% covered |
| `apps/credits/selectors/balances.py` | VERIFIED | `FilteredRelation` present; read-only |
| `apps/credits/admin.py` | VERIFIED | Read-only |
| `apps/credits/migrations/0001_initial.py`, `organisations/migrations/0003_...` | VERIFIED | Applied cleanly on PG14 during tests; no pending model changes |
| `config/settings/test_pg.py`, `conftest.py`, `ci.yml`, `Makefile` | VERIFIED (CI unexecuted) | See human item |
| `apps/credits/tests/*` | VERIFIED | All pass; no test for WR-01/WR-02 paths |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| `allocation.py` | `ShopCreditBalance` via `get_or_create` in atomic | WIRED | Confirmed in source; PG race test passes |
| `allocation.py` | `AuditLog` (`shop.credits.allocated`) | WIRED | Confirmed |
| `allocation.py` | `Organisation.monthly_credit_allocation` | WIRED | `organisation__monthly_credit_allocation` values_list |
| `ledger.py::transition_status` / `models.save` | `cas_status` | WIRED | Only two callers, as required |
| `credit_cost.py` | `settings.REVIEWBEE_CREDIT_TIERS` | WIRED | Read at call time |
| `balances.py` | `periods.next_period_start` / `current_period` | WIRED | Used for default period and `renews_on` |
| `ci.yml::backend-pg` | `config/settings/test_pg.py` | WIRED (unexecuted) | `--ds=config.settings.test_pg` |
| Phase 29 services/selectors | any production caller | ORPHANED by design | Callers arrive in Phases 30-33 (see ROADMAP); not a gap |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real Data | Status |
|----------|------|--------|-----------|--------|
| `get_shop_credit_balance` | allocated/bonus/consumed | `ShopCreditBalance` row, else `Shop.organisation.monthly_credit_allocation` | Yes | FLOWING |
| `annotate_credit_state` | `credit_*` annotations | LEFT JOIN on balances + Coalesce on org allocation | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Credits suite on SQLite | `pytest apps/credits` | all pass (3 pg tests skipped with reason) | PASS |
| Credits suite on real PG14 | `pytest --ds=config.settings.test_pg apps/credits` (throwaway local cluster) | all 126 pass | PASS |
| `pg_concurrency` tests on PG14 with `REQUIRE_PG=1` | `pytest --ds=config.settings.test_pg -m pg_concurrency` | 3 passed, 0 skipped | PASS |
| Migrations in sync | `makemigrations --check --dry-run` | No changes detected | PASS |
| Typecheck | `mypy apps/credits` | no issues in 26 files | PASS |
| Coverage | `pytest apps/credits --cov=apps/credits` | 99.04% | PASS |
| WR-01 reproduction | hand-built pk instance `.save()` | row rewritten to -99 / COMMITTED, no exception | FAIL (gap) |
| WR-02 reproduction | `bulk_create(update_conflicts=True)` | row rewritten to -77 / COMMITTED, no exception | FAIL (gap) |

### Probe Execution

No `probe-*.sh` scripts declared or present. Step 7c: SKIPPED.

### Requirements Coverage

All five phase IDs appear in the PLAN frontmatter and in REQUIREMENTS.md; no orphaned Phase 29 requirements.

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| CRED-02 | 29-01 (+29-02 constraints) | SATISFIED | Lazy per-month balance, DB uniqueness and CHECKs, tests on SQLite + PG |
| CRED-03 | 29-02 | PARTIAL | Append-only ledger, status CAS, read-only admin, all in place; "no update/delete path exists" falsified by WR-01/WR-02 (gap above) |
| CRED-04 | 29-03 | SATISFIED | Single pure `credit_cost`, settings tiers, full boundary set |
| CRED-05 | 29-03 | SATISFIED | Virtual balance, never writes, full-allocation fallback, 1-query list annotation |
| CQA-01 | 29-01, 29-02 | SATISFIED for Phase 29 scope, CI run pending | Job + marker + first-use race test (and CAS race test) exist and pass on local PG14. REQUIREMENTS.md already notes that the N-threads-vs-K-credits test (CCON-02, Phase 30) and reaper-vs-late-commit test (CREN-03, Phase 31) are added later, but the CQA-01 checkbox is already `[x]`. Consider keeping it tracked until those two tests land. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/credits/models.py` | ~195-200 | `_state.adding` save without `force_insert`; dead positional-args branch (IN-01) | Warning | WR-01 gap |
| `apps/credits/managers.py` | 15-25 | `bulk_create` unguarded | Warning | WR-02 gap |
| `apps/credits/selectors/balances.py`, `services/allocation.py` | 68-79, 37-47 | Past-period fallback invents a balance; `ensure_balance(period=past)` writes retroactive INITIAL (WR-03); allocation read outside the atomic block (IN-04) | Info | Out of must-have scope |
| `apps/credits/services/credit_cost.py` | 38 | Uncovered fallback branch for malformed tiers; no runtime tier validation (IN-03) | Info | Config-only risk |
| all phase files | - | TBD/FIXME/XXX/TODO/HACK | none found | - |

Review disposition file lists all 9 findings as `open`; none triaged. The warnings above should be moved to fixed/deferred explicitly.

### Human Verification Required

#### 1. First GitHub Actions run of `backend-pg`

**Test:** Push the branch and open or update the PR; watch the `backend-pg` job on `postgres:16-alpine`.
**Expected:** 3 `pg_concurrency` tests pass, 0 skipped, job green; `backend-test` (SQLite, 85% gate) and the other jobs still green.
**Why human:** The workflow cannot run locally and has never executed. Everything that is checkable locally (same 3 tests plus the full credits suite on PG14, REQUIRE_PG exit behaviour, marker registration) passed. What remains unproven is the GitHub-side wiring and PG16 itself.

### Gaps Summary

One gap, low blast radius but a genuine contradiction of CRED-03 / SC2 as written: the append-only guard has two ORM bypasses (WR-01 hand-built pk `save()`, WR-02 `bulk_create(update_conflicts=True)`), both reproduced and both untested. They are not reachable from any Phase 29 caller and DB CHECK constraints still bound the damage, so this is a warning-level gap, not a design failure. D-05's acceptance of ORM-level-only enforcement covers raw SQL / non-ORM writers, not these. Fix is roughly 10 lines and 2 tests (see `gaps.missing`). Everything else in the phase goal is substantiated by code and tests: lazy single-row balance with INITIAL + audit, DB-enforced balance invariants, status-only CAS, read-only admin, never-writing selectors with the full-allocation fallback, the single pure pricing function, and the Postgres concurrency tests (locally verified on PG14). The remaining item (first real CI run on PG16) is routed to human verification and will be the post-push check. Because gaps_found takes precedence over human_needed in the decision tree, the human item is carried in the frontmatter so it is not lost.

---

_Verified: 2026-11-11_
_Verifier: Claude (gsd-verifier)_
