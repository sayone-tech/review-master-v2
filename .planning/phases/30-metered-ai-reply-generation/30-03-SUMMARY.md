---
phase: 30-metered-ai-reply-generation
plan: 03
subsystem: api
tags: [django, drf, credits, ledger, openai, moderation, throttling, drf-spectacular, pytest]

requires:
  - phase: 30-metered-ai-reply-generation
    provides: "Plan 30-01 reserve/commit/refund + orchestrator; Plan 30-02 moderation stage / usage_log_id and bounded reply options"
provides:
  - "generate_reply_with_credits outcome matrix: success and output-stage block consume; input block, OpenAI error, unexpected error, stage-less exception and interruption refund; D-17 AiUsageLog linkage"
  - "ReplyModeratedError / ReplyUnavailableError carrying credits_charged and credits_remaining, built only after settlement"
  - "generate-reply 400 empty_comment, 402 insufficient_credits, 409 generation_in_progress; 422/502 bodies with credit fields"
  - "GET /api/v1/reviews/{id}/credit-cost/ -> {cost, remaining, is_enabled}, read-only, own credit_cost throttle (120/minute)"
  - "moderate_input / moderate_output on the reply path bounded by REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS and REPLY_MODERATION_MAX_RETRIES (D-15 carry-over from 30-02)"
affects: [30-04, 31-reaper-lapse, 33-composer-ui]

actuals:
  tokens: 21000
  tasks: 2
  commits: 4
plan_head_before: ff88e0f15ef3590e8240f916791c5fcb502c1d9c
plan_head_after: 2dc12d0e33c6b96cd9c1bbe02623460866f18c15

tech-stack:
  added: []
  patterns:
    - "Default-refund orchestrator: commit/reason/usage_log_id start as refund/unexpected_error/None and only a success or a certain output-stage block flips to commit"
    - "Wrapper exceptions (ReplyModeratedError / ReplyUnavailableError) built after the finally settles, so credit fields in every body are the settled balance"
    - "FAILED usage-log pk handed back through a private mutable holder so the thin generate_reply_draft wrapper signature is unchanged"
    - "Per-action throttle scope chosen in get_throttles (WR-02) with an aliased import so the credit_cost action does not shadow the pricing function"

key-files:
  created:
    - apps/reviews/tests/test_reply_generation_credits.py
  modified:
    - apps/reviews/services/reply_generation.py
    - apps/reviews/views.py
    - apps/reviews/tests/test_views.py
    - apps/reviews/tests/test_reply_generation_service.py
    - config/settings/base.py

key-decisions:
  - "400 empty_comment and 409 generation_in_progress bodies carry only {code, detail}; 402 is exactly {code, reason, required, remaining} (D-08/D-09 reading, flagged in the plan)"
  - "A moderation exception with stage None or an unknown stage refunds (reason input_moderated); the shop is charged only when the output stage is certain"
  - "The view keeps a generic final clause that also returns 502 with credits_charged 0 and a freshly read credits_remaining, for failures outside the orchestrator's try block"
  - "Log lines in the orchestrator carry review id, transaction id, stage and exception class name only"

patterns-established:
  - "Credit-cost reads go through get_object() over the Staff-scoped queryset, so tenant and StaffAccessScope scoping is shared with generate"

requirements-completed: [CCON-03, CCON-04, CCON-05, CCON-06, CCON-07, CQA-02]

coverage:
  - id: D1
    description: "Outcome matrix: success and output block consume (COMMITTED, linked SUCCESS / MODERATED row, consumed audit outcome); input block, OpenAI transient/permanent, RuntimeError, stage None/unknown and KeyboardInterrupt refund with the right reason and link; one AiUsageLog row per branch; ledger reconciles"
    requirement: "CCON-05"
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_reply_generation_credits.py#TestCommitBranches,TestRefundBranches"
        status: pass
    human_judgment: false
  - id: D2
    description: "Settle failure does not mask the outcome: caller still gets its result, row stays RESERVED, log holds the transaction id and not the comment text"
    requirement: "CCON-05"
    verification:
      - kind: unit
        ref: "apps/reviews/tests/test_reply_generation_credits.py#TestSettleFailure"
        status: pass
    human_judgment: false
  - id: D3
    description: "Transaction guard pinned: no raise under pytest-django's wrapper, RuntimeError in an explicit atomic block (default and transaction=True tests); an orchestrator call inside atomic never reaches the draft seam and refunds"
    requirement: "CCON-06"
    verification:
      - kind: unit
        ref: "apps/reviews/tests/test_reply_generation_credits.py#TestTransactionGuard"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both moderation calls receive timeout 30 and max_retries 0 from the reply path"
    requirement: "CCON-08"
    verification:
      - kind: unit
        ref: "apps/reviews/tests/test_reply_generation_service.py#TestReplyPathModerationBounds"
        status: pass
    human_judgment: false
  - id: D5
    description: "422 bodies keep the byte-exact detail with keys {code, detail, credits_charged, credits_remaining} (cost for output block, 0 for input block) and leak no category or review text; 502 bodies report credits_charged 0 and credits_remaining = allocation"
    requirement: "CQA-02"
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestGenerateReplyEndpoint"
        status: pass
    human_judgment: false
  - id: D6
    description: "400 empty_comment (empty, spaces, tabs, NBSP, ideographic space) writes nothing and never calls the seam; invalid tone wins over empty comment; 402 not_enabled writes no balance row; 402 exhausted; exact-capacity boundary; 409 in progress; regenerate charged twice; superadmin 403; cross-tenant 404"
    requirement: "CCON-03"
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestGenerateReplyEndpoint"
        status: pass
    human_judgment: false
  - id: D7
    description: "credit-cost: Org Admin and in-scope Staff 200 with exact keys, out-of-scope Staff and cross-tenant 404, superadmin 403, whitespace review cost 0, cost equals the following generate's credits_charged, never writes, query count fixed (<= 4) and independent of review count, remaining excludes an in-flight reservation, own throttle scope returns 429 at 1/minute"
    requirement: "CCON-07"
    verification:
      - kind: integration
        ref: "apps/reviews/tests/test_views.py#TestReviewCreditCost"
        status: pass
    human_judgment: false
  - id: D8
    description: "spectacular --validate exits 0 and no warning or error names generate-reply, credit-cost or their serializers"
    requirement: "CCON-07"
    verification:
      - kind: other
        ref: "manage.py spectacular --validate, grep for the operation names returned no match"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-11-11
status: complete
---

# Phase 30 Plan 03: Outcome matrix, payment ladder and credit-cost Summary

**Every generate outcome now settles exactly once in the service `finally` (output block and success consume; input block, OpenAI/unexpected failure and interruption refund) with the MODERATED or FAILED usage-log row linked, unpayable or empty requests stop at 400/402/409 with no writes, and a read-only `credit-cost` endpoint on its own throttle returns the price generate will charge.**

## Accomplishments

- Orchestrator defaults to refund; only a success or a certain `stage == "output"` block commits. `ReplyModeratedError` and `ReplyUnavailableError` are raised after settlement, so `credits_remaining` in every 422/502 body is the settled balance. A failing settle call is logged with ids only and leaves the row RESERVED for the Phase 31 reaper.
- Carry-over from 30-02 done: `moderate_input` and `moderate_output` get `timeout=settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS` and `max_retries=REPLY_MODERATION_MAX_RETRIES`.
- D-17: `_write_failure_log` returns the pk it wrote; a private `_LogHolder` hands it to the orchestrator for the FAILED link.
- View: `EmptyCommentError` -> 400, `InsufficientCreditsError` -> 402 `{code, reason, required, remaining}`, `GenerationInProgressError` -> 409; the old moderation and OpenAI clauses are gone from the view (`grep -c "except ContentModeratedException"` = 0).
- `credit_cost` action, `credit_cost` throttle scope (`120/minute`), and schemas for 400/402/409/422/429/502 and the new operation.

## Task Commits

1. **Task 1 RED:** `e351fa1` (test) - collection ImportError plus 8 failing tests
2. **Task 1 GREEN:** `024825f` (feat)
3. **Task 2 RED:** `251903f` (test) - 17 of 24 selected tests failed
4. **Task 2 GREEN:** `2dc12d0` (feat)

## Verification Results (real output)

| Command | Result |
|---|---|
| `pytest apps/reviews/tests/test_reply_generation_credits.py` | 13 passed |
| `pytest test_reply_generation_service.py test_views.py test_enrichment_service.py apps/integrations/openai apps/credits` | 357 passed, 3 skipped |
| `pytest apps/reviews/tests/test_views.py -k "TestReviewCreditCost or empty_comment or ... or cross"` | 24 passed (plan floor: 16) |
| `pytest apps/reviews apps/credits apps/integrations/openai` | 609 passed, 3 skipped |
| `pytest apps/ -q -o addopts=""` (full suite) | **1439 passed, 5 skipped** (1401 after 30-02) |
| `mypy apps/reviews config` | Success: no issues found in 60 source files |
| `ruff check` / `ruff format --check` on apps/reviews config | All checks passed / formatted (one `ruff format` pass on views.py before the final commit) |
| `manage.py spectacular --file /dev/null --validate` | exit 0 |
| spectacular output grep for generate_reply / credit_cost / credit-cost / GenerateReply / CreditCost / InsufficientCredits / GenerationInProgress | no match |
| pre-commit hooks on every commit (no `--no-verify`) | passed (first RED commit needed one re-stage after ruff-format) |

Acceptance greps: `HTTP_402_PAYMENT_REQUIRED` 1, `url_path="credit-cost"` 1, `throttle_scope = "credit_cost"` 1, `"credit_cost": "120/minute"` 1, `"generate_reply": "10/minute"` 1, `credit_cost as compute_credit_cost` 1, `class TestReviewCreditCost` 1, `REPLY_MODERATION_MAX_RETRIES` in reply_generation.py 3, `content_moderated` in test_views 3, `credits_remaining` in test_views 11, `except ContentModeratedException` in views 0, `class ReplyModeratedError` / `class ReplyUnavailableError` 1 each.

Not run: `make test` (Docker unresponsive; used `.venv`), the Postgres concurrency proof (`pg_concurrency` tests still skipped, owned by Plan 30-04), any real OpenAI or Moderation call (the Moderation transport and the chat call are mocked).

## Deviations from Plan

### Process note

**1. [Process] RED commits were staged after the implementation was first drafted**
- **Found during:** Task 1
- **Issue:** I wrote the implementation before the tests, which inverts the TDD order the plan asked for.
- **Fix:** Before committing anything I saved the drafted production files outside the repo, restored them to HEAD, wrote the tests, ran them red, and committed the RED state. The production code was then re-applied for each GREEN commit (the Task 1 views.py was derived from the final file by removing the Task 2 pieces). The RED commits therefore fail genuinely against the real prior code. No behaviour changed as a result.
- **Commits:** `e351fa1`, `024825f`, `251903f`, `2dc12d0`

Otherwise none: plan executed as written. Code-level deviations: none.

## Decisions Made

- The generic `except Exception` clause stays in the view as a backstop. It now returns the 502 credit fields too, with `credits_remaining` read from the database.
- The two stage-less / unknown-stage tests are parametrized through the seam rather than the real guardrails, since the real guardrails always set a stage.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None. T-30-12..17 are mitigated as planned (settlement in finally, key-set and no-leak assertions on 422/502, cross-tenant / out-of-scope / superadmin tests on credit-cost, own throttle scope with a fixed query ceiling, default-refund matrix, guard plus refund inside atomic).

## Next Phase Readiness

Plan 30-04 can build the Postgres N-thread concurrency proof and run `tenant-security-auditor` and `orm-performance-auditor` against the new surface. Note the generate query ceiling (21) was not changed by this plan; the credit-cost path measures at or under 4 queries.

## Self-Check: PASSED

- Created and modified files present: `test_reply_generation_credits.py`, `reply_generation.py`, `views.py`, `test_views.py`, `test_reply_generation_service.py`, `base.py`.
- Commits `e351fa1`, `024825f`, `251903f`, `2dc12d0` are ancestors of HEAD; `commits: 4` measured from the persisted ledger (base `ff88e0f`).
