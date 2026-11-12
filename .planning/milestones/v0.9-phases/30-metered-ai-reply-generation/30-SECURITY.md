---
phase: "30"
slug: "metered-ai-reply-generation"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-11"
---

# Phase 30 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| client → generate-reply / credit-cost | Untrusted caller; shop and organisation come only from the scoped Review row, never request data | review id, tone choice |
| request thread → shop balance row | Concurrent requests for one shop compete for the same credits | credit counters |
| settle → append-only ledger | Status CAS is the only allowed mutation; D-14 adds one linked column (`ai_usage_log_id`) | ledger status, usage-log FK |
| service → AuditLog / logs / Sentry | Review text is PII and must not leave the request | ids, counts, reason codes |
| app → OpenAI chat / moderation APIs | Network calls whose latency must stay below the reservation TTL | review text (to OpenAI) |
| guardrails → callers | Moderation exception crosses into reviews and enrichment layers | stage, usage-log id |
| environment → settings | Env overrides can change the timeout and retries | config ints |
| client connection → server settlement | A client abort must not change what is charged | — |
| server → HTTP error bodies | Moderation outcome details must not leak | credit ints, error codes |
| OpenAI call → DB transactions | The network call must not run while a row lock is held | — |
| operators → production shell | Runbook procedures act on live credit data | allocation, ledger rows |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-30-01 | Tampering | `reserve_credits` overspend under concurrency | high | mitigate | `select_for_update` on balance + guarded `F()` UPDATE + CHECK `credit_balance_no_overspend` (`services/consumption.py`); 12-thread PG race test (30-04) | closed |
| T-30-02 | Tampering | Double refund / refund after commit | high | mitigate | Every balance change gated by a won RESERVED CAS in the same atomic (`refund_reservation`); double-refund tests | closed |
| T-30-03 | Elevation of privilege | Staff generating on an out-of-scope shop | high | mitigate | `get_object()` over Staff-scoped `get_queryset` (`apps/reviews/views.py`); out-of-scope 404 test asserts zero balance/ledger rows; confirmed by tenant-security-auditor | closed |
| T-30-04 | Tampering | 402 path materialising zero-allocation rows | medium | mitigate | Read-only `get_shop_credit_balance` pre-check before `ensure_balance` (D-19); no-write SQL capture test | closed |
| T-30-05 | Information disclosure | Review text / draft in audit payloads, logs, Sentry | medium | mitigate | Payloads/messages carry ids + ints only (tested). **Gap (tenant audit M-1):** sentry_sdk 2.58.0 defaults `include_local_variables=True` and `config/settings/base.py:585` does not disable it; `logger.exception` on the unexpected-error path (`reply_generation.py:374-379`, `views.py:547`) ships frame locals (`truncated_comment`, `draft`) the denylist does not scrub. Pre-existing via the view handler; Phase 30 adds a second emission point | open — below high threshold (non-blocking) |
| T-30-06 | Tampering | D-14 widening the ledger's mutable surface | medium | mitigate | `ai_usage_log_id` written only inside the status CAS UPDATE (`managers.py cas_status`); `save()` status-only; append-only + source-scan tests | closed |
| T-30-07 | Tampering | Late commit charging twice or across months | high | mitigate | Re-read status; only REFUNDED re-deducts, current month, no LAPSED, guarded `F()`; `already_settled` never charges (D-16 tests) | closed |
| T-30-08 | Denial of service | Hung chat/moderation call past the 5-min TTL | medium | mitigate | Reply chat 30 s / 1 retry; moderation 30 s / 0 retries, passed on both moderate_* calls; budget test. Residual: LangSmith fallback second call is outside the budget (review WR-02) | closed |
| T-30-09 | Repudiation | Untraced second billed OpenAI call | medium | mitigate | `APIConnectionError`/`APITimeoutError` mapped to `OpenAITransientError`. **Gap (review WR-02):** mapper is not exhaustive — e.g. `APIResponseValidationError` still reaches the generic fallback and triggers a second billed call | open — below high threshold (non-blocking) |
| T-30-10 | Information disclosure | Moderation categories/review text on the exception | medium | mitigate | Exception carries only stage + int id; test asserts no category name | closed |
| T-30-11 | Tampering | Env override widening the timeout beyond the TTL | low | mitigate | Settings tests assert the margin. **Gap (review WR-03):** only the test-environment values are checked; a production env override is never validated | open — below high threshold (non-blocking) |
| T-30-12 | Repudiation | Free generation by aborting / forcing an exception after OpenAI billed | high | mitigate | Settlement in service `finally` (D-03); `_settle` catches `Exception` only so `BaseException` still settles; output block consumes; KeyboardInterrupt and client-abort PG tests | closed |
| T-30-13 | Information disclosure | 422/502 bodies leaking categories or review text | medium | mitigate | Only two int credit fields added; key-set + no-category/no-comment assertions on every error body; confirmed by tenant-security-auditor | closed |
| T-30-14 | Information disclosure | Cross-tenant / out-of-scope Staff reading a balance via credit-cost | high | mitigate | `get_object()` over scoped queryset; cross-tenant, out-of-scope Staff and Superadmin tests; confirmed by tenant-security-auditor (no HIGH) | closed |
| T-30-15 | Denial of service | credit-cost polled to load the DB | low | mitigate | Own `ScopedRateThrottle` scope `credit_cost` 120/min; fixed query ceiling | closed |
| T-30-16 | Tampering | Charging when OpenAI did not bill | high | mitigate | Refund is the default outcome; only success or certain output-stage block commits; matrix tests | closed |
| T-30-17 | Denial of service | OpenAI call inside a transaction holding the balance lock | medium | mitigate | Reserve commits before the call; `_assert_no_open_transaction` raises `RuntimeError` inside any non-test atomic block (`reply_generation.py:150-157`) | closed |
| T-30-18 | Tampering | Overspend / double settlement only under real concurrency | high | mitigate | 12 `pg_concurrency` tests on PostgreSQL 14 (N vs K, costs 2/3, mixed failures, same review, commit vs refund, first use, client abort); `REQUIRE_PG` makes a skip fail. CI on PG16 pending (human item) | closed |
| T-30-19 | Denial of service | Stranded RESERVED rows before Phase 31's reaper | medium | mitigate | Runbook query + manual `refund_reservation` procedure (`docs/sre/v0.9-credits-rollout.md`) | closed |
| T-30-20 | Information disclosure | Runbook leaking secrets or review text | low | mitigate | Ids-only examples; credential-shape grep | closed |
| T-30-21 | Elevation of privilege | Tenant/Staff scoping regression slipping past review | high | mitigate | Real `tenant-security-auditor` run 2026-11-11 (no HIGH; M-1 → T-30-05; L-1 review/shop org mismatch reachable only via inconsistent data; L-2 test gaps); scope tests from 30-01/30-03 in the full suite | closed |
| T-30-SC | Tampering | npm/pip/cargo installs | low | accept | No packages installed in this phase | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-30-01 | T-30-SC | No new dependencies installed | plan-time decision | 2026-11-11 |

Open non-blocking items (not accepted — tracked for follow-up): T-30-05 (Sentry frame locals, tenant audit M-1), T-30-09 (non-exhaustive OpenAI error mapping, review WR-02), T-30-11 (prod env override unvalidated, review WR-03). Tenant audit LOW items: L-1 (authorise on `Review.organisation_id` but bill `Review.shop_id` — add `shop__organisation_id` filter), L-2 (missing tests: credit-cost no-write assertions, REGION-scoped Staff, soft-deleted review, mismatched review/shop org).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-11 | 22 | 19 | 3 (all below high; threats_open: 0) | secure-phase orchestrator (ASVS L1 grep) + tenant-security-auditor agent + gsd-code-reviewer cross-check |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (no open threat at or above `high`)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-11 (3 medium/low threats remain open below the blocking threshold)
