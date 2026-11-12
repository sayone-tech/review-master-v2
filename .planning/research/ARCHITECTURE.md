# Architecture Patterns

**Domain:** Per-shop monthly AI Reply Credits, added to an existing multi-tenant Django 6 / DRF / Celery / React-widget platform
**Milestone:** v0.9 AI Reply Credits (subsequent milestone; integration-focused)
**Researched:** 2026-11-11
**Confidence:** HIGH. Every integration point below was read from the live code, not inferred from the spec.

---

## Recommended Architecture

Credits is a leaf bounded context. `apps/credits` owns the ledger and the reserve/commit/refund state machine. It knows nothing about OpenAI prompts or Google. The reviews app owns the orchestration of "reserve, then call AI, then commit or refund", because that is where the AI call already lives.

```
                    POST /api/v1/reviews/{id}/generate-reply/
                                    |
                        ReviewViewSet.generate_reply   (thin: map exceptions -> HTTP)
                                    |
          apps/reviews/services/reply_generation.py
          generate_reply_with_credits(review, tone, user)        <- NEW orchestrator
             |  1. guard empty comment      -> EmptyCommentError (400)
             |  2. cost = calculate_credit_cost(len(comment))    [credits.services.credit_cost]
             |  3. reserve_credits(...)     -> InsufficientCreditsError (402)   [credits.services.consumption]
             |  4. generate_reply_draft(...)   <- EXISTING, unchanged semantics, now also returns usage-log id
             |        moderate_input -> OpenAI -> pricing -> moderate_output -> AiUsageLog
             |  5a. success                 -> commit_reservation(tx, ai_usage_log_id)
             |  5b. input moderation block  -> refund_reservation(tx)   then re-raise
             |  5c. output moderation block -> commit_reservation(tx, ai_usage_log_id=MODERATED row)  then re-raise
             |  5d. any other exception     -> refund_reservation(tx)   then re-raise
             v
      apps/credits  (models, services, selectors, tasks, views)  ---- Celery Beat ---> lapse + reaper
```

### Component Boundaries

| Component | New / Modified | Responsibility | Communicates With |
|-----------|----------------|----------------|-------------------|
| `apps/credits/models.py` | NEW | `ShopCreditBalance`, `CreditTransaction` (string FKs only) | DB |
| `apps/credits/services/credit_cost.py` | NEW | Pure `calculate_credit_cost(comment_length)` reading `settings.REVIEWBEE_CREDIT_TIERS` | reviews orchestrator, cost endpoint, review serializer |
| `apps/credits/services/periods.py` | NEW | `current_period()` / `previous_period()` in UTC. Single source of the month boundary | consumption, lapse, selectors |
| `apps/credits/services/consumption.py` | NEW | `reserve_credits`, `commit_reservation`, `refund_reservation`. Idempotent state transitions | reviews orchestrator, reaper |
| `apps/credits/services/allocation.py` | NEW | `get_or_create_current_balance` (lazy), `allocate_bonus_credits` (Superadmin) | consumption, superadmin view |
| `apps/credits/services/lapse.py` | NEW | Idempotent catch-up lapse of all past periods | `tasks.py` |
| `apps/credits/selectors/balances.py` | NEW | `get_shop_credit_state`, `list_transactions`, `annotate_credit_state(qs)` | shops selector, credits views |
| `apps/credits/tasks.py` | NEW | Thin `lapse_previous_month_credits_task`, `reap_stale_reserved_transactions_task` | Celery Beat |
| `apps/credits/views.py`, `urls.py` | NEW | Shop credits GET, history GET, Superadmin bonus POST and state GET | credits services/selectors |
| `apps/credits/exceptions.py` | NEW | `InsufficientCreditsError`, `EmptyCommentError` (plain exceptions; the view maps them, as `apps/shops/exceptions.py` does) | reviews view |
| `apps/reviews/services/reply_generation.py` | MODIFIED | Add `generate_reply_with_credits`; `generate_reply_draft` additionally surfaces the `AiUsageLog` pk | credits.services |
| `apps/reviews/views.py::generate_reply` | MODIFIED | Call orchestrator; add 402/400 mapping; add `cost` action; return `credits_used/credits_remaining` | orchestrator |
| `apps/integrations/openai/guardrails.py` + `exceptions.py` | MODIFIED (small) | `ContentModeratedException` gains `stage` and `usage_log_id` attributes | reviews orchestrator |
| `apps/integrations/openai/client.py` | MODIFIED (small) | Explicit request timeout on the reply call (see Pitfall in "Anti-Patterns") | OpenAI SDK |
| `apps/organisations/models.py`, `services/organisations.py`, `serializers.py` | MODIFIED | `monthly_credit_allocation` field, whitelist, audit `organisation.credits.set` | AuditLog |
| `apps/shops/selectors/shops.py::list_shops`, `serializers.py::ShopReadSerializer` | MODIFIED | Opt-in credit annotation + two read-only fields | credits.selectors |
| `config/settings/base.py`, `INSTALLED_APPS`, `CELERY_TASK_ROUTES` | MODIFIED | `apps.credits`, `REVIEWBEE_*` settings, task routes | |
| React: shop-management, review-management, org-management | MODIFIED | Credits card, badge, composer cost/remaining, Buy More modal, bonus modal, org form field | new endpoints |

### Data Flow

**Generate (happy path).** The view loads the review through `ReviewViewSet.get_queryset()`, which already enforces tenant and `StaffAccessScope`. The orchestrator computes cost from `len(review.comment.strip())`. `reserve_credits` opens one `transaction.atomic()`:

1. ensure the current-period balance row exists, creating it lazily with `allocated_credits = organisation.monthly_credit_allocation` and an `INITIAL_ALLOCATION` transaction;
2. `select_for_update()` the balance row;
3. raise `InsufficientCreditsError` if `allocated + bonus - consumed < cost`;
4. run `UPDATE ... SET consumed_credits = consumed_credits + cost` via `F()`;
5. insert a `CreditTransaction(type=CONSUMPTION, status=RESERVED, credits_delta=-cost, review_id, performed_by)`.

The transaction commits and the row lock is released **before** OpenAI is called. After the AI call, `commit_reservation` locks only the transaction row, flips `RESERVED -> COMMITTED`, stores `ai_usage_log_id`, and writes the `shop.credits.consumed` `AuditLog` row.

**Failure paths.** `refund_reservation` locks the transaction row, no-ops unless it is still `RESERVED`, decrements the balance via `F()`, and sets `REFUNDED`. The reaper calls the same function, so a slow view and the reaper racing each other cannot double-refund.

**Month lifecycle.** There are no pre-created rows. The first reserve of a UTC month creates the row. The Beat lapse task writes `LAPSED` transactions for any past-period balance with `remaining > 0`.

---

## Answers to the Specific Integration Questions

### 1. Where reserve/commit/refund wraps `generate_reply_draft`: a service wrapper, not the view and not inside the draft function

**Recommendation:** add `generate_reply_with_credits(*, review, tone, user)` to `apps/reviews/services/reply_generation.py`. The view calls only that.

Why not the view: a reserve/try/commit/refund workflow is a multi-step write workflow, which CLAUDE.md §5 forbids in views. The view's existing `except Exception -> 502` clause would also have to be threaded around credit calls.

Why not inside `generate_reply_draft`: it is currently pure OpenAI orchestration with a documented contract (one `AiUsageLog` row, raises, view maps). Burying credits inside it makes that function untestable without a credits fixture. It would also hide the input-versus-output moderation distinction the refund policy depends on.

The spec says to extend `apps/reviews/services/replies.py`. That is wrong for this codebase. `replies.py` is Google reply posting (`submit_reply`/`remove_reply`); the AI path is `reply_generation.py`. Use `reply_generation.py`.

```python
# apps/reviews/services/reply_generation.py  (new function; draft fn stays)
def generate_reply_with_credits(*, review: Review, tone: str, user: User) -> ReplyResult:
    comment = (review.comment or "").strip()
    if not comment:
        raise EmptyCommentError            # view -> 400
    cost = calculate_credit_cost(comment_length=len(comment))
    reservation = reserve_credits(         # raises InsufficientCreditsError -> 402
        shop_id=review.shop_id, organisation_id=review.organisation_id,
        review_id=review.pk, user_id=user.pk, cost=cost,
    )                                      # committed + lock released here
    try:
        draft, usage_log_id = _generate_reply_draft_with_log(review=review, tone=tone)
    except ContentModeratedException as exc:
        if exc.stage == "output":          # OpenAI was billed -> consume (locked decision)
            _safe(commit_reservation, reservation.pk, ai_usage_log_id=exc.usage_log_id)
        else:                              # input block -> refund (locked decision)
            _safe(refund_reservation, reservation.pk, reason="input_moderated")
        raise
    except Exception:
        _safe(refund_reservation, reservation.pk, reason="openai_failure")
        raise
    remaining = _safe(commit_reservation, reservation.pk, ai_usage_log_id=usage_log_id)
    return ReplyResult(draft=draft, credits_used=cost, credits_remaining=remaining)
```

Details that matter:

- **Keep `generate_reply_draft(review, tone) -> str` as a thin wrapper** over `_generate_reply_draft_with_log(...) -> (str, usage_log_id)`. Existing tests and any other caller keep working; only the new orchestrator uses the tuple form. This is the surgical option.
- **Moderation stage.** Today `ContentModeratedException` carries only a message string ("input flagged"/"output flagged"). Do not string-match it. Add `stage: Literal["input","output"]` and optional `usage_log_id`, set at the two raise sites in `guardrails.py`. `_persist_moderated_log` must return the created pk so the output-block case can link the MODERATED row. This is a small edit to a file shared with enrichment; the enrichment call sites are unaffected because the new kwargs are optional.
- **`_safe(...)`** wraps credit bookkeeping in try/except with `logger.exception`. A bookkeeping failure after the user already has a draft must not turn into a 502. If a refund fails, the reaper will pick the row up. If a commit fails, the reaper will wrongly refund it; accept that (rare, user-favourable) and log it.
- **Never use `transaction.atomic()` around the orchestrator.** `ATOMIC_REQUESTS` is not set (verified), and the reserve must commit before the OpenAI call. Existing guardrails also rely on moderated-log rows being written outside any atomic block (D-33).
- **Exception ordering in the view.** The existing view ends with `except APIException: raise` followed by `except Exception -> 502`. Put the new `except InsufficientCreditsError` (402) and `except EmptyCommentError` (400) **before** the generic `except Exception`, or they become 502s.
- **Response shape.** `200 {draft, credits_used, credits_remaining}`. The additive fields feed the toast ("X used, Y remaining") with no second request. `402 {code: "insufficient_credits", detail, required, remaining}`. `400 {code: "empty_comment"}`.
- **Throttle.** `generate_reply` stays at 10/min via the existing `get_throttles()` override. A 402 or 400 still consumes a throttle slot; that is fine.

### 2. Linking `CreditTransaction` to the `AiUsageLog` row written inside `generate_reply_draft`

The FK must point **credits -> openai**, never the reverse. Adding a `credit_transaction` FK to `AiUsageLog` would make `integrations.openai` depend on `credits`, inverting the layering.

- `CreditTransaction.ai_usage_log = ForeignKey("openai.AiUsageLog", null=True, blank=True, on_delete=SET_NULL, related_name="credit_transactions")`. The app label is `openai` (verified in `apps.py`), so the string reference is `"openai.AiUsageLog"`.
- **Success:** `_generate_reply_draft_with_log` captures the `.pk` of the row from `AiUsageLog.objects.create(...)`, which is already at the end of the function, and returns it. `commit_reservation(ai_usage_log_id=...)` stores it.
- **Output-moderation block:** the exception carries the MODERATED row's pk (see above), so the CONSUMPTION row links to the billed call.
- **Input-moderation block or OpenAI failure:** the transaction is REFUNDED. Link the MODERATED or FAILED row too if it is cheap. The input-moderation exception also carries `usage_log_id`. For a plain OpenAI failure, `_write_failure_log` currently returns `None`; leave it unlinked and put the reason in `notes`. The link is nullable by design and acceptance criterion 38 only requires that AiUsageLog still be written.
- Do **not** correlate after the fact by querying `AiUsageLog` on `(review, created_at)`. It is racy under double-clicks on the same review.
- Index `ai_usage_log` implicitly (FK); the `(shop, created_at)` and `(organisation, created_at)` indexes from the spec cover the history endpoint.

`AiUsageLog` has no `shop_id` and no user. Credits does not change that: `CreditTransaction` carries `shop`, `organisation`, `performed_by`, and `review`, which is the join the spec wants.

### 3. Annotating `remaining_credits` on the shops list without N+1

`list_shops()` in `apps/shops/selectors/shops.py` feeds both the template view `shop_list` and `ShopViewSet.list`, and `ShopReadSerializer` renders both. Annotate once in the selector, and surface via the serializer.

```python
# apps/credits/selectors/balances.py   (imports credits.models + periods only; NO shops/reviews imports)
from django.db.models import F, IntegerField, OuterRef, QuerySet, Subquery
from django.db.models.functions import Coalesce
from apps.credits.models import ShopCreditBalance
from apps.credits.services.periods import current_period

def annotate_credit_state(qs: QuerySet) -> QuerySet:          # qs is a Shop queryset
    year, month = current_period()                              # UTC, evaluated once per request
    bal = ShopCreditBalance.objects.filter(
        shop_id=OuterRef("pk"), period_year=year, period_month=month
    )
    total = Subquery(
        bal.annotate(t=F("allocated_credits") + F("bonus_credits")).values("t")[:1],
        output_field=IntegerField(),
    )
    used = Subquery(bal.values("consumed_credits")[:1], output_field=IntegerField())
    return qs.annotate(
        credits_total=Coalesce(total, F("organisation__monthly_credit_allocation")),
        credits_used=Coalesce(used, 0),
    ).annotate(remaining_credits=F("credits_total") - F("credits_used"))
```

Rules that make this correct:

- **Lazy rows mean "no row" is not "zero".** A shop with no balance row this month has `monthly_credit_allocation` credits available, so the `Coalesce` fallback to the org field is mandatory. Without it the badge shows 0 for every shop that has not yet used AI this month. The `organisation__...` reference is a forward FK join inside the same SQL statement, so there are no extra queries.
- Both subqueries hit the unique index `(shop_id, period_year, period_month)`, so each is one index probe per row. A page is at most 100 rows.
- **Opt-in, not default.** Add `with_credits: bool = False` to `list_shops`. It is also called with `active_only=True` for scope selectors (`organisations/views.py`), where the annotation is wasted work. Only the two list callers pass `with_credits=True`.
- **Serializer.** Add `remaining_credits` and `credits_total` to `ShopReadSerializer` as `IntegerField(read_only=True, default=None)`. The `default=None` is required because the same serializer renders `create` and `update` responses on un-annotated instances. DRF returns the default on `AttributeError`, as the existing `region_name` field already relies on. Add the fields to `read_only_fields` too.
- **Query-count test** (spec 14.8 #37): `CaptureQueriesContext` on `/api/v1/shops/` with 5 vs 25 shops, asserting an equal, fixed ceiling.
- Equivalent alternative: `FilteredRelation("credit_balances", condition=Q(period_year=..., period_month=...))` gives a single LEFT JOIN. It is equally N+1-safe because the unique constraint caps matches at one. Use it only if profiling shows the two subqueries matter; the Subquery form is the more explicit of the two.
- **Single shop detail** (`GET /shops/{id}/credits/`): the selector returns a dict from one query on the balance row. If no row exists, it synthesises `{allocated: org.monthly_credit_allocation, bonus: 0, consumed: 0}` and **never writes on a GET**. Lazy creation happens only in `reserve_credits` and the bonus service.
- **Reviews list:** do not add per-shop credits to `ReviewReadSerializer`. Expose only `credit_cost` (pure function of `comment`, `None` when empty, zero queries). The composer fetches `remaining` through the `cost` endpoint or the shop-credits endpoint on open.

### 4. App dependency direction (no cycles)

Import layering, low to high. An arrow means "may import":

```
common (AuditLog, TimeStampedModel)
  <- accounts (User, StaffAccessScope)
  <- organisations (Organisation + monthly_credit_allocation)
  <- shops (Shop)  <- reviews (Review)        integrations.openai (AiUsageLog)
                  \         |                 /
                   credits  (string-FK to shops, reviews, openai, organisations, AUTH_USER_MODEL)
  reviews.services.reply_generation  --imports-->  credits.services / credits.exceptions
  shops.selectors.shops              --imports-->  credits.selectors.balances
```

Rules to hold:

1. **`credits.models` and `credits.selectors.*` import nothing from `shops`, `reviews`, or `organisations` at module level.** All FKs are strings (`"shops.Shop"`, `"reviews.Review"`, `"organisations.Organisation"`, `"openai.AiUsageLog"`, `settings.AUTH_USER_MODEL`). This is what allows `shops.selectors` to import `credits.selectors` safely.
2. **`credits.services.*` may import `shops`/`organisations` models** (e.g. `Shop.objects.select_related("organisation")` to read the allocation). The reverse import (shops/organisations importing `credits.services`) must not happen. `shops` imports only `credits.selectors`.
3. **`credits` never imports `apps.reviews`.** The orchestrator passes plain values (`shop_id`, `review_id`, `cost`, `user_id`). The credits app never loads a `Review`. The cost function takes `comment_length: int`.
4. **`organisations` writes the `organisation.credits.set` audit row itself**, using `apps.common.models.AuditLog`. It does not call into credits.
5. **Migrations:** `credits/0001` depends on `organisations`, `shops`, `reviews`, `openai`, and the user model. The `organisations` migration adding `monthly_credit_allocation` has no credits dependency. Run it first.
6. **Credits views** need Staff shop scoping (spec criterion 28). `get_accessible_shop_ids` lives in `apps/reviews/selectors/reviews.py`. Import it in `credits/views.py` only (view layer; `reviews.selectors` does not import credits, so there is no cycle). Do not relocate it this milestone (surgical scope).

The cost-function location conflict (spec §4.3 says `apps/reviews/services/credit_cost.py`; §13.1 says credits) is already resolved to `apps/credits/services/credit_cost.py`. This layering supports that choice: the reviews serializer and cost endpoint import it from credits.

### 5. Beat schedule seeding

Follow the established pattern (`apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py`): a data migration with `RunPython(seed, remove)`, `get_or_create` on the schedule, and `update_or_create` on the `PeriodicTask` by name.

`apps/credits/migrations/0002_beat_seed_credit_tasks.py`:

| PeriodicTask name | task | schedule | queue |
|---|---|---|---|
| `lapse_previous_month_credits` | `apps.credits.tasks.lapse_previous_month_credits_task` | `CrontabSchedule(minute="5", hour="0", day_of_month="1", day_of_week="*", month_of_year="*", timezone="UTC")` | `default` |
| `reap_stale_reserved_credit_transactions` | `apps.credits.tasks.reap_stale_reserved_transactions_task` | `IntervalSchedule(every=10, period=MINUTES)` (check the `0015_beat_incremental_6h` migration for the interval idiom to mirror) | `default` |

- `dependencies = [("credits", "0001_initial"), ("django_celery_beat", "0019_alter_periodictasks_options")]` (the beat migration id is the one existing seeds use).
- Set the crontab `timezone="UTC"` explicitly, as the polarity migration does. `TIME_ZONE` is already UTC.
- Add both tasks to `CELERY_TASK_ROUTES` as `{"queue": "default"}` for documentation and consistency with the existing routes block. `apps.credits` must be in `INSTALLED_APPS` so Celery autodiscovery imports `tasks.py`.
- Update CLAUDE.md §12.5's Beat table in the same change.

**Make lapse a catch-up, not a "previous month only" job.** The spec says "previous month". A Beat outage spanning a month boundary would otherwise leave a period permanently un-lapsed. Select all balances with `(period_year, period_month) < current_period()` that have `remaining > 0` and no existing `LAPSED` transaction:

- Idempotency comes from a **partial unique constraint** on `CreditTransaction(shop_credit_balance) WHERE transaction_type='LAPSED'`, with `bulk_create(ignore_conflicts=True)` in chunks. The same technique makes `INITIAL_ALLOCATION` once-per-balance under concurrent lazy creation (`WHERE transaction_type='INITIAL_ALLOCATION'`).
- Iterate with `.iterator(chunk_size=500)`. One `AuditLog` (`shop.credits.lapsed`, `actor=None`) per lapsed shop, as the spec requires.
- The task is a thin wrapper over `lapse.lapse_past_periods()`.

**Reaper.** Select `status=RESERVED AND created_at < now - REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES`, then call `refund_reservation` for each. Add a composite index `(status, created_at)` on `CreditTransaction`. No distributed lock is needed because `refund_reservation` is row-locked and idempotent. Wrap each refund in try/except so one bad row does not stop the sweep.

### 6. Suggested build order (dependency-driven)

| Order | Phase focus | Contents | Why here |
|---|---|---|---|
| 1 | **Data foundation** | `Organisation.monthly_credit_allocation` (+ migration, serializers, add to `_UPDATABLE_FIELDS`, `actor` param on `update_organisation`/create, `organisation.credits.set` audit); `apps/credits` app, models, constraints, indexes, `periods.py`, `credit_cost.py` + boundary tests; settings; `INSTALLED_APPS`; migration `0001` | Everything else depends on the schema. The cost function is pure and unblocks UI work in parallel. Highest-leverage place to get constraints right. |
| 2 | **Consumption core** | `allocation.py` (lazy balance), `consumption.py` (reserve/commit/refund), exceptions; guardrails/exception `stage` + `usage_log_id`; `_generate_reply_draft_with_log`; `generate_reply_with_credits`; view mapping (402/400), `cost` action, response fields; OpenAI client timeout | The risky, race-sensitive part. Needs concurrency tests (spec 14.2 #7) and the moderation-policy matrix tests before UI builds on it. Mandatory `ai-enrichment-specialist` and `tenant-security-auditor` review. |
| 3 | **Beat jobs** | `lapse.py`, `tasks.py` (lapse + reaper), seed migration `0002`, `CELERY_TASK_ROUTES`, CLAUDE.md §12.5 | Depends on the models and on `refund_reservation` from phase 2. No UI dependency, so it can run in parallel with phase 4. |
| 4 | **Read API and visibility plumbing** | `selectors/balances.py` (`annotate_credit_state`, current state, history), `list_shops(with_credits=True)`, `ShopReadSerializer` fields, credits GET and history endpoints with Staff scoping, query-count tests | Depends on models and periods. Provides the data the three UI surfaces consume. |
| 5 | **Superadmin controls** | Bonus allocation service plus `POST` endpoint (Superadmin, no `TenantScopedViewSet`), Superadmin read endpoint, org form field (Create/Edit React modals), audit rows | Depends on `allocation.py`. Needs a Superadmin shop surface (see Gaps). |
| 6 | **Frontend** | Shop Details credits card and badge (`shop-management`), composer cost and remaining and disabled state, Generate hidden for empty comments, Buy More modal (a11y: focus trap, ESC, `mailto:` from `REVIEWBEE_SUPPORT_EMAIL`), Shops list badge, Superadmin bonus modal | Last, so it consumes stable endpoint contracts. Run `/gsd-ui-phase` first. |

Phases 3 and 4 are independent and can be parallelised. Phase 5's backend can start after phase 1 and 2. A reasonable roadmap collapse: 1 plus 2 as one phase if the team prefers fewer phases, but do **not** merge 2 with any UI phase.

---

## Patterns to Follow

### Pattern 1: Reserve outside the AI call, idempotent transitions
**What:** Short row-locked transaction to reserve, AI call with no lock held, then an idempotent commit or refund that checks `status == RESERVED` under `select_for_update()`.
**When:** Always for credit consumption. Never hold the balance lock across the OpenAI call (PROJECT.md decision "OpenAI call outside `transaction.atomic()`" confirms this is existing policy).
```python
@transaction.atomic
def refund_reservation(*, transaction_id: int, reason: str) -> bool:
    tx = CreditTransaction.objects.select_for_update().get(pk=transaction_id)
    if tx.status != CreditTransaction.Status.RESERVED:
        return False                                   # idempotent: reaper vs view race is harmless
    ShopCreditBalance.objects.filter(pk=tx.shop_credit_balance_id).update(
        consumed_credits=F("consumed_credits") + tx.credits_delta   # delta is negative
    )
    tx.status = CreditTransaction.Status.REFUNDED
    tx.notes = reason
    tx.save(update_fields=["status", "notes"])
    return True
```
Lock order is consistent, so no deadlock: reserve locks the balance only; refund locks the transaction then updates the balance through an atomic `UPDATE`; commit locks the transaction only.

### Pattern 2: Race-safe lazy creation
**What:** `bulk_create([ShopCreditBalance(...)], ignore_conflicts=True)` then `select_for_update().get(...)`, the same shape as the canonical-tag insert in CLAUDE.md §29.3. Write the `INITIAL_ALLOCATION` transaction and audit row only if the insert actually created the row (guard with the partial unique constraint above).
**When:** `reserve_credits` and `allocate_bonus_credits` (bonus on a shop with no row yet must create it first).

### Pattern 3: Database safety net
**What:** `CheckConstraint(check=Q(consumed_credits__gte=0) & Q(consumed_credits__lte=F("allocated_credits") + F("bonus_credits")))` on `ShopCreditBalance`.
**When:** Always. If a logic bug or race ever over-spends, the write fails loudly instead of silently going negative.

### Pattern 4: Derive-on-read balance arithmetic
**What:** `remaining = allocated + bonus - consumed` is never stored. Compute it in selectors via annotation, and via a `@property` on the instance for the single-row case.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Business logic in the view
**What:** Calling reserve, then `generate_reply_draft`, then commit or refund inside `generate_reply`.
**Why bad:** Violates CLAUDE.md §5, and the existing broad `except Exception -> 502` would swallow or mis-map credit errors.
**Instead:** One orchestrator service; the view only maps exceptions to HTTP.

### Anti-Pattern 2: Holding the balance lock during OpenAI
**What:** The spec's §6.1 flow (SELECT FOR UPDATE, call OpenAI, then deduct).
**Why bad:** Serialises all replies for a shop, and a hung call holds the lock. The spec itself recommends the two-phase alternative (§6.2); follow that.

### Anti-Pattern 3: Reaper TTL shorter than the real OpenAI timeout
**What:** `client.py` builds `OpenAI(api_key=...)` with **no explicit timeout**. The SDK default is long (minutes) and retries twice. A slow call can outlive the 5-minute reservation TTL, and the reaper would refund a call that then succeeds, giving the user a free reply.
**Why bad:** Silent credit leakage.
**Instead:** Pass an explicit `timeout` (for example 60s, well under the TTL) on the reply-generation call and keep `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES` comfortably above `timeout x (max_retries+1)`. Add this to phase 2.

### Anti-Pattern 4: Writing balance rows on GET
**What:** Letting the credits card or shops list create the current-month row.
**Why bad:** Creates rows for shops that never use AI, which the spec's lazy design explicitly avoids; it also puts writes on read endpoints.
**Instead:** Synthesise the "virtual" balance from the org allocation in the selector.

### Anti-Pattern 5: Inverting the FK to AiUsageLog
**What:** Adding `credit_transaction` to `AiUsageLog`.
**Why bad:** `integrations.openai` would import credits. Keep the FK on `CreditTransaction`.

### Anti-Pattern 6: Whitelist miss on organisation update
**What:** Adding the model field and serializer field but not `_UPDATABLE_FIELDS` in `apps/organisations/services/organisations.py`.
**Why bad:** `update_organisation` silently skips any field not in the whitelist, so edits to the credit allocation would be dropped without error.
**Instead:** Add the field to the whitelist, and test that an edit actually persists and writes the audit row.

---

## Scalability Considerations

| Concern | At 100 shops | At 10K shops | At 1M shops |
|---------|--------------|--------------|-------------|
| Shops list annotation | 2 index-probe subqueries per row, trivial | Same, bounded by page size (max 100) | Same per page; the table is not scanned |
| Reserve contention | Row lock per shop, negligible | Per-shop only; no global lock | Per-shop only |
| `CreditTransaction` growth | Tiny | About 1 row per AI reply, fine with `(shop, created_at)` index | Consider partitioning by `created_at` and archiving |
| Lapse job | One sweep, a few hundred rows | Chunked `iterator()` + `bulk_create`, seconds | Chunk and shard by organisation; still idempotent |
| Reaper | Index scan on `(status, created_at)` | Same, near-empty set normally | Same |

Throttle (10/min/user) bounds consumption rate far below any contention ceiling.

---

## Gaps and Risks for the Roadmap

1. **No Superadmin shop UI exists.** `ShopViewSet` is `TenantScopedViewSet` (queryset is `none()` for Superadmin, who has no `organisation_id`), and Superadmin's React surface (`org-management.tsx`) is organisations-only. The spec's "Allocate Bonus Credits on the Shop Details screen (Superadmin only)" has no screen to live on. **Recommendation:** add a Superadmin-only, non-tenant endpoint `GET /api/v1/superadmin/organisations/{org_id}/shops/credits/` (paginated) and `POST /api/v1/superadmin/shops/{shop_id}/credits/bonus/`, plus an org-row action in `org-management` that opens a shops-and-balances modal with a per-shop "Allocate bonus" action. This is the main scope risk in the milestone and needs a UI-SPEC and a roadmap decision before phase 5. Superadmin views must use `IsAuthenticated + IsSuperadmin` and must not inherit `TenantScopedViewSet` (per its docstring).
2. **Staff shop scoping is not applied in the existing shops list.** `list_shops` and `ShopViewSet.get_queryset` filter by organisation only; Staff scoping via `StaffAccessScope` exists on reviews but not here. Adding `remaining_credits` to that list would expose credit counts for out-of-scope shops to Staff, against spec criterion 28. Surface this to the roadmap. Fixing the existing list is outside the credits scope, so either scope the credits fields to accessible shops (null out others) or fix the list under a separate requirement. Run `tenant-security-auditor` on phases 4 and 5.
3. **Spec drifts from the live model.** The spec says `review.text`; the field is `Review.comment`. The spec says UUID primary keys; the codebase uses `BigAutoField`. Pick bigint for consistency (the `UUIDModel` mixin exists if UUIDs are required). Both are low-stakes; decide in phase 1.
4. **Audit action for refunds is missing from spec §3.4.** Add `shop.credits.refunded` so the audit log covers every state change. `CreditTransaction` rows are "immutable" in the spec but must have their `status` and `ai_usage_log` set via the service layer; make that explicit (no update endpoint, no admin edit permission).
5. **Whitespace-only comments:** the spec says "zero comment text". Use `comment.strip()` consistently in the frontend visibility check, the server guard, and the cost function input, so the three never disagree.
6. **Credits are checked before moderation (locked decision).** Every input-moderation block therefore creates a RESERVED then REFUNDED transaction pair. That is intended and keeps the ledger honest, but expect noise in history. Filter `REFUNDED` out of the default history view if it clutters.

---

## Sources

- `/Users/renjith/Documents/Accounts/review-master/docs/completed/Requirements_Credits_System.md` (spec v1.0): HIGH
- `/Users/renjith/Documents/Accounts/review-master/.planning/PROJECT.md` (v0.9 locked decisions): HIGH
- `/Users/renjith/Documents/Accounts/review-master/CLAUDE.md` §5, §6, §7.6, §9, §12, §13, §14, §22, §29: HIGH
- `apps/reviews/services/reply_generation.py`, `apps/reviews/views.py` (`generate_reply`, `get_throttles`, `get_queryset`): HIGH, read directly
- `apps/integrations/openai/guardrails.py`, `exceptions.py`, `models.py` (`AiUsageLog`, app label `openai`), `client.py` (no explicit timeout): HIGH, read directly
- `apps/shops/selectors/shops.py`, `views.py`, `serializers.py`; `apps/common/viewsets.py` (`TenantScopedViewSet`): HIGH, read directly
- `apps/organisations/services/organisations.py` (`_UPDATABLE_FIELDS`, `update_organisation`), `views.py`, `serializers.py`: HIGH, read directly
- `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py` (Beat seeding pattern); `apps/common/models.py` (`AuditLog`): HIGH, read directly
- `config/settings/base.py` (`TIME_ZONE="UTC"`, `USE_TZ=True`, no `ATOMIC_REQUESTS`, `generate_reply: 10/minute`): HIGH, read directly
