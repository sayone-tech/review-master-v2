# Phase 34 — AI Cost Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Superadmin-only AI Cost Explorer page showing OpenAI spend by organisation → shop, by request type and by model, filtered by date range.

**Architecture:** Read-only aggregations over `AiUsageLog` live in selectors in `apps/integrations/openai/`; thin DRF `APIView`s under `/api/v1/superadmin/ai-cost/` cache whole responses in Redis for 10 min; two Django page routes render one template that mounts a React island (`ai-cost-explorer` Vite entrypoint), which switches between the platform view and the org drill-down client-side with filter state in the URL query string.

**Tech Stack:** Django 6 + DRF, PostgreSQL, django-redis, drf-spectacular, pytest + factory-boy; React + TypeScript + Tailwind via Vite, vitest.

**Spec:** `docs/superpowers/specs/2026-11-12-ai-cost-and-pricing-design.md` (authoritative) + `docs/in-progress/Requirements_AI_Cost_Explorer.md` (CE §n). Requirements COST-01..07 in `.planning/REQUIREMENTS.md`.

**Branch:** `feat/v0.10-ai-cost-explorer`, cut from `docs/v0.10-ai-cost-pricing`.

## Global Constraints

- Superadmin only: pages return **403** for any other role; APIs use `permission_classes = [IsAuthenticated, IsSuperadmin]` (`apps/accounts/permissions.py`).
- API prefix `/api/v1/superadmin/ai-cost/`; page routes `/admin/ai-cost/` and `/admin/ai-cost/organisations/<org_id>/`.
- Cost and token totals sum **`status = SUCCESS` rows only**. Call counts include **all** statuses (`SUCCESS`, `FAILED`, `MODERATED`).
- Null `prompt_tokens` / `completion_tokens` sum as 0; no `null` numbers in any response.
- Date windows are UTC, start-inclusive / end-exclusive. Range keys: `this_month` (default), `last_month`, `7d`, `30d`, `90d`, `custom` (+ `from`, `to` as `YYYY-MM-DD`). Custom: `from > to` → 400; span > 365 days → 400.
- Orgs and shops with zero calls in the window are excluded.
- Org list and shop list paginated with `DefaultPageNumberPagination` (`page_size` 10/25/50/100, default 25).
- Every endpoint throttled with `ScopedRateThrottle`, scope `superadmin_ai_cost_read` = `"120/minute"`.
- Every endpoint has a `CaptureQueriesContext` ceiling test using the `assert_query_ceiling` fixture; ceilings do not grow with row count.
- Cache: Redis, TTL **600 s**, key `admin:ai_cost:{endpoint}:{hash}`; responses carry `generated_at` (ISO UTC).
- Display: cost `$X.XX` with thousands separators; tokens abbreviated `12.4M` / `342K` with the full number in a `title` tooltip; call counts with thousands separators, never abbreviated.
- Page footer copy (exact): "Estimated based on configured pricing — actual OpenAI invoice is authoritative."
- Never write to `AiUsageLog` or `AiPricing` in this phase.

## Review Focus

1. **Org whose calls in the window all FAILED** — listed (calls > 0) with $0.00 cost and 0 tokens; the average-tokens-per-call footers show 0, not an error or NaN. → Task 2.
2. **A row at exactly 00:00:00 UTC on the 1st** — belongs to `this_month`, not `last_month`. → Task 1.
3. **Rows with `prompt_tokens = NULL`** (moderated/failed) — totals stay integers, never `null`. → Task 2.
4. **Drill-down for a nonexistent org id** → 404; an existing org with no calls in the window → 200 with zeroed KPIs and empty lists (the empty state). → Task 5.
5. **Usage row whose review was deleted (`review_id IS NULL`)** — counted in the org total and in the shops table's "Unattributed" row, never dropped. → Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `apps/integrations/openai/cost_window.py` (create) | Parse range params → `CostWindow` |
| `apps/integrations/openai/selectors/__init__.py` (create) | package |
| `apps/integrations/openai/selectors/ai_cost.py` (create) | All aggregations |
| `apps/integrations/openai/migrations/00NN_ai_usage_cost_indexes.py` (create) | Two composite indexes |
| `apps/integrations/openai/serializers.py` (create) | Response serializers (schema + shaping) |
| `apps/integrations/openai/views.py` (create) | API views + page view |
| `apps/integrations/openai/api_urls.py` (create) | API routes |
| `apps/integrations/openai/urls.py` (create) | Page routes |
| `config/urls.py` (modify) | include both |
| `config/settings/base.py` (modify ~L438) | throttle rate |
| `templates/ai_cost/explorer.html` (create) | Page shell |
| `templates/partials/sidebar.html` (modify L27–31) | "AI Cost" nav item |
| `frontend/vite.config.ts` (modify input map) | `ai-cost-explorer` entry |
| `frontend/src/entrypoints/ai-cost-explorer.tsx` (create) | Mount |
| `frontend/src/widgets/ai-cost/*` (create) | Widget, API client, formatting |
| `apps/integrations/openai/tests/test_cost_window.py`, `test_ai_cost_selectors.py`, `test_ai_cost_views.py` (create) | Tests |

---

### Task 1: Date-window parsing

**Files:**
- Create: `apps/integrations/openai/cost_window.py`
- Test: `apps/integrations/openai/tests/test_cost_window.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class CostWindow: range_key: str; start: datetime; end: datetime` with `def cache_hash(self) -> str` (stable sha1 of `range_key|start.isoformat()|end.isoformat()`; for non-custom ranges round `end` down to the minute so the cache can hit).
  - `def resolve_cost_window(*, params: Mapping[str, str], now: datetime | None = None) -> CostWindow` — raises `rest_framework.exceptions.ValidationError({"detail": ...})` on bad input.

- [ ] **Step 1: Write the failing tests**

```python
NOW = datetime(2026, 11, 12, 15, 30, tzinfo=UTC)

def test_default_is_this_month():
    w = resolve_cost_window(params={}, now=NOW)
    assert (w.range_key, w.start, w.end) == ("this_month", datetime(2026, 11, 1, tzinfo=UTC), NOW)

def test_last_month_is_full_previous_calendar_month():
    w = resolve_cost_window(params={"range": "last_month"}, now=NOW)
    assert (w.start, w.end) == (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC))

def test_last_month_in_january_wraps_year():
    w = resolve_cost_window(params={"range": "last_month"}, now=datetime(2027, 1, 5, tzinfo=UTC))
    assert w.start == datetime(2026, 12, 1, tzinfo=UTC)

@pytest.mark.parametrize(("key", "days"), [("7d", 7), ("30d", 30), ("90d", 90)])
def test_rolling_ranges_anchor_to_utc_midnight(key, days):
    w = resolve_cost_window(params={"range": key}, now=NOW)
    assert w.start == datetime(2026, 11, 12, tzinfo=UTC) - timedelta(days=days - 1)
    assert w.end == NOW

def test_custom_range_is_inclusive_of_to_date():
    w = resolve_cost_window(params={"range": "custom", "from": "2026-10-01", "to": "2026-10-31"}, now=NOW)
    assert (w.start, w.end) == (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC))

def test_midnight_on_first_belongs_to_this_month():  # Review Focus 2
    this_m = resolve_cost_window(params={}, now=NOW)
    last_m = resolve_cost_window(params={"range": "last_month"}, now=NOW)
    t = datetime(2026, 11, 1, tzinfo=UTC)
    assert this_m.start <= t < this_m.end
    assert not (last_m.start <= t < last_m.end)

@pytest.mark.parametrize("params", [
    {"range": "custom", "from": "2026-10-31", "to": "2026-10-01"},   # from > to
    {"range": "custom", "from": "2025-01-01", "to": "2026-01-01"},   # 366 days
    {"range": "custom", "from": "2026-10-01"},                       # missing to
    {"range": "custom", "from": "bad", "to": "2026-10-01"},
    {"range": "yesterday"},
])
def test_invalid_params_raise(params):
    with pytest.raises(ValidationError):
        resolve_cost_window(params=params, now=NOW)

def test_365_day_custom_range_is_allowed():
    resolve_cost_window(params={"range": "custom", "from": "2025-01-01", "to": "2025-12-31"}, now=NOW)
```

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_cost_window.py -v` — Expected: FAIL (ImportError).
- [ ] **Step 3: Implement `CostWindow` and `resolve_cost_window` in `apps/integrations/openai/cost_window.py`.** Span check: `(to - from).days + 1 > 365` → error.
- [ ] **Step 4: Run** the same command — Expected: all PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(ai-cost): date-window parsing for cost explorer"`

---

### Task 2: Summary and organisation-list selectors (+ indexes)

**Files:**
- Create: `apps/integrations/openai/selectors/__init__.py`, `apps/integrations/openai/selectors/ai_cost.py`
- Create: `apps/integrations/openai/migrations/00NN_ai_usage_cost_indexes.py` (via `makemigrations`)
- Modify: `apps/integrations/openai/models.py` (`AiUsageLog.Meta.indexes`)
- Test: `apps/integrations/openai/tests/test_ai_cost_selectors.py`

**Interfaces:**
- Consumes: `CostWindow` (Task 1).
- Produces:
  - `class CostTotals(TypedDict): calls: int; success_calls: int; failed_calls: int; moderated_calls: int; input_tokens: int; output_tokens: int; cost: Decimal`
  - `def get_cost_summary(*, window: CostWindow, organisation_id: int | None = None) -> CostTotals & {"org_count": int, "active_shops": int}` (declare as `class CostSummary(CostTotals)` with those two extra keys). Exactly 1 query.
  - `ORG_SORT_FIELDS: dict[str, str]` mapping API sort keys `name, active_shops, calls, input_tokens, output_tokens, cost` to annotation names; `def list_org_costs(*, window: CostWindow, sort: str = "-cost") -> QuerySet` — `values()` rows with keys `organisation_id, name, org_type, active_shops, calls, input_tokens, output_tokens, cost`; unknown sort raises `ValidationError`. Tie-break ordering by `organisation_id`.
  - `def get_request_type_costs(*, window: CostWindow, organisation_ids: Sequence[int]) -> dict[int, dict[str, Decimal]]` — one query, `GROUP BY organisation_id, request_type`, SUCCESS only.

Aggregation shape (one grouped query, all `Sum`s wrapped in `Coalesce(..., 0)`):

```python
SUCCESS = Q(status=AiUsageLog.Status.SUCCESS)
calls=Count("id"), success_calls=Count("id", filter=SUCCESS), ...
input_tokens=Coalesce(Sum("prompt_tokens", filter=SUCCESS), 0)
cost=Coalesce(Sum("estimated_cost_usd", filter=SUCCESS), Decimal("0"))
active_shops=Count("review__shop_id", filter=SUCCESS, distinct=True)
```

- [ ] **Step 1: Write the failing tests** (use `AiUsageLogFactory`, `ReviewFactory`, `ShopFactory`, `OrganisationFactory`; window = `resolve_cost_window(params={}, now=NOW)`; create rows with `created_at` inside the window)

```python
def test_summary_counts_all_statuses_but_costs_success_only(db):
    org = OrganisationFactory()
    AiUsageLogFactory(organisation=org, estimated_cost_usd=Decimal("1.00"), prompt_tokens=100, completion_tokens=10, created_at=IN)
    AiUsageLogFactory(organisation=org, status="FAILED", estimated_cost_usd=Decimal("0"), prompt_tokens=None, completion_tokens=None, created_at=IN)
    AiUsageLogFactory(organisation=org, status="MODERATED", estimated_cost_usd=Decimal("0.50"), prompt_tokens=50, completion_tokens=5, created_at=IN)
    s = get_cost_summary(window=W)
    assert (s["calls"], s["success_calls"], s["failed_calls"], s["moderated_calls"]) == (3, 1, 1, 1)
    assert s["cost"] == Decimal("1.00")
    assert (s["input_tokens"], s["output_tokens"]) == (100, 10)
    assert s["org_count"] == 1

def test_summary_excludes_rows_outside_window(db): ...   # one row at W.start - 1s, one at W.end → both excluded

def test_null_tokens_sum_to_zero_not_none(db):  # Review Focus 3
    AiUsageLogFactory(status="FAILED", prompt_tokens=None, completion_tokens=None, created_at=IN)
    s = get_cost_summary(window=W)
    assert s["input_tokens"] == 0 and s["output_tokens"] == 0 and s["cost"] == Decimal("0")

def test_empty_window_returns_zeros(db):
    assert get_cost_summary(window=W) == {"calls": 0, "success_calls": 0, "failed_calls": 0, "moderated_calls": 0,
        "input_tokens": 0, "output_tokens": 0, "cost": Decimal("0"), "org_count": 0, "active_shops": 0}

def test_org_scoped_summary_ignores_other_orgs(db): ...

def test_org_list_excludes_inactive_orgs_and_sorts_by_cost_desc(db):
    # org_a cost 2.00, org_b cost 5.00, org_c only rows outside window
    rows = list(list_org_costs(window=W))
    assert [r["organisation_id"] for r in rows] == [org_b.id, org_a.id]

def test_org_with_only_failed_calls_is_listed_with_zero_cost(db):  # Review Focus 1
    rows = list(list_org_costs(window=W))
    assert rows[0]["calls"] == 2 and rows[0]["cost"] == Decimal("0") and rows[0]["input_tokens"] == 0

def test_active_shops_counts_distinct_shops_with_success(db): ...  # 3 SUCCESS rows over 2 shops + 1 FAILED on 3rd shop → 2

def test_org_list_sort_by_name_ascending(db):
    assert [r["name"] for r in list_org_costs(window=W, sort="name")] == ["Alpha", "Beta"]

def test_org_list_unknown_sort_raises(db):
    with pytest.raises(ValidationError):
        list_org_costs(window=W, sort="-latency")

def test_request_type_costs_sum_to_org_cost(db):
    # enrichment 1.20 + reply_generation 0.30 (+ a FAILED reply row, ignored)
    by_type = get_request_type_costs(window=W, organisation_ids=[org.id])
    assert by_type == {org.id: {"enrichment": Decimal("1.20"), "reply_generation": Decimal("0.30")}}

def test_selectors_use_fixed_query_counts(db, django_assert_max_num_queries):
    # 20 orgs × 3 rows each
    with django_assert_max_num_queries(1): get_cost_summary(window=W)
    with django_assert_max_num_queries(1): list(list_org_costs(window=W))
    with django_assert_max_num_queries(1): get_request_type_costs(window=W, organisation_ids=ids)
```

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_ai_cost_selectors.py -v` — Expected: FAIL (ImportError).
- [ ] **Step 3: Implement the selectors** in `apps/integrations/openai/selectors/ai_cost.py` per the Interfaces block.
- [ ] **Step 4: Run** the tests — Expected: PASS.
- [ ] **Step 5: Add indexes** to `AiUsageLog.Meta.indexes`: `Index(fields=["organisation", "status", "created_at"], name="ai_usage_org_status_created_idx")` and `Index(fields=["organisation", "request_type", "created_at"], name="ai_usage_org_type_created_idx")`; run `uv run python manage.py makemigrations openai --name ai_usage_cost_indexes`, then `uv run python manage.py migrate` and `uv run python manage.py migrate openai <previous>` and back again to prove the migration reverses.
- [ ] **Step 6: Record `EXPLAIN ANALYZE`** for `list_org_costs` and `get_cost_summary` on a local dataset of ~100k rows (seed with a throwaway shell loop of `bulk_create`) in the PR description. If the planner does not use an added index, drop that index from the migration.
- [ ] **Step 7: Commit** `git commit -m "feat(ai-cost): summary + organisation cost selectors and indexes"`

---

### Task 3: Shop and model breakdown selectors

**Files:**
- Modify: `apps/integrations/openai/selectors/ai_cost.py`
- Test: `apps/integrations/openai/tests/test_ai_cost_selectors.py`

**Interfaces:**
- Consumes: `CostWindow`, `CostTotals` (Tasks 1–2).
- Produces:
  - `SHOP_SORT_FIELDS` keys `name, calls, input_tokens, output_tokens, cost`; `def list_shop_costs(*, window: CostWindow, organisation_id: int, sort: str = "-cost") -> QuerySet` — `values()` rows `shop_id, name, region_name, calls, input_tokens, output_tokens, cost`, filtered to `review__isnull=False`, grouped by `review__shop_id`.
  - `def get_shop_request_type_costs(*, window: CostWindow, organisation_id: int, shop_ids: Sequence[int]) -> dict[int, dict[str, Decimal]]`.
  - `def get_unattributed_costs(*, window: CostWindow, organisation_id: int) -> (CostTotals & {"by_request_type": dict[str, Decimal]}) | None` — rows with `review_id IS NULL`; `None` when there are zero such calls. Max 2 queries.
  - `def list_model_costs(*, window: CostWindow, organisation_id: int) -> list[dict]` — keys `model, calls, input_tokens, output_tokens, cost`, ordered `-cost, model`.

- [ ] **Step 1: Write the failing tests**

```python
def test_shop_list_groups_by_shop_and_sorts_by_cost(db): ...  # 2 shops, asserts order + per-shop sums + region_name

def test_shop_list_scoped_to_org(db): ...  # a shop row from another org never appears

def test_unattributed_row_holds_rows_without_review(db):  # Review Focus 5
    AiUsageLogFactory(organisation=org, review=review_in_shop_a, estimated_cost_usd=Decimal("1.00"), created_at=IN)
    AiUsageLogFactory(organisation=org, review=None, estimated_cost_usd=Decimal("0.40"), created_at=IN)
    shops = list(list_shop_costs(window=W, organisation_id=org.id))
    un = get_unattributed_costs(window=W, organisation_id=org.id)
    assert sum(r["cost"] for r in shops) + un["cost"] == get_cost_summary(window=W, organisation_id=org.id)["cost"]
    assert un["cost"] == Decimal("0.40")

def test_unattributed_is_none_when_all_rows_have_reviews(db): ...

def test_model_costs_sum_to_org_cost(db): ...  # two models; sum equals org summary cost

def test_drilldown_selectors_fixed_query_counts(db, django_assert_max_num_queries): ...
    # 15 shops × 2 rows: list_shop_costs 1, get_shop_request_type_costs 1, get_unattributed_costs ≤2, list_model_costs 1
```

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_ai_cost_selectors.py -v` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the four functions.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(ai-cost): shop, unattributed and model breakdown selectors"`

---

### Task 4: Platform API endpoints (summary + organisation list)

**Files:**
- Create: `apps/integrations/openai/serializers.py`, `apps/integrations/openai/views.py`, `apps/integrations/openai/api_urls.py`
- Modify: `config/urls.py` (add `path("api/v1/", include("apps.integrations.openai.api_urls"))` beside the credits include), `config/settings/base.py` (`"superadmin_ai_cost_read": "120/minute"` in `DEFAULT_THROTTLE_RATES`)
- Test: `apps/integrations/openai/tests/test_ai_cost_views.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces (JSON contracts the frontend relies on; Decimals serialised as strings with 6 dp, ints as ints):
  - `GET /api/v1/superadmin/ai-cost/summary/?range=…` → `{"range": {"key","start","end"}, "generated_at", "has_any_usage": bool (one `AiUsageLog.objects.exists()` query, any date), "totals": {calls, success_calls, failed_calls, moderated_calls, input_tokens, output_tokens, cost, org_count, active_shops}}`  — url name `superadmin-ai-cost-summary`
  - `GET /api/v1/superadmin/ai-cost/organisations/?range=…&page=&page_size=&sort=` → DRF page `{"count","next","previous","results":[{organisation_id, name, org_type, active_shops, calls, input_tokens, output_tokens, cost, by_request_type: {type: cost}}]}` plus top-level `generated_at` — url name `superadmin-ai-cost-orgs`
  - A shared helper in `views.py`: `def _cached(endpoint: str, request: Request, build: Callable[[], dict]) -> dict` — key `f"admin:ai_cost:{endpoint}:{sha1(request.get_full_path())}"` (the window's `cache_hash` folded in so rolling ranges change keys per minute), TTL 600.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
@pytest.mark.parametrize("url", [SUMMARY_URL, ORGS_URL])
def test_non_superadmin_gets_403(db, factory, url):
    c = APIClient(); c.force_authenticate(factory())
    assert c.get(url).status_code == 403

def test_anonymous_gets_401_or_403(db): ...

def test_summary_shape_and_values(db, superadmin_client): ...  # asserts keys + cost "1.000000"

def test_bad_range_returns_400(db, superadmin_client):
    r = superadmin_client.get(SUMMARY_URL, {"range": "custom", "from": "2026-10-31", "to": "2026-10-01"})
    assert r.status_code == 400

def test_org_list_includes_request_type_badges_and_paginates(db, superadmin_client):
    # 30 active orgs → default page has 25, page_size=10 → 10
    ...

def test_org_list_query_ceiling(db, superadmin_client, assert_query_ceiling):
    # 40 orgs × 3 rows; cache cleared first
    with CaptureQueriesContext(connection) as ctx:
        superadmin_client.get(ORGS_URL)
    assert_query_ceiling(ctx, max_queries=6)   # auth/session + count + page + badges

def test_second_call_is_served_from_cache(db, superadmin_client, django_assert_max_num_queries): ...
    # first GET warms; second GET of same URL runs ≤ 2 queries (auth only)

def test_views_are_throttled():
    assert AiCostSummaryView.throttle_scope == "superadmin_ai_cost_read"
```

Add a `superadmin_client` fixture in `apps/integrations/openai/tests/conftest.py` (`UserFactory()` is a superadmin) and re-export `assert_query_ceiling` from `apps.common.tests.fixtures` as `apps/credits/tests/conftest.py` does. Clear the default cache in an autouse fixture.

- [ ] **Step 2: Run** `uv run pytest apps/integrations/openai/tests/test_ai_cost_views.py -v` — Expected: FAIL (404 on URLs).
- [ ] **Step 3: Implement** `AiCostSummaryView`, `AiCostOrganisationListView` (`APIView`, Global Constraints permissions/throttle, `@extend_schema` with `tags=["superadmin-ai-cost"]` and the `range/from/to/sort/page/page_size` parameters), response serializers, `api_urls.py`, and the two config edits.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Run** `uv run python manage.py spectacular --validate --fail-on-warn --file /dev/null` — Expected: exit 0.
- [ ] **Step 6: Commit** `git commit -m "feat(ai-cost): superadmin summary and organisation list endpoints"`

---

### Task 5: Organisation drill-down endpoints

**Files:**
- Modify: `apps/integrations/openai/views.py`, `serializers.py`, `api_urls.py`
- Test: `apps/integrations/openai/tests/test_ai_cost_views.py`

**Interfaces:**
- Consumes: Tasks 1–4 (`_cached`, serializers).
- Produces:
  - `GET …/ai-cost/organisations/<int:org_id>/summary/` → `{"organisation": {id, name, org_type, shop_count}, "range", "generated_at", "totals": {…same as platform…}}` — name `superadmin-ai-cost-org-summary`. `shop_count` = all shops of the org (header subtitle "N shops").
  - `GET …/organisations/<int:org_id>/shops/?sort=&page=&page_size=` → DRF page of `{shop_id, name, region_name, calls, input_tokens, output_tokens, cost, by_request_type}` plus top-level `"unattributed": {calls, input_tokens, output_tokens, cost, by_request_type} | null` and `generated_at` — name `superadmin-ai-cost-org-shops`.
  - `GET …/organisations/<int:org_id>/models/` → `{"results": [{model, calls, input_tokens, output_tokens, cost}], "generated_at"}` — name `superadmin-ai-cost-org-models`.
  - All three return **404** `{"code": "organisation_not_found", "detail": "Organisation not found."}` for an unknown `org_id`.

- [ ] **Step 1: Write the failing tests**

```python
def test_unknown_org_returns_404_on_all_drilldown_endpoints(db, superadmin_client): ...   # Review Focus 4

def test_existing_org_without_activity_returns_zeros(db, superadmin_client):              # Review Focus 4
    r = superadmin_client.get(org_summary_url(org.id))
    assert r.status_code == 200 and r.json()["totals"]["calls"] == 0
    assert superadmin_client.get(org_shops_url(org.id)).json()["results"] == []

def test_shops_endpoint_returns_unattributed_block(db, superadmin_client): ...
def test_models_endpoint_sorted_by_cost(db, superadmin_client): ...
@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
def test_drilldown_forbidden_for_tenants(db, factory): ...   # incl. an org admin requesting their OWN org → 403
def test_drilldown_query_ceilings(db, superadmin_client, assert_query_ceiling): ...
    # summary ≤ 5, shops ≤ 8, models ≤ 4 with 20 shops × 3 rows
```

- [ ] **Step 2: Run** the view tests — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the three views and serializers.
- [ ] **Step 4: Run** the full openai test package `uv run pytest apps/integrations/openai -v` — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(ai-cost): organisation drill-down endpoints"`

---

### Task 6: Page routes, template and sidebar

**Files:**
- Create: `apps/integrations/openai/urls.py`, `templates/ai_cost/explorer.html`
- Modify: `apps/integrations/openai/views.py` (page view), `config/urls.py` (`path("", include("apps.integrations.openai.urls"))` with the other page includes), `templates/partials/sidebar.html` (superadmin branch, after "Organisations")
- Test: `apps/integrations/openai/tests/test_ai_cost_views.py`

**Interfaces:**
- Produces: `def ai_cost_page(request: HttpRequest, org_id: int | None = None) -> HttpResponse` at `admin/ai-cost/` (name `ai_cost_explorer`) and `admin/ai-cost/organisations/<int:org_id>/` (name `ai_cost_org_detail`). Anonymous → redirect `/login/` (match `organisation_list`); authenticated non-superadmin → `HttpResponseForbidden()`. Template extends `base.html`, renders `<div id="ai-cost-root" data-org-id="{{ org_id|default:'' }}"></div>` and `{% vite_asset 'src/entrypoints/ai-cost-explorer.tsx' %}` in `extra_js`.
- Sidebar line: `{% include "partials/_nav_item.html" with href="/admin/ai-cost/" icon="zap" label="AI Cost" %}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_page_renders_for_superadmin(client, db):  # both routes 200, contains 'id="ai-cost-root"'
def test_org_detail_page_passes_org_id(client, db):  # contains 'data-org-id="<id>"'
@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
def test_page_forbidden_for_tenants(client, db, factory): ...  # 403
def test_sidebar_shows_ai_cost_only_for_superadmin(client, db): ...  # '/admin/ai-cost/' in superadmin page HTML, absent from an org admin's dashboard HTML
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** the view, urls, template and sidebar line. (Existing page tests such as the audit-log page already render `vite_asset` tags under test settings; follow the same setup.)
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(ai-cost): superadmin AI Cost page shell and sidebar entry"`

---

### Task 7: React widget — platform view

**Files:**
- Modify: `frontend/vite.config.ts` (input map: `"ai-cost-explorer": resolve(__dirname, "src/entrypoints/ai-cost-explorer.tsx")`)
- Create: `frontend/src/entrypoints/ai-cost-explorer.tsx` (mount pattern of `audit-log.tsx`: guard `dataset.mounted`, also on `turbo:load`)
- Create: `frontend/src/widgets/ai-cost/types.ts`, `api.ts`, `format.ts`, `urlState.ts`, `AiCostWidget.tsx`, `RangeFilter.tsx`, `KpiRow.tsx`, `OrgTable.tsx`, `RequestTypeBadges.tsx`
- Test: `frontend/src/widgets/ai-cost/format.test.ts`, `urlState.test.ts`, `OrgTable.test.tsx`, `RequestTypeBadges.test.tsx`

**Interfaces:**
- Consumes: Task 4 JSON contracts (types in `types.ts` mirror them exactly; cost fields are `string`).
- Produces:
  - `format.ts`: `formatCost(v: string): string` → `"$1,245.67"`; `formatTokens(n: number): string` → `"12.4M" | "342K" | "999"`; `formatCount(n: number): string` → `"48,312"`; `avgPerCall(total: number, calls: number): number` → 0 when `calls === 0`.
  - `urlState.ts`: `readFilters(search: string): CostFilters` / `writeFilters(f: CostFilters): string` with `CostFilters = { range: RangeKey; from?: string; to?: string }`, default `this_month`.
  - `AiCostWidget({ orgId }: { orgId: number | null })` renders the platform view when `orgId` is null, else `OrgDetail` (Task 8). Navigation to a row uses `history.pushState` to `/admin/ai-cost/organisations/{id}/?{query}` and listens to `popstate`.

- [ ] **Step 1: Write the failing tests**

```ts
expect(formatCost("1245.670000")).toBe("$1,245.67");
expect(formatCost("0.000195")).toBe("$0.00");
expect(formatTokens(12_400_000)).toBe("12.4M");
expect(formatTokens(342_000)).toBe("342K");
expect(formatTokens(999)).toBe("999");
expect(formatCount(48312)).toBe("48,312");
expect(avgPerCall(500, 0)).toBe(0);                       // Review Focus 1
expect(readFilters("")).toEqual({ range: "this_month" });
expect(readFilters(writeFilters({ range: "custom", from: "2026-10-01", to: "2026-10-31" })))
  .toEqual({ range: "custom", from: "2026-10-01", to: "2026-10-31" });
// RequestTypeBadges renders every key it is given, incl. an unknown "summary" type
// OrgTable: clicking the "Cost" header calls onSort("cost"); clicking again calls onSort("-cost");
//           clicking a row calls onOpen(organisation_id); token cell has title="12,400,000"
```

- [ ] **Step 2: Run** `cd frontend && npx vitest run src/widgets/ai-cost` — Expected: FAIL.
- [ ] **Step 3: Implement** the files. Copy (exact): header "AI Cost Explorer", subtitle "Platform-wide OpenAI spend"; KPI footers "Across N organisations", "N succeeded · M failed · K moderated", "Avg N per call"; empty states: when `has_any_usage` is false → "No AI calls yet. Costs will appear here as reviews are enriched."; otherwise when the window is empty → "No AI usage in this period" / "Try widening the date range."; footer caveat from Global Constraints; "Updated X min ago" from `generated_at`. Page-size selector 10/25/50/100. Lucide icons per CE §4.2.
- [ ] **Step 4: Run** vitest — Expected: PASS. Run `cd frontend && npm run build` — Expected: exit 0.
- [ ] **Step 5: Commit** `git commit -m "feat(ai-cost): React platform view for AI Cost Explorer"`

---

### Task 8: React widget — organisation drill-down

**Files:**
- Create: `frontend/src/widgets/ai-cost/OrgDetail.tsx`, `ShopTable.tsx`, `ModelTable.tsx`
- Test: `frontend/src/widgets/ai-cost/ShopTable.test.tsx`

**Interfaces:**
- Consumes: Task 5 JSON contracts; `format.ts`, `urlState.ts`, `KpiRow`, `RangeFilter`, `RequestTypeBadges` (Task 7).
- Produces: `OrgDetail({ orgId, filters, onBack })`.

- [ ] **Step 1: Write the failing tests**

```ts
// ShopTable renders an "Unattributed" final row when `unattributed` is non-null, not clickable, no region badge
// ShopTable renders no "Unattributed" row when it is null
// ShopTable shows the region badge text for each shop
```

- [ ] **Step 2: Run** vitest — Expected: FAIL.
- [ ] **Step 3: Implement.** Header: back link "← Back to AI Cost" (returns to `/admin/ai-cost/?{same query}`), org name, subtitle "{org type} · {N} shops · active in date range"; scoped KPI row; shops table (sortable, paginated); "Cost by Model" table; 404 → "Organisation not found"; empty → "No AI usage for this organisation in the selected period" with a "Reset filter" link to `this_month`.
- [ ] **Step 4: Run** vitest and `npm run build` — Expected: PASS / exit 0.
- [ ] **Step 5: Manually verify** with `make up`: log in as superadmin, open `/admin/ai-cost/`, switch range, open an org, press browser Back — filter is preserved; log in as an org admin — `/admin/ai-cost/` is 403 and no sidebar entry.
- [ ] **Step 6: Commit** `git commit -m "feat(ai-cost): organisation drill-down view"`

---

### Task 9: Phase close-out

**Files:**
- Modify: `.planning/ROADMAP.md` (tick Phase 34), `CLAUDE.md` §3 tree (`apps/integrations/openai/selectors/ai_cost.py`, `views.py`, `api_urls.py`)

- [ ] **Step 1:** Run the `code-reviewer`, `orm-performance-auditor` and `tenant-security-auditor` subagents on the branch diff; apply findings.
- [ ] **Step 2:** Run `uv run pre-commit run --all-files` — Expected: all pass.
- [ ] **Step 3:** Run `uv run pytest` — Expected: full suite passes, coverage ≥ 85% on new selectors/views.
- [ ] **Step 4:** Run `uv run python manage.py makemigrations --check --dry-run` — Expected: "No changes detected".
- [ ] **Step 5:** Update ROADMAP + CLAUDE.md and commit `git commit -m "docs(ai-cost): close out phase 34"`
