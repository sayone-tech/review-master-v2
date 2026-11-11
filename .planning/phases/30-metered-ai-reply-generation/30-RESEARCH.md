# Phase 30: Metered AI Reply Generation - Research

**Researched:** 2026-11-11
**Domain:** Django/DRF two-phase credit consumption (reserve -> OpenAI outside any transaction -> CAS settle) wired into the Phase 19/20 AI reply endpoint
**Confidence:** HIGH on code facts and runtime behaviour (all verified by reading the repo or running probes this session); MEDIUM on three Phase 29 interface items that are mid-execution; LOW only where tagged `[ASSUMED]`

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Already closed upstream (do not re-litigate)**
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

**Late commit & disconnect**
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

**Timeout & TTL**
- **D-05:** The reply-path OpenAI client uses `timeout=30` seconds and `max_retries=1`, through `_get_client().with_options(...)` on the reply path only. The shared client defaults used by enrichment are untouched.
  - Values come from new settings `REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS=30` and `REVIEWBEE_REPLY_OPENAI_MAX_RETRIES=1`.
  - Verify that LangSmith tracing still wraps the `with_options` client.
- **D-06:** `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5` (the setting already exists from Phase 29; confirm or set this value). A settings test asserts `TTL_seconds >= 2 × timeout × (max_retries + 1)`.
- **D-07:** Guarding against the OpenAI call running inside a transaction: raise a real `RuntimeError` if `connection.in_atomic_block` is true at the call site, not a bare `assert` (which `-O` strips). Tests cover it.

**Error & response contract**
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

**Regenerate & double-click**
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

### Deferred Ideas (OUT OF SCOPE)
- An Idempotency-Key header for generate (a more robust dedupe than D-12). Revisit if mobile clients retry aggressively.
- A free regenerate window. Rejected for now (leaks spend).

**Not in this phase (CONTEXT domain):** the reaper and lapse Beat jobs (Phase 31; this phase only sets the TTL setting the reaper will use); Superadmin allocation and bonus UI (Phase 32); Composer UI, Buy More modal, badges (Phase 33); shops-list Staff scoping (SCOPE-01, Phase 33).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CCON-01 | Org Admin / in-scope Staff generating a reply is charged the review's credit cost via reserve -> OpenAI outside any transaction -> commit | Orchestrator skeleton, `reserve_credits` / `commit_reservation` design, `ReviewViewSet.get_queryset` already scopes Staff (views.py L108-L125), transaction guard via `connection.atomic_blocks` (Finding F3) |
| CCON-02 | Concurrent generate requests never spend beyond remaining credits (Postgres test) | Guarded `F()` UPDATE + `select_for_update(of=("self",))` reserve; N-threads-vs-K-credits design in Validation Architecture; harness reuse |
| CCON-03 | 402 `not_enabled`/`exhausted` with `required`, `remaining`, no reservation | Read-only pre-check + re-check under lock; body contract D-08 |
| CCON-04 | 400 for empty/whitespace comment before any reservation | `credit_cost()` returns 0 -> `EmptyCommentError` before `reserve_credits` |
| CCON-05 | Refund on OpenAI failure / input block, consume on output block; AuditLog `shop.credits.consumed` / `refunded` | Moderation `stage` plumbing (F4), try/finally settlement (F5), AuditLog payload table |
| CCON-06 | Each consumption row links to the single AiUsageLog row; exactly one AiUsageLog row per request | **Blocking Phase 29 gap F1:** append-only ledger cannot set `ai_usage_log` after insert; concrete extension specified |
| CCON-07 | Response includes `credits_charged` / `credits_remaining`; cost endpoint | View ladder + `credit-cost` `@action` + throttle scope; schemas |
| CCON-08 | Explicit reply-path timeout well below TTL; 10/min throttle unchanged | `with_options` verified on openai 2.33.0 (F2), worst-case budget arithmetic, margin test |
| CQA-02 | Existing Phase 19/20 generate-reply tests/factories updated; deploy note | Exhaustive affected-test table; minimal fix; runbook outline |
</phase_requirements>

## Summary

Phase 30 is almost entirely integration work on top of Phase 29's primitives, and the three hard problems the roadmap flagged all have clear, verified answers. Client disconnect under Daphne is safe by construction: Django's `ASGIHandler` cancels only the *awaiting* task on `http.disconnect`, while asgiref's `SyncToAsync` shields the executor future, so the sync DRF view body and any `finally` run to completion (proven with a probe that includes `ThreadSensitiveContext`, the exact wrapper Django uses). `with_options` returns a plain `openai.OpenAI` copy with the new timeout/retries; LangSmith tracing in this repo is a `@traceable` decorator around the call function, not a wrapped client, so tracing is unaffected. The reserve/commit/refund design is a small amount of code (`consumption.py`) because commit is a status CAS only (credits were already incremented at reserve) and only refund / late-commit touch the balance.

Research found **five issues that CONTEXT.md does not anticipate** and that the planner must absorb (details in "Key Findings"): (F1) the append-only ledger from Phase 29 makes the "set `ai_usage_log` on commit" requirement impossible as shipped; (F2) an `openai.APITimeoutError` on the reply path is not mapped to our hierarchy and falls into the "LangSmith fallback" branch, which fires a **second, untraced OpenAI call**, and the two moderation calls in the same request still use the 600 s default timeout; (F3) a literal `connection.in_atomic_block` guard raises in every default `@pytest.mark.django_db` test, so it needs the `connection.atomic_blocks` / `_from_testcase` form; (F6) the D-02 "one late-commit path" would double-charge if the row is already COMMITTED; (F7) the shipped React composer aborts and immediately re-requests on tone switch, which will now hit the D-12 409 until the first request settles.

**Primary recommendation:** Build `apps/credits/services/consumption.py` (reserve / commit / refund / late re-deduct, all keyed by plain IDs, settle-by-`transaction_id`), a `generate_reply_with_credits` orchestrator whose settlement lives in a `finally`, and have the orchestrator raise post-settlement wrapper exceptions that carry `credits_charged` / `credits_remaining` so the view ladder stays a thin mapper. Resolve F1 first (ask the Phase 29 executor to add an `ai_usage_log_id` argument to `cas_status`/`transition_status` while 29-02 is still in flight; otherwise make it Plan 30-01 Task 1).

## Key Findings (read these before planning)

| # | Finding | Impact | Tag |
|---|---------|--------|-----|
| F1 | **Phase 29's append-only ledger cannot link `ai_usage_log` after insert.** `CreditTransaction.save()` rejects any `update_fields` other than `{"status"}`; `CreditTransactionQuerySet.update()` raises `AppendOnlyViolation`; `cas_status(self, *, pk: int, from_status: str, to_status: str)` only writes `status`. The reservation row is inserted *before* the OpenAI call, so no usage-log id exists at insert time. CONTEXT says the FK is "set on commit". | CCON-06 is unimplementable without a contract change. | [VERIFIED: apps/credits/managers.py, apps/credits/models.py:189-213 (read this session)] |
| F2 | **Timeout/transport errors take the wrong branch.** `openai.APITimeoutError` MRO is `APITimeoutError -> APIConnectionError -> APIError`; it is neither `RateLimitError` nor `APIStatusError`, so `_map_openai_error` returns it unchanged and `call_openai_reply_generation` falls into `except Exception` ("LangSmith init / shipping failure") and calls `_do_chat_completions_create` **again, untraced**. Also `guardrails._call_moderation_api` uses `_get_client()` (default 600 s read timeout), so input and output moderation are unbounded relative to the 5 min TTL. | Doubles worst-case latency and violates "one OpenAI call"; the D-06 margin is only true for the chat call. | [VERIFIED: client.py reply path, guardrails.py:139-141, runtime MRO probe] |
| F3 | **`connection.in_atomic_block` guard breaks every default `django_db` test** (pytest-django wraps tests in an atomic block, so it is always `True`). Use `any(not getattr(b, "_from_testcase", False) for b in connection.atomic_blocks)`. | Without this, all view tests raise RuntimeError. | [VERIFIED: probe test passed; Django 6.0.2 transaction.py:180-188] |
| F4 | `_persist_moderated_log` returns `None` today; `ContentModeratedException` has only a docstring body. Both raise sites are bare `raise ContentModeratedException("input flagged")` / `("output flagged")`. Enrichment catches the exception at enrichment.py:562 and ignores kwargs, so optional kwargs are safe. | Straightforward plumbing. | [VERIFIED: guardrails.py:292,338; exceptions.py; enrichment.py:559-563] |
| F5 | Client abort: the sync view body and its `finally` complete after the client disconnects, also inside `ThreadSensitiveContext`. | D-03 satisfied by a `try/finally` in the service; no disconnect detection needed. | [VERIFIED: probes + Django asgi.py handle()] |
| F6 | D-02 says every CAS miss uses the late re-deduct path. If the row is already **COMMITTED** (duplicate settle bug), re-deducting charges twice. Only a **REFUNDED** row justifies a re-deduct. | Money-safety refinement of D-02, not a contradiction. | reasoning from D-01/D-02 + ledger semantics |
| F7 | `ReplyComposer.tsx` calls `generateAbortRef.current?.abort()` then fires a new request on every tone click. The server-side request is **not** cancelled (F5), so its RESERVED row exists until it settles and the immediate second request returns 409 `generation_in_progress`. The current composer maps unknown errors to a generic message. | Phase 33 UI must handle 402/409; document in the rollout note that between Phase 30 and 33 the composer shows the generic failure copy. | [VERIFIED: ReplyComposer.tsx:80-123, api.ts:147-161] |
| F8 | Existing view tests `@patch("apps.reviews.views.generate_reply_draft")`; the view will import the orchestrator instead, so every one of those patches breaks (not just 402s). The T-20-LK test asserts `set(resp.json().keys()) == {"code", "detail"}`, which D-09 deliberately changes. | CQA-02 scope is larger than "add an allocation fixture". | [VERIFIED: test_views.py:407-606] |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reserve / commit / refund / late re-deduct (ledger + balance writes) | API / Backend (`apps/credits/services/consumption.py`) | Database (CHECK constraints, row lock) | Credits is a leaf bounded context; DB CHECK `credit_balance_no_overspend` is the last-resort guard |
| Orchestration reserve -> OpenAI -> settle, exception->outcome mapping | API / Backend (`apps/reviews/services/reply_generation.py`) | — | Only reviews may import both credits and openai; credits never imports reviews (D-locked) |
| HTTP status/body mapping (400/402/409/422/502) and throttle scope | API / Backend (`ReviewViewSet`) | — | Thin view maps domain exceptions to responses (CLAUDE.md §5, §8) |
| Reply-path timeout / retries | API / Backend (`apps/integrations/openai/client.py` + settings) | — | SDK client option, reply path only |
| Cost display value (`credit-cost`) | API / Backend (selector + `credit_cost`) | Browser (Phase 33 renders) | Price shown must equal price charged; UI never recomputes (Phase 29 D-09) |
| Distributed correctness under concurrency | Database (row lock on `ShopCreditBalance`, CAS) | Redis not used | No Redis lock needed: the balance row lock is the serialiser |
| Deploy/rollout note | Docs (`docs/sre/v0.9-credits-rollout.md`) | — | CQA-02 |

## Standard Stack

No new dependencies. [VERIFIED: introspection of the repo venv this session]

### Core (already installed, versions read from the venv)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.2 | ORM `select_for_update(of=("self",))`, `F()`, `transaction.atomic` | Project standard |
| djangorestframework + drf-spectacular | existing | Views, `@action`, `inline_serializer`, `OpenApiResponse` | Pattern already used by `generate_reply` |
| openai | 2.33.0 | `OpenAI.with_options(timeout=..., max_retries=...)` | Official SDK copy-with-options API |
| langsmith | 0.8.0 | `@traceable` already decorates the reply call | Unchanged |
| asgiref | 3.11.1 / daphne 4.2.1 | Sync view execution under ASGI | Disconnect behaviour verified |
| pytest 8.3.3 + pytest-django + factory-boy, psycopg 3.2.3 | existing | Tests incl. `pg_concurrency` | Project standard |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DB partial unique index for D-12 | App-level check under the balance lock only | **Recommend skipping the index** (see Pattern 3): the lock already serialises; the existing partial index `credit_tx_reserved_idx` (RESERVED rows only) makes the lookup cheap; avoids a new credits migration that Phase 29 D-01 explicitly tried to avoid; only the month-boundary straddle would escape the lock (different balance rows) and that is negligible. |
| Redis lock per review for D-12 | Balance-row lock | Redis adds a failure mode (`IGNORE_EXCEPTIONS`), DB lock is authoritative |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed or added in this phase. Gate not applicable. Packages inspected (`openai`, `langsmith`, `asgiref`, `daphne`) are existing pinned project dependencies. **Packages removed due to SLOP:** none. **Packages flagged SUS:** none.

## Phase 29 interface contract consumed

Phase 30 plans MUST re-verify each row against real code before executing (29-02/29-03 were mid-execution while this research ran). "On disk" = read this session; status can only be better by the time Phase 30 executes.

| Symbol | Module | Signature (as planned / as on disk) | Source plan | State when researched |
|--------|--------|-------------------------------------|-------------|-----------------------|
| `ShopCreditBalance` | `apps.credits.models` | fields `shop, organisation, period_year, period_month, allocated_credits, bonus_credits, consumed_credits, created_at, updated_at`; related_name `credit_balances`; CHECKs `credit_balance_nonneg`, `credit_balance_no_overspend` (`consumed_credits__lte=F("allocated_credits") + F("bonus_credits")`) | 29-01 | on disk, read. Balance is **mutable**; `updated_at` is `auto_now` and does **not** fire on `QuerySet.update()`, so set it explicitly |
| `CreditTransaction` (`Type`, `Status`) | `apps.credits.models` | `Type`: `INITIAL_ALLOCATION, BONUS_ALLOCATION, CONSUMPTION, LAPSED`; `Status`: `RESERVED, COMMITTED, REFUNDED`; FKs `shop_credit_balance` (PROTECT), `shop`, `organisation` (PROTECT), `review`, `ai_usage_log`, `actor` (SET_NULL); `note` (255, null); CHECK `credit_tx_only_consumption_reserved`, `credit_tx_delta_sign`; index `credit_tx_reserved_idx (status, created_at) WHERE status=RESERVED` | 29-01 | on disk, read |
| `ensure_balance` | `apps.credits.services.allocation` | `ensure_balance(*, shop_id: int, period: Period \| None = None) -> tuple[ShopCreditBalance, bool]`; own `transaction.atomic()`; derives org from Shop; raises `Shop.DoesNotExist`; **writes a balance row even when allocation is 0** (no INITIAL tx, no audit) | 29-01 | on disk, read |
| `current_period`, `next_period_start`, `utc_now`, `Period` | `apps.credits.services.periods` | `current_period(now=None) -> Period(year, month)` | 29-01 | on disk, read |
| `transition_status` | `apps.credits.services.ledger` | `transition_status(*, transaction_id: int, from_status: str, to_status: str) -> bool` (True = this call won; raises `InvalidStatusTransition` for pairs other than RESERVED->COMMITTED/REFUNDED; False for absent/already-settled row) | 29-02 | **on disk and implemented** (commit e8a8b93) |
| `CreditTransactionQuerySet.cas_status` | `apps.credits.managers` | `cas_status(self, *, pk: int, from_status: str, to_status: str) -> int` | 29-02 | on disk, read. **Writes only `status` (gap F1)** |
| `AppendOnlyViolation`, `InvalidStatusTransition` | `apps.credits.exceptions` | plain `Exception` subclasses | 29-02 | on disk. Phase 30 adds its own classes to this module |
| `CreditTransaction.ALLOWED_STATUS_TRANSITIONS` | `apps.credits.models` | `frozenset({(RESERVED, COMMITTED), (RESERVED, REFUNDED)})` | 29-02 | on disk |
| `CreditTransaction.objects.create()/bulk_create()` allowed; `.update()/.delete()`, instance `.delete()`, non-status `.save()` raise `AppendOnlyViolation` | `apps.credits.managers/models` | — | 29-02 | on disk |
| `assert_ledger_reconciles` | `apps.credits.tests.helpers` | `assert_ledger_reconciles(balance: ShopCreditBalance) -> None` (balance.consumed == SUM(-delta) over CONSUMPTION in RESERVED/COMMITTED) | 29-02 | on disk, read |
| `ShopCreditBalanceFactory`, `CreditTransactionFactory` | `apps.credits.tests.factories` | defaults: balance allocated 10 / bonus 0 / consumed 0 current period; tx CONSUMPTION / RESERVED / -1 (note: factory does **not** bump `consumed_credits`) | 29-01 | on disk, read |
| `pg_concurrency` marker, `REQUIRE_PG`, `config.settings.test_pg`, `make test-pg`, `backend-pg` CI job | root `conftest.py`, pyproject, ci.yml | `@pytest.mark.pg_concurrency` + `@pytest.mark.django_db(transaction=True)`, `threading.Barrier`, `connections.close_all()` in `finally` | 29-01 | on disk, read |
| `credit_cost` | `apps.credits.services.credit_cost` | `credit_cost(text: str \| None) -> int` (0 = not chargeable; reads `settings.REVIEWBEE_CREDIT_TIERS` at call time) | 29-03 | **NOT on disk** (planned) |
| `CreditBalanceView`, `get_shop_credit_balance` | `apps.credits.selectors.balances` | frozen dataclass `(shop_id, year, month, allocated, bonus, consumed, remaining, is_enabled, is_materialized, renews_on)`; `get_shop_credit_balance(*, shop_id: int, period: Period \| None = None) -> CreditBalanceView`; read-only; unmaterialised shop reports the **org's live allocation** | 29-03 | **NOT on disk** (planned) |
| `annotate_credit_state` | `apps.credits.selectors.balances` | Phase 33 consumer only | 29-03 | not used by Phase 30 |
| Settings `REVIEWBEE_CREDIT_TIERS`, `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES`, `REVIEWBEE_SUPPORT_EMAIL` | `config/settings/base.py:233-238` | quoted in "Settings" below | 29-01 | on disk, read |
| `apps.credits` in `INSTALLED_APPS` (base + test) | settings | — | 29-01 | on disk |

**Interface gap to resolve before Phase 30 execution (F1):**

> `cas_status` and `transition_status` must accept an optional `ai_usage_log_id: int | None = None` and write it **in the same single conditional UPDATE** as the status: `models.QuerySet.update(self.filter(pk=pk, status=from_status), status=to_status, **({"ai_usage_log_id": ai_usage_log_id} if ai_usage_log_id is not None else {}))`. No other column becomes writable; `save()` stays status-only; the source-scan test (only `ledger.py`, `models.py`, `managers.py` mention `cas_status(`) still holds. Add to `test_append_only.py`: linking succeeds on RESERVED->COMMITTED, is a no-op when the CAS loses (the FK stays NULL), and `credits_delta`/`note` remain unwritable.

Cheapest path: the orchestrator should ask the Phase 29 executor to add this **now** (small, localised). Fallback: make it Plan 30-01 Task 1. Alternatives (reverse FK on `AiUsageLog`, creating the ledger row after the call) both contradict locked decisions (direction tx -> usage log; reserve-before-call). Also note the link is only strictly required on commit (CCON-06); linking on refund is optional (see Open Question OQ-4).

## Architecture Patterns

### System Architecture Diagram

```
POST /api/v1/reviews/{id}/generate-reply/   (sync DRF view, run in executor thread under ASGI)
  |
  v
DRF initial(): authn -> permission IsOrgScoped -> throttle scope "generate_reply" (10/min) -> 429
  |
  v
ReviewViewSet.get_object()  (tenant + StaffAccessScope scoping; 404 if out of scope)
  |
  v
GenerateReplySerializer (tone)  --invalid--> 400 (DRF)
  |
  v
generate_reply_with_credits(review, tone, actor_id)           [apps/reviews/services/reply_generation.py]
  |-- tone allow-list check (before any reservation)
  |-- cost = credit_cost(review.comment)   ==0--> EmptyCommentError --> 400 {code:"empty_comment"}   (no reservation)
  |-- reserve_credits(shop_id, review_id, cost, actor_id)      [apps/credits/services/consumption.py]
  |       pre-check (read-only selector): not enabled -> InsufficientCreditsError(not_enabled)  --> 402   (no writes)
  |       ensure_balance()  (own atomic, lazy create)
  |       atomic { SELECT ... FOR UPDATE (of self) on balance
  |                RESERVED CONSUMPTION for review_id exists? -> GenerationInProgressError --> 409
  |                total==0 -> not_enabled; remaining<cost -> exhausted  --> 402
  |                guarded F() UPDATE consumed += cost  (rowcount 1)
  |                INSERT CreditTransaction(CONSUMPTION, RESERVED, -cost, review, actor) }   <- commit; lock released
  |       returns Reservation(transaction_id, shop_credit_balance_id, credits, ...)
  |
  |-- try:
  |      _assert_no_open_transaction()                          (RuntimeError if inside atomic)
  |      draft, usage_log_id = _generate_reply_draft_with_log() (moderate_input -> OpenAI[with_options timeout]
  |                                                              -> moderate_output -> AiUsageLog row)
  |      outcome = COMMIT(success)
  |   except ContentModeratedException(stage, usage_log_id): output -> COMMIT(output_moderated); input/None -> REFUND
  |   except OpenAITransientError/OpenAIPermanentError/Exception: REFUND
  |   finally:                                                  <- runs even if the client is gone / BaseException
  |      settle:  COMMIT -> commit_reservation()  : CAS RESERVED->COMMITTED (+ai_usage_log_id) + AuditLog consumed
  |                                                 CAS lost  -> late-commit path (re-deduct once | free draft) + AuditLog + Sentry
  |               REFUND -> refund_reservation()  : atomic{ CAS RESERVED->REFUNDED; guarded F() consumed -= cost; AuditLog refunded }
  |      credits_remaining = get_shop_credit_balance(...).remaining   (1 query)
  v
returns ReplyResult(draft, credits_charged, credits_remaining)  or raises ReplyModeratedError / ReplyUnavailableError
  (both carry credits_charged / credits_remaining; raised AFTER settlement)
  |
  v
View ladder: EmptyComment->400 | InsufficientCredits->402 | GenerationInProgress->409 | ReplyModerated->422
             | ReplyUnavailable->502 | APIException re-raise | Exception->502   ;  success -> 200 {draft, credits_charged, credits_remaining}

GET /api/v1/reviews/{id}/credit-cost/  -> get_object() -> {cost: credit_cost(comment), remaining, is_enabled} (never writes)
```

### Recommended Project Structure
```
apps/credits/
├── exceptions.py            # + InsufficientCreditsError(reason, required, remaining), GenerationInProgressError
├── services/consumption.py  # NEW: Reservation, reserve_credits, commit_reservation, refund_reservation, _late_commit
├── services/ledger.py       # (Phase 29) transition_status; + ai_usage_log_id arg (F1)
└── tests/test_consumption.py, test_pg_concurrency.py (+3 tests), test_settings.py (+margin test)
apps/reviews/
├── services/reply_generation.py   # generate_reply_draft (thin wrapper), _generate_reply_draft_with_log, generate_reply_with_credits, ReplyResult, EmptyCommentError, ReplyModeratedError, ReplyUnavailableError
├── views.py                       # generate_reply ladder, credit_cost @action, get_throttles
└── tests/test_views.py (re-point), test_reply_generation_credits.py (orchestrator matrix), test_pg_reply_concurrency.py
apps/integrations/openai/
├── exceptions.py   # ContentModeratedException(msg, *, stage=None, usage_log_id=None)
├── guardrails.py   # _persist_moderated_log returns pk; raise sites pass stage/usage_log_id
└── client.py       # _get_reply_client(); APIConnectionError mapping on reply path
config/settings/base.py  # + REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS, REVIEWBEE_REPLY_OPENAI_MAX_RETRIES, "credit_cost" throttle rate
docs/sre/v0.9-credits-rollout.md
```

### Pattern 1: Reserve (short row-locked transaction, guarded F() update)
**What:** Lock the balance row only for the duration of check + increment + insert; the OpenAI call happens after the transaction commits.
**When:** Every generate request after the 400 gate.
**Example (sketch, not final code):**
```python
# apps/credits/services/consumption.py
@dataclass(frozen=True, slots=True)
class Reservation:
    transaction_id: int
    shop_credit_balance_id: int
    shop_id: int
    organisation_id: int
    review_id: int
    credits: int
    actor_id: int | None

def reserve_credits(*, shop_id: int, review_id: int, credits: int, actor_id: int | None) -> Reservation:
    if credits <= 0:
        raise ValueError("credits must be positive; cost 0 is rejected upstream (CCON-04)")
    # Read-only pre-check: a not-enabled org must never materialise a zero balance row
    # (rollout: EVERY org starts at 0, so otherwise every click would write a row).
    view = get_shop_credit_balance(shop_id=shop_id)
    if not view.is_enabled:
        raise InsufficientCreditsError(reason="not_enabled", required=credits, remaining=view.remaining)
    balance, _ = ensure_balance(shop_id=shop_id)               # own atomic; call OUTSIDE the reserve atomic
    with transaction.atomic():
        locked = ShopCreditBalance.objects.select_for_update(of=("self",)).get(pk=balance.pk)  # no select_related
        if CreditTransaction.objects.filter(               # by review_id only (not by balance): straddles months
            review_id=review_id,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status=CreditTransaction.Status.RESERVED,
        ).exists():
            raise GenerationInProgressError(review_id=review_id)
        total = locked.allocated_credits + locked.bonus_credits
        remaining = total - locked.consumed_credits
        if total == 0:
            raise InsufficientCreditsError(reason="not_enabled", required=credits, remaining=0)
        if remaining < credits:
            raise InsufficientCreditsError(reason="exhausted", required=credits, remaining=remaining)
        updated = ShopCreditBalance.objects.filter(
            pk=locked.pk,
            consumed_credits__lte=F("allocated_credits") + F("bonus_credits") - credits,   # guard also valid on SQLite
        ).update(consumed_credits=F("consumed_credits") + credits, updated_at=timezone.now())
        if updated != 1:                                    # belt and braces; DB CHECK is the last line
            raise InsufficientCreditsError(reason="exhausted", required=credits, remaining=remaining)
        tx = CreditTransaction.objects.create(
            shop_credit_balance_id=locked.pk, shop_id=shop_id, organisation_id=locked.organisation_id,
            transaction_type=CreditTransaction.Type.CONSUMPTION, status=CreditTransaction.Status.RESERVED,
            credits_delta=-credits, review_id=review_id, actor_id=actor_id,
        )
    return Reservation(tx.pk, locked.pk, shop_id, locked.organisation_id, review_id, credits, actor_id)
```
`[VERIFIED: guarded-update pattern ran green on the project's SQLite test DB this session; the first update succeeded (rowcount 1) and the guard semantics were confirmed (a `<=` boundary allows consumed to reach allocated+bonus exactly).]` The lock is taken **after** `ensure_balance` committed so first-use losers re-read the committed row (29 research, allocation.py docstring).

### Pattern 2: Settle by `transaction_id` (commit = CAS only; refund = CAS + decrement)
**What:** Credits were already added to `consumed_credits` at reserve, so **commit does not touch the balance**; refund must give them back; both are addressed through the transaction row (`tx.shop_credit_balance_id`), never through a recomputed period.
```python
def commit_reservation(*, transaction_id: int, ai_usage_log_id: int | None, outcome: str) -> CommitResult:
    tx = CreditTransaction.objects.get(pk=transaction_id)   # 1 query; reaper/orchestrator both may call
    with transaction.atomic():
        won = transition_status(transaction_id=transaction_id, from_status=RESERVED, to_status=COMMITTED,
                                ai_usage_log_id=ai_usage_log_id)          # needs F1 extension
        if won:
            _audit(tx, "shop.credits.consumed", {...}); return CommitResult(charged=-tx.credits_delta, late=False)
    return _late_commit(tx, ai_usage_log_id, outcome)   # CAS lost

def refund_reservation(*, transaction_id: int, reason: str, ai_usage_log_id: int | None = None) -> bool:
    tx = CreditTransaction.objects.get(pk=transaction_id)
    credits = -tx.credits_delta
    with transaction.atomic():
        if not transition_status(transaction_id=transaction_id, from_status=RESERVED, to_status=REFUNDED, ...):
            return False                                  # someone else settled it: do NOT touch the balance
        n = ShopCreditBalance.objects.filter(pk=tx.shop_credit_balance_id, consumed_credits__gte=credits).update(
            consumed_credits=F("consumed_credits") - credits, updated_at=timezone.now())
        if n != 1:
            raise RuntimeError("refund would drive consumed_credits negative")   # rolls the CAS back; ledger stays RESERVED
        _audit(tx, "shop.credits.refunded", {...})
        return True
```
`refund_reservation` is also the symbol Phase 31's reaper consumes (ROADMAP Phase 31 "Depends on ... `refund_reservation`"): keep the name and the `transaction_id`-only addressing. The CAS gates the decrement, so a double refund or reaper-vs-late-commit race cannot return credits twice. The CAS and the balance update run in one atomic so a failed decrement rolls the status change back.

Lock order: reserve takes balance-row lock then inserts a new tx row; settle updates the tx row then the balance row via an atomic `F()` UPDATE. There is no cycle (reserve never waits on an existing tx row), so no deadlock; the PG race tests below prove it.

### Pattern 3: D-12 in-flight guard without a new index
The `exists()` filter is `review_id=… AND transaction_type='CONSUMPTION' AND status='RESERVED'`. Phase 29 already ships the partial index `credit_tx_reserved_idx (status, created_at) WHERE status='RESERVED'`, which is tiny (RESERVED rows are short-lived), so the lookup is cheap. **Recommendation: do not add `UNIQUE(review) WHERE type=CONSUMPTION AND status=RESERVED`.** Reasons: (a) the balance-row lock already serialises same-shop requests; (b) the only escape is a reservation straddling a month boundary (two balance rows, two locks), which is vanishingly rare and bounded by one extra charge-then-refund; (c) it adds a credits migration that Phase 29 D-01 deliberately avoided; (d) an `IntegrityError` would poison the surrounding atomic on Postgres and would need a savepoint dance. Prove the guard with a Postgres test instead (same-review N threads -> exactly one success, the rest 409). If the planner overrides this, the migration must be a new `credits/0002`, with a savepoint around the insert.

### Pattern 4: Orchestrator with `finally` settlement (D-03, D-04)
```python
def generate_reply_with_credits(*, review: Review, tone: str, actor_id: int | None) -> ReplyResult:
    if tone not in _ALLOWED_TONES:
        raise ValueError(...)                                  # before any reservation
    cost = credit_cost(review.comment)
    if cost == 0:
        raise EmptyCommentError()                              # 400, before reserve (CCON-04)
    reservation = reserve_credits(shop_id=review.shop_id, review_id=review.pk, credits=cost, actor_id=actor_id)

    kind, reason, usage_log_id = "refund", "unexpected_error", None      # default = refund (D-04, also BaseException)
    draft: str | None = None
    failure: Exception | None = None
    try:
        _assert_no_open_transaction()
        draft, usage_log_id = _generate_reply_draft_with_log(review=review, tone=tone)
        kind, reason = "commit", "success"
    except ContentModeratedException as exc:
        usage_log_id = exc.usage_log_id
        if exc.stage == "output":                                        # OpenAI billed us
            kind, reason = "commit", "output_moderated"
        else:                                                            # "input" or unknown stage -> never charge unless sure
            kind, reason = "refund", "input_moderated"
        failure = ReplyModeratedError(stage=exc.stage)
    except (OpenAITransientError, OpenAIPermanentError) as exc:
        reason = "openai_failure"; failure = ReplyUnavailableError(); failure.__cause__ = exc
    except Exception as exc:
        reason = "unexpected_error"; failure = ReplyUnavailableError(); failure.__cause__ = exc
    finally:
        charged = _settle(reservation, kind, reason, usage_log_id)       # never raises (own try/except + logger.exception)
    remaining = get_shop_credit_balance(shop_id=review.shop_id).remaining
    if failure is not None:
        failure.credits_charged, failure.credits_remaining = charged, remaining
        raise failure
    return ReplyResult(draft=draft, credits_charged=charged, credits_remaining=remaining)
```
Design points: `finally` runs for `BaseException` too, defaulting to REFUND. `_settle` must swallow and log its own failures (`logger.exception`, ids only) so it never masks the original exception; a failed settlement leaves a RESERVED row that Phase 31's reaper clears. `_assert_no_open_transaction` is inside the `try` so a guard failure refunds. Wrapper exceptions are raised **after** the `finally`, so settlement has completed before the view builds a response, and `credits_remaining` is "current" per D-09. Wrapper exceptions must NOT subclass `OpenAIError` or `APIException`, so they do not collide with the legacy ladder. `credits_charged` is `cost` only for COMMIT outcomes (including late re-deduct success) and `0` otherwise (including a free late-commit draft).

### Pattern 5: Reply-path timeout via a dedicated helper (verified)
```python
# apps/integrations/openai/client.py
def _get_reply_client() -> OpenAI:
    return _get_client().with_options(
        timeout=settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS,
        max_retries=settings.REVIEWBEE_REPLY_OPENAI_MAX_RETRIES,
    )
# _do_chat_completions_create uses _get_reply_client(); the enrichment path (_do_responses_parse) keeps _get_client().
```
`[VERIFIED: runtime probe on openai 2.33.0]`: `OpenAI.with_options` has signature `(self, *, api_key=…, …, timeout=NOT_GIVEN, http_client=None, max_retries=NOT_GIVEN, …) -> Self`; `c.with_options(timeout=30, max_retries=1)` returns a **new** `openai.OpenAI` (`c2 is c` is `False`) with `timeout == 30` and `max_retries == 1` while the original keeps `Timeout(connect=5.0, read=600, write=600, pool=600)` and `max_retries == 2`. So the shared singleton and enrichment are untouched. LangSmith: tracing is the `@traceable(run_type="llm", name="generate_reply")` decorator on `_call_openai_reply_with_tracing`, and the repo never calls `wrap_openai` (grep over `apps/` and `config/` returned no match), so the options-bearing client is traced identically. Use a named helper (not inline `with_options`) so tests patch one seam. Per-call `with_options` copies are cheap and reuse the underlying httpx client. Tests patching `apps.integrations.openai.client._get_client` with a `MagicMock` (test_client.py:289, 321, 342, 363) would otherwise get a *different* mock from `.with_options(...)`; re-point those four to `_get_reply_client` (or set `fake_client.with_options.return_value = fake_client`).

**Also required (F2):** in `_do_chat_completions_create`, map `openai.APIConnectionError` (covers `APITimeoutError`) to `OpenAITransientError` on the reply path only, so it hits the `except (OpenAITransientError, OpenAIPermanentError): raise` branch instead of the untraced duplicate-call fallback. Do not change `_map_openai_error` (shared with enrichment, where Celery retries the task anyway).

**Worst-case budget** (timeout `T=30`, SDK `max_retries=1` => each call up to `T*(1+1)=60` s plus backoff):

| Component | Current (F2 unfixed) | Recommended (F2 fixed, moderation `T=30, max_retries=0`) |
|---|---|---|
| input moderation (2 app attempts + 1 s sleep) | 2x600x3 s (unbounded) | 2x30 + 1 = 61 s |
| chat completion | 60 s, x2 via untraced fallback = 120 s | 60 s |
| output moderation | unbounded | 61 s |
| **Total** | unbounded | **~182 s < TTL 300 s** |

The D-06 formula `TTL >= 2 x timeout x (max_retries + 1)` (=120 s) covers the chat call including a hypothetical double attempt, but is not a bound on the whole request. See OQ-1 for the recommended moderation change; its late-commit safety net (D-01) covers anything beyond the budget.

### Pattern 6: Moderation stage + usage-log id plumbing
```python
# exceptions.py
class ContentModeratedException(OpenAIError):  # noqa: N818
    def __init__(self, message: str = "", *, stage: str | None = None, usage_log_id: int | None = None) -> None:
        super().__init__(message); self.stage = stage; self.usage_log_id = usage_log_id
# guardrails.py: _persist_moderated_log(...) -> int   (return AiUsageLog.objects.create(...).pk)
#   moderate_input : usage_log_id = _persist_moderated_log(...) if review is not None else None
#                    raise ContentModeratedException("input flagged", stage="input", usage_log_id=usage_log_id)
#   moderate_output: same with stage="output"
```
`_generate_reply_draft_with_log(*, review, tone) -> tuple[str, int]`: identical body to today's `generate_reply_draft`, but returns `AiUsageLog.objects.create(...).pk` alongside the draft; `generate_reply_draft(*, review, tone) -> str` becomes `return _generate_reply_draft_with_log(review=review, tone=tone)[0]` so `test_reply_generation_service.py` (which patches `apps.reviews.services.reply_generation.call_openai_reply_generation` / `moderate_*`) and any other caller are unaffected. `_write_failure_log` need not return an id (no link needed for refunds unless OQ-4 is accepted). Enrichment: `enrichment.py:562 except ContentModeratedException:` ignores kwargs; `test_enrichment_service.py` and `test_guardrails.py` keep passing. Existing `test_guardrails.py` tests for `moderate_*` stay valid; add tests that the new attributes are set (and `None` when `review=None`).

### Pattern 7: The transaction guard (D-07, F3)
```python
def _assert_no_open_transaction() -> None:
    # Django TestCase / pytest-django wrap tests in an atomic flagged _from_testcase; real atomics are not.
    if any(not getattr(b, "_from_testcase", False) for b in connection.atomic_blocks):
        raise RuntimeError("OpenAI call must not run inside a database transaction")
```
`[VERIFIED: probe test, 2 passed]`: with `@pytest.mark.django_db`, `connection.in_atomic_block is True` yet the guard returns False; inside a user `with transaction.atomic():` it returns True; with `transaction=True` both behave as expected. `connection.atomic_blocks` and `Atomic._from_testcase` exist in Django 6.0.2 (`django/db/transaction.py:180-188`, `django/test/testcases.py:1395`) but are semi-private; pin the behaviour with the guard tests below so a Django upgrade fails loudly. Production runs without `ATOMIC_REQUESTS` (no match in `config/`), so the guard is a pure regression tripwire there.

### Pattern 8: Client abort under Daphne (research flag 1) - verified
`django/core/handlers/asgi.py::ASGIHandler.handle` races `listen_for_disconnect` against `process_request`; on `http.disconnect` it calls `task.cancel()` on `process_request`. The sync view is executed through asgiref `SyncToAsync.__call__`, which awaits `asyncio.shield(exec_coro)` and, on `CancelledError`, re-awaits the executor future; Python cannot kill the worker thread. Probe 1 (plain `sync_to_async`) and probe 2 (inside `ThreadSensitiveContext`, exactly how `ASGIHandler.__call__` wraps each request) both printed `['awaiter-cancelled', 'body-finished', 'finally-ran', ('context-exited')]`: the thread body and its `finally` complete, and the context exit waits for them. `[VERIFIED: probes in scratchpad, asgiref 3.11.1, Django 6.0.2]`. Conclusion: placement of settlement inside the service `try/finally` guarantees it; nothing in the view response construction is needed. Residual risks outside this guarantee: process termination (SIGKILL/instance recycle) and platform request timeouts. Those leave a RESERVED row that the Phase 31 reaper refunds; the rollout note should state it. `[ASSUMED]` Cloud Run's request timeout (60 s default per CLAUDE.md §10) returns 504 to the client but does not stop the in-flight thread, and CPU may be throttled after the response is sent unless CPU is always allocated; ask `deployment-helper` to confirm timeout >= worst-case budget (~182 s) or accept reaper cleanup.

### Anti-Patterns to Avoid
- **Calling `ensure_balance` inside the reserve atomic or computing the period for settlement.** Settle by `tx.shop_credit_balance_id` (Phase 29 D-locked); a reservation that straddles midnight must settle against its original month.
- **`select_related` + `select_for_update`** (locks Shop/Org rows and serialises the whole tenant): use `of=("self",)`, no `select_related`.
- **Mutating `consumed_credits` with read-modify-write or `save()`.** Always `F()` via guarded `.update()`; and always set `updated_at`.
- **A pre-check via `ensure_balance` on the 402 `not_enabled` path.** It would write a zero-allocation balance row for every click of every un-enabled org at rollout, which also complicates Phase 32's 0->N immediate rule. Use the read-only selector first.
- **Catching `ContentModeratedException` in the view.** The view only sees wrapper exceptions after settlement.
- **Logging review text or the draft** (CLAUDE.md §22). Log ids, cost, outcome only.
- **Adding credit fields to the 422 body via a code path that reads LLM categories** (T-20-LK). Add only the two ints.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cost computation | Tier logic in the view or orchestrator | `credit_cost()` (Phase 29-03), only caller of `REVIEWBEE_CREDIT_TIERS` | A scan test enforces the price shown == price charged |
| Status transition | `.update(status=...)` or `save()` | `ledger.transition_status` (CAS) | Append-only guards raise on anything else |
| Balance read for 402 / `credits_remaining` / `credit-cost` | Ad-hoc `ShopCreditBalance.objects.filter(...)` in a view | `get_shop_credit_balance` (Phase 29-03) | Handles the unmaterialised-shop fallback |
| Lazy balance creation | `get_or_create` + INITIAL row in the consumption module | `ensure_balance` | Race-safe, one INITIAL row, audit row |
| Cross-worker serialisation | Redis lock for D-12 / overspend | Balance-row `select_for_update(of=("self",))` | DB is authoritative; Redis can be ignored via `IGNORE_EXCEPTIONS` |
| Overspend protection | Python-side `if remaining >= cost` alone | Guarded `F()` UPDATE (rowcount) + DB CHECK `credit_balance_no_overspend` | Works on SQLite where `select_for_update` is a no-op |
| Throttle | Custom limiter | DRF `ScopedRateThrottle` via `get_throttles` (WR-02 pattern) | Existing mechanism |
| Request-scoped OpenAI timeout | Thread timers / `signal.alarm` / wrapping with `asyncio.wait_for` | SDK `with_options(timeout, max_retries)` | The SDK owns httpx timeouts |

**Key insight:** every hard property here (no overspend, no double refund, idempotent settle) falls out of two database primitives, the guarded `UPDATE ... WHERE consumed <= allocated + bonus - cost` and the `UPDATE ... WHERE status='RESERVED'` CAS, so the service layer should stay a thin composition of them.

## Common Pitfalls

### Pitfall 1: Existing view tests break on the `patch` target, not just the 402
**What goes wrong:** All `@patch("apps.reviews.views.generate_reply_draft")` tests raise `AttributeError` once the view imports `generate_reply_with_credits`.
**How to avoid:** Re-point the seam to the layer **below** credits so the real credits path is exercised: patch `apps.reviews.services.reply_generation._generate_reply_draft_with_log` (return `("draft", None)` or side-effect the legacy exceptions) and give the test org an explicit allocation (`OrganisationFactory(monthly_credit_allocation=...)`). The org factory default stays 0 (CONTEXT discretion).
**Warning signs:** `AttributeError: <module 'apps.reviews.views'> does not have the attribute 'generate_reply_draft'`.

### Pitfall 2: Untraced duplicate OpenAI call on timeout (F2)
**What goes wrong:** `APITimeoutError` -> `except Exception` -> second call without tracing; billing and latency double, "exactly one AiUsageLog" still holds but the second call is invisible to LangSmith.
**How to avoid:** Map `openai.APIConnectionError` to `OpenAITransientError` in the reply `_do_chat_completions_create`; add a test that a timeout produces exactly one `create` call and one FAILED log.

### Pitfall 3: Moderation calls outlive the TTL (F2)
**What goes wrong:** `moderate_input`/`moderate_output` use the 600 s client, so a hung Moderation API can outlast the 5 min TTL and the reaper refunds an in-flight reservation (then late-commit must re-deduct).
**How to avoid:** apply reply-path options to the moderation calls (OQ-1) and widen the margin test to the whole-request budget.
**Signal:** `shop.credits.late_commit` audit rows in production.

### Pitfall 4: The `in_atomic_block` guard raising in tests (F3)
See Pattern 7. Without the `_from_testcase` filter every `@pytest.mark.django_db` view/service test fails.

### Pitfall 5: Late-commit double charge (F6)
**What goes wrong:** CAS lost because the row is already COMMITTED, then "re-deduct" charges again.
**How to avoid:** the late path re-reads the status. REFUNDED -> try the one guarded re-deduct. COMMITTED -> no-op + audit `already_settled` (never charge). Absent row -> audit only. Also decide the policy for a balance that is no longer the current period (A3): recommended, re-deduct only when the original balance's period is the current period and it has no LAPSED row; otherwise the draft is free. Re-deduct inserts a new COMMITTED CONSUMPTION row (`credits_delta=-cost`, `review`, `actor`, `ai_usage_log`, `note="late_commit"`) and increments `consumed_credits` via the guarded `F()`, inside one atomic; the old REFUNDED row stays as history. `assert_ledger_reconciles` still holds (new COMMITTED row == increment; REFUNDED rows excluded).

### Pitfall 6: Settle swallowing / masking errors
`_settle` runs in `finally`; an exception there would replace the real failure and skip the response. Wrap it, log with `logger.exception` (ids only), and let the reaper clean up. Unit-test: force `commit_reservation` to raise -> original outcome still delivered, RESERVED row remains.

### Pitfall 7: Query-count test ceiling (existing `<= 4`)
`test_generate_reply_query_count` asserts `<= 4` queries with the service patched. With the orchestrator unpatched below credits, reserve + settle add roughly 15-20 queries. Re-baseline to a fixed ceiling independent of cost/review count (measure after implementation, pin with ~20% headroom), and add the same ceiling for the `credit-cost` endpoint (<= ~6).

### Pitfall 8: Throttle cache bleed
Tests that hit `generate-reply` repeatedly hit the 10/min limit (locmem `throttle` cache survives DB rollback). Keep `caches["throttle"].clear()` in an autouse fixture for the new test classes (existing test does it inline).

### Pitfall 9: `ScopedRateThrottle` requires a configured rate
A new `credit_cost` scope without an entry in `DEFAULT_THROTTLE_RATES` raises `ImproperlyConfigured` at request time. Add the rate and handle the action in `get_throttles()` (WR-02 pattern) and pass `throttle_classes=[ScopedRateThrottle]` on the `@action`.

### Pitfall 10: Frontend contract drift (F7)
Between Phase 30 and 33 the composer shows the generic failure string for 402/409; document. Do not change the frontend in this phase (backend only per ROADMAP).

## Code Examples

### View ladder (replaces `generate_reply` body after `get_object` + tone validation)
```python
# apps/reviews/views.py  (sketch; keep legacy log lines, no review text)
try:
    result = generate_reply_with_credits(review=review, tone=tone, actor_id=request.user.pk)
except EmptyCommentError:
    return Response({"code": "empty_comment", "detail": "This review has no text to reply to."}, status=400)
except InsufficientCreditsError as exc:
    return Response({"code": "insufficient_credits", "reason": exc.reason,
                     "required": exc.required, "remaining": exc.remaining}, status=402)
except GenerationInProgressError:
    return Response({"code": "generation_in_progress", "detail": "..."}, status=409)
except ReplyModeratedError as exc:
    return Response({"code": "content_moderated",
                     "detail": "AI reply isn't available for this review. Please write your reply manually.",
                     "credits_charged": exc.credits_charged, "credits_remaining": exc.credits_remaining}, status=422)
except ReplyUnavailableError as exc:
    return Response({"code": "ai_unavailable", "detail": "AI generation failed. Please try again or write your reply manually.",
                     "credits_charged": 0, "credits_remaining": exc.credits_remaining}, status=502)
except APIException:
    raise
except Exception:
    logger.exception("generate_reply_unexpected review_id=%s tone=%s", review.pk, tone)
    return Response({... 502 ...})   # reserve/settle already handled inside; credit fields best-effort via selector
return Response({"draft": result.draft, "credits_charged": result.credits_charged,
                 "credits_remaining": result.credits_remaining}, status=200)
```
The legacy `except (OpenAITransientError, OpenAIPermanentError)` / `except ContentModeratedException` clauses move into the orchestrator. 402/409/400 clauses MUST precede `except Exception` (CONTEXT order). Keep the byte-exact 422 `detail` string (test_views.py:576).

### `credit-cost` action
```python
@extend_schema(operation_id="reviews_credit_cost", responses={200: inline_serializer("ReviewCreditCostResponse", {...cost,remaining,is_enabled})})
@action(detail=True, methods=["get"], url_path="credit-cost", throttle_classes=[ScopedRateThrottle])
def credit_cost(self, request, pk=None):
    review = self.get_object()                                  # same tenant + StaffAccessScope scoping as generate
    view = get_shop_credit_balance(shop_id=review.shop_id)      # never writes
    return Response({"cost": credit_cost_fn(review.comment), "remaining": view.remaining, "is_enabled": view.is_enabled})
# get_throttles(): elif self.action == "credit_cost": self.throttle_scope = "credit_cost"
# settings: "credit_cost": "120/minute"   [ASSUMED rate; cheap read, UI calls it per visible review]
```
Name the imported function differently from the action method (`from apps.credits.services.credit_cost import credit_cost as compute_credit_cost`) to avoid shadowing. Note spec §10 (`/generate-reply/cost/`, unthrottled) is superseded by D-10 and the REQUIREMENTS.md reconciliation line.

### AuditLog payloads (no PII, no review text) `[ASSUMED shapes, discretion]`
| action | entity | actor | `after_data` |
|---|---|---|---|
| `shop.credits.consumed` | `entity_type="shop"`, `entity_id=str(shop_id)` | requesting user | `{"transaction_id", "review_id", "credits", "outcome": "success"\|"output_moderated", "ai_usage_log_id", "period_year", "period_month"}` |
| `shop.credits.refunded` | same | requesting user (`None` when the reaper refunds) | `{"transaction_id", "review_id", "credits", "reason": "openai_failure"\|"input_moderated"\|"unexpected_error"\|"reaper_ttl", "period_year", "period_month"}` |
| `shop.credits.late_commit` | same | requesting user | `{"transaction_id", "review_id", "credits", "prior_status": "REFUNDED"\|"COMMITTED", "outcome": "rededucted"\|"free_draft"\|"already_settled"}` |

`organisation_id` comes from the transaction row; follow the `ensure_balance` audit write (`entity_type="shop"`, `entity_id=str(shop_id)`, `before_data=None`) [VERIFIED: allocation.py:59-71]. Write the consumed/refunded row inside the same atomic as the CAS so a rolled-back settle leaves no audit. The Org Activity Log selector whitelists actions (`apps/common/selectors/audit_logs.py:31` lists reply actions), so the new actions will not appear in the viewer until Phase 33 wires them; that is expected. Sentry: the default Python logging integration turns `ERROR` records into events and `WARNING` into breadcrumbs `[ASSUMED]`, so for the D-01 "Sentry warning" use `sentry_sdk.capture_message("credits.late_commit ...", level="warning")` with ids only (the `_before_send` scrubber in base.py already filters sensitive keys).

### Settings (base.py)
Existing, quoted verbatim `[VERIFIED: config/settings/base.py:233-238, 417-418]`:
```python
REVIEWBEE_CREDIT_TIERS: list[tuple[int | None, int]] = [(100, 1), (500, 2), (None, 3)]
REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5
REVIEWBEE_SUPPORT_EMAIL = env("REVIEWBEE_SUPPORT_EMAIL", default="support@reviewbee.in")
        "review_reply": "30/minute",
        "generate_reply": "10/minute",
```
Add: `REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS = env.int("...", default=30)`, `REVIEWBEE_REPLY_OPENAI_MAX_RETRIES = env.int("...", default=1)`, `"credit_cost": "120/minute"`. The TTL is currently a literal 5 (not env-overridable): leave it. Margin tests: `TTL*60 >= 2 * timeout * (max_retries + 1)` (D-06) and, if OQ-1 is accepted, a stricter `TTL*60 >= worst_case_request_budget(...)` using the table above, both reading `settings` so an env override that breaks the margin fails CI.

## Existing Test / Factory Impact (CQA-02)

| File | Lines | Impact | Minimal fix |
|---|---|---|---|
| `apps/reviews/tests/test_views.py` `TestGenerateReplyEndpoint` | 407, 445, 460, 475, 489, 507, 525, 558, 576, 594 | `@patch("apps.reviews.views.generate_reply_draft")` no longer exists | Patch `apps.reviews.services.reply_generation._generate_reply_draft_with_log`; use `OrganisationFactory(monthly_credit_allocation=10)` in each test that reaches reserve |
| same | 416-421 | `resp.data == {"draft": "Great reply!"}`; `mock_generate.call_args.kwargs["tone"/"review"]` | New body has `credits_charged`/`credits_remaining`; assert tone/review via the below-credits seam's kwargs |
| same | 489-505 (staff accessible) | `resp.data == {"draft": ...}`; staff org has 0 credits -> 402 | Allocation on the staff test's org; assert new body |
| same | 507-523 (staff inaccessible) | `mock_generate.assert_not_called()` stays valid | add `assert no reservation was created` |
| same | 525-556 (`<= 4` queries) | credits reserve/settle add queries | Re-baseline fixed ceiling; add a "same count for cost 1 vs 3" assertion |
| same | 558-614 (422 tests) | Exact-dict `resp.json() == {"code","detail"}` and `set(resp.json().keys()) == {"code","detail"}` (T-20-LK) | Update to `{"code","detail","credits_charged","credits_remaining"}`; keep the byte-exact `detail` test and add an explicit "no categories / review text anywhere in the body" assertion so the T-20-LK intent survives. Both input/output variants need `ContentModeratedException(stage=...)` |
| `apps/integrations/openai/tests/test_client.py` | 289, 321, 342, 363 | Patch `_get_client` returning a `MagicMock`; reply path now calls `.with_options(...)` | Patch `_get_reply_client` (new helper) or set `fake_client.with_options.return_value = fake_client`; add tests asserting `with_options` is called with the two settings and that `APITimeoutError` -> `OpenAITransientError` with one `create` call |
| `apps/reviews/tests/test_reply_generation_service.py` | ~427-445 (`_input_se`/`_output_se` strict signatures) | Only if OQ-1 adds kwargs to `moderate_*` calls (TypeError on unexpected kwarg) | Add `**_kw` to those two side-effects. Other tests use `lambda text, **kw` and are unaffected. `generate_reply_draft` keeps its signature (thin wrapper), so no other service test changes |
| `apps/integrations/openai/tests/test_guardrails.py` | 173-253 | Unaffected (kwargs optional) | Add assertions for `exc.stage`, `exc.usage_log_id`, `None` when `review=None` |
| `apps/reviews/tests/test_enrichment_service.py` | — | Unaffected | none (regression-run only) |
| Factories | `apps/organisations/tests/factories.py`, `apps/reviews/tests/factories.py` | `OrganisationFactory` has no `monthly_credit_allocation` (default 0); `ReviewFactory.comment = factory.Faker("paragraph")` is non-empty (cost 1-2) | Do NOT change the org factory default; add a trait/fixture (`credits_enabled`) or pass the field explicitly. Pin a `comment` length when the assertion needs a specific cost |
| Frontend | `ReplyComposer.tsx`, `api.ts` | Types still `{draft}`; extra keys are harmless | No change in Phase 30 (F7) |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single click = one unmetered call; "if the user clicks twice, that is two calls intentionally" (reply_generation.py module docstring) | Reserve/settle with in-flight 409 guard | Phase 30 | Update the module docstring's Idempotency paragraph |
| SDK default 600 s timeout, `max_retries=2` on the shared client | Reply path: 30 s, 1 retry via `with_options`; shared client untouched | Phase 30 | Enrichment behaviour unchanged |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Cloud Run returns 504 on request timeout but keeps the thread running; CPU may be throttled after response unless always-allocated | Pattern 8 | Reservations strand until the reaper; late-commit rate higher. Ask `deployment-helper` |
| A2 | Default Sentry logging integration emits events only for ERROR and records WARNING as breadcrumbs | AuditLog/Sentry | D-01 "Sentry warning" would be invisible if `capture_message` is not used |
| A3 | A late re-deduct against a prior-month or already-lapsed balance should be a free draft | Pitfall 5 | Over/under-charging around month boundaries; Phase 31 lapse semantics not yet written |
| A4 | `credit_cost` throttle of 120/min is adequate | `credit-cost` | UI polling could be throttled; trivial to raise |
| A5 | Per-call `with_options` copy cost is negligible and reuses the httpx pool (SDK copy semantics) | Pattern 5 | Slight overhead only |
| A6 | AuditLog payload key names and the `empty_comment` / `generation_in_progress` detail strings | Code Examples | Cosmetic; Phase 33 UI keys on `code` |
| A7 | SDK's internal retry policy covers 408/409/429/5xx and connection errors (so `max_retries=1` retries a timeout once) | Pattern 5 budget | Budget arithmetic slightly optimistic if retries behave differently |

## Open Questions

1. **OQ-1: Should moderation calls on the reply path also use the bounded client?** (Recommended: yes.)
   - Known: both moderation calls use the 600 s shared client and add a 1 s sleep + one app-level retry; without bounding, the TTL margin claim (CCON-08) is only true for the chat call.
   - Unclear: D-05 names only the chat client.
   - Recommendation: add optional `timeout`/`max_retries` params to `moderate_input`/`moderate_output` -> `_call_moderation_api` (apply `with_options` only when provided, so enrichment and `test_guardrails.py` `_get_client` patches are unaffected); pass the reply settings with `max_retries=0` from the orchestrator path. Cost: one test side-effect signature fix (table above). If the user prefers strict D-05 scope, record the unbounded-moderation risk in the rollout note and rely on D-01.
2. **OQ-2: Who adds `ai_usage_log_id` to the CAS (F1)?** Recommended: Phase 29 executor now (29-02 in flight); else Plan 30-01 Task 1.
3. **OQ-3: Late-commit when the original balance is a prior month / lapsed (A3).** Recommended default: current-period + no LAPSED row, else free draft. Confirm with Phase 31 planning.
4. **OQ-4: Link `ai_usage_log` on refunds too?** CCON-06 requires it only for consumption rows that commit. Linking refunds gives traceability for input-moderation refunds (id available via `exc.usage_log_id`); FAILED-log id would need `_write_failure_log` to return the pk. Recommend: link when the id is already in hand (moderated), skip otherwise.
5. **OQ-5: `EmptyCommentError` placement.** Recommend `apps/reviews/services/reply_generation.py` (it is review-comment semantics; credits never sees cost 0 and `reserve_credits` raises `ValueError` for `credits <= 0`). `InsufficientCreditsError(reason, required, remaining)` and `GenerationInProgressError` go in `apps/credits/exceptions.py`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/pytest` (SQLite suite) | all unit/view tests | yes | pytest 8.3.3 | — (system python lacks Django) |
| PostgreSQL server binaries (`initdb`, `pg_ctl`, `psql`) | `pg_concurrency` tests locally | yes (`/opt/homebrew/bin`, Homebrew `postgresql@14`) | 14 (CI uses 16) | `make test-pg` against docker-compose `db`; docker at `/usr/local/bin/docker` |
| Docker | `make test-pg` | yes | — | throwaway `initdb` pattern from 29 plans (`pg_ctl -p 54329`) |
| psycopg | Postgres tests | yes | 3.2.3 | — |
| Redis | not needed (throttle cache is locmem in tests; DB lock, no Redis lock) | — | — | — |
| Real OpenAI / LangSmith | never (tests mock `_generate_reply_draft_with_log` / `call_openai_reply_generation` / `_get_reply_client`) | — | — | — |

Throwaway PG run command (from 29-02 plan, reuse): `D=$(mktemp -d) && initdb -D "$D" -U app --auth=trust && pg_ctl -D "$D" -o "-p 54329 -c unix_socket_directories=''" -w start && DATABASE_URL=postgres://app@localhost:54329/reviewmaster REQUIRE_PG=1 .venv/bin/pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs`. **Missing dependencies:** none blocking.

## Validation Architecture

(`workflow.nyquist_validation: true` in `.planning/config.json`.)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django + factory-boy; `--strict-markers --ds=config.settings.test` (SQLite `:memory:`) |
| Config file | `pyproject.toml` (addopts L155, markers L157-158); root `conftest.py` (pg auto-skip / `REQUIRE_PG`) |
| Quick run command | `.venv/bin/pytest apps/credits apps/reviews/tests/test_reply_generation_service.py apps/reviews/tests/test_views.py apps/integrations/openai -x -q --no-cov` |
| Full suite command | `.venv/bin/pytest --cov=apps --cov-fail-under=85 -q` |
| Postgres command | see Environment Availability (throwaway PG) or `make test-pg` |
| Extra gates | `.venv/bin/mypy .`; `.venv/bin/ruff check . && .venv/bin/ruff format --check .`; `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py makemigrations --check --dry-run`; `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py spectacular --file /dev/null --validate` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CCON-01 / SC1 | Org Admin and in-scope Staff generate: cost deducted, `credits_charged`/`credits_remaining` returned; out-of-scope Staff 404 and no reservation | integration (view) | `.venv/bin/pytest apps/reviews/tests/test_views.py -k generate_reply -x -q --no-cov` | modify (Wave 0) |
| CCON-01 | reserve -> call outside txn -> commit lifecycle; one consumed AuditLog; ledger reconciles | unit | `.venv/bin/pytest apps/credits/tests/test_consumption.py apps/reviews/tests/test_reply_generation_credits.py -x -q --no-cov` | new (Wave 0) |
| D-07 | OpenAI call inside an `atomic` raises `RuntimeError`; default `django_db` tests are not flagged | unit | `.venv/bin/pytest apps/reviews/tests/test_reply_generation_credits.py -k atomic -x -q --no-cov` | new |
| CCON-02 / SC3 | N threads vs K credits: exactly floor(K/cost) succeed, rest 402, `consumed <= allocated+bonus`, ledger reconciles | pg_concurrency | PG command with `-k n_threads` | new in `apps/credits/tests/test_pg_concurrency.py` and `apps/reviews/tests/test_pg_reply_concurrency.py` |
| D-12 | Same-review N threads: exactly one success, others 409, no extra reservation (real lock) | pg_concurrency | PG command with `-k same_review` | new |
| CCON-02 | First-use + reserve race (no pre-created balance) yields one balance row, one INITIAL row, no overspend | pg_concurrency | PG command with `-k first_use_reserve` | new |
| CCON-03 / SC2 | 402 `not_enabled` (allocated+bonus == 0, **no balance row written**) vs `exhausted`; body `{code, reason, required, remaining}`; no reservation | unit + view | `.venv/bin/pytest apps/credits/tests/test_consumption.py apps/reviews/tests/test_views.py -k "402 or insufficient" -x -q --no-cov` | new |
| CCON-04 / SC2 | Empty and whitespace-only comment -> 400 `empty_comment`, zero ledger/balance writes, zero AiUsageLog | view | `.venv/bin/pytest apps/reviews/tests/test_views.py -k empty_comment -x -q --no-cov` | new |
| CCON-05 / SC4 | Outcome matrix: success -> COMMITTED; output block -> COMMITTED + MODERATED log linked; input block -> REFUNDED; OpenAI transient/permanent -> REFUNDED; unexpected Exception -> REFUNDED; `BaseException` -> REFUNDED (finally); one consumed/refunded AuditLog per request; balance returns to pre-reserve value after refund | unit | `.venv/bin/pytest apps/reviews/tests/test_reply_generation_credits.py -x -q --no-cov` | new |
| CCON-05 | Double refund impossible; refund after commit impossible; settle failure does not mask outcome (row stays RESERVED) | unit | `.venv/bin/pytest apps/credits/tests/test_consumption.py -k "double or masks" -x -q --no-cov` | new |
| D-01/D-02 | Late commit: REFUNDED row + capacity -> new COMMITTED row, consumed re-incremented, AuditLog `late_commit` outcome `rededucted`; no capacity -> `free_draft`; row already COMMITTED -> `already_settled`, **no second charge**; never raises/500; ledger reconciles in all three | unit | `.venv/bin/pytest apps/credits/tests/test_consumption.py -k late -x -q --no-cov` | new |
| D-03 | Disconnect-style cancellation: executor-thread orchestrator still settles (probe-style test with `ThreadSensitiveContext` + cancel), on PG | pg_concurrency | PG command with `-k abort` | new (optional but recommended) |
| CCON-06 / SC4 | Exactly one AiUsageLog row per request in every branch; committed ledger row's `ai_usage_log_id` equals that row's pk; refunds link only when id known | unit | `.venv/bin/pytest apps/reviews/tests/test_reply_generation_credits.py -k usage_log -x -q --no-cov` | new |
| F1 | `transition_status(..., ai_usage_log_id=)` links atomically with the status, no-op on a lost CAS, other columns still immutable | unit | `.venv/bin/pytest apps/credits/tests/test_append_only.py -x -q --no-cov` | modify (Phase 29 file) |
| F4 | `ContentModeratedException` carries `stage`/`usage_log_id`; `None` with `review=None`; enrichment still passes | unit | `.venv/bin/pytest apps/integrations/openai/tests/test_guardrails.py apps/reviews/tests/test_enrichment_service.py -x -q --no-cov` | modify |
| CCON-07 / SC1 | 200 body keys exactly `{draft, credits_charged, credits_remaining}`; 422/502 bodies per D-09 table (cost vs 0; remaining current); 422 never leaks categories or review text | view | `.venv/bin/pytest apps/reviews/tests/test_views.py -k generate_reply -x -q --no-cov` | modify |
| CCON-07 / SC1 | `credit-cost`: Org Admin ok, Staff in-scope ok, Staff out-of-scope 404, cross-tenant 404, Superadmin per existing queryset behaviour; returns `{cost, remaining, is_enabled}`; whitespace-only -> `cost: 0`; never writes (no INSERT/UPDATE/DELETE captured); cost equals what generate charges; query ceiling fixed for 2 vs 10 reviews; 429 on its scope | view | `.venv/bin/pytest apps/reviews/tests/test_views.py -k credit_cost -x -q --no-cov` | new |
| CCON-08 / SC5 | `_get_reply_client` calls `with_options(timeout=30, max_retries=1)`; shared client and enrichment path untouched; `APITimeoutError` -> `OpenAITransientError` with exactly one `create` call; traced function still invoked | unit | `.venv/bin/pytest apps/integrations/openai/tests/test_client.py -x -q --no-cov` | modify/new |
| CCON-08 / D-06 | Settings margin: `TTL*60 >= 2*timeout*(max_retries+1)`; (if OQ-1) whole-request budget; throttle `generate_reply == "10/minute"`; `credit_cost` rate exists | unit | `.venv/bin/pytest apps/credits/tests/test_settings.py -x -q --no-cov` | modify (Phase 29 file) |
| CQA-02 / SC5 | Whole Phase 19/20 generate-reply suite green with credits; deploy note exists with the three required topics | unit + file check | `.venv/bin/pytest apps/reviews apps/integrations -q --no-cov` and `test -s docs/sre/v0.9-credits-rollout.md && grep -c "monthly_credit_allocation" docs/sre/v0.9-credits-rollout.md` (>= 1) | new doc |
| Phase gate | Coverage >= 85%, mypy strict, ruff, migrations clean (expect **no** new credits migration), spectacular validate | gate | commands above | — |

### Sampling Rate
- **Per task commit:** the single new/modified test file for that task with `--no-cov` (< 30 s).
- **Per wave merge:** Quick run command above + the throwaway-PG `pg_concurrency` run (all marked tests green, none skipped; `REQUIRE_PG=1`).
- **Phase gate:** Full suite with coverage, mypy, ruff, `makemigrations --check`, `spectacular --validate`, PG run, then `/gsd-verify-work`. Post-push: confirm CI `backend-pg` job green.

### Wave 0 Gaps
- [ ] F1 extension to `cas_status`/`transition_status` (+ tests in `apps/credits/tests/test_append_only.py`) if the Phase 29 executor has not already added it
- [ ] `apps/credits/tests/test_consumption.py` (reserve, commit, refund, late, 409, 402, double-settle, reconcile)
- [ ] `apps/reviews/tests/test_reply_generation_credits.py` (orchestrator outcome matrix, guard, usage-log link, one-AiUsageLog-per-branch)
- [ ] `apps/reviews/tests/test_pg_reply_concurrency.py` and additions to `apps/credits/tests/test_pg_concurrency.py`
- [ ] Credits-enabled fixture/trait for `OrganisationFactory` users in view tests (do not change the factory default)
- [ ] Re-point `TestGenerateReplyEndpoint` patches; update T-20-LK key-set tests
- [ ] Phase 29 contract re-verification step at the top of Plan 30-01 (grep the symbols in the contract table; fail fast if `credit_cost`, `get_shop_credit_balance`, `CreditBalanceView` are absent)

**N-threads-vs-K-credits design (reuse the Phase 29 harness verbatim):** `@pytest.mark.pg_concurrency` + `@pytest.mark.django_db(transaction=True)`; org `monthly_credit_allocation=10`; one shop; **12 distinct reviews** with `comment="x"*150` (cost 2, so no 409 noise); `threading.Barrier(12)`; each thread loads `Review.objects.select_related("shop__organisation").get(pk=...)` inside the thread and calls `generate_reply_with_credits` with `_generate_reply_draft_with_log` patched (process-global patch, applied once outside the threads) to `("draft", None)` after a short sleep to widen the window; collect `(ok, exc_class)` per thread; `connections.close_all()` in `finally`. Assert: no unexpected errors; exactly 5 successes and 7 `InsufficientCreditsError(exhausted)`; `balance.consumed_credits == 10 <= allocated + bonus`; 5 COMMITTED rows; `assert_ledger_reconciles(balance)`; AuditLog `shop.credits.consumed` count == 5. Variants: cost 3 vs K=10 (3 succeed, 1 credit left); mixed failures (half of calls raise `OpenAITransientError` -> refunded -> later requests succeed, final reconcile); same-review 8 threads (exactly 1 success, 7 `GenerationInProgressError`); first-use race (no pre-created balance). A credits-level variant calling `reserve_credits` directly (no review/OpenAI) belongs in `apps/credits/tests/test_pg_concurrency.py` so credits is testable without reviews.

## Security Domain

(`security_enforcement` absent in config => enabled.) Mandatory subagent reviews before PR: `ai-enrichment-specialist` (touches `apps/integrations/openai/`, locked), `tenant-security-auditor` (Staff scope on generate and `credit-cost`), `orm-performance-auditor` (new queries, locking, query-count tests); run the `security-checklist` and `feature-impact` skills.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (existing) | DRF session auth + `IsOrgScoped`; no change |
| V3 Session Management | no change | — |
| V4 Access Control | **yes** | `get_object()` tenant + `StaffAccessScope` scoping on both generate and `credit-cost`; shop/org for credits derived from the Review row, never from request data; Staff cannot reach out-of-scope reviews (404) |
| V5 Input Validation | yes | `GenerateReplySerializer` tone ChoiceField; `required`/`remaining` ints from server only |
| V6 Cryptography | no | — |
| V7 Error handling/logging | yes | No review text/draft in logs, audit payloads, or Sentry messages (CLAUDE.md §22); 422 body never leaks moderation categories (T-20-LK) |
| V11 Business logic | **yes** | Guarded UPDATE + CHECK against overspend; CAS against double settle/refund; per-review in-flight guard; throttle 10/min unchanged |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Concurrent requests overspend a shop's credits | Tampering | Row lock + guarded `F()` UPDATE + DB CHECK; PG N-threads test |
| Double refund / refund-after-commit / reaper vs late commit | Tampering | CAS on `status=RESERVED` gates every balance change; refund decrement only after a won CAS |
| Free generation via forced client abort | Elevation/Repudiation | Settlement in server-side `finally` (F5); abort cannot skip consume |
| Replay / double-click draining credits | DoS | D-12 409 guard, 10/min throttle, no free retry (D-11 accepts each retry charges) |
| Cross-tenant balance or cost read via `credit-cost` | Information disclosure | `get_object()` scoping; tenant-security-auditor + cross-org tests |
| Credit read path writing rows (locking allocation) | Tampering | Read-only selector pre-check; never-writes test on `credit-cost` and on the 402 path |
| Review text / draft in logs or audit | Information disclosure | Ids-only logging; payload tables above |
| Stale RESERVED row blocks a review indefinitely | DoS (self) | Reaper (Phase 31); TTL 5 min; worst-case request budget << TTL |
| Hung OpenAI/moderation call holds a request thread | DoS | Reply-path timeout + retry cap; no DB lock held during the call (reserve commits first) |

## Project Constraints (from CLAUDE.md)

- §5: thin views; business logic in `services/`; no multi-step workflow in views; Celery not involved here.
- §6.11/6.12: multi-step writes in `transaction.atomic()`; `select_for_update` for critical counters; §6.9 query-count tests with fixed ceilings; §6.10 `F()` for batch counters.
- §8: explicit permissions and throttling on every endpoint (including the new `credit-cost`); DRF exception handler; drf-spectacular schemas (§24 step 11).
- §9/§22: tenant scoping from the caller's organisation; Staff scope enforced in the queryset (`ReviewViewSet.get_queryset`); never log review text.
- §14: one combined OpenAI call per review; **exactly one `AiUsageLog` row per request**; never bypass the log; tests never hit real OpenAI (mock `_get_reply_client` / `_generate_reply_draft_with_log`).
- §16: pytest + factory-boy; 85% coverage; `django_db(transaction=True)` + Barrier for races; Mock Google/OpenAI.
- §24: requirements-first gate (CCON-01..08, CQA-02 exist in REQUIREMENTS.md), simplicity and surgical scope (skip the partial unique index; no frontend change; do not touch `list_shops`), run `code-reviewer` + `orm-performance-auditor` + `tenant-security-auditor` before PR; `pre-commit run --all-files`.
- §27: mandatory `ai-enrichment-specialist` review (this phase touches `apps/integrations/openai/`).
- `.claude/rules/openai-enrichment.md`: reply path still one call, `AiUsageLog` always written, PII never logged; `.claude/rules/drf-views.md`, `testing-python.md` (descriptive names `test_<behavior>_when_<condition>`, factories not `.objects.create()`).
- Ruff DJ012 model member order; mypy strict (`apps/credits` already strict-clean); line length 100.

## Sources

### Primary (HIGH confidence) - verified this session
- Repository files read: `30-CONTEXT.md`, `29-CONTEXT.md`, `29-02-PLAN.md`, `29-03-PLAN.md`, `apps/credits/{models,managers,exceptions}.py`, `apps/credits/services/{allocation,periods,ledger}.py`, `apps/credits/tests/{factories,conftest,helpers,test_pg_concurrency}.py`, `apps/reviews/{views,serializers}.py`, `apps/reviews/services/reply_generation.py`, `apps/integrations/openai/{client,guardrails,exceptions}.py`, `apps/reviews/tests/{test_views,test_reply_generation_service}.py`, `apps/integrations/openai/tests/test_client.py`, `config/settings/base.py`, `config/asgi.py`, `frontend/src/widgets/review-management/{api.ts,ReplyComposer.tsx}`, `docs/in-progress/Requirements_Credits_System.md` §6/§10, `.planning/research/{SUMMARY,PITFALLS}.md`, `.planning/ROADMAP.md` Phase 30, `.planning/REQUIREMENTS.md`.
- Runtime probes (scratchpad, not in repo): `openai==2.33.0` `with_options` signature/behaviour and `APITimeoutError` MRO; asgiref 3.11.1 cancel probes (plain and inside `ThreadSensitiveContext`); pytest probe for the `atomic_blocks`/`_from_testcase` guard; SQLite guarded-`F()` update probe.
- Installed library source: `django/core/handlers/asgi.py` (`handle`, `__call__`), `asgiref/sync.py` (`SyncToAsync.__call__`), `django/db/transaction.py`.

### Secondary (MEDIUM confidence)
- `.planning/research/SUMMARY.md` items #2, #3, #8 (milestone research, consistent with code reading).

### Tertiary (LOW confidence)
- Cloud Run timeout/CPU-throttling behaviour (A1), Sentry integration defaults (A2), SDK retry-policy details (A7): training knowledge, flagged `[ASSUMED]`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies; versions read from the venv.
- Architecture: HIGH for the reserve/settle/orchestrator design and disconnect behaviour (probe-verified); MEDIUM for Phase 29 interfaces not yet on disk (`credit_cost`, selectors) and the F1 extension, which depends on the 29-02 executor.
- Pitfalls: HIGH - each tied to a read line or a probe.

**Research date:** 2026-11-11
**Valid until:** 2026-11-25 (fast-moving: Phase 29 interfaces change until 29-03 lands; re-verify the contract table before executing)
