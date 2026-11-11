# Phase 29: Credits Ledger Foundation - Research

**Researched:** 2026-11-11
**Domain:** Django 6.0.2 ledger + balance models (DB-enforced invariants), virtual-balance read selectors, Postgres-backed concurrency CI
**Confidence:** HIGH (every ORM/constraint/race claim below was executed against the pinned Django 6.0.2 on SQLite AND a real PostgreSQL in a throwaway probe outside the repo; the repo was not modified)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Already closed upstream (do not re-litigate)**
- BigAutoField PKs, not UUIDs.
- Cost is computed from `Review.comment`, trimmed (not `review.text`).
- Consumption `credits_delta` is **negative**. Headline "used" reads `balance.consumed_credits`, never `SUM(history)`.
- No backfill. Rollout is a deploy note (CQA-02, Phase 30), and orgs are enabled through CRED-06 (Phase 32).
- On lazy creation with allocation 0, write the balance row but **no** zero-amount INITIAL transaction and no audit row.

**Ledger schema & FKs**
- **D-01:** Create the **full** `CreditTransaction` schema in Phase 29, including the nullable forward columns later phases need: `review` FK, `actor` FK (user), `ai_usage_log` FK -> `openai.AiUsageLog` (direction is tx -> usage log, never the reverse), `note`. Phases 30/31 then add code only, with no ledger-table migrations.
- **D-02:** FK delete rules: `ShopCreditBalance.shop`: **PROTECT**; `CreditTransaction.shop_credit_balance`: **PROTECT**; `review`, `actor`, `ai_usage_log`: **SET_NULL**. Ledger history must never disappear. Shops are only soft-deactivated today (`Shop.is_active`). An org/shop hard-delete or data reset (deferred Phase 28) will need to handle these PROTECT FKs explicitly.
- **D-03:** Lazy-creation events are **system events**. The INITIAL_ALLOCATION ledger row and the `shop.credits.allocated` AuditLog row use `actor=None`, following the Phase 24 polarity-job convention.
- **D-04:** `note` is an optional nullable short text column (<=255) for BONUS_ALLOCATION reasons. Phase 32's bonus modal may use it.

**Append-only enforcement**
- **D-05:** App layer plus DB CHECKs, **no Postgres trigger**: `save()` on an existing row rejects any change other than `status`; `delete()` raises; a custom QuerySet blocks `update()` and `delete()`, except through the named status-transition service functions; Django admin is read-only for both models (no add/change/delete permissions); value invariants are DB `CheckConstraint`s so SQLite and Postgres behave the same.
- **D-06:** Allowed status transitions are **RESERVED -> COMMITTED** and **RESERVED -> REFUNDED** only. Only CONSUMPTION rows are created as RESERVED. INITIAL_ALLOCATION, BONUS_ALLOCATION and LAPSED rows are created COMMITTED and are final. Each transition is a CAS: `filter(pk=..., status=RESERVED).update(status=...)`, success judged by affected-row count. COMMITTED -> REFUNDED is **not** allowed.
- **D-07:** Ledger DB constraints/indexes in Phase 29: partial `UniqueConstraint(balance) WHERE type=INITIAL_ALLOCATION`; partial `UniqueConstraint(balance) WHERE type=LAPSED`; partial index on `(status, created_at) WHERE status=RESERVED`. Alongside the balance's `UniqueConstraint(shop, year, month)` and the `CHECK (consumed >= 0 AND consumed <= allocated + bonus)` / non-negative CHECKs.

**Cost function**
- **D-08:** `credit_cost(text) -> int` is pure and total. Empty/whitespace-only input (trimmed length 0) **returns 0** and does not raise. 0 means "not chargeable".
- **D-09:** Length is `len(comment.strip())` in **Python code points**, no new dependency. The UI never recomputes cost. The emoji boundary test documents that one emoji code point counts as 1.
- **D-10:** `REVIEWBEE_CREDIT_TIERS` is a list of `(max_len, cost)` tuples whose last `max_len` is `None`. Default `[(100, 1), (500, 2), (None, 3)]`. A settings test asserts ascending, ends with `None`, positive costs. Boundary tests: 0, 1, 100, 101, 500, 501, 10000, 10001, emoji, whitespace-only.

**Balance read contract**
- **D-11:** Single-shop virtual-balance selector returns a **frozen dataclass**, e.g. `CreditBalanceView(shop_id, year, month, allocated, bonus, consumed, remaining, is_enabled, is_materialized, renews_on)`. `is_enabled = (allocated + bonus) > 0`. `is_materialized` says whether a row exists. The selector never writes.
- **D-12:** A shop with no current-month row reports the **organisation's live `monthly_credit_allocation`** as allocated/remaining (CRED-05), bonus=0, consumed=0. `annotate_credit_state` uses the same `Coalesce` fallback (FilteredRelation or Subquery; both N+1-safe).
- **D-13:** Inactive shops are **computed normally**. Selectors don't filter on `is_active`.

**Postgres CI (CQA-01)**
- **D-14:** Separate `backend-pg` CI job: `services: postgres:16`, new `config.settings.test_pg`, runs `pytest -m pg_concurrency` only. Register `pg_concurrency` in `pyproject.toml` markers (`--strict-markers` is on). Marked tests auto-skip when the DB vendor isn't Postgres so the SQLite job and its 85% gate are unchanged. Add `make test-pg`. Race tests use `django_db(transaction=True)`, `threading.Barrier`, `connections.close_all()` in `finally`. Phase 29 ships the first-use race test (N concurrent first uses -> one balance row, one INITIAL row).

### Claude's Discretion
- Exact module/file names inside `apps/credits` (follow ARCHITECTURE.md: `services/periods.py`, `services/credit_cost.py`, `services/allocation.py`, `selectors/balances.py`).
- Enum storage (TextChoices) and column names, as long as the semantics above hold.
- FilteredRelation vs Subquery for `annotate_credit_state`, decided by a query-count test.
- Exactly how `ensure_balance` handles the lock: `get_or_create` in its own atomic, then INITIAL tx + audit only when `created`. Do not use `select_related` with `select_for_update`; use `of=("self",)`.

### Deferred Ideas (OUT OF SCOPE)
- A Postgres trigger enforcing ledger immutability (rejected for now).
- COMMITTED -> REFUNDED goodwill refunds.
- Handling PROTECT FKs during a future org/shop hard-delete or the deferred Phase 28 data reset.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CRED-02 | One balance per shop per UTC month, lazily created; DB enforces `(shop, year, month)` uniqueness and `0 <= consumed <= allocated + bonus` | Model/constraint block in Code Examples (verified on SQLite + PG); `ensure_balance` get_or_create pattern + 8-thread race verified on PG |
| CRED-03 | Append-only ledger; status the only mutation via named service functions; admin read-only | Append-only QuerySet/save/delete pattern verified (16 negative cases on both engines); CAS helper; admin pattern (renders under test settings) |
| CRED-04 | Cost 1/2/3 via one pure function, settings tiers, open top tier, boundary tests | `credit_cost` sketch; Unicode facts verified (code points vs ZWJ/flags/ZWSP) |
| CRED-05 | Reading a balance never creates a row; no-row shop reports org allocation | `annotate_credit_state` (FilteredRelation + Coalesce, 1 query, verified) and single-shop selector design; "never writes" test recipe |
| CQA-01 | Postgres CI job running `pg_concurrency` tests incl. first-use race | CI job YAML, `test_pg` settings, marker registration, conftest auto-skip hook + `REQUIRE_PG` guard, `make test-pg`, race test skeleton (mutation-checked) |
</phase_requirements>

## Summary

Phase 29 is a leaf-app build with no new dependencies. Everything the CONTEXT decisions ask for works exactly as designed on Django 6.0.2: `CheckConstraint(condition=...)` with `F()` arithmetic, partial `UniqueConstraint(condition=Q(...))`, and partial `Index(condition=Q(...))` all compile and are enforced on SQLite (the test suite) and Postgres (CI). I built a throwaway probe app with the proposed models and ran 16 negative constraint/append-only cases on both engines (all rejected as intended, zero escapes), a 3x repeated 8-thread first-use race on Postgres (always exactly one balance + one INITIAL + one AuditLog), a mutation check (a naive "check then insert" implementation FAILS the same race test, so the test is meaningful), and 1-query FilteredRelation/Subquery annotations. mypy `--strict` with the repo's django-stubs plugin is clean on the typed model code shown below.

The three things that will bite the planner if missed: (1) `Coalesce` over the org allocation and the balance columns raises `FieldError: Expression contains mixed types: IntegerField, PositiveIntegerField` unless the field types match or `output_field=IntegerField()` is passed (use both: `IntegerField` for `Organisation.monthly_credit_allocation` and an explicit `output_field`); (2) `QuerySet.update(consumed=F(...))` does **not** bump `auto_now` `updated_at`, so every balance `.update()` must set `updated_at` explicitly (relevant from Phase 30, but the model should be designed for it now); (3) the `pg_concurrency` auto-skip makes a misconfigured `backend-pg` job green with zero tests run, so the job must fail hard when the DB is not Postgres (`REQUIRE_PG=1` guard, verified).

**Primary recommendation:** Build in this order: (A) CI/marker/test_pg infra, (B) `Organisation.monthly_credit_allocation` migration alone, (C) `apps/credits` models + constraints + admin + settings + both `INSTALLED_APPS`, (D) `periods` + `credit_cost`, (E) `ensure_balance` + selectors + query-count tests + the `pg_concurrency` race test, (F) CLAUDE.md §3 + `orm-performance-auditor`. Use `FilteredRelation` for `annotate_credit_state` (single LEFT JOIN, verified 1 query for 5 and 25 shops).

## Project Constraints (from CLAUDE.md)

- Apps live under `apps/`; one app = one bounded context; **update the CLAUDE.md §3 app list** with `apps/credits` (phase success note).
- Services (write) / selectors (read-only, keyword-only args) split; views thin; no business logic in `save()` beyond trivial normalisation (the append-only `save()` guard is a *rejecting* guard, not logic).
- No-N+1 is blocker-level (§6): every list-backing selector/annotation needs a `CaptureQueriesContext` fixed-ceiling test (identical count for few vs many rows). Add explicit `db_index` decision for every field; `Meta.indexes` for real query shapes.
- Multi-step writes in `transaction.atomic()`; `select_for_update` with `of=("self",)`, no `select_related` (CONTEXT discretion note).
- Never log secrets/review text at INFO+; AuditLog preferred for user-visible domain events (§29.4); system events `actor=None`.
- Pin exact versions; **no new dependencies** (none are needed).
- Testing (§16): pytest + factory-boy (one factory per model in `apps/<app>/tests/factories.py`), one test file per module, >=85% coverage on services/selectors, never hit external APIs, mypy strict on non-test code (tests are `ignore_errors` per pyproject override).
- Pre-commit/CI: ruff (rules incl. `S`, `DJ`, `RUF`, `PT`), mypy strict (`uv run mypy .`), `makemigrations --check --dry-run`, `manage.py check --deploy` (both under `config.settings.test`).
- §27: run `orm-performance-auditor` on models/constraints/indexes/migrations; §24: requirements-first gate (REQ-IDs exist already) and "simplicity first / surgical changes".
- `.claude/rules/migrations.md`: reversible, descriptive names, schema separate from data migrations, explicit `db_index` decisions. `.claude/rules/selectors.md`: read-only, keyword-only, query-count test per list selector. `.claude/rules/testing-python.md`: factories, `test_<behavior>_when_<condition>` names, cross-tenant tests for scoped surfaces.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Balance/ledger invariants (uniqueness, 0 <= consumed <= allocated+bonus, once-per-balance INITIAL/LAPSED, delta-sign) | Database / Storage | API / Backend (app-layer guard) | DB constraints are the only thing that holds under races and non-ORM writes; identical on SQLite and PG |
| Append-only enforcement | API / Backend (model + QuerySet) | Database (CHECKs) | Decision D-05: no trigger; app layer rejects `update/delete/save`, admin read-only |
| Lazy balance creation (`ensure_balance`) | API / Backend (service) | Database (unique index decides the race) | `get_or_create` relies on the unique constraint to pick one winner |
| Period boundary (`current_period`) | API / Backend (service seam) | — | Single UTC seam; also the test seam |
| Cost function | API / Backend (pure service) | — | Server-authoritative; UI consumes server value only |
| Virtual balance read (single + list annotation) | API / Backend (selectors) | Database (JOIN + COALESCE) | Reads never write; fallback computed in SQL so lists are one query |
| Postgres concurrency verification | CI / Test infra | Database | SQLite hides locking; only real PG proves race-safety |
| Read-only admin | Frontend Server (Django admin) | — | Investigation surface only |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.2 [VERIFIED: pyproject.toml `django==6.0.2`; `.venv` python -c `django.__version__` = 6.0.2] | Models, constraints, `get_or_create`, `FilteredRelation`, admin | Pinned project framework |
| psycopg | 3.2.3 [VERIFIED: pyproject.toml] | PG driver for `backend-pg` job | Already pinned |
| pytest / pytest-django | 8.3.3 / 4.9.0 [VERIFIED: pyproject.toml] | `django_db(transaction=True)`, markers, `--ds` override | Already pinned |
| factory-boy | 3.3.3 [VERIFIED: pyproject.toml] | Credits factories | Project convention |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| django-unfold | >=0.92.0 [VERIFIED: pyproject.toml] | Admin base class (`unfold.admin.ModelAdmin`) | All existing admins use it; follow precedent |
| `threading` / `unittest.mock` | stdlib | Race test + clock patching | No freezegun/time-machine (not installed, not needed) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FilteredRelation | Correlated `Subquery` | Both verified 1 query; Subquery repeats a correlated subselect per annotation; FilteredRelation = one LEFT JOIN, capped to <=1 match by the unique constraint. Recommend FilteredRelation (CONTEXT lets the query-count test decide; both pass) |
| App-layer append-only | PG trigger | Rejected in CONTEXT (untestable on SQLite) |
| `PositiveIntegerField` | `IntegerField` + named CheckConstraint | Named constraint gives a readable `IntegrityError` and avoids the Coalesce mixed-type `FieldError`; recommended |

**Installation:** nothing to install. No `pyproject.toml` dependency change, no `uv.lock` change. [VERIFIED: probe built and ran with the existing `.venv`]

**Version verification:** no new packages, so no registry lookups were needed.

## Package Legitimacy Audit

No external packages are installed in this phase. Audit not applicable. **Packages removed due to [SLOP]:** none. **Packages flagged [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                        (Phase 29 surface only; Phase 30+ callers shown dashed)

  settings.REVIEWBEE_CREDIT_TIERS ──► credit_cost(text) ──► int (0 = not chargeable)       (pure)

  periods.current_period(now=None) ─► Period(year, month)  ◄── UTC seam / test seam
                │                                │
                ▼                                ▼
   allocation.ensure_balance(shop_id) ───────► selectors.balances
     │ 1 query: shop→(org_id, org.monthly_credit_allocation)     ├─ get_shop_credit_balance()  → CreditBalanceView (frozen dataclass, never writes)
     │ atomic():                                                  └─ annotate_credit_state(qs)  → Shop qs + credit_* annotations (1 LEFT JOIN + COALESCE)
     │   ShopCreditBalance.get_or_create(shop, y, m)  ◄── unique (shop,y,m) picks ONE winner
     │   if created and allocation>0:
     │      CreditTransaction(INITIAL_ALLOCATION, +alloc, COMMITTED, actor=None)  ◄── partial unique: once per balance
     │      AuditLog(shop.credits.allocated, actor=None)
     ▼
   DB: credits_shopcreditbalance ◄──PROTECT── credits_credittransaction ──SET_NULL──► review / actor / openai.AiUsageLog
        CHECKs: month 1-12, nonneg, consumed <= allocated+bonus      CHECKs: delta sign by type, only CONSUMPTION may be non-COMMITTED
        UNIQUE (shop,year,month)                                      partial UNIQUE INITIAL/LAPSED per balance; partial INDEX RESERVED (status,created_at)

   ledger.transition_status(tx_id, from→to)  (CAS; RESERVED→COMMITTED|REFUNDED only)  ◄┈┈ Phase 30 commit/refund, Phase 31 reaper
   admin: read-only (no add/change/delete)

   CI: backend-test (SQLite, 85% gate, pg tests auto-skip)   ∥   backend-pg (postgres:16, config.settings.test_pg, -m pg_concurrency, REQUIRE_PG=1)
```

### Recommended Project Structure
```
apps/credits/
├── __init__.py
├── apps.py                 # CreditsConfig(name="apps.credits", label "credits", BigAutoField)
├── models.py               # ShopCreditBalance, CreditTransaction
├── managers.py             # CreditTransactionQuerySet (repo precedent: apps/organisations/managers.py)
├── exceptions.py           # AppendOnlyViolation, InvalidStatusTransition
├── admin.py                # read-only registrations
├── services/
│   ├── __init__.py
│   ├── periods.py          # Period, current_period(), next_period_start(), renews_on
│   ├── credit_cost.py      # credit_cost(text) -> int
│   ├── allocation.py       # ensure_balance()
│   └── ledger.py           # transition_status() CAS primitive (named status-transition fn)
├── selectors/
│   ├── __init__.py
│   └── balances.py         # CreditBalanceView, get_shop_credit_balance(), annotate_credit_state()
├── migrations/0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py        # ShopCreditBalanceFactory, CreditTransactionFactory
    ├── test_models.py      # constraints (names asserted on PG; just IntegrityError on SQLite)
    ├── test_append_only.py
    ├── test_credit_cost.py
    ├── test_periods.py
    ├── test_settings.py    # tiers shape (D-10)
    ├── test_allocation.py
    ├── test_selectors.py   # never-writes + query-count + Coalesce fallback
    ├── test_admin.py
    └── test_pg_concurrency.py   # @pytest.mark.pg_concurrency
config/settings/test_pg.py
```

### Pattern 1: Models + constraints (verified on Django 6.0.2, SQLite + PG)
**What:** Integer columns as plain `IntegerField` with **named** CheckConstraints; FKs per D-02; indexes with explicit decisions.
**Example (typed; mypy-strict clean under the repo's plugin):**
```python
# apps/credits/models.py   -- Source: probe app, executed on SQLite + PostgreSQL 14.20
from typing import ClassVar, Any, NoReturn
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from apps.credits.managers import CreditTransactionQuerySet
from apps.credits.exceptions import AppendOnlyViolation

class ShopCreditBalance(models.Model):
    # db_index=False on shop/organisation FKs: the unique (shop,y,m) and (org,y,m) indexes already lead with them
    shop = models.ForeignKey("shops.Shop", on_delete=models.PROTECT, related_name="credit_balances", db_index=False)
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.PROTECT, related_name="+", db_index=False)
    period_year = models.SmallIntegerField()
    period_month = models.SmallIntegerField()
    allocated_credits = models.IntegerField()
    bonus_credits = models.IntegerField(default=0)
    consumed_credits = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["shop", "period_year", "period_month"], name="credit_balance_shop_period_uniq"),
            models.CheckConstraint(condition=Q(period_month__gte=1, period_month__lte=12), name="credit_balance_month_range"),
            models.CheckConstraint(condition=Q(allocated_credits__gte=0, bonus_credits__gte=0, consumed_credits__gte=0), name="credit_balance_nonneg"),
            models.CheckConstraint(condition=Q(consumed_credits__lte=F("allocated_credits") + F("bonus_credits")), name="credit_balance_no_overspend"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "period_year", "period_month"], name="credit_bal_org_period_idx"),
        ]

class CreditTransaction(models.Model):
    class Type(models.TextChoices):
        INITIAL_ALLOCATION = "INITIAL_ALLOCATION", "Initial allocation"
        BONUS_ALLOCATION = "BONUS_ALLOCATION", "Bonus allocation"
        CONSUMPTION = "CONSUMPTION", "Consumption"
        LAPSED = "LAPSED", "Lapsed"
    class Status(models.TextChoices):
        RESERVED = "RESERVED", "Reserved"
        COMMITTED = "COMMITTED", "Committed"
        REFUNDED = "REFUNDED", "Refunded"

    shop_credit_balance = models.ForeignKey(ShopCreditBalance, on_delete=models.PROTECT, related_name="transactions")
    shop = models.ForeignKey("shops.Shop", on_delete=models.PROTECT, related_name="+")          # denormalised; covered by (shop, created_at) idx -> db_index=False is also valid
    organisation = models.ForeignKey("organisations.Organisation", on_delete=models.PROTECT, related_name="+")
    transaction_type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMMITTED)
    credits_delta = models.IntegerField()
    review = models.ForeignKey("reviews.Review", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ai_usage_log = models.ForeignKey("openai.AiUsageLog", null=True, blank=True, on_delete=models.SET_NULL, related_name="credit_transactions")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)     # ledger has created_at only (no auto_now updated_at)

    objects: CreditTransactionQuerySet = CreditTransactionQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["shop_credit_balance"], condition=Q(transaction_type="INITIAL_ALLOCATION"), name="credit_tx_one_initial_per_balance"),
            models.UniqueConstraint(fields=["shop_credit_balance"], condition=Q(transaction_type="LAPSED"), name="credit_tx_one_lapse_per_balance"),
            models.CheckConstraint(condition=Q(transaction_type="CONSUMPTION") | Q(status="COMMITTED"), name="credit_tx_only_consumption_reserved"),
            models.CheckConstraint(
                condition=(Q(transaction_type__in=["INITIAL_ALLOCATION", "BONUS_ALLOCATION"], credits_delta__gt=0)
                           | Q(transaction_type__in=["CONSUMPTION", "LAPSED"], credits_delta__lt=0)),
                name="credit_tx_delta_sign"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["shop", "created_at"], name="credit_tx_shop_created_idx"),
            models.Index(fields=["organisation", "created_at"], name="credit_tx_org_created_idx"),
            models.Index(fields=["status", "created_at"], condition=Q(status="RESERVED"), name="credit_tx_reserved_idx"),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            update_fields = kwargs.get("update_fields")
            if update_fields is None or set(update_fields) - {"status"}:
                raise AppendOnlyViolation("CreditTransaction rows are append-only; only `status` may change")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise AppendOnlyViolation("CreditTransaction rows cannot be deleted")
```
Verified SQL (PG): `CREATE UNIQUE INDEX "credit_tx_one_initial_per_balance" ON ... ("shop_credit_balance_id") WHERE "transaction_type" = 'INITIAL_ALLOCATION'`; `CREATE INDEX "credit_tx_reserved_idx" ON ... ("status","created_at") WHERE "status" = 'RESERVED'`. [VERIFIED: `sqlmigrate` on probe]

### Pattern 2: Append-only QuerySet + CAS primitive
```python
# apps/credits/managers.py -- verified runtime + mypy strict
from typing import Any, NoReturn
from django.db import models
from apps.credits.exceptions import AppendOnlyViolation

class CreditTransactionQuerySet(models.QuerySet["CreditTransaction"]):   # string subscript works at runtime and for mypy
    def update(self, **kwargs: Any) -> NoReturn:
        raise AppendOnlyViolation("CreditTransaction.update() is blocked; use ledger.transition_status()")
    def delete(self) -> NoReturn:
        raise AppendOnlyViolation("CreditTransaction.delete() is blocked")
    def transition_status(self, *, pk: int, from_status: str, to_status: str) -> int:
        """CAS. Calls the base QuerySet.update, bypassing the override. Callers: services/ledger.py ONLY."""
        return models.QuerySet.update(self.filter(pk=pk, status=from_status), status=to_status)
```
- `bulk_update()` is also blocked (it calls `filter(pk__in=...).update(...)` on the same QuerySet class) [VERIFIED: raised `AppendOnlyViolation`].
- `bulk_create` and `create` are intentionally allowed (LAPSED bulk writes in Phase 31).
- Named service function (Phase 29 deliverable, tiny): `services/ledger.py::transition_status(*, transaction_id, from_status, to_status) -> bool` that rejects any pair other than `(RESERVED, COMMITTED)` / `(RESERVED, REFUNDED)` with `InvalidStatusTransition` (D-06), then returns `rows == 1`. Phase 30 composes it with the balance `F()` update inside one atomic.
- **SET_NULL / PROTECT cascade interplay verified:** deleting a `Review` and a `User` referenced by a ledger row nulls `review`/`actor` and the ledger row survives (Django's `Collector` uses `sql.UpdateQuery`, not `QuerySet.update`, so the guard does not interfere). `shop.delete()` raises `ProtectedError`. [VERIFIED: probe]
- Instance `save(update_fields=["status"])` is permitted by D-05 but is a check-then-act path; the CAS helper is the only *recommended* path. Both are covered by tests.

### Pattern 3: `ensure_balance` (verified: 8 threads x 3 runs on PG, always 1 balance / 1 INITIAL / 1 AuditLog)
```python
# apps/credits/services/allocation.py -- services MAY import shops/organisations models (credits never imports reviews)
from django.db import transaction
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import Period, current_period
from apps.shops.models import Shop

def ensure_balance(*, shop_id: int, period: Period | None = None) -> tuple[ShopCreditBalance, bool]:
    period = period or current_period()
    # ONE fresh read; organisation derived structurally from the shop (never a parameter, CLAUDE.md §9)
    organisation_id, allocation = Shop.objects.filter(pk=shop_id).values_list(
        "organisation_id", "organisation__monthly_credit_allocation").get()
    with transaction.atomic():
        balance, created = ShopCreditBalance.objects.get_or_create(
            shop_id=shop_id, period_year=period.year, period_month=period.month,
            defaults={"organisation_id": organisation_id, "allocated_credits": allocation},
        )
        if created and allocation > 0:
            CreditTransaction.objects.create(
                shop_credit_balance=balance, shop_id=shop_id, organisation_id=organisation_id,
                transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION,
                status=CreditTransaction.Status.COMMITTED, credits_delta=allocation, actor=None)
            AuditLog.objects.create(
                organisation_id=organisation_id, actor=None, entity_type="shop", entity_id=str(shop_id),
                action="shop.credits.allocated", before_data=None,
                after_data={"period_year": period.year, "period_month": period.month, "allocated_credits": allocation})
    return balance, created
```
Why it is race-safe [VERIFIED on PG]: Django's `get_or_create` creates inside its own savepoint; the loser blocks on the unique index until the winner's *outer* atomic (balance + INITIAL + audit) commits, gets `IntegrityError`, the savepoint rolls back, and the follow-up `get()` sees the committed row with `created=False`. The loser therefore never observes a balance without its INITIAL row. Safe to call both outside and (later, Phase 30) inside an outer atomic. No `select_for_update` is needed in Phase 29 (lock-for-spend is Phase 30; use `select_for_update(of=("self",))` then).
- A naive `filter().first()`-then-`save()` variant FAILS the identical race test with `IntegrityError ... credit_balance_shop_period_uniq` [VERIFIED mutation check], so the test genuinely detects regressions.
- `get_or_create` on a *different* second call returns `created=False` and writes nothing (sequential test).

### Pattern 4: `annotate_credit_state` (FilteredRelation; verified 1 query for 5 and 25 shops, SQLite + PG)
```python
# apps/credits/selectors/balances.py -- imports credits models/periods only (NO shops/reviews/organisations at module level)
from typing import Any
from django.db.models import (BooleanField, ExpressionWrapper, F, FilteredRelation, IntegerField, Q, QuerySet, Value)
from django.db.models.functions import Coalesce
from apps.credits.services.periods import Period, current_period

def annotate_credit_state(qs: QuerySet[Any], *, period: Period | None = None) -> QuerySet[Any]:
    """qs must be a Shop queryset (reverse relation `credit_balances`). Never writes."""
    p = period or current_period()
    i = IntegerField()
    return (
        qs.annotate(_cb=FilteredRelation(
            "credit_balances",
            condition=Q(credit_balances__period_year=p.year, credit_balances__period_month=p.month)))
        .annotate(
            credit_allocated=Coalesce(F("_cb__allocated_credits"), F("organisation__monthly_credit_allocation"), output_field=i),
            credit_bonus=Coalesce(F("_cb__bonus_credits"), Value(0), output_field=i),
            credit_consumed=Coalesce(F("_cb__consumed_credits"), Value(0), output_field=i),
            credit_materialized=ExpressionWrapper(Q(_cb__isnull=False), output_field=BooleanField()),
        )
        .annotate(credit_remaining=F("credit_allocated") + F("credit_bonus") - F("credit_consumed"))
    )
```
Verified result with rows `[materialised 5/+2/-4, other-month row only, no row]` -> `(remaining, materialised) == [(3, True), (7, False), (7, False)]` and `.filter(credit_remaining__lte=3).count() == 1` (annotation is filterable/orderable). Generated SQL: `COALESCE(_cb."allocated_credits", "organisations_organisation"."monthly_credit_allocation")` — the `organisation__` forward join is inside the same statement (no extra query, no `select_related` needed).
- Phase 29 only provides the annotation. Wiring `with_credits` into `apps/shops/selectors/shops.py::list_shops` is Phase 32/33 (today `list_shops` is `Shop.objects.filter(organisation_id=...).select_related("region")` plus filters; `shops.selectors -> credits.selectors` is the allowed import direction). [VERIFIED: apps/shops/selectors/shops.py:1-31]
- **Subquery alternative** (also verified, 1 query) is documented in `ARCHITECTURE.md`; not needed.

### Pattern 5: Single-shop virtual balance (never writes)
```python
@dataclass(frozen=True, slots=True)
class CreditBalanceView:
    shop_id: int; year: int; month: int
    allocated: int; bonus: int; consumed: int; remaining: int
    is_enabled: bool; is_materialized: bool; renews_on: date

def get_shop_credit_balance(*, shop_id: int, period: Period | None = None) -> CreditBalanceView:
    p = period or current_period()
    row = ShopCreditBalance.objects.filter(shop_id=shop_id, period_year=p.year, period_month=p.month).values(
        "allocated_credits", "bonus_credits", "consumed_credits").first()          # query 1
    if row is None:
        from apps.shops.models import Shop        # function-level: avoids a module-level credits->shops edge
        allocation = Shop.objects.filter(pk=shop_id).values_list("organisation__monthly_credit_allocation", flat=True).get()  # query 2 (live org value, D-12)
        ...
```
Max 2 queries (1 when a row exists), no writes. Tenant/Staff scoping is the caller's job (Phase 32/33); the selector takes only `shop_id` and derives the org structurally.

### Pattern 6: Period seam (stdlib only)
```python
class Period(NamedTuple):
    year: int
    month: int

def utc_now() -> datetime:               # THE patch point: patch("apps.credits.services.periods.utc_now")
    return datetime.now(UTC)

def current_period(now: datetime | None = None) -> Period:
    n = (now or utc_now()).astimezone(UTC)   # naive datetimes would raise/assume local: reject naive explicitly
    return Period(n.year, n.month)

def next_period_start(p: Period) -> datetime:
    return datetime(p.year + p.month // 12, p.month % 12 + 1, 1, tzinfo=UTC)   # Dec -> Jan next year
```
`renews_on` for the dataclass = `next_period_start(p).date()`. Never use `date.today()`/`timezone.localtime()` (server-local). Tests: Nov 30 23:59:59 UTC -> (y, 11); Dec 1 00:00:00 UTC -> (y, 12); Dec 31 -> next year Jan; a non-UTC-aware `now` (e.g. +05:30) converts correctly.

### Pattern 7: Cost function
```python
def credit_cost(text: str | None) -> int:
    length = len((text or "").strip())
    if length == 0:
        return 0
    tiers = settings.REVIEWBEE_CREDIT_TIERS            # read at CALL time so override_settings works
    for max_len, cost in tiers:
        if max_len is None or length <= max_len:
            return cost
    return tiers[-1][1]                                # total even if config is malformed (settings test guards shape)
```
Verified Python facts for the boundary tests [VERIFIED: python3 run]: `len('😀'.strip()) == 1`; a ZWJ family emoji (man+woman+girl joined by U+200D) has length 5; a flag `'🇮🇳'` has length 2; combining `'é'` has length 2 vs precomposed `'é'` 1; `U+200B `.strip()`` is **not** stripped (zero-width space is not whitespace to Python) so a ZWSP-only comment costs 1; `' 　 \n'.strip() == ''` (NBSP and ideographic space ARE stripped). Test the single-code-point emoji for the "counts as 1" documentation; document ZWJ/flag/ZWSP as known behaviours, not bugs (D-09).

### Pattern 8: Read-only admin (renders under test settings -> test through the client)
```python
@admin.register(CreditTransaction)
class CreditTransactionAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (...); list_select_related = ("shop", "organisation", "shop_credit_balance")
    raw_id_fields = (...)              # avoid select dropdown over big tables
    def has_add_permission(self, request) -> bool: return False            # same signature/type-ignore style as apps/shops/admin.py:ShopAuditLogAdmin
    def has_change_permission(self, request, obj=None) -> bool: return False
    def has_delete_permission(self, request, obj=None) -> bool: return False
```
With `has_change_permission=False` and `has_view_permission` untouched, Django serves a view-only page; `delete_selected` is hidden because it requires delete permission. A superuser admin changelist under `config.settings.test` returns 200 [VERIFIED: probe with `client.force_login(create_superuser)` against `/django-admin/organisations/organisation/`], so admin tests can use the client: changelist 200, add URL 403, POST to change URL 403, delete URL 403. Precedent: `apps/shops/admin.py::ShopAuditLogAdmin` denies add+delete; Phase 29 goes further (also denies change) per D-05.

### Pattern 9: Organisation field + migration (own migration)
```python
# apps/organisations/models.py (additions)
monthly_credit_allocation = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10000)])
class Meta:
    constraints: ClassVar[list[models.BaseConstraint]] = [
        models.CheckConstraint(condition=Q(monthly_credit_allocation__gte=0, monthly_credit_allocation__lte=10000),
                               name="org_monthly_credit_allocation_range"),
    ]
```
- Use `IntegerField` (NOT `PositiveIntegerField`): mixing with the balance `IntegerField` columns inside `Coalesce` raises `FieldError: Expression contains mixed types: IntegerField, PositiveIntegerField. You must set output_field.` [VERIFIED: hit exactly this in the probe against `Organisation.number_of_stores`, a `PositiveIntegerField`]. Also pass `output_field=IntegerField()` as shown.
- Migration name: `organisations/0003_organisation_monthly_credit_allocation.py` (AddField + AddConstraint together; current leaf is `0002_organisation_allow_custom_sync_depth`). Generate this migration FIRST, separately from `credits/0001`.
- `OrganisationAdmin` has no `fields` restriction, so the field is auto-editable in Django admin (consistent with Phase 30's "manual UAT via shell or Django admin"); admin edits write no `organisation.credits.set` audit (Phase 32). `OrganisationSerializer`s use explicit `fields` lists [VERIFIED: apps/organisations/serializers.py:23,67,92], so the field is NOT exposed or writable via the API until Phase 32 (no mass-assignment); `_UPDATABLE_FIELDS` is untouched in Phase 29 [VERIFIED: apps/organisations/services/organisations.py:19-21].
- `ADD COLUMN ... DEFAULT 0 NOT NULL` is metadata-only on PG 11+ [ASSUMED: PG behaviour from training knowledge; STACK.md says the same]. Adding the CHECK scans the (tiny) organisations table.

### Pattern 10: Postgres test infrastructure (CQA-01)

**`pyproject.toml`** (add under `[tool.pytest.ini_options]`):
```toml
markers = [
  "pg_concurrency: real-PostgreSQL concurrency tests (run in the backend-pg CI job; auto-skipped on SQLite)",
]
```
**Auto-skip + hard-fail guard** (root `/conftest.py` currently only has `pytest_configure` -> `django.setup()`; add a hook). Verified in a probe (SQLite -> skip; `REQUIRE_PG=1` on SQLite -> `pytest.exit` non-zero instead of a green all-skipped run):
```python
def pytest_collection_modifyitems(config, items):
    from django.db import connection
    if connection.vendor == "postgresql":
        return
    if os.environ.get("REQUIRE_PG"):
        pytest.exit("REQUIRE_PG is set but the test DB is not PostgreSQL", returncode=3)
    skip = pytest.mark.skip(reason="pg_concurrency requires PostgreSQL (use `make test-pg`)")
    for item in items:
        if "pg_concurrency" in item.keywords:
            item.add_marker(skip)
```
`connection.vendor` is a class attribute: no DB connection is made at collection.

**`config/settings/test_pg.py`:**
```python
from .test import *  # noqa: F403  (re-exports `env` from base)
DATABASES = {"default": env.db("DATABASE_URL", default="postgres://app:app@localhost:5432/reviewmaster")}  # noqa: F405
```
`test.py` hard-sets SQLite and re-declares `INSTALLED_APPS`; `base.py` reads `.env` with `read_env` (does not override real env vars), so CI's `DATABASE_URL` wins. `--ds` on the CLI **overrides** the `--ds=config.settings.test` baked into `addopts` [VERIFIED: `--ds=config.settings.test` on CLI flipped vendor to sqlite while the ini default was postgres; the reverse is the intended `--ds=config.settings.test_pg` usage].

**CI job** (add to `.github/workflows/ci.yml` beside `backend-test`; mirror its uv steps):
```yaml
  backend-pg:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: reviewmaster, POSTGRES_USER: app, POSTGRES_PASSWORD: app }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U app -d reviewmaster" --health-interval 5s --health-timeout 5s --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { version: "latest" }
      - run: uv python install 3.12
      - run: uv sync --frozen
      - name: Postgres concurrency tests (CQA-01)
        run: uv run pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs
        env:
          DATABASE_URL: postgres://app:app@localhost:5432/reviewmaster
          REQUIRE_PG: "1"
```
The `app` role is the image's POSTGRES_USER (superuser) so it can create `test_reviewmaster`. No `--cov` (coverage is only enabled by the CLI flag in `backend-test`; `--cov-fail-under=85` there is unaffected because pg tests live under `*/tests/*`, which `[tool.coverage.run] omit` excludes, and the service code they exercise is covered by sequential SQLite tests).

**Makefile** (add to `.PHONY` and body): `test-pg:` -> `$(COMPOSE) exec web pytest --ds=config.settings.test_pg -m pg_concurrency -x -q --no-cov`. Runs inside the `web` container where `DATABASE_URL=postgres://app:app@db:5432/reviewmaster` is already set [VERIFIED: docker-compose.yml web.environment]; the compose `db` is `postgres:16-alpine` with `POSTGRES_USER: app` (superuser). Do not run it from the host with the `.env` URL (`@db` host does not resolve).

**First-use race test skeleton** (verified pattern; mirrors D-14):
```python
@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_first_use_creates_one_balance_and_one_initial_when_n_threads_race():
    shop = ShopFactory(organisation=OrganisationFactory(monthly_credit_allocation=7))
    N = 8; barrier = threading.Barrier(N); created_flags: list[bool] = []; errors: list[str] = []
    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            _, created = ensure_balance(shop_id=shop.pk)
            created_flags.append(created)
        except Exception as exc:
            errors.append(repr(exc))
        finally:
            connections.close_all()
    threads = [threading.Thread(target=worker) for _ in range(N)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert not errors, errors
    assert created_flags.count(True) == 1 and len(created_flags) == N
    assert ShopCreditBalance.objects.filter(shop=shop).count() == 1
    assert CreditTransaction.objects.filter(transaction_type="INITIAL_ALLOCATION").count() == 1
    assert AuditLog.objects.filter(action="shop.credits.allocated").count() == 1
```
Create fixtures (factories) **before** starting threads (they commit under `transaction=True`). The `ShopFactory` default creates a Region/Org via SubFactory — pass the org explicitly so the allocation is set.

### Anti-Patterns to Avoid
- **`PositiveIntegerField` for credit columns while the org field is `IntegerField` (or vice versa)** - `Coalesce` `FieldError`; use `IntegerField` everywhere and always `output_field=IntegerField()`.
- **`bulk_create(ignore_conflicts=True)` for the balance** - cannot say who won, so it can't gate the INITIAL row (already settled upstream; stay with `get_or_create`).
- **Skipping `updated_at` on `.update()`** - `auto_now` fires only on `save()`. Every future balance `QuerySet.update(...)` must pass `updated_at=timezone.now()` explicitly (Phase 30/32 concern; note it in the Phase 29 balance docstring).
- **Redundant FK indexes** - `shop`/`organisation` FKs on the balance get an automatic single-column index in addition to the unique/composite indexes that already lead with them (visible in `sqlmigrate`: `probeapp_shopcreditbalance_shop_id_...`, `..._organisation_id_...`). Set `db_index=False` on those two FKs (CLAUDE.md §6.8 wants an explicit decision; `orm-performance-auditor` will ask).
- **Asserting constraint *names* on SQLite for unique violations** - SQLite reports `UNIQUE constraint failed: table.col` (no constraint name) while PG reports the name; CHECK failures name the constraint on both. Assert `IntegrityError` generally for unique cases; assert names only for CHECKs (or only on PG).
- **Marking every transaction test pg-only** - only genuine race tests need `pg_concurrency`; state-machine tests run deterministically on SQLite.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Exactly one winner" under concurrent first use | try/except around `create` + manual retry, Redis lock | `get_or_create` + DB unique constraint | Verified race-safe on PG; savepoint semantics handled by Django |
| Overspend protection | Python-side `if remaining >= cost` as the guard | `CheckConstraint(consumed <= allocated + bonus)` (+ Phase 30 guarded UPDATE) | DB rejects the write even if app logic has a bug (verified: `CHECK constraint failed: credit_balance_no_overspend` / PG `violates check constraint`) |
| Once-per-balance INITIAL / LAPSED | pre-check queries | Partial `UniqueConstraint(condition=...)` | Atomic under races; verified on both engines |
| Per-row balance in lists | per-row selector calls / serializer methods | `FilteredRelation` + `Coalesce` annotation | 1 query regardless of N (verified at 5 and 25 rows) |
| Time travel in tests | freezegun/time-machine dependency | `current_period(now=...)` + patchable `utc_now()` | Zero new deps |
| Status state machine | django-fsm | CAS `filter(pk, status=RESERVED).update(...)` + 2-entry allowed-transition table | 3 states, 2 edges |
| DB immutability | PG trigger | App-layer guards + CHECKs (D-05) | Locked decision |

**Key insight:** every correctness property is delegated to a database constraint or a single atomic statement; the app layer only adds guard rails and keeps SQLite and Postgres behaviour identical.

## Common Pitfalls

### Pitfall 1: Green `backend-pg` job that ran zero tests
**What goes wrong:** auto-skip on non-Postgres + a misconfigured `DATABASE_URL`/`--ds` -> all `pg_concurrency` tests skipped -> job exits 0.
**How to avoid:** `REQUIRE_PG=1` in the job env + the `pytest.exit` hook (verified); also pass `-rs` so skips are visible. Optionally add a marked `test_connection_is_postgres` that asserts `connection.vendor == "postgresql"`.
**Warning signs:** CI log shows `N skipped`.

### Pitfall 2: `transaction=True` flushes seeded data
**What goes wrong:** `django_db(transaction=True)` truncates all tables at teardown, including rows created by data migrations (existing repo note: `apps/notifications/tests/test_dispatch.py:263` — "Migration 0002 seeds gpt-4o-mini, but transaction=True tests truncate"). Beat `PeriodicTask` seeds and `AiPricing` rows vanish for later tests in the same DB.
**How to avoid:** The `backend-pg` job runs only `pg_concurrency` tests, so ordering is irrelevant there. Tests that need seeded rows (Phase 30 reply path needs `AiPricing`) must create them explicitly. pytest-django runs transactional tests after non-transactional ones in a default run, but don't rely on it.

### Pitfall 3: Leaked thread connections break teardown
**What goes wrong:** Postgres refuses to drop `test_<db>` ("being accessed by other users") if worker threads keep connections.
**How to avoid:** `connections.close_all()` in each worker's `finally` (D-14, verified: three consecutive runs tore down cleanly).

### Pitfall 4: `Coalesce` mixed-type `FieldError`
See Pattern 9 / Anti-Patterns. Caught live in the probe; add a test that runs `annotate_credit_state` against a real shop with and without a row (which would have raised).

### Pitfall 5: Read selector accidentally creates rows
**What goes wrong:** copying `ensure_balance` into the read path for "convenience".
**How to avoid:** selector tests assert `ShopCreditBalance.objects.count() == 0` after calls **and** inspect `CaptureQueriesContext` SQL for no `INSERT`/`UPDATE`/`DELETE` (Validation section).

### Pitfall 6: Ledger rows created in tests via `.objects.create(...)` then re-saved
**What goes wrong:** `CreditTransactionFactory(...)` then `tx.save()` raises `AppendOnlyViolation` (intended). Factory `_create` uses `manager.create` (adding=True) so creation works. Use `transition_status`/`save(update_fields=["status"])` in tests that need a status change; never `tx.save()` bare.

### Pitfall 7: `settings.test.py` omission
**What goes wrong:** `apps.credits` missing from `test.py` `INSTALLED_APPS` (it re-declares the list, it does not extend base) -> models "not in INSTALLED_APPS", missing from `makemigrations --check`. **How to avoid:** add to `base.py` and `test.py` in the same commit as the app skeleton; `local.py` extends base (`INSTALLED_APPS += [...]`) so needs nothing. [VERIFIED: config/settings/test.py:17-40, local.py:6]

### Pitfall 8: Org hard-delete in existing/new tests
**What goes wrong:** `PROTECT` on the balance `shop` FK means `shop.delete()` / `organisation.delete()` (CASCADE -> shops) raises `ProtectedError` for any org with a balance row. Existing code only soft-deletes; only *new* credits tests that create balances and then delete are affected. Rollback-based DB teardown doesn't call `.delete()`. [VERIFIED: ProtectedError raised in probe]

### Pitfall 9: Window-less typing of the custom QuerySet
Repo precedent types custom querysets with `# type: ignore[type-arg]` / `# type: ignore[assignment]` (apps/organisations/managers.py, models.py). The subscripted `models.QuerySet["CreditTransaction"]` form passed mypy strict with the repo plugin and avoids the `type-arg` ignore; the `objects: ... = ...as_manager()  # type: ignore[assignment]` ignore is still required. [VERIFIED: probe mypy run]

## Code Examples

See Patterns 1-10 above (all derived from executed probes). Additional items:

**Settings (config/settings/base.py):**
```python
REVIEWBEE_CREDIT_TIERS: list[tuple[int | None, int]] = [(100, 1), (500, 2), (None, 3)]
REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES = 5          # spec §12 value; Phase 30 adds the TTL >= 2x OpenAI-timeout margin test
REVIEWBEE_SUPPORT_EMAIL = env("REVIEWBEE_SUPPORT_EMAIL", default="support@reviewbee.in")   # spec §12 default
```
(`env` pattern as used by `DEFAULT_REPLY_TO` at base.py:468. [VERIFIED: grep; spec lines 399-410].)

**Settings test (D-10):**
```python
def test_credit_tiers_are_ascending_end_open_and_positive():
    tiers = settings.REVIEWBEE_CREDIT_TIERS
    assert tiers[-1][0] is None
    bounded = [m for m, _ in tiers[:-1]]
    assert bounded == sorted(set(bounded)) and all(isinstance(m, int) and m > 0 for m in bounded)
    assert all(isinstance(c, int) and c > 0 for _, c in tiers)
```

**Test-only invariant helper** (CONTEXT "Specific Ideas"): in `apps/credits/tests/helpers.py` (or `factories.py`):
```python
def assert_ledger_reconciles(balance) -> None:
    consumed = (CreditTransaction.objects.filter(shop_credit_balance=balance, transaction_type="CONSUMPTION",
                status__in=["RESERVED", "COMMITTED"]).aggregate(s=Sum(-F("credits_delta")))["s"] or 0)
    assert balance.consumed_credits == consumed
```
Phase 30 exercises it; Phase 29 can unit-test it with hand-built rows (balance consumed set via `.update(consumed_credits=...)`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `CheckConstraint(check=Q(...))` | `CheckConstraint(condition=Q(...))` | Django 6.0 removed `check=` | Repo already uses `condition=` (apps/accounts/models.py:152) |
| `bulk_create(ignore_conflicts=True)` to dedupe | `get_or_create` when you need "who won" | n/a | Required for INITIAL gating |

**Deprecated/outdated:** nothing relevant; no upgrade bundled (Django 6.1/Celery 5.7 exist but out of scope per STACK.md).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ADD COLUMN ... DEFAULT 0 NOT NULL` is metadata-only on PG 11+ (no table rewrite) | Pattern 9 | Negligible (tiny `organisations` table either way) |
| A2 | Local verification ran on PostgreSQL **14.20** (the only local build); CI uses 16. Constraint/partial-index/`get_or_create` semantics are identical on 16 | whole doc | Very low; `backend-pg` on 16 is itself the confirmation |
| A3 | `organisation`/`shop` FKs on `CreditTransaction` and `organisation` on the balance use `PROTECT` (D-02 only specifies balance.shop and tx.balance) | Pattern 1 | If user wants CASCADE on org, a later migration is needed; PROTECT matches "ledger history must never disappear". Needs user OK |
| A3b | Extra CHECKs beyond D-07: `credit_tx_delta_sign` (INITIAL/BONUS > 0, CONSUMPTION/LAPSED < 0) and `credit_tx_only_consumption_reserved` (non-CONSUMPTION rows must be COMMITTED). Derived from D-06 + the negative-delta decision | Pattern 1 | A later phase wanting a zero-delta row (e.g. zero-amount LAPSED) would violate it; Phase 31 plans to skip `remaining <= 0`. Needs user OK |
| A4 | `ensure_balance(*, shop_id, period=None)` derives the organisation from the shop (not a parameter) instead of ARCHITECTURE.md's `(shop_id, organisation_id, ...)` | Pattern 3 | Phase 30's signature expectations differ slightly; low (discretion item) |
| A5 | No `settled_at`/`resolved_at` column on the ledger (PITFALLS suggested one); status change time is recoverable from the settle-time AuditLog row. Adding a nullable column later is cheap on PG | Pattern 1 | If Phase 30/31 want it they'd add a trivial migration despite D-01's "no ledger migrations" goal |
| A6 | Selector `get_shop_credit_balance` takes only `shop_id` and function-level-imports `Shop` for the fallback allocation | Pattern 5 | If strict "no import of shops even function-level" is wanted, pass the allocation in from the caller |
| A7 | Recommending `FilteredRelation` over `Subquery` (both verified 1 query) | Pattern 4 | None functionally; CONTEXT leaves this to the query-count test |

## Open Questions

1. **Include the two extra CHECK constraints (A3b)?**
   - What we know: they follow directly from D-06/negative-delta; verified on both engines.
   - What's unclear: whether the user wants DB-level sign/status rules beyond D-07's list.
   - Recommendation: include them (defence in depth; cost is two CHECKs). Confirm in plan-check.
2. **`PROTECT` on denormalised `shop`/`organisation` FKs of `CreditTransaction` and `organisation` of the balance (A3)?**
   - Recommendation: PROTECT for all (matches D-02 intent). If CASCADE is later needed for the Phase 28 reset, handle there.
3. **Should the CAS service function ship in Phase 29 (`services/ledger.py::transition_status`)?**
   - Success criterion 2 references "named status-transition service functions", and the QuerySet guard needs a legitimate caller to be testable; Phase 30 composes commit/refund (balance `F()` update) on top. Recommendation: ship the thin, tested primitive now; do **not** ship reserve/commit/refund.
4. **Ordering of org migration vs `credits/0001`.** `makemigrations` will make `credits/0001` depend on the organisations leaf at generation time. Generate the org migration first (so the dependency is `organisations.0003`), or run `makemigrations organisations` then `credits`. Either is functionally fine.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv (`.venv`) | all tests | ✓ | Python 3.12, Django 6.0.2 | — |
| PostgreSQL service in CI | CQA-01 | ✓ (GitHub Actions `services:`) | postgres:16-alpine | — |
| Local Postgres binaries | local race-test dev | ✓ (not running by default) | 14.20 (Homebrew) | `make test-pg` against docker-compose `db` (16) |
| docker-compose `db` | `make test-pg` | ✓ (config present: `postgres:16-alpine`, user `app`) | 16 | Homebrew PG with `DATABASE_URL` override |
| Context7 / external doc MCPs | n/a | ✗ (unauthenticated in this session) | — | Not needed: all behaviour was verified by executing against the pinned Django/PG |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none blocking.

## Validation Architecture

> Nyquist validation enabled (`.planning/config.json` `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 + factory-boy 3.3.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`addopts = "--strict-markers --tb=short -q --ds=config.settings.test"`); add `markers` |
| Quick run command | `.venv/bin/pytest apps/credits -x -q --no-cov` |
| Full suite command | `.venv/bin/pytest --cov=apps --cov-fail-under=85` |
| Postgres race command | `DATABASE_URL=postgres://app:app@localhost:5432/reviewmaster REQUIRE_PG=1 .venv/bin/pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs` (or `make test-pg`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRED-02 | Second balance for same `(shop,year,month)` rejected (`IntegrityError`) | unit/DB | `pytest apps/credits/tests/test_models.py -k duplicate_period -x` | ❌ Wave 0 |
| CRED-02 | `consumed < 0`, `consumed > allocated+bonus`, month 0/13 rejected; boundary `consumed == allocated+bonus` allowed | unit/DB | `pytest apps/credits/tests/test_models.py -k "overspend or negative or month" -x` | ❌ Wave 0 |
| CRED-02 | `ensure_balance`: created once, `created=True` then `False`; seeds `allocated` from org's live value | unit | `pytest apps/credits/tests/test_allocation.py -x` | ❌ Wave 0 |
| CRED-02 | allocation 0 -> balance row, **no** INITIAL tx, **no** AuditLog; allocation>0 -> exactly 1 INITIAL (+delta, COMMITTED, actor None) + 1 `shop.credits.allocated` (actor None) | unit | `pytest apps/credits/tests/test_allocation.py -k "zero or initial" -x` | ❌ Wave 0 |
| CRED-02 / CQA-01 | N=8 concurrent first uses -> 1 balance, 1 INITIAL, 1 AuditLog, 1 `created=True`, no errors | pg_concurrency | `pytest --ds=config.settings.test_pg -m pg_concurrency apps/credits/tests/test_pg_concurrency.py` | ❌ Wave 0 |
| CRED-03 | Second INITIAL and second LAPSED per balance rejected; many CONSUMPTION rows allowed | unit/DB | `pytest apps/credits/tests/test_models.py -k "initial or lapse or consumption" -x` | ❌ Wave 0 |
| CRED-03 | delta-sign + non-CONSUMPTION-must-be-COMMITTED CHECKs | unit/DB | `pytest apps/credits/tests/test_models.py -k "delta_sign or reserved" -x` | ❌ Wave 0 |
| CRED-03 | `qs.update`, `qs.delete`, `bulk_update`, `instance.delete`, `save()` full/other fields all raise `AppendOnlyViolation`; `save(update_fields=["status"])` allowed | unit | `pytest apps/credits/tests/test_append_only.py -x` | ❌ Wave 0 |
| CRED-03 | CAS: RESERVED->COMMITTED/REFUNDED rowcount 1 once, 0 on repeat; COMMITTED->REFUNDED / REFUNDED->COMMITTED raise `InvalidStatusTransition` | unit | `pytest apps/credits/tests/test_append_only.py -k transition -x` | ❌ Wave 0 |
| CRED-03 | Deleting Review/User nulls FKs, ledger row survives; `shop.delete()` -> `ProtectedError` | unit | `pytest apps/credits/tests/test_models.py -k "set_null or protect" -x` | ❌ Wave 0 |
| CRED-03 | Admin read-only: changelist 200 for superuser; add/change POST/delete -> 403 (both models) | integration | `pytest apps/credits/tests/test_admin.py -x` | ❌ Wave 0 |
| CRED-04 | Cost boundaries 0,1,100,101,500,501,10000,10001, emoji (1 code point), whitespace-only (0, incl. NBSP/ideographic), `None` -> 0; tiers read at call time (`override_settings`) | unit | `pytest apps/credits/tests/test_credit_cost.py -x` | ❌ Wave 0 |
| CRED-04 | Tier config shape (ascending, ends `None`, positive ints) | unit | `pytest apps/credits/tests/test_settings.py -x` | ❌ Wave 0 |
| CRED-04 | Periods: month rollover, Dec->Jan, non-UTC `now` converted, injectable seam; `next_period_start` | unit | `pytest apps/credits/tests/test_periods.py -x` | ❌ Wave 0 |
| CRED-05 | `get_shop_credit_balance` no-row -> org live allocation, bonus 0, consumed 0, `is_materialized False`, `is_enabled` per allocation>0; row exists -> row values; org value change reflected live | unit | `pytest apps/credits/tests/test_selectors.py -k single -x` | ❌ Wave 0 |
| CRED-05 | **Never writes**: `ShopCreditBalance.objects.count()==0` after single + annotate calls AND no INSERT/UPDATE/DELETE in captured SQL | unit | `pytest apps/credits/tests/test_selectors.py -k never_writes -x` | ❌ Wave 0 |
| CRED-05 | `annotate_credit_state`: fixed query count (1 for 2 shops vs 1 for 20 shops; `assert_query_ceiling` fixture); untouched shop shows full org allocation not 0; other-month row ignored; inactive shop computed | unit | `pytest apps/credits/tests/test_selectors.py -k annotate -x` | ❌ Wave 0 |
| CQA-01 | Marker registered (collection with `--strict-markers` passes); auto-skip on SQLite; `REQUIRE_PG` fails hard on non-PG | infra | `pytest apps/credits -q -rs` (shows the skip) ; `REQUIRE_PG=1 pytest apps/credits -q` (must exit non-zero on SQLite) | ❌ Wave 0 |
| CQA-01 | `backend-pg` job exists, `postgres:16`, runs `-m pg_concurrency` | CI | push branch; `gh run view` on `CI / backend-pg` green with N>=1 tests passed (not skipped) | ❌ Wave 0 |
| (all) | `makemigrations --check --dry-run`, `manage.py check`, mypy strict | CI | `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py makemigrations --check --dry-run` ; `.venv/bin/mypy .` | ✅ existing gates |
| (all) | Migrations reversible | manual/CI | `manage.py migrate credits zero && migrate organisations 0002` on a scratch PG | ❌ Wave 0 (one-off check) |

Success-criteria coverage: SC1 (first-use creates one row + INITIAL + AuditLog, race) -> CRED-02 rows + pg test; SC2 (DB rejects + no update/delete path + read-only admin) -> CRED-02/03 rows; SC3 (reads never create, no-row = org allocation) -> CRED-05 rows; SC4 (cost tiers) -> CRED-04 rows; SC5 (CI job + marker) -> CQA-01 rows.

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest apps/credits -x -q --no-cov`
- **Per wave merge:** `.venv/bin/pytest apps/credits apps/organisations apps/shops -q --no-cov` + `mypy apps/credits` + `makemigrations --check --dry-run`
- **Phase gate:** full `pytest --cov=apps --cov-fail-under=85` green AND `backend-pg` CI job green (tests passed, not skipped); `orm-performance-auditor` review recorded.

### Wave 0 Gaps
- [ ] `apps/credits/` skeleton + `tests/factories.py` (`ShopCreditBalanceFactory`, `CreditTransactionFactory`; extend `OrganisationFactory` usage with explicit `monthly_credit_allocation=`; do not change its default of 0)
- [ ] `pyproject.toml` `markers`, root `conftest.py` hook, `config/settings/test_pg.py`, `ci.yml` `backend-pg`, `Makefile test-pg`
- [ ] All `apps/credits/tests/test_*.py` listed above
- [ ] Query-count tests reuse `assert_query_ceiling` from `apps/common/tests/fixtures.py` (re-export in `apps/credits/tests/conftest.py` as `apps/shops/tests/conftest.py` does)

## Security Domain

> `security_enforcement` not disabled in config -> included. Phase 29 adds no HTTP endpoints; surface is DB, admin, and internal services.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | no auth surface added |
| V3 Session Management | no | — |
| V4 Access Control | yes (limited) | Admin: `has_add/change/delete_permission = False` (read-only even for superusers); no API endpoints this phase (Staff/tenant scoping is Phase 32/33). Selectors derive organisation structurally from the shop and take no org parameter |
| V5 Input Validation | yes | DB CHECK constraints (month range, non-negative, no-overspend, delta sign, org allocation 0-10,000) + model validators; cost function is total and typed |
| V6 Cryptography | no | — |
| V7 Error/Logging | yes | No review text or PII in AuditLog `after_data` (period, allocated count only); system events `actor=None` |
| V8 Data Protection / integrity | yes | Ledger integrity: append-only guards + PROTECT FKs + partial unique indexes |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Concurrent over-spend / double allocation (TOCTOU) | Tampering | Unique + CHECK constraints (DB-enforced); `get_or_create` winner selection; verified race test on PG |
| Ledger tampering via ORM bulk ops / admin edits | Tampering / Repudiation | `update()`/`delete()`/`bulk_update()` blocked, `save()` allows `status` only, admin read-only (note: raw SQL / `_raw_delete` / `Collector` SET_NULL remain possible by design — trigger rejected in D-05) |
| Cross-tenant data via denormalised `organisation` | Information disclosure | Organisation derived from `Shop` server-side (never a parameter); Phase 32/33 add scoping at the endpoint layer |
| Mass-assignment of `monthly_credit_allocation` | Elevation of privilege | Serializers use explicit `fields` lists and `_UPDATABLE_FIELDS` whitelist untouched (verified); no API write path until Phase 32 |
| Silent test false-assurance (SQLite hides locks) | Repudiation (of correctness) | `backend-pg` job + `REQUIRE_PG` hard-fail guard |

## Sources

### Primary (HIGH confidence)
- Executed probes (SQLite in-memory + PostgreSQL 14.20 temp cluster, Django 6.0.2 from the repo `.venv`, project `config.settings.test` + a throwaway `probeapp`, outside the repo): constraint enforcement (16 negative cases x 2 engines), append-only guards, SET_NULL/PROTECT behaviour, `get_or_create` 8-thread race x3 + naive-implementation mutation check, FilteredRelation vs Subquery (1 query, 5 and 25 shops), `Coalesce` mixed-type `FieldError`, `sqlmigrate` partial-index SQL, admin render under test settings, `--ds` CLI override of `addopts`, `REQUIRE_PG` exit guard, mypy strict with `mypy_django_plugin`.
- Repo reads: `config/settings/{base,test,local}.py`, `pyproject.toml`, `.github/workflows/ci.yml`, `Makefile`, `docker-compose.yml`, `conftest.py`, `apps/common/models.py` (AuditLog), `apps/common/tests/fixtures.py`, `apps/reviews/services/reclassify.py`, `apps/reviews/tests/test_finalise.py`, `apps/organisations/{models,managers,admin,serializers,services/organisations}.py`, `apps/shops/{models,admin,selectors/shops}.py`, `apps/shops/tests/{factories,conftest}.py`, `apps/organisations/tests/factories.py`, `apps/reviews/tests/factories.py`, `apps/integrations/openai/{models,apps}.py`, `apps/common/selectors/audit_logs.py`, `apps/accounts/models.py` (existing `CheckConstraint(condition=...)`).
- `.planning/phases/29-credits-ledger-foundation/29-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` Phase 29, `.planning/research/{SUMMARY,ARCHITECTURE,STACK,PITFALLS}.md`, `docs/in-progress/Requirements_Credits_System.md` (§3, §12 config).
- Python 3.12 `str.strip()/len()` behaviour (executed).

### Secondary (MEDIUM confidence)
- none required.

### Tertiary (LOW confidence)
- PG 11+ metadata-only `ADD COLUMN DEFAULT` (training knowledge; tagged A1).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new packages; versions read from `pyproject.toml`
- Architecture / ORM patterns: HIGH - executed on both engines
- CI/test infra: HIGH for mechanics (executed locally incl. `--ds` override, hook, guard); MEDIUM for the exact GitHub Actions YAML (standard `services:` syntax, not run on GitHub)
- Pitfalls: HIGH - most reproduced live (`Coalesce` FieldError, naive-race failure)

**Research date:** 2026-11-11
**Valid until:** 2026-12-11 (stable stack; Django pinned)
