---
phase: 30-metered-ai-reply-generation
reviewed: 2026-11-11T00:00:00Z
depth: standard
files_reviewed: 12
diff_base: 555aba2d6a90e9c6bb72bfd7688c53e23e4aff40
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-11-11 · **Depth:** standard · **Files Reviewed:** 12 · **Status:** issues_found

Files: apps/credits/{exceptions,managers,models}.py, apps/credits/services/{consumption,ledger}.py, apps/integrations/openai/{client,exceptions,guardrails}.py, apps/reviews/services/reply_generation.py, apps/reviews/views.py, config/settings/base.py, docs/sre/v0.9-credits-rollout.md.

## Summary

Money core is sound: reserve is row-locked + guarded `F()` UPDATE (no overspend); commit/refund are single-winner status CAS (no double refund); the OpenAI call runs outside any atomic block (`ATOMIC_REQUESTS` unset; `_assert_no_open_transaction` is a real raise); settlement is in `finally` and `_settle` swallows only `Exception`, so a `BaseException` still settles then propagates. The 400/402/409/422/502 contract is consistent, credit fields are read after settlement, and the new endpoint has a throttle, tenant-scoped `get_object`, no N+1 and no writes. No BLOCKERs; weaknesses are in settlement-failure reporting, a double-call path in the OpenAI client, a timeout invariant only the defaults satisfy, and a month-boundary gap in the one-reservation-per-review guard.

## Warnings

### WR-01: Failed commit/settle reported as "charged 0" while credits stay held
**File:** `apps/reviews/services/reply_generation.py:276-305, 380-396`; `apps/credits/services/consumption.py:206-231, 358-375`
**Issue:** `_settle` swallows every `Exception` and returns `None`, which the caller turns into `credits_charged = 0`. If `commit_reservation` fails after OpenAI billed (e.g. the `shop.credits.consumed` AuditLog insert fails and rolls back the CAS), the row stays RESERVED and the credits stay deducted, yet the user gets 200 with `credits_charged: 0`. In `_settle_lost_race`, a failure of the trailing `AuditLog.objects.create` after a successful re-deduction also reports 0. Until Phase 31's reaper exists, a stranded RESERVED row holds credits and blocks the review with 409. No Sentry signal beyond `logger.exception`, no settle retry.
**Fix:** Retry the settle once; on persistent failure `sentry_sdk.capture_message("credits.settle_failed ...", level="error")`; when `settle is None` and commit was intended, report `reservation.credits` as charged (held) and flag it; wrap the trailing AuditLog/Sentry in `_settle_lost_race` in try/except.

### WR-02: LangSmith fallback can call OpenAI a second time (double billing) and escapes the timeout budget
**File:** `apps/integrations/openai/client.py:410-423` (`_do_chat_completions_create` at :310)
**Issue:** Only `RateLimitError`, `APIStatusError`, `APIConnectionError` are mapped; any other exception (e.g. `openai.APIResponseValidationError`, or a bug in the `@traceable` wrapper) reaches the generic `except Exception` at :417 and triggers a second full chat call — after a possibly successful first call, so OpenAI bills twice while only one `AiUsageLog` row and one credit charge result. The second call is outside the 190 s budget asserted by `test_whole_request_budget_fits_inside_reservation_ttl` (real worst case ≈ 260 s).
**Fix:** Make the mapper exhaustive (`except openai.OpenAIError as exc: raise _map_openai_error(exc) from exc`); make the fallback conditional on a LangSmith-specific failure and skip it once a response exists.

### WR-03: TTL/timeout invariant only enforced for default values
**File:** `config/settings/base.py:240-244` (tested in `apps/credits/tests/test_settings.py`)
**Issue:** `REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS` / `_MAX_RETRIES` are env-overridable but only the test environment's values are asserted; production could set 120 s and nothing fails, so requests outlive the 5-min reservation TTL and Phase 31's reaper would refund slow calls at scale. 0/negative accepted. httpx int timeouts apply per phase, so the true ceiling is higher than the formula.
**Fix:** Validate at startup (system check or `ImproperlyConfigured` in `base.py`) that `0 < T <= 60`, `0 <= R <= 2` and the worst-case budget ≤ TTL.

### WR-04: One-RESERVED-per-review guard leaks at a UTC month boundary
**File:** `apps/credits/services/consumption.py:129-142`
**Issue:** The in-flight `.exists()` check is race-free only because requests for a shop share one `ShopCreditBalance` row lock. Requests straddling month turnover lock different balance rows, so both can pass the check and both reserve — a narrow double-charge path with no DB backstop.
**Fix:** Partial unique constraint `UniqueConstraint(fields=["review"], condition=Q(transaction_type="CONSUMPTION", status="RESERVED"), name="credit_tx_one_reserved_per_review")`; map the `IntegrityError` to `GenerationInProgressError`.

### WR-05: Unmetered `generate_reply_draft` remains a public entry point
**File:** `apps/reviews/services/reply_generation.py:271-273`
**Issue:** No production caller remains (only stale comments), but it is public, calls OpenAI and writes `AiUsageLog` with no reservation — a future task/bulk caller would silently bypass metering. Dead code per CLAUDE.md surgical-scope rule.
**Fix:** Remove it or make it private and document `generate_reply_with_credits` as the only entry point; update tests that import it.

## Info

### IN-01: `credit_cost` throttle (120/min) can be exceeded by the UI's own usage
**File:** `config/settings/base.py:426-428`, `apps/reviews/views.py:588-613` — one per visible review × `max_page_size` 100 + refresh can 429. **Fix:** call lazily on composer open, or annotate cost/remaining on the list serializer, or raise the rate.

### IN-02: Runbook understates 409 duration and worst-case budget
**File:** `docs/sre/v0.9-credits-rollout.md:31-34, 88-91` — 409 lasts the whole in-flight duration (up to ~3 min degraded), the ~190 s figure omits WR-02/httpx per-phase, and the Cloud Run reference conflicts with the EC2/docker-compose deploy described elsewhere. **Fix:** correct the wording; make the proxy-timeout check (research A1) a go-live checklist item.

### IN-03: Runbook operator snippets have gaps
**File:** `docs/sre/v0.9-credits-rollout.md:46-51, 99-110` — shell `update(monthly_credit_allocation=...)` writes no AuditLog; stranded-reservation query hard-codes `minutes=5`. **Fix:** read `settings.REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES`; note manual change-log entry until Phase 32.

### IN-04: Stale docstrings and duplicated except branch
**File:** `apps/reviews/services/reply_generation.py:3-6, 20-21, 198-207`; `apps/reviews/views.py:119` — docstrings still describe `generate_reply_draft`/view-level 502 mapping; two byte-identical except branches in `_generate_reply_draft_with_log`. **Fix:** collapse to one `except Exception`; update docstrings/comments.

### IN-05: `CreditTransaction.save` breaks a positional `force_insert`
**File:** `apps/credits/models.py:193-198` — `obj.save(True)` raises `TypeError: got multiple values`. **Fix:** pop `force_insert` / reject positional args explicitly.

_Reviewer: gsd-code-reviewer (standard depth); persisted by orchestrator because the reviewer harness could not write report files._
