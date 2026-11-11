---
phase: 30-metered-ai-reply-generation
verified: 2026-11-11T14:10:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - .planning/phases/30-metered-ai-reply-generation/30-01-PLAN.md
  - .planning/phases/30-metered-ai-reply-generation/30-01-SUMMARY.md
  - .planning/phases/30-metered-ai-reply-generation/30-02-PLAN.md
  - .planning/phases/30-metered-ai-reply-generation/30-02-SUMMARY.md
  - .planning/phases/30-metered-ai-reply-generation/30-03-PLAN.md
  - .planning/phases/30-metered-ai-reply-generation/30-03-SUMMARY.md
  - .planning/phases/30-metered-ai-reply-generation/30-04-PLAN.md
  - .planning/phases/30-metered-ai-reply-generation/30-04-SUMMARY.md
  - apps/credits/exceptions.py
  - apps/credits/managers.py
  - apps/credits/services/consumption.py
  - apps/credits/services/ledger.py
  - apps/credits/tests/test_pg_concurrency.py
  - apps/integrations/openai/client.py
  - apps/integrations/openai/exceptions.py
  - apps/integrations/openai/guardrails.py
  - apps/reviews/services/reply_generation.py
  - apps/reviews/tests/test_pg_reply_concurrency.py
  - apps/reviews/views.py
  - config/settings/base.py
  - docs/sre/v0.9-credits-rollout.md
covered_digest: "v4:sha256:d3c6c874986afd72d6f7b16937515c28222cf4d66a108b498b6fbe66b3aff4b9"
behavior_unverified: 0
overrides_applied: 0
advisory:
  - finding: "WR-02: OpenAI client LangSmith fallback can issue a second billed chat call for a non-mapped SDK exception (reproduced with a mocked client: APIResponseValidationError -> 2 create calls). Reachable only under SDK strict response validation (not enabled) or an SDK-internal bug; credit accounting stays one charge per request."
    category: other
    reason: "Latent platform-cost leak and timeout-budget escape, not a credit mis-charge. Fix: make the mapper exhaustive (except openai.OpenAIError) and skip the fallback once a response exists. Track as T-30-09."
    evidence_status: "reproduced"
  - finding: "WR-01: settle failure after OpenAI billed is reported as credits_charged=0 while the row stays RESERVED (credits held, review 409s) until Phase 31's reaper."
    category: other
    reason: "This is the planned behaviour (30-03 must-have: failing settle is logged, does not mask the outcome, leaves RESERVED for the reaper) and the runbook documents the manual refund procedure. Narrow misreport exists only if the trailing AuditLog write in _settle_lost_race fails after a successful re-deduct."
    evidence_status: "code read"
  - finding: "WR-04: one-RESERVED-per-review guard serialises on the balance row; two requests straddling a UTC month boundary lock different balance rows and can both reserve for one review."
    category: other
    reason: "Each reservation is independently paid from its own balance under the row lock and CHECK constraint, and each triggers its own OpenAI call; no overspend and no uncharged call. D-12 / 30-04 explicitly chose no partial unique index. Optional hardening: partial unique index on (review) WHERE CONSUMPTION AND RESERVED, map IntegrityError to 409."
    evidence_status: "code read"
  - finding: "Tenant audit M-1 / T-30-05: sentry_sdk.init in config/settings/base.py does not set include_local_variables=False, so the unexpected-error logger.exception paths can ship frame locals (truncated_comment, draft) to Sentry."
    category: security
    reason: "Pre-existing project-wide configuration (Phase 10); Phase 30 adds one more emission point. Not a Phase 30 must-have: the 30-03 prohibition covers Sentry messages, which carry ids/ints only. Conflicts with the spirit of CLAUDE.md section 22 (review text is PII), so a one-line fix (include_local_variables=False) is recommended before any org is enabled in production."
    evidence_status: "config read"
human_verification:
  - test: "Run CI job backend-pg on postgres:16 (push the branch)"
    expected: "All 12 pg_concurrency tests pass with 0 skipped under REQUIRE_PG=1"
    why_human: "Branch is unpushed. Verifier re-ran the 12 tests on a throwaway PostgreSQL 14 cluster: 12 passed, 0 skipped, cluster deleted. PG16 behaviour is unconfirmed."
  - test: "UAT: generate a reply for an enabled org (allocation > 0) in the running app; check the response credit fields, the COMMITTED ledger row linked to its AiUsageLog row, the shop.credits.consumed AuditLog row, and credit-cost returns the same cost"
    expected: "200 with credits_charged / credits_remaining; one ledger row linked to one AiUsageLog row; credit-cost cost equals credits_charged"
    why_human: "Needs a running app with a live OpenAI key; Docker is unresponsive locally."
  - test: "Go-live check: reverse-proxy / platform request timeout vs worst-case generate duration (research A1, review IN-02)"
    expected: "Proxy timeout is not below the 190 s worst case documented for a generate request"
    why_human: "Infrastructure outside the repo."
---

# Phase 30: Metered AI Reply Generation Verification Report

**Phase Goal:** Generating an AI reply draft spends the shop's credits safely. Credits are charged once when OpenAI bills and refunded when it does not. The shop is never overspent under concurrency, and a request that can't be paid for gets a clear 402 or 400 before any OpenAI spend.
**Verified:** 2026-11-11
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Org Admin / in-scope Staff generate is charged the review cost; response carries `credits_charged` and `credits_remaining`; cost endpoint returns the same cost | VERIFIED | `generate_reply_with_credits` (reply_generation.py) reserves via `reserve_credits`, settles in `finally`, reads remaining after settlement; view returns `{draft, credits_charged, credits_remaining}`. `credit_cost` action uses the same `compute_credit_cost(review.comment)` as the orchestrator's `credit_cost(review.comment)`. Tests in test_views.py / test_reply_generation_credits.py pass (353 passed, 12 PG skipped on SQLite). Scope via `get_object()` over scoped queryset. |
| 2 | 402 with `reason` / `required` / `remaining` and no reservation; empty or whitespace comment returns 400 before any reservation | VERIFIED | `reserve_credits` does a read-only `get_shop_credit_balance` pre-check before `ensure_balance` (raises `InsufficientCreditsError` not_enabled / exhausted, no writes). `EmptyCommentError` raised when cost == 0, before reserve. View maps both before the catch-all 502. No-write SQL-capture tests pass. |
| 3 | On Postgres N concurrent generates against K credits never spend more than K; consumed <= allocated + bonus holds | VERIFIED (re-run) | Reserve = `select_for_update` on balance row + guarded `F()` UPDATE + DB CHECK `credit_balance_no_overspend`. Verifier ran the 12 `pg_concurrency` tests on a throwaway PostgreSQL 14 cluster with `REQUIRE_PG=1`: 12 passed, 0 skipped (cluster stopped and deleted). PG16 CI run pending (human item). |
| 4 | Success and output-moderation blocks consume; OpenAI failures and input-moderation blocks refund; one consumed/refunded AuditLog row and one AiUsageLog row per settled request, linked to the ledger row | VERIFIED | Orchestrator default is refund; only success or `exc.stage == "output"` sets `commit=True`; settle in `finally` (BaseException still settles). `commit_reservation` / `refund_reservation` are single-winner status CAS carrying `ai_usage_log_id` in the same UPDATE; one AuditLog row inside the same atomic. Outcome-matrix, one-AiUsageLog-per-branch and late-commit tests pass. |
| 5 | Reply-path OpenAI timeout well below TTL (settings test); throttle still 10/min; existing Phase 19/20 tests pass with credits; deploy note says orgs start at 0 | VERIFIED | `_get_reply_client()` = `with_options(timeout=30, max_retries=1)`; moderation calls pass timeout + `REPLY_MODERATION_MAX_RETRIES=0`; `test_settings.py` budget/margin/throttle tests pass; `DEFAULT_THROTTLE_RATES["generate_reply"] == "10/minute"`. Runbook `docs/sre/v0.9-credits-rollout.md` states organisations start at 0 and get 402 `not_enabled`; indexed in `docs/sre/README.md`. Residual: margin is only tested on default values (WR-03, advisory). |

**Score:** 5/5 roadmap truths verified (0 present-but-behavior-unverified). Plan-level must-haves from 30-01..30-04 were also spot-checked against code and tests; none failed.

### Review-gate findings (30-REVIEW.md / 30-SECURITY.md)

| Finding | Classification | Violates a must-have / success criterion? |
|---------|----------------|-------------------------------------------|
| WR-02 LangSmith fallback second billed call | Advisory (reproduced) | No. Reproduced: a mocked first call raising `openai.APIResponseValidationError` (not an `APIStatusError` or `APIConnectionError`) yields 2 `chat.completions.create` calls. The 30-02 must-have is narrower (timeout / connection errors map to one call) and holds. The SDK raises this error only in strict-validation mode (`_strict_response_validation`, not enabled anywhere in the repo); the non-strict path uses tolerant `construct_type`. Credit accounting is still one charge per request, so the shop is not mis-charged; the platform would absorb an extra OpenAI bill and the call escapes the 190 s budget. Pre-dates Phase 30 (Phase 19 fallback). |
| WR-01 settle failure shows `credits_charged=0` | Advisory | No. The 30-03 must-have explicitly specifies this behaviour. The row is left RESERVED (credits held, review returns 409), which biases toward the user and is recoverable via the runbook's manual `refund_reservation` procedure and Phase 31's reaper. |
| WR-04 month-boundary double-reserve | Advisory | No. Each reservation is paid under its own balance's row lock and CHECK, and each makes its own OpenAI call, so nothing is overspent and nothing is free. D-12 deliberately avoided a partial unique index. |
| M-1 Sentry `include_local_variables` default | Advisory | No (not a must-have). Prohibition 30-03 covers bodies, AuditLog payloads, log lines and Sentry messages, all of which carry ids/ints only. It is a pre-existing config weakness against CLAUDE.md section 22, now with one more emission point; recommend closing before production enablement. |
| WR-03 TTL/timeout invariant only tested on defaults | Advisory | No. Success criterion 5 asks for a settings test enforcing the margin; it exists and passes. |
| WR-05 unmetered `generate_reply_draft` public | Advisory | No production caller; dead-code hygiene. |

No finding fails a must-have or a success criterion, so none is a gap.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `apps/credits/services/consumption.py` | VERIFIED | reserve / commit / refund / late-commit; imported and called by reply_generation.py |
| `apps/credits/exceptions.py`, `managers.py`, `services/ledger.py` | VERIFIED | `GenerationInProgressError`, `InsufficientCreditsError`, CAS with `ai_usage_log_id` |
| `apps/reviews/services/reply_generation.py` | VERIFIED | orchestrator, `EmptyCommentError`, `ReplyModeratedError`, `ReplyUnavailableError`, no-open-transaction guard (real raise) |
| `apps/integrations/openai/{client,guardrails,exceptions}.py` | VERIFIED | bounded reply client, `stage` + `usage_log_id` on moderation exception, `with_options` only when args given |
| `apps/reviews/views.py` | VERIFIED | 400/402/409/422/502 ladder before catch-all; `credit-cost` action with own throttle scope |
| `config/settings/base.py` | VERIFIED | timeout/retries settings, `credit_cost` 120/min, `generate_reply` 10/min |
| `docs/sre/v0.9-credits-rollout.md` + README row | VERIFIED | CQA-02 deploy note |
| pg_concurrency test files | VERIFIED | 12 tests, pass on PostgreSQL 14 |

### Key Link Verification

| From | To | Status |
|------|----|--------|
| `ReviewViewSet.generate_reply` | `generate_reply_with_credits` | WIRED |
| `generate_reply_with_credits` | `reserve_credits` / `commit_reservation` / `refund_reservation` (settle in `finally`) | WIRED |
| `commit_reservation` / `refund_reservation` | `transition_status` CAS carrying `ai_usage_log_id` | WIRED |
| `reserve_credits` | `get_shop_credit_balance` read-only pre-check before `ensure_balance` | WIRED |
| `_do_chat_completions_create` | `_get_reply_client()` | WIRED |
| `ReviewViewSet.get_throttles` | `credit_cost` / `generate_reply` scopes | WIRED |

### Behavioral Spot-Checks and Test Evidence

| Check | Result |
|-------|--------|
| `pytest apps/credits apps/integrations/openai apps/reviews/tests/{test_reply_generation_credits,test_reply_generation_service,test_views,test_pg_reply_concurrency}.py` (SQLite) | 353 passed, 12 skipped (the PG-only tests) |
| `pytest --ds=config.settings.test_pg -m pg_concurrency` on throwaway PostgreSQL 14, `REQUIRE_PG=1` | 12 passed, 0 skipped; cluster stopped and removed |
| WR-02 reproduction (throwaway script, deleted) | 2 `create` calls for one `APIResponseValidationError` |
| `ruff check` on touched sources | clean |
| `makemigrations --check --dry-run` | no changes |
| Debt markers (TBD/FIXME/XXX) in phase source files | none |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| CCON-01 | 30-01 | SATISFIED | Reserve -> OpenAI outside transaction -> commit; scoped `get_object()` |
| CCON-02 | 30-01, 30-04 | SATISFIED (PG14; PG16 CI pending) | Row lock + guarded UPDATE + CHECK; 12 PG tests pass |
| CCON-03 | 30-01, 30-03 | SATISFIED | 402 body `{code, reason, required, remaining}`, no write |
| CCON-04 | 30-03 | SATISFIED | 400 `empty_comment` before reserve |
| CCON-05 | 30-01, 30-02, 30-03 | SATISFIED | Outcome matrix; one AuditLog row per settlement |
| CCON-06 | 30-01, 30-02, 30-03 | SATISFIED | `ai_usage_log_id` linked in the status CAS |
| CCON-07 | 30-01, 30-03 | SATISFIED | Credit fields in 200/422/502; `credit-cost` endpoint |
| CCON-08 | 30-02, 30-03 | SATISFIED | 30 s / 1 retry reply client, 10/min throttle unchanged |
| CQA-02 | 30-01, 30-03, 30-04 | SATISFIED | Phase 19/20 tests updated and passing; rollout runbook |

All nine requirement IDs appear in plan frontmatter and are marked complete in REQUIREMENTS.md. No orphaned Phase 30 requirements.

### Anti-Patterns Found

None blocking. Informational items are the review's IN-01..IN-05 (documentation / hygiene) and the advisory findings above.

### Human Verification Required

1. **CI `backend-pg` on postgres:16.** Push the branch and confirm 12 `pg_concurrency` tests pass with 0 skipped. Verifier's PG14 re-run passed.
2. **UAT generate on an enabled org** in the running app: response credit fields, linked ledger and AiUsageLog rows, consumed AuditLog row, credit-cost parity. Needs a running app and a live OpenAI key.
3. **Go-live proxy timeout check** against the documented worst-case request duration (infrastructure).

### Gaps Summary

No gaps. Every roadmap success criterion and requirement is satisfied in code and in passing tests, and CCON-02 was independently re-proven on a real PostgreSQL cluster. Status is `human_needed` only because PG16 CI and the live UAT cannot be run here. Four advisory findings are recorded; recommended before production enablement are the one-line Sentry `include_local_variables=False` and the exhaustive OpenAI error mapping (WR-02).

---

_Verified: 2026-11-11_
_Verifier: Claude (gsd-verifier)_
