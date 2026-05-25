# Roadmap: Multi-Tenant Review Management Platform

## Milestones

- ✅ **v1.0 — Superadmin Module** — Phases 1–5, 24 plans, 52/52 requirements, shipped 2026-04-27 → [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v0.2-org-admin — Organisation Admin Module** — Phases 6–9, 20 plans, 57/57 requirements, shipped 2026-04-30 → [archive](milestones/v0.2-org-admin-ROADMAP.md)
- ✅ **v0.3 — Reviews and Action Items** — Phases 10–13, 37 plans, 77/77 requirements, shipped 2026-05-05 → [archive](milestones/v0.3-ROADMAP.md)
- ✅ **v0.4 — Dashboard** — Phase 14, 8 plans, 38/38 requirements, shipped 2026-05-07
- ✅ **v0.5 — Configurable Sync Depth** — Phases 15–16, 6 plans, 9/9 requirements, shipped 2026-05-16 → [archive](milestones/v0.5-ROADMAP.md)
- ✅ **v0.6 — Tag Rework & Action Item Quality** — Phases 17–19, 11 plans, shipped 2026-05-22 → [archive](milestones/v0.6-ROADMAP.md)
- ✅ **v0.7 — AI Safety & Governance** — Phases 20–21, 12 plans, shipped 2026-05-24 → [archive](milestones/v0.7-ROADMAP.md)

> 🚀 **Web Beta 1 (`web-beta-1`)** — v0.7 marks the close of the first
> web beta. The web app is on **maintenance footing** as of
> 2026-05-24; no new feature work until the mobile launch. Tag
> `web-beta-1` points at this release for rollback / reference.

## Next Up

- 📱 **Mobile app** — scope, requirements, and roadmap to be defined
  in a new milestone (`/gsd-new-milestone` once direction is clear).

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

<details>
<summary>✅ v0.5 — Configurable Sync Depth (Phases 15–16) — SHIPPED 2026-05-16</summary>

- [x] Phase 15: Sync Depth Data Layer and Superadmin Controls (4/4 plans) — completed 2026-05-15
- [x] Phase 16: Org Admin Shop Creation — Conditional Depth Selector (2/2 plans) — completed 2026-05-16

Full archive: `.planning/milestones/v0.5-ROADMAP.md`

</details>

<details>
<summary>✅ v0.6 — Tag Rework & Action Item Quality (Phases 17–19) — SHIPPED 2026-05-22</summary>

- [x] Phase 17: Tag Rework — ReviewTag Model and Filter (4/4 plans) — completed 2026-05-21
- [x] Phase 18: Action Item Duplicate Merge (4/4 plans) — completed 2026-05-22
- [x] Phase 19: AI Reply Generation (3/3 plans) — completed 2026-05-22

Full archive: `.planning/milestones/v0.6-ROADMAP.md`

</details>

<details>
<summary>✅ v0.7 — AI Safety & Governance (Phases 20–21) — SHIPPED 2026-05-24</summary>

- [x] Phase 20: AI Guardrails (8/8 plans) — completed 2026-05-23
- [x] Phase 21: Audit Log Viewer (4/4 plans) — completed 2026-05-24

Full archive: `.planning/milestones/v0.7-ROADMAP.md`

</details>

---

🚀 **Web Beta 1 closed here (2026-05-24).** Web feature work paused;
mobile app is the next focus.

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

> **Phases 15–21** are shipped and archived. Full details in
> [`milestones/v0.5-ROADMAP.md`](milestones/v0.5-ROADMAP.md),
> [`milestones/v0.6-ROADMAP.md`](milestones/v0.6-ROADMAP.md), and
> [`milestones/v0.7-ROADMAP.md`](milestones/v0.7-ROADMAP.md).

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
| 16. Org Admin Shop Creation — Conditional Depth Selector | v0.5 | 2/2 | ✅ Complete | 2026-05-16 |
| 17. Tag Rework — ReviewTag Model and Filter | v0.6 | 4/4 | ✅ Complete | 2026-05-21 |
| 18. Action Item Duplicate Merge | v0.6 | 4/4 | ✅ Complete | 2026-05-22 |
| 19. AI Reply Generation | v0.6 | 3/3 | ✅ Complete | 2026-05-22 |
| 20. AI Guardrails | v0.7 | 8/8 | ✅ Complete | 2026-05-23 |
| 21. Audit Log Viewer | v0.7 | 4/4 | ✅ Complete | 2026-05-24 |
