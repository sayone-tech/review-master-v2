# Roadmap: Multi-Tenant Review Management Platform

## Milestones

- ✅ **v1.0 — Superadmin Module** — Phases 1–5, 24 plans, 52/52 requirements, shipped 2026-04-27 → [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v0.2-org-admin — Organisation Admin Module** — Phases 6–9, 20 plans, 57/57 requirements, shipped 2026-04-30 → [archive](milestones/v0.2-org-admin-ROADMAP.md)
- ✅ **v0.3 — Reviews and Action Items** — Phases 10–13, 37 plans, 77/77 requirements, shipped 2026-05-05 → [archive](milestones/v0.3-ROADMAP.md)
- ✅ **v0.4 — Dashboard** — Phase 14, 8 plans, 38/38 requirements, shipped 2026-05-07
- ✅ **v0.5 — Configurable Sync Depth** — Phases 15–16, 6 plans, 9/9 requirements, shipped 2026-05-16 → [archive](milestones/v0.5-ROADMAP.md)
- ✅ **v0.6 — Tag Rework & Action Item Quality** — Phases 17–19, 11 plans, shipped 2026-05-22 → [archive](milestones/v0.6-ROADMAP.md)
- 🚧 **v0.7 — AI Safety & Governance** — Phases 20–21 (in progress)

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

### 🚧 v0.7 — AI Safety & Governance (In Progress)

- [x] **Phase 20: AI Guardrails** — Input and output safety controls around all OpenAI calls: OpenAI Moderation API checks (category-aware blocking on 5 high-severity categories, fail-open with 1 retry on API errors), content length truncation (env-configurable `OPENAI_REVIEW_TEXT_MAX_CHARS`, default 4000), 300-word output cap with sentence-boundary truncation, shared HTTP 422 mapping for moderated content. Per-org token budget + Superadmin AI toggle deferred to a future pricing phase. (completed 2026-05-23)
- [x] **Phase 21: Audit Log Viewer** — Read-only "Activity Log" page in Org Admin UI showing reply and action item audit events; Staff-scoped to accessible shops + SHOP-scope action items only (CLAUDE.md §9 layer-1 defence); cursor-paginated (Prev/Next, no page numbers); filters by type/date/actor with URL-synced state for bookmarkability. (completed 2026-05-24; 6 visual UI checks pending manual verification)

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

> **Phases 15–19** are shipped and archived. Full details in
> [`milestones/v0.5-ROADMAP.md`](milestones/v0.5-ROADMAP.md) and
> [`milestones/v0.6-ROADMAP.md`](milestones/v0.6-ROADMAP.md).

### Phase 20: AI Guardrails

**Goal**: Add input/output safety controls around all OpenAI calls — Moderation API checks (category-aware blocking) and content length truncation. MVP scope: NO token budget, NO org AI toggle (deferred to a future pricing phase).
**Depends on**: Phase 19
**Requirements**: D-01 through D-33 (from 20-CONTEXT.md)
**Success Criteria** (what must be TRUE):

  1. Review text >4000 chars (env-configurable) is truncated with "…[truncated]" before any OpenAI call
  2. Review text flagged by high-severity moderation categories (sexual_minors, hate_threatening, violence_graphic, self_harm_intent, self_harm_instructions — underscore form) blocks the OpenAI enrichment call and sets Review.enrichment_status=FAILED with enrichment_error_code="content_moderated"
  3. AI reply generation: input moderation blocks before OpenAI; output moderation blocks before the draft reaches the user; replies >300 words are truncated at sentence boundary with " (Please review and complete before sending.)" suffix
  4. ContentModeratedException maps to HTTP 422 with canonical body {code: "content_moderated", detail: "AI reply isn't available for this review. Please write your reply manually."}
  5. Moderation API outage: fail-open with one retry after 1s; ERROR log on second failure
  6. AiUsageLog rows for moderated events: input-moderated → status=MODERATED + zero tokens; output-moderated → status=MODERATED + real tokens + error_code="output_moderated"
  7. retry_failed_enrichments_task excludes rows with enrichment_error_code="content_moderated"
  8. All AiUsageLog writes for moderation events happen OUTSIDE any transaction.atomic() block (audit-row survival on rollback)
**Plans**: 8 plans

Plans:

Wave 1 (parallel — foundations):

- [ ] 20-01-PLAN.md — Settings: OPENAI_REVIEW_TEXT_MAX_CHARS env-configurable (D-03/D-21) + .env.example
- [ ] 20-02-PLAN.md — ContentModeratedException(OpenAIError) in exceptions.py (D-16/D-32)
- [ ] 20-03-PLAN.md — Schema: AiUsageLog.Status.MODERATED enum + Review.enrichment_error_code field + two migrations (D-20/D-28/D-31)

Wave 2 (depends on Wave 1):

- [ ] 20-04-PLAN.md — apps/integrations/openai/guardrails.py: BLOCKING_MODERATION_CATEGORIES (underscore form), _moderate_with_retry (fail-open D-24), moderate_input, moderate_output, truncate_reply_at_sentence, _persist_moderated_log + full unit tests (D-01/D-02/D-03/D-04/D-07/D-08/D-13/D-21/D-22/D-23/D-24/D-30/D-33)

Wave 3 (depends on Wave 2):

- [ ] 20-05-PLAN.md — Service wiring: enrich_review calls moderate_input outside atomic; _persist_moderated helper sets enrichment_error_code; tests (D-04/D-15/D-20/D-28/D-29/D-31/D-33)
- [ ] 20-06-PLAN.md — Service wiring: generate_reply_draft calls moderate_input → OpenAI → moderate_output → truncate_reply_at_sentence; output-moderation AiUsageLog carries real tokens; tests (D-07/D-08/D-14/D-22/D-29/D-33)

Wave 4 (depends on Wave 3):

- [ ] 20-07-PLAN.md — View: ReviewViewSet.generate_reply catches ContentModeratedException → HTTP 422 with canonical D-26 copy; tests (D-16/D-26/D-32)
- [ ] 20-08-PLAN.md — Retry task: retry_failed_enrichments_task .exclude(enrichment_error_code="content_moderated"); tests (D-25/D-31)

Cross-cutting constraints: BLOCKING_MODERATION_CATEGORIES uses underscore form (D-30, RESEARCH.md Pitfall 1); all moderate_* calls must be outside transaction.atomic() (D-33, RESEARCH.md Pitfall 3); never log review text at WARNING+ (CLAUDE.md §21); MODERATED enum value is uppercase string (D-28, RESEARCH.md Pitfall 2).

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

### Phase 21: Audit Log Viewer

**Goal**: Org Admins and Staff can view a read-only "Activity Log" page showing reply and action item audit events scoped to their organisation; Staff Admins see only entries from their accessible shops; the list is cursor-paginated and filterable by type, date range, and actor.
**Depends on**: Phase 18 (action_item.merged AuditLog write), Phase 19 (AuditLog model in place)
**Requirements**: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07, REQ-08, REQ-09
**Success Criteria** (what must be TRUE):

  1. GET /api/v1/audit-logs/ returns cursor-paginated results scoped to the caller's org; Staff receives only entries from their accessible shops and SHOP-scope action items
  2. Response has next/previous cursor URLs, no before_data field, and includes actor_name (null for system actions)
  3. Filters work: entity_type (review/action_item), actor (user ID or "system"), date_from/date_to (ISO date), shop
  4. Superadmin receives 403; unauthenticated receives 401; throttle enforced at 120/minute
  5. "Activity Log" nav item appears in sidebar_org.html for both ORG_ADMIN and STAFF_ADMIN
  6. /admin/org/activity-log/ renders the Django template with React widget at #audit-log-root
  7. React widget shows 5-column table with expandable JSON detail panel, Type pills (Reply/Action Item), cursor pagination, and filter bar with 30d default date preset
**Plans**: 4 plans

Wave 1 (parallel):

- [ ] 21-01-PLAN.md — Selectors (list_audit_logs_for_org/staff), AuditLogReadSerializer, AuditLogCursorPagination, AuditLogFilterSet, selector tests (REQ-01/REQ-02/REQ-03/REQ-04)
- [ ] 21-02-PLAN.md — AuditLogViewSet in apps/common/views.py + audit_log_view + URL registration + settings throttle + API tests (REQ-01/REQ-02/REQ-03/REQ-04/REQ-05/REQ-09)

Wave 2 (depends on Wave 1):

- [ ] 21-03-PLAN.md — Django template templates/org-admin/audit-log.html + sidebar Activity Log nav item (REQ-06/REQ-07/REQ-08)
- [ ] 21-04-PLAN.md — React widget: types, utils, api, useAuditLog hook, TypePill, AuditLogFilters, AuditLogTable, AuditLogWidget + vite entrypoint (REQ-07/REQ-08)

Cross-cutting constraints: IsOrgScoped permission (NOT IsStaffAdmin — does not exist); AuditLogCursorPagination.ordering = ("-created_at", "id") tiebreaker; AuditLogFactory imported from apps/reviews/tests/factories.py (already exists); templates/org-admin/ directory must be created; after_data.merged_ids.length used for count — no count key on action_item.merged rows.
