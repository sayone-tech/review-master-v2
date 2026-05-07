---
phase: 14-dashboard
verified: 2026-05-07T10:45:00Z
status: passed
score: 38/38 must-haves verified
re_verification: false
human_verification:
  - test: "Bar chart threshold coloring renders correctly in browser"
    expected: "Bars with avg_rating >= 4.0 show green (#22C55E), 3.0-3.99 amber (#F59E0B), <3.0 red (#EF4444)"
    why_human: "SVG fill props cannot be verified via grep; requires visual inspection"
  - test: "Bar chart tooltip on hover shows shop name, avg rating, review count"
    expected: "CustomDonutTooltip-style popup appears on bar hover with correct values"
    why_human: "Interactive recharts tooltip requires browser rendering"
  - test: "Clicking a bar navigates to /admin/org/reviews/ with correct params"
    expected: "window.location.href fires with ?store={id}&from={iso}&to={iso}"
    why_human: "Navigation behavior requires running browser"
  - test: "Sentiment donut tooltip on hover shows label + count + percentage"
    expected: "Custom tooltip component renders correctly on donut segment hover"
    why_human: "Interactive recharts tooltip requires browser rendering"
  - test: "Custom date panel anchors correctly below Filter Bar"
    expected: "Absolute-positioned panel appears below date range select without overflow"
    why_human: "CSS layout and positioning requires visual inspection"
  - test: "All 5 widgets fire their queries in parallel on first load"
    expected: "Network waterfall shows 5 concurrent requests to /api/v1/dashboard/*"
    why_human: "Parallel query behavior requires browser devtools network panel inspection"
  - test: "Dashboard page renders at /admin/org/dashboard/ in dev server with populated data"
    expected: "Page shows FilterBar, KpiCards, SentimentDonut, TopPerformingSection (or YourStore for single-shop)"
    why_human: "End-to-end rendering with live data requires running dev server"
---

# Phase 14: Dashboard Verification Report

**Phase Goal:** Build the analytics dashboard — a full-stack feature giving Org Admins and Staff Admins a filterable, real-time view of review KPIs, sentiment breakdown, top-performing outlets, and action-item highlights, backed by scope-enforced Django API endpoints and a React frontend.
**Verified:** 2026-05-07T10:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Filter validation raises 403 for out-of-scope shop/region | VERIFIED | `validate_filter_params()` in `filters.py:108-122` raises `PermissionDenied` |
| 2 | Filter validation raises 400 for date range > 365 days or from > to | VERIFIED | `_resolve_date_window()` in `filters.py:71-76` raises `ValidationError` |
| 3 | DashboardFilterParams.filter_hash() includes accessible_shop_ids | VERIFIED | `filters.py:33` — `"shop_ids": list(self.accessible_shop_ids)` in JSON payload |
| 4 | Cache key includes filter_hash with 5-minute TTL | VERIFIED | `cache.py:14` format `dashboard:{endpoint}:{org_id}:{user_id}:{params.filter_hash()}`, `DASHBOARD_TTL_SECONDS = 300` |
| 5 | Three composite indexes exist on Review table | VERIFIED | Migration `0006_dashboard_indexes.py` adds `review_org_time_sent_idx`, `review_shop_time_idx`, `review_org_time_status_idx`; all three in `reviews/models.py` Meta.indexes |
| 6 | 5 dashboard endpoints registered under /api/v1/dashboard/ | VERIFIED | `apps/dashboard/urls.py` has 5 paths; `config/urls.py:26` includes `apps.dashboard.urls` |
| 7 | KPI endpoint counts negative reviews by AI sentiment=negative + enrichment_status=SUCCESS | VERIFIED | `aggregations.py:79-82` — `Q(sentiment="negative", enrichment_status=SUCCESS)` |
| 8 | dashboard_top_performing ignores region_id/shop_id (date-only scope, TOP-01) | VERIFIED | `_date_only_qs()` in `aggregations.py:46-57` explicitly excludes region/shop filters |
| 9 | dashboard_top_performing excludes shops with < 3 reviews (TOP-02) | VERIFIED | `aggregations.py:228` — `.filter(review_count__gte=MIN_REVIEWS_FOR_RANKING)` where `MIN_REVIEWS_FOR_RANKING = 3` |
| 10 | dashboard_top_performing returns split=True with Top5+Worst5 when > 10 shops | VERIFIED | `aggregations.py:240-241` — `if len(shops) > 10: return {"shops": shops[:5] + shops[-5:], "split": True}` |
| 11 | dashboard_highlights uses AI-derived positive/negative counts (TOP-06) | VERIFIED | `aggregations.py:257-258` — `Q(sentiment="positive", enrichment_status=SUCCESS)` |
| 12 | dashboard_your_store returns None for multi-shop users | VERIFIED | `aggregations.py:138` — `if len(params.accessible_shop_ids) != 1: return None` |
| 13 | dashboard_your_store trend_direction='none' when previous window < 3 reviews | VERIFIED | `aggregations.py:178` — `if prev_total >= MIN_REVIEWS_FOR_RANKING` gates the trend calc |
| 14 | DashboardApiView base handles validation + caching for all 5 views | VERIFIED | `views.py:27-57` — shared `get()` method calls `validate_filter_params`, `cache_get`, `_fetch`, `cache_set` |
| 15 | handler404 and handler500 wired in config/urls.py | VERIFIED | `config/urls.py:36-37` — `handler404 = "apps.common.views.page_not_found"`, `handler500 = "apps.common.views.server_error"` |
| 16 | Branded 404/500 templates with auth-aware CTA exist | VERIFIED | `templates/404.html` and `templates/500.html` contain "Page Not Found" / "Something went wrong", logo, `request.user.is_authenticated` branch, "Go to Dashboard" / "Go to Login" CTAs |
| 17 | Dashboard page template mounts React island with bootstrap data | VERIFIED | `org_dashboard.html` — `id="dashboard-root"`, `dashboard-regions`, `dashboard-shops` json_script tags, `data-is-single-shop` attribute |
| 18 | org_admin_dashboard view provides scoped bootstrap context | VERIFIED | `organisations/views.py:113-144` — calls `get_accessible_shop_ids`, builds `regions_json`, `shops_json`, `is_single_shop` |
| 19 | recharts and @tanstack/react-query installed | VERIFIED | `package.json:17,24` — `@tanstack/react-query: ^5.100.9`, `recharts: ^3.8.1` |
| 20 | Dashboard Vite entrypoint registered | VERIFIED | `vite.config.ts:28` — `dashboard: resolve(__dirname, "src/entrypoints/dashboard.tsx")` |
| 21 | TypeScript contracts in types.ts cover all 5 response shapes | VERIFIED | `types.ts` exports `KpisResponse`, `SentimentResponse`, `TopPerformingResponse`, `HighlightsResponse`, `YourStoreResponse`, `DashboardFilters`, `Region`, `Shop`, `DashboardBootstrap` |
| 22 | api.ts uses date-only query string for top-performing/highlights/your-store | VERIFIED | `api.ts:72-97` — `fetchTopPerforming`, `fetchHighlights`, `fetchYourStore` use `buildDateOnlyQs` |
| 23 | useFilterState uses URL precedence over sessionStorage | VERIFIED | `useFilterState.ts:103-107` — `parseFromUrl` checked first, sessionStorage fallback |
| 24 | Filter state syncs to URL via history.replaceState | VERIFIED | `useFilterState.ts:84` — `window.history.replaceState` |
| 25 | FilterBar renders all 5 controls with correct copy | VERIFIED | "All Regions", "All Stores", "Last 30 days", "Custom range", "All dates in UTC", "End date must be after start date.", "Date range cannot exceed 365 days." all present |
| 26 | DashboardWidget passes fullFilters to KpiCards+SentimentDonut, dateOnlyFilters to TopPerforming/Highlights/YourStore | VERIFIED | `DashboardWidget.tsx:40-83` — explicit split of `fullFilters` and `dateOnlyFilters` |
| 27 | When isSingleShop, YourStore renders instead of TopPerformingSection+PerformanceHighlights | VERIFIED | `DashboardWidget.tsx:70-84` — `bootstrap.isSingleShop` ternary controls which widgets render |
| 28 | TopPerformingSection has bar colors, "View last 90 days" CTA, click navigation | VERIFIED | `TopPerformingSection.tsx` — `#22C55E`, `#EF4444`, "View last 90 days", `window.location.href` |
| 29 | PerformanceHighlights shows AI-derived positive/negative with "Top Performer" / "Needs Attention" | VERIFIED | `PerformanceHighlights.tsx:50,57,66,73` — exact copy present |
| 30 | YourStore shows shop name, avg rating, "No previous data" for trend_direction='none', distribution | VERIFIED | `YourStore.tsx:48,146` — "No previous data", "out of 5" |
| 31 | KpiCards renders 3 cards with correct copy and half-star logic | VERIFIED | "Total Reviews", "Average Rating", "Negative Reviews", "out of 5 stars", "No reviews in this period", "of enriched reviews", "Across N stores", `StarHalf` import all present |
| 32 | SentimentDonut renders donut, coverage footer, spinner under 50% | VERIFIED | "Sentiment Distribution", COLORS object, "No reviews to analyze", "Sentiment analysis is in progress", "Analysis is still in progress.", "coverage_pct < 50" spinner all present |
| 33 | Entrypoint mounts DashboardWidget via createRoot | VERIFIED | `dashboard.tsx:2,8` — `createRoot(el).render(<StrictMode><DashboardWidget /></StrictMode>)` |
| 34 | CaptureQueriesContext tests assert fixed query ceilings | VERIFIED | `test_aggregations.py:9` imports `CaptureQueriesContext`; used at lines 55, 134, 358, 430 for kpis, sentiment, top-performing, highlights |
| 35 | Security: filter_hash isolates users by accessible_shop_ids | VERIFIED | `test_filters.py` — `test_filter_hash_differs_by_shop_scope` and `test_filter_hash_stable_for_same_inputs` tests exist |
| 36 | Handler path tests assert correct module paths | VERIFIED | `apps/common/tests/test_views.py:51-60` — `test_handler404_module_path`, `test_handler500_module_path` |
| 37 | View 403/400/200 path tests exist | VERIFIED | `test_views.py:51-90` — `test_kpis_view_returns_200`, `test_kpis_view_out_of_scope_store_returns_403`, `test_kpis_view_date_range_too_long_returns_400`, `test_kpis_view_from_after_to_returns_400` |
| 38 | Cache-hit test verifies selector is not called twice | VERIFIED | `test_views.py:90` — `test_kpis_view_cache_hit_skips_selector` |

**Score:** 38/38 truths verified

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `apps/dashboard/__init__.py` | VERIFIED | Exists |
| `apps/dashboard/apps.py` | VERIFIED | `DashboardConfig.name = "apps.dashboard"` |
| `apps/dashboard/filters.py` | VERIFIED | `@dataclass(frozen=True)` on `DashboardFilterParams`; `validate_filter_params()`; `MAX_RANGE_DAYS = 365`; `shop_ids` in filter_hash payload |
| `apps/dashboard/services/cache.py` | VERIFIED | Exports `dashboard_cache_key`, `cache_get`, `cache_set`, `DASHBOARD_TTL_SECONDS = 300`; key format includes `filter_hash()` |
| `apps/dashboard/selectors/aggregations.py` | VERIFIED | Exports `dashboard_kpis`, `dashboard_sentiment_distribution`, `dashboard_top_performing`, `dashboard_highlights`, `dashboard_your_store`, `MIN_REVIEWS_FOR_RANKING = 3`; `_date_only_qs` for TOP-01; `review_count__gte=MIN_REVIEWS_FOR_RANKING` for TOP-02 |
| `apps/dashboard/views.py` | VERIFIED | `DashboardApiView(APIView)` with `permission_classes = [IsOrgScoped]`; 5 concrete subclasses each with `endpoint_name` |
| `apps/dashboard/urls.py` | VERIFIED | 5 URL patterns matching all 5 views |
| `apps/reviews/migrations/0006_dashboard_indexes.py` | VERIFIED | Adds `review_org_time_sent_idx`, `review_shop_time_idx`, `review_org_time_status_idx`; matches `review_create_time` field (correct — model uses `review_create_time` not `review_created_at` as REQUIREMENTS.md typo suggests) |
| `config/settings/base.py` | VERIFIED | `"apps.dashboard"` in `INSTALLED_APPS` |
| `config/urls.py` | VERIFIED | `include("apps.dashboard.urls")` at `api/v1/dashboard/`; `handler404` and `handler500` module-level strings |
| `apps/common/views.py` | VERIFIED | `page_not_found(request, exception=None)` and `server_error(request)` functions |
| `templates/organisations/org_dashboard.html` | VERIFIED | Extends `base_org.html`; `id="dashboard-root"` with `data-is-single-shop`; `dashboard-regions` and `dashboard-shops` json_script tags; loads `src/entrypoints/dashboard.tsx` via `vite_asset` |
| `apps/organisations/views.py` (dashboard view) | VERIFIED | Builds `regions_json`, `shops_json`, `is_single_shop` context; calls `get_accessible_shop_ids` |
| `templates/404.html` | VERIFIED | Standalone (no base extend); "Page Not Found"; logo; auth-aware CTA ("Go to Dashboard" / "Go to Login") |
| `templates/500.html` | VERIFIED | "Something went wrong"; "Our team has been notified"; logo; auth-aware CTA |
| `frontend/package.json` | VERIFIED | `recharts: ^3.8.1`; `@tanstack/react-query: ^5.100.9` |
| `frontend/vite.config.ts` | VERIFIED | `dashboard: resolve(..., "src/entrypoints/dashboard.tsx")` |
| `frontend/src/widgets/dashboard/types.ts` | VERIFIED | All 8 required interfaces exported |
| `frontend/src/widgets/dashboard/api.ts` | VERIFIED | 5 fetch functions; `buildDateOnlyQs` for TOP-01 prevention on client; `ApiError` class |
| `frontend/src/widgets/dashboard/useFilterState.ts` | VERIFIED | `useFilterState`, `DEFAULT_FILTERS`, `presetToAbsoluteDates`, `isDefault`; `history.replaceState`; `sessionStorage`; `parseFromUrl` |
| `frontend/src/widgets/dashboard/FilterBar.tsx` | VERIFIED | Controlled component; "All Regions", "All Stores", "Last 30 days", "Custom range", "All dates in UTC"; client validation errors; `aria-label="Filter by region"` |
| `frontend/src/widgets/dashboard/useTopPerforming.ts` | VERIFIED | `queryKey: ["dashboard", "top-performing", filters]` |
| `frontend/src/widgets/dashboard/useHighlights.ts` | VERIFIED | `queryKey: ["dashboard", "highlights", filters]` |
| `frontend/src/widgets/dashboard/useYourStore.ts` | VERIFIED | `queryKey: ["dashboard", "your-store", filters]`; `enabled` parameter |
| `frontend/src/widgets/dashboard/TopPerformingSection.tsx` | VERIFIED | "Best Performing Outlets"; threshold colors; "View last 90 days"; `window.location.href` navigation; `split` gap rendering |
| `frontend/src/widgets/dashboard/PerformanceHighlights.tsx` | VERIFIED | "Top Performer"; "Needs Attention"; "(AI-derived)" |
| `frontend/src/widgets/dashboard/YourStore.tsx` | VERIFIED | "Your Store"; trend_direction handling; "No previous data" for none; distribution bars; "out of 5" |
| `frontend/src/widgets/dashboard/KpiCards.tsx` | VERIFIED | 3 cards; "Total Reviews", "Average Rating", "Negative Reviews"; "out of 5 stars"; "No reviews in this period"; "of enriched reviews"; "Across N stores"; `StarHalf` half-star |
| `frontend/src/widgets/dashboard/SentimentDonut.tsx` | VERIFIED | "Sentiment Distribution"; 3 COLORS; "No reviews to analyze in this period."; "Sentiment analysis is in progress. Check back shortly."; "Analysis is still in progress."; `coverage_pct < 50` spinner; "of total" footer |
| `frontend/src/widgets/dashboard/DashboardWidget.tsx` | VERIFIED | `QueryClientProvider`; `readBootstrap()` from DOM; `fullFilters` to KpiCards/SentimentDonut; `dateOnlyFilters` to TopPerformingSection/Highlights/YourStore; `isSingleShop` branching |
| `frontend/src/widgets/dashboard/index.ts` | VERIFIED | Barrel exports all components, hooks, and types |
| `frontend/src/entrypoints/dashboard.tsx` | VERIFIED | `createRoot`; `DashboardWidget` mounted |
| `apps/dashboard/tests/test_filters.py` | VERIFIED | 5 security/correctness tests |
| `apps/dashboard/tests/test_aggregations.py` | VERIFIED | `CaptureQueriesContext` tests at lines 55, 134, 358, 430; all required correctness tests |
| `apps/dashboard/tests/test_views.py` | VERIFIED | 200/400/403 path tests; cache-hit test; query count test; smoke tests for all 5 endpoints |
| `apps/common/tests/test_views.py` | VERIFIED | `test_handler404_module_path`, `test_handler500_module_path` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `DashboardFilterParams.filter_hash()` | `accessible_shop_ids` | `json.dumps payload includes shop_ids list` | WIRED | `filters.py:33` — `"shop_ids": list(self.accessible_shop_ids)` |
| `validate_filter_params()` | `get_accessible_shop_ids()` | `from apps.reviews.selectors.reviews import get_accessible_shop_ids` | WIRED | `filters.py:12` — import present; `filters.py:94` — called for STAFF_ADMIN |
| `DashboardApiView.get()` | `validate_filter_params + dashboard_cache_key + cache_get/cache_set` | `shared base class` | WIRED | `views.py:34-51` — all four called in sequence |
| `dashboard_top_performing()` | `params.accessible_shop_ids` via date-only scope | `shop_id__in=params.accessible_shop_ids` in `_date_only_qs` | WIRED | `aggregations.py:50-51` — region_id and shop_id are NOT applied in `_date_only_qs` |
| `dashboard_kpis() negative_count` | `Review.EnrichmentStatus.SUCCESS` | `Q(sentiment='negative', enrichment_status=SUCCESS)` | WIRED | `aggregations.py:80-82` — both conditions present |
| `config/urls.py` | `apps.common.views.page_not_found` | `handler404 string assignment` | WIRED | `config/urls.py:36` — `handler404 = "apps.common.views.page_not_found"` |
| `DashboardWidget` | `fullFilters / dateOnlyFilters separation` | `two filter objects passed to widgets` | WIRED | `DashboardWidget.tsx:40-83` — explicit `dateOnlyFilters` memo; `fullFilters` to kpis/sentiment only |
| `useTopPerforming / useHighlights / useYourStore` | `fetchTopPerforming/Highlights/YourStore(dateOnlyFilters)` | `useQuery with date-only key` | WIRED | Hook files confirmed; `api.ts` uses `buildDateOnlyQs` for these three |
| `org_admin_dashboard view` | `regions_json + shops_json + is_single_shop context` | `render context dict` | WIRED | `organisations/views.py:113-144` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| FILT-01 | 14-04, 14-05, 14-08 | Filter by Region | SATISFIED | `FilterBar.tsx` Region select; `org_dashboard.html` bootstrap data |
| FILT-02 | 14-04, 14-05, 14-08 | Filter by Store with cascade | SATISFIED | `FilterBar.tsx` `visibleShops` filters by `region_id` |
| FILT-03 | 14-05, 14-08 | Date Range presets: 7d/30d/90d/custom | SATISFIED | `FilterBar.tsx` — all 4 options; `useFilterState.ts` — all presets |
| FILT-04 | 14-05 | Custom From/To date picker with inline validation | SATISFIED | `FilterBar.tsx` — custom date panel; `validateCustom()` |
| FILT-05 | 14-05 | Clear Filters button enabled only when non-default | SATISFIED | `FilterBar.tsx` — `isDefault(filters)` gates disabled state |
| FILT-06 | 14-05 | URL params via history.replaceState | SATISFIED | `useFilterState.ts:84` — `window.history.replaceState` |
| FILT-07 | 14-05 | URL params precede sessionStorage | SATISFIED | `useFilterState.ts:103-107` — URL parsed first |
| FILT-08 | 14-01, 14-03 | Out-of-scope store/region → 403 | SATISFIED | `filters.py:108-122` — `PermissionDenied` raised; `test_views.py:60` tests 403 |
| FILT-09 | 14-01, 14-03, 14-05 | Date range > 365 days → 400 | SATISFIED | `filters.py:74-75`; `FilterBar.tsx:25`; `test_views.py:68` |
| FILT-10 | 14-01, 14-03, 14-05 | from > to → 400 | SATISFIED | `filters.py:72-73`; `FilterBar.tsx:23`; `test_views.py:76` |
| TOP-01 | 14-02, 14-06 | Bar chart date-only scope | SATISFIED | `_date_only_qs()` excludes region/shop; `api.ts` uses `buildDateOnlyQs` |
| TOP-02 | 14-02, 14-06 | ≥3 reviews threshold; Top5+Worst5 when >10 | SATISFIED | `aggregations.py:228,240-241` |
| TOP-03 | 14-06 | Bar colors by rating threshold | SATISFIED | `TopPerformingSection.tsx:22-24` — barColor function with three thresholds (human visual verification needed) |
| TOP-04 | 14-06 | Bar hover tooltip | SATISFIED | Custom tooltip component in `TopPerformingSection.tsx` (human interaction needed) |
| TOP-05 | 14-06 | Bar click → Reviews page with filters | SATISFIED | `TopPerformingSection.tsx:171` — `window.location.href = buildReviewsUrl(...)` |
| TOP-06 | 14-02, 14-06 | Highlights with AI-derived counts | SATISFIED | `aggregations.py:257-258`; `PerformanceHighlights.tsx:57,73` — "(AI-derived)" text |
| TOP-07 | 14-06 | Combined empty state + "View last 90 days" CTA | SATISFIED | `TopPerformingSection.tsx:121` — "View last 90 days" button with `onSelect90d` callback |
| STORE-01 | 14-06, 14-08 | Single-shop sees YourStore instead of bar chart | SATISFIED | `DashboardWidget.tsx:70-76` — `isSingleShop` ternary |
| STORE-02 | 14-02, 14-06 | YourStore card fields | SATISFIED | `aggregations.py` returns all fields; `YourStore.tsx` renders shop name, region badge, avg rating, counts, distribution |
| STORE-03 | 14-02, 14-06 | Trend indicator; "no previous data" < 3 reviews | SATISFIED | `aggregations.py:178`; `YourStore.tsx:48` — "No previous data" |
| KPI-01 | 14-02, 14-07 | Total Reviews with "Across N stores" / store name | SATISFIED | `KpiCards.tsx:119-121` |
| KPI-02 | 14-02, 14-07 | Average Rating with half-star | SATISFIED | `KpiCards.tsx:54` — StarHalf; "out of 5 stars" |
| KPI-03 | 14-02, 14-07 | Negative Reviews by AI sentiment NOT star rating | SATISFIED | `aggregations.py:79-82` — explicit AI-sentiment filter |
| KPI-04 | 14-02, 14-07 | Negative % uses enriched_count denominator | SATISFIED | `aggregations.py:88` — `round(negative / enriched * 100, 1) if enriched > 0` |
| KPI-05 | 14-07 | Independent skeleton/empty/error per card | SATISFIED | `KpiCards.tsx:80-85` — 3 `CardSkeleton` elements rendered; individual error/empty paths per plan 14-07 design note |
| SENT-01 | 14-02, 14-07 | Donut from enriched reviews only | SATISFIED | `aggregations.py:110-114` — all sentiment counts filtered by `enrichment_status=SUCCESS` |
| SENT-02 | 14-07 | Summary list with count, %, color bar | SATISFIED | `SentimentDonut.tsx` — per-sentiment rows with inline style width |
| SENT-03 | 14-07 | Donut hover tooltip | SATISFIED | `CustomDonutTooltip` component in `SentimentDonut.tsx` (human interaction needed) |
| SENT-04 | 14-02, 14-07 | Coverage footer < 100% | SATISFIED | `SentimentDonut.tsx:151-158` — `coverage_pct < 100` conditional footer |
| SENT-05 | 14-07 | Spinner when coverage < 50% | SATISFIED | `SentimentDonut.tsx:154-158` — `coverage_pct < 50` spinner |
| SENT-06 | 14-02, 14-07 | Empty states (no reviews / no enriched) | SATISFIED | `SentimentDonut.tsx:74,86`; `aggregations.py:117` — coverage_pct=0 when total=0 |
| TECH-01 | 14-01, 14-03 | apps/dashboard app with endpoints under /api/v1/dashboard/ | SATISFIED | App registered; 5 endpoints wired |
| TECH-02 | 14-01, 14-03 | Redis 5-min TTL cache with filter_hash scope prevention | SATISFIED | `cache.py:7,14` — TTL=300, key includes `user_id` and `filter_hash()` which contains `accessible_shop_ids` |
| TECH-03 | 14-01 | 3 composite indexes on Review table | SATISFIED | `0006_dashboard_indexes.py` — all 3 indexes; field name `review_create_time` is correct (REQUIREMENTS.md contains a typo `review_created_at`) |
| TECH-04 | 14-02, 14-03 | CaptureQueriesContext tests on all 5 endpoints | SATISFIED | `test_aggregations.py` — 4 of 5 query-count tests (kpis, sentiment, top-performing, highlights); `test_views.py:127` — 5th for view layer |
| TECH-05 | 14-04, 14-08 | Dashboard replaces Phase 2 placeholder | SATISFIED | `org_dashboard.html` renders full React island; URL `admin/org/dashboard/` at `name="org_admin_dashboard_v02"` |
| TECH-06 | 14-07, 14-08 | All 5 widgets load in parallel with independent skeletons | SATISFIED | Each widget has its own `useQuery` hook; DashboardWidget renders all simultaneously; parallel network requests require manual verification |
| ERR-01 | 14-03, 14-08 | Branded 404 page | SATISFIED | `templates/404.html`; `handler404` in `config/urls.py`; `page_not_found()` in `common/views.py` |
| ERR-02 | 14-03, 14-08 | Branded 500 page | SATISFIED | `templates/500.html`; `handler500` in `config/urls.py`; `server_error()` in `common/views.py` |

### Anti-Patterns Found

No TODOs, FIXMEs, stubs, or placeholder implementations found in any dashboard files. All component functions return substantive JSX. All API views delegate to real selector functions.

One minor note (non-blocking): The REQUIREMENTS.md description of TECH-03 says `review_created_at` but the actual Review model field and migration correctly use `review_create_time`. The implementation matches the model — the requirements document has the typo, not the code.

### Human Verification Required

The following items cannot be verified programmatically and require manual testing in a running browser:

**1. Bar Chart Threshold Coloring**
- Test: Load dashboard with shops spanning all three rating bands; inspect bar colors
- Expected: green (#22C55E) for avg_rating >= 4.0, amber (#F59E0B) for 3.0-3.99, red (#EF4444) for <3.0
- Why human: SVG Cell fill props only verifiable via browser render

**2. Bar Chart and Donut Tooltips on Hover (TOP-04, SENT-03)**
- Test: Hover over bars in TopPerformingSection and segments in SentimentDonut
- Expected: Tooltips appear with shop name + avg rating + count (bars); sentiment label + count + percentage (donut)
- Why human: recharts tooltip requires interactive browser session

**3. Bar Click Navigation (TOP-05)**
- Test: Click a bar in TopPerformingSection
- Expected: Browser navigates to `/admin/org/reviews/?store={id}&from={iso}&to={iso}`
- Why human: `window.location.href` requires running browser

**4. Parallel Query Loading (TECH-06)**
- Test: Open browser DevTools Network tab, load dashboard
- Expected: 5 concurrent requests to `/api/v1/dashboard/{kpis,sentiment-distribution,top-performing,highlights,your-store}/`
- Why human: Network waterfall requires browser devtools

**5. Custom Date Panel Positioning**
- Test: Click "Custom range" in FilterBar; observe panel position
- Expected: Panel anchors below the Date Range select without viewport overflow
- Why human: CSS absolute positioning requires visual inspection

**6. End-to-End Dashboard Page Render**
- Test: Log in as Org Admin, navigate to `/admin/org/dashboard/`
- Expected: Full dashboard renders with all 5 widgets populating from live data
- Why human: Full-stack integration requires running dev server with data

### Gaps Summary

No gaps found. All 38 must-haves are verified. The codebase matches the plan designs across all 8 sub-plans. The only items remaining are 7 human-verification checks for browser-rendered behavior (tooltip interactions, visual coloring, navigation, parallel loading) that cannot be validated statically.

---

_Verified: 2026-05-07T10:45:00Z_
_Verifier: Claude (gsd-verifier)_
