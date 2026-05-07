# Architecture Research

**Domain:** Multi-tenant SaaS — Organisation Admin Dashboard (v0.4)
**Researched:** 2026-05-07
**Confidence:** HIGH — based on direct codebase inspection, not training assumptions

---

## Standard Architecture

### System Overview

```text
Browser (Django Template: dashboard.html)
    │
    ├── Django template renders page shell, filter dropdowns, JSON bootstrap data
    │    (regions list, shops list) into <script type="application/json"> tags
    │
    └── <div id="dashboard-root"> mounts single React island
         │
         ├── DashboardWidget (React root — one entrypoint)
         │    ├── useFilterState        — URL + sessionStorage sync
         │    ├── FilterBar             — cascading Region→Store dropdowns + date range
         │    ├── useTopPerforming      — React Query → GET /api/v1/dashboard/top-performing/
         │    ├── useHighlights         — React Query → GET /api/v1/dashboard/highlights/
         │    │                              OR useYourStore for single-shop
         │    ├── useKpis               — React Query → GET /api/v1/dashboard/kpis/
         │    └── useSentiment          — React Query → GET /api/v1/dashboard/sentiment-distribution/
         │
         └── All 5 calls fire in parallel on mount and on filter change

Django API Layer (apps/dashboard/)
    │
    ├── views.py (5 APIView subclasses, not ViewSets — no CRUD, pure read)
    │    ├── GET /api/v1/dashboard/top-performing/      (date-range filter only)
    │    ├── GET /api/v1/dashboard/highlights/          (date-range filter only)
    │    ├── GET /api/v1/dashboard/your-store/          (date-range filter only)
    │    ├── GET /api/v1/dashboard/kpis/               (full filter)
    │    └── GET /api/v1/dashboard/sentiment-distribution/  (full filter)
    │
    ├── filters.py — DashboardFilterParams (dataclass, not FilterSet)
    │    └── validate_filter_params() — raises ValidationError or PermissionDenied
    │
    ├── selectors/aggregations.py — all ORM aggregations; views call these
    │
    └── services/cache.py — cache_get / cache_set helpers, key builder

Redis (DB 0, "default" cache, KEY_PREFIX="app")
    └── dashboard:{endpoint}:{org_id}:{user_id}:{filter_hash} → TTL 5 min

PostgreSQL (Review table + 3 new composite indexes)
    ├── (organisation_id, review_create_time, sentiment)    — KPI + sentiment queries
    ├── (shop_id, review_create_time)                       — top-performing per shop
    └── (organisation_id, review_create_time, enrichment_status) — sentiment coverage
```

---

## Component Responsibilities

| Component | Responsibility | Location |
| --------- | -------------- | -------- |
| `DashboardWidget` | Single React root; owns QueryClient; renders all sections | `frontend/src/widgets/dashboard/` |
| `FilterBar` | Cascading region/store dropdowns, date range, URL sync | `frontend/src/widgets/dashboard/FilterBar.tsx` |
| `useDashboard*` hooks | React Query wrappers; one per endpoint | `frontend/src/widgets/dashboard/use*.ts` |
| `DashboardApiView` (base) | Shared filter validation + permission check; all 5 views inherit | `apps/dashboard/views.py` |
| `validate_filter_params()` | Scope enforcement: out-of-scope region/store → 403; range >365d → 400; from>to → 400 | `apps/dashboard/filters.py` |
| `aggregations.py` | All ORM `.aggregate()` / `.annotate()` calls; selectors pattern — no mutations | `apps/dashboard/selectors/aggregations.py` |
| `services/cache.py` | `dashboard_cache_key()`, `cache_get()`, `cache_set()` — TTL-only, 5 min | `apps/dashboard/services/cache.py` |
| 3 new Review indexes | Eliminate seq-scan on filtered aggregate queries | `apps/reviews/migrations/000N_dashboard_indexes.py` |

---

## Recommended Project Structure

```text
apps/dashboard/
├── __init__.py
├── apps.py
├── urls.py                  # urlpatterns for all 5 endpoints
├── filters.py               # DashboardFilterParams dataclass + validate_filter_params()
├── views.py                 # DashboardApiView base + 5 concrete views
├── selectors/
│   ├── __init__.py
│   └── aggregations.py      # top_performing(), kpis(), sentiment_distribution(), highlights()
├── services/
│   ├── __init__.py
│   └── cache.py             # dashboard_cache_key(), cache_get(), cache_set()
└── tests/
    ├── __init__.py
    ├── factories.py          # reuse ReviewFactory from apps/reviews/tests/factories.py
    ├── test_filters.py       # validate_filter_params() — 403/400 branches
    ├── test_aggregations.py  # ORM aggregation correctness + query count assertions
    └── test_views.py         # end-to-end with CaptureQueriesContext per endpoint

frontend/src/widgets/dashboard/
├── DashboardWidget.tsx       # root component; owns QueryClient; renders all sections
├── FilterBar.tsx             # region+store cascading dropdowns, date range, clear
├── TopPerformingSection.tsx  # bar chart + highlights card
├── KpiCards.tsx              # total reviews, avg rating, negative count
├── SentimentDonut.tsx        # donut + summary + coverage footer
├── api.ts                   # fetch wrappers for all 5 endpoints
├── types.ts                 # TypeScript response types
├── useFilterState.ts         # URL search params + sessionStorage sync
├── useTopPerforming.ts       # React Query hook
├── useHighlights.ts          # React Query hook
├── useKpis.ts               # React Query hook
├── useSentiment.ts          # React Query hook
└── useDashboardData.ts      # orchestrator: runs all 4 queries in parallel

frontend/src/entrypoints/
└── dashboard.tsx            # mounts DashboardWidget on #dashboard-root
```

---

## Architectural Patterns

### Pattern 1: Single `DashboardApiView` Base Class for Shared Validation

**What:** All 5 endpoints inherit a common base `APIView` that handles filter extraction, scope validation, and cache lookup/population. Concrete subclasses implement only `_fetch()` which calls the appropriate selector.

**When to use:** Anytime 5+ endpoints share identical validation logic. Avoids copy-paste divergence.

**Trade-offs:** Thin base class is fine. Resist putting aggregation logic in the base — keep that in selectors.

```python
# apps/dashboard/views.py
from __future__ import annotations
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from apps.common.permissions import IsOrgScoped
from apps.dashboard.filters import validate_filter_params, DashboardFilterParams
from apps.dashboard.services.cache import dashboard_cache_key, cache_get, cache_set

DASHBOARD_TTL = 300  # 5 minutes

class DashboardApiView(APIView):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    endpoint_name: str = ""  # set by subclass

    def get(self, request: Request) -> Response:
        user = request.user
        org_id: int = user.organisation_id
        # validate_filter_params raises ValidationError (400) or PermissionDenied (403)
        params: DashboardFilterParams = validate_filter_params(
            request=request,
            user=user,
            org_id=org_id,
        )
        key = dashboard_cache_key(
            endpoint=self.endpoint_name,
            org_id=org_id,
            user_id=user.pk,
            params=params,
        )
        cached = cache_get(key)
        if cached is not None:
            return Response(cached)
        data = self._fetch(org_id=org_id, params=params, user=user)
        cache_set(key, data, ttl=DASHBOARD_TTL)
        return Response(data)

    def _fetch(self, *, org_id: int, params: DashboardFilterParams, user) -> dict:
        raise NotImplementedError


class KpisView(DashboardApiView):
    endpoint_name = "kpis"

    def _fetch(self, *, org_id, params, user):
        from apps.dashboard.selectors.aggregations import dashboard_kpis
        return dashboard_kpis(org_id=org_id, params=params)
```

### Pattern 2: `DashboardFilterParams` Dataclass with Centralised Scope Enforcement

**What:** A frozen dataclass (not a Django FilterSet) holds validated, normalised filter values plus the resolved `accessible_shop_ids` tuple. The `validate_filter_params()` function is the single point where scope checks, range limits, and ordering of `from_date`/`to_date` are enforced.

**When to use:** Dashboard endpoints are read-only aggregations, not ORM querysets — Django FilterSet is overkill and adds unnecessary coupling to model field names.

**Trade-offs:** The dataclass approach means filter validation is tested independently of DRF, which is easier to test and reason about.

```python
# apps/dashboard/filters.py
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from datetime import date
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.reviews.selectors.reviews import get_accessible_shop_ids
from apps.accounts.models import User

@dataclass(frozen=True)
class DashboardFilterParams:
    region_id: int | None
    shop_id: int | None
    date_from: date | None
    date_to: date | None
    # resolved shop IDs scoped to user; always populated; used in cache key
    accessible_shop_ids: tuple[int, ...]

    def filter_hash(self) -> str:
        """Deterministic hash for cache key — includes accessible_shop_ids for Staff scoping."""
        payload = {
            "region_id": self.region_id,
            "shop_id": self.shop_id,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "shop_ids": list(self.accessible_shop_ids),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def validate_filter_params(*, request, user, org_id: int) -> DashboardFilterParams:
    qp = request.query_params

    # resolve accessible shops (always needed for scoping + cache key)
    if user.role == User.Role.STAFF_ADMIN:
        accessible = tuple(get_accessible_shop_ids(user_id=user.pk))
    else:
        # ORG_ADMIN sees all active shops in org
        from apps.shops.models import Shop
        accessible = tuple(
            Shop.objects.filter(organisation_id=org_id, is_active=True)
            .values_list("id", flat=True)
            .order_by("id")
        )

    # region param
    region_id: int | None = None
    if raw_region := qp.get("region"):
        try:
            region_id = int(raw_region)
        except ValueError:
            raise ValidationError({"region": "Must be an integer."})
        from apps.regions.models import Region
        if not Region.objects.filter(id=region_id, organisation_id=org_id).exists():
            raise PermissionDenied("Region is not in your organisation.")

    # shop param
    shop_id: int | None = None
    if raw_shop := qp.get("shop"):
        try:
            shop_id = int(raw_shop)
        except ValueError:
            raise ValidationError({"shop": "Must be an integer."})
        if shop_id not in accessible:
            raise PermissionDenied("Shop is not accessible to you.")

    # date params
    date_from: date | None = None
    date_to: date | None = None
    if raw_from := qp.get("from"):
        try:
            date_from = date.fromisoformat(raw_from)
        except ValueError:
            raise ValidationError({"from": "Must be ISO date (YYYY-MM-DD)."})
    if raw_to := qp.get("to"):
        try:
            date_to = date.fromisoformat(raw_to)
        except ValueError:
            raise ValidationError({"to": "Must be ISO date (YYYY-MM-DD)."})

    if date_from and date_to:
        if date_from > date_to:
            raise ValidationError({"from": "from date cannot be after to date."})
        if (date_to - date_from).days > 365:
            raise ValidationError({"range": "Custom date range cannot exceed 365 days."})

    return DashboardFilterParams(
        region_id=region_id,
        shop_id=shop_id,
        date_from=date_from,
        date_to=date_to,
        accessible_shop_ids=accessible,
    )
```

### Pattern 3: Cache Key Embeds `accessible_shop_ids` for Correct Staff Scoping

**What:** The cache key includes a hash of `accessible_shop_ids` (the Staff user's resolved shop list). Two Staff users in the same org with different scope assignments get different cache entries. An Org Admin's cache key includes all active shops in the org.

**When to use:** Any multi-role system where different users within the same org should see different aggregate data subsets.

**Trade-offs:** Cache hit rate is lower for Staff users (more unique keys) but correctness is non-negotiable. TTL-only invalidation is safe here because dashboard data staleness of 5 minutes is acceptable — do not add event-based invalidation for this endpoint (complexity not justified for aggregate read data).

```python
# apps/dashboard/services/cache.py
from __future__ import annotations
from django.core.cache import cache
from apps.dashboard.filters import DashboardFilterParams

def dashboard_cache_key(
    *,
    endpoint: str,
    org_id: int,
    user_id: int,
    params: DashboardFilterParams,
) -> str:
    """
    Format: dashboard:{endpoint}:{org_id}:{user_id}:{filter_hash}

    filter_hash is a 16-char SHA-256 prefix of the serialised filter params
    including accessible_shop_ids — this is what prevents cross-user cache leakage
    for Staff Admins with different StaffAccessScope assignments.
    """
    return f"dashboard:{endpoint}:{org_id}:{user_id}:{params.filter_hash()}"

def cache_get(key: str) -> dict | None:
    return cache.get(key)

def cache_set(key: str, data: dict, *, ttl: int) -> None:
    cache.set(key, data, timeout=ttl)
```

**Critical correctness note:** Including `user_id` in the key is intentional. Two Org Admins in the same org see identical data, so their keys differ only by `user_id`. This is slightly redundant for Org Admins (where `accessible_shop_ids` is the same for all Org Admins in the same org) but it eliminates any possibility of a Staff Admin receiving a cached result from an Org Admin's key or vice versa. The 5-minute TTL means the worst-case wastage is a few extra Redis keys — acceptable.

### Pattern 4: ORM Aggregations with `Q` Filters — All in Selectors

**What:** All `aggregate()` and `annotate()` calls live in `apps/dashboard/selectors/aggregations.py`. Views call selector functions. No raw SQL.

**When to use:** Always in this codebase. The services/selectors pattern is established convention.

```python
# apps/dashboard/selectors/aggregations.py
from __future__ import annotations
from django.db.models import Avg, Count, Q
from apps.reviews.models import Review
from apps.dashboard.filters import DashboardFilterParams


def _base_qs(org_id: int, params: DashboardFilterParams):
    """Base active queryset scoped to org + accessible shops + date range."""
    qs = (
        Review.objects.active()
        .filter(organisation_id=org_id)
        .filter(shop_id__in=params.accessible_shop_ids)
    )
    if params.region_id is not None:
        qs = qs.filter(shop__region_id=params.region_id)
    if params.shop_id is not None:
        qs = qs.filter(shop_id=params.shop_id)
    if params.date_from is not None:
        qs = qs.filter(review_create_time__date__gte=params.date_from)
    if params.date_to is not None:
        qs = qs.filter(review_create_time__date__lte=params.date_to)
    return qs


def dashboard_kpis(*, org_id: int, params: DashboardFilterParams) -> dict:
    """
    KPI card row: total reviews, average rating, negative review count.
    Negative = AI sentiment "negative" WHERE enrichment_status = SUCCESS only.
    Query count: 1 (single aggregate call).
    """
    qs = _base_qs(org_id, params)
    agg = qs.aggregate(
        total_reviews=Count("pk"),
        avg_rating=Avg("star_rating"),
        negative_count=Count(
            "pk",
            filter=Q(
                sentiment="negative",
                enrichment_status=Review.EnrichmentStatus.SUCCESS,
            ),
        ),
    )
    return {
        "total_reviews": agg["total_reviews"] or 0,
        "avg_rating": round(float(agg["avg_rating"] or 0.0), 1),
        "negative_reviews": agg["negative_count"] or 0,
    }


def dashboard_sentiment_distribution(*, org_id: int, params: DashboardFilterParams) -> dict:
    """
    Sentiment donut: positive/neutral/negative counts for enriched reviews only.
    Coverage = enriched / total (for the footer).
    Query count: 1 (single aggregate call with 4 conditional counts).
    """
    qs = _base_qs(org_id, params)
    agg = qs.aggregate(
        total=Count("pk"),
        enriched=Count("pk", filter=Q(enrichment_status=Review.EnrichmentStatus.SUCCESS)),
        positive=Count(
            "pk",
            filter=Q(sentiment="positive", enrichment_status=Review.EnrichmentStatus.SUCCESS),
        ),
        neutral=Count(
            "pk",
            filter=Q(sentiment="neutral", enrichment_status=Review.EnrichmentStatus.SUCCESS),
        ),
        negative=Count(
            "pk",
            filter=Q(sentiment="negative", enrichment_status=Review.EnrichmentStatus.SUCCESS),
        ),
    )
    total: int = agg["total"] or 0
    enriched: int = agg["enriched"] or 0
    coverage_pct: int = round(enriched / total * 100) if total > 0 else 0
    return {
        "positive": agg["positive"] or 0,
        "neutral": agg["neutral"] or 0,
        "negative": agg["negative"] or 0,
        "enriched_count": enriched,
        "total_count": total,
        "coverage_pct": coverage_pct,
    }


def dashboard_top_performing(
    *, org_id: int, params: DashboardFilterParams, limit: int = 10
) -> list[dict]:
    """
    Bar chart: shops ranked by average rating + review count, descending.
    Uses date-range-only (region/shop filter NOT applied — per spec).
    N+1 risk: shop name fetched in the same query via values("shop__name") — no extra query.
    Query count: 1 (single values/annotate/order_by).
    """
    qs = (
        Review.objects.active()
        .filter(organisation_id=org_id)
        .filter(shop_id__in=params.accessible_shop_ids)
    )
    if params.date_from is not None:
        qs = qs.filter(review_create_time__date__gte=params.date_from)
    if params.date_to is not None:
        qs = qs.filter(review_create_time__date__lte=params.date_to)

    rows = (
        qs.values("shop_id", "shop__name")
        .annotate(
            review_count=Count("pk"),
            avg_rating=Avg("star_rating"),
        )
        .order_by("-avg_rating", "-review_count")[:limit]
    )
    return [
        {
            "shop_id": r["shop_id"],
            "shop_name": r["shop__name"],
            "review_count": r["review_count"],
            "avg_rating": round(float(r["avg_rating"] or 0.0), 2),
        }
        for r in rows
    ]
```

### Pattern 5: React Query for Parallel Fetching with Filter State as Query Keys

**What:** One `QueryClient` is instantiated in `DashboardWidget`. Each widget section uses `useQuery` with a stable query key that includes all filter state. When filters change, all 5 queries refetch automatically because their keys change.

**When to use:** Multiple independent data fetches that all depend on shared filter state. React Query's declarative key-based refetch model eliminates the `useEffect` + manual fetch chains found in the existing `useReviews.ts`.

**Trade-offs:** React Query is not currently a dependency (`package.json` confirms only `react`, `react-dom`, `lucide-react`, `alpinejs`, `focus-trap-react`). It must be added (`@tanstack/react-query`). The existing custom `useReviews` / `useActionItems` patterns use `useState` + `useEffect` + `useCallback` and work for single-endpoint widgets. For a dashboard with 5 parallel endpoints that all share filter state, React Query eliminates ~150 lines of boilerplate and provides automatic background refetch, stale-while-revalidate, and loading/error states per query — worth the new dependency.

```typescript
// frontend/src/widgets/dashboard/DashboardWidget.tsx
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useFilterState } from "./useFilterState";
import { fetchKpis, fetchSentiment, fetchTopPerforming, fetchHighlights } from "./api";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5 min — matches server TTL exactly
      retry: 1,
    },
  },
});

export function DashboardWidget() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardInner />
    </QueryClientProvider>
  );
}

function DashboardInner() {
  const { filters, setRegion, setShop, setDateRange, clearFilters } = useFilterState();

  // All 5 queries fire in parallel; each re-fetches when filters change.
  // queryKey includes filters so React Query treats different filter combos as distinct cache entries.
  const kpisQuery = useQuery({
    queryKey: ["dashboard", "kpis", filters],
    queryFn: () => fetchKpis(filters),
  });

  const sentimentQuery = useQuery({
    queryKey: ["dashboard", "sentiment", filters],
    queryFn: () => fetchSentiment(filters),
  });

  // top-performing uses date range only — region/shop excluded from key to match server behaviour
  const topFilters = { date_from: filters.date_from, date_to: filters.date_to };
  const topQuery = useQuery({
    queryKey: ["dashboard", "top-performing", topFilters],
    queryFn: () => fetchTopPerforming(topFilters),
  });

  const highlightsQuery = useQuery({
    queryKey: ["dashboard", "highlights", topFilters],
    queryFn: () => fetchHighlights(topFilters),
  });

  return ( /* render sections from each query result */ );
}
```

**Note on `staleTime: 5 * 60 * 1000`:** Matches the server-side TTL exactly. React Query will not refetch from the server within 5 minutes of a successful fetch — the client-side cache and server-side Redis cache share the same TTL window, preventing redundant requests.

---

## Data Flow

### Filter Change Flow

```text
User changes a filter (region / store / date)
    │
    ├── useFilterState updates URL search params (window.history.replaceState)
    │   and sessionStorage (for persistence across page navigations)
    │
    └── React Query detects queryKey change → triggers 5 parallel fetches
         │
         ├── fetch /api/v1/dashboard/kpis/?region=X&from=Y&to=Z
         ├── fetch /api/v1/dashboard/sentiment-distribution/?region=X&from=Y&to=Z
         ├── fetch /api/v1/dashboard/top-performing/?from=Y&to=Z      (date only)
         ├── fetch /api/v1/dashboard/highlights/?from=Y&to=Z          (date only)
         └── fetch /api/v1/dashboard/your-store/?from=Y&to=Z          (if single-shop user)
              │
              └── DashboardApiView.get()
                   ├── validate_filter_params() — 400 / 403 on bad input
                   ├── dashboard_cache_key() → cache.get()
                   │    ├── HIT → return cached Response immediately (no DB query)
                   │    └── MISS → call selector → single DB aggregate → cache.set(ttl=300) → return
                   └── selector calls _base_qs() → .aggregate() → single DB query
```

### Filter State Architecture

```text
URL search params (source of truth, shareable URLs)
    ↕  read on mount, write on change
sessionStorage (persistence across same-tab navigations)

useFilterState hook
    ├── reads from URL on mount
    ├── updates URL on change (replaceState — no browser history entry per keystroke)
    ├── syncs to sessionStorage on change
    └── exposes: filters, setRegion, setShop, setDateRange, clearFilters

DashboardWidget uses filters as React Query keys
    └── all 5 queries refetch automatically when filters change
```

### Cache Invalidation Policy

TTL-only — 5 minutes. No event-based invalidation. This is correct because:

- Review writes happen via Celery background sync, not user-triggered writes
- Adding cache invalidation hooks to the sync pipeline would couple `apps/reviews` to `apps/dashboard` — wrong dependency direction
- Dashboard aggregate staleness of 5 minutes is acceptable for this use case
- After sync completes, the TTL expires naturally and the next page load gets fresh data

---

## New Review Table Indexes

Three composite indexes must be added to `apps/reviews/migrations/` as a standalone migration.

```python
# Additions to Review.Meta.indexes in the new migration:

models.Index(
    fields=["organisation", "review_create_time", "sentiment"],
    name="review_org_date_sentiment_idx",
),
models.Index(
    fields=["shop", "review_create_time"],
    name="review_shop_date_idx",
),
models.Index(
    fields=["organisation", "review_create_time", "enrichment_status"],
    name="review_org_date_status_idx",
),
```

**Why these three:**

- `(organisation, review_create_time, sentiment)` — used by KPI negative count and sentiment distribution queries which always filter on `organisation_id`, optionally on date range, then aggregate by sentiment. Postgres index-only scan possible.
- `(shop, review_create_time)` — used by top-performing query which groups by `shop_id` within a date range. The existing `review_org_date_idx (organisation, review_create_time)` does not help here because this query's outer group is `shop_id`, not `organisation_id`.
- `(organisation, review_create_time, enrichment_status)` — used by sentiment coverage query counting enriched vs total within org + date range.

**Existing indexes preserved (do not drop):**

- `review_org_shop_filter_idx (organisation, shop, is_replied, star_rating)` — Reviews list view
- `review_org_date_idx (organisation, review_create_time)` — general org+date queries
- `review_search_vec_idx (search_vector GIN)` — full-text search

---

## Integration Points

### Backend Integration

| Boundary | Integration | Notes |
| -------- | ----------- | ----- |
| `apps/dashboard` → `apps/reviews` | Import `Review` model + `ReviewQuerySet.active()` | One-way dependency; `apps/reviews` must not import from `apps/dashboard` |
| `apps/dashboard` → `apps/reviews.selectors` | Reuse `get_accessible_shop_ids()` from `apps/reviews/selectors/reviews.py` | Already tested; do not duplicate |
| `apps/dashboard` → `apps/shops` | Import `Shop` model inside `validate_filter_params()` for Org Admin shop resolution | Local import to avoid circular app load |
| `apps/dashboard` → `apps/regions` | Import `Region` model inside `validate_filter_params()` for region existence check | Local import |
| `apps/dashboard` → `apps/common` | Inherit `IsOrgScoped` permission; do NOT inherit `TenantScopedViewSet` | `TenantScopedViewSet` is for `ModelViewSet` with `get_queryset()`; dashboard views are `APIView` with no queryset |
| `apps/dashboard` → Django cache | Use `django.core.cache.cache` (Redis DB 0, `KEY_PREFIX="app"`) | No new Redis DB needed |
| `config/urls.py` | `path("api/v1/", include("apps.dashboard.urls"))` | Same pattern as `action_items_api_urls` and `notifications_api_urls` |
| `config/settings/base.py` | Add `"apps.dashboard"` to `INSTALLED_APPS` after `apps.reviews` | Standard app registration |

### Frontend Integration

| Boundary | Integration | Notes |
| -------- | ----------- | ----- |
| New `dashboard.tsx` entrypoint | Add to `vite.config.ts` `rollupOptions.input` | Same pattern as all other 9 existing entrypoints |
| Django dashboard template | `<div id="dashboard-root">` + `{% vite_asset 'dashboard' %}` | Bootstrap data (regions, shops) passed via `<script type="application/json">` tags — same pattern `ReviewManagementWidget` uses via `readJsonScript()` |
| React Query | New npm dependency `@tanstack/react-query` | Not in current `package.json`; must be added |
| Filter state URL sync | `window.history.replaceState` + `URLSearchParams` | No router library; consistent with existing no-router pattern |
| `accessible_shop_ids` | NOT passed from template; resolved server-side in `validate_filter_params()` | Intentional — client never receives the accessible list |
| Single-shop Staff variant | Django template view detects `accessible_shop_ids` length == 1 and passes `data-is-single-shop="true"` to `#dashboard-root` | React island renders `YourStoreCard` instead of `PerformanceHighlightsCard` |

### Permission Model

Dashboard views use `IsOrgScoped` directly (not `TenantScopedViewSet`). Confirmed from codebase:

- `IsOrgScoped.has_permission()` checks `ORG_ADMIN or STAFF_ADMIN` role with valid `organisation_id` — this is the correct gate
- `TenantScopedViewSet.get_queryset()` operates on `qs.filter(organisation_id=org_id)` which requires a `queryset` class attribute — dashboard views have no such queryset
- Additional Staff scoping (accessible_shop_ids) happens inside `validate_filter_params()`

---

## Build Order

Dependencies between backend and frontend components determine this sequence:

1. **Indexes migration** (`apps/reviews/migrations/000N_dashboard_indexes.py`) — no code dependencies; add first so queries use indexes from day one of testing
2. **`apps/dashboard/` backend** in this order:
   - `filters.py` (no model imports at module level; local imports only inside functions)
   - `selectors/aggregations.py` (imports Review model)
   - `services/cache.py` (imports from filters.py)
   - `views.py` (imports all of the above)
   - `urls.py` + wire into `config/urls.py` + add to `INSTALLED_APPS`
3. **Tests for `filters.py` and `aggregations.py`** — query count assertions here; validates correctness before wiring the frontend
4. **Django dashboard template view** (renders the shell; mounts `#dashboard-root`; passes bootstrap JSON)
5. **Frontend**:
   - `npm install @tanstack/react-query` — add dependency
   - `api.ts` + `types.ts` (fetch wrappers, TypeScript types)
   - `useFilterState.ts` (URL + sessionStorage sync)
   - Individual query hooks (`useKpis.ts`, `useSentiment.ts`, `useTopPerforming.ts`, `useHighlights.ts`)
   - Widget components (`KpiCards.tsx`, `SentimentDonut.tsx`, `TopPerformingSection.tsx`, `FilterBar.tsx`)
   - `DashboardWidget.tsx` (root component, `QueryClient`)
   - `dashboard.tsx` entrypoint + `vite.config.ts` entry
6. **`CaptureQueriesContext` tests** on all 5 endpoints — target: 3 queries per endpoint (1 shop resolution, 1 aggregate, cache is mocked/bypassed in tests)

---

## Scaling Considerations

| Scale | Architecture Adjustments |
| ----- | ------------------------ |
| Current (< 1K reviews/org) | No changes needed; single aggregate query well under 10ms |
| 10K reviews/org | 3 new composite indexes handle this cleanly |
| 100K+ reviews/org | Increase `DASHBOARD_CACHE_TTL` to 15 min via settings; consider Postgres materialized view for top-performing |
| Concurrent users during peak | Redis TTL cache absorbs thundering herd; worst case is one DB query per 5-minute window per user+filter combination |

---

## Anti-Patterns

### Anti-Pattern 1: Using `TenantScopedViewSet` for Dashboard Views

**What people do:** Inherit `TenantScopedViewSet` because all other org admin views do.

**Why it's wrong:** `TenantScopedViewSet.get_queryset()` works only when there is a `queryset` model on the viewset. Dashboard views aggregate across a queryset — they are `APIView`, not `ModelViewSet`. Inheriting would require setting `queryset = Review.objects.none()` which is misleading and fragile.

**Do this instead:** Use `APIView` + `IsOrgScoped` permission directly. Put scoping logic in `validate_filter_params()`.

### Anti-Pattern 2: Separate `QueryClient` Per Widget

**What people do:** Create a `QueryClient` inside each widget hook or component.

**Why it's wrong:** Separate clients cannot share cache entries, so parallel queries that happen to request the same data get duplicated. Also prevents global loading/error coordination.

**Do this instead:** Instantiate one `QueryClient` at the `DashboardWidget` root and wrap with `QueryClientProvider`.

### Anti-Pattern 3: Passing `accessible_shop_ids` to the Frontend

**What people do:** Serialize the Staff user's accessible shop list into the template or API response so the frontend can filter results.

**Why it's wrong:** Leaks the user's exact access scope to the client. A Staff user could infer which shop IDs they cannot access. Also makes the frontend responsible for enforcing a security boundary.

**Do this instead:** Resolve `accessible_shop_ids` server-side in `validate_filter_params()`, embed it in the cache key via `filter_hash()`, and never expose it in API responses.

### Anti-Pattern 4: Python-Side Aggregation

**What people do:** Fetch all matching `Review` rows, then compute counts/averages with `len()`, `sum()`, `statistics.mean()` in Python.

**Why it's wrong:** Loads potentially thousands of rows from Postgres into Python memory. Violates the no-N+1 policy. P95 < 400ms constraint would be breached.

**Do this instead:** Push all aggregation to the database with `.aggregate()` and conditional `Count(..., filter=Q(...))`. One query per endpoint.

### Anti-Pattern 5: Event-Based Cache Invalidation for Dashboard

**What people do:** Emit a signal or Celery task on every `Review` create/update to invalidate dashboard cache keys for the relevant org.

**Why it's wrong:** Reviews are created by background Celery sync — potentially thousands at once during initial backfill. Each create would trigger cache invalidation, flooding Redis. The cache key includes `user_id` and `filter_hash`, so there is no stable wildcard pattern without a Redis SCAN — expensive under load.

**Do this instead:** TTL-only invalidation. 5 minutes of staleness during active sync is acceptable. After sync completes, TTL expires naturally.

### Anti-Pattern 6: Using Django FilterSet for Dashboard Params

**What people do:** Define a `DashboardFilterSet(django_filters.FilterSet)` wired to the `Review` model, same as `ReviewFilterSet`.

**Why it's wrong:** `ReviewFilterSet` filters rows for a list view. Dashboard endpoints aggregate — they do not return a filtered queryset. FilterSet is designed for queryset filtering + DRF integration; it cannot express the "resolve accessible_shop_ids for cache key" logic or the 365-day range check.

**Do this instead:** Plain dataclass + validation function as shown in Pattern 2. Simpler, testable without a request object.

---

## Sources

- Direct codebase inspection: `apps/common/viewsets.py`, `apps/common/permissions.py`, `apps/reviews/models.py`, `apps/reviews/views.py`, `apps/reviews/selectors/reviews.py`, `apps/reviews/filters.py`, `apps/reviews/managers.py`, `config/settings/base.py`, `config/urls.py`, `frontend/vite.config.ts`, `frontend/package.json`, `frontend/src/entrypoints/` (all 9), `frontend/src/widgets/review-management/` (all), `frontend/src/widgets/action-items/useActionItems.ts`
- Existing confirmed patterns: `IsOrgScoped` + `TenantScopedViewSet` separation; `get_accessible_shop_ids()` selector; `cache` default Redis DB 0; `KEY_PREFIX="app"`; `readJsonScript()` for template bootstrap data; `APIView` for non-CRUD endpoints (`/api/v1/reviews/stats/` uses a ViewSet action, but notifications and action-item list use `APIView`)
- Django ORM conditional aggregation: <https://docs.djangoproject.com/en/5.2/topics/db/aggregation/#conditional-aggregation>
- React Query parallel queries: <https://tanstack.com/query/latest/docs/framework/react/guides/parallel-queries>

---

*Architecture research for: Organisation Admin Dashboard — v0.4*
*Researched: 2026-05-07*
