# Roadmap: Multi-Tenant Review Management Platform

## Milestones

- [x] **v1.0 — Superadmin Module** — Phases 1–5, 24 plans, 52/52 requirements, shipped 2026-04-27 → [archive](milestones/v1.0-ROADMAP.md)
- [x] **v0.2-org-admin — Organisation Admin Module** — Phases 6–9, 17 plans, 57/57 requirements, shipped 2026-04-30 → [archive](milestones/v0.2-org-admin-ROADMAP.md)
- [ ] **v0.3 — Reviews and Action Items** — Phases 10–13, 68 requirements, in progress

## Phases

### ✅ v0.2-org-admin — Organisation Admin Module (Phases 6–9) — SHIPPED 2026-04-30

- [x] Phase 6: Org Admin Shell (5/5 plans) — completed 2026-04-27
- [x] Phase 7: Regions (3/3 plans) — completed 2026-04-28
- [x] Phase 8: Shops (7/7 plans) — completed 2026-04-29
- [x] Phase 9: Team (5/5 plans) — completed 2026-04-30

Full archive: `.planning/milestones/v0.2-org-admin-ROADMAP.md`

### ✅ v1.0 — Superadmin Module (Phases 1–5) — SHIPPED 2026-04-27

5 phases, 24 plans, 52/52 requirements. Full archive: `.planning/milestones/v1.0-ROADMAP.md`

### 🚧 v0.3 — Reviews and Action Items (In Progress)

**Milestone Goal:** Org Admins and Staff can view, respond to, and action Google Business Profile reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.

- [x] **Phase 10: Infrastructure Foundation** — Celery, Beat, Channels, Redis lock helper, retry/backoff utilities — completed 2026-05-01
- [ ] **Phase 11: Reviews Fetching, Display, Reply** — Google review sync, real-time progress UI, Reviews list with filters and reply
- [ ] **Phase 12: AI Enrichment Pipeline** — OpenAI GPT-4o-mini enrichment, AiUsageLog, AiPricing, LangSmith tracing
- [ ] **Phase 13: Action Items and Notifications** — Action Items module, manual creation, status workflow, notification bell

## Phase Details

### Phase 10: Infrastructure Foundation
**Goal**: The async runtime is live — Celery workers, Beat scheduler, Channels WebSocket layer, Redis lock helper, and retry utilities are all operational and observable
**Depends on**: Phase 9 (v0.2-org-admin complete)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, INFRA-08, INFRA-09, INFRA-10, INFRA-11
**Success Criteria** (what must be TRUE):
  1. A Celery task enqueued on `google-sync` or `ai-enrichment` completes successfully within 30 seconds in CI smoke test
  2. A WebSocket connection to `/ws/sync-progress/` is accepted for authenticated users and rejected with code 4403 for unauthenticated or cross-tenant requests
  3. A task that fails three times with exponential backoff is marked permanently failed; Sentry captures the traceback and task arguments
  4. The Redis lock helper prevents a second task from acquiring the same lock while the first holds it, verified by a unit test
**Plans**: 5 plans
  - [x] 10-01-PLAN.md — Celery app, settings, smoke task, worker compose service (INFRA-01, INFRA-04, INFRA-07)
  - [x] 10-02-PLAN.md — Beat scheduler + Flower compose services + Makefile targets (INFRA-02, INFRA-03)
  - [x] 10-03-PLAN.md — Channels ASGI + SyncProgressConsumer + reviews/action_items/notifications app skeletons (INFRA-08, INFRA-09)
  - [x] 10-04-PLAN.md — Redis distributed_lock helper + tenacity with_retry decorator (INFRA-05, INFRA-10, INFRA-11)
  - [x] 10-05-PLAN.md — Sentry integration with PII scrubber + CI smoke test gate (INFRA-06, INFRA-07)

### Phase 11: Reviews Fetching, Display, Reply
**Goal**: Org Admins and Staff can see all their Google reviews in a filterable, searchable list — with live sync progress after OAuth, a reply composer, and reliable background fetching every 6 hours
**Depends on**: Phase 10
**Requirements**: SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06, SYNC-07, SYNC-08, SYNC-09, SYNC-10, PROG-01, PROG-02, PROG-03, PROG-04, PROG-05, PROG-06, PROG-07, PROG-08, PROG-09, PROG-10, REVW-01, REVW-02, REVW-03, REVW-04, REVW-05, REVW-06, REVW-07, REVW-08, REVW-09, REVW-10, REVW-11, REVW-12, REVW-13, REVW-14
**Success Criteria** (what must be TRUE):
  1. After completing Google OAuth for a shop, the Progress Modal opens automatically showing live fetch progress; the Org Admin can click "Run in background" and the top-bar indicator continues tracking all syncing shops
  2. The Reviews list at `/admin/org/reviews/` renders all reviews with filters (Store, Rating, Sentiment, Reply Status, Date, Search) applying additively; Staff users see only reviews for their assigned shops
  3. An Org Admin or Staff member can submit a reply via the inline composer; the reply is posted to Google synchronously and the composer is replaced with the posted reply view on success
  4. Re-running sync for a shop updates changed reviews and resets `enrichment_status` to PENDING rather than creating duplicates; soft-deleted reviews are never hard-deleted
  5. `GET /api/v1/reviews/` resolves in 5 or fewer SQL queries regardless of page size, verified in CI
**Plans**: 13 plans
  - [ ] 11-01-PLAN.md — Review/AuditLog models + Shop GBP fields + factories + django-filter (SYNC-04..06, SYNC-10, REVW-13, REVW-14)
  - [ ] 11-02-PLAN.md — Google Reviews API client (list_reviews + post_reply) (SYNC-07..09)
  - [ ] 11-03-PLAN.md — Sync service: fetch_and_persist + run_initial_backfill + Redis progress + token bucket (SYNC-03..07, SYNC-09..10, PROG-10)
  - [ ] 11-04-PLAN.md — Celery tasks + Beat seed migration for incremental fan-out (SYNC-01, SYNC-02, SYNC-08, SYNC-10)
  - [ ] 11-05-PLAN.md — SyncProgressConsumer staff-scope tightening + Redis snapshot reader (PROG-08, PROG-09)
  - [ ] 11-06-PLAN.md — ReviewViewSet + filters + selectors + cursor pagination + REVW-14 query-count test (REVW-01..05, REVW-14)
  - [ ] 11-07-PLAN.md — Reply service + endpoint + ScopedRateThrottle + AuditLog (REVW-09, REVW-10, REVW-12, REVW-13)
  - [ ] 11-08-PLAN.md — Shop create dispatches initial_backfill + /shops/syncing/ endpoint + GBP resource names (SYNC-01, PROG-01, PROG-06)
  - [ ] 11-09-PLAN.md — Frontend foundation: types + api + useReviews hook + template + Vite entry (REVW-01, REVW-03..05, REVW-11)
  - [ ] 11-10-PLAN.md — Reviews list UI: ReviewTable + filters + badges + empty states (REVW-02..08, REVW-11)
  - [ ] 11-11-PLAN.md — Inline ReplyComposer accordion (REVW-09, REVW-10, REVW-12)
  - [ ] 11-12-PLAN.md — ProgressModal + OAuth->modal trigger on Shops page (PROG-01..05, PROG-08, PROG-09)
  - [ ] 11-13-PLAN.md — TopbarSyncIndicator widget + topbar partial + Vite entry (PROG-03, PROG-06, PROG-07, PROG-08)

### Phase 12: AI Enrichment Pipeline
**Goal**: Every fetched review is automatically enriched with sentiment, tags, and action item suggestions by GPT-4o-mini; costs are tracked at log time with immutable pricing, and all calls are traced in LangSmith
**Depends on**: Phase 11
**Requirements**: ENRCH-01, ENRCH-02, ENRCH-03, ENRCH-04, ENRCH-05, ENRCH-06, ENRCH-07, ENRCH-08, ENRCH-09, ENRCH-10, ENRCH-11, ENRCH-12, ENRCH-13, ENRCH-14
**Success Criteria** (what must be TRUE):
  1. An enriched review card in the Reviews list shows the correct sentiment badge (Positive/Neutral/Negative) and up to 5 tag chips; a failed enrichment shows the "AI analysis failed" indicator without hiding the review
  2. Re-enqueuing `enrich_review` for a review whose `enrichment_status` is already SUCCESS exits immediately without calling OpenAI; the Redis lock prevents concurrent enrichment of the same review
  3. Every successful OpenAI call writes one `AiUsageLog` row with token counts, latency, computed cost, and `langsmith_trace_id`; the cost formula matches the hand-computed reference within $0.01
  4. When the active `AiPricing` row is updated, costs on historical `AiUsageLog` rows are unchanged
  5. All reviews from Phase 11 are enriched by the one-time post-deployment job; the `retry_failed_enrichments` Beat task re-attempts FAILED reviews every 6 hours
**Plans**: TBD

### Phase 13: Action Items and Notifications
**Goal**: Org Admins and Staff can manage AI-extracted and manually created action items through a scoped table with status workflow, modal detail view, and a notification bell that surfaces new reviews and assigned items
**Depends on**: Phase 12
**Requirements**: ACTN-01, ACTN-02, ACTN-03, ACTN-04, ACTN-05, ACTN-06, ACTN-07, ACTN-08, ACTN-09, ACTN-10, ACTN-11, ACTN-12, ACTN-13, NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05
**Success Criteria** (what must be TRUE):
  1. The Action Items list at `/admin/org/action-items/` shows all AI-extracted and manual items; Staff users see only SHOP-scoped items for their accessible shops and cannot access BRAND-scoped items (403 at API layer)
  2. An Org Admin or Manager can manually create an action item with title, scope, shop, priority, assignee, due date, and initial note; every status transition (To Do → In Progress → Complete → Won't Do, any direction) writes to the audit log
  3. The notification bell shows an unread count and opens a popover with the last 10 unread notifications; clicking any notification navigates to the relevant page and marks it read; Staff users do not receive brand-scoped action item notifications
  4. `GET /api/v1/action-items/` resolves in 5 or fewer SQL queries, verified in CI
**Plans**: TBD

## Progress

| Phase | Milestone | Plans | Status | Completed |
| ----- | --------- | ----- | ------ | --------- |
| 1–5. Superadmin | v1.0 | 24/24 | Complete | 2026-04-27 |
| 6. Org Admin Shell | v0.2-org-admin | 5/5 | Complete | 2026-04-27 |
| 7. Regions | v0.2-org-admin | 3/3 | Complete | 2026-04-28 |
| 8. Shops | v0.2-org-admin | 7/7 | Complete | 2026-04-29 |
| 9. Team | v0.2-org-admin | 5/5 | Complete | 2026-04-30 |
| 10. Infrastructure Foundation | v0.3 | 5/5 | Complete | 2026-05-01 |
| 11. Reviews Fetching, Display, Reply | 5/13 | In Progress|  | - |
| 12. AI Enrichment Pipeline | v0.3 | 0/TBD | Not started | - |
| 13. Action Items and Notifications | v0.3 | 0/TBD | Not started | - |
