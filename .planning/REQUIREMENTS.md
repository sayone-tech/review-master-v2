# Requirements: Multi-Tenant Review Management Platform — v0.3

**Defined:** 2026-05-01
**Milestone:** v0.3-reviews-and-action-items
**Source:** docs/requirements-phase-3.docx (v1.0, May 2026)
**Core Value:** Org Admins and Staff can view, respond to, and action Google Business Profile reviews — backed by Celery background sync, AI enrichment, and an Action Items workflow.

---

## Phase 10 Requirements (3a-i — Infrastructure Foundation)

### Infrastructure

- [x] **INFRA-01**: Celery 5.x worker runs with Redis broker (DB index 3) and result backend (DB index 4); two named queues (`google-sync`, `ai-enrichment`) with separate worker pools
- [ ] **INFRA-02**: Celery Beat runs as a single instance with `django-celery-beat` DB-backed schedule; schedule is editable at runtime
- [ ] **INFRA-03**: Flower runs in dev and staging environments only; never deployed to production
- [x] **INFRA-04**: Worker concurrency is configurable via env var (default 8 per queue per pod); soft time limit 5 min, hard time limit 10 min
- [ ] **INFRA-05**: Tasks auto-retry on failure with exponential backoff: 3 retries, base delay 30s, max delay 10 min
- [ ] **INFRA-06**: Sentry captures task failures with full traceback and task arguments for both web and Celery worker processes
- [x] **INFRA-07**: CI smoke test enqueues a task on each queue and verifies completion within 30 seconds
- [x] **INFRA-08**: Django Channels is configured with Redis channel layer (DB index 5); ASGI server runs alongside WSGI
- [x] **INFRA-09**: `SyncProgressConsumer` at `/ws/sync-progress/` accepts authenticated connections; rejects unauthenticated and cross-tenant connections with code 4403
- [ ] **INFRA-10**: Redis distributed lock helper is implemented (`acquire`, `release`, TTL expiry) and unit-tested
- [ ] **INFRA-11**: Retry/backoff decorator is implemented and verified with a deliberately-failing test task that retries 3 times then fails permanently

---

## Phase 11 Requirements (3a-ii — Reviews Fetching, Display, Reply)

### Review Sync

- [x] **SYNC-01**: Initial backfill task is dispatched immediately after a shop completes Google OAuth; fetches all historical reviews paginated, persisting each page before fetching the next
- [x] **SYNC-02**: Incremental sync runs every 6 hours per shop via Celery Beat fan-out; each shop's exact next-sync time is jittered by up to 30 minutes to spread load
- [x] **SYNC-03**: Per-shop Redis lock (`lock:google_sync:shop:{shop_id}`, 5-min TTL) prevents concurrent duplicate syncs; task exits cleanly if lock is already held
- [x] **SYNC-04**: Reviews are unique on `(shop_id, google_review_id)`; re-fetching an existing review updates it rather than creating a duplicate
- [x] **SYNC-05**: If a review's text or rating has changed since last fetch, the existing row is updated and `enrichment_status` is reset to `PENDING`
- [x] **SYNC-06**: Reviews no longer returned by Google are soft-deleted (`deleted_at` set); never hard-deleted
- [x] **SYNC-07**: On `401 invalid_grant`, shop `connection_status` is set to `EXPIRED` and excluded from future syncs until Org Admin reconnects
- [x] **SYNC-08**: On `403 quota_exceeded` or 5xx, task retries with exponential backoff (3 retries); on persistent failure, error is written to AuditLog and Sentry
- [x] **SYNC-09**: Redis token bucket tracks Google API calls per project; new sync tasks are held when bucket is near depletion
- [x] **SYNC-10**: Audit log entries written for `sync.started`, `sync.completed`, `sync.failed`, `review.fetched`

### Progress UI

- [x] **PROG-01**: Progress Modal opens automatically after Google OAuth completes; shows two stacked progress bars (Fetched from Google / Processed with AI) with live counters and a "Last update: N seconds ago" line
- [x] **PROG-02**: Estimated time remaining is computed once at least 2 pages have been fetched; displayed as "About N minutes left"
- [x] **PROG-03**: "Run in background" button closes the modal while sync continues; persistent top-bar indicator appears (spinner + count badge)
- [x] **PROG-04**: "View shop details" button is enabled only after sync completes (or on error to allow investigation); navigates to Shop Details page
- [x] **PROG-05**: Progress Modal error state shows: "Sync paused — {error}. We'll retry automatically. Click Reconnect Google if you've revoked access."
- [x] **PROG-06**: Top-bar indicator shows count badge when multiple shops are syncing; tooltip says "N shops syncing reviews"; click opens popover with per-shop progress bars
- [x] **PROG-07**: Top-bar indicator turns red with warning icon on permanent sync failure; popover includes "View error" link per failed shop
- [x] **PROG-08**: WebSocket client connects to `/ws/sync-progress/?shop_id={id}`; receives `sync.fetch.progress`, `sync.enrichment.progress`, `sync.complete`, and `sync.error` events
- [x] **PROG-09**: On WebSocket reconnect, consumer immediately sends the current snapshot from Redis so UI is correct without waiting for the next event
- [x] **PROG-10**: Sync progress state persisted in Redis under `sync:progress:{shop_id}` with 24-hour TTL; retained 1 hour after success, 7 days after permanent failure

### Reviews Module

- [x] **REVW-01**: Reviews list page at `/admin/org/reviews/`; accessible to all roles; Staff queryset filtered to assigned shops only
- [x] **REVW-02**: Filter bar with Store, Rating, Sentiment, Reply Status, From Date, To Date, and Search (full-text on review text + reviewer name); all filters apply additively
- [x] **REVW-03**: "Showing X of Y reviews" live count below filter bar; search debounced 300ms
- [x] **REVW-04**: Sort selector: Newest first (default), Oldest first, Lowest rating first, Highest rating first
- [x] **REVW-05**: Pagination with 10/25/50/100 selector (default 10); shows "Showing X–Y of Z" with first/prev/next/last controls
- [ ] **REVW-06**: Each review renders as a card: reviewer name + avatar, star rating, source shop badge (Region • Shop), review date (relative + full timestamp on hover), review text with "Show more" toggle if >1000 chars
- [ ] **REVW-07**: Sentiment badge (Positive/Neutral/Negative) and tag chips shown on enriched reviews; "Analyzing..." pill shown while enrichment is pending; red exclamation with tooltip on enrichment failure
- [ ] **REVW-08**: Action item chips on review card; clickable to open Action Item modal
- [x] **REVW-09**: Reply section: if replied — shows "Replied on {date}" with yellow check icon and reply text; if not replied — shows "Reply" button that expands inline composer with 4000-char counter
- [x] **REVW-10**: Inline reply submit posts to Google synchronously; on success, composer replaced with posted reply view; on failure, inline error banner shown; no local row created on failure
- [x] **REVW-11**: Three empty states: no connected shops (with "Go to Shops" CTA for Org Admin), shops connected but no reviews yet, filters match nothing (with "Clear Filters" CTA)
- [x] **REVW-12**: Reply throttle: 30 submissions per minute per user (DRF throttle)
- [x] **REVW-13**: Audit log entries written for `review.replied` and `review.reply_failed`
- [x] **REVW-14**: `GET /api/v1/reviews/` resolves in ≤5 SQL queries regardless of page size; verified by `CaptureQueriesContext` test in CI

---

## Phase 12 Requirements (3b-i — AI Enrichment Pipeline)

### AI Enrichment

- [ ] **ENRCH-01**: OpenAI client wrapper calls GPT-4o-mini with a single combined prompt per review; returns structured JSON with `sentiment`, `tags` (max 5, each with `label` + `polarity`), and `action_items` (each with `title`, `scope`, `priority`)
- [ ] **ENRCH-02**: `enrich_review(review_id)` acquires Redis lock (`lock:enrich:review:{review_id}`, 5-min TTL); exits immediately if `enrichment_status` is already `SUCCESS` or `IN_PROGRESS`
- [ ] **ENRCH-03**: `enrichment_status` transitions `PENDING → IN_PROGRESS → SUCCESS | FAILED` under `transaction.atomic()` with `select_for_update` on the Review row
- [ ] **ENRCH-04**: On OpenAI 429 or 5xx: retry 3 times (30s, 2 min, 10 min); on other 4xx: no retry, mark `FAILED`; on JSON parse failure: retry once, then mark `FAILED`
- [ ] **ENRCH-05**: Failed enrichments do not block the review from appearing in the Reviews list; card shows "AI analysis failed" indicator
- [ ] **ENRCH-06**: `retry_failed_enrichments` Beat task runs every 6 hours; re-attempts `FAILED` reviews up to 3 times total before giving up permanently
- [ ] **ENRCH-07**: Every successful OpenAI call writes one `AiUsageLog` row with all token counts (prompt, completion, cached, total), latency, status, computed cost, and `langsmith_trace_id`
- [ ] **ENRCH-08**: Cost computed at log time using active `AiPricing` row (`effective_from <= now AND (effective_to IS NULL OR effective_to > now)`); formula: `(prompt - cached)/1M * input_price + cached/1M * cached_price + completion/1M * output_price`
- [ ] **ENRCH-09**: Historical costs are never retroactively changed when pricing rows are updated
- [ ] **ENRCH-10**: `AiPricing` seed data loaded for GPT-4o-mini at published rates; cost calculation matches hand-computed reference within $0.01 on a verification dataset
- [ ] **ENRCH-11**: LangSmith tracing wraps every OpenAI call; trace metadata includes `organisation_id`, `review_id`, `shop_id`, `model`, `request_type`; if LangSmith is unreachable, the OpenAI call still proceeds
- [ ] **ENRCH-12**: `langsmith_trace_id` captured from SDK response and persisted on `AiUsageLog`
- [ ] **ENRCH-13**: Existing reviews from Phase 11 are enriched via a one-time post-deployment job
- [ ] **ENRCH-14**: Reviews list shows sentiment badges and tag chips for enriched reviews (updates Phase 11 cards)

---

## Phase 13 Requirements (3b-ii — Action Items Module)

### Action Items

- [ ] **ACTN-01**: `ActionItem` rows are created from GPT's `action_items` JSON output; scope = `SHOP` items have `shop_id` set to the source review's shop; scope = `BRAND` items have `shop_id = NULL`
- [ ] **ACTN-02**: Action Items list page at `/admin/org/action-items/`; Staff queryset filtered to `scope = SHOP AND shop_id IN (staff's accessible shops)`; brand-scoped items hidden from Staff at API layer (403 on direct access)
- [ ] **ACTN-03**: Filter bar: Store, Status (To Do / In Progress / Complete / Won't Do), Scope toggle (Shop / Brand / All — Org Admin / Manager only; hidden from Staff), Assignee (All / Assigned to me / Unassigned / by name), From Date, To Date, Search (title + notes)
- [ ] **ACTN-04**: Table columns: Title (clickable), Status badge, Scope pill, Shop, Assignee, Due Date (red if overdue), Created, Source (Robot/User icon), three-dot action menu
- [ ] **ACTN-05**: Pagination with 10/25/50/100 selector (default 25); sort: Newest first (default), Oldest first, Due Date ascending, Status (To Do first), Priority (high first)
- [ ] **ACTN-06**: Action Item modal with three tabs: Details (read-only + Edit button), Notes (append-only timeline), Source Review (visible only for AI-extracted items); modal title shows action item title
- [ ] **ACTN-07**: Edit mode: Title, Priority, Due Date, Assignee are editable; Scope and Shop are NOT editable for AI-extracted items; Status changes only via dedicated status buttons or row actions menu
- [ ] **ACTN-08**: Status workflow: any-to-any transitions (To Do, In Progress, Complete, Won't Do); every transition writes to audit log with old and new status
- [ ] **ACTN-09**: Manual action item creation via "+ New Action Item": fields Title (5–200 chars), Scope (Shop/Brand), Shop (required when Scope=Shop), Priority, Assignee, Due date (today or future), Initial note; Brand scope option hidden from Staff
- [ ] **ACTN-10**: Notes are append-only (1–2000 chars each); existing notes cannot be edited or deleted
- [ ] **ACTN-11**: Source Review tab renders read-only review card; "Open in Reviews" link navigates to `/admin/org/reviews/?id={review_id}`
- [ ] **ACTN-12**: `GET /api/v1/action-items/` resolves in ≤5 SQL queries; verified by `CaptureQueriesContext` test in CI
- [ ] **ACTN-13**: Audit log entries written for `action_item.created`, `action_item.status_changed`, `action_item.assigned`, `action_item.note_added`

### Notifications

- [ ] **NOTF-01**: Notification bell in top bar shows unread count (red dot or numeric badge); click opens popover listing last 10 unread notifications newest-first
- [ ] **NOTF-02**: Three notification types: `new_review` (all team; Staff only for accessible shops), `new_action_item` (all team; Staff only for shop-scoped accessible items), `action_item_assigned` (assignee only)
- [ ] **NOTF-03**: Clicking a notification navigates to the relevant page and marks it read; "Mark all as read" link in popover
- [ ] **NOTF-04**: Unread counter polled every 60 seconds via HTTP (no WebSocket); counter refreshes immediately after any notification interaction
- [ ] **NOTF-05**: Brand-scoped action item notifications are not delivered to Staff users

---

## Out of Scope (v0.3)

| Feature | Reason |
|---------|--------|
| AI-suggested replies | Org Admin types replies manually; AI reply-drafting is a future feature |
| Editing or deleting an existing Google reply | Google API does not support this cleanly |
| Bulk actions on reviews | Not needed for v0.3 |
| Daily email digest | Deferred |
| Live toast notifications for new reviews | WebSocket surface kept narrow per §3.3 |
| Live action item status updates across sessions | Deferred to a future phase |
| Manual sync trigger ("Sync Now" button) | Automation sufficient for v0.3 |
| AI cost dashboard for Superadmin | Data model ready; UI deferred |
| Canonical tag vocabulary normalisation | Free-text tags in v0.3; canonical phase to follow |
| Re-processing historical reviews on prompt change | Future: `enrichment_version` field ready |
| Hard delete of action items | Use Won't Do status instead |
| CSV/Excel export | Deferred |
| Kanban board for action items | Table only in v0.3 |
| Filter reviews by tag | Requires canonical tags first |
| "View all notifications" full page | Deferred if not built in Phase 13 |
| AI cost dashboard for Superadmin | Data model ships in Phase 12; UI deferred post-v0.3 |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 10 | Complete |
| INFRA-02 | Phase 10 | Pending |
| INFRA-03 | Phase 10 | Pending |
| INFRA-04 | Phase 10 | Complete |
| INFRA-05 | Phase 10 | Pending |
| INFRA-06 | Phase 10 | Pending |
| INFRA-07 | Phase 10 | Complete |
| INFRA-08 | Phase 10 | Complete |
| INFRA-09 | Phase 10 | Complete |
| INFRA-10 | Phase 10 | Pending |
| INFRA-11 | Phase 10 | Pending |
| SYNC-01 | Phase 11 | Complete |
| SYNC-02 | Phase 11 | Complete |
| SYNC-03 | Phase 11 | Complete |
| SYNC-04 | Phase 11 | Complete |
| SYNC-05 | Phase 11 | Complete |
| SYNC-06 | Phase 11 | Complete |
| SYNC-07 | Phase 11 | Complete |
| SYNC-08 | Phase 11 | Complete |
| SYNC-09 | Phase 11 | Complete |
| SYNC-10 | Phase 11 | Complete |
| PROG-01 | Phase 11 | Complete |
| PROG-02 | Phase 11 | Complete |
| PROG-03 | Phase 11 | Complete |
| PROG-04 | Phase 11 | Complete |
| PROG-05 | Phase 11 | Complete |
| PROG-06 | Phase 11 | Complete |
| PROG-07 | Phase 11 | Complete |
| PROG-08 | Phase 11 | Complete |
| PROG-09 | Phase 11 | Complete |
| PROG-10 | Phase 11 | Complete |
| REVW-01 | Phase 11 | Complete |
| REVW-02 | Phase 11 | Complete |
| REVW-03 | Phase 11 | Complete |
| REVW-04 | Phase 11 | Complete |
| REVW-05 | Phase 11 | Complete |
| REVW-06 | Phase 11 | Pending |
| REVW-07 | Phase 11 | Pending |
| REVW-08 | Phase 11 | Pending |
| REVW-09 | Phase 11 | Complete |
| REVW-10 | Phase 11 | Complete |
| REVW-11 | Phase 11 | Complete |
| REVW-12 | Phase 11 | Complete |
| REVW-13 | Phase 11 | Complete |
| REVW-14 | Phase 11 | Complete |
| ENRCH-01 | Phase 12 | Pending |
| ENRCH-02 | Phase 12 | Pending |
| ENRCH-03 | Phase 12 | Pending |
| ENRCH-04 | Phase 12 | Pending |
| ENRCH-05 | Phase 12 | Pending |
| ENRCH-06 | Phase 12 | Pending |
| ENRCH-07 | Phase 12 | Pending |
| ENRCH-08 | Phase 12 | Pending |
| ENRCH-09 | Phase 12 | Pending |
| ENRCH-10 | Phase 12 | Pending |
| ENRCH-11 | Phase 12 | Pending |
| ENRCH-12 | Phase 12 | Pending |
| ENRCH-13 | Phase 12 | Pending |
| ENRCH-14 | Phase 12 | Pending |
| ACTN-01 | Phase 13 | Pending |
| ACTN-02 | Phase 13 | Pending |
| ACTN-03 | Phase 13 | Pending |
| ACTN-04 | Phase 13 | Pending |
| ACTN-05 | Phase 13 | Pending |
| ACTN-06 | Phase 13 | Pending |
| ACTN-07 | Phase 13 | Pending |
| ACTN-08 | Phase 13 | Pending |
| ACTN-09 | Phase 13 | Pending |
| ACTN-10 | Phase 13 | Pending |
| ACTN-11 | Phase 13 | Pending |
| ACTN-12 | Phase 13 | Pending |
| ACTN-13 | Phase 13 | Pending |
| NOTF-01 | Phase 13 | Pending |
| NOTF-02 | Phase 13 | Pending |
| NOTF-03 | Phase 13 | Pending |
| NOTF-04 | Phase 13 | Pending |
| NOTF-05 | Phase 13 | Pending |

**Coverage:**
- v0.3 requirements: 68 total
- Mapped to phases: 68
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-01*
*Source: docs/requirements-phase-3.docx v1.0*
*Last updated: 2026-05-01 after initial definition*
