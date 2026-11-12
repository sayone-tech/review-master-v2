# Technology Stack — v0.9 AI Reply Credits

**Project:** ReviewBee (review-master) — milestone v0.9 AI Reply Credits
**Researched:** 2026-11-11
**Scope:** Only what is NEW for the credits feature. The existing stack is validated and not re-researched.
**Overall confidence:** HIGH

## Verdict

**Add zero new runtime dependencies. Add zero new dev dependencies. Add zero frontend packages.**

Everything the spec needs is already in the pinned stack (Django 6.0.2, Celery 5.6.3, django-celery-beat 2.9.0, psycopg 3.2.3, DRF 3.17.1, drf-spectacular 0.28.0, React 19 + `focus-trap-react`). The work is a new `apps/credits` Django app that uses four Django ORM features correctly, one Celery Beat seed migration (same pattern as `reviews/0013`), and one settings change. The hard parts are concurrency semantics and failure-window handling, not libraries. See "Pitfalls the stack choices must absorb" below.

Versions were checked against PyPI on 2026-11-11. Newer releases exist (Django 6.1.3, Celery 5.7.0, DRF 3.18.3) but none are needed for this milestone. Do NOT bundle a framework upgrade into v0.9. django-celery-beat 2.9.0 is already the latest.

## Recommended Stack (new usage of already-installed components)

### Core Framework — all existing, pinned

| Technology | Pinned version | Purpose in v0.9 | Why it is sufficient |
|------------|---------------|-----------------|----------------------|
| Django ORM | 6.0.2 | `ShopCreditBalance` / `CreditTransaction` models, `F()` atomic increments, `select_for_update`, `CheckConstraint`, partial `UniqueConstraint`, `FilteredRelation` annotations | All verified by compiling SQL against the installed 6.0.2 (see "Verified behaviours") |
| Django REST Framework | 3.17.1 | Credits endpoints, 402/400 error mapping | A 402 is a trivial `APIException` subclass with `status_code = 402` in `apps/common/exceptions.py` |
| drf-spectacular | 0.28.0 | Document 400/402/422/502 on `generate-reply`, new endpoints | `extend_schema(responses={...})` |
| Celery + django-celery-beat | 5.6.3 / 2.9.0 | Monthly lapse + 10-min reaper | `CrontabSchedule(timezone="UTC")` seeded by data migration |
| Python stdlib | 3.12 | `datetime.UTC`, month arithmetic, tier lookup | No `dateutil`/`pendulum` needed (see below) |

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 16 (existing) | Row locks, CHECK constraints, partial unique indexes | `SELECT ... FOR UPDATE`, cross-column CHECK, and partial unique indexes are all native. Concurrency tests MUST run on Postgres (SQLite silently ignores `select_for_update`). |

No new extension, no `GeneratedField`, no materialised view, no DB trigger (see Alternatives).

### Infrastructure

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Redis (existing) | 7 | NOT used for balances. Optional per-shop `distributed_lock` is unnecessary | Balance is write-after-read data; CLAUDE.md §7.2 says do not cache it. The Postgres row lock is the single source of truth. |
| Celery Beat (existing, exactly 1 instance) | — | Two new `PeriodicTask` rows on queue `default` | Matches spec §11 and CLAUDE.md §12.5 |

### Supporting Libraries — all already present

| Library | Version | Purpose | When to use |
|---------|---------|---------|-------------|
| `focus-trap-react` + `frontend/src/widgets/modal/Modal.tsx` | 12.0.0 | "Buy More Credits" modal and "Allocate Bonus Credits" modal (AC 36: focus trap, ESC, backdrop close, ARIA) | Reuse the existing `Modal`. Do not add Headless UI/Radix. |
| `@tanstack/react-query` | ^5.100.9 | Fetch `GET .../generate-reply/cost/` and `GET .../credits/`; invalidate the credits query after a generate | Already the widget data layer |
| `lucide-react` | 1.8.0 | Mail icon for the Buy More modal | Already present |
| Tailwind | 4.2.4 | Progress bar and badge colour thresholds (green/amber/red/gray) | Already present |
| `pytest` + `pytest-django` | 8.3.3 / 4.9.0 | Concurrency tests with `@pytest.mark.django_db(transaction=True)` + `ThreadPoolExecutor` | No `pytest-xdist`, no `freezegun`, no `time-machine` (see clock seam below) |

## Capability-by-capability implementation guidance

### 1. Credit ledger with two-phase reserve / commit / refund

Use plain ORM. Three short DB transactions; the OpenAI call happens between them with no transaction open.

**Models (`apps/credits/models.py`)**
- Inherit `UUIDModel` + `TimeStampedModel` from `apps/common/models.py` (both exist). The spec calls for UUID PKs; note `Shop.pk` is the project default `BigAutoField`, so FKs to Shop are integer FKs. That is fine.
- Integer fields on `ShopCreditBalance`: `allocated_credits`, `bonus_credits`, `consumed_credits`. Plain `IntegerField` plus explicit constraints (below). Never `Decimal`/`float` for credits.
- `CreditTransaction.status` as `TextChoices` (`RESERVED | COMMITTED | REFUNDED`); `transaction_type` as `TextChoices`. Add `credits_cost`/use `credits_delta` consistently so refund math can read the original cost from the row rather than recomputing from review text (the review may be edited between reserve and reap).
- FK `on_delete`: balance FK `PROTECT`; `review`, `ai_usage_log`, `performed_by` `SET_NULL` (nullable, history must survive review soft-delete / user removal). Add the `(shop, created_at)` and `(organisation, created_at)` indexes from spec §3.3 plus `(status, created_at)` for the reaper scan (partial index `condition=Q(status="RESERVED")` is cheaper and tiny).

**Constraints (the correctness backstop; verified to compile on Django 6.0.2)**
```python
class Meta:  # ShopCreditBalance
    constraints = [
        models.UniqueConstraint(fields=["shop", "period_year", "period_month"], name="credit_balance_shop_period_uniq"),
        models.CheckConstraint(condition=Q(period_month__gte=1, period_month__lte=12), name="credit_balance_month_range"),
        models.CheckConstraint(condition=Q(allocated_credits__gte=0, bonus_credits__gte=0, consumed_credits__gte=0), name="credit_balance_nonneg"),
        # THE anti-overspend invariant, enforced by Postgres regardless of app bugs:
        models.CheckConstraint(condition=Q(consumed_credits__lte=F("allocated_credits") + F("bonus_credits")), name="credit_balance_no_overspend"),
    ]

class Meta:  # CreditTransaction — idempotency keys for allocation + lapse
    constraints = [
        models.UniqueConstraint(fields=["shop_credit_balance"], condition=Q(transaction_type="LAPSED"), name="credit_tx_one_lapse_per_balance"),
        models.UniqueConstraint(fields=["shop_credit_balance"], condition=Q(transaction_type="INITIAL_ALLOCATION"), name="credit_tx_one_initial_per_balance"),
    ]
```
Note: Django 6.0 `CheckConstraint` takes `condition=` (the old `check=` was removed). `UniqueConstraint(condition=...)` creates a partial unique index.

**Phase A — reserve (one short `transaction.atomic()`, no network I/O):**
1. `ShopCreditBalance.objects.get_or_create(shop=..., period_year=y, period_month=m, defaults={"organisation_id":..., "allocated_credits": org.monthly_credit_allocation})` — race-safe because of the unique constraint. When `created=True`, also write the `INITIAL_ALLOCATION` transaction and `shop.credits.allocated` AuditLog row.
2. `.select_for_update().get(pk=...)` (consistent with CLAUDE.md §6.12 and the spec). Check `allocated + bonus - consumed >= cost`, else raise `InsufficientCreditsError` (-> 402).
3. `balance.consumed_credits = F("consumed_credits") + cost` via `.update()`, insert `CreditTransaction(type=CONSUMPTION, status=RESERVED, credits_delta=-cost, review, performed_by)`. Commit.

Optional single-statement alternative (kept as the fallback if lock contention ever matters): `ShopCreditBalance.objects.filter(pk=pk, consumed_credits__lte=F("allocated_credits") + F("bonus_credits") - cost).update(consumed_credits=F("consumed_credits") + cost)` and treat `rowcount == 0` as insufficient. Verified to compile to one `UPDATE ... WHERE consumed <= (allocated + bonus) - cost`. The CHECK constraint makes both variants safe.

**Phase B — fulfil (no transaction open):** call the existing reply generation (moderation + OpenAI). Guard the call site with `assert not connection.in_atomic_block` (or a `RuntimeError`) so nobody wraps the view in `atomic()` and silently re-introduces the long lock. `ATOMIC_REQUESTS` is not set in this repo (verified), so Phase A genuinely commits before OpenAI runs.

**Phase C — settle (short `atomic()`), compare-and-swap on status:**
```python
# commit
n = CreditTransaction.objects.filter(pk=tx_id, status=RESERVED).update(status=COMMITTED, ai_usage_log_id=log_id)
# refund (OpenAI failure / input-moderation block / reaper)
with transaction.atomic():
    n = CreditTransaction.objects.filter(pk=tx_id, status=RESERVED).update(status=REFUNDED)
    if n == 1:
        ShopCreditBalance.objects.filter(pk=balance_id).update(consumed_credits=F("consumed_credits") - cost)
```
The `status=RESERVED` filter makes commit, refund and the reaper mutually exclusive: whichever transitions the row first wins, a double refund is impossible, and `n == 0` is a clean "someone else settled it" signal. This is the core reason no state-machine library is needed. Keep the ledger append-only in spirit: no update/delete endpoints, `ModelAdmin.has_change_permission/has_delete_permission = False` (django-unfold admin is already in use), and status is only ever changed by these named service functions. (Spec §3.3 says "immutable" but §6.2 requires a status flip; treat `status` as the single permitted transition and everything else as immutable.)

**Refund policy mapping (PROJECT.md decisions):** OpenAI transient/permanent/unknown error -> refund. Input moderation block (`ContentModeratedException` raised before the OpenAI call) -> refund. Output moderation block -> commit (OpenAI was billed) and link the MODERATED `AiUsageLog` row.

**Integration change required in existing code:** `generate_reply_draft()` currently returns only the draft `str` and writes `AiUsageLog` internally. To satisfy AC 5/38 (link `ai_usage_log_id` on commit) it must also surface the usage-log id (return a small frozen dataclass, or let the credits service read the latest log for `(review, request_type)`; the dataclass is cleaner). `apps/reviews/services/replies.py` / the `generate_reply` view action should call `apps.credits.services.consumption.generate_reply_with_credits(...)`, which wraps `generate_reply_draft`.

### 2. Monthly UTC lapse via Celery Beat crontab

Use the existing seed-via-data-migration pattern, copying `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py`:
```python
CrontabSchedule.objects.get_or_create(minute="5", hour="0", day_of_week="*", day_of_month="1", month_of_year="*", timezone="UTC")
# PeriodicTask name="lapse_previous_month_credits", task="apps.credits.tasks.lapse_previous_month_credits_task", queue="default"
CrontabSchedule.objects.get_or_create(minute="*/10", hour="*", day_of_week="*", day_of_month="*", month_of_year="*", timezone="UTC")
# PeriodicTask name="reap_stale_reserved_credits", task="apps.credits.tasks.reap_stale_reserved_transactions_task", queue="default"
```
Migration dependency: same as existing seeds, `("django_celery_beat", "0019_alter_periodictasks_options")`. Reversible `RunPython` that deletes the two PeriodicTask rows by name. Also add both tasks to `CELERY_TASK_ROUTES` for explicitness (queue `default`).

Timezone facts verified in the installed django-celery-beat 2.9.0 source: `CrontabSchedule.timezone` is stored per row and evaluated via `TzAwareCrontab(tz=...)`; `DJANGO_CELERY_BEAT_TZ_AWARE` defaults to True. The repo has `TIME_ZONE = "UTC"` / `USE_TZ = True` and no `CELERY_TIMEZONE`, so everything is UTC already. Always set `timezone="UTC"` explicitly on the seeded row (the existing seeds do) rather than relying on defaults. Do not change `TIME_ZONE` later without resetting `last_run_at` (django-celery-beat docs warning).

**Lapse task must be self-healing, not just "previous month":**
- Service selects every `ShopCreditBalance` with `(period_year, period_month) < current UTC period` that has no `LAPSED` transaction, not literally "last month only". A missed or late Beat run (Beat is a singleton) is then repaired by the next run.
- Per-balance function `lapse_balance(balance_id)` runs in its own `atomic()` with `select_for_update`, writes the `LAPSED` transaction (`credits_delta = -remaining`) and the `shop.credits.lapsed` AuditLog row; the partial unique index `credit_tx_one_lapse_per_balance` makes a double run a no-op (catch `IntegrityError` inside a savepoint or pre-check). Skip when `remaining <= 0`.
- Process in chunks (`.iterator(chunk_size=500)`), one transaction per balance, so a failure does not roll back the whole month and the run stays under the 600s Celery hard limit.
- Skip (do not lapse) any balance that still has a `RESERVED` transaction; see Pitfall A.
- Celery's crontab `is_due(last_run_at)` normally fires a catch-up run after a Beat restart, but do not depend on it; the self-healing query is the guarantee. Spec risk-table monitoring (alert if not completed by 00:30 UTC) is infra work, not a library.

**Period math with stdlib only:**
```python
from datetime import UTC, datetime
def current_period(now: datetime | None = None) -> tuple[int, int]:
    now = (now or datetime.now(UTC)); return now.year, now.month
def next_period_start(y: int, m: int) -> datetime:
    return datetime(y + m // 12, m % 12 + 1, 1, tzinfo=UTC)
```
Put these in one module (`apps/credits/services/periods.py`) and route every "what month is it" call through `current_period()`. That single seam is also the test seam (patch it, or pass `now=`), which removes any need for `freezegun`/`time-machine`. Never use `timezone.localtime()` for period selection (spec §13.4: UTC boundaries; only the "Renews on ..." display converts to the user's tz, client-side or via `localtime` at serialization).

### 3. Per-row annotated balances on list endpoints (no N+1)

Use `FilteredRelation` + `Coalesce`, not a correlated `Subquery` and not a window function. Verified on installed Django 6.0.2: it compiles to ONE `LEFT OUTER JOIN` on `(shop_id, period_year, period_month)`, which cannot multiply rows because of the unique constraint.
```python
# apps/credits/selectors/balances.py
def annotate_remaining_credits(qs, *, period: tuple[int, int] | None = None):
    y, m = period or current_period()
    return qs.annotate(
        _cb=FilteredRelation("credit_balances", condition=Q(credit_balances__period_year=y, credit_balances__period_month=m)),
    ).annotate(
        credits_total=Coalesce(F("_cb__allocated_credits") + F("_cb__bonus_credits"), F("organisation__monthly_credit_allocation")),
        credits_consumed=Coalesce(F("_cb__consumed_credits"), Value(0)),
        credits_remaining=Coalesce(
            F("_cb__allocated_credits") + F("_cb__bonus_credits") - F("_cb__consumed_credits"),
            F("organisation__monthly_credit_allocation"),
        ),
    )
```
- The `Coalesce` fallback to `organisation.monthly_credit_allocation` is essential: balance rows are created lazily (spec §7.1), so a shop that has not generated a reply this month has NO row, yet the badge must show the full allocation. Without it, the list shows NULL/0 for every untouched shop.
- Apply in `apps/shops/selectors/shops.py::list_shops` (it already does `select_related("region")`; add `select_related("organisation")` or rely on the `organisation__` join, which the annotate adds). Expose the three annotations on the serializer as plain read-only fields (CLAUDE.md §6.7: flattened data, not `SerializerMethodField`).
- Nested form works too (verified): `FilteredRelation("shop__credit_balances", condition=Q(shop__credit_balances__period_year=...))` for any Review-list annotation. Use only if a list needs per-row credits; the reply composer needs one shop's balance, so prefer the single-shop selector there.
- Single-shop endpoint `GET /api/v1/shops/{id}/credits/`: one query, `ShopCreditBalance.objects.filter(shop_id=..., period...).first()` falling back to a computed in-memory zero-state from the org allocation (still O(1) queries; org is already loaded by `TenantScopedViewSet`).
- Query-count tests (AC 37): `CaptureQueriesContext` with 1 vs 20 shops must show an identical ceiling. Add a regression test that a shop with no balance row reports the org allocation.
- The `remaining_credits` "derived, not stored" rule from the spec is honoured: expose it as a `@property` on the model for single-row use and as the annotation for lists. Do NOT add a Postgres `GeneratedField`: it works (Django 5.0+, stored generated column) but adds a migration-rewrite cost and a second source of truth the spec explicitly rejects; the CHECK constraint already protects the invariant.

### 4. Cost tiers (config, not code)

Implement `calculate_credit_cost` in `apps/credits/services/credit_cost.py` (PROJECT.md decision; spec §4.3 vs §13.1 resolved) reading `settings.REVIEWBEE_CREDIT_TIERS`. Two fixes to the spec's sample config:
- Use an open-ended last tier (`None`/`math.inf`) rather than `(10000, 3)`. The spec's ceiling of 10000 leaves comments >10000 chars with no tier. (Review text is already capped at 4000 chars for the prompt by Phase 20, but the stored `Review.comment` is not.)
- Measure `len(review.comment.strip())`; treat whitespace-only as zero (400, button hidden) so the hidden-button rule and the server check agree.
Boundary unit tests per AC 40: 0 (raises), 1, 100, 101, 500, 501, 10000, 10001.

## Verified behaviours (Django 6.0.2, local probe)

| Claim | Result |
|-------|--------|
| `FilteredRelation` + `Coalesce` over F-arithmetic | One `LEFT OUTER JOIN ... ON (shop_id = ... AND m = 11 AND y = 2026)` |
| Nested `FilteredRelation("shop__bals", ...)` from Review | Works, single LEFT JOIN |
| `CheckConstraint(condition=Q(consumed__lte=F("allocated")+F("bonus")))` | Compiles to `CHECK ("consumed" <= ("allocated" + "bonus"))` |
| `.filter(consumed__lte=F("allocated")+F("bonus")-N)` before `.update()` | Compiles to a single guarded predicate (conditional UPDATE viable) |
| `select_for_update` | PostgreSQL supports `nowait`, `skip_locked`, `of`, `no_key`; SQLite ignores it (tests must use Postgres) |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Concurrency control | `select_for_update` in short txn + F() + CHECK constraint | Redis counter / Lua script for balances | Two sources of truth, loses transactional link to the ledger row; CLAUDE.md §7.2 forbids caching write-after-read data |
| Concurrency control | Same | `django-concurrency` (optimistic versioning) | Adds a dependency to solve a problem a row lock solves natively; optimistic retries are worse UX here |
| Concurrency control | Same | Redis `distributed_lock` around generate | Not needed: the DB lock is held only for milliseconds (Phase A); a Redis lock would add a failure mode (TTL expiry) for no gain |
| Status transitions | CAS `filter(status=RESERVED).update(...)` | `django-fsm` / `django-fsm-2` | A 3-state, 3-edge machine; library adds dependency and model-level side effects (violates CLAUDE.md "no logic in save()") |
| Ledger | Two plain models | `django-ledger`, `django-simple-history`, `django-money` | Domain is integer credits, not money; spec defines the exact schema; history libs duplicate `CreditTransaction` |
| Derived balance | `FilteredRelation` annotation | Postgres `GeneratedField` / materialised view / denormalised `remaining` column | Second source of truth; spec §3.2 says derived, not stored |
| Per-row balance | `FilteredRelation` (1 JOIN) | Correlated `Subquery(...)` per annotation | N subqueries for N annotations; spec §13.2 allows either, join is simpler and indexed by the unique constraint |
| Lapse scheduling | Beat `CrontabSchedule` + self-healing query | Per-shop `expires_at` countdown tasks, or lapse-on-read | Many scheduled tasks / hidden writes in GETs; spec mandates a monthly Beat job |
| Date math | stdlib `datetime` + 4-line helper | `python-dateutil`, `pendulum`, `arrow` | Only "first of next month in UTC" is needed |
| Time-freezing in tests | Single `current_period()` seam + `now=` params | `freezegun`, `time-machine` | Zero-dep; keeps services deterministic without global clock patching |
| Modal a11y | Existing `Modal` + `focus-trap-react` | Headless UI / Radix Dialog | Already built and used; new dep would fragment the widget kit |
| Stale reservation cleanup | Beat reaper every 10 min (spec) | Celery `countdown`/ETA task per reservation | Lost on broker flush; the reaper is the durable source of truth |

## What NOT to add

- No new PyPI package of any kind. Do not touch `pyproject.toml` dependencies for this milestone.
- No Redis keys for credit balances or reservations, no cache layer on balance reads (stale reads cause overspend UX bugs; spec acceptance criteria are DB-checked).
- No Channels consumer / WebSocket for balance updates (CLAUDE.md §13.2 forbids; refresh via react-query invalidation after generate and normal page loads).
- No `GeneratedField`, DB triggers, or stored `remaining_credits`.
- No payment SDK (Stripe/Razorpay): "Buy More" is a placeholder modal with a `mailto:` to `settings.REVIEWBEE_SUPPORT_EMAIL`.
- No Django/Celery/DRF upgrade inside v0.9 (6.1.3 / 5.7.0 / 3.18.3 exist; schedule a separate chore. The 6.0.x patch line has reached 6.0.9, so a patch bump of the Django pin to the latest 6.0.x is worth doing as a standalone security-hygiene change; confirm release notes first).

## Integration points and required config changes

| Where | Change | Why |
|-------|--------|-----|
| `config/settings/base.py` | Add `REVIEWBEE_CREDIT_TIERS`, `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES`, `REVIEWBEE_SUPPORT_EMAIL`; add `apps.credits` to `INSTALLED_APPS` and to `config/settings/test.py` (it re-declares `INSTALLED_APPS`) | Spec §12; test.py does not inherit the list |
| `apps/integrations/openai/client.py` | **Set an explicit request timeout on the reply-generation call** (e.g. 45-60s total, `max_retries` low) | The client is built with `OpenAI(api_key=...)` and no timeout, so the SDK default (several minutes) applies. If a call outlives `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES` (5 min), the reaper refunds a reservation whose OpenAI call then succeeds -> free reply. Keep `worst_case_call_time << TTL`. Cloud Run request timeout (60s) is the practical bound anyway. |
| `apps/reviews/services/reply_generation.py` | Return the usage-log id alongside the draft | Needed to link `CreditTransaction.ai_usage_log` (AC 38) |
| `apps/reviews/views.py` (`generate_reply` action) | Route through the credits consumption service; map `InsufficientCreditsError` -> 402, empty/whitespace comment -> 400; keep the existing 10/min throttle | PROJECT.md decisions |
| `apps/common/exceptions.py` | `InsufficientCreditsError` (402) | DRF exception handler convention |
| `apps/common/models.py::AuditLog` | Reuse as-is for the 5 new actions (`entity_type="shop"` / `"organisation"`) | CLAUDE.md §29.4: prefer AuditLog over a bespoke log; actor null for system events (allocated/lapsed) |
| `apps/organisations/models.py` | `monthly_credit_allocation = IntegerField(default=0, validators=[Min 0, Max 10000])` + `CheckConstraint(0..10000)`; migration with `default=0` is metadata-only on PG 11+ | Spec §3.1; NOT NULL + default is a safe, non-rewriting migration |
| `apps/shops/selectors/shops.py::list_shops` | Compose `annotate_remaining_credits` | Spec §13.2 |
| Django admin (unfold) | Read-only `CreditTransaction`, read-only `ShopCreditBalance` | Spec §8.3: investigate via admin; ledger stays append-only |
| `frontend/` | New widget code only; reuse `Modal`, react-query, lucide, Tailwind | No package.json changes |
| `.claude/rules` / CLAUDE.md | Add `apps/credits` + queues note when merged (no new queue; both tasks use `default`) | §3, §12.1 stay accurate |

## Pitfalls the stack choices must absorb (feed to PITFALLS.md)

- **A. Lapse vs reaper race at the month boundary.** A reservation made at 23:58 on the last day can still be RESERVED at 00:05 when lapse runs (reaper cadence is 10 min, TTL 5). If lapse writes `-remaining` while credits are reserved and the reaper later refunds them into the old month's balance, `remaining` goes positive again with no LAPSED row covering it. Rule: lapse skips balances with RESERVED rows; the reaper calls `lapse_balance(balance_id)` after refunding into a past-period balance; the self-healing sweep catches the rest.
- **B. Reservation TTL vs OpenAI timeout** (see config table above). Highest-impact single change outside the credits app.
- **C. Non-transactional tests hide races.** `@pytest.mark.django_db` without `transaction=True` wraps the test in one transaction, so "commit" never happens and `select_for_update` never contends. Race tests (AC 7) need `transaction=True`, real threads each closing their DB connection in `finally`, and Postgres.
- **D. Whole-request `atomic()` would hold the lock across OpenAI.** Guard with `connection.in_atomic_block` check at Phase B.
- **E. Lazy rows vs list display.** Annotation must `Coalesce` to the org allocation (above) or untouched shops show 0 and incorrectly render the red/"Buy more" state.
- **F. Mid-month allocation changes** apply only to rows created after the change (spec §7.3): the lazy-create reads the org value at creation time, so never "re-sync" existing rows.
- **G. Stale `Review.comment` between reserve and refund.** Store the cost on the transaction row; never recompute from current review text during refund/reap.

## Installation

```bash
# Nothing to install. No pyproject.toml or package.json dependency changes.
# Schema + schedule:
python manage.py makemigrations organisations credits   # new field + new app
# hand-write apps/credits/migrations/000N_beat_seed_credit_tasks.py (RunPython, reversible)
python manage.py makemigrations --check --dry-run       # CI gate (CLAUDE.md §19)
```

## Sources

- PyPI JSON API, queried 2026-11-11: django 6.1.3 (6.0.x line up to 6.0.9), celery 5.7.0, django-celery-beat 2.9.0 (latest), djangorestframework 3.18.3 — HIGH
- Installed packages in `.venv`: Django 6.0.2, Celery 5.6.3, django-celery-beat 2.9.0 (read `tzcrontab.py`, `schedulers.py`) — HIGH
- Local probe compiling SQL on Django 6.0.2 (FilteredRelation, nested FilteredRelation, CheckConstraint with F(), guarded UPDATE) — HIGH
- https://docs.djangoproject.com/en/6.0/ref/models/querysets/ (`select_for_update` options and backend support) — HIGH (official)
- https://docs.djangoproject.com/en/6.0/ref/models/constraints/ (`CheckConstraint(condition=)`, partial `UniqueConstraint(condition=)`) — HIGH (official)
- https://django-celery-beat.readthedocs.io/en/latest/ (TIME_ZONE warning, `last_run_at` reset) — MEDIUM (docs thin on missed-run semantics; mitigated by the self-healing lapse design)
- Repo reads: `docs/completed/Requirements_Credits_System.md`, `.planning/PROJECT.md`, `CLAUDE.md`, `pyproject.toml`, `apps/reviews/services/reply_generation.py`, `apps/reviews/migrations/0013_*.py`, `apps/common/locks.py`, `apps/common/models.py`, `apps/shops/selectors/shops.py`, `apps/integrations/openai/client.py`, `config/settings/{base,test}.py`, `frontend/package.json`, `frontend/src/widgets/modal/Modal.tsx` — HIGH
- Note: Context7 MCP was not authorised in this session; library behaviour was verified from official docs plus executing against the installed versions instead.

## Confidence Assessment

| Area | Level | Notes |
|------|-------|-------|
| "Zero new dependencies" | HIGH | Every capability mapped to an installed, version-verified component |
| ORM patterns (lock, CHECK, FilteredRelation) | HIGH | SQL compiled on the pinned Django 6.0.2 |
| Beat crontab + UTC | HIGH for config, MEDIUM for missed-run catch-up | Mitigated by self-healing lapse query rather than relying on Beat catch-up |
| OpenAI timeout finding | HIGH that no explicit timeout is set in `client.py`; MEDIUM on SDK default value | Verify `openai==2.33.0` default timeout when fixing; set explicitly regardless |
