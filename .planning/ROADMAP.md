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

- [x] **Phase 17: Tag Rework — ReviewTag Model and Filter** — Replace Review.tags JSONField with a proper ReviewTag relational model; add multi-select tag filter (with search) to the reviews UI; make tag chips clickable to filter (completed 2026-05-21)
- [x] **Phase 18: Action Item Duplicate Merge** — User-driven merge of duplicate AI-extracted action items across stores; merged duplicates hidden from list, shown as read-only context in canonical detail; "+N" badge in list view (completed 2026-05-22)
- [ ] **Phase 19: AI Reply Generation** — "Generate with AI" button in ReplyComposer with Professional/Friendly tone picker; GPT-4o-mini generates a draft that fills the textarea for user review before submitting

### 📋 v0.7 — AI Safety & Governance (Planned)

- [ ] **Phase 20: AI Guardrails** — Input and output safety controls around all OpenAI calls: OpenAI Moderation API checks, content length truncation, per-org daily token budget (Redis counter), org-level AI enable/disable toggle (Superadmin)
- [ ] **Phase 21: Audit Log Viewer** — Read-only "Activity Log" page in Org Admin UI showing reply and action item audit events; Staff-scoped to accessible shops; cursor-paginated; filters by type, date, and actor

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
**Requirements**: TAG-01, TAG-02, TAG-03
**Success Criteria** (what must be TRUE):

  1. A `ReviewTag` model exists with `(id, review_id, label, polarity)`; `Review.tags` JSONField is removed
  2. Review enrichment writes `ReviewTag` rows (title-cased, case-insensitively deduplicated per org) instead of updating the JSONField
  3. The reviews list API returns tags as `[{label, polarity}]` via the new model — same JSON shape as before
  4. A `GET /api/v1/reviews/tags/` endpoint returns `[{label, count}]` scoped to the caller's org (optionally filtered by `?shop=<id>`)
  5. The reviews UI has a Tags multi-select dropdown with search; selecting tags filters the review list (AND semantics); clickable tag chips on rows add to the active filter
**Plans**: 4 plans

Plans:
- [x] 17-01-PLAN.md — ReviewTag model + migration 0008_reviewtag + factory update (TAG-01)
- [x] 17-02-PLAN.md — Enrichment service write path + ReviewTagSerializer + prefetch_related (TAG-02)
- [x] 17-03-PLAN.md — Tags @action endpoint + ReviewFilterSet tags CharFilter + TAG-03 tests (TAG-03)
- [x] 17-04-PLAN.md — Frontend: TagsFilter dropdown, clickable chips, ReviewManagementWidget wiring (TAG-03)

### Phase 18: Action Item Duplicate Merge

**Goal**: Allow Org Admins to mark action items as duplicates of one another, merging them under a canonical item. Duplicate items are hidden from the default list, the canonical shows a "+N" badge, and a detail section lists all duplicates with links.
**Depends on**: Phase 17
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-16, D-17, D-18, D-19, D-20
**Success Criteria** (what must be TRUE):

  1. Org Admin can select 2+ AI-extracted action items from the list (using checkboxes) and merge them into a single canonical item via a two-step modal (pick primary → confirm)
  2. Merged duplicate items no longer appear in the action items list; the canonical item shows a "+N" badge indicating how many duplicates are merged into it
  3. The canonical item's detail view shows an "Also reported in" section listing each merged duplicate's shop name, source review date, and star rating
  4. Org Admin can mark a single action item as a duplicate of another from the detail modal using "Mark as duplicate of…" which opens a search-as-you-type picker
  5. Merged duplicates are read-only: status changes, assignment, and notes are rejected (400) on duplicate items; only the canonical remains actionable
  6. POST /api/v1/action-items/merge/ is restricted to Org Admin (Staff receives 403); service validates same org, same scope (SHOP/BRAND), source=AI, and non-chained primary
**Plans**: 4 plans

Plans:

- [x] 18-01-PLAN.md — ActionItem canonical FK + migration 0003_actionitem_canonical + model tests (D-01/D-02/D-04)
- [x] 18-02-PLAN.md — Backend: merge service + lifecycle guards + selector filter/annotation + serializers + merge API endpoint + full test suite (D-03/D-05–D-17)
- [x] 18-03-PLAN.md — Frontend list: DataTable checkbox extension + ActionItemTable + MergeModal + toolbar + types/api (D-11/D-18/D-20)
- [x] 18-04-PLAN.md — Frontend detail: DuplicatePickerModal + "Also reported in" + "Mark as duplicate of…" (D-12/D-13/D-19/D-20)


### Phase 19: AI Reply Generation

**Goal**: Org Admins and Staff can generate an AI-drafted reply inside the ReplyComposer by clicking "Generate with AI", selecting Professional or Friendly tone, and reviewing the draft before submitting it manually — powered by GPT-4o-mini with full AiUsageLog cost tracking.
**Depends on**: Phase 18
**Requirements**: D-01 through D-25 (from 19-CONTEXT.md)
**Success Criteria** (what must be TRUE):

  1. "Generate with AI" button appears in the ReplyComposer toolbar to the left of "Use template"
  2. Clicking Generate with an empty textarea shows Professional / Friendly tone pills; with non-empty textarea shows a confirmation row requiring the user to confirm overwrite
  3. Clicking a tone pill calls POST /api/v1/reviews/{id}/generate-reply/ and fills the textarea with the returned draft on success
  4. Loading state shows a spinner on the active pill; both pills disabled during load
  5. On error (any), an inline error message appears (reusing the existing errorMessage slot); pills collapse
  6. Every call writes one AiUsageLog row with request_type="reply_generation" and estimated_cost_usd calculated from AiPricing
  7. Endpoint is throttled at 10/minute per user; invalid tone returns 400; OpenAI failure returns 502
**Plans**: 3 plans

Plans:

Wave 1:

- [x] 19-01-PLAN.md — Backend service layer: REPLY_GENERATION_PROMPT_VERSION, build_reply_generation_messages(), call_openai_reply_generation(), generate_reply_draft() + AiUsageLog write + tests (D-04/D-05/D-06/D-07/D-08/D-14/D-15/D-16)

Wave 2 (blocked on Wave 1 completion):

- [ ] 19-02-PLAN.md — API endpoint: GenerateReplySerializer, generate_reply @action on ReviewViewSet, generate_reply throttle rate, endpoint tests (D-09/D-10/D-11/D-12/D-13/D-17/D-18)

- [ ] 19-03-PLAN.md — Frontend: generateReply() in api.ts, generator button + tone pills + confirmation row + state machine + focus management in ReplyComposer.tsx (D-19/D-20/D-21/D-22/D-23/D-24/D-25)

Cross-cutting constraints: every OpenAI call MUST write one AiUsageLog row (CLAUDE.md §14); select_related("shop__organisation") MUST be on ReviewViewSet.get_queryset() (CLAUDE.md §6).

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
| 17. Tag Rework — ReviewTag Model and Filter | v0.6 | 4/4 | Complete    | 2026-05-21 |
| 18. Action Item Duplicate Merge | v0.6 | 4/4 | Complete    | 2026-05-22 |
| 19. AI Reply Generation | v0.6 | 1/3 | In Progress|  |
