---
phase: 30-metered-ai-reply-generation
plan: 04
subsystem: testing
tags: [postgres, concurrency, credits, pytest, runbook, sre, auditor-review]

requires:
  - phase: 30-metered-ai-reply-generation
    provides: "reserve_credits / commit_reservation / refund_reservation (30-01), reply OpenAI timeouts (30-02), generate_reply_with_credits + 400/402/409 ladder + credit-cost (30-03)"
provides:
  - "Postgres race tests proving no overspend for N threads vs K credits (cost 2 and 3, mixed refunds), one reservation per review, exactly-once settlement, and settlement after a client abort"
  - "docs/sre/v0.9-credits-rollout.md: CQA-02 runbook (orgs start at 0, enable, verify, stranded-reservation and late_commit procedures)"
  - "Recorded ai-enrichment-specialist, tenant-security-auditor and orm-performance-auditor findings with dispositions, and green local gates"
affects: [31-reaper-lapse, 32-superadmin-allocation, 33-composer-ui]

actuals:
  tokens: 10000
  tasks: 3
  commits: 3
plan_head_before: 7107154ca95915b199929b4f75175962b5861e5a
plan_head_after: b1338c4cd4935ef50c822e5d3accd4269fc389fd

tech-stack:
  added: []
  patterns:
    - "pg_concurrency harness: Barrier + results/errors/Lock, connections.close_all() in finally, bounded join with an is_alive deadlock assertion"
    - "Seam patched once outside the threads (process-global) with a short sleep to widen the race window"
    - "Client-abort probe: sync_to_async inside ThreadSensitiveContext, cancel the awaiting task, wait on a finished Event"

key-files:
  created:
    - apps/reviews/tests/test_pg_reply_concurrency.py
    - docs/sre/v0.9-credits-rollout.md
  modified:
    - apps/credits/tests/test_pg_concurrency.py
    - docs/sre/README.md
    - .planning/phases/30-metered-ai-reply-generation/30-VALIDATION.md

key-decisions:
  - "No production code changed: every race passed on the first run and on two repeats, so no defect fix was needed"
  - "The mixed-failure test asserts the refunded set equals the set of ReplyUnavailableError reviews rather than 'every odd review is 502', because an odd review can legitimately lose the reserve race and get 402 first"
  - "README runbook row placed after the incidents row (1 added line, 0 deleted)"

patterns-established:
  - "Every generate race ends with assert_ledger_reconciles on the shop balance"

requirements-completed: [CCON-02, CQA-02]

coverage:
  - id: D1
    description: "On PostgreSQL, 12 threads vs 10 credits at cost 2 produce exactly 5 successes and 7 exhausted; consumed 10; 5 COMMITTED rows; 5 consumed AuditLog rows; ledger reconciles"
    requirement: "CCON-02"
    verification:
      - kind: pg_concurrency
        ref: "apps/reviews/tests/test_pg_reply_concurrency.py#test_generate_never_overspends_when_n_threads_race_for_k_credits"
        status: pass
    human_judgment: false
  - id: D2
    description: "Cost-3 boundary: 3 successes, consumed 9, remaining 1"
    requirement: "CCON-02"
    verification:
      - kind: pg_concurrency
        ref: "apps/reviews/tests/test_pg_reply_concurrency.py#test_generate_leaves_one_credit_when_n_threads_race_with_cost_three"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mixed failures: every refund is a REFUNDED row surfaced as ReplyUnavailableError, consumed equals 2 x COMMITTED rows, never above allocated + bonus, no RESERVED left"
    requirement: "CCON-02"
    verification:
      - kind: pg_concurrency
        ref: "apps/reviews/tests/test_pg_reply_concurrency.py#test_refunded_failures_free_credits_when_mixed_threads_race"
        status: pass
    human_judgment: false
  - id: D4
    description: "8 threads on one review: 1 success, 7 GenerationInProgressError, one CONSUMPTION row (D-12 without a unique index)"
    requirement: "CCON-02"
    verification:
      - kind: pg_concurrency
        ref: "apps/reviews/tests/test_pg_reply_concurrency.py#test_generate_yields_one_success_when_n_threads_race_on_same_review"
        status: pass
    human_judgment: false
  - id: D5
    description: "Credits-level races: reserve N vs K, same review, first use (one balance + one INITIAL_ALLOCATION), commit vs refund charges exactly once"
    requirement: "CCON-02"
    verification:
      - kind: pg_concurrency
        ref: "apps/credits/tests/test_pg_concurrency.py#test_reserve_*, test_first_use_reserve_*, test_charges_once_when_commit_and_refund_race"
        status: pass
    human_judgment: false
  - id: D6
    description: "Client abort mid-draft: the worker thread completes, the reservation ends COMMITTED, one shop.credits.consumed row (D-03)"
    requirement: "CCON-02"
    verification:
      - kind: pg_concurrency
        ref: "apps/reviews/tests/test_pg_reply_concurrency.py#test_settles_when_client_aborts_mid_generation"
        status: pass
    human_judgment: false
  - id: D7
    description: "Runbook states orgs start at 0 (402 not_enabled), how to enable until Phase 32, verification steps, interim 402/409 UI behaviour, stranded-RESERVED procedure, timeouts and late_commit meaning; no secrets or review text; linked from the SRE index"
    requirement: "CQA-02"
    verification:
      - kind: command
        ref: "grep checks on docs/sre/v0.9-credits-rollout.md and docs/sre/README.md (see Self-Check)"
        status: pass
    human_judgment: true
    rationale: "Operator accuracy of the shell procedures (admin path, compose command) needs a human run against production; the CI backend-pg run on PG16 and a UAT generate are manual post-push items"
---

# Phase 30 Plan 04: Postgres Races, Rollout Runbook and Phase Gate Summary

**Real-PostgreSQL proof that concurrent AI-reply generation never overspends a shop's credits and that a client abort still settles, plus the CQA-02 rollout runbook and the Phase 30 auditor/gate record.**

## Performance

- **Duration:** about 25 min
- **Tasks:** 3 of 3
- **Files:** 2 created, 3 modified

## Accomplishments

- 4 credits-level and 5 reviews-level `pg_concurrency` tests added; 12 pg_concurrency tests pass in total (3 from Phase 29), stable over 3 consecutive runs. On SQLite all 12 report skipped.
- All threads join within their timeout (an `is_alive` assertion turns a deadlock into a failure), so the reserve lock order and the settle CAS do not deadlock.
- Runbook `docs/sre/v0.9-credits-rollout.md` delivered and linked from `docs/sre/README.md`.
- Auditor reviews and every local gate recorded below.

## Task Commits

1. **Task 1: Postgres race tests** - `72152d2` (test)
2. **Task 2: Rollout runbook + SRE index row** - `8aafd29` (docs)
3. **Task 3: Phase gate, VALIDATION sign-off** - `b1338c4` (docs)

## Verification Results (real output)

- Throwaway PostgreSQL **14.20** (Homebrew, local; CI uses 16): `REQUIRE_PG=1 pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs` gives **12 passed, 0 skipped** (run four times, all green). Cluster stopped with `pg_ctl stop`, temp dir deleted, no postgres process left.
- SQLite: the two pg files report 12 skipped, 0 failed.
- Full suite `pytest --cov=apps --cov-fail-under=85 -q`: coverage **89.39%** (required 85%), green. `pytest apps/ -q -o addopts=""`: **1439 passed, 14 skipped**. `consumption.py` 97%, `reply_generation.py` 97%.
- `mypy .`: no issues in 333 files. `ruff check .` and `ruff format --check .`: clean.
- `makemigrations --check --dry-run`: no changes; `ls apps/credits/migrations/*.py | wc -l` = 2 (no new migration). `check --deploy` (test settings): warnings only (21 issues, W-level, no errors).
- `spectacular --validate`: no warning or error names a Phase 30 operation or serializer.
- Invariant guard (credits production code imports nothing from `apps.reviews`): 0.
- Not run: CI `backend-pg` on PG16 (needs push) and a UAT generate against an enabled org (needs a running app). Both remain manual per 30-VALIDATION.md.

## Auditor Reviews

The Agent tool was not available to this executor, so each subagent checklist was walked inline against the code.

### ai-enrichment-specialist

| Finding | Disposition |
|---|---|
| One OpenAI chat call per generate request; orchestrator calls the seam once, the SDK retry is internal | OK |
| Exactly one `AiUsageLog` row per request (SUCCESS, FAILED, or MODERATED written by guardrails); the commit/refund links that row | OK |
| `@traceable(name="generate_reply")` still wraps the reply call; LangSmith remains best-effort | OK |
| Enrichment untouched: `git diff` of enrichment.py, parser.py, prompts.py over the phase is empty | OK |
| No review text logged at INFO or above in the new code. Pre-existing `ai.moderation.errored` logs `error=` from the OpenAI client at ERROR level (Phase 20) | Accepted: out of this phase's scope; no review text is passed in |
| Reply path timeout 30 s, 1 retry, moderation bounded (CCON-08) keeps the worst case under the 5-minute TTL | OK, documented in the runbook |

### tenant-security-auditor

| Finding | Disposition |
|---|---|
| `generate_reply` and `credit_cost` both call `self.get_object()` on the scoped queryset (org filter plus Staff `get_accessible_shop_ids`); shop and org for credits come from that Review row | OK |
| No cross-tenant read through credit-cost: 404 for out-of-scope reviews, nothing written | OK |
| `IsOrgScoped` permission on the viewset; both endpoints throttled on their own scopes | OK |
| 402 body exposes `reason/required/remaining` of the caller's own shop only; 422/502 bodies carry canonical text plus credit ints, no review text, categories or exception detail | OK |
| `actor_id` is the authenticated user; audit payloads hold ids and ints only | OK |
| `reserve_credits` trusts the `shop_id` supplied by the orchestrator (no re-check against the org) | Accepted: it is an internal primitive whose only caller derives the id from the scoped Review; documented in 30-01 |

### orm-performance-auditor

| Finding | Disposition |
|---|---|
| Balance lock is `select_for_update(of=("self",))` over `.values()`, no `select_related` | OK |
| Guarded `F()` updates in reserve, refund and late-commit all set `updated_at` | OK |
| D-12 `exists()` filters on status RESERVED and is served by the partial `credit_tx_reserved_idx` (status, created_at) plus the review FK index | OK |
| Fixed query-count tests exist for generate (ceiling 21, identical for cost 1 and 3) and credit-cost (independent of review count) | OK |
| No new migration | OK |

No blockers found, so no production code changed in this plan.

## Deviations from Plan

### Auto-fixed Issues

None for production code. One test-design adjustment:

**1. [Rule 1 - Test correctness] Mixed-failure assertion relaxed from "every odd review is 502"**
- **Found during:** Task 1 (design, before first run)
- **Issue:** With 12 threads and 10 credits, an odd-pk review can lose the reserve race and legitimately get 402 before it ever reaches the failing draft seam; a strict "all odd -> ReplyUnavailableError" would be flaky.
- **Fix:** Assert that the set of `ReplyUnavailableError` reviews equals the set of REFUNDED rows, that all of them are odd, and that the only error classes are `ReplyUnavailableError` and `InsufficientCreditsError`; the money invariants (consumed = 2 x COMMITTED, never above allocation, no RESERVED left, reconciles) are unchanged.
- **Files modified:** apps/reviews/tests/test_pg_reply_concurrency.py
- **Commit:** 72152d2

**Total deviations:** 1 (test-design). **Impact:** none on the proof; the invariants asserted are the same.

## Known Stubs

None.

## Threat Flags

None. No new endpoints, auth paths or schema.

## Issues Encountered

None. Docker was unavailable as expected; the local `.venv` and a throwaway PostgreSQL 14 were used.

## Next Phase Readiness

- Phase 31 (reaper/lapse) can reuse `refund_reservation`; the runbook's manual procedure is the interim for stranded RESERVED rows.
- Manual after push: confirm CI `backend-pg` ran the 12 tests with none skipped, and run a UAT generate for an org enabled per the runbook.

## Self-Check: PASSED

- Files exist: `apps/reviews/tests/test_pg_reply_concurrency.py`, `docs/sre/v0.9-credits-rollout.md`.
- Commits reachable: `72152d2`, `8aafd29`, `b1338c4`.
- Acceptance greps: pg_concurrency marker count 5, assert_ledger_reconciles 6, ThreadSensitiveContext 3, reserve_credits in credits pg file 5; runbook mentions monthly_credit_allocation, not_enabled, credit-cost, refund_reservation, late_commit; README diff 1 added / 0 deleted; credential-shaped strings 0.
