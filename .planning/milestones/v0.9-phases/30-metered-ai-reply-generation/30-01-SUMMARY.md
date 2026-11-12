---
phase: 30-metered-ai-reply-generation
plan: 01
subsystem: api
tags: [django, drf, credits, ledger, openai, reserve-commit-refund, pytest]

requires:
  - phase: 29-credits-ledger-foundation
    provides: "ShopCreditBalance + append-only CreditTransaction, ensure_balance, transition_status CAS, credit_cost, get_shop_credit_balance, assert_ledger_reconciles"
provides:
  - "Status CAS and transition_status that link ai_usage_log_id in the same conditional UPDATE (D-14, D-17)"
  - "apps/credits/services/consumption.py: reserve_credits, commit_reservation, refund_reservation, single late-commit policy"
  - "InsufficientCreditsError(reason, required, remaining) and GenerationInProgressError(review_id)"
  - "generate_reply_with_credits orchestrator (reserve -> OpenAI outside any transaction -> settle in finally) and _generate_reply_draft_with_log -> (draft, usage_log_id)"
  - "generate-reply 200 body {draft, credits_charged, credits_remaining}"
affects: [30-02, 30-03, 30-04, 31-reaper-lapse, 33-composer-ui]

actuals:
  tokens: 13000
  tasks: 2
  commits: 3
plan_head_before: a0c28ccdcedab5e5affaf0970d40393a64d7bcf1
plan_head_after: 31bda0f4953c179567b08ff42689f511079dcf3b

tech-stack:
  added: []
  patterns:
    - "Reserve in a short row-locked transaction (select_for_update of self + guarded F() UPDATE), commit before the network call"
    - "Settle in the service's finally so it survives client disconnect; settle failures are logged and never mask the original outcome"
    - "One late-commit path: re-read status, re-deduct only REFUNDED + current month + no LAPSED + capacity"
    - "Open-transaction guard via connection.atomic_blocks ignoring _from_testcase blocks"

key-files:
  created:
    - apps/credits/services/consumption.py
    - apps/credits/tests/test_consumption.py
  modified:
    - apps/credits/managers.py
    - apps/credits/services/ledger.py
    - apps/credits/exceptions.py
    - apps/credits/tests/test_append_only.py
    - apps/reviews/services/reply_generation.py
    - apps/reviews/views.py
    - apps/reviews/tests/test_views.py

key-decisions:
  - "D-14 implemented as an optional ai_usage_log_id on cas_status/transition_status, written only inside the same conditional UPDATE as the status; save() stays status-only"
  - "No partial unique index or credits migration for D-12; the balance-row lock serialises the in-flight check"
  - "commit_reservation never touches the balance (credits were added at reserve); refund is CAS + guarded decrement in one atomic block and raises RuntimeError (rolling the CAS back) if the decrement cannot apply"
  - "Late commit uses sentry_sdk.capture_message (WARNING log records are only breadcrumbs) with ids only"
  - "The generate query-count ceiling is 21 (measured 19 for both a cost-1 and a cost-3 review); the old <=4 ceiling covered a mocked service that did no credit work"

patterns-established:
  - "Credits services take plain ids/ints and never import apps.reviews (invariant grep stays 0)"
  - "Audit actions: shop.credits.consumed, shop.credits.refunded, shop.credits.late_commit; payloads carry ids and ints only"

requirements-completed: [CCON-01, CCON-02, CCON-03, CCON-05, CCON-06, CQA-02]

coverage:
  - id: D1
    description: "Org Admin and in-scope Staff are charged the review's credit cost end to end; 200 body is {draft, credits_charged, credits_remaining}; the consumption row is COMMITTED and linked to the single AiUsageLog row; one shop.credits.consumed AuditLog row; ledger reconciles"
    requirement: "CCON-01"
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestGenerateReplyCredits"
        status: pass
    human_judgment: false
  - id: D2
    description: "Out-of-scope Staff get 404 with the draft seam never called and zero ShopCreditBalance / CreditTransaction rows written"
    requirement: "CCON-01"
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestGenerateReplyCredits::test_out_of_scope_staff_gets_404_and_nothing_is_written_when_generating"
        status: pass
    human_judgment: false
  - id: D3
    description: "402 pre-check is read-only (not_enabled vs exhausted), exact-capacity boundary succeeds, bonus-only shops are enabled"
    requirement: "CCON-03"
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_consumption.py#test_reserve_*"
        status: pass
    human_judgment: false
  - id: D4
    description: "In-flight guard (GenerationInProgressError) under the balance lock; prior COMMITTED/REFUNDED rows do not block"
    requirement: "CCON-01"
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_consumption.py#test_reserve_raises_in_progress_and_changes_nothing_when_review_has_reserved_row"
        status: pass
    human_judgment: false
  - id: D5
    description: "Refunds settle exactly once (double refund, refund after commit, negative-decrement rollback); a failing OpenAI call is refunded in finally and the original exception reaches the view"
    requirement: "CCON-05"
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_consumption.py#test_refund_*"
        status: pass
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestGenerateReplyCredits::test_openai_failure_is_refunded_and_returns_502_when_generating"
        status: pass
    human_judgment: false
  - id: D6
    description: "Single late-commit path: rededucted / free_draft / already_settled, never a second charge, never a past-month or lapsed charge, always audited with a Sentry warning"
    requirement: "CCON-05"
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_consumption.py#test_late_commit_*"
        status: pass
    human_judgment: false
  - id: D7
    description: "ai_usage_log link written in the same CAS UPDATE on commit and refund; lost CAS leaves FK NULL; save() still rejects the link"
    requirement: "CCON-06"
    verification:
      - kind: unit
        ref: "apps/credits/tests/test_append_only.py#test_transition_links_usage_log_*"
        status: pass
    human_judgment: false
  - id: D8
    description: "Phase 19/20 generate-reply tests re-pointed below the credits layer with explicit allocations, throttle cache cleared, fixed query ceiling identical for cost-1 and cost-3"
    requirement: "CQA-02"
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestGenerateReplyEndpoint"
        status: pass
    human_judgment: false

duration: 28min
completed: 2026-11-11
status: complete
---

# Phase 30 Plan 01: Metered generate-reply tracer Summary

**Reserve (row-locked, guarded F()) -> OpenAI outside any transaction -> commit CAS that links the AiUsageLog row, with refund-in-finally and a single late-commit policy, wired into generate-reply with credits_charged / credits_remaining in the 200 body.**

## Performance

- **Duration:** 28 min
- **Started:** 2026-11-11 (session start)
- **Completed:** 2026-11-11T13:20Z
- **Tasks:** 2 (1 tracer, 1 TDD)
- **Files modified:** 9 (2 created, 7 modified)

## Accomplishments

- Step 0 contract check passed against real code (`CONTRACT_OK`, credits suite green at 127 passed before any edit).
- D-14/D-17: `cas_status` and `transition_status` take an optional `ai_usage_log_id`, written in the same conditional UPDATE as the status. Phase 29's source-scan test and the force_insert / explicit-signature `bulk_create` guard are untouched.
- `consumption.py`: `reserve_credits` (read-only 402 pre-check, then lock, in-flight check, re-check, guarded `F()` UPDATE, RESERVED row), `commit_reservation`, `refund_reservation` (reusable by Phase 31's reaper), and `_settle_lost_race` (D-16).
- `generate_reply_with_credits`: tone check, `credit_cost`, `EmptyCommentError` before reserve, `_assert_no_open_transaction` (real raise, `_from_testcase` aware), settlement in `finally`, never masking the original exception.
- View returns `{draft, credits_charged, credits_remaining}`; OpenAPI schema and example updated.
- Tests: 24 in `test_consumption.py`, 5 link tests in `test_append_only.py`, `TestGenerateReplyCredits` (5 tests incl. the D-07 guard), and the 11 re-pointed `TestGenerateReplyEndpoint` tests.

## Task Commits

1. **Task 1 (tracer): metered generate-reply end to end** - `ba56e41` (feat)
2. **Task 2 RED: failing late-commit and money-edge tests** - `939c137` (test; 5 late-commit tests failed against the Task 1 placeholder)
3. **Task 2 GREEN: single late-commit policy** - `31bda0f` (feat)

Tracer gate: auto-mode / end-of-phase with an automated-only verify, so the tracer's `TestGenerateReplyCredits` suite was re-run (5 passed) before expanding.

## Verification Results (real output)

| Command | Result |
|---|---|
| CONTRACT_OK grep chain (step 0) | `CONTRACT_OK` |
| `.venv/bin/pytest apps/reviews/tests/test_views.py -k TestGenerateReplyCredits` | 5 passed |
| `.venv/bin/pytest apps/credits/tests/test_consumption.py` | 24 passed |
| `.venv/bin/pytest apps/credits apps/reviews/tests/test_views.py apps/reviews/tests/test_reply_generation_service.py` | 222 passed, 3 skipped |
| `.venv/bin/pytest apps/ -q -o addopts=""` (full suite) | **1378 passed, 5 skipped** in 32s |
| `.venv/bin/mypy apps/credits apps/reviews` | Success: no issues found in 75 source files |
| `.venv/bin/ruff check` / `ruff format --check` on apps/credits apps/reviews | All checks passed / 75 files already formatted |
| pre-commit hooks (every commit, no `--no-verify`) | ruff, mypy, bandit, gitleaks, missing-migrations all passed |

Not run: the Postgres N-thread concurrency proof (`pg_concurrency`, skipped here: no local Postgres cluster; Plan 30-04 owns it) and `make test` (Docker unresponsive; used `.venv` directly).

Acceptance greps: `ai_usage_log_id` in managers.py = 4, `ai_usage_log_id=ai_usage_log_id` in ledger.py = 1, `generate_reply_with_credits` def = 1, `_generate_reply_draft_with_log` def = 1, `atomic_blocks` = 1, leading `assert` = 0, view references = 2, old patch target in test_views = 0, reviews imports from non-test credits code = 0, credits migrations = 2 (no new), `cas_status` mentions in consumption.py = 0. Task 2: `capture_message` 2, `shop.credits.late_commit` 2, `get_shop_credit_balance` 2, `late_commit` in tests 17, `assert_ledger_reconciles` in tests 12.

## Query-count baseline

`test_generate_reply_query_count` measured **19 queries** for both a cost-1 and a cost-3 review (identical); ceiling pinned at 21. The previous ceiling of 4 covered a mocked service that did no credits work.

## Deviations from Plan

None - plan executed exactly as written. Two additions inside plan scope: a test for the D-07 open-transaction guard (the plan said "tests cover it" without naming one) and `__all__` on `consumption.py`.

## Decisions Made

- `_settle` returns `None` on a swallowed settle failure and the orchestrator reports `credits_charged=0`, so a settle error is visible in logs (`logger.exception`) but never changes the HTTP outcome. The reservation stays RESERVED for Phase 31's reaper.
- The late-commit audit payload also carries `prior_status`, `reason` (`past_period` / `no_capacity`) and `new_transaction_id`, ids and ints only.
- The 402/409 assumption from the plan holds: the read-only pre-check answers 402 before the lock-scoped 409 check.

## Issues Encountered

None. One ruff `--fix` pass transiently removed the then-unused `sentry_sdk` import in `consumption.py` while the late-commit body was still a placeholder; it was re-added with the GREEN implementation.

## Known Stubs

None. `_settle_lost_race` was a placeholder only between Task 1 and Task 2 and is fully implemented in `31bda0f`.

## Threat Flags

None. No new endpoints or trust boundaries beyond the plan's threat model (T-30-01..07 mitigated at the service layer; the Postgres concurrency proof for T-30-01 is deferred to Plan 30-04 as planned).

## Next Phase Readiness

Plan 30-02 (credit-cost endpoint / timeouts), 30-03 (outcome matrix: moderation stage split, 402/409/422 bodies) and 30-04 (Postgres concurrency, auditors) can build on `reserve_credits` / `commit_reservation` / `refund_reservation`. Plan 30-03 replaces the view's exception ladder and adds the moderation split; until then an output-moderation block refunds (the Task 1 finally treats every exception as a refund).

## Self-Check: PASSED

- Created files present: `apps/credits/services/consumption.py`, `apps/credits/tests/test_consumption.py`.
- Commits `ba56e41`, `939c137`, `31bda0f` are ancestors of HEAD.
