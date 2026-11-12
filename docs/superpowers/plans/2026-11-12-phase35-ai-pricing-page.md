# Phase 35 — AI Pricing Page + Gap Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Superadmin AI Pricing page to add, schedule, view and delete `AiPricing` rows safely (append-only, no backdating), plus always-on detection of models used without a price — shown on the AI Pricing and AI Cost Explorer pages and enforced at deploy time for the configured model.

**Architecture:** Model hardening first (who/where a price came from, a DB-enforced "one open row per model" invariant, a time-aware active-price lookup). Write logic lives in `services/pricing_management.py` under row locks; reads in `selectors/pricing.py`; thin superadmin DRF views under `/api/v1/superadmin/ai-pricing/`; a Django system check guards the configured model at deploy; a new React island `ai-pricing` renders the page and a shared `MissingPricingAlert` is reused on the Cost Explorer.

**Tech Stack:** Django 6 + DRF, PostgreSQL, django-redis, drf-spectacular, pytest + factory-boy; React + TypeScript + Tailwind via Vite, vitest.

**Spec:** `docs/superpowers/specs/2026-11-12-ai-cost-and-pricing-design.md` §5 (authoritative) + `docs/in-progress/Requirements_AI_Pricing_Management.md` v1.1 (PM §n). Requirements PRICE-01..06, GAP-01..03 in `.planning/REQUIREMENTS.md`.

**Branch:** `feat/v0.10-ai-cost-pricing` (continues after Phase 34; one PR for Phases 34–36).

## Global Constraints

- Superadmin only: pages 403 for other roles (anonymous → login redirect); APIs `permission_classes = [IsAuthenticated, IsSuperadmin]`. API prefix `/api/v1/superadmin/ai-pricing/`; page route `/admin/ai-pricing/`.
- Throttles: `ScopedRateThrottle` scopes `superadmin_ai_pricing_read` = `"120/minute"`, `superadmin_ai_pricing_write` = `"30/minute"`, `superadmin_ai_pricing_refresh` = `"1/minute"`.
- **Append-only:** existing `AiPricing` rows are never edited except (a) setting `effective_to` on the row being closed, (b) resetting `effective_to` to `NULL` when its scheduled successor is deleted. Never touch `AiUsageLog`.
- **Invariant (DB-enforced):** at most one row per `model` with `effective_to IS NULL`.
- **Active price at time T** = row with `effective_from <= T < coalesce(effective_to, ∞)`.
- **Scheduled price** = row with `effective_from > now`. At most one per model.
- No backdating: `effective_from >= now - 5 seconds`.
- Prices: each of input / output / cached is `0 ≤ p ≤ 1000`, max 8 decimal places. Serialised as strings with 8 dp; displayed as `$` + 6 dp (e.g. `$0.150000`).
- `AiPricing.source` ∈ `manual` | `sync` | `seed`; `created_by` nullable FK to user.
- Audit: `AuditLog(organisation=None, actor=<user>, entity_type="ai_pricing", entity_id=str(pricing.pk), action=…, before_data, after_data)`; actions `ai_pricing.added`, `ai_pricing.deleted`. Platform-level rows (organisation `NULL`) must never appear in any tenant's activity log.
- Gap detection: models with ≥1 `AiUsageLog` row in the last `AI_PRICING_LOOKBACK_DAYS` (90) **plus** `settings.OPENAI_MODEL`, minus `AI_PRICING_KNOWN_FREE_MODELS`, that have **no price active now**. Cached in Redis key `ai_pricing:missing_models` for `AI_PRICING_MISSING_CACHE_TTL_SECONDS` (600); cache deleted on every add/delete and on manual refresh.
- Settings (env-backed in `config/settings/base.py`): `AI_PRICING_LOOKBACK_DAYS=90`, `AI_PRICING_KNOWN_FREE_MODELS=["omni-moderation-latest","text-moderation-latest","text-moderation-stable"]`, `AI_PRICING_MISSING_CACHE_TTL_SECONDS=600`.
- Every list endpoint paginated (`DefaultPageNumberPagination`), except `model-suggestions` (capped at 20) and `missing` (an object) — controller ruling.
- Every endpoint has a `CaptureQueriesContext` ceiling test independent of row count.
- Test DB is SQLite `:memory:`; tests never hit the network.

## Review Focus

1. **Two Superadmins add a price for the same model at the same moment** → exactly one succeeds; the other gets a clean 409, never two open rows. → Task 3.
2. **A cost is logged between saving a scheduled price and its start time** → it uses the *current* rate, not the scheduled one. → Task 1.
3. **Deleting a scheduled price** → the previous price is active again with no gap; deleting the current or a past price is refused. → Task 3.
4. **An Org Admin opens their Activity Log after pricing changes** → no `ai_pricing.*` rows appear. → Task 1.
5. **The configured `OPENAI_MODEL` has no price** → the missing list includes it even if no usage was logged (enrichment fails before logging), and the deploy check fails. → Tasks 2, 4.

---

## File Structure

| File | Responsibility |
|---|---|
| `apps/integrations/openai/models.py` (modify) | `AiPricing.Source`, `source`, `created_by`, partial unique constraint, time-aware `get_active` |
| `apps/integrations/openai/migrations/0005_ai_pricing_source_created_by.py` (create) | fields + backfill `seed` + constraint |
| `apps/common/models.py` + `apps/common/migrations/00NN_auditlog_nullable_org.py` | `AuditLog.organisation` nullable |
| `apps/integrations/openai/admin.py` (modify) | `AiPricing` admin read-only; read-only admin for platform audit rows |
| `apps/integrations/openai/services/__init__.py`, `services/pricing_management.py` (create) | `add_price`, `delete_scheduled_price` |
| `apps/integrations/openai/selectors/pricing.py` (create) | current/scheduled list, history, suggestions, missing models |
| `apps/integrations/openai/checks.py` (create) + `apps.py` (modify) | system check |
| `deployment/scripts/deploy.sh` (modify) | run the check after migrate |
| `apps/integrations/openai/views.py`, `serializers.py`, `api_urls.py`, `urls.py` (modify) | pricing APIs + page |
| `config/settings/base.py` (modify) | settings + throttle rates |
| `templates/ai_pricing/page.html` (create), `templates/partials/sidebar.html` (modify) | page shell, nav |
| `frontend/src/entrypoints/ai-pricing.tsx`, `frontend/src/widgets/ai-pricing/*` (create), `frontend/vite.config.ts` (modify) | React island |
| `frontend/src/widgets/ai-cost/AiCostWidget.tsx` (modify) | missing-pricing alert on Cost Explorer |
| tests under `apps/integrations/openai/tests/`, `apps/common/tests/`, `frontend/src/widgets/ai-pricing/` | tests |

---

### Task 1: Pricing model hardening + nullable audit organisation

**Files:**
- Modify: `apps/integrations/openai/models.py`, `apps/integrations/openai/admin.py`, `apps/common/models.py`
- Create: `apps/integrations/openai/migrations/0005_ai_pricing_source_created_by.py`, `apps/common/migrations/00NN_auditlog_nullable_org.py` (via `makemigrations`; hand-add the RunPython backfill)
- Test: `apps/integrations/openai/tests/test_pricing_model.py`, `apps/common/tests/test_audit_platform_rows.py`

**Interfaces:**
- Produces:
  - `class AiPricing.Source(models.TextChoices): MANUAL="manual"; SYNC="sync"; SEED="seed"`; fields `source = CharField(max_length=10, choices=Source.choices, default=Source.MANUAL, db_index=False)` and `created_by = ForeignKey(AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name="+")`.
  - `UniqueConstraint(fields=["model"], condition=Q(effective_to__isnull=True), name="ai_pricing_one_open_row_per_model")`.
  - `AiPricingQuerySet.get_active(*, model: str, at: datetime | None = None) -> AiPricing` — time-window lookup; raises `AiPricing.DoesNotExist` as today. `calculate_cost` is unchanged.
  - `AiPricingQuerySet.active_at(at: datetime) -> QuerySet` — rows active at `at` (used by selectors).
  - `AuditLog.organisation` becomes `null=True, blank=True` (still `on_delete=CASCADE`, `db_index=True`).

- [ ] **Step 1: Write the failing tests**

```python
def test_get_active_ignores_scheduled_row(db):                       # Review Focus 2
    now = timezone.now()
    cur = AiPricingFactory(model="m", effective_from=now - timedelta(days=10), effective_to=now + timedelta(days=1))
    AiPricingFactory(model="m", effective_from=now + timedelta(days=1), effective_to=None)
    assert AiPricing.objects.get_active(model="m") == cur

def test_get_active_switches_at_scheduled_start(db):
    ...  # at = start exactly → scheduled row; at = start - 1µs → current row

def test_get_active_raises_when_no_row_covers_time(db):
    ...  # only a scheduled row → DoesNotExist for now

def test_two_open_rows_for_one_model_are_rejected(db):
    AiPricingFactory(model="m", effective_from=T1, effective_to=None)
    with pytest.raises(IntegrityError):
        AiPricingFactory(model="m", effective_from=T2, effective_to=None)

def test_existing_rows_backfilled_as_seed(migrator_or_direct_call): ...
    # call the migration's backfill function on a row created with source="manual" → "seed"

def test_calculate_cost_unchanged_with_scheduled_row(db): ...  # uses current rate

def test_platform_audit_rows_never_in_tenant_activity_log(db):        # Review Focus 4
    AuditLog.objects.create(organisation=None, entity_type="ai_pricing", entity_id="1", action="ai_pricing.added")
    org_admin = OrgAdminFactory()
    assert not list_audit_logs_for_org(organisation_id=org_admin.organisation_id).filter(organisation__isnull=True)
    # and via the API: GET the activity-log endpoint as that org admin → no "ai_pricing.added" rows

def test_pricing_admin_is_read_only(admin_client_superuser): ...  # add/change/delete permissions all False
```

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_pricing_model.py apps/common/tests/test_audit_platform_rows.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** fields, constraint, `get_active(at=)`, `active_at`, `AuditLog` nullability, migrations (backfill existing `AiPricing` rows to `seed` in a `RunPython` with a no-op reverse), `AiPricingAdmin` read-only (`has_add/change/delete_permission → False`, all fields readonly), and a read-only `PlatformAuditLogAdmin` registered on a proxy model `PlatformAuditLog(AuditLog)` (in `apps/integrations/openai/models.py`, `proxy = True`) whose `get_queryset` filters `organisation__isnull=True, entity_type="ai_pricing"`. Update the `get_active` docstring.
- [ ] **Step 4: Run** — Expected: PASS. Also `uv run pytest apps/common apps/reviews/tests/test_enrichment_service.py apps/integrations/openai -q` — Expected: PASS (enrichment/cost paths unaffected).
- [ ] **Step 5: Verify migrations** on dev Postgres: `docker compose exec web python manage.py migrate` then reverse both new migrations and re-apply. Expected: clean both ways.
- [ ] **Step 6: Commit** `feat(ai-pricing): pricing source/creator, one-open-row constraint, time-aware active price`

---

### Task 2: Pricing selectors + gap detection

**Files:**
- Create: `apps/integrations/openai/selectors/pricing.py`
- Modify: `config/settings/base.py` (the three settings)
- Test: `apps/integrations/openai/tests/test_pricing_selectors.py`

**Interfaces:**
- Consumes: Task 1 (`active_at`, `get_active(at=)`).
- Produces:
  - `MISSING_CACHE_KEY = "ai_pricing:missing_models"`
  - `class MissingModel(TypedDict): model: str; last_used_at: datetime | None; configured: bool`
  - `def list_missing_pricing_models(*, now: datetime | None = None, use_cache: bool = True) -> list[MissingModel]` — ordered by `last_used_at` desc (None last); `configured=True` for `settings.OPENAI_MODEL`. ≤ 3 queries on a miss.
  - `def invalidate_missing_pricing_cache() -> None`
  - `class PriceSummaryRow(TypedDict): model: str; current: AiPricing | None; scheduled: AiPricing | None`
  - `def list_price_summary(*, now: datetime | None = None) -> list[PriceSummaryRow]` — one entry per model that has a current or scheduled row, sorted by model; 1 query (`select_related("created_by")`).
  - `def list_price_history(*, model: str) -> QuerySet[AiPricing]` — chronological ascending, `select_related("created_by")`.
  - `class ModelSuggestion(TypedDict): model: str; last_used_at: datetime | None; has_price: bool`
  - `def list_model_suggestions(*, query: str = "", limit: int = 20, now: datetime | None = None) -> list[ModelSuggestion]` — distinct models from `AiUsageLog` (lookback window) ∪ models in `AiPricing` ∪ `OPENAI_MODEL`, `icontains` filter on `query`; ordering: `has_price=False` first by `last_used_at` desc, then the rest alphabetically; capped at `limit`. ≤ 3 queries.

- [ ] **Step 1: Write the failing tests**

```python
def test_all_priced_returns_empty(db): ...
def test_logged_unpriced_model_is_listed_with_last_used(db): ...
def test_known_free_models_excluded(db, settings): ...
def test_lookback_window_boundary(db, settings): ...           # 89 days ago listed; 91 days ago not
def test_configured_model_listed_even_without_usage(db, settings):   # Review Focus 5
    settings.OPENAI_MODEL = "gpt-new"
    assert list_missing_pricing_models(use_cache=False) == [{"model": "gpt-new", "last_used_at": None, "configured": True}]
def test_model_with_only_scheduled_price_counts_as_missing(db): ...
def test_missing_result_is_cached_and_invalidated(db): ...      # 2nd call 0 queries; after invalidate, recomputed
def test_price_summary_current_and_scheduled(db): ...
def test_history_chronological(db): ...
def test_suggestions_unpriced_first_then_alpha_and_capped(db): ...
def test_pricing_selectors_fixed_query_counts(db, django_assert_max_num_queries): ...
    # 30 models × 3 rows: summary 1, history 1, suggestions ≤3, missing ≤3 (miss) / 0 (hit)
```

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_pricing_selectors.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): pricing selectors and missing-pricing detection`

---

### Task 3: Pricing management service

**Files:**
- Create: `apps/integrations/openai/services/__init__.py`, `apps/integrations/openai/services/pricing_management.py`
- Test: `apps/integrations/openai/tests/test_pricing_management.py`

**Interfaces:**
- Consumes: Task 1 model API; Task 2 `invalidate_missing_pricing_cache()`.
- Produces:
  - `class PricingError(Exception): code: str` with subclasses `BackdatedPriceError` (code `backdated`), `ScheduledPriceExistsError` (`scheduled_price_exists`), `PriceNotScheduledError` (`price_not_scheduled`), `ConcurrentPriceChangeError` (`concurrent_change`).
  - `GRACE = timedelta(seconds=5)`
  - `@transaction.atomic def add_price(*, model: str, input_token_price_per_1m: Decimal, output_token_price_per_1m: Decimal, cached_token_price_per_1m: Decimal, effective_from: datetime, actor: User | None, source: str = AiPricing.Source.MANUAL, now: datetime | None = None) -> AiPricing`
  - `@transaction.atomic def delete_scheduled_price(*, pricing_id: int, actor: User, now: datetime | None = None) -> None` (raises `AiPricing.DoesNotExist` for unknown id)
  - Both register `transaction.on_commit(invalidate_missing_pricing_cache)` (from `selectors/pricing.py`, Task 2).

`add_price` algorithm:
```
lock: rows = AiPricing.objects.select_for_update().filter(model=model, effective_to__isnull=True)
if effective_from < now - GRACE: raise BackdatedPriceError
open_row = rows.first()
if open_row and open_row.effective_from > now: raise ScheduledPriceExistsError
if open_row: open_row.effective_to = effective_from; save(update_fields=["effective_to"])
new = AiPricing.objects.create(model, prices…, effective_from, effective_to=None, source, created_by=actor)
   — wrap create in a savepoint; IntegrityError → ConcurrentPriceChangeError
AuditLog(organisation=None, actor, entity_type="ai_pricing", entity_id=str(new.pk), action="ai_pricing.added",
         before_data=_snapshot(open_row) or None, after_data=_snapshot(new))
```
`_snapshot(row)` = `{model, input_token_price_per_1m, output_token_price_per_1m, cached_token_price_per_1m (as str), effective_from, effective_to (ISO), source}`.

`delete_scheduled_price`: lock the row; if `effective_from <= now` → `PriceNotScheduledError`; find predecessor `filter(model=row.model, effective_to=row.effective_from)` (locked); delete row first, then set predecessor `effective_to=None`; audit `ai_pricing.deleted` with `before_data=_snapshot(row)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_first_price_for_model_creates_open_row_and_audit(db): ...      # source manual, created_by actor, AuditLog org None
def test_new_price_now_closes_current_at_new_start(db): ...             # old.effective_to == new.effective_from
def test_scheduled_price_keeps_current_active_until_start(db): ...       # get_active(now) is old; get_active(start) is new
def test_backdated_price_rejected(db): ...                              # now - 6s → BackdatedPriceError; now - 4s OK
def test_second_scheduled_price_rejected(db): ...                       # ScheduledPriceExistsError, nothing written
def test_delete_scheduled_reopens_previous(db):                          # Review Focus 3
    ...  # afterwards: previous.effective_to is None, get_active(now) == previous, scheduled row gone, audit row written
def test_delete_current_or_past_price_rejected(db): ...                  # PriceNotScheduledError, nothing written
def test_concurrent_open_row_maps_to_concurrent_change_error(db):        # Review Focus 1
    # simulate the race: patch AiPricing.objects.create to raise IntegrityError once → ConcurrentPriceChangeError, no partial writes
def test_add_price_invalidates_missing_cache_on_commit(db, django_capture_on_commit_callbacks): ...
def test_never_touches_usage_log(db): ...                                # AiUsageLog rows unchanged
```

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_pricing_management.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): append-only add/schedule/delete pricing service with audit`

---

### Task 4: Deploy-time guard for the configured model

**Files:**
- Create: `apps/integrations/openai/checks.py`
- Modify: `apps/integrations/openai/apps.py` (register in `ready()`), `deployment/scripts/deploy.sh` (after step 5 migrate)
- Test: `apps/integrations/openai/tests/test_checks.py`

**Interfaces:**
- Produces: `@register(Tags.database) def check_configured_model_priced(app_configs, databases, **kwargs) -> list[CheckMessage]` — only runs when `databases` is given (Django passes it for `--database`); returns `Error("OPENAI_MODEL '<m>' has no active AiPricing row.", hint="Add a price on /admin/ai-pricing/ or via Django admin before deploying.", id="openai.E001")` when `get_active(model=settings.OPENAI_MODEL)` raises; returns `[]` if the pricing table doesn't exist yet (catch `ProgrammingError`/`OperationalError`, return a `Warning` id `openai.W001`).
- deploy.sh: new step after migrations — `docker compose -f "${COMPOSE_FILE}" run --rm web python manage.py check --database default --fail-level ERROR` with a comment "5b. Guard: configured OpenAI model must have a price (openai.E001)". It runs before services restart, so a failing check aborts the deploy (`set -e`).

- [ ] **Step 1: Write the failing tests**

```python
def test_check_errors_when_configured_model_unpriced(db, settings):    # Review Focus 5
    settings.OPENAI_MODEL = "gpt-unpriced"
    errors = check_configured_model_priced(None, databases=["default"])
    assert [e.id for e in errors] == ["openai.E001"]
def test_check_passes_when_priced(db, settings): ...
def test_check_skipped_without_databases(settings): ...                # databases=None → []
def test_check_runs_via_call_command(db, settings): ...                # call_command("check", "--database", "default", "--fail-level", "ERROR") raises SystemCheckError when unpriced
```

- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** — Expected: PASS; and `uv run python manage.py check` (no `--database`) still passes locally.
- [ ] **Step 5: Commit** `feat(ai-pricing): deploy-time check that the configured model has a price`

---

### Task 5: Read APIs (summary, history, suggestions, missing, refresh)

**Files:**
- Modify: `apps/integrations/openai/views.py`, `serializers.py`, `api_urls.py`, `config/settings/base.py` (throttle rates)
- Test: `apps/integrations/openai/tests/test_ai_pricing_views.py`

**Interfaces:**
- Consumes: Task 2 selectors.
- Produces (JSON the frontend relies on; prices as 8-dp strings; datetimes via DRF representation):
  - `PriceRow = {id, model, input_token_price_per_1m, output_token_price_per_1m, cached_token_price_per_1m, effective_from, effective_to, source, created_by: {id, name} | null, status: "current" | "scheduled" | "past", can_delete: bool}` — `name` = user's full name or email.
  - `GET /api/v1/superadmin/ai-pricing/` → paginated `{count, next, previous, results: [{model, current: PriceRow | null, scheduled: PriceRow | null}]}` — name `superadmin-ai-pricing-list`.
  - `GET /api/v1/superadmin/ai-pricing/history/?model=<model>` → paginated `results: [PriceRow]` ascending; 400 if `model` missing — name `superadmin-ai-pricing-history`. *(Ruling: query param instead of the spec's `{model}/history/` path, so model ids never need path encoding.)*
  - `GET /api/v1/superadmin/ai-pricing/model-suggestions/?q=` → `{results: [{model, last_used_at, has_price}]}` (≤ 20) — name `superadmin-ai-pricing-suggestions`.
  - `GET /api/v1/superadmin/ai-pricing/missing/` → `{models: [{model, last_used_at, configured}], generated_at}` — name `superadmin-ai-pricing-missing`.
  - `POST /api/v1/superadmin/ai-pricing/missing/refresh/` → same payload, recomputed after `invalidate_missing_pricing_cache()`; throttle scope `superadmin_ai_pricing_refresh` — name `superadmin-ai-pricing-missing-refresh`.

- [ ] **Step 1: Write the failing tests** — 403 for Org Admin/Staff and 401/403 anonymous on every endpoint; shapes and values for each; history 400 without `model`; `status`/`can_delete` correct for past/current/scheduled rows; missing returns configured model; refresh recomputes (add a price via the service with cache warm, refresh → model gone); refresh throttled (second call within a minute → 429); query ceilings with 30 models (list ≤ 4, history ≤ 4, suggestions ≤ 5, missing ≤ 5) asserted equal across two data sizes.
- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_ai_pricing_views.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** views on a `_AiPricingBaseView` (same pattern as `_AiCostBaseView`), serializers, URLs, throttle rates. `@extend_schema(tags=["superadmin-ai-pricing"])` on each.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): superadmin pricing read and gap-detection endpoints`

---

### Task 6: Write APIs (add, delete scheduled)

**Files:**
- Modify: `apps/integrations/openai/views.py`, `serializers.py`, `api_urls.py`
- Test: `apps/integrations/openai/tests/test_ai_pricing_views.py`

**Interfaces:**
- Consumes: Task 3 service + errors; Task 5 `PriceRow` serializer.
- Produces:
  - `POST /api/v1/superadmin/ai-pricing/` body `{model, input_token_price_per_1m, output_token_price_per_1m, cached_token_price_per_1m, effective_from}` → 201 `PriceRow`. Input serializer `AiPriceCreateSerializer`: `model` CharField 1–100 (stripped), three `DecimalField(max_digits=12, decimal_places=8, min_value=0, max_value=1000)`, `effective_from` DateTimeField. Errors: 400 field errors; `PricingError` → `{"code": e.code, "detail": str(e)}` with 400 for `backdated`, 409 for `scheduled_price_exists` and `concurrent_change`. Throttle scope `superadmin_ai_pricing_write`. Name same as list (`superadmin-ai-pricing-list`, POST).
  - `DELETE /api/v1/superadmin/ai-pricing/<int:pk>/` → 204; 404 unknown; 409 `price_not_scheduled` — name `superadmin-ai-pricing-detail`.
  - Views stay thin: validate → service → serialize.

- [ ] **Step 1: Write the failing tests** — 403 tenants/anon; 201 + audit row (`organisation_id is None`, actor = superadmin); 400 for each validation bound (-0.00000001, 1000.00000001, 9 dp, empty model, 101-char model); 400 `backdated`; 409 `scheduled_price_exists`; delete scheduled → 204 and previous reopened; delete current → 409; delete unknown → 404; write throttle scope set; query ceilings (POST ≤ 8, DELETE ≤ 8).
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** `uv run pytest apps/integrations/openai -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): superadmin add and delete-scheduled pricing endpoints`

---

### Task 7: Page shell + React pricing table and history

**Files:**
- Create: `templates/ai_pricing/page.html`, `frontend/src/entrypoints/ai-pricing.tsx`, `frontend/src/widgets/ai-pricing/{types.ts, api.ts, format.ts, AiPricingWidget.tsx, PricesTable.tsx, HistoryRows.tsx}` + tests
- Modify: `apps/integrations/openai/views.py` (`ai_pricing_page`), `apps/integrations/openai/urls.py` (`admin/ai-pricing/`, name `ai_pricing_page`), `templates/partials/sidebar.html` (superadmin branch, after "AI Cost": `{% include "partials/_nav_item.html" with href="/admin/ai-pricing/" icon="receipt" label="AI Pricing" %}`), `frontend/vite.config.ts`
- Test: page tests in `test_ai_pricing_views.py`; `frontend/src/widgets/ai-pricing/*.test.tsx`

**Interfaces:**
- Consumes: Task 5/6 JSON contracts.
- Produces: `AiPricingWidget()`; `formatPrice(v: string): string` → `"$0.150000"`; `formatDate(iso): string` → `"YYYY-MM-DD"` (UTC); `api.ts` exports `fetchPriceSummary(page)`, `fetchHistory(model)`, `deleteScheduledPrice(id)` (sends `X-CSRFToken` from the `csrftoken` cookie, `credentials: "same-origin"`), `ApiError`.

Copy (exact, PM §3–4): header "AI Pricing", subtitle "Current and historical token rates for OpenAI models"; button "Add New Price" (primary yellow; opens the Task 8 modal — render a disabled placeholder until Task 8); table columns "Model" (bold, below it "Active since {YYYY-MM-DD}"), "Input (per 1M tokens)", "Output (per 1M tokens)", "Cached Input (per 1M)", "Effective From", "Actions"; a scheduled price shows under the model as "Scheduled: {input}/{output}/{cached} from {YYYY-MM-DD HH:MM UTC}"; row actions menu "Add new price for this model" · "View history"; empty state "No pricing configured. Add pricing for at least one model to enable cost tracking." with an "Add New Price" CTA; history (expand per model) lists every row chronologically with a "Current" pill on `status="current"`, "Scheduled" pill on scheduled rows, source label ("Manual" / "LiteLLM sync" / "Seed") and who set it; delete button enabled only when `can_delete`, otherwise disabled with tooltip "This pricing is in effect or has been in effect — can't delete."; delete asks for confirmation using the existing `frontend/src/widgets/modal/ConfirmModal`.

- [ ] **Step 1: Write the failing tests** — Python: page 200 superadmin, 403 org admin/staff, 302 anonymous, sidebar link only for superadmin. Vitest: `formatPrice("0.15000000") === "$0.150000"`; PricesTable renders columns, "Active since", scheduled line, empty state; HistoryRows shows pills and source labels, delete disabled with the tooltip text for non-deletable rows, confirm → calls `deleteScheduledPrice(id)`.
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** pytest + `cd frontend && npx vitest run src/widgets/ai-pricing && npm run build` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): AI Pricing page with current prices and history`

---

### Task 8: Add-price modal, model autocomplete, missing-pricing alerts

**Files:**
- Create: `frontend/src/widgets/ai-pricing/{AddPriceModal.tsx, ModelAutocomplete.tsx, MissingPricingAlert.tsx}` + tests
- Modify: `frontend/src/widgets/ai-pricing/AiPricingWidget.tsx`, `api.ts` (`createPrice`, `fetchMissing`, `refreshMissing`, `fetchSuggestions`), `frontend/src/widgets/ai-cost/AiCostWidget.tsx` (platform view: render `MissingPricingAlert variant="cost-explorer"` above the KPI row)

**Interfaces:**
- Consumes: Task 5/6 contracts; Task 7 widget/api.
- Produces: `MissingPricingAlert({ variant: "pricing" | "cost-explorer", onAddFor?: (model: string) => void })` — fetches `/missing/` itself; renders nothing when the list is empty.

Copy (exact, PM §5, §7.3–7.5):
- Modal title "Add New Price"; fields "Model", "Input price (USD per 1M tokens)", "Output price (USD per 1M tokens)", "Cached input price (USD per 1M tokens)", "Effective from"; buttons "Cancel" and "Save" (primary yellow). Client-side checks mirror the server (0–1000, ≤ 8 dp, required, not in the past). Before saving show the exact timestamp: "This price will apply from {YYYY-MM-DD HH:MM:SS} UTC." `effective_from` defaults to now; the picker is local time, converted to UTC ISO on submit. Server 400/409 `detail` shown inline at the top of the modal.
- Autocomplete: suggestions from `/model-suggestions/?q=` (debounced 200 ms); unpriced entries first with a red "⚠ No pricing" label on the right; free text accepted.
- Pricing-page alert (amber, warning icon): "⚠ **{N} models are logged without pricing.** These calls show $0 in cost totals until pricing is added." (singular "1 model is logged…"), then "Missing: `m1`, `m2`", then one button per model "Add pricing for {model} →" that opens the modal pre-filled (`onAddFor`). A configured model is labelled "(configured model)". A secondary action "Refresh missing-pricing check" calls `refreshMissing()`; on 429 show "Please wait a minute before refreshing again."
- Cost Explorer alert: same heading and "Missing:" line; single link "Go to AI Pricing →" to `/admin/ai-pricing/`.
- After a successful save or delete: refetch the table, the history (if open) and the alert.

- [ ] **Step 1: Write the failing tests** — AddPriceModal: validation messages for each bound, timestamp confirmation line, submits converted UTC ISO, shows server 409 detail; ModelAutocomplete: unpriced first with "⚠ No pricing", free text submit; MissingPricingAlert: hidden when empty, singular/plural heading, buttons call `onAddFor(model)`, cost-explorer variant renders the link and no add buttons, 429 message on refresh.
- [ ] **Step 2: Run** — Expected: FAIL. **Step 3: Implement.** **Step 4: Run** `cd frontend && npx vitest run && npm run build` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ai-pricing): add-price modal, model autocomplete and missing-pricing alerts`

---

### Task 9: Phase close-out

**Files:**
- Modify: `.planning/ROADMAP.md` (tick Phase 35), `CLAUDE.md` §3 tree (`services/pricing_management.py`, `selectors/pricing.py`, `checks.py` under `apps/integrations/openai/`), `CLAUDE.md` §14.4 (pricing rows are managed on `/admin/ai-pricing/`; Django admin is read-only)

- [ ] **Step 1:** Run `code-reviewer`, `orm-performance-auditor`, `tenant-security-auditor` (controller dispatches) on the Phase 35 diff; apply accepted findings.
- [ ] **Step 2:** `uv run pre-commit run --all-files`, full `uv run pytest`, `uv run python manage.py makemigrations --check --dry-run`, `cd frontend && npx vitest run && npm run build` — all pass.
- [ ] **Step 3:** Commit `docs(ai-pricing): close out phase 35`.
