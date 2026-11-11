# Phase 30: Metered AI Reply Generation - Context

**Gathered:** 2026-11-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the existing Phase 19/20 `POST /api/v1/reviews/{id}/generate-reply/` metered by shop credits.

Flow:
1. Empty-comment 400 and 402 gates run before any reservation.
2. Reserve: a short row-locked transaction.
3. The OpenAI call runs outside any transaction.
4. Settle: commit or refund through the Phase 29 CAS (`ledger.transition_status`).

Also in scope:
- AuditLog rows for consumed and refunded credits.
- Each consumption row links to the AiUsageLog row of its call.
- `credits_charged` / `credits_remaining` in responses.
- A `credit-cost` endpoint.
- A reply-path-only OpenAI timeout.
- A Postgres concurrency test proving no overspend.
- CQA-02: update the existing tests and factories, plus a deploy note.

Requirements: CCON-01..08, CQA-02.

**Not in this phase:**
- The reaper and lapse Beat jobs (Phase 31). This phase only sets the TTL setting the reaper will use.
- Superadmin allocation and bonus UI (Phase 32).
- Composer UI, Buy More modal, badges (Phase 33).
- Shops-list Staff scoping (SCOPE-01, Phase 33).

</domain>

<decisions>
## Implementation Decisions

### Already closed upstream (do not re-litigate)
- The orchestrator is `generate_reply_with_credits` in `apps/reviews/services/reply_generation.py`.
  - `apps/credits` never imports `apps/reviews`. The orchestrator passes plain IDs and ints.
- View order: auth/scope → tone validation → throttle → empty-comment 400 → reserve.
  - 402 and 400 responses are mapped before the `except Exception → 502` catch-all.
- Settlement is a CAS on `status=RESERVED`, addressed through `tx.shop_credit_balance_id`. It reuses Phase 29's `transition_status` (only RESERVED→COMMITTED and RESERVED→REFUNDED are allowed).
- `consumed_credits` only ever moves via `F()`. Consumption `credits_delta` is negative.
- Refund on an OpenAI failure or an input-moderation block. Consume on success or an output-moderation block.
- `ContentModeratedException` gains optional `stage` and `usage_log_id` kwargs, set at both raise sites in `apps/integrations/openai/guardrails.py` (~L292 input, ~L338 output). Enrichment is unaffected.
- `generate_reply_draft` becomes a thin wrapper over `_generate_reply_draft_with_log -> (draft, usage_log_id)`. Still exactly one AiUsageLog row per request.
- Generate-reply throttle stays at **10/min** (`DEFAULT_THROTTLE_RATES["generate_reply"]`).
- Cost comes from trimmed `Review.comment` via Phase 29 `credit_cost()`, where 0 means "not chargeable".
- `ensure_balance()` (Phase 29) creates the current-month row lazily before reserving.
- A mandatory `ai-enrichment-specialist` review is required (CLAUDE.md §27).

### Late commit & disconnect
- **D-01:** If the commit CAS finds the reservation is no longer RESERVED (the reaper refunded it because the call outlived the TTL, or any other race):
  - Return the draft to the user anyway.
  - Try **one** conditional re-deduct: a new COMMITTED CONSUMPTION row plus an `F()` increment, guarded by the balance CHECK.
  - If the shop now lacks credits, the draft is free.
  - Either way, write an AuditLog row (e.g. `shop.credits.late_commit` with the outcome) and a Sentry warning. Log no review text.
- **D-02:** A CAS miss for any other reason uses the **same** late-commit path. There is one code path for "settle lost the race", and never a 500.
- **D-03:** Client disconnect or abort does not change settlement. Settlement runs server-side after the OpenAI call returns, regardless of the client connection:
  - success or output-moderation block → consume
  - failure or input-moderation block → refund

  Do not try to detect a disconnect under Daphne. Settlement must sit in a code path that runs even if the response can't be delivered (e.g. a `try/finally` around the call in the service, not in the view's response construction).
- **D-04:** An unexpected exception (the view's generic `except Exception → 502`) **refunds** the reservation, the same as an OpenAI failure.

### Timeout & TTL
- **D-05:** The reply-path OpenAI client uses `timeout=30` seconds and `max_retries=1`, through `_get_client().with_options(...)` on the reply path only. The shared client defaults used by enrichment are untouched.
  - Values come from new settings `REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS=30` and `REVIEWBEE_REPLY_OPENAI_MAX_RETRIES=1`.
  - Verify that LangSmith tracing still wraps the `with_options` client.
- **D-06:** `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5` (the setting already exists from Phase 29; confirm or set this value). A settings test asserts `TTL_seconds >= 2 × timeout × (max_retries + 1)`.
- **D-07:** Guarding against the OpenAI call running inside a transaction: raise a real `RuntimeError` if `connection.in_atomic_block` is true at the call site, not a bare `assert` (which `-O` strips). Tests cover it.

### Error & response contract
- **D-08:** 402 `reason` is:
  - `not_enabled` when the current month's `allocated + bonus == 0`, the same as `CreditBalanceView.is_enabled == False`
  - `exhausted` when the total is above 0 but `remaining < cost`

  The body is `{code: "insufficient_credits", reason, required, remaining}`. No reservation is created.
- **D-09:** Success body: `{draft, credits_charged, credits_remaining}`. Error bodies also carry credit fields, and the existing `code` / `detail` keys are unchanged:

  | Response | `credits_charged` | `credits_remaining` |
  |---|---|---|
  | 422 output-moderation block | cost | current |
  | 422 input-moderation block | 0 | current |
  | 502 (any failure, refunded) | 0 | current |

  Update the drf-spectacular `OpenApiResponse` schemas for 200/400/402/409/422/502.
- **D-10:** Cost endpoint: `GET /api/v1/reviews/{id}/credit-cost/` as an `@action` on `ReviewViewSet`.
  - It reuses the same review scoping as generate (`self.get_object()`, which includes Staff scope).
  - It is throttled, with its own scope or a reuse of `review_reply`, at Claude's discretion.
  - It returns `{cost, remaining, is_enabled}` using Phase 29's `credit_cost` and `get_shop_credit_balance`.
  - It never writes. Whitespace-only reviews return `cost: 0`.

### Regenerate & double-click
- **D-11:** Every generate request charges, including a tone switch or a same-tone regenerate. There is no free-retry window.
- **D-12:** Duplicate in-flight guard. Inside the reserve transaction, after locking the balance row, check whether a `RESERVED` CONSUMPTION transaction already exists for this `review_id`.
  - If one does, return **409** `{code: "generation_in_progress"}` with no charge and no reservation.
  - The balance-row lock serialises concurrent requests for the same shop, so the check is race-free.
  - A stale RESERVED row clears when Phase 31's reaper refunds it after the TTL.
  - Whether to also back it with a DB partial unique index (`UNIQUE(review) WHERE type=CONSUMPTION AND status=RESERVED`) is left to the planner/researcher. It would be a new credits migration in this phase.
  - The view order becomes: … → empty-comment 400 → 402/409 at reserve.
- **D-13:** CQA-02 deploy note: a short runbook at `docs/sre/v0.9-credits-rollout.md`, linked from the PR description. It covers:
  - Organisations start at 0 credits, so AI replies return 402 `not_enabled`.
  - How to set `monthly_credit_allocation` through Django admin or the shell until Phase 32 ships the Superadmin control.
  - Verification steps.

### Claude's Discretion
- Exact service-function names and split in `apps/credits/services/consumption.py` (reserve / commit / refund / late re-deduct) and exception classes (`InsufficientCreditsError`, `EmptyCommentError`, `GenerationInProgressError`).
- The `credit-cost` throttle scope.
- The partial unique index backing D-12, as described above.
- The AuditLog action name and payload for the late-commit outcome (no PII or review text).
- How existing Phase 19/20 tests get credits: an explicit allocation in factories or fixtures; the org factory default stays 0.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec & requirements
- `docs/in-progress/Requirements_Credits_System.md`: the binding spec (consumption flow, 402 semantics, moderation split).
- `.planning/REQUIREMENTS.md`: CCON-01..08 and CQA-02, plus the binding reconciliations on line 7.
- `.planning/ROADMAP.md` § "Phase 30: Metered AI Reply Generation": success criteria, notes, research flags.
- `.planning/PROJECT.md` § "Key v0.9 decisions"

### Phase 29 (dependency, being executed in parallel)
- `.planning/phases/29-credits-ledger-foundation/29-CONTEXT.md`: ledger semantics D-01..D-14 (CAS transitions, negative deltas, the `ai_usage_log`/`review`/`actor` FKs already in the schema, `CreditBalanceView`, `credit_cost` returning 0).
- `.planning/phases/29-credits-ledger-foundation/29-RESEARCH.md` and `29-0{1,2,3}-PLAN.md`: the exact symbols Phase 30 consumes (`ensure_balance`, `transition_status`/`cas_status`, `get_shop_credit_balance`, `credit_cost`, the `pg_concurrency` harness).

### Milestone research
- `.planning/research/SUMMARY.md`: cross-cutting items #2 (timeout vs TTL), #3 (moderation stage and usage-log plumbing), #8 (rollout).
- `.planning/research/PITFALLS.md`: double refund, late commit, month boundary, exception ordering.
- `.planning/research/ARCHITECTURE.md`: orchestrator placement, dependency direction.

### Project conventions
- `CLAUDE.md` §5 (thin views/services), §6.11–6.12 (atomic, `select_for_update`), §8 (DRF errors, throttling), §14 (OpenAI, AiUsageLog, one call per request), §16 (tests), §22 (no review text in logs), §27 (`ai-enrichment-specialist`, `tenant-security-auditor`, `orm-performance-auditor`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/reviews/views.py::ReviewViewSet.generate_reply` (~L380–460): the existing flow and exception ladder.
  - `ContentModeratedException` maps to 422 `content_moderated`.
  - Transient and permanent errors map to 502 `ai_unavailable`.
  - `APIException` is re-raised.
  - A generic `Exception` maps to 502.
  - Throttle scope is set in `get_throttles` (WR-02).
- `apps/reviews/services/reply_generation.py::generate_reply_draft` (L84) and `_write_failure_log` (L56): the one-AiUsageLog-per-call contract, and input moderation outside any atomic block.
- `apps/integrations/openai/guardrails.py`: the `raise ContentModeratedException` sites at ~L292 (input) and ~L338 (output), plus `_persist_moderated_log`.
- `apps/integrations/openai/client.py::_get_client` (L50): the shared client, which has no explicit timeout (SDK default 600s).
- `config/settings/base.py` (~L417): `generate_reply: 10/minute`, `review_reply: 30/minute`.

### Established Patterns
- The 422 body never leaks LLM categories or review text (T-20-LK). The new credit fields must not change that.
- Phase 29 `pg_concurrency` tests: `django_db(transaction=True)`, `threading.Barrier`, `connections.close_all()` in `finally`, `REQUIRE_PG` guard. The N-threads-vs-K-credits test goes in the same `backend-pg` job.

### Integration Points
- Credits services (Phase 29): `allocation.ensure_balance`, `ledger.transition_status`, `selectors.balances.get_shop_credit_balance`, `services.credit_cost.credit_cost`.
- The `CreditTransaction.ai_usage_log` FK (SET_NULL), set on commit.

</code_context>

<specifics>
## Specific Ideas

- Test matrix (from research):
  - input-block refund
  - output-block commit with usage-log link
  - OpenAI failure refund
  - unexpected exception refund
  - success
  - late commit with and without re-deduct capacity
  - 409 duplicate in-flight
  - 402 `not_enabled` vs `exhausted`
  - 400 whitespace-only
  - exactly one AiUsageLog row per request in every branch
- Postgres race: N threads against K credits; exactly K/cost succeed and the rest get 402. Balance invariant `consumed <= allocated + bonus` holds, and the ledger reconciles via Phase 29's `assert_ledger_reconciles`.

</specifics>

<deferred>
## Deferred Ideas

- An Idempotency-Key header for generate (a more robust dedupe than D-12). Revisit if mobile clients retry aggressively.
- A free regenerate window. Rejected for now (leaks spend).

</deferred>

---

*Phase: 30-metered-ai-reply-generation*
*Context gathered: 2026-11-11*
