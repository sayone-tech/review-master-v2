# Project Research Summary

**Project:** Review Master — v0.4 Organisation Admin Dashboard
**Domain:** Multi-tenant SaaS analytics dashboard — Django backend + React island frontend
**Researched:** 2026-05-07
**Confidence:** HIGH

## Executive Summary

The v0.4 milestone adds a read-only analytics dashboard to an existing multi-tenant SaaS platform. The dashboard is a React island embedded in a Django template page, surfacing five data widgets (KPI cards, sentiment donut, top-performing outlets bar chart, performance highlights card, and a single-store variant) all driven by a shared filter bar. The backend is a new `apps/dashboard/` Django app with five pure-read `APIView` endpoints backed by single-query ORM aggregations, Redis TTL caching, and three new composite indexes on the `Review` table. The frontend introduces `recharts` for charting and `@tanstack/react-query` for parallel data fetching with filter-key-driven refetch.

The recommended approach is to build backend-first: add indexes, write the `DashboardFilterParams` validation function and cache key builder, implement aggregation selectors with `CaptureQueriesContext` tests, then wire views and URLs. The frontend follows once the API contract is locked. The single most important architectural decision is that the cache key must embed a hash of the user's `accessible_shop_ids` — without this, Staff Admins with different shop scopes will receive each other's cached dashboard data, a security failure. All other design choices follow directly from this constraint.

The two primary risks are: (1) the cache scoping bug described above, which must be designed in from the very first utility function written; and (2) the timezone boundary mismatch, where date-window presets computed in UTC silently exclude reviews from non-UTC users' current day. If adding `User.timezone` is out of scope, the correct mitigation is an explicit "Dates are shown in UTC" notice rather than silent incorrect exclusion. The remaining pitfalls (index field order, Python-side aggregation, wrong filter scope on the top-performers widget) are all preventable with the `CaptureQueriesContext` query-count tests and `EXPLAIN ANALYZE` verification called for in the implementation plan.

---

## Key Findings

### Recommended Stack

The milestone adds exactly two new npm packages to the existing Vite + React 19 + TypeScript + Tailwind setup: `recharts@^3.8.1` for charts and `@tanstack/react-query` v5 for data fetching. No other packages are required. No new backend packages are needed; all backend dependencies are already installed from earlier phases.

**Conflict resolved: TanStack Query v5 is added (overrides STACK.md recommendation).**

STACK.md recommended continuing the existing vanilla `useEffect` + `fetch` pattern and not adding React Query. ARCHITECTURE.md, after direct codebase inspection, concluded that React Query must be added. The conflict is resolved in favor of ARCHITECTURE.md and the explicit requirement in the project requirements doc (section 9.6: "React Query handles parallel fetching and per-card loading states") for the following reasons:

- The dashboard has five parallel endpoints all sharing a single filter state object. Filter changes must trigger coordinated refetches across all five queries, which requires approximately 150 lines of `useEffect` + `useCallback` boilerplate per hook without React Query.
- React Query's query-key-based declarative refetch model maps directly to the filter-as-key pattern used here.
- `staleTime: 5min` on the client aligns with the 5-minute server-side Redis TTL, preventing redundant requests.
- TanStack Query v5 is React 19 compatible (peer dep includes `^18 || ^19`).

STACK.md's concern about bundle cost (13.4 KB gzipped) and unfamiliar abstraction is noted. The tradeoff is accepted because the dashboard is the most complex widget in the codebase and the vanilla hooks pattern would produce a maintenance burden disproportionate to the size saving.

**Core technologies:**
- `recharts@^3.8.1`: bar chart + donut chart — React 19 peer dep verified; SVG rendering avoids Canvas destroy lifecycle; single package covers both required chart types
- `@tanstack/react-query` v5: parallel fetching with filter-as-query-key — declarative refetch on filter change; `staleTime` aligned to server TTL; per-query loading/error states
- `URLSearchParams` + `window.history.replaceState`: URL filter state — no library needed; 20-line utility; `replaceState` over `pushState` prevents browser history pollution
- `sessionStorage`: filter persistence across same-tab navigation — fallback when URL params absent

**Not added:**
- `react-chartjs-2` / `chart.js`: NOT React 19 compatible (peer dep omits React 19; open issue #1235)
- `@nivo/*`: PARTIAL React 19 compatibility; requires `--legacy-peer-deps` (open issue #2618)
- `nuqs` / `react-router-dom`: over-engineering for 5 filter params in a non-SPA Django page

---

### Expected Features

All items below are required for v0.4. There are no optional items in the MVP.

**Must have (table stakes) — v0.4:**
- Filter bar: cascading Region to Store dropdowns, date presets (7d/30d/90d) plus custom date pickers, Clear Filters button, URL state via `replaceState`, `sessionStorage` fallback
- KPI cards: Total Reviews, Average Rating with half-star SVG display, Negative Reviews (AI sentiment-based) — skeleton loading, independent per-card error states with inline Retry
- Best Performing Outlets bar chart: threshold coloring (green ≥4.0, amber 3.0–3.99, red <3.0), hover tooltip, click navigates to Reviews page, `ResponsiveContainer`
- Sentiment Distribution donut: 3 segments with hover tooltips, legend, coverage footer, <20% enrichment warning, enrichment-aware empty state, accessibility attributes
- Performance Highlights card: top and bottom performer sub-cards — multi-store path only
- "Your Store" single-shop variant: KPIs + rating distribution mini-bars + trend indicator — mutually exclusive with bar chart, active when exactly 1 store in scope
- `apps/dashboard/` Django app with 5 focused read-only API endpoints
- Redis 5-minute TTL caching with scope-aware cache keys (includes `accessible_shop_ids` hash)
- 3 new composite indexes on the `Review` table

**Should have (competitive differentiators):**
- Threshold-based bar coloring — instant visual triage without reading numbers
- Bar chart click to Reviews page navigation — bridges insight to action
- Session persistence of filter state — reduces repetitive reconfiguration
- Coverage footer with warning callout when enrichment coverage < 20%

**Defer to v1.x:**
- Manual Refresh button — add only if user research shows staleness complaints
- Export to CSV — for users needing historical analysis beyond 365 days

**Defer to v2+:**
- Real-time WebSocket dashboard — only after explicit Channels scope review (CLAUDE.md section 13.2 prohibits new consumers without architecture sign-off)
- Compare-to-previous-period toggle on bar chart
- AI-powered anomaly callouts

**Anti-features — never build:**
- Global error boundary replacing all widgets — hides which widget failed
- Date range beyond 365 days — breaks P95 < 400ms target under load
- `history.pushState` for filter changes — pollutes browser history

---

### Architecture Approach

The architecture is a strict separation of concerns across three layers. The backend layer: a single-query aggregation layer in `apps/dashboard/selectors/aggregations.py` using ORM `aggregate()` and `annotate()`; a thin `DashboardApiView` base class that handles validation, cache lookup, and cache write; and a `DashboardFilterParams` frozen dataclass that carries validated params and the resolved `accessible_shop_ids` tuple. The frontend layer: one `QueryClient` at the React root serving five parallel `useQuery` hooks whose keys are the filter state object. The integration layer: Django template passes bootstrap data as `<script type="application/json">` tags read via `readJsonScript()`, the established pattern from `ReviewManagementWidget`.

**Major components:**

1. `apps/dashboard/filters.py` — `DashboardFilterParams` dataclass plus `validate_filter_params()`. Single point for scope enforcement (403 on out-of-scope region/shop), date range validation (400 on >365d or from>to), and `accessible_shop_ids` resolution. Must be the first module written.

2. `apps/dashboard/selectors/aggregations.py` — all ORM aggregations; `_base_qs()` shared queryset; `dashboard_kpis()`, `dashboard_sentiment_distribution()`, `dashboard_top_performing()`, `dashboard_highlights()`. Each function is one DB query. No Python-side aggregation.

3. `apps/dashboard/services/cache.py` — `dashboard_cache_key()` (embeds `filter_hash()` which includes `accessible_shop_ids`), `cache_get()`, `cache_set()`. TTL-only invalidation; no event-based invalidation.

4. `apps/dashboard/views.py` — `DashboardApiView` base plus 5 concrete views. Base handles filter validation, cache check, and cache write. Subclasses implement only `_fetch()`. Uses `IsOrgScoped` directly, not `TenantScopedViewSet` (dashboard views are `APIView` with no queryset class attribute — `TenantScopedViewSet` is incompatible).

5. `frontend/src/widgets/dashboard/DashboardWidget.tsx` — single React root; owns `QueryClient`; renders all sections. Five `useQuery` hooks fire in parallel. Top-performing and highlights use a `dateOnlyFilters` object, not `fullFilters` — this is the prevention for DASH-C2.

6. `apps/reviews/migrations/000N_dashboard_indexes.py` — three new composite indexes. Must be added first; indexes must exist from the first day of testing.

---

### Critical Pitfalls

1. **DASH-C1: Cache key missing `accessible_shop_ids` hash (security incident risk)** — Staff Admin A's cached data is served to Staff Admin B if they share org and filter params. Prevention: `dashboard_cache_key()` must include `filter_hash()` which serializes `accessible_shop_ids`. For Org Admins pass empty list (`[]`); the hash of `[]` is stable and distinct from any Staff user's list. Recovery cost: HIGH — requires cache flush, access log audit, and user notification.

2. **DASH-C2: Top Performing Outlets applies Region/Store filter (data correctness)** — When a specific store is selected, the "top performers" chart shows only that one store. Prevention: construct two filter objects in React: `fullFilters` (all params) for KPIs and Sentiment, `dateOnlyFilters` (date only) for Top Performers and Highlights. Backend must also ignore region/shop params for those two endpoints. Test: `GET /api/v1/dashboard/top-performing/?region=1` returns all shops.

3. **DASH-C3: Out-of-scope URL params silently ignored instead of 403 (security)** — Staff user with a bookmarked Org Admin URL sees unfiltered data without knowing their scope filter was dropped. Prevention: `validate_filter_params()` raises `PermissionDenied` (403, not 400) for any `shop_id` or `region_id` outside the user's `accessible_shop_ids` or `organisation_id`. Frontend handles 403 by clearing the offending filter and showing an access-denied message.

4. **DASH-C5: Composite index field order mismatches query filter shape (performance)** — Index added as `(organisation, sentiment, review_create_time)` but query filters on `(organisation, enrichment_status, sentiment, review_create_time)`. PostgreSQL falls back to seq scan; P95 > 400ms at >10K reviews. Prevention: design indexes from actual `EXPLAIN ANALYZE` output. Correct indexes: `(organisation, review_create_time, sentiment)`, `(shop, review_create_time)`, `(organisation, review_create_time, enrichment_status)`. Verify with `EXPLAIN ANALYZE` after seeding 5K rows in staging.

5. **DASH-C7: Timezone mismatch on date window boundaries (silent data exclusion)** — UTC-based "Last 30 days" silently excludes reviews from non-UTC users' current partial day. Prevention: compute date windows in the user's local timezone, then convert to UTC for DB queries. If `User.timezone` is out of scope, show explicit "Dates are shown in UTC" notice. Never silently drop data.

---

## Implications for Roadmap

This milestone is a single phase (Phase 14 in the existing roadmap). The internal build order is strictly determined by the dependency graph — indexes enable query testing; filter validation is the security foundation; selectors before views; backend API contract before frontend binds to it.

### Phase 1: Indexes + Filter Validation Foundation
**Rationale:** Indexes are a prerequisite to all query plan testing. `DashboardFilterParams` and `validate_filter_params()` are prerequisites to every other backend module — building them first means security constraints (DASH-C1, DASH-C3) are in the data model before any endpoint code exists.
**Delivers:** Migration with 3 composite indexes; `filters.py` with full scope enforcement and 403/400 behavior; `services/cache.py` with scope-aware key builder; tests for both modules.
**Addresses:** DASH-C1 (cache scoping), DASH-C3 (403 on out-of-scope params), DASH-C5 (correct index field order).
**Avoids:** Retrofitting security constraints onto already-written endpoints.

### Phase 2: Aggregation Selectors + Query-Count Tests
**Rationale:** Selectors are the most logic-dense backend layer and have the highest test value. Writing them before views allows `CaptureQueriesContext` tests to validate query counts in isolation — no HTTP stack overhead, no cache interference. DASH-C4 (Python-side aggregation) cannot survive this phase if query-count ceilings are enforced.
**Delivers:** `aggregations.py` with five selector functions (each one DB query); `test_aggregations.py` with `CaptureQueriesContext` assertions; test for DASH-C6 (50% enrichment coverage = chart renders, not blank).
**Addresses:** DASH-C4 (all aggregation at DB level), DASH-C6 (partial enrichment coverage is informative, not an empty state).
**Uses:** Composite indexes from Phase 1.

### Phase 3: Dashboard Views + URL Registration
**Rationale:** Views are thin wrappers once selectors are tested. This phase is low-complexity and enables end-to-end HTTP testing before any frontend work begins.
**Delivers:** `DashboardApiView` base + 5 concrete views; `apps/dashboard/urls.py`; wired into `config/urls.py`; `INSTALLED_APPS` updated; `test_views.py` covering 403/400/cache-hit/cache-miss paths.
**Implements:** `DashboardApiView` base class pattern (single validation + cache check + delegate `_fetch()` pattern from ARCHITECTURE.md).

### Phase 4: Django Template View + Bootstrap Data
**Rationale:** The template view defines the bootstrap data contract (regions JSON, shops JSON, `data-is-single-shop` attribute). Defining it before the React island means the contract is testable from the server side before the frontend binds to it, preventing shape-mismatch surprises late in development.
**Delivers:** Django template view for the dashboard page; `dashboard.html` with `#dashboard-root` mount point and `<script type="application/json">` bootstrap tags.

### Phase 5: React Frontend — Hooks, Components, Entrypoint
**Rationale:** Frontend is the last layer; all API contracts are locked. Build order: types then api.ts then hooks then components then root then entrypoint, following the dependency graph.
**Delivers:** `types.ts`; `api.ts`; `useFilterState.ts` (URL + sessionStorage); four `useQuery` hooks; `FilterBar.tsx`; `KpiCards.tsx`; `SentimentDonut.tsx`; `TopPerformingSection.tsx`; `DashboardWidget.tsx` with `QueryClientProvider`; `dashboard.tsx` entrypoint; `vite.config.ts` entry added.
**Uses:** `recharts@^3.8.1` and `@tanstack/react-query` v5 (both added to `package.json`).
**Addresses:** DASH-C2 (two separate filter objects: `fullFilters` and `dateOnlyFilters`); `replaceState` not `pushState`; `staleTime: 5min` matching server TTL.

### Phase Ordering Rationale

- Indexes before selectors: composite indexes must exist before `EXPLAIN ANALYZE` verification is meaningful and before CI query-count tests can confirm the correct query plan is selected.
- `filters.py` before `views.py`: the filter validation function is the security contract. Building it first ensures scope enforcement is the foundation, not a retrofit.
- Selectors before views: decouples aggregation correctness testing from the HTTP layer. `CaptureQueriesContext` tests on selectors alone are faster and more precise than on views.
- Backend fully wired before frontend: the Django template bootstrap data shape and URL contracts must be stable before React binds to them.
- `api.ts` and `types.ts` before components: TypeScript types from API responses prevent runtime shape mismatches in components.

### Research Flags

Phases with standard, well-documented patterns (no additional research needed):
- **All phases:** ARCHITECTURE.md is based on direct codebase inspection. PITFALLS.md provides verified prevention strategies and test assertions for every critical pitfall. The implementation plan is complete enough to execute without further research.

Areas requiring implementation decisions before coding begins (not research, but scope decisions):
- **`User.timezone` field (DASH-C7):** Does Phase 14 add this field to the `User` model, or does it ship with a "UTC only" notice? This must be resolved before `validate_filter_params()` is written.
- **Minimum review threshold for Top Performers:** PITFALLS.md references a minimum-3-reviews threshold (HAVING clause). The threshold value must be confirmed with the product owner before writing `dashboard_top_performing()`.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | `recharts` React 19 peer dep verified on GitHub main branch. TanStack Query v5 React 19 peer dep verified on npm. Stack conflict resolved with explicit rationale. |
| Features | HIGH | All features verified against existing v0.3 infrastructure capabilities. Feature dependency graph fully mapped. UX patterns sourced from established design systems (Carbon, PatternFly). |
| Architecture | HIGH | Based on direct codebase inspection of `apps/common/permissions.py`, `apps/reviews/selectors/reviews.py`, `config/urls.py`, `frontend/package.json`, `frontend/vite.config.ts`, and all 9 existing entrypoints. Not training assumptions. |
| Pitfalls | HIGH (cache, ORM, indexes) / MEDIUM (timezone, React Query patterns) | Cache scoping and ORM aggregation verified against Django 6.0 docs and existing codebase. Timezone handling verified against Django docs and known production failure modes. React Query stale patterns verified against TanStack Query v5 docs. |

**Overall confidence:** HIGH

### Gaps to Address

- **`User.timezone` field scope:** DASH-C7 requires a decision before implementation begins. Option A: add `timezone = CharField(default="UTC", max_length=64)` to `User` model, validated against `zoneinfo.available_timezones()` on save — clean, correct. Option B: ship with an explicit "Dates are shown in UTC" notice in the filter bar — honest limitation. Neither is a research gap; it is a product scope decision.

- **Minimum review threshold for Top Performers:** PITFALLS.md assumes a minimum of 3 reviews threshold enforced via HAVING clause. FEATURES.md and ARCHITECTURE.md do not specify this value. The implementation should confirm the threshold with the product owner before writing the `dashboard_top_performing()` selector. Default to no minimum (1+) if unspecified.

- **`your-store` vs `highlights` endpoint structure:** ARCHITECTURE.md shows both `/your-store/` and `/highlights/` as separate endpoints. FEATURES.md describes them as mutually exclusive views. The implementation should confirm whether these are two separate conditional endpoints (cleaner, consistent with single-responsibility principle) or one endpoint with a `variant` response field.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `apps/common/permissions.py` — `IsOrgScoped` confirmed; `TenantScopedViewSet` incompatibility with `APIView` confirmed
- `apps/reviews/selectors/reviews.py` — `get_accessible_shop_ids()` exists and is tested
- `config/settings/base.py` — Redis DB 0, `KEY_PREFIX="app"`, `django-redis` backend confirmed
- `config/urls.py` — URL namespace patterns confirmed
- `frontend/package.json` — existing deps confirmed; `@tanstack/react-query` and `recharts` absent
- `frontend/vite.config.ts` — entrypoint pattern confirmed (9 existing entrypoints)
- `recharts/recharts package.json` (GitHub main) — React 19 peer dep verified: `"react": "^16.8.0 || ^17.0.0 || ^18.0.0 || ^19.0.0"`
- `@tanstack/react-query` npm — v5 React 18 + 19 peer dep verified

### Secondary (MEDIUM confidence — official documentation)
- Django 6.0 ORM aggregation docs — `annotate()` plus HAVING via `.filter()` after `.annotate()` confirmed
- PostgreSQL multicolumn index docs — leftmost field must match leading filter predicate
- TanStack Query v5 docs — `staleTime`, `refetchOnWindowFocus`, parallel queries confirmed
- Django `USE_TZ = True` timezone docs — all `DateTimeField` values stored in UTC; comparison requires timezone-aware datetimes
- `history.replaceState` vs `pushState` — React Router and TanStack Router docs both recommend `replaceState` for filter state

### Tertiary (supporting)
- PkgPulse — Recharts vs Chart.js vs Nivo 2026 comparison
- LogRocket — Best React chart libraries 2025
- Carbon Design System — Loading Pattern (skeleton + per-card error states)
- Pencil and Paper — Filter UX Design Patterns (cascading dropdowns, Clear Filters)

---
*Research completed: 2026-05-07*
*Ready for roadmap: yes*
