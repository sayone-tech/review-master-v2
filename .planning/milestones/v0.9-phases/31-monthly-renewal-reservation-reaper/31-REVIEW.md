---
phase: 31-monthly-renewal-reservation-reaper
reviewed: 2026-11-11T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - apps/credits/migrations/0002_shopcreditbalance_lapsed_at.py
  - apps/credits/migrations/0003_beat_credit_lapse.py
  - apps/credits/migrations/0004_beat_credit_reaper.py
  - apps/credits/models.py
  - apps/credits/selectors/lapse.py
  - apps/credits/selectors/reservations.py
  - apps/credits/services/consumption.py
  - apps/credits/services/lapse.py
  - apps/credits/services/reaper.py
  - apps/credits/tasks.py
  - config/settings/base.py
  - docs/sre/v0.9-credits-rollout.md
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-11-11
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

The lapse and reaper logic holds up on the money-correctness questions it was asked to answer.

- **Double LAPSED:** blocked three ways. The `lapsed_at IS NULL` predicate is re-checked under a `skip_locked` row lock. The `lapsed_at` marker is set in the same atomic block as the ledger and audit rows. The `credit_tx_one_lapse_per_balance` unique constraint is a DB backstop.
- **Lapse over an unsettled reservation:** lock order is safe. `reserve` locks the balance row. `refund` locks the tx row, then the balance row. `lapse` locks the balance row and then does a plain read of the tx rows, so there is no deadlock cycle. Under READ COMMITTED an uncommitted refund or commit still looks RESERVED to the lapse, so the lapse skips the balance.
- **Double refund:** `transition_status` is a single conditional UPDATE, so one CAS winner per reservation. The decrement shares an atomic block with the CAS, so it rolls back together.
- **Tenant attribution:** every ledger and AuditLog row copies `organisation_id` and `shop_id` from the locked balance row (lapse) or the transaction row (refund). Nothing comes from arguments. Logs and Sentry messages carry ids and ints only.
- **Migrations:** the Beat seeds match the existing repo pattern. Both reverse functions delete only the `PeriodicTask` by name and never the shared crontab or interval rows.

No critical issues. The findings are hardening gaps, one operational starvation and alert-flood risk, and some config robustness.

## Warnings

### WR-01: Re-deduct and reserve UPDATEs do not guard on `lapsed_at IS NULL` (stale period check can spend lapsed credits)

**File:** `apps/credits/services/consumption.py:324-340` (also `reserve_credits`, `consumption.py:153-156`)

**Issue:**
- `_settle_lost_race` decides "current month and not lapsed" from a read of `current_period()` and a `lapsed_at` existence check. It then runs the re-deduct as an unlocked F() UPDATE whose WHERE clause checks only the capacity guard.
- `reserve_credits` has the same shape. `ensure_balance()` picks the period before the transaction, and the locked UPDATE does not re-check the period or `lapsed_at`.
- If the lapse commits between the decision and the UPDATE, the UPDATE still matches, because `consumed_credits` is untouched by a lapse and capacity still looks available. The result is `consumed_credits` rising, plus a new COMMITTED CONSUMPTION row, on a balance whose full remaining amount was just written off by a LAPSED row. The same credits are then spent and lapsed.
- The window is very narrow in practice. Reaching it needs a UTC month flip between the check and the UPDATE and the daily sweep or reaper re-lapse to commit inside it. Phase 31 is what introduces the writer that makes the race possible, because lapse is the first thing that treats a past-month balance as closed. It is also the only invariant here that is enforced by a point-in-time read and not atomically.

**Fix:** put the guard in the UPDATE predicate, so it is atomic with the row lock:
```python
updated = ShopCreditBalance.objects.filter(
    pk=row.shop_credit_balance_id,
    lapsed_at__isnull=True,
    consumed_credits__lte=F("allocated_credits") + F("bonus_credits") - row.credits,
).update(consumed_credits=F("consumed_credits") + row.credits, updated_at=timezone.now())
```
If `updated == 0`, `_settle_lost_race` already falls through to `free_draft` / `no_capacity`. A lapsed-balance miss would read better with reason `past_period`. Add the same `lapsed_at__isnull=True` to the `reserve_credits` UPDATE and raise `InsufficientCreditsError` or retry on a miss.

### WR-02: A poison RESERVED row can starve the reaper batch and floods Sentry every 10 minutes

**File:** `apps/credits/selectors/reservations.py:46-47` and `apps/credits/services/reaper.py:76-84`

**Issue:**
- Rows are selected oldest-first (`order_by("created_at", "pk")[:limit]`). A row whose refund raises `RuntimeError` (balance and ledger disagree) stays RESERVED, so it stays at the head of every subsequent selection.
- With 500 or more such rows the batch is filled with permanently failing rows, and no newer abandoned reservation is ever refunded.
- Even with only a few poison rows, each run emits one `capture_message(level="error")` per row. That is one Sentry event per stuck row every 10 minutes indefinitely. The runbook acknowledges this ("alert repeats every 10 minutes"), but a per-row event with the tx id in the message text also produces a distinct issue per row.
- Poison rows also pin their balance as unlapsed permanently, which is by design (D-09).

**Fix:**
- Keep processing independent of poison rows. Options: page by keyset (`pk > last_seen`) within one run so errored rows are not re-fetched in the same run. Across runs, rotate with `order_by("pk")` over a random offset, or skip rows already reported (for example a short-TTL Redis marker `credits:reaper:poison:{tx_id}`).
- Emit one aggregated Sentry event per run (`errored=N`, ids in `extra`) instead of one per row. Keep the per-row logger line.

### WR-03: Env-driven sweep and batch sizes are unvalidated (0 silently disables, negative crashes)

**File:** `config/settings/base.py:242-245`, consumed at `apps/credits/services/lapse.py:159` and `apps/credits/services/reaper.py:63`

**Issue:**
- `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE=0` makes `list_stale_reservations` return an empty list every run. No reservation is ever reaped and no error is raised, so credits stay locked and reviews return 409.
- `REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE=0` makes the first page empty and the sweep a silent no-op. A negative value hits Django's "Negative indexing is not supported" assertion on every run.
- Both are money-affecting jobs. A typo in the environment should fail at startup, not silently stop refunds and lapses.

**Fix:** clamp or validate at settings load:
```python
REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE = max(1, env.int("REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE", default=500))
REVIEWBEE_CREDIT_REAPER_BATCH_SIZE = max(1, env.int("REVIEWBEE_CREDIT_REAPER_BATCH_SIZE", default=500))
```
Alternatively raise `ImproperlyConfigured` when the value is below 1. Extend `test_settings.py` accordingly.

## Info

### IN-01: Reaper classifies any `RuntimeError` as a "refund cannot apply" ledger mismatch

**File:** `apps/credits/services/reaper.py:76-84` (raise site: `apps/credits/services/consumption.py:269`)

**Issue:** `except RuntimeError` is a broad contract. Any unrelated `RuntimeError` raised in the refund path, for example from a driver, Sentry or Celery, would be reported as `credits.reaper.refund_failed` and sent without a traceback. That sends operators to investigate balance and ledger drift that does not exist. `refund_reservation` also uses the same bare type as an invariant signal.

**Fix:** introduce a dedicated `RefundInvariantError(RuntimeError)` in `apps/credits/exceptions.py`, raise it from `refund_reservation`, and catch only that in the reaper. Everything else then falls into the `logger.exception` branch with a traceback.

### IN-02: Soft-time-limit abort drops the progress counters

**File:** `apps/credits/services/lapse.py:176-177`, `apps/credits/services/reaper.py:74-75, 114-115`

**Issue:** `SoftTimeLimitExceeded` is correctly re-raised, with every unit atomic and safe to resume. The counters accumulated so far are lost, though. Operators see a bare exception with no sense of how far the sweep got. In the reaper, an abort in the refund loop also skips the D-08 re-lapse of already-touched balances until the next daily sweep, and skips the `credits.reaper.reaped` Sentry message for refunds that did commit.

**Fix:** wrap the loop in `try/finally` (or catch, log an ids-free partial summary at WARNING, and re-raise) so the counters are always logged. In the reaper, consider running the re-lapse of `touched` in the `finally` block, bounded by a short remaining budget.

### IN-03: Migration 0002 carries unrelated cross-app dependencies

**File:** `apps/credits/migrations/0002_shopcreditbalance_lapsed_at.py:9-13`

**Issue:** the migration adds a field and an index on `credits` only, yet depends on `organisations.0003_organisation_monthly_credit_allocation` and `shops.0008_shop_sync_depth`. These came from the autogenerator and add needless ordering coupling. It is harmless today, but it constrains future migration squashing and reversal ordering.

**Fix:** drop the two unrelated dependencies and keep only `("credits", "0001_initial")`, unless the generator added them for a reason you can name. The index is created non-concurrently, which is fine at the current table size. Note that in the rollout doc if the table is large before deploy.

---

_Reviewed: 2026-11-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
