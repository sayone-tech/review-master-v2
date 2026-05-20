# Roadmap: Multi-Tenant Review Management Platform

## Milestones

- ✅ **v1.0 — Superadmin Module** — Phases 1–5, 24 plans, 52/52 requirements, shipped 2026-04-27 → [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v0.2-org-admin — Organisation Admin Module** — Phases 6–9, 20 plans, 57/57 requirements, shipped 2026-04-30 → [archive](milestones/v0.2-org-admin-ROADMAP.md)
- ✅ **v0.3 — Reviews and Action Items** — Phases 10–13, 37 plans, 77/77 requirements, shipped 2026-05-05 → [archive](milestones/v0.3-ROADMAP.md)
- ✅ **v0.4 — Dashboard** — Phase 14, 8 plans, 38/38 requirements, shipped 2026-05-07
- 🚧 **v0.5 — Configurable Sync Depth** — Phases 15–16, 9/9 requirements (in progress)

## Phases

<details>
<summary>✅ v1.0 — Superadmin Module (Phases 1–5) — SHIPPED 2026-04-27</summary>

5 phases, 24 plans, 52/52 requirements. Full archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v0.2-org-admin — Organisation Admin Module (Phases 6–9) — SHIPPED 2026-04-30</summary>

- [x] Phase 6: Org Admin Shell (5/5 plans) — completed 2026-04-27
- [x] Phase 7: Regions (3/3 plans) — completed 2026-04-28
- [x] Phase 8: Shops (7/7 plans) — completed 2026-04-29
- [x] Phase 9: Team (5/5 plans) — completed 2026-04-30

Full archive: `.planning/milestones/v0.2-org-admin-ROADMAP.md`

</details>

<details>
<summary>✅ v0.3 — Reviews and Action Items (Phases 10–13) — SHIPPED 2026-05-05</summary>

- [x] Phase 10: Infrastructure Foundation (5/5 plans) — completed 2026-05-01
- [x] Phase 11: Reviews Fetching, Display, Reply (15/15 plans) — completed 2026-05-02
- [x] Phase 12: AI Enrichment Pipeline (9/9 plans) — completed 2026-05-03
- [x] Phase 13: Action Items and Notifications (8/8 plans) — completed 2026-05-04

Full archive: `.planning/milestones/v0.3-ROADMAP.md`

</details>

<details>
<summary>✅ v0.4 — Dashboard (Phase 14) — SHIPPED 2026-05-07</summary>

- [x] Phase 14: Dashboard (8/8 plans) — completed 2026-05-07

</details>

### 🚧 v0.5 — Configurable Sync Depth (In Progress)

**Milestone Goal:** Let Superadmins enable a per-org "configurable sync depth" flag; when enabled, Org Admins choose how far back the initial review backfill goes (1 year / 2 years / all time) at shop creation time — replacing the hard-coded 2-year default.

- [x] **Phase 15: Sync Depth Data Layer and Superadmin Controls** — Model fields, migration, serializer updates, Superadmin org toggle UI, backfill service logic, shop detail display — completed 2026-05-15
- [ ] **Phase 16: Org Admin Shop Creation — Conditional Depth Selector** — Conditional "Review History" dropdown in shop creation form, wired through API to persisted sync_depth

### 📋 v0.6 — Tag Rework & Action Item Quality (Planned)

- [ ] **Phase 17: Tag Rework — ReviewTag Model and Filter** — Replace Review.tags JSONField with a proper ReviewTag relational model; add multi-select tag filter (with search) to the reviews UI; make tag chips clickable to filter
- [ ] **Phase 18: Action Item Duplicate Merge** — User-driven merge of duplicate AI-extracted action items across stores; merged duplicates hidden from list, shown as read-only context in canonical detail; "+N" badge in list view

## Phase Details

### Phase 14: Dashboard
**Goal**: Org Admins, Managers, and Staff can view an analytics dashboard surfacing review-volume KPIs, shop performance rankings, and AI-derived sentiment distribution, filtered by Region, Store, and Date Range — with Redis caching and composite DB indexes ensuring sub-400ms P95 response times.
**Depends on**: Phase 13 (v0.3 Reviews and Action Items complete)
**Requirements**: FILT-01, FILT-02, FILT-03, FILT-04, FILT-05, FILT-06, FILT-07, FILT-08, FILT-09, FILT-10, TOP-01, TOP-02, TOP-03, TOP-04, TOP-05, TOP-06, TOP-07, STORE-01, STORE-02, STORE-03, KPI-01, KPI-02, KPI-03, KPI-04, KPI-05, SENT-01, SENT-02, SENT-03, SENT-04, SENT-05, SENT-06, TECH-01, TECH-02, TECH-03, TECH-04, TECH-05, TECH-06, ERR-01, ERR-02
**Success Criteria** (what must be TRUE):
  1. User can filter the dashboard by Region, Store, and Date Range (7d/30d/90d/custom), and the URL reflects the active filter state so the page is bookmarkable and shareable
  2. User sees a Top Performing Outlets bar chart (multi-shop) or a "Your Store" card (single-shop) — both scoped to date range only, never to Region/Store filters — with threshold-based bar coloring and a hover tooltip showing exact rating and review count
  3. User sees three KPI cards (Total Reviews, Average Rating, Negative Reviews based on AI sentiment) each with independent loading skeletons, empty states, and inline error+retry states
  4. User sees a Sentiment Distribution donut chart with Positive/Neutral/Negative segments, color-coded summary bars, hover tooltips, and a coverage footer when enrichment is below 100%
  5. Out-of-scope Region or Store IDs in URL params return 403 (not silent fallback); custom date ranges over 365 days or with from>to return 400 with a clear error message
  6. All five dashboard widgets load in parallel; each widget is independently cached in Redis for 5 minutes using a scope-aware cache key that includes `accessible_shop_ids` hash to prevent cross-user leakage
  7. User sees branded 404 and 500 error pages matching the platform design system, with navigation actions appropriate to authentication state
**Plans**: 8 plans

Plans:
- [x] 14-01: Indexes + filter validation foundation (3 composite Review indexes, `DashboardFilterParams`, `validate_filter_params()`, `services/cache.py` with `accessible_shop_ids` hash)
- [x] 14-02: Aggregation selectors + query-count tests (`aggregations.py` with 5 selector functions, `CaptureQueriesContext` assertions on all 5)
- [x] 14-03: Dashboard views + URL registration (`DashboardApiView` base + 5 concrete views, `apps/dashboard/urls.py`, INSTALLED_APPS, `test_views.py` for 403/400/cache paths)
- [x] 14-04: Django template view + bootstrap data (dashboard page view, `dashboard.html` with `#dashboard-root` + `<script type="application/json">` bootstrap tags, npm packages added)
- [x] 14-05: React filter bar component (`types.ts`, `api.ts`, `useFilterState.ts`, `FilterBar.tsx` with cascading dropdowns + URL state + sessionStorage)
- [x] 14-06: Bar chart + highlights widgets (`TopPerformingSection.tsx` with recharts `BarChart`, threshold coloring, hover tooltip, click navigation; `PerformanceHighlights.tsx`; `YourStore.tsx` single-shop variant)
- [x] 14-07: KPI cards + sentiment donut widgets (`KpiCards.tsx` with parallel useQuery hooks; `SentimentDonut.tsx` donut chart + summary bars + coverage footer)
- [x] 14-08: Dashboard root + entrypoint + error pages (`DashboardWidget.tsx` with `QueryClientProvider`, `dashboard.tsx` entrypoint, `vite.config.ts` entry, branded 404/500 templates + Django handler config)

### Phase 15: Sync Depth Data Layer and Superadmin Controls

**Goal**: The data model, migration, and service layer for configurable sync depth are in place — Organisation carries an `allow_custom_sync_depth` flag controllable by Superadmin at create and edit time; Shop carries a `sync_depth` field visible on shop detail; and the initial backfill Celery task reads that field to compute the Google API `start_date` (or passes no date filter for all-time).
**Depends on**: Phase 14
**Requirements**: SYNC-01, SYNC-02, SYNC-03, SDEP-02, SDEP-03, BKFL-01, BKFL-02, BKFL-03
**Success Criteria** (what must be TRUE):

  1. Superadmin can check "Allow configurable sync depth" when creating a new organisation, and the setting is persisted and visible on the org detail page
  2. Superadmin can enable or disable "Allow configurable sync depth" on an existing organisation's edit form, and the change takes effect immediately
  3. When an org does not allow custom sync depth, any shop created under it is automatically assigned "Last 2 years" as its review history depth, with no selector shown and no API parameter needed from the client
  4. Shop detail page shows the current review history depth (e.g., "Last 1 year", "Last 2 years", "All time") for every shop
  5. Initial backfill for a "Last 1 year" shop fetches only reviews from the past 12 months; for a "Last 2 years" shop it fetches the past 24 months; for an "All time" shop no date filter is sent to the Google API
**Plans**: 4 plans

Plans:
- [x] 15-01-PLAN.md — Organisation `allow_custom_sync_depth`: model, migration, service, serializers, tests (SYNC-01/02/03)
- [x] 15-02-PLAN.md — Shop `sync_depth` TextChoices field default TWO_YEARS: model, migration, serializer, tests (SDEP-02/03 backend)
- [x] 15-03-PLAN.md — Backfill date filter: thread `start_date` through `fetch_and_persist_reviews` and `_persist_page` (BKFL-01/02/03)
- [x] 15-04-PLAN.md — Frontend: Superadmin toggle in Create/Edit/View Org modals + 'Review history' row in ShopDetailsModal

### Phase 16: Org Admin Shop Creation — Conditional Depth Selector

**Goal**: Org Admins whose organisation has "Allow configurable sync depth" enabled see a "Review History" dropdown in the shop creation form; selecting a depth persists it to the shop and drives the backfill; Org Admins without the flag enabled never see the dropdown and always get the 2-year default.
**Depends on**: Phase 15
**Requirements**: SDEP-01
**Success Criteria** (what must be TRUE):

  1. Org Admin creating a shop when the parent org has "Allow configurable sync depth" enabled sees a "Review History" dropdown with exactly three options: "Last 1 year", "Last 2 years", "All time"
  2. Org Admin creating a shop when the parent org does not have the flag enabled sees no dropdown; the shop is silently created with "Last 2 years" and no user action is required
  3. After shop creation with a custom depth, the shop detail page reflects the chosen depth, confirming the value was stored and returned correctly
**Plans**: 2 plans

Plans:
- [ ] 16-01-PLAN.md — Backend: ShopCreateSerializer sync_depth field, create_shop() kwarg, shop_list view context, template bootstrap tag (SDEP-01)
- [ ] 16-02-PLAN.md — Frontend: types.ts, entrypoint, ShopModals, CreateShopModal conditional Review History dropdown (SDEP-01)

### Phase 17: Tag Rework — ReviewTag Model and Filter

**Goal**: Replace `Review.tags` JSONField with a proper `ReviewTag` relational model; update the AI enrichment pipeline to write rows into the new table; add a multi-select tag filter with search to the reviews list UI; and make tag chips on review rows clickable to filter — giving Org Admins a fast, queryable way to explore reviews by AI-generated topic.
**Depends on**: Phase 16
**Requirements**: TAG-01, TAG-02, TAG-03 (to be added to REQUIREMENTS.md)
**Success Criteria** (what must be TRUE):

  1. A `ReviewTag` model exists with `(id, review_id, label, polarity)`; `Review.tags` JSONField is removed
  2. Review enrichment writes `ReviewTag` rows (title-cased, case-insensitively deduplicated per org) instead of updating the JSONField
  3. The reviews list API returns tags as `[{label, polarity}]` via the new model — same JSON shape as before
  4. A `GET /api/v1/reviews/tags/` endpoint returns `[{label, count}]` scoped to the caller's org (optionally filtered by `?shop=<id>`)
  5. The reviews UI has a Tags multi-select dropdown with search; selecting tags filters the review list (AND semantics); clickable tag chips on rows add to the active filter

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1–5. Superadmin | v1.0 | 24/24 | ✅ Complete | 2026-04-27 |
| 6. Org Admin Shell | v0.2-org-admin | 5/5 | ✅ Complete | 2026-04-27 |
| 7. Regions | v0.2-org-admin | 3/3 | ✅ Complete | 2026-04-28 |
| 8. Shops | v0.2-org-admin | 7/7 | ✅ Complete | 2026-04-29 |
| 9. Team | v0.2-org-admin | 5/5 | ✅ Complete | 2026-04-30 |
| 10. Infrastructure Foundation | v0.3 | 5/5 | ✅ Complete | 2026-05-01 |
| 11. Reviews Fetching, Display, Reply | v0.3 | 15/15 | ✅ Complete | 2026-05-02 |
| 12. AI Enrichment Pipeline | v0.3 | 9/9 | ✅ Complete | 2026-05-03 |
| 13. Action Items and Notifications | v0.3 | 8/8 | ✅ Complete | 2026-05-04 |
| 14. Dashboard | v0.4 | 8/8 | ✅ Complete | 2026-05-07 |
| 15. Sync Depth Data Layer and Superadmin Controls | v0.5 | 4/4 | ✅ Complete | 2026-05-15 |
| 16. Org Admin Shop Creation — Conditional Depth Selector | v0.5 | 0/2 | Not started | - |
| 17. Tag Rework — ReviewTag Model and Filter | v0.6 | 0/? | Not started | - |
