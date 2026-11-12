# Phase 31: Monthly Renewal & Reservation Reaper - Research

**Researched:** 2026-11-11
**Domain:** Django 6.0.2 + Celery Beat (django-celery-beat DB scheduler) + PostgreSQL row-locking / CAS ledger
**Confidence:** HIGH (everything below is read from shipped code in this branch; no new packages)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
D-01..D-12 are LOCKED (full text in `31-CONTEXT.md`; summary):
- **D-01** Add nullable `ShopCreditBalance.lapsed_at` (DateTimeField) = sweep done-marker, set for EVERY lapsed balance (incl. 0 remaining). Sweep selects `lapsed_at IS NULL AND (period_year, period_month) < current`. New migration `credits/0002`. Only the lapse service writes it (NULL -> ts, once, guarded `lapsed_at__isnull=True`). Planner records the index decision explicitly. `_settle_lost_race`'s "lapsed" check must switch to / also honour `lapsed_at IS NOT NULL` (+ update tests).
- **D-02** 0 remaining: NO LAPSED row, NO AuditLog row, only `lapsed_at`.
- **D-03** remaining > 0: one LAPSED row `credits_delta = -remaining` (COMMITTED, actor=None) + one `shop.credits.lapsed` AuditLog (`organisation`=balance org, `entity_type="shop"`, `actor=None`, `after_data` = `allocated, bonus, consumed, lapsed, period_year, period_month, transaction_id`).
- **D-04** DAILY Beat at 00:05 UTC (one schedule).
- **D-05** Lookback = all past periods, no cap.
- **D-06** Single task, chunked loop (`REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE`=500); per-balance `transaction.atomic()` + `select_for_update(skip_locked=True)`; re-check `lapsed_at IS NULL` and no RESERVED rows inside the lock; per-balance failures logged + skipped. `lapse_balance(*, balance_id) -> LapseOutcome`, `lapse_past_balances(*, now=None) -> summary` in `apps/credits/services/lapse.py`.
- **D-07** Sweep SKIPS past balances holding a RESERVED row (stay unlapsed, retried later).
- **D-08** After refunding, reaper immediately calls `lapse_balance` for each touched past-period balance with no RESERVED rows left.
- **D-09** `RuntimeError` from refund => balance stays unlapsed + Sentry error with ids only.
- **D-10** Reaper batch = `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE` (500), oldest-first (`status=RESERVED, transaction_type=CONSUMPTION, created_at < now - TTL`), per row `refund_reservation(transaction_id=..., reason="reaped_stale", actor_id=None)`; False => "skipped".
- **D-11** One WARNING log per reaped tx (ids + credits only); ONE Sentry message per run when reaped > 0; summary `reaped / skipped / errored / lapsed_after`.
- **D-12** Two env settings in `config/settings/base.py`; TTL reuses `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES`; schedules live in the Beat migration.
- Already closed upstream: lapse never changes balance credit fields; LAPSED once-per-balance partial unique; tasks are thin wrappers; Beat seeded by data migration with explicit `timezone="UTC"`, `default` queue, in `CELERY_TASK_ROUTES` and CLAUDE.md §12.5; inactive shops lapse normally.

### Claude's Discretion
Task names; summary dataclass shapes; `lapse.py`/`reaper.py` module split; reaper `skip_locked` pre-lock vs CAS-only; `lapsed_at` index shape; Celery retry config.

### Deferred Ideas (OUT OF SCOPE)
Postgres immutability trigger on the ledger; the "lapse not complete by 00:30 UTC" infra alert (outside this repo, flag in runbook); Superadmin controls (Phase 32); credits UI / "Renews {date}" (Phase 33).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CREN-01 | Beat job lapses unused credits for every past-month, not-yet-lapsed balance; idempotent; self-healing; LAPSED row + `shop.credits.lapsed` AuditLog | Sections "Lapse service design", "Beat seed", partial unique `credit_tx_one_lapse_per_balance` is the DB backstop |
| CREN-02 | New month starts from org's current allocation, bonus never carries over | Verified: `ensure_balance` already does this; NO CODE, tests only (see "CREN-02 confirmation") |
| CREN-03 | Beat job every 10 min refunds stale RESERVED; never double-refunds / refunds a committed row | "Reaper design"; CAS in `refund_reservation`; PG reaper-vs-late-commit test |
</phase_requirements>

## Summary

Phase 31 is a standard "thin Celery task -> service" phase on top of Phase 29/30 primitives that are already correct for it. Two new service modules (`apps/credits/services/lapse.py`, `reaper.py`), one tasks module (`apps/credits/tasks.py`), one schema migration (`lapsed_at` + partial index), one Beat-seed data migration, two settings, a one-line change to `_settle_lost_race`, and docs. No new packages. No contradictions with CONTEXT.md were found; two small refinements are flagged (see Open Questions: poison-row head-of-line, and a held-then-committed balance waiting up to 24h for lapse).

The race-safety story rests on mechanisms that already exist and are verified in code: `refund_reservation` does CAS + guarded decrement + AuditLog inside one `transaction.atomic()` and returns True only for the CAS winner; the commit path's CAS loser falls into `_settle_lost_race`. Postgres READ COMMITTED row-lock semantics guarantee a concurrent CAS blocks on the winner's uncommitted UPDATE and then re-evaluates `status='RESERVED'` to 0 rows. So the reaper needs **no** `skip_locked` pre-select; CAS-only is sufficient and avoids nesting atomics. The lapse sweep DOES need `select_for_update(skip_locked=True)` on the balance row (D-06) because its work is multi-statement (read RESERVED, insert LAPSED, update marker).

**Primary recommendation:** Build `lapse_balance` (balance-row lock, skip_locked, re-check marker + RESERVED, write LAPSED+AuditLog+`lapsed_at` in one atomic) and `reap_stale_reservations` (CAS-only via `refund_reservation`, then `lapse_balance` for touched past balances); keyset-paginate the sweep by pk (do NOT loop on "select unlapsed" or held balances are re-selected forever); inject `now` into both services so tests need no time-freezing library.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Lapse sweep / reaper scheduling | Celery Beat (DB-backed `django_celery_beat`) | — | CLAUDE.md §10/§12.5: retry-heavy, per-entity, DB-backed schedules |
| Lapse / reaper business logic | API/Backend services (`apps/credits/services/`) | — | CLAUDE.md §5: tasks are thin; logic testable without worker |
| Row selection for sweep / reaper | Backend selectors (`apps/credits/selectors/`) | — | Read-only query functions (§5); single-query shape asserted by a query-count test |
| Idempotency / exactly-once | Database (partial unique `credit_tx_one_lapse_per_balance`, CAS UPDATE, `lapsed_at IS NULL` guard) | Services (`select_for_update`) | DB constraints are the authoritative backstop |
| Observability | Sentry + structured logs | AuditLog (`shop.credits.lapsed`, existing `shop.credits.refunded`) | §21/§22 ids only |
| 00:30 UTC "lapse not complete" alert | Infra (outside repo) | — | Deferred; runbook handoff only |

## Standard Stack

No new dependencies. All verified present in this venv this session.

| Library | Version | Purpose |
|---------|---------|---------|
| Django | 6.0.2 [VERIFIED: `.venv` `django.VERSION` = (6, 0, 2)] | ORM, `select_for_update(skip_locked, of)` |
| celery + django-celery-beat | already pinned; beat migration head is `0019_alter_periodictasks_options` [VERIFIED: `site-packages/django_celery_beat/migrations/`] | Beat schedules seeded by data migration |
| sentry-sdk | already used in `consumption.py` (`sentry_sdk.capture_message`) [VERIFIED: consumption.py imports] | one-per-run signals |
| psycopg | 3.2.3 [VERIFIED: `.venv` import] (no psycopg2) | client-side binding by default => literal `status = 'RESERVED'` in SQL, so the partial index predicate matches [ASSUMED: Django's psycopg3 default `server_side_binding=False`; confirm with `EXPLAIN` in PG test if desired] |
| pytest 8.3.3 / pytest-django 4.9.0 / factory-boy | pinned in `pyproject.toml` [VERIFIED: pyproject.toml:40-42] | tests |

**Time control in tests:** `freezegun` / `time-machine` are NOT in `pyproject.toml` or the venv [VERIFIED: grep of pyproject.toml lines 40-52 + `pip list` showed no match]. Do not add one. Use (a) `now` parameters on the new services and (b) `apps.credits.services.periods.utc_now` as the single patch point (documented in `periods.py`).

## Package Legitimacy Audit

No external packages are installed by this phase. **Packages removed (SLOP):** none. **Flagged (SUS):** none.

## Verified Shipped Contracts

[VERIFIED: read this session] — quotes are verbatim.

**`apps/credits/models.py`**
- `ShopCreditBalance` fields: `shop`, `organisation`, `period_year = SmallIntegerField()`, `period_month = SmallIntegerField()`, `allocated_credits`, `bonus_credits` (default 0), `consumed_credits` (default 0), `created_at (auto_now_add)`, `updated_at (auto_now)`. Docstring: "NOTE: `updated_at` uses `auto_now`, which fires only on `save()`. Any future `QuerySet.update()` on balances MUST set `updated_at` explicitly." => the `lapsed_at` marker update via `.filter(...).update(...)` MUST pass `updated_at=` too.
- Balance constraints: `credit_balance_shop_period_uniq`, `credit_balance_month_range`, `credit_balance_nonneg`, `credit_balance_no_overspend` (`consumed_credits <= allocated_credits + bonus_credits`). Index: `credit_bal_org_period_idx (organisation, period_year, period_month)`. No current index on `lapsed_at`.
- `CreditTransaction` constraints: `credit_tx_one_initial_per_balance`, `credit_tx_one_lapse_per_balance` (`UniqueConstraint(fields=["shop_credit_balance"], condition=Q(transaction_type="LAPSED"))`), `credit_tx_only_consumption_reserved` (`Q(transaction_type="CONSUMPTION") | Q(status="COMMITTED")`), `credit_tx_delta_sign` (LAPSED/CONSUMPTION need `credits_delta__lt=0`). Partial index: `models.Index(fields=["status","created_at"], condition=Q(status="RESERVED"), name="credit_tx_reserved_idx")`.
- Enums: `Type.{INITIAL_ALLOCATION, BONUS_ALLOCATION, CONSUMPTION, LAPSED}`, `Status.{RESERVED, COMMITTED, REFUNDED}`. `ALLOWED_STATUS_TRANSITIONS` = `{(RESERVED, COMMITTED), (RESERVED, REFUNDED)}`.
- `CreditTransaction.created_at = DateTimeField(auto_now_add=True)`; the queryset `update()`/`delete()` raise `AppendOnlyViolation`; only `cas_status` calls `models.QuerySet.update` directly.

**`apps/credits/services/consumption.py`**
- `refund_reservation(*, transaction_id, reason, ai_usage_log_id=None, actor_id=None) -> bool`: `_read_tx` (returns False if row missing) -> `with transaction.atomic():` `transition_status(RESERVED -> REFUNDED)` (False => `return False`) -> `ShopCreditBalance.objects.filter(pk=..., consumed_credits__gte=row.credits).update(consumed_credits=F("consumed_credits") - row.credits, updated_at=timezone.now())`; `if updated != 1: raise RuntimeError(...)` (rolls the CAS back) -> writes `shop.credits.refunded` AuditLog -> `logger.info("credits.refunded tx_id=%s reason=%s credits=%d", ...)`; returns True. [VERIFIED: consumption.py `refund_reservation`]
- `_settle_lost_race`, current lapsed check (the line D-01 changes):
  ```python
  period = current_period()
  lapsed = CreditTransaction.objects.filter(
      shop_credit_balance_id=row.shop_credit_balance_id,
      transaction_type=CreditTransaction.Type.LAPSED,
  ).exists()
  if (row.period_year, row.period_month) != (period.year, period.month) or lapsed:
      outcome, credits_charged, reason = "free_draft", 0, "past_period"
  ```
  Sentry pattern: `sentry_sdk.capture_message(message, level="warning")` with ids-only message; tests patch `"apps.credits.services.consumption.sentry_sdk.capture_message"`. AuditLog pattern: `AuditLog.objects.create(organisation_id=..., actor_id=..., entity_type="shop", entity_id=str(shop_id), action="shop.credits.<x>", before_data=None, after_data={...})`.
- `reserve_credits` always targets the CURRENT period balance (`ensure_balance(shop_id=...)` default period) and takes the balance row lock `select_for_update(of=("self",))` before checking for an existing RESERVED row for the review.

**`ledger.transition_status`** — single conditional UPDATE via `cas_status`, returns bool; raises `InvalidStatusTransition` for pairs outside the allow-list. **`periods.py`** — `utc_now()` "is the single patch point for tests"; `current_period(now=None) -> Period(year, month)` (rejects naive datetimes); `next_period_start(period)`. **`allocation.ensure_balance(*, shop_id, period=None) -> (balance, created)`**.

**`selectors/balances.py`** — virtual balance reads only the CURRENT period row (`period_year=p.year, period_month=p.month`); does NOT need to know about `lapsed_at` (current-month rows are never lapsed). No change needed. Phase 33 may later want past-period views; out of scope.

**Existing tests:** `apps/credits/tests/` has `conftest.py`, `factories.py` (`ShopCreditBalanceFactory`, `CreditTransactionFactory` default type CONSUMPTION / status RESERVED / delta -1), `helpers.py` (`assert_ledger_reconciles`), `test_consumption.py`, `test_pg_concurrency.py` (+ `apps/reviews/tests/test_pg_reply_concurrency.py`), `test_settings.py`. Only existing `LAPSED`-related tests: `test_consumption.py::test_late_commit_is_free_draft_when_current_balance_has_lapsed_row` (creates a LAPSED row with delta -7 via factory, no `lapsed_at`) and `test_late_commit_is_free_draft_without_balance_write_when_reservation_is_prior_month`. [VERIFIED: grep + Read]

## Architecture Patterns

### Data flow

```
Beat 00:05 UTC daily -> lapse_expired_credit_balances_task ──> lapse_past_balances(now)
      selector: unlapsed past balance ids (keyset by pk, chunk 500) ──> for id: lapse_balance(id)
            atomic { SELECT ... FOR UPDATE SKIP LOCKED (lapsed_at IS NULL, pk, past period)
                     has RESERVED? -> HELD (skip, stays NULL)
                     remaining>0 -> INSERT LAPSED + AuditLog ; UPDATE lapsed_at (guarded) }
Beat */10 min ───────> reap_stale_reservations_task ──> reap_stale_reservations(now)
      selector: stale RESERVED ids (partial index, oldest first, LIMIT batch)
         for tx: refund_reservation(reason="reaped_stale")  -> True=reaped | False=skipped | RuntimeError=errored(Sentry error)
         WARNING log per reaped tx
      then for each touched balance whose period < current: lapse_balance(id)  (D-08)
      one Sentry warning per run if reaped > 0 ; return {reaped, skipped, errored, lapsed_after}
Late commit (Phase 30) -> commit CAS loses -> _settle_lost_race (checks lapsed_at)
```

### Recommended structure

```
apps/credits/
├── services/lapse.py          # LapseOutcome, LapseSummary, lapse_balance, lapse_past_balances
├── services/reaper.py         # ReapSummary, reap_stale_reservations
├── selectors/lapse.py         # list_unlapsed_past_balance_ids(now, after_pk, limit)  (read-only, 1 query)
├── selectors/reservations.py  # list_stale_reservations(now, limit)                    (read-only, 1 query)
├── tasks.py                   # two thin @shared_task wrappers (autodiscovered)
├── migrations/0002_shopcreditbalance_lapsed_at.py   # schema (AddField + AddIndex)
├── migrations/0003_beat_credit_lapse_and_reaper.py  # data (Beat seed, reversible)
└── tests/ test_lapse.py, test_reaper.py, test_tasks.py, test_renewal.py (CREN-02), + additions to test_pg_concurrency.py, test_settings.py, test_consumption.py, helpers.py
```
`config/celery.py` calls `app.autodiscover_tasks()` and `apps.credits` is in `INSTALLED_APPS` (base.py:53) [VERIFIED], so `apps/credits/tasks.py` is discovered with names `apps.credits.tasks.<fn>`.

### Lapse service design (D-01..D-07)

```python
# apps/credits/services/lapse.py  (sketch; full type annotations required: mypy strict)
@dataclass(frozen=True, slots=True)
class LapseOutcome:
    status: Literal["lapsed", "lapsed_zero", "skipped_held", "skipped_noop"]
    balance_id: int
    lapsed_credits: int = 0
    transaction_id: int | None = None

def lapse_balance(*, balance_id: int, now: datetime | None = None) -> LapseOutcome:
    now = now or utc_now()
    p = current_period(now)
    with transaction.atomic():
        bal = (
            ShopCreditBalance.objects.select_for_update(skip_locked=True, of=("self",))
            .filter(pk=balance_id, lapsed_at__isnull=True)
            .filter(Q(period_year__lt=p.year) | Q(period_year=p.year, period_month__lt=p.month))
            .first()                       # None => already lapsed, locked by another run, current/future period
        )
        if bal is None:
            return LapseOutcome("skipped_noop", balance_id)
        if CreditTransaction.objects.filter(
            shop_credit_balance_id=bal.pk,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status=CreditTransaction.Status.RESERVED,
        ).exists():
            return LapseOutcome("skipped_held", balance_id)       # D-07
        remaining = bal.allocated_credits + bal.bonus_credits - bal.consumed_credits
        tx_id = None
        if remaining > 0:                                          # D-02: zero => marker only
            tx = CreditTransaction.objects.create(
                shop_credit_balance=bal, shop_id=bal.shop_id, organisation_id=bal.organisation_id,
                transaction_type=CreditTransaction.Type.LAPSED,
                status=CreditTransaction.Status.COMMITTED, credits_delta=-remaining, actor=None)
            AuditLog.objects.create(organisation_id=bal.organisation_id, actor=None, entity_type="shop",
                entity_id=str(bal.shop_id), action="shop.credits.lapsed", before_data=None,
                after_data={"allocated": ..., "bonus": ..., "consumed": ..., "lapsed": remaining,
                            "period_year": ..., "period_month": ..., "transaction_id": tx.pk})
            tx_id = tx.pk
        ShopCreditBalance.objects.filter(pk=bal.pk, lapsed_at__isnull=True).update(lapsed_at=now, updated_at=now)
    ...
```
Key points:
- `select_for_update(of=("self",))` is the exact form already used in `reserve_credits`. `.first()` adds `ORDER BY pk LIMIT 1`; Django permits LIMIT with FOR UPDATE on PG (`supports_select_for_update_with_limit = True` in base features) [VERIFIED: base/features.py:236].
- **SQLite behaviour:** `has_select_for_update = False` on the base features and the SQLite backend does not override it; `SQLCompiler.as_sql` only emits FOR UPDATE under `if self.query.select_for_update and features.has_select_for_update:` [VERIFIED: compiler.py:840, features.py:50-53]. So `select_for_update(skip_locked=True)` is **silently ignored on SQLite** (no `NotSupportedError`): unit tests on SQLite exercise the logic but NOT the locking; locking is covered only by `pg_concurrency` tests.
- Wrap each balance in a `try/except Exception` at the sweep level (D-06: per-balance failure logged + skipped). An `IntegrityError` on `credit_tx_one_lapse_per_balance` would mean the lock logic failed; log at ERROR + Sentry, don't abort the sweep.
- Past-period guard inside `lapse_balance` (not just in the selector) so a direct call can never lapse the current month.
- `lapsed_at` marker must be set in the SAME atomic as the LAPSED row so the "lapsed" view is consistent for `_settle_lost_race` (which reads outside the lock).
- No deadlock cycle: `refund_reservation` locks tx row (CAS) then balance row (UPDATE); `lapse_balance` locks the balance row and only READS tx rows; `reserve_credits` locks balance then inserts. No path locks tx-then-balance AND balance-then-tx-row. [VERIFIED by reading all three]
- A refund in flight (tx CAS uncommitted, waiting on the balance lock held by lapse) still reads as RESERVED to the lapse check => `skipped_held` (conservative and correct). The reverse (lapse sees none RESERVED, then refund) cannot happen: nothing to refund.

### Sweep loop (D-05/D-06) — keyset pagination is mandatory

```python
def lapse_past_balances(*, now=None) -> LapseSummary:
    now = now or utc_now(); after_pk = 0; chunk = settings.REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE
    while True:
        ids = list_unlapsed_past_balance_ids(now=now, after_pk=after_pk, limit=chunk)   # ORDER BY pk, pk > after_pk, LIMIT chunk
        if not ids: break
        for balance_id in ids:
            try: outcome = lapse_balance(balance_id=balance_id, now=now)
            except Exception: logger.exception(...); errored += 1; continue
            ...tally...
        after_pk = ids[-1]
```
**Pitfall:** "while there are unlapsed rows: process" loops forever because HELD/locked/errored balances remain `lapsed_at IS NULL`. Advance by `pk > after_pk`. Selection shape: `ShopCreditBalance.objects.filter(lapsed_at__isnull=True).filter(Q(period_year__lt=y) | Q(period_year=y, period_month__lt=m), pk__gt=after_pk).order_by("pk").values_list("pk", flat=True)[:limit]` — one query per chunk regardless of rows (this is the query-count-ceiling test target; D-06 says "selection", §6.9).

### Index decision for `lapsed_at` (record explicitly in the migration/PLAN)

Recommendation: add a **partial index** `models.Index(fields=["period_year", "period_month"], condition=Q(lapsed_at__isnull=True), name="credit_bal_unlapsed_idx")`. Rationale: the unlapsed set is ~one row per active shop (current month) plus stragglers, while the table grows monotonically (shops x months); the daily sweep predicate is exactly this partial set, the index is tiny, and it mirrors the existing `credit_tx_reserved_idx` pattern. (Acceptable alternative per CONTEXT: argue no index needed at current scale; either is fine as long as the decision is recorded. `ORDER BY pk` keyset scans use the PK index + filter, so the partial index mainly helps the period predicate.) `AddField(null=True)` with no default is metadata-only on PG; `AddIndex` on a small table is fine non-concurrently. Reverse is automatic.

### Reaper design (D-08..D-11)

- **CAS-only, no `skip_locked` pre-select** (recommend). Reason: `refund_reservation` already owns its atomic and its CAS; a concurrent late commit or a second reaper blocks on the winner's row lock, then re-evaluates `status='RESERVED'` => 0 rows => `False` ("skipped"). A `skip_locked` pre-select would need an outer transaction holding row locks across `refund_reservation` (nested atomic => savepoint; held locks across up to 500 refunds) for no safety gain. The roadmap note "reaper uses skip_locked" is superseded by CONTEXT's explicit discretion; document the choice in the plan.
- Selector (partial-index friendly; ordering and predicate match `credit_tx_reserved_idx`):
  `CreditTransaction.objects.filter(status=RESERVED, transaction_type=CONSUMPTION, created_at__lt=now - timedelta(minutes=settings.REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES)).order_by("created_at").values_list("pk", "shop_credit_balance_id", "shop_credit_balance__period_year", "shop_credit_balance__period_month", "credits_delta")[:batch]` (one query, join to balance for the period so D-08 needs no extra query). All RESERVED rows are CONSUMPTION by `credit_tx_only_consumption_reserved`, so the type filter is redundant but harmless.
- Per row: `try: won = refund_reservation(transaction_id=pk, reason="reaped_stale", actor_id=None)`. `True` => `logger.warning("credits.reaped tx_id=%s shop_id=%s credits=%d", ...)` (ids + credits only, §22); `False` => skipped; `RuntimeError` => errored + `sentry_sdk.capture_message(f"credits.reaper.refund_failed tx_id=%s balance_id=%s", level="error")` and do NOT add the balance to the re-lapse set. Other `Exception` => log + errored, continue.
- D-08: after the loop, for each distinct touched balance with `(year, month) < current_period(now)`, call `lapse_balance(balance_id=..., now=now)`; count `outcome.status in {"lapsed","lapsed_zero"}` as `lapsed_after`. (`lapse_balance` re-verifies no RESERVED rows remain, so a balance that still holds another RESERVED row, or one whose refund failed, stays unlapsed automatically => D-09 holds by construction.)
- D-11: once per run if `reaped > 0`: `sentry_sdk.capture_message(f"credits.reaper.reaped count={reaped}", level="warning")`. Task returns `dataclasses.asdict(summary)` (JSON-serialisable for the Redis result backend).

### Celery task conventions (answer to focus #3)

Existing: `CELERY_TASK_TIME_LIMIT = 600`, `CELERY_TASK_SOFT_TIME_LIMIT = 300`, `CELERY_TASK_ACKS_LATE = True`, `CELERY_TASK_REJECT_ON_WORKER_LOST = True`, `CELERY_WORKER_PREFETCH_MULTIPLIER = 1`; `CELERY_TASK_ROUTES` ends with `"apps.reviews.tasks.recover_stuck_syncs_task": {"queue": "default"}, "apps.common.tasks.publish_celery_queue_depths_task": {"queue": "default"}` [VERIFIED: base.py:118-142]. The directly comparable existing tasks (`reclassify_polarity_task`, `recover_stuck_syncs_task` — both bare `@shared_task`, import service lazily inside the body, no autoretry) [VERIFIED: tasks.py]. **Recommendation:** bare `@shared_task` (no `autoretry_for=(Exception,)`) for BOTH tasks. Reason: §12.3's blanket autoretry is meant for single-entity work; these are idempotent fleet sweeps that handle per-row errors internally, the reaper re-runs in 10 minutes, the lapse re-runs next day (and a failed night is exactly what the self-healing design covers). Blanket retry would re-run the whole sweep and mask real failures; the 00:30 infra alert covers a missed run. If the planner wants a safety net for the daily lapse, restrict to infrastructure errors only: `autoretry_for=(OperationalError, InterfaceError), max_retries=2, retry_backoff=60, retry_jitter=True`. Add a comment citing this section so a reviewer does not "fix" it to §12.3. Add both to `CELERY_TASK_ROUTES` -> `{"queue": "default"}` and note in the module docstring that the 300 s soft limit can interrupt a very large catch-up; both services are resumable (idempotent, pk-keyset) so the next run continues.
Suggested task names: `lapse_expired_credit_balances_task`, `reap_stale_reservations_task`.

### Beat seed migration (answer to focus #2)

Shape verified in `reviews/0013` (CrontabSchedule) and `reviews/0016` (IntervalSchedule) [VERIFIED: both Read]. Both: `RunPython(seed, unseed)`; `PeriodicTask.objects.update_or_create(name=..., defaults={task, crontab/interval (other=None), enabled=True, queue="default", args=json.dumps([]), kwargs=json.dumps({}), description=...})`; reverse deletes by name; dependencies include `("django_celery_beat", "0019_alter_periodictasks_options")` (the installed head). Credits migration dir has only `0001_initial.py` [VERIFIED: ls], so:

- `credits/0002_shopcreditbalance_lapsed_at.py` (schema: AddField + AddIndex) — separate from data per `.claude/rules/migrations.md`. Generate with `makemigrations credits -n shopcreditbalance_lapsed_at` (descriptive name; 0001 was auto-generated style, so edit header as needed).
- `credits/0003_beat_credit_lapse_and_reaper.py` (data): `dependencies = [("credits", "0002_shopcreditbalance_lapsed_at"), ("django_celery_beat", "0019_alter_periodictasks_options")]`.
  - Lapse: `CrontabSchedule.objects.get_or_create(minute="5", hour="0", day_of_week="*", day_of_month="*", month_of_year="*", timezone="UTC")`; task `apps.credits.tasks.lapse_expired_credit_balances_task`; name `credits_lapse_expired_balances`.
  - Reaper: `IntervalSchedule.objects.get_or_create(every=10, period="minutes")` (note: the same IntervalSchedule row already exists from `recover_stuck_syncs`; `get_or_create` reuses it, and the unseed must delete only the PeriodicTask by name, never the shared schedule); task `apps.credits.tasks.reap_stale_reservations_task`; name `credits_reap_stale_reservations`.
- Test: a `test_tasks.py` check mirroring `apps/reviews/tests/test_tasks.py::test_periodic_task_seeded` (PeriodicTask exists, task path, `queue == "default"`, `enabled`, crontab `hour=="0"`/`minute=="5"`, timezone UTC), and a routes assertion mirroring `test_initial_backfill_dispatched_to_google_sync_queue` (via `current_app.conf.task_routes`).
- `reviews/0016` is credits/0001's dependency, so migration order is linear; no cross-app cycle.

### `_settle_lost_race` change (D-01)

Replace the LAPSED-row existence query with the marker (single query, same cost):
```python
lapsed = ShopCreditBalance.objects.filter(
    pk=row.shop_credit_balance_id, lapsed_at__isnull=False
).exists()
```
Recommend switching (not OR-ing): the lapse service always writes marker and row atomically, nothing lapsed in production before this phase ships, and `lapsed_at` also covers 0-remaining balances which have no LAPSED row. Keep the fresh read inside `_settle_lost_race` (do NOT fold into `_read_tx`, which runs before the CAS and can be stale). Tests to update: `test_late_commit_is_free_draft_when_current_balance_has_lapsed_row` (set `lapsed_at` instead of / as well as creating the LAPSED row; note ledger can't be edited, so use `ShopCreditBalance.objects.filter(pk=...).update(lapsed_at=timezone.now())` — balances are not append-only) and add a new case: 0-remaining-style lapsed balance (marker only, no LAPSED row) => free_draft. Check any query-count assertion in `test_consumption.py` still holds (same count).

### CREN-02 confirmation (focus #6)

[VERIFIED: allocation.py] `ensure_balance` derives `allocation` from the live `organisation__monthly_credit_allocation` on each call and creates `ShopCreditBalance(... allocated_credits=allocation)` via `get_or_create` with `bonus_credits` left at its model default 0 and `consumed_credits` default 0. Nothing reads prior-month rows. **CREN-02 needs no code.** Prove with tests only (see test map): prior-month row with bonus and unused credits, org allocation changed, `ensure_balance(shop_id)` for the current period => `allocated == org.allocation`, `bonus == 0`, `consumed == 0`, one INITIAL_ALLOCATION row for the new allocation, prior row unchanged (lapse never mutates credit fields).

### Anti-Patterns to Avoid
- Looping "select unlapsed until none" (infinite on held balances) — keyset by pk.
- `ShopCreditBalance.objects.update(lapsed_at=...)` without `updated_at=` (auto_now does not fire on `update()`).
- Writing a 0-delta LAPSED row (violates `credit_tx_delta_sign`; D-02 says marker only).
- Modifying balance credit fields at lapse (spec §7.2 / CONTEXT closed).
- Logging review text or drafts; the reaper only has ids and credit ints, keep it so (§22).
- Calling `datetime.now()` / `date.today()` in services (use `utc_now()` / injected `now`).
- Wrapping `refund_reservation` in an outer `atomic()` in the reaper (would make a `RuntimeError` roll back all previously reaped rows in the batch, or turn the CAS into a savepoint).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Refund + balance decrement + audit | Custom refund in the reaper | `refund_reservation(..., reason="reaped_stale", actor_id=None)` | CAS, guarded decrement, AuditLog, INFO log are already atomic and tested |
| Once-per-balance lapse | App-level "exists?" check alone | Marker guard + `credit_tx_one_lapse_per_balance` + row lock | DB constraint is the backstop for any lock bug |
| Distributed lock for the sweep | Redis `distributed_lock` | Row lock `skip_locked` on the balance | Per-balance DB lock is finer, transactional, and needs no Redis (§7.6 locks are for Redis-bound entity work; D-06 chose DB lock) |
| Period arithmetic | `date.today()`, manual month math | `periods.current_period(now)` / `next_period_start` | UTC seam; single patch point |
| Beat schedule creation | Manual admin / settings `CELERY_BEAT_SCHEDULE` | Data migration with `update_or_create` (`reviews/0013/0016` shape) | DB scheduler (`DatabaseScheduler`) ignores settings schedules; §12.5 |

## Runtime State Inventory

Not a rename/refactor/migration phase (it adds a column and two schedules). Not applicable. One relevant runtime note: the Beat `PeriodicTask` rows live in the DB, so deploying the migration IS what activates the schedules; the `django_celery_beat` `PeriodicTasks.last_update` is bumped by model save signals, but historical-model writes inside a migration do NOT fire those signals, so a **running Beat process picks up new rows only after its next schedule-refresh/restart** [ASSUMED: matches how reviews/0013/0016 were deployed; mention "restart beat after deploy" in the runbook as a precaution].

## Common Pitfalls

### Pitfall 1: Infinite sweep on held balances
Covered above (keyset by pk). Test: a held balance plus 2 eligible ones => sweep terminates, summary counts held=1.

### Pitfall 2: Backdating `created_at` in tests
`created_at` is `auto_now_add` and `CreditTransaction.objects.filter(...).update()` raises `AppendOnlyViolation`; passing `created_at=` to the factory is overridden (existing tests pass `created_at=timezone.now()` and rely on that). **Use `models.QuerySet.update(CreditTransaction.objects.filter(pk=tx.pk), created_at=...)`** (same escape hatch as `cas_status`). Add `age_reservation(tx, minutes)` helper to `apps/credits/tests/helpers.py`. [VERIFIED: models.py/managers.py]

### Pitfall 3: SQLite hides locking
Per above, `skip_locked` is ignored on SQLite. Do not claim lock behaviour is tested by SQLite tests; every concurrency claim needs a `pg_concurrency` test.

### Pitfall 4: Poison row at the head of the reaper queue
A row whose refund raises `RuntimeError` stays RESERVED and is the oldest, so every run re-selects it, re-fires the Sentry error every 10 min, and (if >= batch-size such rows) starves newer rows. With batch 500 starvation is theoretical; the repeated Sentry error is the intended D-09 "stays visible" signal. Planner: accept as-is and note in runbook (Sentry message prefix `credits.reaper.refund_failed`); no quarantine column (would be a new schema/scope).

### Pitfall 5: Held-then-committed balance waits for the next daily run
D-07 skips a balance with a RESERVED row. If that reservation then COMMITS (the normal case) nothing re-triggers lapse until the next 00:05 run (<= 24h). D-08 only fires after a reaper refund. This is consistent with CONTEXT and SC4 ("lapses only after the reservation is settled"); flagged in Open Questions only because Phase 33 will show "Renews" dates; no change recommended.

### Pitfall 6: Reserve racing the month boundary
`reserve_credits` calls `ensure_balance` (current period) outside the lock transaction. A reserve that resolves "current period" at 23:59:59.99 and acquires the lock after a lapse committed could theoretically insert a RESERVED row against an already-lapsed balance. Practically impossible: the sweep runs >= 00:05 (5 minutes after the boundary) and the ensure/lock gap is milliseconds. Accept; if it ever happened the reaper refunds it and `_settle_lost_race` treats it as past-period free draft. No action.

### Pitfall 7: Sweep exceeding the 300 s soft limit
Catch-up over many months/shops can exceed `CELERY_TASK_SOFT_TIME_LIMIT`. `SoftTimeLimitExceeded` rolls back only the in-flight balance's atomic; completed balances stay committed. Next run continues. Do not catch `SoftTimeLimitExceeded` in the per-balance `except Exception` swallow (it derives from `Exception`; re-raise it) so the task actually stops.

### Pitfall 8: AuditLog volume / entity id
One row per lapsed-with-credits balance per month. `entity_id=str(shop_id)` (consistent with existing credit events so the Phase 33 Activity Log can filter by shop).

## Code Examples

Reaper skeleton (sketch):
```python
def reap_stale_reservations(*, now: datetime | None = None) -> ReapSummary:
    now = now or utc_now()
    rows = list_stale_reservations(now=now, limit=settings.REVIEWBEE_CREDIT_REAPER_BATCH_SIZE)
    current = current_period(now)
    reaped = skipped = errored = 0
    touched: dict[int, bool] = {}              # balance_id -> is_past_period
    for tx_id, balance_id, year, month, delta in rows:
        try:
            won = refund_reservation(transaction_id=tx_id, reason="reaped_stale", actor_id=None)
        except RuntimeError:
            errored += 1; sentry_sdk.capture_message(f"credits.reaper.refund_failed tx_id={tx_id} balance_id={balance_id}", level="error"); continue
        except Exception: ...errored += 1; logger.exception(...); continue
        if not won: skipped += 1; continue
        reaped += 1; logger.warning("credits.reaped tx_id=%s balance_id=%s credits=%d", tx_id, balance_id, -delta)
        if (year, month) < (current.year, current.month): touched[balance_id] = True
    lapsed_after = sum(1 for b in touched if lapse_balance(balance_id=b, now=now).status in ("lapsed", "lapsed_zero"))
    if reaped: sentry_sdk.capture_message(f"credits.reaper.reaped count={reaped}", level="warning")
    return ReapSummary(reaped, skipped, errored, lapsed_after)
```

## State of the Art
N/A (stable Django/Celery patterns). Django 6.0's `select_for_update(skip_locked=True, of=("self",))` works as in 5.x.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | psycopg3 default client-side binding => Django emits literal `status = 'RESERVED'` so the partial index predicate matches | Standard Stack | Reaper query could seq-scan at scale; verify with `EXPLAIN` once; low blast radius (table small, scan once per 10 min) |
| A2 | Beat picks up historical-model-inserted PeriodicTask rows only after a beat restart/refresh | Runtime State | Runbook wording only; schedules might start slightly later than deploy |
| A3 | `SoftTimeLimitExceeded` subclasses `Exception` (so a naive `except Exception` would swallow it) | Pitfall 7 | If not, the re-raise guard is merely redundant |

## Open Questions

1. **Held-then-committed lapse latency (Pitfall 5)** — What we know: D-07/D-08 as locked produce <=24h delay when the straddling reservation commits normally. Recommendation: accept; no code. (Optional cheap alternative the planner may reject: have the reaper task also call `lapse_past_balances`; this is NOT in CONTEXT, so don't add unless the user asks.)
2. **Poison-row Sentry noise (Pitfall 4)** — Recommendation: accept, document in runbook.

No blockers; nothing contradicts D-01..D-12. One doc-level contradiction to fix: `docs/sre/v0.9-credits-rollout.md` line ~95 "Stranded reservations (until Phase 31's reaper)" manual-refund procedure must be reworded to "now automated by the reaper; manual procedure only if the reaper is disabled/failing".

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv` Python 3.12 + Django 6.0.2 | all tests | yes | 3.12 / 6.0.2 | — |
| PostgreSQL | `pg_concurrency` tests | not probed locally (`pg_isready` hung, no running service confirmed); CI `backend-pg` job provides `postgres:16-alpine` | — | `pg_concurrency` tests auto-skip on SQLite (`conftest.py`); run `make test-pg` (docker-compose `web` service) or CI |
| Redis | not needed (no Redis locks in this phase; test settings use locmem) | n/a | — | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 + factory-boy; `pyproject.toml [tool.pytest.ini_options]` (`--strict-markers --ds=config.settings.test`, `asyncio_mode=auto`, marker `pg_concurrency`) |
| Config file | `/Users/renjith/Documents/Accounts/review-master/pyproject.toml`; root `conftest.py` auto-skips `pg_concurrency` off PG, `REQUIRE_PG` hard-fails a non-PG run |
| Quick run command | `.venv/bin/pytest apps/credits -x -q --no-cov` (SQLite) |
| Full suite command | `.venv/bin/pytest --no-cov -q` (CI: `pytest --cov=apps --cov-fail-under=85`) |
| PG command | `make test-pg` (= `docker-compose -p review-master exec -e REQUIRE_PG=1 web pytest --ds=config.settings.test_pg -m pg_concurrency -x -q --no-cov -rs`) |
| Migration check | `.venv/bin/python manage.py makemigrations --check --dry-run` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CREN-01 | Past balance with remaining>0 -> one LAPSED row (delta=-remaining, COMMITTED, actor None) + one `shop.credits.lapsed` AuditLog with D-03 `after_data` keys; `lapsed_at` set; unused bonus lapses | unit | `.venv/bin/pytest apps/credits/tests/test_lapse.py -x -q --no-cov` | Wave 0 |
| CREN-01 | 0-remaining balance: `lapsed_at` set, NO LAPSED row, NO AuditLog (D-02) | unit | same | Wave 0 |
| CREN-01 | Idempotent: second `lapse_past_balances` adds 0 rows | unit | same | Wave 0 |
| CREN-01 | Catch-up: balances 1, 2, 14 months back all lapse in one run; current-month balance untouched; year-boundary (Dec -> Jan) via `now=` | unit | same | Wave 0 |
| CREN-01 | Past-period/current guard: `lapse_balance` on current-month balance is `skipped_noop` | unit | same | Wave 0 |
| CREN-01 | Inactive shop lapses (D-13) | unit | same | Wave 0 |
| CREN-01 / SC4 | Month straddle: RESERVED on a past balance -> sweep `skipped_held`, `lapsed_at` NULL; after commit (or reaper refund) -> lapses; after refund, `consumed` decreased and LAPSED delta = remaining post-refund | unit | `.venv/bin/pytest apps/credits/tests/test_lapse.py apps/credits/tests/test_reaper.py -x -q --no-cov` | Wave 0 |
| CREN-01 | Sweep terminates with held balance present (keyset) and per-balance exception does not abort the sweep (patch `lapse_balance` to raise for one id) | unit | test_lapse.py | Wave 0 |
| CREN-01 | Query-count ceiling on selector: identical count for 2 vs 5 eligible balances (`CaptureQueriesContext` + `assert_query_ceiling` fixture) | unit | test_lapse.py | Wave 0 |
| CREN-01 | `lapsed_at` honoured by `_settle_lost_race` (marker-only lapsed -> `free_draft`; existing LAPSED-row test updated) | unit | `.venv/bin/pytest apps/credits/tests/test_consumption.py -x -q --no-cov` | exists (edit) |
| CREN-01 | Overlapping sweeps: N threads call `lapse_past_balances` concurrently -> exactly one LAPSED row + one AuditLog per eligible balance, held balance untouched, no thread errors | pg_concurrency | `make test-pg` (or `.venv/bin/pytest --ds=config.settings.test_pg -m pg_concurrency apps/credits/tests/test_pg_concurrency.py`) | Wave 0 (add to existing file) |
| CREN-02 | After lapsing a prior month (bonus 3, unused), change org allocation, `ensure_balance(shop_id)` current period -> `allocated == org.allocation`, `bonus == 0`, `consumed == 0`, one INITIAL_ALLOCATION row, prior row credit fields unchanged | unit | `.venv/bin/pytest apps/credits/tests/test_renewal.py -x -q --no-cov` | Wave 0 |
| CREN-03 | Reaper refunds RESERVED older than TTL (aged via base `QuerySet.update`), restores `consumed`, writes one `shop.credits.refunded` (`reason="reaped_stale"`, actor None); fresh (< TTL) rows untouched; COMMITTED/REFUNDED rows untouched; `assert_ledger_reconciles` | unit | `.venv/bin/pytest apps/credits/tests/test_reaper.py -x -q --no-cov` | Wave 0 |
| CREN-03 | Re-run adds nothing (no double refund); batch size respected (set `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE` via `settings` fixture, rest rolls to next run, oldest first) | unit | test_reaper.py | Wave 0 |
| CREN-03 | `RuntimeError` path: patch `refund_reservation` (or craft consumed < credits) -> errored count, balance stays unlapsed, Sentry error captured with ids only (patch `sentry_sdk.capture_message` on the reaper module) | unit | test_reaper.py | Wave 0 |
| CREN-03 | One Sentry warning per run when reaped > 0, none when 0; WARNING log lines contain no review text (use `SECRET` comment sentinel as in test_consumption, assert not in caplog/Sentry/AuditLog) | unit | test_reaper.py | Wave 0 |
| CREN-03 | D-08: past-period touched balance lapsed right after refund (`lapsed_after == 1`); current-period balance not lapsed | unit | test_reaper.py | Wave 0 |
| CREN-03 / CQA-01 | **Reaper vs late commit**: per reservation, 2 threads (barrier): reaper vs `commit_reservation`; invariants: final status in {COMMITTED, REFUNDED}; if COMMITTED -> zero `shop.credits.refunded` rows for that tx and no `late_commit` row; if REFUNDED -> exactly one refunded row and the late commit re-deducts (`late_commit` row, outcome `rededucted`) so `consumed == credits`; `consumed <= allocated+bonus`; `assert_ledger_reconciles`; repeat for ~10 reservations (pattern of `test_charges_once_when_commit_and_refund_race`) | pg_concurrency | `make test-pg` | Wave 0 |
| CREN-03 | Overlapping reapers: K threads run `reap_stale_reservations` on same stale rows -> sum(reaped) == rows, one REFUNDED + one refunded AuditLog per row, `consumed` back to 0 (never negative; no `RuntimeError`) | pg_concurrency | `make test-pg` | Wave 0 |
| CREN-03 | Reaper vs late commit on a PAST-period balance -> commit result `free_draft`, balance not re-deducted, then balance lapses once | pg_concurrency | `make test-pg` | Wave 0 |
| Schedules | PeriodicTask `credits_lapse_expired_balances` (crontab minute 5 hour 0, UTC, queue `default`, enabled) and `credits_reap_stale_reservations` (interval 10 min) seeded; `CELERY_TASK_ROUTES` entries for both; task wrappers call services and return dict | unit | `.venv/bin/pytest apps/credits/tests/test_tasks.py -x -q --no-cov` | Wave 0 |
| Settings | `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE == 500`, `REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE == 500` (positive ints) | unit | `.venv/bin/pytest apps/credits/tests/test_settings.py -x -q --no-cov` | exists (edit) |
| Model | `lapsed_at` nullable; partial index `credit_bal_unlapsed_idx` declared (like `test_reserved_partial_index_covers_status_and_created_at_when_declared`); migration reverses (`migrate credits 0001` then forward) | unit | `.venv/bin/pytest apps/credits/tests/test_models.py -x -q --no-cov` + `makemigrations --check` | exists (edit) |

Time control: no freezing library. Pass `now=` to `lapse_past_balances`/`reap_stale_reservations`/`lapse_balance`; for code paths that call `current_period()` with no argument (e.g. `_settle_lost_race`, `ensure_balance`) patch `apps.credits.services.periods.utc_now`. Build past balances with explicit `period_year/period_month` on `ShopCreditBalanceFactory` (see `_previous_period()` helper in `test_consumption.py`).

PG test thread pattern: copy `_run_threads` + `threading.Barrier` + `@pytest.mark.pg_concurrency` + `@pytest.mark.django_db(transaction=True)` from `apps/credits/tests/test_pg_concurrency.py` (each thread `connections.close_all()` in `finally`; bounded `join(timeout=30)`). Setup rows inside the test thread (main) before starting workers; assert from the main thread after join.

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest apps/credits -x -q --no-cov`
- **Per wave merge:** `.venv/bin/pytest --no-cov -q` + `make test-pg` (or CI `backend-pg`) + `.venv/bin/python manage.py makemigrations --check --dry-run`
- **Phase gate:** full suite green with coverage >= 85% on services/selectors, `pre-commit run --all-files`, `make test-pg` green, then `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `apps/credits/tests/test_lapse.py`, `test_reaper.py`, `test_renewal.py`, `test_tasks.py` (new)
- [ ] `apps/credits/tests/helpers.py` — add `age_reservation(tx, minutes)` (base `QuerySet.update` on `created_at`)
- [ ] Edits: `test_pg_concurrency.py` (3 new PG tests), `test_consumption.py` (lapsed marker), `test_settings.py`, `test_models.py`
- [ ] Framework install: none needed

## Security Domain

`security_enforcement` is not disabled in `.planning/config.json` (key absent => enabled). Backend-only, no new endpoints, no user input.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no request surface; Beat/Celery internal) |
| V3 Session Management | no | — |
| V4 Access Control | yes (tenant integrity) | Services derive `organisation_id` from the locked balance/tx row, never from args (§9, §22 "Celery tasks verify organisation matches the entity"); tasks take no ids from users (sweep) / ids read from DB (reaper) |
| V5 Input Validation | minimal | Settings ints validated positive (settings test); no external input |
| V6 Cryptography | no | — |
| V7 Logging | yes | ids + credit counts only; no review text/drafts/moderation categories (§22); Sentry messages ids only |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Double refund / refunding a committed row (ledger inflation) | Tampering | CAS `status='RESERVED'` UPDATE (`transition_status`) + guarded decrement in same atomic; PG race tests |
| Double lapse (duplicate LAPSED rows) | Tampering | `credit_tx_one_lapse_per_balance` + `lapsed_at IS NULL` guard + `skip_locked` row lock |
| Cross-tenant write by sweep | Tampering / Info disclosure | Writes use the balance's own `organisation_id`; AuditLog `organisation` = balance org |
| PII in logs/Sentry | Info disclosure | ids + ints only; test with a secret sentinel in the review comment |
| Lapse forced over an unsettled reservation | Tampering (credit loss) | Skip when any RESERVED row exists (D-07), never force (D-09) |

## Docs to Touch (focus #7)
- `CLAUDE.md` §12.5 Beat table: add two rows (`lapse_expired_credit_balances_task` | `default` | Daily 00:05 UTC — idempotent catch-up lapse (v0.9/Phase 31); `reap_stale_reservations_task` | `default` | Every 10 minutes — refunds stale RESERVED credits). Also the §12.2 `CELERY_TASK_ROUTES` snippet if the planner wants it kept in sync (optional; the current snippet is already not exhaustive).
- `CLAUDE.md` §3 credits layout (currently lists `periods.py, credit_cost.py, allocation.py, ledger.py` and `selectors/balances.py` only — it already omits Phase 30's `consumption.py`): add `consumption.py`, `lapse.py`, `reaper.py`, `selectors/lapse.py`, `selectors/reservations.py`, `tasks.py`.
- `docs/sre/v0.9-credits-rollout.md` [exists, VERIFIED; 30-04 created it]: (a) add a "Monthly lapse & reaper" section: both schedules, how to run manually (`python manage.py shell -c "from apps.credits.services.lapse import lapse_past_balances; print(lapse_past_balances())"`), restart Beat after deploy, ids-only reporting; (b) hand off the **"lapse not complete by 00:30 UTC" alert** to the deployment owner (note: with the daily cadence the check is "a `lapsed_at`-NULL past-period balance older than 00:30 UTC on the 1st with no RESERVED rows", or task-heartbeat based); (c) reword the "Stranded reservations (until Phase 31's reaper)" bullet (~line 95) since the reaper now automates it. Coordinate: 30-04 ran in a parallel terminal and may still touch this file; edit only after it lands.
- `CLAUDE.md` §27: run `orm-performance-auditor` on the migration/selectors (roadmap/CONTEXT requirement); `tenant-security-auditor` is optional (no scoping surface) but cheap.
- `.planning/REQUIREMENTS.md`: CREN-01..03 status flips are the orchestrator's/verifier's job.

## Sources

### Primary (HIGH confidence) — all read this session
- `apps/credits/models.py`, `managers.py`, `services/{consumption,ledger,periods,allocation}.py`, `selectors/balances.py`, `tests/{conftest,factories,helpers,test_pg_concurrency,test_consumption,test_settings}.py`
- `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py`, `0016_beat_recover_stuck_syncs.py`, `apps/common/migrations/0003_...`; `apps/reviews/tasks.py` (`reclassify_polarity_task`, `recover_stuck_syncs_task`); `apps/reviews/tests/test_tasks.py` (seed test pattern)
- `config/settings/base.py:118-142, 232-240`; `config/settings/test.py`, `test_pg.py`; root `conftest.py`; `Makefile test-pg`; `.github/workflows/ci.yml backend-pg`; `config/celery.py`
- Django 6.0.2 source in `.venv`: `db/models/sql/compiler.py:840`, `db/backends/base/features.py:50-53,236`
- `docs/completed/Requirements_Credits_System.md` §6.2, §7.2, §11, §14.3; `.planning/{REQUIREMENTS,ROADMAP}.md`; CLAUDE.md §5, §12, §22, §24, §27; `.claude/rules/{migrations,testing-python}.md`

### Secondary / Tertiary
- None (no web research needed; this phase uses only in-repo patterns and the installed Django/Celery source).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, no new packages; versions read from venv
- Architecture: HIGH, composed from verified shipped primitives; lock-order analysis done by reading all three lock paths
- Pitfalls: HIGH, except A1-A3 (low-impact assumptions)

**Research date:** 2026-11-11
**Valid until:** 2026-12-11 (stable; invalidates only if Phase 30-04 or Phase 32 alter `consumption.py` / balance schema)
