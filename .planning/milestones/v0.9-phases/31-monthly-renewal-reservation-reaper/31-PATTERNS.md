# Phase 31: Monthly Renewal & Reservation Reaper - Pattern Map

**Mapped:** 2026-11-11
**Files analyzed:** 20 (new/modified)
**Analogs found:** 20 / 20 (all analog paths verified git-tracked)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/credits/services/lapse.py` | service | batch + CRUD (row-locked write) | `apps/credits/services/consumption.py` (`reserve_credits` lock, `refund_reservation` atomic + AuditLog) | role-match |
| `apps/credits/services/reaper.py` | service | batch (CAS loop) | `apps/credits/services/consumption.py::refund_reservation` + `apps/reviews/services/sync.py::recover_stuck_syncs` | role-match |
| `apps/credits/selectors/lapse.py`, `selectors/reservations.py` | selector | read-only, single query | `apps/credits/selectors/balances.py` | exact |
| `apps/credits/tasks.py` | task (thin wrapper) | batch / event-driven (Beat) | `apps/reviews/tasks.py::reclassify_polarity_task`, `recover_stuck_syncs_task` | exact |
| `apps/credits/migrations/0002_shopcreditbalance_lapsed_at.py` | migration (schema) | n/a | `apps/credits/migrations/0001_initial.py` (partial `Index` form) | role-match |
| `apps/credits/migrations/0003_beat_credit_lapse_and_reaper.py` | migration (data) | seed | `apps/reviews/migrations/0013_...polarity_reclassify.py` (Crontab) + `0016_beat_recover_stuck_syncs.py` (Interval) | exact |
| `apps/credits/models.py` (add `lapsed_at` + partial index) | model | CRUD | same file, `credit_bal_org_period_idx` / `credit_tx_reserved_idx` | exact |
| `apps/credits/services/consumption.py` (`_settle_lost_race`, modify) | service | request-response | itself, lines 323-330 | exact |
| `config/settings/base.py` (2 settings + 2 routes) | config | n/a | lines 134, 236-237 | exact |
| `CLAUDE.md` §12.5 / §3, `docs/sre/v0.9-credits-rollout.md` | docs | n/a | existing Beat table rows | exact |
| `apps/credits/tests/test_lapse.py`, `test_reaper.py`, `test_renewal.py` | test | unit | `apps/credits/tests/test_consumption.py` | exact |
| `apps/credits/tests/test_tasks.py` | test | unit | `apps/reviews/tests/test_tasks.py` lines 54-70 | exact |
| `apps/credits/tests/test_pg_concurrency.py` (add 3 tests) | test | pg_concurrency | same file `_run_threads`, `test_charges_once_when_commit_and_refund_race` | exact |
| `apps/credits/tests/helpers.py` (add `age_reservation`) | test util | n/a | same file `assert_ledger_reconciles` | exact |
| `test_consumption.py`, `test_settings.py`, `test_models.py` (edit) | test | unit | themselves | exact |

## Pattern Assignments

### `apps/credits/tasks.py` (task, Beat batch)

**Analog:** `apps/reviews/tasks.py` lines 381-393 and 443-453. Bare `@shared_task`, lazy service import inside the body, no autoretry, logs counts only.

```python
@shared_task  # type: ignore[misc]
def reclassify_polarity_task() -> dict[str, int]:
    """... No autoretry: the job is idempotent and weekly; ... Routes to the default queue (D-05, §12.5)."""
    from apps.reviews.services.reclassify import run_polarity_reclassification

    result = run_polarity_reclassification()
    logger.info("reclassify_polarity_task.complete flipped=%s ...", ...)
```
```python
@shared_task  # type: ignore[misc]
def recover_stuck_syncs_task() -> int:
    from apps.reviews.services.sync import recover_stuck_syncs
    count = recover_stuck_syncs(stale_after_seconds=stale_seconds)
    if count:
        logger.warning("recover_stuck_syncs_task.recovered count=%s", count)
    return count
```
Apply: two tasks (`lapse_expired_credit_balances_task`, `reap_stale_reservations_task`), return `dataclasses.asdict(summary)` (JSON-safe). Add a comment citing why no §12.3 autoretry. Module needs `logger = logging.getLogger(__name__)`.

---

### `apps/credits/migrations/0003_beat_credit_lapse_and_reaper.py` (data migration)

**Analog (cron):** `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py` lines 1-60. **Analog (interval):** `0016_beat_recover_stuck_syncs.py`.

```python
crontab, _ = CrontabSchedule.objects.get_or_create(
    minute="0", hour="3", day_of_week="0", day_of_month="*", month_of_year="*", timezone="UTC",
)
PeriodicTask.objects.update_or_create(
    name="reclassify_polarity_tags",
    defaults={
        "task": "apps.reviews.tasks.reclassify_polarity_task",
        "crontab": crontab, "interval": None, "enabled": True, "queue": "default",
        "args": json.dumps([]), "kwargs": json.dumps({}), "description": (...),
    },
)
```
```python
interval, _ = IntervalSchedule.objects.get_or_create(every=10, period="minutes")
# unseed: PeriodicTask.objects.filter(name="recover_stuck_syncs").delete()  (delete task by name only; schedule row is shared)
class Migration(migrations.Migration):
    dependencies = [("reviews", "0015_beat_incremental_6h"), ("django_celery_beat", "0019_alter_periodictasks_options")]
    operations = [migrations.RunPython(seed, unseed)]
```
Apply: crontab `minute="5", hour="0"`, `day_of_week="*"`, tz UTC, name `credits_lapse_expired_balances`; interval 10 min, name `credits_reap_stale_reservations`. Dependencies: `("credits", "0002_shopcreditbalance_lapsed_at")` + the beat 0019 entry. Keep `# type: ignore[no-untyped-def]` on seed/unseed signatures. Schema (0002) stays separate from data (0003).

---

### `apps/credits/models.py` + `0002` (lapsed_at + partial index)

**Analog:** same file lines 70-75 (balance index) and 179-183 (partial index on tx):
```python
models.Index(
    fields=["status", "created_at"],
    condition=Q(status="RESERVED"),
    name="credit_tx_reserved_idx",
),
```
Apply: `lapsed_at = models.DateTimeField(null=True, blank=True)` on `ShopCreditBalance`; add `models.Index(fields=["period_year","period_month"], condition=Q(lapsed_at__isnull=True), name="credit_bal_unlapsed_idx")` to its `indexes`. Record the index decision in the plan. Update the docstring note that `lapsed_at` is the only non-counter writable field. Generate with `makemigrations credits -n shopcreditbalance_lapsed_at`.

---

### `apps/credits/services/lapse.py` (service, row-locked batch write)

**Analogs:** `consumption.py` imports (lines 21-40), the `refund_reservation` atomic + AuditLog block (lines 257-291), and the `reserve_credits` lock form `select_for_update(of=("self",))`.

Imports to copy:
```python
import logging
from dataclasses import dataclass
import sentry_sdk
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import current_period, utc_now
```
AuditLog pattern (consumption.py 272-288):
```python
AuditLog.objects.create(
    organisation_id=row.organisation_id, actor_id=actor_id, entity_type="shop",
    entity_id=str(row.shop_id), action="shop.credits.refunded", before_data=None,
    after_data={...},
)
```
Apply: action `shop.credits.lapsed`, `actor=None`, `after_data` keys per D-03. Use `models.Q(period_year__lt=y) | Q(period_year=y, period_month__lt=m)`. The marker UPDATE MUST set `updated_at=` explicitly (auto_now does not fire on `update()`), guarded by `lapsed_at__isnull=True`. Follow RESEARCH "Lapse service design" sketch. Keyset-paginate by pk in `lapse_past_balances` (never "select until none"). Re-raise `SoftTimeLimitExceeded` rather than swallow it in the per-balance `except Exception`. Docstring style: module leaf note "takes ids/ints, no review text (section 22)".

---

### `apps/credits/services/reaper.py` (service, CAS loop)

**Analog:** `refund_reservation` (consumption.py 241-292) is the primitive; Sentry style from consumption.py:
```python
sentry_sdk.capture_message(message, level="warning")   # ids-only message
```
Tests patch `"apps.credits.services.consumption.sentry_sdk.capture_message"`; so in reaper.py `import sentry_sdk` at module level and patch `apps.credits.services.reaper.sentry_sdk.capture_message`.

Apply: per row `refund_reservation(transaction_id=pk, reason="reaped_stale", actor_id=None)`. True means reaped (WARNING log ids+credits only), False means skipped, `RuntimeError` means errored (`level="error"`, ids only). No outer `atomic()` around the loop. No `skip_locked` pre-select (CAS-only). After the loop, call `lapse_balance` for touched past-period balances; one warning Sentry message per run if reaped > 0.

---

### `apps/credits/selectors/lapse.py`, `reservations.py` (selector)

**Analog:** `apps/credits/selectors/balances.py` (read-only, keyword-only args, no mutation). Return `values_list(...)[:limit]` as one query. Reaper filter must mirror `credit_tx_reserved_idx`: `status=RESERVED`, `created_at__lt=now - timedelta(minutes=settings.REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES)`, `order_by("created_at")`.

---

### `apps/credits/services/consumption.py::_settle_lost_race` (modify, D-01)

**Current (lines 323-330):**
```python
period = current_period()
lapsed = CreditTransaction.objects.filter(
    shop_credit_balance_id=row.shop_credit_balance_id,
    transaction_type=CreditTransaction.Type.LAPSED,
).exists()
if (row.period_year, row.period_month) != (period.year, period.month) or lapsed:
    outcome, credits_charged, reason = "free_draft", 0, "past_period"
```
**Change** the `lapsed` query only to `ShopCreditBalance.objects.filter(pk=row.shop_credit_balance_id, lapsed_at__isnull=False).exists()`. Keep the fresh read inside this function (not `_read_tx`).

---

### `config/settings/base.py`

**Analog:** line 134 `"apps.reviews.tasks.recover_stuck_syncs_task": {"queue": "default"},` and lines 236-237:
```python
# REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES: age after which a RESERVED credit is reaped (Phase 31).
REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5
```
Apply: add `apps.credits.tasks.lapse_expired_credit_balances_task` and `reap_stale_reservations_task` routes to `default`; add `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE = env.int(..., default=500)` and `REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE` with the same comment style (check how neighbouring settings use `env`; the TTL line is a plain literal, so a plain literal is also acceptable, but D-12 asks for env-overridable).

---

### Tests

**`test_pg_concurrency.py` additions.** Copy `_run_threads` (lines 128-150; closes `connections.close_all()` in `finally`, bounded join) and the shape of `test_charges_once_when_commit_and_refund_race` (lines 272-328):
```python
@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_...():
    ...reservations = [reserve_credits(shop_id=shop.pk, review_id=r.pk, credits=1, actor_id=None) ...]
    barriers = [threading.Barrier(2) for _ in reservations]
    def worker(index): barriers[index // 2].wait(timeout=10); ...
    errors = _run_threads(n * 2, worker)
    assert not errors, errors
    ... assert_ledger_reconciles(balance)
```
Apply: reaper (via `reap_stale_reservations` or `refund_reservation(reason="reaped_stale")`) versus `commit_reservation`; age rows first with `age_reservation`. Also N-thread overlapping `lapse_past_balances` (one LAPSED + one AuditLog per eligible balance). Lines 277-278 docstring says that test is explicitly "not the Phase 31 reaper-vs-late-commit test".

**`helpers.py`**: add `age_reservation(tx, minutes)` using the base `models.QuerySet.update(CreditTransaction.objects.filter(pk=tx.pk), created_at=...)` escape hatch (queryset `update()` raises `AppendOnlyViolation`).

**`test_consumption.py` helper:** reuse `_previous_period()` (lines 62-64) and `ShopCreditBalanceFactory(shop=shop, period_year=year, period_month=month, allocated_credits=10, consumed_credits=3)` (lines 395-398) for past balances. Time control: pass `now=`; patch `apps.credits.services.periods.utc_now` for `current_period()` callers (no freezegun installed).

**`test_tasks.py`**: copy `apps/reviews/tests/test_tasks.py` lines 54-70 (PeriodicTask seeded: task path, `queue == "default"`, `enabled`; `current_app.conf.task_routes[...]["queue"]`). Also assert crontab `minute=="5"`, `hour=="0"`, tz UTC.

## Shared Patterns

- **Thin task, logic in service** (CLAUDE.md §5/§12.3): task body = lazy import + service call + count log.
- **CAS-only settlement**: all status changes via `transition_status` / `refund_reservation`; never `.update()` on `CreditTransaction` (append-only).
- **AuditLog over bespoke log**: `entity_type="shop"`, `entity_id=str(shop_id)`, `action="shop.credits.<x>"`, org from the locked row, never from args.
- **Logging (section 22)**: ids and int credits only (`"credits.reaped tx_id=%s balance_id=%s credits=%d"`); never review text, draft, or moderation category. Test with a sentinel in the review comment.
- **Balance `.update()` must set `updated_at=`** (see consumption.py line 267 `updated_at=timezone.now()`).
- **Time**: use `utc_now()` / `current_period(now)` / injected `now`, never `datetime.now()`.
- **SQLite ignores `select_for_update`**: lock claims need `pg_concurrency` tests only.

## No Analog Found

| File | Role | Reason |
|---|---|---|
| keyset-paginated sweep loop in `lapse_past_balances` | service | No existing pk-keyset chunk loop in credits; follow RESEARCH "Sweep loop" sketch |
| `select_for_update(skip_locked=True)` | service | Existing code uses `select_for_update(of=("self",))` without `skip_locked`; add the flag per D-06 |

## Metadata

**Analog search scope:** `apps/credits/**`, `apps/reviews/{tasks.py,migrations,tests/test_tasks.py}`, `config/settings/base.py`
**Files scanned:** ~12 read or grepped; `apps/credits/tasks.py` does not exist yet (new file)
**Pattern extraction date:** 2026-11-11
