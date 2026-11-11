---
phase: 31-monthly-renewal-reservation-reaper
verified: 2026-11-11T15:00:00Z
status: human_needed
score: 4/4 roadmap success criteria verified (plus all plan must-have truths)
covered_files:
  - .planning/phases/31-monthly-renewal-reservation-reaper/31-01-PLAN.md
  - .planning/phases/31-monthly-renewal-reservation-reaper/31-01-SUMMARY.md
  - .planning/phases/31-monthly-renewal-reservation-reaper/31-02-PLAN.md
  - .planning/phases/31-monthly-renewal-reservation-reaper/31-02-SUMMARY.md
  - .planning/phases/31-monthly-renewal-reservation-reaper/31-03-PLAN.md
  - .planning/phases/31-monthly-renewal-reservation-reaper/31-03-SUMMARY.md
  - apps/credits/migrations/0002_shopcreditbalance_lapsed_at.py
  - apps/credits/migrations/0003_beat_credit_lapse.py
  - apps/credits/migrations/0004_beat_credit_reaper.py
  - apps/credits/models.py
  - apps/credits/selectors/lapse.py
  - apps/credits/selectors/reservations.py
  - apps/credits/services/consumption.py
  - apps/credits/services/lapse.py
  - apps/credits/services/reaper.py
  - apps/credits/tasks.py
  - config/settings/base.py
  - docs/sre/v0.9-credits-rollout.md
covered_digest: "v4:sha256:6e65203b95b26197429d5a88e75b1d364740573e0cd48fb680effc2841d41841"
behavior_unverified: 0
overrides_applied: 0
gaps: []
advisory:
  - finding: "WR-01 / T-31-05 residual: reserve_credits lock-query/UPDATE and _settle_lost_race re-deduct UPDATE do not guard on lapsed_at IS NULL. Reproduced under a forced interleaving (see body): consumed_credits rises on a lapsed balance and its ledger sums to -credits instead of 0."
    category: other
    reason: "Needs a UTC month flip inside a microsecond gap plus a lapse of that same balance committing in it (reaper D-08 re-lapse or a manual sweep; the scheduled 00:05 sweep cannot land in it). No must-have or success criterion asserts the property. One-predicate fix recommended."
    evidence_status: "reproduced deterministically (forced interleaving), probability negligible, customer impact nil"
  - finding: "WR-03: REVIEWBEE_CREDIT_REAPER_BATCH_SIZE / REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE unvalidated (0 silently disables, negative crashes)."
    category: other
    reason: "Operator misconfiguration only; defaults are 500 and no must-have covers invalid env. Matches the repo-wide unvalidated env.int convention."
    evidence_status: "code reading: settings/base.py:242-245"
  - finding: "WR-02 / T-31-14: oldest-first reaper selection can be starved by >= batch-size poison RESERVED rows."
    category: other
    reason: "Accepted at plan time (AR-31-02). Poison means consumed_credits < reservation credits, an invariant the DB CHECK and refund CAS make practically unreachable; needs >= 500 such rows."
    evidence_status: "code reading: selectors/reservations.py:46-47, services/reaper.py:76-84"
  - finding: "No loop-level query-count test for reap_stale_reservations / lapse_past_balances."
    category: other
    reason: "Plan truths require selection-level and per-balance fixed ceilings, and those exist and pass. Per-row queries in the loops are bounded by design (one atomic per row, batch capped at 500)."
    evidence_status: "test_lapse.py:306,328; test_reaper.py:354"
human_verification:
  - test: "Push the branch and confirm CI job backend-pg on postgres:16 is green"
    expected: "gh run view shows backend-pg with >= 16 pg_concurrency tests passed and 0 skipped"
    why_human: "Branch is unpushed. I re-ran the suite on a throwaway PostgreSQL 14.20 cluster (2 runs, 16 passed, 0 skipped, REQUIRE_PG=1) but PG16 in CI has not run."
  - test: "After deploy, run migrate, restart Celery Beat, open Django admin Periodic tasks"
    expected: "credits_lapse_expired_balances (crontab 00:05, UTC, queue default, enabled) and credits_reap_stale_reservations (every 10 minutes, queue default, enabled) are listed and fire"
    why_human: "Needs a running Beat; the seed migrations and routing are verified statically and in tests only"
  - test: "Deployment owner configures the 'lapse not complete by 00:30 UTC' alert"
    expected: "Alert exists and fires when past-period unlapsed balances remain after 00:30 UTC on the 1st"
    why_human: "Infra outside this repo; handed off in docs/sre/v0.9-credits-rollout.md (T-31-20, transferred)"
---

# Phase 31: Monthly Renewal & Reservation Reaper Verification Report

**Phase Goal:** Credits renew cleanly every month, and no credit is stranded by an abandoned request. Unused credits lapse on schedule (self-healing after a missed run) and stale reservations are returned automatically.
**Verified:** 2026-11-11
**Status:** human_needed (no gaps; three known deployment/CI human items)
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | At 00:05 UTC every past-month unlapsed balance gets one LAPSED row and one `shop.credits.lapsed` AuditLog row; re-run adds nothing; missed months all lapse | VERIFIED | `services/lapse.py:lapse_balance` writes LAPSED (`-remaining`, COMMITTED, actor None) + AuditLog + `lapsed_at` marker inside one atomic under `select_for_update(skip_locked)`, past-period and `lapsed_at IS NULL` predicates in the locked query. `lapse_past_balances` keyset-pages (`pk > after_pk`) over all past periods (no lookback cap). Migration 0003 seeds crontab minute 5 hour 0, UTC, queue default; route in `base.py:137`. Zero-remaining: marker only. `test_lapse.py` (idempotence, 1/2/13-month catch-up, Dec to Jan, inactive shops, per-balance IntegrityError isolation) passes; `credit_tx_one_lapse_per_balance` is a DB backstop. Overlapping-sweeps PG test passed on my PG14 run. |
| 2 | New month starts from the org's current allocation, zero bonus, no carry-over | VERIFIED | No new code by design (Phase 29 `ensure_balance`); `test_renewal.py` proves allocation 10 to 20, bonus 0, one INITIAL row, prior row untouched, allocation 0 stays not enabled, Dec to Jan. Passes. |
| 3 | Every 10 min, RESERVED rows older than TTL are refunded; never twice; never a committed row; proven by Postgres reaper-vs-late-commit test | VERIFIED | `services/reaper.py` selects oldest stale RESERVED CONSUMPTION rows (batch 500) via `selectors/reservations.py` and refunds each through `refund_reservation` (CAS RESERVED to REFUNDED + decrement in one atomic, no outer transaction). Lost CAS returns False and counts as skipped. Migration 0004 seeds interval 10 min, queue default; route `base.py:139`. `test_reaper.py` (TTL boundary, re-run no-op, committed/refunded ignored, commit-wins-after-selection) passes. `test_reaper_and_late_commit_settle_each_reservation_once_when_racing` and `test_overlapping_reapers_...` exist and passed on my throwaway PG14 cluster. |
| 4 | A reservation straddling midnight settles against its original month and that balance lapses only after settlement | VERIFIED | `lapse_balance` re-checks RESERVED rows under the balance lock (`skipped_held`); reaper re-lapses touched past balances (D-08); a late commit on a past-month or lapsed balance is `free_draft`. `test_reaper_settles_straddling_reservation_before_lapse_and_late_commit_is_free` passes; the three-way commit/reaper/sweep PG race test passed on PG14. |

**Score:** 4/4 roadmap truths verified. All plan must-have truths (31-01, 31-02, 31-03) checked against code and tests; none failed. No behavior-dependent truth was left presence-only: each concurrency or ordering invariant has a passing behavioral test (SQLite unit tests, plus `pg_concurrency` tests which I ran myself).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/credits/models.py` + `migrations/0002` | nullable `lapsed_at` + partial index `credit_bal_unlapsed_idx` | VERIFIED | Present; `makemigrations --check` clean |
| `migrations/0003`, `0004` | Beat seeds, reversible, delete only the PeriodicTask by name | VERIFIED | Read; shared crontab/interval never deleted |
| `selectors/lapse.py`, `selectors/reservations.py` | read-only selection, one query each | VERIFIED | Query-count tests pass |
| `services/lapse.py`, `services/reaper.py` | sweep and reaper | VERIFIED | Substantive, wired |
| `services/consumption.py` | late commit honours `lapsed_at` | VERIFIED | `_settle_lost_race` reads `lapsed_at__isnull=False` |
| `tasks.py` | two thin tasks | VERIFIED | Wrappers over services, return JSON-safe dicts |
| `config/settings/base.py` | two settings, two routes | VERIFIED | Lines 137, 139, 242-245 |
| CLAUDE.md section 12.5, runbook | schedules documented, 00:30 alert handed off | VERIFIED | CLAUDE.md:700-701; runbook sections present |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| Beat PeriodicTask rows | tasks | task path + `CELERY_TASK_ROUTES` | WIRED (migrations 0003/0004; `test_tasks.py`) |
| tasks | `lapse_past_balances` / `reap_stale_reservations` | local import in task body | WIRED |
| reaper | `refund_reservation` | direct call, CAS | WIRED |
| reaper | `lapse_balance` | D-08 re-lapse of touched past balances | WIRED |
| `_settle_lost_race` | `lapsed_at` marker | `.exists()` read | WIRED |

### Data-Flow Trace (Level 4)

Backend jobs only, no rendered values. Tenant ids and org/shop attribution in LAPSED and AuditLog rows come from the locked balance row, never arguments (`lapse.py`), and refund rows from the transaction row. A cross-tenant reaper attribution test exists and passes.

### Behavioral Spot-Checks and Probes

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Credits suite | `pytest apps/credits --no-cov` | 215 passed, 11 skipped (PG-only on SQLite) | PASS |
| PG concurrency (my own run, PG 14.20, throwaway cluster, removed afterwards) | `REQUIRE_PG=1 pytest --ds=config.settings.test_pg -m pg_concurrency` x2 | 16 passed, 0 skipped each run | PASS |
| Migrations | `makemigrations --check --dry-run` | No changes detected | PASS |
| Lint / types | `ruff check apps/credits config`; `mypy apps/credits` | clean; no issues in 37 files | PASS |

No `probe-*.sh` scripts are declared for this phase (Step 7c not applicable).

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| CREN-01 | 31-01 (also 31-02, 31-03) | SATISFIED | Truth 1; REQUIREMENTS.md marks Complete |
| CREN-02 | 31-01 | SATISFIED | Truth 2 (`test_renewal.py`) |
| CREN-03 | 31-02 (also 31-03) | SATISFIED | Truths 3 and 4 |

REQUIREMENTS.md maps only CREN-01..03 to Phase 31; no orphaned IDs. CQA-01 is a Phase 29 requirement (status "Gaps Found" there) to which Phase 31 contributed the reaper-vs-late-commit PG test; that test exists and passes. CQA-01 closure remains pending the CI run (human item 1), which is outside Phase 31's own requirement set.

### Anti-Patterns Found

TBD/FIXME/XXX scan over the modified implementation files: none. No stubs, empty returns or hardcoded-empty data in the lapse/reaper paths.

### Review-gate findings: gap vs advisory

**WR-01 (and ORM audit LOW, T-31-05 residual): ADVISORY, not a gap.**
- *Reproduced.* I wrote a throwaway test that forces the interleaving (hooking `transaction.atomic` in `consumption.py` so `lapse_balance` for the next UTC month commits right before the guarded UPDATE), then deleted it. Results:
  - Late-commit path: reservation refunded, then late commit. Outcome `rededucted` on a balance that was just lapsed (`lapsed_at` set, LAPSED row -10). `consumed_credits` ends at 3 and the non-refunded ledger sums to -3 instead of 0.
  - `reserve_credits` path: after `ensure_balance`, a lapse commits, then the reserve proceeds. It writes a RESERVED row and `consumed_credits = 3` on the lapsed balance.
  So the defect is real, not theoretical. The repo's own `assert_ledger_reconciles` (consumed equals live CONSUMPTION rows) would still hold; what breaks is "a lapsed balance is closed and nets to zero".
- *Why not a gap.* (a) No ROADMAP success criterion or plan truth asserts this property. The D-01 truth ("late commit honours the marker") is about a marker already set when read, and it holds. SC4 concerns reservations still RESERVED at lapse time (skipped under the lock); here the reservation was already REFUNDED. (b) Reachability: it needs the month to flip between `current_period()` / `ensure_balance` and the UPDATE and a lapse of that same balance to commit in that gap. The scheduled 00:05 sweep runs 5 minutes after the flip and cannot fall inside a microsecond gap; only a reaper D-08 re-lapse or a manual sweep at the flip instant can, and the late-commit variant additionally needs a request outliving the 5 minute TTL (worst case about 190 s). (c) Impact: the charge lands on a closed month's written-off credits and the new month is untouched, so the shop is not overcharged; the effect is a ledger drift of one draft's cost in a closed month. This matches the plan's accepted T-31-09 straddle risk.
- *Recommendation (cheap, do before Phase 32/33 or in a follow-up).* Add `lapsed_at__isnull=True` to the UPDATE predicate in `_settle_lost_race` (map a miss to `free_draft` / `past_period`) and to the `reserve_credits` UPDATE (map a miss to a retry or `InsufficientCreditsError`), plus a forced-interleaving regression test like the one used here. Keep T-31-05 open until then.

**WR-03: ADVISORY (config hygiene).** A value of 0 for either setting would silently stop reaping or lapsing, which would undermine the "returned automatically" must-have, but only if an operator sets it wrong; the shipped defaults (500) and the seeded schedules work, and no must-have or test covers invalid env input. The repo convention for env-driven sizes is unvalidated `env.int` (for example `SEED_PHASE_SIZE`). Fix with `max(1, ...)` clamps and a settings test when convenient.

**WR-02: ADVISORY (accepted, T-31-14 / AR-31-02).** Starvation needs at least 500 permanently failing rows. A poison row requires `consumed_credits < reservation credits`, which the balance CHECK plus the CAS-and-decrement atomic make practically unreachable. D-09 explicitly wants the repeated Sentry error as visibility, and the runbook documents the procedure. SC3 says stale reservations are refunded; poison rows are deliberately held (never forced) so a lapse is never forced over an unsettled row.

**ORM audit, no loop-level query-count test: ADVISORY.** The plan truths require selection-level ceilings (1 query for 2 and for 5 rows, both present) and a fixed per-balance count for `lapse_balance` (present and passing). The sweep and reaper loops are intentionally one atomic unit per row, bounded by the batch and chunk caps, so a per-row query count is not an N+1 defect. A whole-function ceiling test would be nice-to-have.

### Human Verification Required

1. **backend-pg on PG16.** Push the branch; confirm `backend-pg` is green with at least 16 passed and 0 skipped. Why human: not pushed. Mitigated: I ran the same 16 tests twice on PG 14.20, all passing.
2. **Beat picks up both schedules after deploy.** After migrate and a Beat restart, Django admin Periodic tasks lists both seeded tasks enabled and in UTC. Why human: needs a running Beat.
3. **00:30 UTC lapse alert.** Owned by the deployment owner (runbook handoff, T-31-20 transferred). Why human: infra outside this repo.

### Gaps Summary

No gaps. All four ROADMAP success criteria and all plan must-have truths are backed by code and passing tests, including real-Postgres concurrency proofs that I re-ran myself. Four review-gate items are classified advisory; WR-01 is a reproducible but negligible-probability invariant hole worth a one-predicate hardening fix. Status is `human_needed` only because of the three known CI and deployment items.

---

_Verified: 2026-11-11_
_Verifier: Claude (gsd-verifier)_
