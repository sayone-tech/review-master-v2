# Phase 31: Monthly Renewal & Reservation Reaper - Context

**Gathered:** 2026-11-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Two Celery Beat jobs in `apps/credits`, backend only:

1. **Lapse sweep.** Every past-month `ShopCreditBalance` that hasn't lapsed yet is closed out:
   - If remaining > 0, it gets one LAPSED ledger row (`credits_delta = -remaining`) and one `shop.credits.lapsed` AuditLog row.
   - The sweep is idempotent and self-healing after missed runs.
2. **Reservation reaper.** Every 10 minutes, refunds RESERVED CONSUMPTION rows older than the reservation TTL through Phase 30's `refund_reservation`. It never refunds twice and never refunds a committed row.

CREN-02 (a new month starts from the org's current allocation with zero bonus) already holds through Phase 29's lazy `ensure_balance`. This phase only proves it with tests and adds no code.

Requirements: CREN-01, CREN-02, CREN-03 (plus the reaper-vs-late-commit `pg_concurrency` test promised under CQA-01).

**Not in this phase:**
- Superadmin allocation/bonus controls (Phase 32).
- Credits UI and the "Renews {date}" display (Phase 33).
- The "lapse not complete by 00:30 UTC" infra alert. It lives outside this repo; flag it to the deployment owner in the runbook.

</domain>

<decisions>
## Implementation Decisions

### Already closed upstream (do not re-litigate)
- Lapse does **not** change the balance's credit fields (spec §7.2). The row stays as the historical record. Remaining = `allocated + bonus - consumed` at lapse time, so unused bonus lapses too.
- Partial unique `credit_tx_one_lapse_per_balance` makes LAPSED once-per-balance (Phase 29). The delta-sign CHECK forbids a 0-delta LAPSED row.
- LAPSED rows are created COMMITTED, with `actor=None` (system event).
- The reaper refunds through `apps/credits/services/consumption.py::refund_reservation(transaction_id, reason, ai_usage_log_id=None, actor_id=None)`. The CAS and decrement share one atomic block. It returns True only for the CAS winner and raises `RuntimeError` if the decrement can't apply (that rolls back, so the row stays RESERVED).
- The TTL is the existing `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5`. The reply-path OpenAI timeout margin is already enforced (Phase 30).
- Phase 30's late commit (`_settle_lost_race`) treats a past-month or lapsed balance as a free draft (D-16). Cross-month charging never happens.
- The partial index `credit_tx_reserved_idx (status, created_at) WHERE status=RESERVED` exists for the reaper.
- Both Beat schedules are seeded by data migration (copy `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py` / `0016_beat_recover_stuck_syncs.py`), with explicit `timezone="UTC"`, on the `default` queue, added to `CELERY_TASK_ROUTES` and the CLAUDE.md §12.5 Beat table.
- Tasks are thin wrappers; the logic lives in `apps/credits/services/` (CLAUDE.md §5/§12.3).
- Inactive shops lapse normally (Phase 29 D-13).

### Zero-remaining lapse & marker
- **D-01:** Add a nullable `ShopCreditBalance.lapsed_at` (DateTimeField) as the sweep's done-marker. It is set for **every** lapsed balance, including those with 0 remaining (which can't get a LAPSED row). The sweep selects `lapsed_at IS NULL AND (period_year, period_month) < current`.
  - This adds one new credits migration (`credits/0002`).
  - `lapsed_at` becomes the only writable non-counter field on the balance, and only the lapse service writes it (NULL → timestamp, once, guarded by `lapsed_at__isnull=True`).
  - Index decision: the planner picks a partial index `WHERE lapsed_at IS NULL` or argues it isn't needed. Record it explicitly (CLAUDE.md §24 "explicit db_index decision").
  - **Reversibility:** costly. It's a schema change, and Phase 30's `_settle_lost_race` "lapsed" check should switch to (or also honour) `lapsed_at IS NOT NULL`. The planner must update that check and its tests.
- **D-02:** A balance with 0 remaining writes **no** LAPSED row and **no** AuditLog row. Only `lapsed_at` is set. This matches spec §7.2's "for each with remaining > 0".
- **D-03:** For remaining > 0, write one LAPSED row with `credits_delta = -remaining`. The `shop.credits.lapsed` AuditLog `after_data` carries `allocated, bonus, consumed, lapsed, period_year, period_month, transaction_id`, so support can see bonus credits lapsing. The AuditLog `organisation` is the balance's org, `entity_type="shop"`, `actor=None`.

### Cadence & sweep shape
- **D-04:** A **daily** Beat schedule at **00:05 UTC** runs the idempotent lapse sweep. This satisfies the spec's "00:05 UTC on the 1st" and also heals a missed night within 24h. On non-1st days it is a cheap no-op. One schedule, not two.
- **D-05:** The lookback covers **all past periods** (no cap). The `lapsed_at` marker keeps the query O(outstanding).
- **D-06:** A **single task with a chunked loop** (chunk = `REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE`, default 500):
  - Each balance runs in its own `transaction.atomic()`, using `select_for_update(skip_locked=True)` on the balance row.
  - Inside the lock it re-checks `lapsed_at IS NULL` and that there are no RESERVED rows. Overlapping runs (Beat plus manual) are therefore safe.
  - Per-balance failures are logged and skipped. They never abort the sweep.
  - The service function is `lapse_balance(*, balance_id) -> LapseOutcome` plus `lapse_past_balances(*, now=None) -> summary`, in `apps/credits/services/lapse.py`.

### Lapse vs held reservations
- **D-07:** The sweep **skips** any past balance that still has a RESERVED row. It stays `lapsed_at IS NULL` and is retried later. This satisfies SC4: a reservation that straddles midnight settles against its original month, and only then lapses.
- **D-08:** After refunding, the reaper **immediately** calls `lapse_balance` for each touched past-period balance that has no RESERVED rows left. Past-month numbers finalise within about 10 minutes instead of waiting for the next daily run.
- **D-09:** If a refund can't apply (`RuntimeError`, which means the ledger and balance invariants disagree), the balance **stays unlapsed** and the reaper reports a **Sentry error** with ids only. A lapse is never forced over an unsettled row.

### Reaper
- **D-10:** Each run selects up to `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE` (default 500) of the oldest stale rows: `status=RESERVED, transaction_type=CONSUMPTION, created_at < now - TTL`, ordered by `created_at`, using the partial index.
  - Each row goes through `refund_reservation(transaction_id=..., reason="reaped_stale", actor_id=None)`. Its CAS makes concurrent late commits and overlapping reaper runs safe; a lost CAS (False) counts as "skipped".
  - Rows beyond the batch roll to the next run.
  - The planner decides whether a `skip_locked` pre-select is needed on top of the CAS.
- **D-11:** Observability:
  - One **WARNING** log per reaped transaction, with ids and credits only (no review text, §22).
  - **One Sentry message per run** when the reaped count is > 0, carrying the count, so stuck workers stay visible without spamming.
  - The return value or summary log carries `reaped / skipped / errored / lapsed_after` counts.
- **D-12:** Two new env-overridable settings in `config/settings/base.py`: `REVIEWBEE_CREDIT_REAPER_BATCH_SIZE` (500) and `REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE` (500). The TTL reuses the existing setting. The 10-minute and daily-00:05 schedules live in the Beat migration.

### Tests that must exist
- A `pg_concurrency` test for the reaper versus a late commit on the same reservation: exactly one wins, and there is no double refund or refund of a committed row (CQA-01 / CREN-03).
- A `pg_concurrency` test for overlapping lapse sweeps: exactly one LAPSED row per balance.
- Idempotency: re-running the sweep adds nothing.
- Catch-up: several missed months all lapse in one run.
- Month-straddle: a reservation held across midnight. The sweep skips the balance, the reaper (or a late commit) settles it, then it lapses.
- CREN-02: a new month's balance equals the org's current allocation, bonus is 0, and nothing carries over.
- A query-count ceiling on the sweep's selection (§6).

### Claude's Discretion
- Task names (spec suggests `lapse_previous_month_credits_task`; a name reflecting the daily catch-up is fine), the summary dataclass shapes, and the module split between `lapse.py` and `reaper.py`.
- Whether the reaper pre-locks with `skip_locked` or relies on the CAS alone.
- The `lapsed_at` index shape.
- Celery retry config for the two tasks, following §12.3 conventions; both are idempotent.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spec & requirements
- `docs/completed/Requirements_Credits_System.md`: §6.2 (reaper), §7.2 (lapse), the §11 task table (~L389), the §12 module layout (~L421), §14.3 acceptance criteria, and the risks table (~L515).
- `.planning/REQUIREMENTS.md`: CREN-01..03, CQA-01.
- `.planning/ROADMAP.md`: Phase 31 success criteria and notes.

### Prior phases
- `.planning/phases/29-credits-ledger-foundation/29-CONTEXT.md`: ledger schema, constraints, D-13.
- `.planning/phases/30-metered-ai-reply-generation/30-CONTEXT.md`: D-01/D-02/D-16 late-commit policy, D-06 TTL, D-14 `transition_status`.

### Code
- `apps/credits/models.py`: `ShopCreditBalance`, `CreditTransaction` constraints and indexes.
- `apps/credits/services/consumption.py`: `refund_reservation`, `_settle_lost_race`.
- `apps/credits/services/ledger.py`: `transition_status`.
- `apps/credits/services/periods.py`: `current_period`, `utc_now`.
- `apps/reviews/migrations/0013_periodic_task_seed_polarity_reclassify.py` and `0016_beat_recover_stuck_syncs.py`: the Beat-seed migration pattern.
- `conftest.py`, `config/settings/test_pg.py`, `Makefile test-pg`, `.github/workflows/ci.yml backend-pg`: the PG concurrency harness.

### Project conventions
- CLAUDE.md §5 (thin tasks), §6.11/§6.12 (atomic + select_for_update), §7.6 (locks), §12.3/§12.5 (Celery task conventions, Beat table), §22 (no review text in logs), §27 (run `orm-performance-auditor`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `refund_reservation` already writes the `shop.credits.refunded` AuditLog row and logs at INFO, so the reaper adds only its WARNING and Sentry signal.
- `ensure_balance` already seeds a new month from the org's live allocation with 0 bonus, which is CREN-02.
- The `pg_concurrency` marker and `REQUIRE_PG` guard come from Phase 29.

### Established Patterns
- Beat schedules are DB-backed (`django_celery_beat`) and seeded by reversible data migrations.
- The CAS-on-status pattern (`transition_status`) is the only ledger mutation.

### Integration Points
- `_settle_lost_race` must honour `lapsed_at` (D-01).
- `config/settings/base.py`: `CELERY_TASK_ROUTES` and the new settings.
- CLAUDE.md §12.5 Beat table: add two rows.
- `docs/sre/v0.9-credits-rollout.md`: add the lapse/reaper schedule and the 00:30 alert handoff.

</code_context>

<specifics>
## Specific Ideas

- The daily 00:05 sweep is deliberately the same job as the "1st of month" run. The spec's 00:05-on-the-1st is satisfied, and every other day it is a no-op safety net.
- The 0-remaining lapse is silent (marker only), so the Activity Log never shows "lapsed 0 credits".

</specifics>

<deferred>
## Deferred Ideas

- Postgres immutability trigger on the ledger (still deferred from Phase 29).
- The infra alert "lapse not complete by 00:30 UTC" is owned by the deployment owner and lives outside this repo.

</deferred>

---

*Phase: 31-monthly-renewal-reservation-reaper*
*Context gathered: 2026-11-11*
