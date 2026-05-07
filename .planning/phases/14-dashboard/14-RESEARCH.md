# Phase 14: Dashboard — Research

**Researched:** 2026-05-07
**Domain:** Django aggregation API + React island (recharts + @tanstack/react-query) + Redis TTL caching
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Date Picker — Custom Range**
- Custom range shows an inline panel that drops below the Date Range dropdown
- Panel contains two HTML `<input type="date">` inputs (From, To) styled with Tailwind — no date picker library
- An Apply button inside the panel triggers the fetch; prevents partial-state API calls (e.g. From filled but To empty)
- Panel closes on Apply, on clicking away, or on switching to a preset (7d/30d/90d)
- Validation (from > to, range > 365 days) fires on Apply, shown as an inline error below the inputs — not a toast

**404 / 500 Error Pages**
- Standalone full-page layout — no sidebar, no topbar, no shell template dependency
- Branded: platform logo (`logo/main_logo.png`), yellow/black palette, centered content on a white/light background
- Same template structure for both pages; only the code, title, and message differ:
  - 404: "404 — Page Not Found" + brief explanation + navigation button
  - 500: "500 — Something went wrong" + brief explanation + navigation button
- Navigation button logic: authenticated user → Dashboard (`/admin/org/dashboard/`), unauthenticated → Login (`/accounts/login/`)
- Wired via Django's `handler404` and `handler500` in `config/urls.py`; templates at `templates/404.html` and `templates/500.html`

**Widget Island Structure**
- Single React island: one `#dashboard-root` div in the Django template
- The island owns the React Query `QueryClientProvider`, filter state, and renders all 5 widgets
- Filter state flows down as props to each widget — no cross-island communication
- Widget directory: `frontend/src/widgets/dashboard/` following the established `api.ts` + `types.ts` + `useXxx.ts` + component files pattern
- Entrypoint: `frontend/src/entrypoints/dashboard.tsx` (consistent with existing entrypoint naming)

**Bootstrap Data**
- Django injects regions list + accessible shops list via `<script type="application/json">` in the template
- This allows the filter bar (dropdowns) to render immediately without a loading state
- All 5 widget datasets are fetched via React Query on mount — they are NOT pre-rendered server-side
- Pattern: consistent with the Reviews page bootstrap approach

**Bar Chart Click Navigation**
- Clicking a bar navigates in the same tab via `window.location.href`
- Always resolve to absolute ISO dates, even for presets:
  - "Last 30 days" → compute `from=YYYY-MM-DD` and `to=YYYY-MM-DD` at click time
  - Custom range → pass the already-absolute from/to values
- URL format: `/admin/org/reviews/?store={shop_id}&from={YYYY-MM-DD}&to={YYYY-MM-DD}`
- The Reviews page filter bar already accepts `?store` and date params; no Reviews page changes needed

### Claude's Discretion
- Loading skeleton design for KPI cards and chart areas
- Exact Tailwind spacing and typography within the established design system tokens
- Transition/animation timing for filter panel open/close
- How to handle the `accessible_shop_ids` empty-list edge case for Org Admins in the bootstrap payload
- Whether `sessionStorage` or a React ref holds the persisted filter state across route changes

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within Phase 14 scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FILT-01 | Region filter (All Regions default; accessible shops only) | `validate_filter_params()` resolves `accessible_shop_ids`; bootstrap data feeds dropdown |
| FILT-02 | Store filter cascades from selected region | Client-side cascade from bootstrap data; no extra API call needed |
| FILT-03 | Date Range presets: 7d / 30d (default) / 90d / Custom | `useFilterState.ts` computes absolute ISO date pairs from preset names |
| FILT-04 | Custom date range with inline date pickers and client-side validation | HTML `<input type="date">` + Apply button; client validates before fetch |
| FILT-05 | Clear Filters button (enabled when at least one filter differs from default) | State comparison in `useFilterState.ts` |
| FILT-06 | Filter state reflected in URL query params via `history.replaceState` | `URLSearchParams` + `replaceState` — no library needed |
| FILT-07 | Filter state persists within session; URL params take precedence | `sessionStorage` read on mount; URL params parsed first |
| FILT-08 | Out-of-scope region/store IDs in URL params return 403 | `validate_filter_params()` raises `PermissionDenied`; frontend clears filter on 403 |
| FILT-09 | Custom date range >365 days returns 400 | `validate_filter_params()` raises `ValidationError` |
| FILT-10 | Custom range with from > to returns 400 | `validate_filter_params()` raises `ValidationError` |
| TOP-01 | Multi-shop users see bar chart scoped to date range only (not region/store) | `dashboard_top_performing()` builds its own base qs without region/shop filters; frontend passes `dateOnlyFilters` |
| TOP-02 | Bar chart shows ≤10 shops or Top 5 + Worst 5 with gap when >10; min 3 reviews | HAVING clause via `.filter(review_count__gte=3)` after `.annotate()`; frontend renders separator cell |
| TOP-03 | Threshold bar coloring: green ≥4.0, amber 3.0–3.99, red <3.0 | recharts `<Cell fill={barColor(rating)}>` per-bar fill |
| TOP-04 | Hover tooltip: shop name, avg rating, review count | recharts custom `<Tooltip>` content component |
| TOP-05 | Bar click navigates to Reviews page with shop + date params | `onClick` → `window.location.href`; absolute ISO dates always used |
| TOP-06 | Performance Highlights card: highest/lowest shop with AI-derived counts | `dashboard_highlights()` selector; requires enrichment_status=SUCCESS |
| TOP-07 | Combined empty state when no shops qualify; "View last 90 days" CTA | Conditional render in React when `top_performing` response is empty list |
| STORE-01 | Single-shop users see "Your Store" card instead of bar chart | Django template sets `data-is-single-shop`; React conditionally renders `YourStore.tsx` |
| STORE-02 | "Your Store" card shows all KPIs + 5-star distribution mini-bars | `dashboard_your_store()` selector returns all required aggregates in one query |
| STORE-03 | "Your Store" shows trend vs previous equivalent period | Selector computes previous window and calculates delta |
| KPI-01 | Total Reviews card with region+store+date filter | `dashboard_kpis()` uses `_base_qs()` which applies all filters |
| KPI-02 | Avg Rating to 1 decimal with half-star display at .25–.74 | Python `round(float, 1)`; React renders `StarHalf` icon at midpoint |
| KPI-03 | Negative Reviews counts AI-derived sentiment=NEGATIVE + enrichment_status=SUCCESS | Conditional `Count()` with `Q(sentiment="negative", enrichment_status=SUCCESS)` |
| KPI-04 | Negative Reviews % uses enriched reviews as denominator | Two counts in one `aggregate()` call; division in Python before returning |
| KPI-05 | Each KPI card has independent loading skeleton, empty state, and error state | React Query per-query `isLoading`/`isError`; each card renders its own skeleton/error |
| SENT-01 | Donut chart from enriched reviews only (enrichment_status=SUCCESS) | Conditional Count in `dashboard_sentiment_distribution()` |
| SENT-02 | Sentiment summary: count, percentage, color-coded progress bar | recharts-free HTML rendering beside donut; hardcoded hex fills |
| SENT-03 | Hover tooltip on donut segment: sentiment, count, percentage | recharts custom `<Tooltip>` on `<Pie>` |
| SENT-04 | Coverage footer when enrichment < 100% | `coverage_pct` from selector; conditional render in React |
| SENT-05 | Coverage footer adds spinner when coverage < 50% | Threshold check on `coverage_pct < 50` in React |
| SENT-06 | Empty states: no reviews / none enriched yet | Two distinct empty state branches based on `total_count` vs `enriched_count` |
| TECH-01 | New `apps/dashboard/` app with aggregation selectors, cache service, and views | New Django app; 5 pure-read `APIView` endpoints |
| TECH-02 | Redis 5-min TTL; cache key includes `accessible_shop_ids` hash | `dashboard_cache_key()` in `services/cache.py`; `filter_hash()` on dataclass |
| TECH-03 | Migration adds 3 composite indexes to Review table | New migration in `apps/reviews/migrations/`; next number is 0006 |
| TECH-04 | All 5 endpoints have `CaptureQueriesContext` query-count tests | `test_views.py` + `test_aggregations.py` in `apps/dashboard/tests/` |
| TECH-05 | Dashboard page at `/admin/org/dashboard/` replaces Phase 2 placeholder | Modify `org_admin_dashboard` view in `apps/organisations/views.py` OR move to new `apps/dashboard/views.py` page view |
| TECH-06 | All 5 widgets load in parallel via parallel API calls | `QueryClient` with 5 parallel `useQuery` hooks; all fire on mount |
| ERR-01 | Branded 404 page via Django `handler404` | `templates/404.html` + `handler404 = "apps.common.views.handler404"` in `config/urls.py` |
| ERR-02 | Branded 500 page via Django `handler500` | `templates/500.html` + `handler500 = "apps.common.views.handler500"` in `config/urls.py` |
</phase_requirements>

---

## Summary

Phase 14 replaces the existing dashboard placeholder at `/admin/org/dashboard/` with a full analytics page. The implementation is a clean layer cake: a new `apps/dashboard/` Django app providing five pure-read `APIView` endpoints backed by single-query ORM aggregations, Redis TTL caching with scope-aware keys, and three new composite indexes on the `Review` table — consumed by a single React island that runs five parallel React Query fetches and renders filter bar, KPI cards, sentiment donut, bar chart, and highlights components.

All foundational decisions are locked: recharts 3.8.1 (React 19 verified) for charts, @tanstack/react-query v5 (React 19 verified) for parallel fetching, `DashboardFilterParams` frozen dataclass for validation, `IsOrgScoped` permission directly on `APIView`, TTL-only cache invalidation, and `history.replaceState` for URL filter state. The prior research (SUMMARY.md, ARCHITECTURE.md) is thorough and codebase-verified — this phase does not re-research those conclusions.

The critical build constraint is ordering: indexes before selectors (query plans are verifiable immediately), `filters.py` before `views.py` (security is the foundation), backend fully wired before frontend binds to it. The most dangerous bug is the cache scoping failure (DASH-C1): if `accessible_shop_ids` is omitted from the cache key hash, Staff Admin A's data is served to Staff Admin B. This must be implemented in the very first utility function written.

**Primary recommendation:** Build in the exact 8-plan order already decomposed (indexes+foundation → selectors → views → template → filter bar → charts → KPI+donut → root+entrypoint+errors). Each plan has a self-contained test gate before the next plan begins.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django 6.0.x | (pinned) | Backend framework | Already in use |
| DRF | (pinned) | `APIView` for 5 read-only endpoints | Already in use |
| django-redis | (pinned) | Redis cache backend (DB 0) | Already in use; `KEY_PREFIX="app"` |
| React 19.2.5 | 19.2.5 | UI island | Already in use |
| TypeScript 5.7.2 | 5.7.2 | Type safety | Already in use |
| Tailwind CSS v4 | 4.2.4 | Styling | Already in use |
| lucide-react | 1.8.0 | Icons | Already in use |
| recharts | 3.8.1 | Bar chart + donut chart | React 19 peer dep verified; single pkg covers both chart types |
| @tanstack/react-query | 5.100.9 | Parallel fetching + per-query loading states | v5 React 19 compatible; declarative refetch on filter key change |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `URLSearchParams` + `history.replaceState` | (browser built-in) | URL filter state sync | No library needed; replaceState over pushState prevents history pollution |
| `sessionStorage` | (browser built-in) | Filter state persistence across same-tab navigation | Fallback when URL params absent on mount |
| `hashlib` + `json` | (Python stdlib) | SHA-256 cache key filter hash | `DashboardFilterParams.filter_hash()` — includes `accessible_shop_ids` |
| `dataclasses.dataclass(frozen=True)` | (Python stdlib) | `DashboardFilterParams` validated params container | Immutable; testable without a request object |

### Alternatives Considered (and rejected)

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| recharts | chart.js / react-chartjs-2 | react-chartjs-2 is NOT React 19 compatible (open issue); recharts is |
| recharts | @nivo/* | Nivo requires `--legacy-peer-deps` for React 19 (open issue #2618); recharts does not |
| @tanstack/react-query | vanilla useEffect + fetch | ~150 lines of boilerplate per hook; no declarative refetch; no per-query loading states |
| DashboardFilterParams (dataclass) | Django FilterSet | FilterSet designed for queryset filtering — cannot express scope resolution or 365d range check |
| IsOrgScoped + APIView | TenantScopedViewSet | TenantScopedViewSet.get_queryset() requires a queryset class attribute — dashboard views have none |
| TTL-only cache invalidation | Event-based cache invalidation | Review writes happen in Celery background sync (potentially thousands at once); event-based invalidation under bulk sync would flood Redis |

**Installation (new packages only — not yet in package.json):**

```bash
cd frontend
npm install recharts@3.8.1 @tanstack/react-query@5.100.9
```

**Version verification (performed 2026-05-07):**
- `recharts`: `npm view recharts version` → `3.8.1` (confirmed current)
- `@tanstack/react-query`: `npm view @tanstack/react-query version` → `5.100.9` (confirmed current)

---

## Architecture Patterns

### Recommended Project Structure

```
apps/dashboard/
├── __init__.py
├── apps.py
├── urls.py                  # urlpatterns for 5 endpoints + dashboard page
├── filters.py               # DashboardFilterParams (frozen dataclass) + validate_filter_params()
├── views.py                 # DashboardApiView base + 5 concrete API views
│                            # + DashboardPageView (Django TemplateView)
├── selectors/
│   ├── __init__.py
│   └── aggregations.py      # dashboard_kpis(), dashboard_sentiment_distribution(),
│                            # dashboard_top_performing(), dashboard_highlights(),
│                            # dashboard_your_store()
├── services/
│   ├── __init__.py
│   └── cache.py             # dashboard_cache_key(), cache_get(), cache_set()
└── tests/
    ├── __init__.py
    ├── factories.py          # Thin wrappers; reuse ReviewFactory from apps/reviews/tests/
    ├── test_filters.py       # validate_filter_params() — 403/400/happy-path branches
    ├── test_aggregations.py  # ORM correctness + CaptureQueriesContext per selector
    └── test_views.py         # HTTP 200/400/403/cache-hit per endpoint

apps/reviews/migrations/
└── 0006_dashboard_indexes.py  # 3 new composite indexes (next migration is 0006)

frontend/src/widgets/dashboard/
├── DashboardWidget.tsx       # React root; QueryClientProvider; renders all sections
├── FilterBar.tsx             # Region + Store dropdowns + date range + clear
├── TopPerformingSection.tsx  # Bar chart + highlights card
├── PerformanceHighlights.tsx # Top/bottom performer sub-cards
├── YourStore.tsx             # Single-shop variant card
├── KpiCards.tsx              # 3 KPI cards with independent loading/error states
├── SentimentDonut.tsx        # Donut + legend + coverage footer
├── api.ts                   # Fetch wrappers for all 5 endpoints
├── types.ts                 # TypeScript response types
├── useFilterState.ts         # URL + sessionStorage sync
├── useKpis.ts               # useQuery hook → /api/v1/dashboard/kpis/
├── useSentiment.ts          # useQuery hook → /api/v1/dashboard/sentiment-distribution/
├── useTopPerforming.ts       # useQuery hook → /api/v1/dashboard/top-performing/
└── useHighlights.ts          # useQuery hook → /api/v1/dashboard/highlights/

frontend/src/entrypoints/
└── dashboard.tsx            # Mounts DashboardWidget on #dashboard-root

templates/
├── 404.html                 # Standalone branded 404
└── 500.html                 # Standalone branded 500
```

### Pattern 1: DashboardApiView Base Class

**What:** All 5 API endpoints inherit a common base that handles filter validation, cache lookup, and cache write. Subclasses implement only `_fetch()`.

**When to use:** 5+ endpoints with identical validation/caching logic. Prevents copy-paste divergence.

```python
# apps/dashboard/views.py
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from apps.common.permissions import IsOrgScoped
from apps.dashboard.filters import validate_filter_params, DashboardFilterParams
from apps.dashboard.services.cache import dashboard_cache_key, cache_get, cache_set

DASHBOARD_TTL = 300  # 5 minutes

class DashboardApiView(APIView):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    endpoint_name: str = ""  # must be set by subclass

    def get(self, request: Request) -> Response:
        user = request.user
        org_id: int = user.organisation_id
        params: DashboardFilterParams = validate_filter_params(
            request=request, user=user, org_id=org_id,
        )
        key = dashboard_cache_key(
            endpoint=self.endpoint_name, org_id=org_id,
            user_id=user.pk, params=params,
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

### Pattern 2: DashboardFilterParams Frozen Dataclass

**What:** A frozen dataclass holds validated params including the resolved `accessible_shop_ids` tuple. `validate_filter_params()` is the single security gate.

**Critical detail:** `filter_hash()` MUST include `accessible_shop_ids` — this is what prevents cross-user cache leakage for Staff Admins with different shop scopes.

```python
# apps/dashboard/filters.py
import hashlib, json
from dataclasses import dataclass
from datetime import date
from rest_framework.exceptions import PermissionDenied, ValidationError

@dataclass(frozen=True)
class DashboardFilterParams:
    region_id: int | None
    shop_id: int | None
    date_from: date | None
    date_to: date | None
    accessible_shop_ids: tuple[int, ...]  # always populated; used in cache key

    def filter_hash(self) -> str:
        payload = {
            "region_id": self.region_id,
            "shop_id": self.shop_id,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "shop_ids": list(self.accessible_shop_ids),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
```

### Pattern 3: Single-Query ORM Aggregation (No Python-side aggregation)

**What:** All `aggregate()` and conditional `Count()` calls push aggregation to the database. One DB query per endpoint.

```python
# apps/dashboard/selectors/aggregations.py
from django.db.models import Avg, Count, Q
from apps.reviews.models import Review

def _base_qs(org_id: int, params: DashboardFilterParams):
    """Applies org, shop-scope, and full filters (region + shop + date)."""
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
    """One aggregate() call. Query count: 1."""
    agg = _base_qs(org_id, params).aggregate(
        total_reviews=Count("pk"),
        avg_rating=Avg("star_rating"),
        negative_count=Count(
            "pk",
            filter=Q(sentiment="negative", enrichment_status=Review.EnrichmentStatus.SUCCESS),
        ),
        enriched_count=Count(
            "pk",
            filter=Q(enrichment_status=Review.EnrichmentStatus.SUCCESS),
        ),
    )
    total = agg["total_reviews"] or 0
    enriched = agg["enriched_count"] or 0
    negative = agg["negative_count"] or 0
    neg_pct = round(negative / enriched * 100, 1) if enriched > 0 else 0.0
    return {
        "total_reviews": total,
        "avg_rating": round(float(agg["avg_rating"] or 0.0), 1),
        "negative_reviews": negative,
        "negative_pct": neg_pct,
        "store_count": len(params.accessible_shop_ids),
    }
```

**Top-performing uses date-range only (not full filters):**

```python
def dashboard_top_performing(*, org_id: int, params: DashboardFilterParams) -> dict:
    """DOES NOT apply region_id or shop_id filters — date range only per spec (TOP-01)."""
    qs = (
        Review.objects.active()
        .filter(organisation_id=org_id)
        .filter(shop_id__in=params.accessible_shop_ids)
    )
    if params.date_from:
        qs = qs.filter(review_create_time__date__gte=params.date_from)
    if params.date_to:
        qs = qs.filter(review_create_time__date__lte=params.date_to)

    # HAVING review_count >= 3 — enforced via filter() after annotate()
    all_rows = (
        qs.values("shop_id", "shop__name")
        .annotate(review_count=Count("pk"), avg_rating=Avg("star_rating"))
        .filter(review_count__gte=3)
        .order_by("-avg_rating", "-review_count")
    )
    shops = [
        {"shop_id": r["shop_id"], "shop_name": r["shop__name"],
         "review_count": r["review_count"], "avg_rating": round(float(r["avg_rating"]), 2)}
        for r in all_rows
    ]
    # TOP-02: if > 10 shops, return top 5 and worst 5
    if len(shops) > 10:
        return {"shops": shops[:5] + shops[-5:], "split": True}
    return {"shops": shops, "split": False}
```

### Pattern 4: React Query Parallel Fetching (two filter objects)

**What:** One `QueryClient` at the React root. Five parallel `useQuery` hooks. Two distinct filter objects: `fullFilters` for KPI+Sentiment, `dateOnlyFilters` for TopPerforming+Highlights — prevents DASH-C2 (applying region/store to bar chart).

```typescript
// frontend/src/widgets/dashboard/DashboardWidget.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useFilterState } from "./useFilterState";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: 1 } },
});

export function DashboardWidget() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardInner />
    </QueryClientProvider>
  );
}

function DashboardInner() {
  const { filters, ...filterActions } = useFilterState();

  // Two filter objects — CRITICAL for DASH-C2 prevention
  const fullFilters = filters;  // region + shop + date
  const dateOnlyFilters = { date_from: filters.date_from, date_to: filters.date_to };

  // 5 queries fire in parallel; each re-fetches automatically when their key changes
  const kpisQuery = useQuery({ queryKey: ["dashboard", "kpis", fullFilters], queryFn: () => fetchKpis(fullFilters) });
  const sentimentQuery = useQuery({ queryKey: ["dashboard", "sentiment", fullFilters], queryFn: () => fetchSentiment(fullFilters) });
  const topQuery = useQuery({ queryKey: ["dashboard", "top-performing", dateOnlyFilters], queryFn: () => fetchTopPerforming(dateOnlyFilters) });
  const highlightsQuery = useQuery({ queryKey: ["dashboard", "highlights", dateOnlyFilters], queryFn: () => fetchHighlights(dateOnlyFilters) });
  // yourStoreQuery only used when isSingleShop — date range only
  // ...render sections
}
```

### Pattern 5: Bootstrap Data via json_script Tag

**What:** Django template renders regions list and accessible shops list as JSON tags. React reads them synchronously on mount — no loading state for dropdowns.

Django template side:
```html
{{ regions_json|json_script:"dashboard-regions" }}
{{ shops_json|json_script:"dashboard-shops" }}
<div id="dashboard-root" data-is-single-shop="{{ is_single_shop|yesno:'true,false' }}"></div>
```

React side (in `DashboardWidget.tsx` or `dashboard.tsx` entrypoint):
```typescript
const regions = JSON.parse(document.getElementById("dashboard-regions")!.textContent ?? "[]");
const shops = JSON.parse(document.getElementById("dashboard-shops")!.textContent ?? "[]");
const isSingleShop = document.getElementById("dashboard-root")!.dataset.isSingleShop === "true";
```

### Pattern 6: Cache Key with accessible_shop_ids Hash

```python
# apps/dashboard/services/cache.py
from django.core.cache import cache
from apps.dashboard.filters import DashboardFilterParams

def dashboard_cache_key(*, endpoint: str, org_id: int, user_id: int, params: DashboardFilterParams) -> str:
    # KEY_PREFIX="app" is added by django-redis; key stored as "app:dashboard:..."
    return f"dashboard:{endpoint}:{org_id}:{user_id}:{params.filter_hash()}"

def cache_get(key: str) -> dict | None:
    return cache.get(key)

def cache_set(key: str, data: dict, *, ttl: int) -> None:
    cache.set(key, data, timeout=ttl)
```

### Pattern 7: URL Filter State (replaceState + sessionStorage)

```typescript
// frontend/src/widgets/dashboard/useFilterState.ts
// replaceState: does not add browser history entry on each filter change
// sessionStorage: survives same-tab navigation

export function useFilterState() {
  const [filters, setFilters] = useState<DashboardFilters>(() => {
    const url = new URLSearchParams(window.location.search);
    // URL params take precedence over sessionStorage (FILT-07)
    if (url.has("region") || url.has("store") || url.has("range")) {
      return parseFromUrl(url);
    }
    const stored = sessionStorage.getItem("dashboard-filters");
    return stored ? JSON.parse(stored) : DEFAULT_FILTERS;
  });

  const updateFilters = useCallback((next: DashboardFilters) => {
    setFilters(next);
    const url = new URLSearchParams();
    if (next.region_id) url.set("region", String(next.region_id));
    if (next.shop_id) url.set("store", String(next.shop_id));
    // ... other params
    window.history.replaceState({}, "", `?${url.toString()}`);
    sessionStorage.setItem("dashboard-filters", JSON.stringify(next));
  }, []);

  return { filters, updateFilters, /* setRegion, setShop, setDateRange, clearFilters */ };
}
```

### Pattern 8: Django Error Handler Views

Django's `handler404` and `handler500` must be set as module-level string paths in `config/urls.py`:

```python
# config/urls.py
handler404 = "apps.common.views.page_not_found"
handler500 = "apps.common.views.server_error"
```

```python
# apps/common/views.py
def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)

def server_error(request):
    return render(request, "500.html", status=500)
```

**Critical:** `handler500` view must not use `request.user` — the request may not have a session if the error is in middleware. Detect auth status via `{% if request.user.is_authenticated %}` in the template, which Django handles safely even during 500 rendering.

### Anti-Patterns to Avoid

- **Using TenantScopedViewSet for dashboard views:** Requires a `queryset` class attribute; dashboard views have none — use `APIView` + `IsOrgScoped` directly.
- **Separate QueryClient per widget:** Prevents cache sharing and coordinated refetch — one QueryClient at the root.
- **Python-side aggregation (len/sum/mean on fetched rows):** Loads all Review rows into Python memory; violates no-N+1 policy; breaks P95 < 400ms target.
- **Passing accessible_shop_ids to frontend:** Leaks scope to client; security boundary must be server-only.
- **Event-based cache invalidation for dashboard:** Reviews are created in bulk by Celery sync; event-based invalidation would flood Redis. TTL-only is correct.
- **Missing accessible_shop_ids in filter_hash():** Critical security bug — Staff Admin A's cache data served to Staff Admin B.
- **Using history.pushState instead of replaceState:** Each filter interaction adds a browser history entry; back button becomes unusable.
- **Applying region/store filter to top-performing endpoint:** Contradicts TOP-01; single-store selection would show one bar — useless chart.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SVG bar chart | Custom SVG paths | recharts `BarChart` + `ResponsiveContainer` | Tooltip, Cell, axis, responsive container — 50+ edge cases |
| SVG donut chart | Custom SVG `<circle>` with `stroke-dasharray` | recharts `PieChart` + `Pie` + `Cell` | Hover state, tooltip, arc gaps, start angle — non-trivial geometry |
| Parallel fetch with per-query loading states | useState + useEffect + useCallback × 5 | @tanstack/react-query `useQuery` | ~150 lines boilerplate per hook; no declarative refetch on key change |
| URL-driven filter state persistence | Custom URL parsing utility | URLSearchParams (browser built-in) | Already a stable API; no library needed for 5 params |
| Cache key hashing | Custom hash function | Python stdlib `hashlib.sha256` + `json.dumps(sort_keys=True)` | Deterministic, collision-resistant, no dependencies |
| Security scope enforcement | Per-view scope checks | `validate_filter_params()` centralised function | Single point of truth; testable without HTTP stack |

**Key insight:** The complexity in this phase lives almost entirely in the ORM aggregation layer and the React Query key design. Everything else is wiring established patterns. Resist the temptation to build custom chart primitives or custom data fetching — the libraries handle the hard parts.

---

## Common Pitfalls

### Pitfall 1: Cache key missing accessible_shop_ids (DASH-C1)
**What goes wrong:** Staff Admin A has shops [1, 2]; Staff Admin B has shops [3, 4]. Same org, same date filter → same cache key → B receives A's data.
**Why it happens:** Developer includes only `org_id + user_id + filter_params` but forgets that filter_params does not include the resolved shop scope.
**How to avoid:** `filter_hash()` on `DashboardFilterParams` MUST serialize `accessible_shop_ids` as part of the hash payload. The dataclass is the canonical location for this.
**Warning signs:** `test_filters.py` has a test asserting that two users in the same org with different shop scopes produce different `filter_hash()` values. If this test doesn't exist, the bug can exist silently.

### Pitfall 2: Top Performing applies full filter instead of date-only (DASH-C2)
**What goes wrong:** User selects "Store = Coffee Shop A" → bar chart shows only one bar (that store). The chart is useless and confusing.
**Why it happens:** `_base_qs()` is reused without overriding. Top-performing builds its own base queryset ignoring `region_id` and `shop_id`.
**How to avoid:** `dashboard_top_performing()` builds its own queryset, NOT via `_base_qs()`. React passes `dateOnlyFilters` (not `fullFilters`) as the query key.
**Warning signs:** `test_aggregations.py` has a test calling `dashboard_top_performing()` with `shop_id=1` and asserting all shops in the org are returned (not just shop 1).

### Pitfall 3: Out-of-scope URL params silently fall back to defaults (DASH-C3)
**What goes wrong:** Staff user with `?region=99` (not their org) sees unfiltered org data without knowing the filter was ignored.
**Why it happens:** Defensive fallback logic that catches errors and silently resets the filter.
**How to avoid:** `validate_filter_params()` raises `PermissionDenied` (403) for any region or shop outside user scope. Frontend handles 403 by clearing the offending filter and showing "You don't have access to the selected Region/Store. Filter has been cleared."
**Warning signs:** `test_filters.py` has a test asserting `PermissionDenied` is raised when `shop_id` is not in `accessible_shop_ids`.

### Pitfall 4: Composite index field order mismatches query shape (DASH-C5)
**What goes wrong:** Index is added as `(organisation, sentiment, review_create_time)` but the query filters on `organisation_id` first, then date range, then aggregates by sentiment. Postgres uses the index only up to the first non-equality field — sentinel order matters.
**Why it happens:** Index field order is chosen intuitively rather than from `EXPLAIN ANALYZE`.
**How to avoid:** The correct field order is `(organisation_id, review_create_time, sentiment)` — org is equality, date is range, sentiment is the aggregate target. Verify with `EXPLAIN ANALYZE` after seeding 5K rows.
**Warning signs:** `EXPLAIN ANALYZE` output shows `Seq Scan` on reviews table when filtering by org + date range with 10K+ rows.

### Pitfall 5: Timezone boundary mismatch silently drops reviews (DASH-C7)
**What goes wrong:** UTC "Last 30 days" = `today_utc - 30 days`. For a user in UTC+8 it's already tomorrow — their current day's reviews are excluded.
**Why it happens:** Date window computed at midnight UTC boundary without user timezone awareness.
**How to avoid:** This decision is locked — `User.timezone` is deferred; the mitigation is the "All dates in UTC" notice in the filter bar. The implementation must use `date.today()` in UTC (not the server's local timezone), and must display the UTC notice prominently.
**Warning signs:** The UTC notice string ("All dates in UTC") is missing from the filter bar render.

### Pitfall 6: Python-side aggregation (DASH-C4)
**What goes wrong:** `Review.objects.filter(...).count()` is called 4 separate times, or all rows are fetched and `len()` / `statistics.mean()` is called in Python.
**Why it happens:** Developer is more comfortable with Python loops than ORM `aggregate()`.
**How to avoid:** Single `aggregate()` call with multiple conditional `Count()` expressions using `Q()`. Enforced by `CaptureQueriesContext` tests asserting query count == 1.
**Warning signs:** `CaptureQueriesContext` test fails with query count > 1.

### Pitfall 7: handler500 using request.user (ERR-02)
**What goes wrong:** The 500 template or view crashes because the exception that triggered the 500 corrupted session middleware — `request.user` is unavailable.
**Why it happens:** Error page view calls `request.user.is_authenticated` in Python; middleware may not have run.
**How to avoid:** Push auth detection to the template via `{% if request.user.is_authenticated %}` — Django's template rendering handles this gracefully even in error contexts. The view itself must be minimal (just `render(request, "500.html", status=500)`).
**Warning signs:** Visiting a URL that triggers a 500 shows Django's default error page instead of the branded one.

### Pitfall 8: Migration number conflict
**What goes wrong:** New migration `0006_dashboard_indexes.py` conflicts with another migration created in the same session.
**Why it happens:** Both `apps/reviews/` and other apps may have recent migrations.
**How to avoid:** Confirm next migration number from `ls apps/reviews/migrations/` — current last is `0005_periodic_tasks_seed_retry_failed_enrichments.py`; next is `0006`. Run `python manage.py makemigrations --check` after creating the migration.

---

## Code Examples

### ORM Aggregation — Sentiment Distribution (1 query)

```python
# apps/dashboard/selectors/aggregations.py
def dashboard_sentiment_distribution(*, org_id: int, params: DashboardFilterParams) -> dict:
    agg = _base_qs(org_id, params).aggregate(
        total=Count("pk"),
        enriched=Count("pk", filter=Q(enrichment_status=Review.EnrichmentStatus.SUCCESS)),
        positive=Count("pk", filter=Q(sentiment="positive", enrichment_status=Review.EnrichmentStatus.SUCCESS)),
        neutral=Count("pk", filter=Q(sentiment="neutral", enrichment_status=Review.EnrichmentStatus.SUCCESS)),
        negative=Count("pk", filter=Q(sentiment="negative", enrichment_status=Review.EnrichmentStatus.SUCCESS)),
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
```

### CaptureQueriesContext Test Pattern

```python
# apps/dashboard/tests/test_aggregations.py
from django.test.utils import CaptureQueriesContext
from django.db import connection
from apps.dashboard.selectors.aggregations import dashboard_kpis
from apps.dashboard.filters import DashboardFilterParams

def test_dashboard_kpis_query_count(db, org, staff_user):
    """KPIs endpoint must never exceed 1 DB query regardless of review count."""
    params = DashboardFilterParams(
        region_id=None, shop_id=None,
        date_from=None, date_to=None,
        accessible_shop_ids=tuple(shop_ids_for_org(org)),
    )
    with CaptureQueriesContext(connection) as ctx:
        result = dashboard_kpis(org_id=org.pk, params=params)
    assert len(ctx.captured_queries) == 1, (
        f"Expected 1 query, got {len(ctx.captured_queries)}: {ctx.captured_queries}"
    )
    assert "total_reviews" in result
```

### React Query Hook Pattern

```typescript
// frontend/src/widgets/dashboard/useKpis.ts
import { useQuery } from "@tanstack/react-query";
import { fetchKpis } from "./api";
import type { DashboardFilters, KpisResponse } from "./types";

export function useKpis(filters: DashboardFilters) {
  return useQuery<KpisResponse>({
    queryKey: ["dashboard", "kpis", filters],
    queryFn: () => fetchKpis(filters),
    staleTime: 5 * 60 * 1000,  // matches server TTL
    retry: 1,
  });
}
```

### recharts BarChart with Per-Bar Cell Coloring

```typescript
// Inside TopPerformingSection.tsx
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

function barColor(rating: number): string {
  if (rating >= 4.0) return "#22C55E";  // green
  if (rating >= 3.0) return "#F59E0B";  // amber
  return "#EF4444";                       // red
}

<ResponsiveContainer width="100%" height={240}>
  <BarChart data={shops} role="img" aria-label="Best performing outlets bar chart">
    <XAxis dataKey="shop_name" tick={{ fontSize: 11 }} interval={0}
           tickFormatter={(name) => name.length > 16 ? name.slice(0, 16) + "…" : name} />
    <YAxis domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 11 }} />
    <Tooltip content={<CustomBarTooltip />} />
    <Bar dataKey="avg_rating" radius={[4, 4, 0, 0]} cursor="pointer"
         onClick={(data) => { window.location.href = buildReviewsUrl(data.shop_id, dateOnlyFilters); }}>
      {shops.map((shop) => (
        <Cell key={shop.shop_id} fill={barColor(shop.avg_rating)} />
      ))}
    </Bar>
  </BarChart>
</ResponsiveContainer>
```

### recharts PieChart Donut

```typescript
// Inside SentimentDonut.tsx
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = { positive: "#22C55E", neutral: "#F59E0B", negative: "#EF4444" };

<ResponsiveContainer width="100%" height={200}>
  <PieChart role="img" aria-label="Sentiment distribution donut chart">
    <Pie
      data={sentimentData}
      dataKey="value"
      innerRadius="55%"
      outerRadius="80%"
      paddingAngle={2}
      startAngle={90}
      endAngle={-270}
    >
      {sentimentData.map((entry) => (
        <Cell key={entry.name} fill={COLORS[entry.name as keyof typeof COLORS]} />
      ))}
    </Pie>
    <Tooltip content={<CustomDonutTooltip />} />
  </PieChart>
</ResponsiveContainer>
```

### Django template bootstrap data pattern

```html
{# templates/organisations/org_dashboard.html — replace existing placeholder #}
{% extends "base_org.html" %}
{% load static django_vite %}

{% block title %}Dashboard · Review Bee{% endblock %}

{% block content %}
  {{ regions_json|json_script:"dashboard-regions" }}
  {{ shops_json|json_script:"dashboard-shops" }}
  <div
    id="dashboard-root"
    data-is-single-shop="{{ is_single_shop|yesno:'true,false' }}"
  ></div>
{% endblock %}

{% block extra_js %}
  {% vite_asset 'src/entrypoints/dashboard.tsx' %}
{% endblock %}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| vanilla useEffect + fetch per widget | @tanstack/react-query v5 useQuery | Phase 14 | Declarative refetch on filter key change; per-query loading/error states; no boilerplate |
| chart.js / react-chartjs-2 | recharts | Phase 14 | React 19 compatibility; simpler Cell-level data binding |
| Simple `aggregate()` single field | Conditional `Count(filter=Q(...))` | Django 2.0+ pattern | Multi-metric aggregate in one DB round-trip |
| history.pushState for filter state | history.replaceState | Industry standard | Prevents browser history pollution from filter interactions |
| FilterSet for aggregation endpoints | Frozen dataclass + validation function | Phase 14 | Testable without DRF; captures security constraints cleanly |

**Deprecated/outdated in this context:**
- `react-chartjs-2`: not React 19 compatible — do not use
- `@nivo/*`: requires `--legacy-peer-deps` for React 19 — do not use
- Using `react-router-dom` for URL filter state in a non-SPA Django page — overkill; URLSearchParams is sufficient

---

## Open Questions

1. **DashboardPageView location — organisations app vs new dashboard app**
   - What we know: `org_admin_dashboard` view exists in `apps/organisations/views.py`; it currently renders the placeholder template
   - What's unclear: Should the refactored analytics view live in `apps/organisations/views.py` (minimal change, reuse existing login redirect) or move to `apps/dashboard/views.py` (cleaner app boundary)?
   - Recommendation: Keep the page view in `apps/organisations/views.py` for now (the URL `/admin/org/dashboard/` is already registered there and the login redirect is wired to it from Phase 6). The page view just needs to pass bootstrap data (regions JSON, shops JSON, is_single_shop) to the template. Moving it would require URL re-registration and risk breaking the login redirect.

2. **`your-store` vs `highlights` endpoint structure**
   - What we know: ARCHITECTURE.md shows `/your-store/` and `/highlights/` as separate endpoints; they are mutually exclusive (based on whether user has exactly 1 or multiple accessible shops)
   - What's unclear: Does the Django template view detect `is_single_shop` and pass it as a flag, or does the React island determine this dynamically from the bootstrap shops list?
   - Recommendation: Detect in the Django template view (`accessible_shop_ids` is resolved there for the bootstrap payload); pass `data-is-single-shop` on the root div. React reads it synchronously on mount — no loading state needed.

3. **HAVING clause threshold value**
   - What we know: `TOP-02` and `TOP-06` specify ≥3 reviews as the minimum for chart inclusion; STATE.md confirms "Minimum review threshold for Top Performers — requirements doc specifies ≥3 reviews (TOP-02, TOP-06); confirmed at 3."
   - What's unclear: Nothing — confirmed at 3.
   - Recommendation: Hardcode `.filter(review_count__gte=3)` as a named constant `MIN_REVIEWS_FOR_RANKING = 3` at the top of `aggregations.py`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `pytest apps/dashboard/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FILT-08 | out-of-scope region/store → 403 | unit | `pytest apps/dashboard/tests/test_filters.py::test_validate_out_of_scope_shop -x` | ❌ Wave 0 |
| FILT-09 | date range > 365d → 400 | unit | `pytest apps/dashboard/tests/test_filters.py::test_validate_range_too_long -x` | ❌ Wave 0 |
| FILT-10 | from > to → 400 | unit | `pytest apps/dashboard/tests/test_filters.py::test_validate_from_after_to -x` | ❌ Wave 0 |
| TOP-01 | top-performing ignores region/store filter | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_top_performing_date_only -x` | ❌ Wave 0 |
| TOP-02 | min 3 reviews threshold enforced | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_top_performing_min_reviews -x` | ❌ Wave 0 |
| TECH-02 | cache key includes accessible_shop_ids | unit | `pytest apps/dashboard/tests/test_filters.py::test_filter_hash_differs_by_shop_scope -x` | ❌ Wave 0 |
| TECH-03 | 3 composite indexes on Review table | unit | `pytest apps/reviews/tests/test_models.py::test_review_meta_indexes -x` | ❌ Wave 0 |
| TECH-04 | all 5 endpoints: query count ≤ 3 | unit | `pytest apps/dashboard/tests/test_aggregations.py -x -q` | ❌ Wave 0 |
| TECH-04 | views: 403/400/cache paths | unit | `pytest apps/dashboard/tests/test_views.py -x -q` | ❌ Wave 0 |
| KPI-03 | negative count uses AI sentiment not star rating | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_negative_count_ai_sentiment -x` | ❌ Wave 0 |
| SENT-06 | empty states: no reviews vs none enriched | unit | `pytest apps/dashboard/tests/test_aggregations.py::test_sentiment_empty_states -x` | ❌ Wave 0 |
| ERR-01 | branded 404 returned by handler404 | unit | `pytest apps/common/tests/test_views.py::test_404_page -x` | ❌ Wave 0 |
| ERR-02 | branded 500 returned by handler500 | unit | `pytest apps/common/tests/test_views.py::test_500_page -x` | ❌ Wave 0 |
| FILT-06, FILT-07 | URL state + sessionStorage | manual-only | N/A — browser API; covered by TypeScript types and integration test in Vitest | N/A |
| TOP-03 | bar threshold coloring | manual-only | N/A — visual; Vitest snapshot test acceptable | N/A |

### Sampling Rate

- **Per task commit:** `pytest apps/dashboard/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/dashboard/__init__.py` — new app
- [ ] `apps/dashboard/apps.py` — app config
- [ ] `apps/dashboard/tests/__init__.py` — test package
- [ ] `apps/dashboard/tests/test_filters.py` — covers FILT-08, FILT-09, FILT-10, TECH-02
- [ ] `apps/dashboard/tests/test_aggregations.py` — covers TOP-01, TOP-02, TECH-04, KPI-03, SENT-06
- [ ] `apps/dashboard/tests/test_views.py` — covers TECH-04 (HTTP layer)
- [ ] Framework install: `pytest` already installed; `pytest-django` already configured
- [ ] Migration: `apps/reviews/migrations/0006_dashboard_indexes.py` — covers TECH-03

---

## Sources

### Primary (HIGH confidence — direct codebase inspection, 2026-05-07)

- `apps/reviews/models.py` — Review model fields confirmed: `star_rating`, `review_create_time`, `enrichment_status`, `sentiment`, `deleted_at`; existing indexes confirmed; `ReviewQuerySet.active()` confirmed
- `apps/reviews/managers.py` — `.active()` returns `filter(deleted_at__isnull=True)` — confirmed safe to chain
- `apps/reviews/selectors/reviews.py` — `get_accessible_shop_ids()` confirmed (handles both SHOP and REGION scope types)
- `apps/common/permissions.py` — `IsOrgScoped.has_permission()` checks `ORG_ADMIN or STAFF_ADMIN` with non-null `organisation_id` — confirmed
- `apps/reviews/tests/factories.py` — `ReviewFactory` confirmed; `organisation`, `shop`, `star_rating`, `enrichment_status`, `sentiment` all settable
- `config/urls.py` — URL include pattern confirmed; `handler404`/`handler500` not yet set
- `frontend/package.json` — `recharts` and `@tanstack/react-query` NOT in dependencies — must be added
- `frontend/vite.config.ts` — entrypoint pattern confirmed (9 existing entrypoints using `resolve(__dirname, "src/entrypoints/...")`); `dashboard` entry not yet registered
- `frontend/src/widgets/action-items/api.ts` — `getCsrfToken()`, `headers()`, `ApiError`, `handle()` patterns confirmed — these are the reference for `dashboard/api.ts`
- `templates/reviews/review_list.html` — `json_script` bootstrap data pattern confirmed
- `templates/organisations/org_dashboard.html` — placeholder content confirmed; existing view in `apps/organisations/views.py` confirmed
- `apps/reviews/migrations/` — last migration is `0005_...`; next is `0006`

### Secondary (MEDIUM confidence — npm registry, 2026-05-07)

- `npm view recharts version` → `3.8.1` (confirmed current; React 19 peer dep includes `^19.0.0`)
- `npm view @tanstack/react-query version` → `5.100.9` (confirmed current; React 18+19 peer dep)

### Tertiary (supporting — prior research)

- `.planning/research/SUMMARY.md` — recharts + React Query stack decisions with full rationale
- `.planning/research/ARCHITECTURE.md` — full pattern documentation with verified codebase references
- `.planning/phases/14-dashboard/14-CONTEXT.md` — locked implementation decisions
- `.planning/phases/14-dashboard/14-UI-SPEC.md` — visual and interaction contract (approved)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — npm registry verified for both new packages today; all existing packages already in use
- Architecture: HIGH — patterns sourced from direct codebase inspection of all integration points
- ORM aggregation: HIGH — conditional Count with Q() is verified Django 6.0 pattern; field names verified in Review model
- Pitfalls: HIGH — DASH-C1 through DASH-C7 all have specific test assertions that will catch them
- React Query patterns: HIGH — v5 API verified against @tanstack/react-query v5 docs; `useQuery` object form confirmed
- Error page wiring: MEDIUM — `handler404`/`handler500` string path format is standard Django; no prior art in this codebase to confirm exact location

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (recharts and react-query versions stable; Django ORM patterns stable)
