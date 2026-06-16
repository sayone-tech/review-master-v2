# Roadmap: Multi-Tenant Review Management Platform

## Milestones

- ✅ **v1.0 — Superadmin Module** — Phases 1–5, 24 plans, 52/52 requirements, shipped 2026-04-27 → [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v0.2-org-admin — Organisation Admin Module** — Phases 6–9, 20 plans, 57/57 requirements, shipped 2026-04-30 → [archive](milestones/v0.2-org-admin-ROADMAP.md)
- ✅ **v0.3 — Reviews and Action Items** — Phases 10–13, 37 plans, 77/77 requirements, shipped 2026-05-05 → [archive](milestones/v0.3-ROADMAP.md)
- ✅ **v0.4 — Dashboard** — Phase 14, 8 plans, 38/38 requirements, shipped 2026-05-07
- ✅ **v0.5 — Configurable Sync Depth** — Phases 15–16, 6 plans, 9/9 requirements, shipped 2026-05-16 → [archive](milestones/v0.5-ROADMAP.md)
- ✅ **v0.6 — Tag Rework & Action Item Quality** — Phases 17–19, 11 plans, shipped 2026-05-22 → [archive](milestones/v0.6-ROADMAP.md)
- ✅ **v0.7 — AI Safety & Governance** — Phases 20–21, 12 plans, shipped 2026-05-24 → [archive](milestones/v0.7-ROADMAP.md)
- 🔵 **v0.8 — Canonical Tag System** — Phases 22–26, 25/25 requirements, in planning

> 🚀 **Web Beta 1 (`web-beta-1`)** — v0.7 marked the close of the first
> web beta. v0.8 reopens web feature work for the canonical tag system
> — a data-quality milestone that normalises AI-generated review tags
> into a self-organising, per-org canonical vocabulary so tag analytics
> become reliable. Tag `web-beta-1` still points at the v0.7 release for
> rollback / reference.

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

### 🔵 v0.8 — Canonical Tag System (Phases 22–26) — IN PLANNING

- [x] **Phase 22: Canonical Tag Foundation & Mapping Pipeline** — `OrgCanonicalTag` model + nullable `canonical_tag` FK on `ReviewTag` + migration; canonical lookup/insert folded into the single GPT call and post-enrichment atomic block; English-only tags; one `AiUsageLog` row per call; global OpenAI rate limit. (completed 2026-06-10)
- [x] **Phase 23: Four-Step Initial Sync, Seeding & Queue Split** — Fetch → Build Vocabulary → Enrich → Finalising progress; sequential first-50 seed phase; parallel bulk phase; finalising dedup/backfill; daily incremental sync through the pipeline; split `ai-enrichment-high`/`-low` + `tag-merge` queues. (completed 2026-06-11)
- [x] **Phase 24: Polarity Auto-Reclassification** — GPT-assigned three-type polarity at tag creation; weekly DB-only Beat job flips `always_*` → `mixed` at the 15% / 30-day threshold; reclassification logged and visible. (completed 2026-06-16)
- [x] **Phase 25: Org Admin Tag Management & Dashboard Polarity** — Tags page (`/admin/org/tags/`) with sortable, query-bounded list, inline rename, and merge via `tag-merge` Celery task with HTTP-polled progress; dashboard polarity split for `mixed` tags. (completed 2026-06-16)
- [~] **Phase 26: Superadmin Data Reset & Re-Sync** — **DEFERRED (pre-launch, 2026-06-16).** One-time pre-production hard wipe of a single org's Review / AiUsageLog / ActionItem / OrgCanonicalTag rows + per-store sync-state clear; Org Admin re-runs the full four-step sync. Parked while there is no production deployment — dev resets use `manage.py flush` / DB recreate + `make seed` / Redis `flushdb`. Revisit before go-live.

---

🚀 **Web Beta 1 closed 2026-05-24.** v0.8 (canonical tag system) reopens
web feature work; mobile app remains the milestone after v0.8.

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

---

### Phase 22: Canonical Tag Foundation & Mapping Pipeline

**Goal**: Each organisation accrues a self-organising per-org canonical tag vocabulary that is built and evolved entirely inside the existing single GPT enrichment call — so every newly enriched review's tags are mapped to a stable canonical label without any extra API call, vector DB, or cost-per-call regression.
**Depends on**: Phase 21 (v0.7 complete); builds directly on the v0.3 enrichment pipeline (`apps/integrations/openai/parser.py`, `prompts.py`, `apps/reviews/services/enrichment.py`) and the v0.6 relational `ReviewTag` model.
**Requirements**: CTAG-01, CTAG-02, CTAG-03, CTAG-04, CTAG-05, CTAG-06, CTAG-07, CTAG-08, QUEUE-02
**Success Criteria** (what must be TRUE):

  1. A new `OrgCanonicalTag` row (Title Case label ≤3 words, `polarity_type`, `review_count`, timestamps, direct `organisation` FK, unique on `(organisation, label)`) is created the first time GPT proposes a new canonical label for that org, and re-used (with `review_count` incremented) on subsequent matches — all inside the existing enrichment `transaction.atomic()` block.
  2. After enrichment, every `ReviewTag` row has its new nullable `canonical_tag` FK populated with the matched/created `OrgCanonicalTag` (matched → reuse, new → insert), resolving the org via `review.organisation_id`.
  3. The org's current canonical vocabulary is injected into the single enrichment prompt, GPT maps each tag to an existing canonical label or proposes a new one in that same call, and all tags and action items come back in English regardless of the review's source language.
  4. Each enrichment call still writes exactly one `AiUsageLog` row — canonicalisation adds no separate OpenAI call — and the enrichment task enforces a global, configurable Celery rate limit (default ~500/min) that holds across all workers.
  5. Reviews enriched before this phase remain valid and queryable with a null `canonical_tag` (backward compatible); the migration adds the model and FK without backfilling or breaking existing rows.

**Plans**: 6 plans

Plans:
**Wave 1**

- [x] 22-01-PLAN.md — Data model: OrgCanonicalTag + nullable ReviewTag.canonical_tag FK + migration (CTAG-01/02/08)
- [x] 22-02-PLAN.md — Settings: CANONICAL_VOCAB_INJECT_LIMIT + ENRICHMENT_RATE_LIMIT (D-02, QUEUE-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 22-03-PLAN.md — Parser schema: Tag.canonical + nullable polarity_type + normalizer (CTAG-04/05)
- [x] 22-04-PLAN.md — Prompt vocab injection + get_org_vocabulary selector + version bump (CTAG-03/05)
- [x] 22-06-PLAN.md — Per-worker rate_limit on enrich_review_task (QUEUE-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 22-05-PLAN.md — Enrichment fold-in: canonical FK resolution in _persist_success (CTAG-06/07)

### Phase 23: Four-Step Initial Sync, Seeding & Queue Split

**Goal**: A store's initial sync visibly progresses through four named steps and seeds the org's canonical vocabulary in a careful sequential-then-parallel order, so the vocabulary is coherent from the first 50 reviews onward; daily incremental sync feeds new reviews through the same pipeline; and enrichment/merge work is isolated on dedicated Celery queues.
**Depends on**: Phase 22 (canonical model, FK, and mapping pipeline must exist)
**Requirements**: SEED-01, SEED-02, SEED-03, SEED-04, DSYNC-01, QUEUE-01
**Success Criteria** (what must be TRUE):

  1. During an initial sync, the user sees four progress steps per store — Fetching Reviews → Building Tag Vocabulary → AI Enrichment → Finalising — each with its own progress text (extending the existing `SyncProgressConsumer` from two to four stages; still no new WebSocket consumer).
  2. The seed phase processes the first 50 reviews sequentially (all of them if fewer than 50), updating the canonical vocabulary before enriching the next review, so early canonical tags stabilise before the bulk phase.
  3. The bulk phase enriches the remaining reviews in parallel against the current vocabulary and can still add new canonical tags; the finalising pass resolves residual duplicate tags by string match and backfills `canonical_tag` on any stragglers.
  4. Daily incremental sync enriches new reviews through the same canonical pipeline (vocabulary injected, new canonical tags auto-added with no approval step) on the low-priority enrichment queue.
  5. Enrichment work is split across `ai-enrichment-high` (initial sync) and `ai-enrichment-low` (daily sync), and a dedicated `tag-merge` queue exists and is wired through routes, `CELERY_QUEUE_NAMES`, and worker `-Q` args.

**Plans**: 4 plans
**UI hint**: yes

Plans:
**Wave 1**

- [x] 23-01-PLAN.md — Queue split + SEED_PHASE_SIZE/OPENAI_GLOBAL_RATE_LIMIT settings + global OpenAI Redis token bucket (QUEUE-01, DSYNC-01)
- [x] 23-04-PLAN.md — Four-step ProgressModal + TopbarSyncIndicator UI extension (SEED-01)

**Wave 2** *(blocked on Wave 1)*

- [x] 23-02-PLAN.md — Finalising pass: case-insensitive dedup merge + straggler backfill + review_count refresh on tag-merge queue (SEED-04)

**Wave 3** *(blocked on Wave 2)*

- [x] 23-03-PLAN.md — Four-phase initial backfill (seed/bulk/finalise dispatch) + incremental ai-enrichment-low routing + global token-bucket guard (SEED-01/02/03, DSYNC-01, QUEUE-01)

### Phase 24: Polarity Auto-Reclassification

**Goal**: Canonical tags carry an accurate, self-maintaining polarity type so dashboards and analytics can trust whether a tag is consistently positive, consistently negative, or genuinely mixed — without any manual curation or extra GPT calls.
**Depends on**: Phase 22 (canonical tags assigned a polarity at creation); benefits from Phase 23 review volume but does not require it
**Requirements**: POL-01, POL-02, POL-03
**Success Criteria** (what must be TRUE):

  1. Every new canonical tag is assigned one of `always_positive` / `always_negative` / `mixed` by GPT at creation time.
  2. A weekly Celery Beat job reclassifies an `always_*` canonical tag to `mixed` when the opposite polarity exceeds 15% of its reviews over the last 30 days, using pure DB aggregation with no GPT call.
  3. Reclassification events are logged, and the current `polarity_type` is visible on the tag list page.

**Plans**: 2 plans

Plans:
**Wave 1**

- [x] 24-01-PLAN.md — Settings (POLARITY_RECLASSIFY_THRESHOLD/WINDOW_DAYS/MIN_REVIEWS) + default-queue route + nullable polarity_reclassified_at field/migration 0012 + Wave-0 failing test suite & POL-01 re-confirmation (POL-01, POL-02)

**Wave 2** *(blocked on Wave 1)*

- [x] 24-02-PLAN.md — run_polarity_reclassification service (single-pass aggregate, one-way flip to mixed, atomic AuditLog) + thin weekly Beat task + CrontabSchedule seed migration 0013 (POL-02, POL-03)

### Phase 25: Org Admin Tag Management & Dashboard Polarity

**Goal**: Org Admins and Managers can directly curate their org's canonical vocabulary — viewing, renaming, and merging tags with safe, observable, reversible-where-possible operations — and the dashboard presents tag data with polarity-aware splits, so the self-organising vocabulary stays clean and the analytics reflect it.
**Depends on**: Phase 22 (canonical model + mappings), Phase 23 (`tag-merge` queue), Phase 24 (`polarity_type` populated for badge display)
**Requirements**: TMGT-01, TMGT-02, TMGT-03, TMGT-04, TMGT-05, TMGT-06, TDASH-01, TDASH-02
**Success Criteria** (what must be TRUE):

  1. Org Admin and Manager can reach a Tags page at `/admin/org/tags/` (sidebar under Settings) showing Label, Polarity Type badge, Review Count, and First Seen — sortable by column, paginated, on a query-count-bounded endpoint; Staff cannot reach it.
  2. A canonical tag can be renamed inline (1–100 chars, unique within the org); saving updates `OrgCanonicalTag.label` and all mapped `ReviewTag` rows synchronously.
  3. A canonical tag can be merged into another via a modal with a searchable target picker and an explicit "re-maps N reviews, cannot be undone" warning; the merge runs as a batched `merge_canonical_tags` Celery task on the `tag-merge` queue under a per-org lock, re-pointing all reviews, deleting the source tag, combining `review_count`, and posting a completion notification.
  4. Merge progress is delivered via HTTP polling — an in-progress bar with dismiss, state that survives page reload, a completion toast, and a failure path that rolls back partial updates (no new WebSocket consumer).
  5. Dashboard tag charts show a simple count for `always_positive` / `always_negative` canonical tags and a positive/negative split for `mixed` tags, and all canonical aggregation queries include only reviews where `canonical_tag` is set.

**Plans**: 4 plans
**UI hint**: yes

Plans:
**Wave 1**

- [x] 25-01-PLAN.md — Backend data + rename/merge services + merge_canonical_tags_task (tag-merge queue) + TagMergeJob model + TAG_MERGE_COMPLETE (TMGT-03/05/06)
- [x] 25-04-PLAN.md — Dashboard polarity: dashboard_tag_polarity selector + view + TagPolarityChart stacked bar (TDASH-01/02)

**Wave 2** *(blocked on 25-01)*

- [x] 25-02-PLAN.md — Tag-management API: viewsets (list/rename/merge), tag-merge-job poll/dismiss, ORG_ADMIN tags page + sidebar (TMGT-01/02/04/05/06)

**Wave 3** *(blocked on 25-02)*

- [x] 25-03-PLAN.md — Tag-management React widget: sortable table, inline rename, merge modal, 2s HTTP-polled progress banner (TMGT-02/03/04/06)

### Phase 26: Superadmin Data Reset & Re-Sync — **DEFERRED (pre-launch, 2026-06-16)**

> **Deferred while there is no production deployment.** The feature's premise — needing an
> in-app Superadmin path to hard-delete a *live* org's data despite the §11 soft-delete rule —
> does not apply during testing, where data is reset directly (`manage.py flush` / DB
> recreate + `make seed`, Redis `flushdb`). Building it now would be over-engineering.
> Revisit before go-live (the pre-production 56-store brand re-sync is the likely trigger).
> If a repeatable testing wipe is wanted sooner, a thin `manage.py reset_org_data <org_id>`
> command is the minimal stand-in — far less than the full phase. v0.8 ships as Phases 22–25.

**Goal**: A Superadmin can fully reset one organisation's review data and sync state in a single deliberate, documented pre-production operation, so the pre-production 56-store brand can be re-synced cleanly through the full canonical pipeline and the whole milestone is validated end-to-end on real data.
**Depends on**: Phases 22–25 (the full canonical pipeline + four-step sync must exist before a reset-and-re-sync proves value)
**Requirements**: RESET-01, RESET-02, RESET-03
**Success Criteria** (what must be TRUE):

  1. A Superadmin can trigger a full data reset for one organisation that hard-deletes its Review, AiUsageLog, ActionItem, and OrgCanonicalTag rows — a documented one-time pre-production exception to the §11 soft-delete rule.
  2. The reset clears each store's sync state (Redis progress snapshot + `Shop.connection_status`) so stores read as "Not synced".
  3. After reset, the Org Admin can re-sync each store through the normal flow, running the full four-step initial sync and rebuilding the canonical vocabulary from scratch.

**Plans**: TBD

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
| 22. Canonical Tag Foundation & Mapping Pipeline | v0.8 | 6/6 | Complete    | 2026-06-10 |
| 23. Four-Step Initial Sync, Seeding & Queue Split | v0.8 | 4/4 | Complete   | 2026-06-11 |
| 24. Polarity Auto-Reclassification | v0.8 | 2/2 | Complete    | 2026-06-16 |
| 25. Org Admin Tag Management & Dashboard Polarity | v0.8 | 4/4 | Complete   | 2026-06-16 |
| 26. Superadmin Data Reset & Re-Sync | v0.8 | 0/TBD | ⬜ Not started | - |
