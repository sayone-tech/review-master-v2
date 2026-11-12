# Phase 30: Metered AI Reply Generation - Pattern Map

**Mapped:** 2026-11-11
**Files analyzed:** 17 (new or modified)
**Analogs found:** 17 / 17

All analog paths below are git-tracked (checked via `git ls-files apps/credits`). Line numbers refer to files on disk at mapping time. Phase 29 is mid-execution, so `get_shop_credit_balance` and `CreditBalanceView` (29-03) are not yet on disk. Cite `.planning/phases/29-credits-ledger-foundation/29-03-PLAN.md` for them and re-verify before executing (30-RESEARCH "Wave 0 Gaps").

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/credits/services/consumption.py` (new) | service | CRUD, row-lock | `apps/credits/services/allocation.py` (+ `ledger.py`) | role-match |
| `apps/credits/managers.py` (mod: `cas_status` + `ai_usage_log_id`) | model manager | CRUD | itself, L28-35 | exact |
| `apps/credits/services/ledger.py` (mod: `transition_status` kwarg) | service | CRUD | itself, L19-42 | exact |
| `apps/credits/exceptions.py` (mod: `InsufficientCreditsError`, `GenerationInProgressError`) | exception | n/a | itself | exact |
| `apps/reviews/services/reply_generation.py` (mod: `_generate_reply_draft_with_log`, `generate_reply_with_credits`, `ReplyResult`, wrapper exceptions) | service/orchestrator | request-response | itself, L84-179 | exact |
| `apps/reviews/views.py` (mod: `generate_reply` ladder, `credit_cost` action, `get_throttles`) | controller | request-response | itself, L91-104, L270-460 | exact |
| `apps/integrations/openai/client.py` (mod: `_get_reply_client`, `APIConnectionError` mapping) | utility | request-response | itself, L50-67, L292-307, L365-394 | exact |
| `apps/integrations/openai/guardrails.py` (mod: `stage` / `usage_log_id`, optional client options) | service | request-response | itself, L139-141, L196-338 | exact |
| `apps/integrations/openai/exceptions.py` (mod: `ContentModeratedException` kwargs) | exception | n/a | `OpenAIPermanentError.__init__` (`status_code` kwarg) | exact |
| `config/settings/base.py` (mod: reply timeout and retries settings, `credit_cost` throttle rate) | config | n/a | settings at ~L233-238, ~L417-418 | exact |
| `apps/credits/tests/test_consumption.py` (new) | test | CRUD | `apps/credits/tests/test_allocation.py`, `test_append_only.py` | role-match |
| `apps/credits/tests/test_pg_concurrency.py` (mod: add N-threads-vs-K-credits tests) | test | concurrency | itself, L1-110 | exact |
| `apps/reviews/tests/test_pg_reply_concurrency.py` (new) | test | concurrency | `apps/credits/tests/test_pg_concurrency.py` | exact |
| `apps/credits/tests/test_settings.py` (mod: TTL margin test) | test | config | itself | exact |
| `apps/credits/tests/test_append_only.py` (mod: `ai_usage_log_id` linking) | test | CRUD | itself | exact |
| `apps/reviews/tests/test_reply_generation_credits.py` (new) and `test_views.py` (mod) | test | request-response | `apps/reviews/tests/test_views.py::TestGenerateReplyEndpoint` (L407+) | exact |
| `docs/sre/v0.9-credits-rollout.md` (new) | docs | n/a | other files in `docs/sre/` | partial |

## Pattern Assignments

### `apps/credits/managers.py` and `apps/credits/services/ledger.py` (D-14, D-17)

**Analog:** the existing CAS code. `cas_status` is at `managers.py` L28-35. `transition_status` is at `ledger.py` L19-42.

Current CAS (managers.py L28-35):
```python
def cas_status(self, *, pk: int, from_status: str, to_status: str) -> int:
    return models.QuerySet.update(self.filter(pk=pk, status=from_status), status=to_status)
```

Change: add `ai_usage_log_id: int | None = None` to both functions, and thread it through from `transition_status` to `cas_status`. Write it in the same single UPDATE:
```python
fields: dict[str, Any] = {"status": to_status}
if ai_usage_log_id is not None:
    fields["ai_usage_log_id"] = ai_usage_log_id
return models.QuerySet.update(self.filter(pk=pk, status=from_status), **fields)
```

Rules:
- Keep the `ALLOWED_STATUS_TRANSITIONS` check and the `won = (... == 1)` pattern in `transition_status` unchanged.
- Do not make any other column writable.
- Extend `test_append_only.py`:
  - linking works on a won CAS;
  - the FK stays NULL on a lost CAS;
  - `credits_delta` and `note` stay unwritable;
  - the source-scan test that only `ledger.py`, `models.py` and `managers.py` mention `cas_status(` still holds.

### `apps/credits/services/consumption.py` (service, row-locked CRUD)

**Analog:** `apps/credits/services/allocation.py`.

**Imports and conventions** (L16-27):
```python
from __future__ import annotations
import logging
from django.db import transaction
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
logger = logging.getLogger(__name__)
```
All functions are keyword-only (`def f(*, shop_id: int, ...)`). The module must not import `apps.reviews`. Pass plain IDs and ints.

**Lazy balance and audit pattern** (allocation.py L30-71):
- Call `ensure_balance(shop_id=...)` OUTSIDE the reserve atomic, as it has its own atomic.
- Audit rows follow this shape:
```python
AuditLog.objects.create(
    organisation_id=organisation_id, actor=None,
    entity_type="shop", entity_id=str(shop_id),
    action="shop.credits.allocated", before_data=None,
    after_data={"period_year": ..., "period_month": ..., "allocated_credits": allocation},
)
```
New actions: `shop.credits.consumed`, `shop.credits.refunded`, `shop.credits.late_commit`.
- Use `actor_id` = the requesting user, `None` for the reaper.
- Payloads carry ids and ints only, never review text (CLAUDE.md §22).

**Core pattern:** 30-RESEARCH.md Patterns 1-3 give the full sketches:
- `reserve_credits`:
  1. Read-only `get_shop_credit_balance` pre-check (D-19). Cite the 29-03 plan for it.
  2. `ensure_balance`.
  3. `atomic { select_for_update(of=("self",)).get(pk=...)`; `RESERVED` CONSUMPTION `exists()` by `review_id` raises 409; guarded `.filter(consumed_credits__lte=F("allocated_credits")+F("bonus_credits")-credits).update(consumed_credits=F(...)+credits, updated_at=timezone.now())`; `CreditTransaction.objects.create(...)` }`.
- `commit_reservation`: CAS only, no balance change. On a lost CAS, re-read the status (D-16):
  - REFUNDED -> one guarded re-deduct on the current-month balance, or a free draft;
  - COMMITTED -> `already_settled` audit, never re-deduct;
  - past or lapsed month -> free draft, audited.
- `refund_reservation(*, transaction_id, reason, ai_usage_log_id=None)`: inside one atomic, a won CAS, then guarded `consumed_credits__gte=credits` decrement by `F()`. Raise `RuntimeError` on a miss so the CAS rolls back. Phase 31's reaper reuses this name.

**Anti-patterns** (from the Phase 29 contract):
- Never use `select_related` together with `select_for_update`.
- Never use `.update()` or `.save()` on a `CreditTransaction` for anything but the CAS.
- Always set `updated_at` explicitly, because `QuerySet.update` does not fire `auto_now`.
- Settle via `tx.shop_credit_balance_id`, never a recomputed period.

### `apps/credits/exceptions.py`

**Analog:** the current file. All exceptions are plain `Exception` subclasses with `# noqa: N818` and a docstring.

New classes:
```python
class InsufficientCreditsError(Exception):  # noqa: N818
    def __init__(self, *, reason: str, required: int, remaining: int) -> None:
        super().__init__(reason); self.reason = reason; self.required = required; self.remaining = remaining
class GenerationInProgressError(Exception):  # noqa: N818
    ...
```
`EmptyCommentError` goes in `reply_generation.py` (OQ-5).

### `apps/reviews/services/reply_generation.py` (orchestrator)

**Analog:** the same file.
- `_write_failure_log` is at L56-81.
- `generate_reply_draft` is at L84-179, with the `moderate_input` -> `call_openai_reply_generation` -> `moderate_output` -> `AiUsageLog.objects.create(...)` chain.

Refactor (D-14, F4):
1. Rename the body to `_generate_reply_draft_with_log(*, review, tone) -> tuple[str, int]`, returning `AiUsageLog.objects.create(...).pk` alongside the draft (L163-179).
2. `generate_reply_draft` becomes `return _generate_reply_draft_with_log(review=review, tone=tone)[0]`.
3. Keep the L96-97 tone allow-list check and the existing import block (L24-45).
4. Update the module docstring "Idempotency" paragraph (L13-16), which is now stale.

Add `generate_reply_with_credits`. Copy the full skeleton from 30-RESEARCH Pattern 4:
- a `try/except/finally` with settlement in `finally`;
- a default outcome of refund (D-04);
- `_assert_no_open_transaction()` (D-07/D-18):
```python
if any(not getattr(b, "_from_testcase", False) for b in connection.atomic_blocks):
    raise RuntimeError("OpenAI call must not run inside a database transaction")
```
- wrapper exceptions `ReplyModeratedError` and `ReplyUnavailableError`, raised AFTER settlement, carrying `credits_charged` and `credits_remaining`. They must not subclass `OpenAIError` or `APIException`;
- `_settle` swallows its own errors with `logger.exception` and ids only.

Existing exception ordering to preserve, from `views.py` L405-451: `ContentModeratedException` is caught BEFORE `OpenAITransientError`/`OpenAIPermanentError`, because it inherits `OpenAIError`.

Per D-15, pass the reply-bounded options to `moderate_input` and `moderate_output`. Fix the strict side-effect signatures in `test_reply_generation_service.py` (~L427-445) by adding `**_kw`.

### `apps/reviews/views.py`

**Analog:** the same file.

**get_throttles** (L91-104). Add a branch following the WR-02 pattern:
```python
if self.action == "generate_reply":
    self.throttle_scope = "generate_reply"
elif self.action == "reply":
    self.throttle_scope = "review_reply"
elif self.action == "credit_cost":      # NEW
    self.throttle_scope = "credit_cost"
return super().get_throttles()
```
The `credit_cost` scope needs a `DEFAULT_THROTTLE_RATES` entry, otherwise it raises `ImproperlyConfigured`. Also pass `throttle_classes=[ScopedRateThrottle]` on the `@action` (see L384).

**generate_reply body** (L386-460). Keep this structure:
```python
review = self.get_object()
serializer = GenerateReplySerializer(data=request.data)
serializer.is_valid(raise_exception=True)
tone = serializer.validated_data["tone"]
try: ... except ContentModeratedException: ... except (OpenAITransientError, OpenAIPermanentError): ...
except APIException: raise
except Exception: logger.exception(...); return 502
```
Changes:
1. Replace the `generate_reply_draft` import (L63) with the orchestrator.
2. The ladder becomes `EmptyCommentError` 400, `InsufficientCreditsError` 402, `GenerationInProgressError` 409, `ReplyModeratedError` 422, `ReplyUnavailableError` 502. This precedes `APIException`, then `Exception`. Credit fields are added to every body per D-09.
3. Keep the byte-exact 422 `detail` string "AI reply isn't available for this review. Please write your reply manually." (T-20-LK). Add only the two integers.
4. Success body is `{draft, credits_charged, credits_remaining}`.
5. Extend the `@extend_schema` block (L276-379): the 200 `inline_serializer`, plus new `OpenApiResponse` entries for 400/402/409 and updated 422/502 fields. Follow the `inline_serializer(name=..., fields={...})` style at L282-300.

**credit-cost action.** Use the `@action(detail=True, methods=["get"], url_path="credit-cost", throttle_classes=[ScopedRateThrottle])` shape. Call `self.get_object()` (same Staff scoping as `get_queryset`, L106-125). Import `credit_cost as compute_credit_cost` to avoid shadowing the method name. Never write.

**get_queryset note.** It already does `select_related("shop__organisation")` and applies Staff scope via `get_accessible_shop_ids` (L106-125).

### `apps/integrations/openai/client.py`

**Analog:** the same file.

**Shared client** (L50-55). Do not touch it:
```python
def _get_client() -> OpenAI: ...
```

Add:
```python
def _get_reply_client() -> OpenAI:
    return _get_client().with_options(
        timeout=settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS,
        max_retries=settings.REVIEWBEE_REPLY_OPENAI_MAX_RETRIES,
    )
```

In `_do_chat_completions_create` (L292-307):
- Swap `_get_client()` for `_get_reply_client()`.
- Add `openai.APIConnectionError` to the `except` clause, mapped to `OpenAITransientError(str(exc))` on the reply path only. Do not change `_map_openai_error` (L58-67), which enrichment shares. This avoids the untraced duplicate-call fallback at L390-394.

LangSmith tracing is an `@traceable` decorator (L365), not a wrapped client, so it is unaffected.

Tests that patch `_get_client` (`test_client.py` L289, 321, 342, 363) should be re-pointed to `_get_reply_client`, or set `fake_client.with_options.return_value = fake_client`.

### `apps/integrations/openai/guardrails.py` and `exceptions.py`

**Analog for the exception:** `OpenAIPermanentError` in `exceptions.py`, which takes a keyword-only extra attribute:
```python
def __init__(self, message: str, *, status_code: int | None = None) -> None:
    super().__init__(message); self.status_code = status_code
```
Mirror this for `ContentModeratedException(message="", *, stage=None, usage_log_id=None)`.

**guardrails.py plumbing:**
- `_persist_moderated_log` (L196+) returns `None` today. Change it to `-> int | None` and return `AiUsageLog.objects.create(...).pk`.
- Raise sites:
  - L292: `raise ContentModeratedException("input flagged", stage="input", usage_log_id=usage_log_id)`.
  - L338: the output variant, with `stage="output"`.
- Capture `usage_log_id = _persist_moderated_log(...)` inside the `if review is not None:` branches. Use `None` otherwise.
- `_call_moderation_api` (L139-141) currently uses `_get_client()`. Add optional `timeout` and `max_retries` parameters. Apply `with_options` only when they are provided, so enrichment and `test_guardrails.py` patches are unaffected. Thread these through `_moderate_with_retry`, `moderate_input` and `moderate_output`.
- Enrichment catches the exception at `enrichment.py:562` and ignores kwargs, so optional kwargs are safe.

### `config/settings/base.py`

**Analog:** existing settings:
- Credits settings at ~L233-238: `REVIEWBEE_CREDIT_TIERS`, `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5`.
- Throttle rates at ~L417-418: `"review_reply": "30/minute"`, `"generate_reply": "10/minute"`.

Add:
- `REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS = env.int(..., default=30)`
- `REVIEWBEE_REPLY_OPENAI_MAX_RETRIES = env.int(..., default=1)`
- `"credit_cost": "120/minute"` (rate is an assumption, A4)

The TTL stays a literal 5. Leave it.

### Tests

**`apps/credits/tests/test_pg_concurrency.py`** (and the new `apps/reviews/tests/test_pg_reply_concurrency.py`). Copy the harness verbatim (L1-110):
```python
@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_...():
    barrier = threading.Barrier(N_THREADS)
    results, errors, lock = [], [], threading.Lock()
    def worker():
        try:
            barrier.wait(timeout=10)
            ...
        except Exception as exc:
            with lock: errors.append(repr(exc))
        finally:
            connections.close_all()
    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    # start / join(timeout=30)
    assert not errors, errors
```
Use `OrganisationFactory(monthly_credit_allocation=...)` and `ShopFactory(organisation=org)`. Close with `assert_ledger_reconciles(balance)`, imported from `apps/credits/tests/helpers.py`. It asserts `consumed_credits == SUM(-delta)` over RESERVED/COMMITTED CONSUMPTION rows.

Design (from 30-RESEARCH): 12 distinct reviews with `comment="x"*150` (cost 2) against 10 credits, which gives 5 successes and 7 `InsufficientCreditsError`. Variants:
- cost 3 vs K=10;
- mixed failures that are refunded;
- same-review 8 threads, one success and the rest `GenerationInProgressError`;
- first-use race.

Add a credits-level variant that calls `reserve_credits` directly in `apps/credits/tests/test_pg_concurrency.py`.

**`apps/credits/tests/test_settings.py`.** Follow its flat module-level test style (L11-40). Add:
- `settings.REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES * 60 >= 2 * timeout * (max_retries + 1)` (D-06);
- the stricter whole-request budget from D-15 (~182 s < 300 s);
- `throttle rates["generate_reply"] == "10/minute"`;
- a `credit_cost` rate exists.

Test names follow `test_<behavior>_when_<condition>` (`.claude/rules/testing-python.md`).

**`test_views.py::TestGenerateReplyEndpoint`** (L407+):
- Current seam: `@patch("apps.reviews.views.generate_reply_draft")`, with `OrganisationFactory()`, `OrgAdminFactory(organisation=org)`, `ReviewFactory(organisation=org)`, `APIClient().force_authenticate(user=user)`, and `_generate_reply_url(review.pk)`.
- Re-point to `apps.reviews.services.reply_generation._generate_reply_draft_with_log` (returns `("draft", None)`).
- Give the org `monthly_credit_allocation=10`. The org factory default stays 0.
- Update the exact-dict and key-set assertions (T-20-LK) to `{"code","detail","credits_charged","credits_remaining"}`. Keep the byte-exact `detail`, and add an assertion that no categories or review text appear in the body.
- Re-baseline the `<= 4` query-count ceiling, and add a fixed ceiling for `credit-cost`.
- Keep `caches["throttle"].clear()` in an autouse fixture, because locmem throttle state survives DB rollback.

## Shared Patterns

**Money-safety primitives** (apply to `consumption.py` and the orchestrator):
- The guarded `UPDATE ... WHERE consumed <= allocated+bonus-cost` is the overspend guard.
- The `UPDATE ... WHERE status='RESERVED'` CAS is the double-settle guard. Source: `managers.py` L28-35.
- The DB CHECK `credit_balance_no_overspend` is the last line of defence.

**Audit logging.** Source: `allocation.py` L59-71. Always `entity_type="shop"`, `entity_id=str(shop_id)`. Write the consumed or refunded row inside the same atomic as the CAS.

**No review text or draft in logs, audit rows or Sentry.** Log ids, cost and outcome only (CLAUDE.md §22, `.claude/rules/openai-enrichment.md`).

**Exactly one `AiUsageLog` row per request in every branch.** Existing contract: `_write_failure_log` (L56-81), the MODERATED rows from guardrails, and the SUCCESS row at the end of `generate_reply_draft`.

**Tenant and Staff scoping.** Derive shop and org from the Review row, never from request data. Source: `ReviewViewSet.get_queryset` (views.py L106-125). Apply it to both `generate_reply` and `credit-cost`.

**Throttling.** WR-02 `get_throttles` plus `ScopedRateThrottle` (views.py L91-104).

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `docs/sre/v0.9-credits-rollout.md` | runbook | Only the `docs/sre/` convention exists. It needs three topics: orgs start at 0 credits so replies return 402 `not_enabled`; setting `monthly_credit_allocation` via admin or shell until Phase 32; verification steps. Also note the F7 frontend caveat: between Phase 30 and 33 the composer shows a generic failure for 402/409. |
| `get_shop_credit_balance`, `CreditBalanceView` | selector | Not on disk yet (Phase 29-03). Cite `29-03-PLAN.md`, and re-verify the contract at the top of Plan 30-01. |

## Notes for the planner

- Prefer the app-level D-12 check only, with no partial unique index and no new credits migration (30-RESEARCH Pattern 3). This is the researcher's recommendation, so the planner decides.
- Mandatory reviews before PR: `ai-enrichment-specialist`, `tenant-security-auditor`, `orm-performance-auditor`.

## Metadata

**Analog search scope:** `apps/credits`, `apps/reviews`, `apps/integrations/openai`, `config/settings/base.py`.
**Pattern extraction date:** 2026-11-11
