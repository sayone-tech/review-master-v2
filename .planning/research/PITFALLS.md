# Pitfalls Research

**Domain:** Per-shop monthly credit ledger (reserve / commit / refund / lapse) added to an existing Django 6 / PostgreSQL 16 / Celery multi-tenant SaaS (v0.9 AI Reply Credits)
**Researched:** 2026-11-11
**Confidence:** HIGH for codebase-specific findings (verified by reading the repo at the cited paths); HIGH for Postgres/Django locking semantics; MEDIUM for the client-abort behaviour under Daphne (verify in a spike)

> Phase labels used below are logical groupings, because the v0.9 roadmap does not exist yet. The roadmapper should map them onto Phases 29+.
> - **P-TEST**: test infrastructure (Postgres CI job, markers, time injection)
> - **P-MODEL**: `apps/credits` models, migration, org field, lazy ensure, cost function, settings
> - **P-CONSUME**: reserve/commit/refund, `generate_reply` wiring, reaper
> - **P-LAPSE**: monthly lapse task and Beat seeding
> - **P-API**: credits, cost and history endpoints, bonus endpoint, scoping
> - **P-UI**: Shops list badge, Shop Details card, composer, modals, AuditLog visibility

---

## Critical Pitfalls

### Pitfall 1: The test suite runs on in-memory SQLite, so every locking and race bug passes CI and fails in production

**What goes wrong:** `config/settings/test.py:51` sets `DATABASES = sqlite3 ":memory:"`. `.github/workflows/ci.yml` has no Postgres service. On SQLite:
- `select_for_update()` is silently ignored (and Django skips its "must be inside atomic" check).
- An `IntegrityError` caught without a savepoint does not poison the transaction. On Postgres it does ("current transaction is aborted").
- Threads cannot share a `:memory:` database, so a threaded concurrency test either errors or tests nothing.
- `skip_locked` and `of=` are not exercised.

A green 85% coverage run therefore proves nothing about the central acceptance criterion (AC 7: "no over-spending past the limit").

**Why it happens:** The project's fast-test policy (CLAUDE.md §16) was fine until the first feature whose correctness depends on row locks.

**How to avoid:**
- Add a Postgres-backed settings module (e.g. `config.settings.test_pg`) and a second CI job with `services: postgres:16`. Run only `-m pg_concurrency` tests there.
- Register the marker in `pyproject.toml`. `--strict-markers` is in `addopts`, so an unregistered marker fails collection.
- Split the tests: state-machine logic (RESERVED to COMMITTED/REFUNDED, double-refund, late commit, lapse idempotency) is tested deterministically on SQLite by calling the steps sequentially in the interleaved order. Only true lock/race tests (N threads, one balance) run on Postgres.
- Make the actual over-spend guard testable on both engines. Use a conditional single-statement update: `ShopCreditBalance.objects.filter(pk=..., ...remaining >= cost).update(consumed_credits=F("consumed_credits") + cost)` and treat rowcount 0 as insufficient. Keep `select_for_update` for reading values.

**Warning signs:** A concurrency test that passes with `pytest` locally but never ran against Postgres. Any "concurrent" test that does not use `threading` plus a real DB. `select_for_update` appearing in code that has no `transaction.atomic()`; it works on SQLite and raises `TransactionManagementError` on Postgres.

**Phase to address:** P-TEST, first. Nothing in P-CONSUME can be called verified without it.

---

### Pitfall 2: Lazy first-use creation race (duplicate rows, double INITIAL ledger rows, poisoned transaction)

**What goes wrong:** Two requests for the same shop in a new month both find no `ShopCreditBalance`. Variants:
1. No DB unique constraint on `(shop, period_year, period_month)`. Duplicate balance rows give each request its own pool.
2. A naive `try: create() except IntegrityError: get()` inside `atomic()` works on SQLite and aborts the transaction on Postgres.
3. Both racers write an `INITIAL_ALLOCATION` CreditTransaction and a `shop.credits.allocated` AuditLog row, so the ledger double-counts the grant.
4. `get_or_create()` followed by a separate un-locked read. The row exists, but the lock was never taken.
5. `select_related(...).select_for_update()` locks the joined `Shop` and `Organisation` rows too. Every reserve then serialises across the entire organisation and collides with org edits. A nullable-side join also errors on Postgres.

**Why it happens:** The spec's step 3 ("select for update; if row does not exist, create") reads as one atomic step. It is not.

**How to avoid:**
- Enforce `UniqueConstraint(fields=[shop, period_year, period_month])` in the migration. The spec already requires this (AC 4).
- Create the row in its own short `transaction.atomic()` using `get_or_create(shop_id=..., period_year=..., period_month=..., defaults={...})`. Django wraps the create in a savepoint, and the `created` flag is reliable. Write the `INITIAL_ALLOCATION` transaction and AuditLog row only when `created is True`, in that same atomic. This is the opposite of the `bulk_create(ignore_conflicts=True)` idiom in the reviews canonical code (§29.3): `ignore_conflicts` does not say who won, so it cannot gate the INITIAL ledger row.
- Then lock in a separate step: `ShopCreditBalance.objects.select_for_update(of=("self",)).get(pk=...)`. No `select_related`.
- Compute `allocated_credits` from a fresh `Organisation.objects.values_list("monthly_credit_allocation", flat=True)` read. Do not use the request's cached `user.organisation`.
- Skip the zero-delta INITIAL row when allocation is 0, but still create the balance row (bonus needs it).
- Bonus allocation must use the same `ensure_balance()` helper. A Superadmin bonus on a shop that has not used AI this month would otherwise hit `DoesNotExist` and return 500.

**Warning signs:** Two INITIAL rows for one `(balance, month)`. `TransactionManagementError` in Sentry on the first request of a month. Postgres `FOR UPDATE` lock waits on `organisations_organisation`.

**Phase to address:** P-MODEL (constraint, `ensure_balance`), verified in P-TEST (Postgres N-thread first-use test).

---

### Pitfall 3: Mid-month allocation change is silently applied by lazy creation (violates spec §7.3 / AC 16)

**What goes wrong:** Superadmin changes `monthly_credit_allocation` on Nov 15 from 100 to 500. Shop X first uses AI on Nov 20, so its row is lazily created with 500 in November. The spec says the change takes effect next month. Shops that already had November rows keep 100. The same org now has inconsistent November budgets depending on who clicked first.

**Why it happens:** Lazy creation reads "the current allocation" at creation time, not "the allocation in force at the start of the month."

**How to avoid:** Pick one explicit behaviour in discuss-phase and test it:
- **(Recommended)** On org edit, inside the same atomic as the audit write, materialise the current-month balance rows for the org's shops with the OLD value (`bulk_create(..., ignore_conflicts=True)`). The cost is some unused rows, only on edit, which is not the hot path. Or:
- Store `previous_monthly_credit_allocation` and `allocation_changed_at` on Organisation. Lazy creation uses the previous value when the change happened in the same calendar month.
- Write `organisation.credits.set` only when the value actually changed. A PATCH of other fields must not emit it.

**Warning signs:** Two shops in one org with different `allocated_credits` for the same month with no bonus rows. A test for AC 16 that only covers shops that already had a row.

**Phase to address:** P-MODEL (field and ensure logic), P-API (org edit service).

---

### Pitfall 4: Double refund, reaper versus late-arriving success (and explicit refund versus reaper)

**What goes wrong:** Timeline: reserve, OpenAI call stalls, reaper refunds at the TTL (`consumed -= cost`, status REFUNDED), the call then succeeds, the commit step flips REFUNDED to COMMITTED or refunds again. Outcomes: consumed goes negative or stays inflated, the user receives a draft for free, or both. The same race exists between the view's own `refund()` on OpenAI failure and the reaper.

**Why it happens:** Status is read, decided in Python, then written (check-then-act), and refund is coded as "restore the balance" rather than as one atomic state transition.

**How to avoid:**
- Make every status change a conditional UPDATE: `CreditTransaction.objects.filter(pk=tx, status=RESERVED).update(status=REFUNDED, resolved_at=now)`. Only if rowcount is 1, run `ShopCreditBalance.filter(pk=...).update(consumed_credits=F("consumed_credits") - cost)`. Do both in one `atomic()`. Same for commit (`RESERVED -> COMMITTED`).
- Keep one lock order everywhere (tx row, then balance row via F-update, never the reverse across paths) to avoid deadlocks between reaper and request.
- Add `CheckConstraint(consumed_credits >= 0)` and `CheckConstraint(consumed_credits <= allocated_credits + bonus_credits)`. Django supports `F()` in constraints. A double refund then fails loudly instead of silently inflating credits. The reaper must wrap each transaction in its own `atomic()` and catch `IntegrityError`, so one bad row does not abort the batch.
- Decide the late-commit policy up front. Commit returns rowcount 0 means the reaper already refunded. **Recommended:** return the draft anyway (OpenAI was billed and the user is waiting), attempt one conditional re-deduct, and if that fails log an AuditLog and Sentry event (`credit.late_commit_after_refund`). A rare free draft is cheaper than discarding a billed one. With Pitfall 5's timeout fix this should be near-impossible.
- `consumed_credits` must only ever move via `F()` updates, never `balance.save()` from a stale instance (it would clobber a concurrent bonus or refund).

**Warning signs:** `consumed_credits` negative or `remaining > allocated + bonus`. COMMITTED and REFUNDED rows for the same review within seconds. Reconciliation invariant violated: `consumed_credits == SUM(-credits_delta) WHERE type=CONSUMPTION AND status IN (RESERVED, COMMITTED)`. Ship this as a test and a management check.

**Phase to address:** P-CONSUME. The state-machine test (sequential interleaving) runs on SQLite; the lock test runs in P-TEST's Postgres job.

---

### Pitfall 5: The reaper refunds a call that is still in flight (the 5-minute TTL is shorter than the real worst case)

**What goes wrong:** `apps/integrations/openai/client.py:54` builds `OpenAI(api_key=...)` with no timeout. The installed SDK's `DEFAULT_TIMEOUT` is 600s (verified in `.venv/.../openai/_constants.py`), with SDK-level retries on top. A slow but alive call can legitimately run longer than the 5-minute TTL. Add two moderation calls with their own retry. The reaper then refunds a reservation whose call later succeeds: free reply, plus Pitfall 4.

**Why it happens:** The spec treats TTL as a crash-recovery number without checking it against the actual timeout configuration. Cloud Run's 60s request timeout (CLAUDE.md §10) means any call over 60s is already abandoned by the client anyway.

**How to avoid:**
- Bound the reply path: `_get_client().with_options(timeout=30, max_retries=1)` for `call_openai_reply_generation` only. Do NOT change the shared client defaults, because enrichment uses them.
- Keep the invariant `RESERVATION_TTL >= 2 x worst-case in-flight time`. Document it next to `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES` and add a settings sanity test.
- Age the reservation from `CreditTransaction.created_at` (the reserve commit time). The reaper selects with `select_for_update(skip_locked=True)` in bounded batches so it never grabs a row a request is committing.
- Effective stale time is TTL plus up to 10 minutes of Beat cadence (up to 15 minutes). The UI must not promise instant refunds after a crash.

**Warning signs:** `latency_ms` on `AiUsageLog` for `reply_generation` rows approaching the TTL. Any REFUNDED reservation that has a SUCCESS `AiUsageLog` for the same review within the window.

**Phase to address:** P-CONSUME (timeout and TTL), verified by the stalled-OpenAI test.

---

### Pitfall 6: Refund or commit credits the wrong month at the month boundary, and lapse then strands the refund

**What goes wrong:**
(a) Reserve at 23:59:58 Oct 31, commit or refund at 00:00:03 Nov 1. If refund looks up "current month's balance" with `now()`, it decrements the November balance (possibly below zero or creating a November row) and leaves October permanently over-charged.
(b) A RESERVED row still on the October balance when the 00:05 lapse runs. Lapse computes `remaining` including the reserved credits. The reaper then refunds into October, so `remaining` rises after the LAPSED row was written. Those credits are stranded and the ledger no longer reconciles.

**How to avoid:**
- Refund and commit always operate on `tx.shop_credit_balance_id`. They never compute a period.
- `lapse_balance(balance_id)` is the single per-balance function. It skips any balance that still has RESERVED rows (the catch-up in Pitfall 7 picks it up later). The reaper calls it after refunding into a past-period balance, so late refunds are lapsed promptly.
- Also write a test for a clock that crosses midnight between reserve and commit.

**Warning signs:** `ShopCreditBalance` rows for the current month created by the refund path. A past-period balance with `remaining > 0` and an existing LAPSED row.

**Phase to address:** P-CONSUME (balance-by-FK), P-LAPSE (skip and re-lapse), with a boundary test in each.

---

### Pitfall 7: Lapse is not idempotent as specified, and "previous month" drops months after an outage

**What goes wrong:** Spec §7.2 says LAPSED writes a row and changes nothing on the balance. A re-run recomputes `remaining > 0` and writes a second LAPSED row (double negative delta, double `shop.credits.lapsed` audit). Also, "find previous month's rows" computed from `now()` misses a month if Beat was down across the 1st, or if the task runs twice because Beat restarted or `DatabaseScheduler` fired again.

**How to avoid:**
- One LAPSED row per balance, enforced in the DB: partial `UniqueConstraint(fields=["shop_credit_balance"], condition=Q(transaction_type="LAPSED"), name=...)`. Write it with `bulk_create(ignore_conflicts=True)`, and write the AuditLog only for rows actually created (re-query the created set, or insert and audit per balance inside one atomic).
- Select by `period < current_period AND NOT EXISTS(LAPSED row)`, not by "previous month". This gives free catch-up after an outage and makes re-runs no-ops.
- Compute "current period" via one helper using `datetime.now(UTC)` (not `date.today()`, which is server-local) with an injectable `now`.
- Seed the Beat entry like `apps/reviews/migrations/0016_beat_recover_stuck_syncs.py` but with `CrontabSchedule(minute="5", hour="0", day_of_month="1", timezone="UTC")` set explicitly. Use `PeriodicTask.update_or_create(name=...)` and avoid `CrontabSchedule.get_or_create` (raises `MultipleObjectsReturned` if duplicates exist). Add a `CELERY_TASK_ROUTES` entry and make sure `apps.credits` is in INSTALLED_APPS so tasks autodiscover.
- Monitoring: alert if no lapse completion by 00:30 UTC (spec §15), not just "task ran".

**Warning signs:** Two LAPSED rows for one balance. A balance with `remaining > 0` and `period < current` with no LAPSED row.

**Phase to address:** P-LAPSE.

---

### Pitfall 8: Negative or over-allocated balances through code paths other than the happy reserve

**What goes wrong:** The reserve path checks `remaining >= cost` but other paths do not: a UX pre-check read before the lock (TOCTOU), refunds applied twice, full-object `save()`, Django admin editing, and the Superadmin who lowers a value. The result is `consumed > allocated + bonus` or negative `consumed`.

**How to avoid:**
- Check sufficiency inside the lock (or inside the conditional UPDATE). A selector-based "can afford?" is a hint for the UI only.
- DB `CheckConstraint`s (Pitfall 4) on all three integer columns, plus non-negative `allocated/bonus`.
- Register the models in Django admin as read-only (`has_add/change/delete_permission = False`). Admin edits bypass the ledger and the AuditLog.
- Ledger "immutability" is not literally true here: status flips on one row. Add `resolved_at`, restrict mutation to one service module, and never expose an update endpoint. Do not delete rows on refund.
- Use `on_delete=PROTECT` for balance to shop and `SET_NULL` for review, ai_usage_log, and performed_by so the ledger survives user or review cleanup.

**Warning signs:** `UPDATE ... SET consumed_credits` anywhere outside `apps/credits/services`. Admin "Save" buttons on credit models.

**Phase to address:** P-MODEL (constraints, admin), P-CONSUME.

---

### Pitfall 9: Bonus allocation racing an in-flight reservation, or landing in the wrong month

**What goes wrong:**
- Lost update: bonus code does `balance = get(); balance.bonus_credits += n; balance.save()` while a reserve or refund changes `consumed_credits`, overwriting it.
- Wrong month: the modal opens at 23:59 Oct 31 showing October numbers, the Superadmin submits at 00:01 Nov 1, and the server applies the bonus to November without telling anyone.
- The modal's "Remaining: 35" is a snapshot. Never compute anything from it.
- Double-click submits two bonuses.

**How to avoid:**
- `bonus_credits = F("bonus_credits") + n` plus the `BONUS_ALLOCATION` tx plus audit, in one atomic, using `ensure_balance()` first (Pitfall 2). Refund and bonus commute when both use `F()`. This is why Pitfall 4's "never `.save()` a stale instance" rule matters.
- The request carries the `period` (year and month) the modal displayed. The server rejects a mismatch with 409 and the current period.
- Derive `organisation_id` from `shop.organisation_id` server-side. Never accept it from the payload. Bound `amount` (1 to 10,000) and `notes` length.
- Disable the submit button while pending; the 10,000 cap limits blast radius.

**Warning signs:** `bonus_credits` that does not equal the sum of BONUS tx deltas for the balance.

**Phase to address:** P-API (bonus service and endpoint), P-UI (modal).

---

### Pitfall 10: Tenant and role leakage on the credits surfaces

**What goes wrong:** Verified gaps in the existing code that new credit fields will inherit:
- `ShopViewSet.list` (`apps/shops/views.py:178`) calls `list_shops(organisation_id=...)`, which has no `StaffAccessScope` filter. `retrieve` uses `TenantScopedViewSet`, which is org-only. If `remaining_credits` is added to `ShopReadSerializer` or the list annotation, Staff see credits for shops outside their scope, violating AC 28.
- `ReviewTargetViewSet._verify_shop_org` (nested `shop_pk` pattern) checks organisation only, not staff scope. Copying it for `/shops/{shop_pk}/credits/` repeats the gap.
- `TenantScopedViewSet.get_queryset` returns `none()` when `organisation_id` is null (Superadmin). The Superadmin Shop Details credits card, which the spec requires, will silently get 404/empty. Superadmin views must not inherit `TenantScopedViewSet`, but then they have no automatic tenant filter at all.
- Spec §10 lets Staff call `/credits/history/`, which exposes `performed_by` identities and Superadmin `notes`. This conflicts with the §2 role table (Staff: no credit audit log).
- The cost endpoint at `/reviews/{id}/generate-reply/cost/` must live as an `@action` on `ReviewViewSet` (which already applies org and staff-shop scoping in `get_queryset`), not as a new view that re-implements scoping.

**How to avoid:**
- One selector `get_accessible_shop_for_credits(user, shop_id)` that applies role, organisation, and `get_accessible_shop_ids` for Staff, used by every credit endpoint and by the list annotation.
- On the shops list for Staff, annotate `remaining_credits` only for in-scope shops (null otherwise), or fix `list_shops` scope. Pick one deliberately and record it.
- History endpoint: Org Admin and Superadmin only. Staff get balance only.
- Superadmin endpoints under `/api/v1/superadmin/...` with `IsSuperadmin` plus `RequiresSessionAuth`, a throttle scope, and an explicit "no tenant filter, by design" comment (CLAUDE.md §22).
- Write negative tests: cross-org Org Admin to 403/404, in-org out-of-scope Staff to 403/404, Staff to history 403, Org Admin to bonus 403, Staff in the shops list gets no out-of-scope balance.
- Run `tenant-security-auditor` on the diff (CLAUDE.md §27).

**Warning signs:** `Shop.objects.get(pk=shop_id)` in a credits view without an org or scope predicate. A serializer field `remaining_credits` on `ShopReadSerializer` with no role gate.

**Phase to address:** P-API (selector, endpoints), P-UI (badge field gating).

---

### Pitfall 11: Existing `generate_reply` plumbing swallows or mishandles the new outcomes

**What goes wrong:** Verified in `apps/reviews/views.py` and `apps/reviews/services/reply_generation.py`:
- The view ends with `except Exception` returning 502 `ai_unavailable`. An `InsufficientCreditsError` raised inside the `try` (not an `APIException`) becomes a 502, not 402. DRF has no built-in 402 exception, so it must be an explicit `Response(status=402)`.
- `ContentModeratedException` carries no stage. The v0.9 policy (refund on input block, consume on output block) cannot be implemented from the exception alone.
- `generate_reply_draft` returns only the draft string. The commit step must link `ai_usage_log_id` (AC 38) but the SUCCESS and MODERATED `AiUsageLog` rows are created inside the function and the id is not returned.
- Any reserve placed before the `try` leaks the reservation if the view raises between reserve and the service call.
- All Phase 19/20 tests that POST `generate-reply` now get 402 because orgs default to `monthly_credit_allocation = 0`.

**How to avoid:**
- Put reserve, call, commit and refund in one service (`apps/credits/services/consumption.py` driving `generate_reply_draft`) with explicit `try/except/else`, not in the view. Reserve is the LAST step after validation (tone, empty comment 400, scope).
- Add a `stage` attribute to `ContentModeratedException` (`"input"` or `"output"`). Or moderate input before reserving, which also removes ledger noise (RESERVED to REFUNDED churn).
- Return a small dataclass (`draft`, `usage_log_id`) from the reply service, or attach the id to the raised exceptions. Update the existing callers and tests.
- Map `InsufficientCreditsError` to 402 with `{code, detail, remaining, cost}` before the generic handlers.
- Update org factories and existing `generate_reply` tests in the same plan that wires credits, and update the drf-spectacular response docs (402) so `spectacular --validate` stays green.
- Rollout: allocation 0 disables a feature that has shipped since Phase 19, so a pre-deploy backfill or runbook step is required (also flagged in FEATURES.md).

**Warning signs:** A test expecting 402 that gets 502. `ContentModeratedException` caught in two places with identical behaviour.

**Phase to address:** P-CONSUME.

---

### Pitfall 12: Tests for new code never run because `config/settings/test.py` hard-codes `INSTALLED_APPS`

**What goes wrong:** `test.py` does not extend `base.INSTALLED_APPS`; it lists apps explicitly. A new `apps.credits` that is missing there produces "model not in INSTALLED_APPS" errors or, worse, an app that is silently absent from `makemigrations --check`, so CI passes while the migration is missing.

**How to avoid:** Add `apps.credits` to `base.py`, `local.py` (if it overrides), and `test.py` in the same commit as the app skeleton. Verify with `makemigrations --check` and that `django_celery_beat` is present (already in the list) for the Beat seed migration.

**Phase to address:** P-MODEL (first commit).

---

## Moderate Pitfalls

### Pitfall 13: N+1 or wrong values on the Shops list badge

**What goes wrong:** Per-row `get_current_balance(shop)` in the serializer is one query per shop (blocker-level, CLAUDE.md §6). The subtler bug: shops with no balance row yet (lazy creation) annotate to NULL, which a naive `Coalesce(..., 0)` renders as "0 credits" with the dark-grey badge for every shop that has not used AI this month.

**How to avoid:** One annotation on `list_shops`: `Subquery(ShopCreditBalance filtered by OuterRef shop and the current (year, month) -> allocated+bonus-consumed)`, with `Coalesce(subquery, F("organisation__monthly_credit_allocation"))` as the fallback for "no row yet." Annotate total (`allocated+bonus`) too so the badge colour (25% / 5%) needs no second query. Compute the period once per request and pass it in. Add a `CaptureQueriesContext` test asserting the same query count for 1 and 20 shops, plus a test for the no-row shop. Never put the balance in the 5-minute Redis cache (CLAUDE.md §7.2: write-after-read data).

**Phase to address:** P-UI (list selector and test).

### Pitfall 14: Displayed cost differs from charged cost

**What goes wrong:**
- Frontend computes cost from `comment.length`. JS counts UTF-16 units; Python `len` and Postgres `char_length` count code points. Emoji-heavy Google reviews can fall on the other side of the 100/500 boundary.
- `comment` is whitespace-only (`blank=True`): the button shows, the backend charges 1 or raises `ValueError`.
- The tier function with the spec's `(10000, 3)` ceiling falls through for longer text. It also reads settings at import time so `override_settings` does not work.
- The review is edited on Google between render and click (sync overwrites `comment`).
- Spec endpoint `cost` per review means N HTTP calls for a page of reviews and burns the 1000/hour user throttle.

**How to avoid:** One pure function `calculate_credit_cost(comment)` in `apps/credits/services/credit_cost.py`. It strips first, uses `len()` of the stripped text, treats the last tier as open-ended, and reads tiers via function call, not module constant. Expose `credit_cost` and `has_comment` in the review list serializer (comment is already loaded, no extra query). The frontend never computes cost. The generate request includes `expected_cost`; the server returns 409 `cost_changed` with the new cost on mismatch. Boundary tests: 0, 1, 100, 101, 500, 501, 4000, emoji and whitespace-only.

**Phase to address:** P-MODEL (function), P-API (serializer field, 409), P-UI.

### Pitfall 15: Client-side double charge and credits spent for a draft the user never sees

**What goes wrong:** `ReplyComposer.tsx` (`handleGenerate`, line ~80) aborts the previous request (`generateAbortRef.current?.abort()`) and starts a new one when the user clicks a second tone while one is in flight. Aborting does not cancel server work, so both reserve and commit: two charges. The unmount cleanup also aborts, so closing the composer mid-generation spends credits for a lost draft. The server may or may not finish the view after a client disconnect (verify under Daphne in a spike), so commit and refund must not depend on the response being delivered.

**How to avoid:** Disable both tone pills and close/collapse while generating (spec §5.3). Do not abort-and-restart. Keep the 10/min throttle as the backstop. An idempotency key is over-engineering here. Place finalisation (commit or refund) in `finally`-style service code and let the reaper cover hard kills.

**Phase to address:** P-UI, with the server finalisation in P-CONSUME.

### Pitfall 16: Frontend balance staleness

**What goes wrong:** Each review row holds its own "X credits remaining". After one generate, other rows, the Shop Details card, and the Shops list badge are stale. Two users on one shop see different numbers. The browser's back/forward cache re-shows an old badge. The toast says "Y remaining" from a client subtraction that drifts under concurrency.

**How to avoid:** The generate response returns `{draft, cost, remaining}` taken under the same transaction as the reserve. 402 and the refund 502 responses also carry the current `remaining`. Keep balance in one per-shop client store keyed by `shop_id`, updated from every response, and dispatch a refresh event (same CustomEvent bridge idea as `notifications:refresh`) so other widgets refetch. Send `Cache-Control: no-store` on credit endpoints. The server remains authoritative; the disabled state from stale `remaining` is a hint, and 402 must be handled gracefully. A 402 branch is needed in `api.ts` and the composer (currently handles 422/429/502).

**Phase to address:** P-UI.

### Pitfall 17: Wrong dates in "Renews on" and period labels

**What goes wrong:** Spec §13.4 says to show the reset date in the user's timezone. `new Date("2026-12-01")` is parsed as UTC midnight and displayed as Nov 30 in the Americas. The month label ("November 2026") computed in the browser can disagree with the server's UTC period near the boundary.

**How to avoid:** Server returns `period_label`, `period_year`, `period_month`, and `renews_on` (ISO date). The client renders them with `timeZone: "UTC"` and the copy "Renews Dec 1 (UTC)". Never derive the period in JS.

**Phase to address:** P-UI.

### Pitfall 18: AuditLog events invisible, over-visible, or inconsistent

**What goes wrong:** `apps/common/selectors/audit_logs.py` whitelists entity types (`AUDIT_ENTITY_FILTER`). New `shop.credits.*` rows are invisible to the Org Admin Activity Log unless added, and if added naively can reach Staff (spec: Org Admin yes, Staff no). Writing the audit row outside the state-change `atomic()` lets them diverge. `AuditLog.organisation` is non-null so lapse must set it per shop. Writing `consumed` on RESERVED instead of COMMITTED (or again on refund) produces phantom consumption events.

**How to avoid:** Write the audit in the same atomic as the ledger change. `consumed` only on commit. Add the credit entity type to the Org Admin selector only, with a Staff negative test. Put volume expectations on `consumed` in the type filter.

**Phase to address:** P-UI (selector and visibility), P-CONSUME and P-LAPSE (writes).

### Pitfall 19: History endpoint and "used" totals computed from the wrong rows

**What goes wrong:** REFUNDED rows keep their negative `credits_delta`, so summing history double-reports usage. "85 credits used" must come from `balance.consumed_credits`, not from `SUM(history)`. Unpaginated history grows forever.

**How to avoid:** Use balance columns for headline numbers. History is cursor-paginated (CLAUDE.md §8), index `(shop_id, created_at)` as the spec says, and renders REFUNDED rows visibly marked. Query-count test with a fixed ceiling.

**Phase to address:** P-API.

### Pitfall 20: Concurrency tests that are flaky, leak connections, or break teardown

**What goes wrong:** Threads that do not close their DB connections leave the test database "being accessed by other users" on teardown (Postgres). `django_db(transaction=True)` tests are slow (flush per test) and run in the default suite. Tests wrapped in pytest-django's `db` transaction never really commit, so `on_commit` callbacks and "reserve commits before OpenAI" are not exercised. No time-freezing library is in `pyproject.toml` (no freezegun or time-machine), and month-boundary tests need clock control.

**How to avoid:** `@pytest.mark.django_db(transaction=True)` plus `@pytest.mark.pg_concurrency`; in each worker `try: ... finally: connections.close_all()`; a `threading.Barrier(N)` to line threads up; a `threading.Event` held inside the mocked OpenAI call to simulate in-flight work. Keep these few and targeted: first-use race (assert one balance row and one INITIAL tx), N concurrent reserves on credits for K < N calls (assert exactly K succeed, `consumed == K x cost`), reaper versus late commit. Inject `now` or `period` into the service functions rather than adding a time-freezing dependency (pin exactly if one is added anyway). Mock OpenAI per CLAUDE.md §16. Never hit real SES, OpenAI, or LangSmith.

**Phase to address:** P-TEST.

---

## Minor Pitfalls

### Pitfall 21: Spec conflicts that will be rediscovered mid-build
Cost function location (spec §4.3 versus §13.1; PROJECT decided `apps/credits/services/credit_cost.py`), throttle (10/min stays, not the spec's 30), confirmation step (removed), "Manager" means Org Admin, spec says `cost` endpoint unthrottled but CLAUDE.md §24 forbids unthrottled endpoints (the global `UserRateThrottle` already applies; add a scope anyway). **Prevention:** record these in REQUIREMENTS acceptance criteria so executors do not re-litigate. **Phase:** requirements, before P-MODEL.

### Pitfall 22: Zero-allocation orgs
Allocation 0 means every request 402s, and the "Buy More" modal is the only path. Make sure the 402 body distinguishes "no allocation configured" from "used up" so the UI can show the right message. **Phase:** P-CONSUME and P-UI.

### Pitfall 23: Inactive or deactivated shops and disabled orgs
Decide whether lapse and the badge include inactive shops (recommended: lapse includes them for ledger completeness; the list badge hides them as the dashboard filter already does). **Phase:** P-LAPSE, P-UI.

### Pitfall 24: Beat timezone and duplicate seeds
Set `timezone="UTC"` explicitly on the `CrontabSchedule`, and run exactly one Beat instance (CLAUDE.md §12.6). **Phase:** P-LAPSE.

### Pitfall 25: Reaper volume and logging
Log each refund at WARNING with `tx_id`, `shop_id`, and age, but never review text (CLAUDE.md §22). Cap batch size per run and emit a count metric so a refund storm (an OpenAI outage) is visible. **Phase:** P-CONSUME.

### Pitfall 26: Migration safety
Adding `Organisation.monthly_credit_allocation` NOT NULL DEFAULT 0 is a fast metadata-only change on Postgres 16, but keep it a separate migration from the new app so rollback is clean (`.claude/rules/migrations.md`). Seed the Beat rows in a separate data migration with a reverse function. **Phase:** P-MODEL.

---

## Phase-Specific Warnings

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|----------------|------------|
| P-TEST | Postgres CI job, markers, time injection | SQLite hides locks (1), flaky threads (20) | Postgres job, registered marker, `connections.close_all()`, `now` injection |
| P-MODEL | Models and constraints | Missing unique/check constraints (2, 4, 8) | Unique balance, partial-unique LAPSED, CheckConstraints, PROTECT/SET_NULL |
| P-MODEL | App registration | Test settings list omits `apps.credits` (12) | Add to base/local/test together |
| P-MODEL | Allocation semantics | Mid-month change leaks into lazy rows (3) | Freeze-on-edit or previous-value columns |
| P-MODEL | Cost function | Unicode/whitespace/open tier (14) | Strip, code-point `len`, open last tier, settings read at call time |
| P-CONSUME | Reserve/commit/refund | Double refund, TOCTOU (4, 8) | Conditional UPDATE transitions; F() only |
| P-CONSUME | OpenAI timeout vs TTL | Reaper refunds in-flight call (5) | 30s timeout, 1 retry, TTL >= 2x worst case |
| P-CONSUME | View wiring | 402 swallowed into 502; moderation stage unknown (11) | Service-level orchestration, `stage` on exception, dataclass return |
| P-CONSUME | Month boundary | Refund hits wrong period (6) | Always operate via `tx.shop_credit_balance_id` |
| P-LAPSE | Lapse idempotency | Duplicate LAPSED rows; missed months (7) | Partial unique constraint, `period < current` catch-up |
| P-LAPSE | Stranded refunds | Refund after lapse (6) | Skip balances with RESERVED; reaper re-lapses |
| P-API | Scoping | Staff scope gap, Superadmin null org, history leak (10) | Single accessible-shop selector; role-gated history; negative tests |
| P-API | Bonus | Lost update, wrong month, double submit (9) | F() update, period echo with 409, ensure_balance |
| P-UI | Shops list | N+1; NULL rendered as 0 (13) | Subquery + Coalesce to org allocation; query-count test |
| P-UI | Composer | Abort-restart double charge; stale balances; 402 UX (15, 16) | Disable controls while loading; response carries `remaining`; shared store |
| P-UI | Dates and caching | Timezone off-by-one; stale bfcache (16, 17) | Server-provided labels; UTC formatting; `no-store` |
| P-UI | Audit visibility | Staff sees credit events (18) | Org Admin-only selector change plus negative test |

## Research flags for deeper phase-level research

- **P-CONSUME:** spike client-disconnect behaviour under Daphne for sync DRF views (does the view run to completion?). Confirm the late-commit policy (Pitfall 4) with the product owner. Confirm the `with_options` timeout does not break LangSmith tracing wrappers.
- **P-API:** confirm whether to fix `list_shops` Staff scoping globally (an existing behaviour change) or only gate credits fields (Pitfall 10).
- **P-LAPSE / rollout:** pre-deploy allocation backfill decision for existing orgs (FEATURES.md gap 1).
- Standard patterns, unlikely to need research: cost function, Beat seeding (copy `0016_beat_recover_stuck_syncs.py`), serializer and list annotation.

## Sources

- Repo (verified, HIGH): `config/settings/test.py` (SQLite, hard-coded INSTALLED_APPS), `.github/workflows/ci.yml` (no Postgres service), `apps/reviews/views.py` (`generate_reply`, catch-all 502), `apps/reviews/services/reply_generation.py` (return type, moderation order), `apps/integrations/openai/client.py` (default client), `apps/integrations/openai/exceptions.py` and `guardrails.py` (no stage), `apps/shops/views.py` and `selectors/shops.py` (no Staff scope on list), `apps/common/viewsets.py` (`TenantScopedViewSet` null-org behaviour), `apps/common/selectors/audit_logs.py` (entity whitelist), `apps/reviews/migrations/0016_beat_recover_stuck_syncs.py` (Beat seed pattern), `frontend/src/widgets/review-management/ReplyComposer.tsx` (abort-and-restart).
- `.venv/lib/python3.12/site-packages/openai/_constants.py`: `DEFAULT_TIMEOUT = 600s` (HIGH; installed `openai==2.33.0`).
- Django ORM semantics (HIGH): `get_or_create` savepoint behaviour, `select_for_update(of=...)`, `skip_locked`, `F()` in `CheckConstraint`, and conditional/partial `UniqueConstraint`. Postgres READ COMMITTED default behaviour on unique-index waits. No web research was needed beyond reading the code; verify the Django 6.0 docs when writing the constraints.
- Project docs: `docs/completed/Requirements_Credits_System.md` (§3, §6, §7, §10, §13), `.planning/PROJECT.md` (v0.9 decisions), CLAUDE.md §6, §9, §12.4, §22, §24; `.planning/research/FEATURES.md` (parallel research, spec gaps).
