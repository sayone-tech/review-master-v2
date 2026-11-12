# Phase 29: Credits Ledger Foundation - Pattern Map

**Mapped:** 2026-11-11
**Files analyzed:** 27 new/modified
**Analogs found:** 19 / 27 (the rest are greenfield; 29-RESEARCH.md Patterns 1-10 are probe-verified and are the primary source)

Note: all analog paths below were checked as git-tracked (`git ls-files`): `apps/organisations/managers.py`, `apps/shops/admin.py`, `conftest.py`. The others sit beside these under `apps/`, `config/` and `.github/`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/credits/apps.py`, `__init__.py` | config | n/a | any existing `apps/*/apps.py` | exact |
| `apps/credits/models.py` | model | CRUD / append-only | `apps/accounts/models.py:152` (CheckConstraint `condition=`); `apps/common/models.py::AuditLog` | role-match |
| `apps/credits/managers.py` | model (QuerySet) | CRUD | `apps/organisations/managers.py` | role-match |
| `apps/credits/exceptions.py` | utility | n/a | `apps/common/exceptions.py` | role-match |
| `apps/credits/admin.py` | config | read-only | `apps/shops/admin.py::ShopAuditLogAdmin` | exact |
| `apps/credits/services/periods.py` | utility | transform | none (RESEARCH Pattern 6) | none |
| `apps/credits/services/credit_cost.py` | utility | transform | none (RESEARCH Pattern 7) | none |
| `apps/credits/services/allocation.py` | service | CRUD + audit | `apps/reviews/services/reclassify.py` (system-actor AuditLog) | role-match |
| `apps/credits/services/ledger.py` | service | CAS update | none (RESEARCH Pattern 2) | none |
| `apps/credits/selectors/balances.py` | selector | read / aggregate | `apps/reviews/services/finalise.py::_refresh_review_counts`; `apps/shops/selectors/shops.py` | role-match |
| `apps/credits/migrations/0001_initial.py` | migration | schema | generated; `.claude/rules/migrations.md` | n/a |
| `apps/organisations/models.py` + `migrations/0003_organisation_monthly_credit_allocation.py` | model/migration | schema | `0002_organisation_allow_custom_sync_depth.py` | exact |
| `apps/credits/tests/factories.py` | test | n/a | `apps/shops/tests/factories.py` | exact |
| `apps/credits/tests/conftest.py` | test | n/a | `apps/shops/tests/conftest.py` | exact |
| `apps/credits/tests/test_*.py` (models, append_only, credit_cost, periods, settings, allocation, selectors, admin) | test | n/a | `apps/shops/tests/test_models.py`, `test_selectors.py` | role-match |
| `apps/credits/tests/test_pg_concurrency.py` | test | threaded race | none | none |
| `config/settings/base.py`, `test.py` | config | n/a | existing `INSTALLED_APPS` lists | exact |
| `config/settings/test_pg.py` | config | n/a | `config/settings/test.py` | role-match |
| `pyproject.toml` (markers) | config | n/a | `[tool.pytest.ini_options]` line 152 | exact |
| `conftest.py` (root) | config | test hook | itself (currently only `pytest_configure`) | exact |
| `.github/workflows/ci.yml` (`backend-pg`) | config | CI | `backend-test` job (line 85) | exact |
| `Makefile` (`test-pg`) | config | n/a | `test:` target (line 27) | exact |
| `CLAUDE.md` §3 | docs | n/a | existing app list | exact |

## Pattern Assignments

### `apps/credits/admin.py` (read-only admin)
**Analog:** `apps/shops/admin.py` lines 1-4, 24-38
```python
from django.contrib import admin
from unfold.admin import ModelAdmin

@admin.register(ShopAuditLog)
class ShopAuditLogAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ("shop", "actor", "action", "created_at")
    raw_id_fields = ("shop", "actor")
    readonly_fields = ("shop", "actor", "action", "created_at")

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False
```
Extend it: also add `has_change_permission` returning False (D-05), and use `list_select_related`. Full sketch is in RESEARCH Pattern 8.

### `apps/credits/managers.py` (append-only QuerySet)
**Analog:** `apps/organisations/managers.py` lines 1-10 (`from __future__ import annotations`, `class XQuerySet(models.QuerySet):  # type: ignore[type-arg]`). Use RESEARCH Pattern 2 verbatim. It uses the subscripted `models.QuerySet["CreditTransaction"]`, which needs no `type-arg` ignore. The model assignment `objects = ...as_manager()  # type: ignore[assignment]` follows the same repo precedent.

### `apps/credits/models.py`
Copy the full model and constraint block from RESEARCH Pattern 1. Repo convention: `condition=` on `CheckConstraint` (`apps/accounts/models.py:152`), `ClassVar` typing on Meta lists, TextChoices enums. Per D-01/D-02/D-07 and Open Questions A3/A3b, the extra CHECKs and PROTECT on the denormalised org/shop FKs are recommended but need user confirmation at plan-check.

### `apps/credits/services/allocation.py::ensure_balance` (service, CRUD + system audit)
**Analog:** `apps/reviews/services/reclassify.py` lines 1-40 (imports, module docstring citing decisions) and 158-170 (system-actor audit):
```python
from django.db import transaction
from apps.common.models import AuditLog
...
AuditLog(
    organisation_id=tag.organisation_id,  # structural FK — never a parameter (§9)
    actor=None,  # system event (D-06)
    entity_type="canonical_tag",
    entity_id=str(tag.pk),
    action="polarity_reclassified",
    before_data={...},
    after_data={...},
)
```
Apply: `entity_type="shop"`, `entity_id=str(shop_id)`, `action="shop.credits.allocated"`, `actor=None`, `before_data=None`. Core body is RESEARCH Pattern 3: a `get_or_create` inside `transaction.atomic()`, then the INITIAL tx and the AuditLog only `if created and allocation > 0`. Keyword-only args, `logger = logging.getLogger(__name__)`.

### `apps/credits/selectors/balances.py` (selector, read-only, no N+1)
**Analog 1:** `apps/reviews/services/finalise.py::_refresh_review_counts` lines 356-377. This is the one-grouped-query, no-N+1 convention (`.values(...).annotate(...)`). Analog 2: `apps/shops/selectors/shops.py` (keyword-only, `select_related`).
Use RESEARCH Patterns 4 and 5: `FilteredRelation("credit_balances", condition=Q(...))` plus `Coalesce(..., output_field=IntegerField())`, and a frozen `@dataclass(slots=True)` view. The selector must never write, and must not import shops/reviews at module level; do the `Shop` import inside the function.

### `apps/organisations/models.py` + migration 0003
**Analog:** `apps/organisations/migrations/0002_organisation_allow_custom_sync_depth.py` (leaf; 0003 depends on it). Field is `IntegerField(default=0, validators=[Min(0), Max(10000)])` plus named `CheckConstraint` `org_monthly_credit_allocation_range`. It must be `IntegerField`, not `PositiveIntegerField`, so `Coalesce` does not raise a mixed-type `FieldError`. Generate this migration FIRST and on its own, before `credits/0001`. Do not touch `_UPDATABLE_FIELDS` (`apps/organisations/services/organisations.py:19-21`).

### Tests
**factories.py analog:** `apps/shops/tests/factories.py` lines 1-40:
```python
class ShopFactory(DjangoModelFactory):
    class Meta:
        model = Shop
    organisation = factory.SubFactory("apps.organisations.tests.factories.OrganisationFactory")
```
Use string-path SubFactory and `factory.LazyAttribute(lambda o: o.shop.organisation)` for denormalised org FKs (see `ReviewTargetFactory`).

**conftest.py analog:** `apps/shops/tests/conftest.py`. Re-export the shared fixtures:
```python
from apps.common.tests.fixtures import (  # noqa: F401
    assert_query_ceiling,
    two_orgs_two_admins,
)
```
**Query-count tests:** use the `assert_query_ceiling(ctx, max_queries=N)` fixture (`apps/common/tests/fixtures.py:40-62`) with `CaptureQueriesContext(connection)`. Compare identical counts for few vs many shops (2 vs 20). Naming: `test_<behavior>_when_<condition>`.

### `config/settings/base.py` / `test.py`
`config/settings/test.py` re-declares the entire `INSTALLED_APPS` list (starts line ~17, `"apps.common"`, `"apps.accounts"`, `"apps.organisations"`, ...). Add `"apps.credits"` in BOTH `base.py` and `test.py`; `local.py` extends base so it needs nothing. Add `REVIEWBEE_CREDIT_TIERS`, `REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES` and `REVIEWBEE_SUPPORT_EMAIL` to `base.py` (see RESEARCH "Settings").

### `config/settings/test_pg.py`
**Analog:** `config/settings/test.py` (`from .base import *`). Use RESEARCH Pattern 10: `from .test import *  # noqa: F403`, then `DATABASES = {"default": env.db("DATABASE_URL", default=...)}  # noqa: F405`.

### `pyproject.toml`, root `conftest.py`
`pyproject.toml` line 152-156 is the `[tool.pytest.ini_options]` block with `addopts = "--strict-markers --tb=short -q --ds=config.settings.test"`. Add `markers = ["pg_concurrency: ..."]` there. Root `conftest.py` currently holds only:
```python
def pytest_configure(config: object) -> None:
    django.setup()
```
Add `pytest_collection_modifyitems` (auto-skip plus the `REQUIRE_PG` `pytest.exit`) from RESEARCH Pattern 10.

### `.github/workflows/ci.yml` (`backend-pg`)
**Analog:** `backend-test` job lines 85-109 (checkout, `astral-sh/setup-uv@v3` with `version: "latest"`, `uv python install 3.12`, `uv sync --frozen`, then `uv run pytest ...`). Add a sibling job with `services: postgres: postgres:16-alpine` and the step `uv run pytest --ds=config.settings.test_pg -m pg_concurrency --no-cov -rs`, with env `DATABASE_URL` and `REQUIRE_PG: "1"`. Full YAML is in RESEARCH Pattern 10.

### `Makefile`
**Analog:** lines 1, 27-28:
```make
.PHONY: up down ... test lint ...
test:
	$(COMPOSE) exec web pytest apps/ -x -q
```
Add `test-pg` to `.PHONY` and a target: `$(COMPOSE) exec web pytest --ds=config.settings.test_pg -m pg_concurrency -x -q --no-cov`.

### `apps/credits/tests/test_pg_concurrency.py`
No analog; use RESEARCH Pattern 10's skeleton. It uses `@pytest.mark.pg_concurrency` and `@pytest.mark.django_db(transaction=True)`, a `threading.Barrier`, and `connections.close_all()` in `finally`. Create fixtures before starting the threads, and pass the org explicitly with `monthly_credit_allocation=7`.

## Shared Patterns

### System-actor audit (`actor=None`)
**Source:** `apps/reviews/services/reclassify.py:158-170`. Apply to `ensure_balance` only. Keep PII and review text out of `after_data`.

### No-N+1 / query-count proof
**Source:** `finalise.py::_refresh_review_counts` plus the `assert_query_ceiling` fixture. Apply to `annotate_credit_state` and the single-shop selector (max 2 queries).

### Services keyword-only, thin, atomic
CLAUDE.md §5/§6.11. Services use `*` keyword-only args and `transaction.atomic()` around multi-step writes. Selectors are read-only. Credits services may import shops/organisations models, but the credits models module must not.

### Model/QuerySet typing
Repo uses `# type: ignore[type-arg]` / `[assignment]` on custom querysets (`apps/organisations/managers.py`) and `# type: ignore[misc]` on Unfold `ModelAdmin`. mypy is strict on non-test code.

### Balance `.update()` must set `updated_at`
`auto_now` does not fire on `QuerySet.update`. Note this in the balance docstring (it matters from Phase 30).

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `services/periods.py` | utility | No time-seam helper exists; use RESEARCH Pattern 6 (`utc_now()` patch point, `current_period`, `next_period_start`) |
| `services/credit_cost.py` | utility | New pure function; RESEARCH Pattern 7 (read `settings.REVIEWBEE_CREDIT_TIERS` at call time) |
| `services/ledger.py` | service | No CAS status-transition precedent; RESEARCH Pattern 2 (2-entry allowed-transition table, raises `InvalidStatusTransition`, returns `rows == 1`) |
| `tests/test_pg_concurrency.py` | test | No threaded or Postgres-only tests exist yet |

## Metadata

**Analog search scope:** `apps/shops`, `apps/organisations`, `apps/reviews/services`, `apps/common/tests`, `config/settings`, `.github/workflows`, `Makefile`, `pyproject.toml`, `conftest.py`
**Pattern extraction date:** 2026-11-11
