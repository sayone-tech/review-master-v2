**REQUIREMENTS DOCUMENT**

Multi-Tenant Review Management Platform

**Phase 3 — Reviews & Action Items**

Google Review Sync, AI Enrichment, and Action Items

Version 1.0 • May 2026

# 1. Document Overview

This document specifies Phase 3 of the multi-tenant Review Management Platform — the Reviews module, AI enrichment pipeline, and Action Items module. It builds on the conventions, data model, design system, and tech stack established in Phase 1 (Superadmin) and Phase 2 (Organisation Admin).

All global UI patterns, branding, design tokens, accessibility rules, and confirmation popup conventions defined in earlier phases apply unchanged to Phase 3 and are not repeated here. Refer to the Phase 1 and Phase 2 documents for those baselines.

Phase 3 introduces significant new infrastructure: Celery for background processing, Django Channels for real-time progress updates, Google Business Profile review fetching at scale, OpenAI GPT-4o-mini integration with cost tracking, and the platform's first AI-driven enrichment pipeline. Because of the scope, Phase 3 is split into four shippable sub-phases (see §1.3).

## 1.1 Phase 3 Scope

- Celery + Celery Beat infrastructure for background jobs
- Django Channels infrastructure for WebSocket-based real-time UI updates
- Google Business Profile review fetching — initial backfill and incremental sync
- Real-time progress UI for initial review backfill (modal + persistent indicator)
- Reviews module — list, filter, search, paginate, view, reply
- Reply-to-Google integration — replies posted back via Google Business Profile API
- OpenAI GPT-4o-mini enrichment pipeline — sentiment, tags, action items, scope detection
- AI cost tracking — per-call token usage, configurable pricing, calculated cost
- LangSmith tracing for AI calls
- Action Items module — list, filter, edit, status workflow, manual creation
- Brand vs Shop scoping for action items, with role-based visibility
- In-app notification bell for new reviews and action items

## 1.2 Out of Scope for Phase 3

- AI-suggested replies (Org Admin types replies manually)
- Editing or deleting an existing reply on Google
- Bulk actions on reviews
- Daily email digest (deferred)
- Real-time email or Slack notifications
- Live notification toasts beyond the bell counter
- Live action item status updates pushed across user sessions
- Manual sync trigger ("Sync Now" button)
- AI cost dashboard for Superadmin (data model ready, UI deferred)
- Canonical tag vocabulary normalisation (Phase 3b ships free-text; canonical tags are a follow-up)
- Re-processing of historical reviews when prompts or models change
- Hard delete of action items (use Won't Do status instead)
- CSV / Excel export of reviews and action items
- Kanban board view for action items (table only in Phase 3)

## 1.3 Phase Split

Phase 3 is delivered across four shippable sub-phases. Each builds on the previous and is independently deployable. The split is designed to validate the foundation before layering AI complexity on top.

| **Sub-phase** | **Focus** | **Ships** |
| --- | --- | --- |
| Phase 3a-i | Infrastructure foundation | Celery, Celery Beat, Flower (dev/staging), Django Channels, WebSocket consumer scaffolding, distributed Redis locks, retry/backoff utilities, monitoring hooks. No business logic. Validates that the infrastructure works under load before any feature code is added. |
| Phase 3a-ii | Reviews fetching, storage, display, reply | Google Business Profile review fetcher (initial backfill + incremental), Review and ReviewReply models, real-time progress UI for initial backfill, Reviews list page with filters / search / pagination, inline reply UI, reply-back-to-Google integration. No AI. |
| Phase 3b-i | AI enrichment pipeline | OpenAI client wrapper, prompt template, structured JSON parser, AiUsageLog and AiPricing models, cost calculator, LangSmith tracing, enrichment Celery task, enrichment_status field on Review. Existing reviews enriched. No UI changes (sentiment/tags shown when Reviews page is later updated). |
| Phase 3b-ii | Action Items module | ActionItem model, brand vs shop scoping, Action Items list page with filters / search / pagination, edit modal, status workflow, manual creation, source-review modal popup, role-based visibility, in-app notification bell counter. |

All four sub-phases together constitute the Phase 3 milestone. The phase numbering follows the milestone-and-phase model used by the GSD workflow.

# 2. Roles and Permissions

Phase 3 introduces no new user roles. The Manager and Staff role labels established in Phase 2 govern access to all Phase 3 features.

## 2.1 Permissions Matrix

| **Action** | **Org Admin / Manager** | **Staff** |
| --- | --- | --- |
| View reviews — all shops in organisation | Yes | Only assigned shops |
| Reply to a review | Yes (any shop) | Only assigned shops |
| View shop-scoped action items | Yes | Only assigned shops |
| View brand-scoped action items | Yes | Hidden completely |
| Edit / change status of shop action items | Yes | Only assigned shops |
| Edit / change status of brand action items | Yes | No |
| Manually create a shop action item | Yes | Only assigned shops |
| Manually create a brand action item | Yes | No |
| Assign action items to other team members | Yes (any team member) | Only within assigned shops |
| See initial sync progress for a shop | Yes | Only for shops they have access to |
| View AI usage and cost (future Superadmin dashboard) | Yes (org level, future) | No |

## 2.2 Tenant Scoping

- All Phase 3 querysets must be filtered by request.user.organisation_id at the base permission layer (per CLAUDE.md §9).
- Review queries for Staff users must additionally filter by the shops in the user's StaffAccessScope (Phase 2).
- Action Item queries for Staff users must filter by both shop access AND scope = SHOP (brand-scoped items are excluded entirely).
- Brand-scoped action item creation, edit, and view endpoints must return 403 Forbidden for Staff role even with valid IDs (cross-tenant probing protection).

# 3. Infrastructure and Architecture

## 3.1 Celery and Background Processing

Phase 3 introduces Celery as the platform's background job processor. Phases 1 and 2 used Django management commands triggered by Cloud Scheduler — that pattern continues to work for those features and does not require migration. Phase 3 features that require concurrency, retries, real-time progress, or per-shop locking use Celery.

### Celery Configuration

- Celery 5.x with Redis as broker (already in stack) — broker DB index 3
- Celery result backend on Redis — DB index 4
- Celery Beat for periodic schedules; schedule stored in django-celery-beat (DB-backed) so it can be edited at runtime
- Flower for monitoring — dev and staging only, never exposed in production
- Two named queues: google-sync and ai-enrichment. Each has its own worker pool to prevent slow OpenAI calls from blocking faster Google API calls.
- Worker concurrency: 8 per queue per pod by default; tuned via env var
- Soft time limit: 5 minutes per task; hard time limit: 10 minutes
- Auto-retry on failure with exponential backoff: 3 retries, base delay 30s, max delay 10 minutes
- Tasks are idempotent (see §3.2)
- Sentry integration captures task failures with full traceback and task arguments

### Deployment

- Celery worker, Celery Beat, and the web server run as separate Cloud Run services (or separate processes within a GKE pod set).
- Workers and Beat use the same Docker image as the web service; entry command differs per service.
- Beat instance count: exactly 1 (running multiple Beat instances would schedule duplicate jobs).
- Worker instance count: scales horizontally per queue based on queue depth.

## 3.2 Idempotency and Distributed Locking

Background tasks must be idempotent — running the same task twice with the same arguments must produce the same final state, never duplicates or partial-state corruption. This is enforced at three layers:

- Layer 1 — Database uniqueness constraints. Reviews are unique on (shop_id, google_review_id). Inserts use ON CONFLICT DO UPDATE semantics so a re-fetched review updates rather than duplicates.
- Layer 2 — Per-entity Redis locks. A task that mutates a single shop or review acquires lock:google_sync:shop:{shop_id} or lock:enrich:review:{review_id} with a 5-minute TTL before proceeding. If the lock cannot be acquired, the task exits cleanly (does not retry — another worker is already handling it).
- Layer 3 — Status flags on the entity. Review.enrichment_status transitions PENDING → IN_PROGRESS → SUCCESS / FAILED. The transition to IN_PROGRESS uses a row-level lock (SELECT FOR UPDATE) inside the same transaction as the lock acquisition to eliminate the window where two workers both think they have the lock.

## 3.3 Django Channels and WebSocket Updates

Phase 3 adds Django Channels to deliver real-time progress updates during a shop's initial review backfill. Channels infrastructure is added once and is available for future real-time features in later phases (live notifications, live action item updates) but is scoped narrowly in Phase 3.

### Configuration

- Django Channels with Redis as channel layer backend — DB index 5
- ASGI server: Daphne (or Uvicorn) running alongside the WSGI web server
- Single consumer class in Phase 3: SyncProgressConsumer at /ws/sync-progress/
- Authentication: Channels session middleware uses the same Django session as the web server; only authenticated users may connect
- Authorisation: on connect, consumer verifies the user's organisation matches the shop_id passed in the connection query string; otherwise closes the connection with code 4403
- Group naming: sync-progress-{shop_id}; the worker publishes progress events to this group, all clients subscribed receive them

### Scope Discipline

Channels is used in Phase 3 ONLY for sync progress. The following are explicitly out of scope:

- Live new-review toast notifications
- Live action item status sync between concurrent users
- Real-time review reply confirmations
- Any live data synchronisation beyond initial sync progress
These are deferred to a future phase to keep the Channels surface small and verifiable in Phase 3.

## 3.4 External API Integration Points

| **API** | **Purpose** | **Module** |
| --- | --- | --- |
| Google Business Profile API | Fetch reviews per location; post reply to a review | apps/integrations/google/ (Phase 2 module extended) |
| OpenAI Chat Completions API | GPT-4o-mini for review enrichment | apps/integrations/openai/ |
| LangSmith API | Tracing of OpenAI calls | apps/integrations/openai/tracing.py |

# 4. Review Fetching from Google

## 4.1 Fetching Strategy

Reviews are fetched from Google Business Profile API in two distinct modes: an initial backfill that runs once when a shop is first connected, and an incremental sync that runs every six hours thereafter.

### Initial Backfill (Run Once Per Shop)

- Triggered immediately after a shop completes Google OAuth connection (Phase 2 §5.5).
- Fetches all available historical reviews via the Google Business Profile API's reviews.list endpoint, paginating until exhausted.
- Each page persists reviews to the database before the next page is fetched (so a long-running backfill is interruptible and resumable).
- Publishes progress events to the WebSocket group on every page (see §5).
- On completion, marks the shop's initial_sync_completed_at timestamp and triggers AI enrichment for all newly-fetched reviews (Phase 3b-i).

### Incremental Sync (Every 6 Hours, Per Shop)

- Celery Beat schedules a fan-out task every hour: enqueue_incremental_syncs.
- The fan-out task selects shops whose last_synced_at is more than 6 hours ago, jittered to spread load (each shop's exact next-sync time is computed as last_synced_at + 6 hours + random jitter of up to 30 minutes).
- For each due shop, enqueues sync_shop_reviews(shop_id) onto the google-sync queue.
- The per-shop task acquires a Redis lock (lock:google_sync:shop:{shop_id}, 5-minute TTL); skips silently if already held.
- Fetches only reviews newer than the latest review already stored for that shop (using Google's review timestamp).
- New reviews are inserted; updated review text or replies update the existing row (idempotency layer 1, §3.2).
- Each newly inserted review is then queued for AI enrichment by enqueueing enrich_review(review_id) onto the ai-enrichment queue.
- Updates the shop's last_synced_at timestamp atomically with the persistence step.

## 4.2 Idempotency Rules

- Reviews are unique on (shop_id, google_review_id). The google_review_id comes from Google's review payload and is stable across fetches.
- Re-fetching a review that already exists in the database does NOT create a duplicate. If the review text or rating has changed since last fetch (rare but possible — Google allows users to edit), the existing row is updated and the enrichment_status is reset to PENDING so the AI enrichment re-runs.
- If Google has marked a review as deleted (the review_id no longer appears in the response), the local row is soft-deleted (deleted_at is set) but never hard-deleted — preserves audit trail and avoids breaking action item linkage.

## 4.3 Rate Limiting and Error Handling

- Google Business Profile API has per-project quotas. The application tracks call counts in Redis using a token bucket per Google project (not per shop) and pauses dispatching new sync tasks when the bucket is near depletion.
- On a 401 invalid_grant response, the shop's connection_status is set to EXPIRED and the OAuth refresh token is marked stale. The shop is excluded from future sync until the Org Admin re-connects (Phase 2 §5.10).
- On a 403 quota_exceeded response, the task retries with exponential backoff.
- On any 5xx response, the task retries up to 3 times with exponential backoff.
- On persistent failure, the task records the error to the AuditLog and to Sentry, then exits without further retries. The next scheduled sync will try again.

## 4.4 Posting Replies Back to Google

When an Org Admin or authorised user submits a reply on a review, the reply is posted to Google Business Profile API immediately and synchronously (within the request lifecycle) so the user receives confirmation that the reply was accepted.

- Reply submit endpoint: POST /api/v1/reviews/{review_id}/reply/ with { text }
- Server validates: text is 1–4000 characters; user has reply permission for the review's shop
- Server posts to Google's reviews.updateReply endpoint synchronously
- On Google success: ReviewReply row is created (or updated, if a previous reply existed locally) with status = POSTED; toast shows success
- On Google failure: no local row is created; toast shows error: "Could not post reply to Google. Please try again." with the underlying error captured for support
- Audit log entry on every reply attempt (success or failure)

# 5. Real-time Progress UI for Initial Sync

## 5.1 Purpose

When a shop is connected to Google Business Profile for the first time, fetching the historical reviews can take from a few seconds (small shop, ~10 reviews) to several minutes (large shop, thousands of reviews). The Org Admin needs visibility into this process and the option to navigate away while it continues in the background.

## 5.2 Progress Modal (Opened After OAuth Completes)

**Trigger:** Successful Google OAuth completion in the Create Shop or Reconnect Google flow

**Title:** Syncing reviews from Google

**Subtitle:** This may take a few minutes for shops with many reviews. You can close this and continue working — we'll keep going in the background.

### Content

- Two stacked progress bars:
- Bar 1 — "Fetched from Google": shows current_count / total_count_estimate with a percentage and a fill bar in the brand yellow.
- Bar 2 — "Processed with AI": shows enriched_count / fetched_count with the same styling. Always lags behind bar 1 because enrichment runs after fetch.
- Live counters below each bar update as WebSocket events arrive.
- Status line: "Last update: 3 seconds ago" — refreshes per WebSocket message.
- Estimated time remaining: "About 2 minutes left" (computed from average per-page latency once at least 2 pages have been fetched).

### Footer Buttons

- Run in background (secondary) — closes the modal; sync continues; persistent indicator appears in the top bar (see §5.3).
- View shop details (primary, only after sync completes) — closes the modal and navigates to the Shop Details page where any sync errors are shown.

### Error State

If sync fails partway through (e.g., Google revokes the token, network error), the modal shows an error banner: "Sync paused — {error message}. We'll retry automatically. Click Reconnect Google if you've revoked access." The Run-in-background button remains; the View-shop-details button is enabled even on error so the user can investigate.

## 5.3 Persistent Top-Bar Indicator

After the user dismisses the modal (or navigates away from the Create Shop / Reconnect flow), a small persistent indicator appears in the top bar to keep the sync visible across pages.

### Indicator Display

- Position: top bar, left of the notification bell
- Visual: small spinner icon plus a count badge "3" if multiple shops are syncing concurrently
- Tooltip on hover: "3 shops syncing reviews"
- Click target: opens a popover panel listing each in-progress shop with a per-shop progress bar; clicking a shop row re-opens the full Progress Modal for that shop

### Lifecycle

- Indicator appears as soon as any sync is running (initial backfill or incremental syncs are NOT shown here — only initial backfills are surfaced to the user).
- Indicator disappears as soon as the last initial sync completes successfully.
- If a sync fails permanently (max retries exceeded), the indicator turns red with a warning icon. Click opens the popover, which now includes a "View error" link per failed shop.

## 5.4 WebSocket Protocol

### Connection

- Client connects to /ws/sync-progress/?shop_id={shop_id} when the Progress Modal opens.
- Server validates: user is authenticated AND user.organisation_id matches the requested shop's organisation_id.
- On authorisation failure, server closes with code 4403.

### Server-to-Client Event Types

| **Event** | **Payload Fields** | **When Sent** |
| --- | --- | --- |
| sync.fetch.progress | shop_id, fetched, total_estimate | After every Google API page is persisted |
| sync.enrichment.progress | shop_id, enriched, fetched | After every batch of reviews is enriched (configurable batch size, default 10) |
| sync.complete | shop_id, total_fetched, total_enriched, duration_seconds | When initial sync (fetch + enrichment) finishes successfully |
| sync.error | shop_id, stage (FETCH \| ENRICHMENT), error_code, error_message | When sync fails permanently (after retries exhausted) |

### Recovery on Reconnect

If the WebSocket disconnects (e.g., user closes laptop), on reconnect the consumer immediately sends the current snapshot state (read from Redis) so the UI is correct without waiting for the next progress event.

## 5.5 Persistence of Progress State

- Progress state for each in-progress sync is stored in Redis under key sync:progress:{shop_id} with a 24-hour TTL.
- The fetcher worker writes to this key after every persist; the API reads from this key when serving the popover panel; the WebSocket consumer reads from this key on reconnect.
- After successful completion, the key is retained for 1 hour (so the user can briefly see "completed" state) then evicted.
- After permanent failure, the key is retained for 7 days (so the failed-state popover entry persists until acknowledged).

# 6. Reviews Module

## 6.1 Sidebar and Navigation

**Route:** /admin/org/reviews/

**Access:** All roles (Org Admin / Manager / Staff). Staff queryset filtered to assigned shops only.

**Sidebar item:** Reviews (MessageSquare icon)

## 6.2 Reviews List Page

### Page Header

- Card title: "Reviews"
- Card subtitle: "View and manage customer reviews across all locations" (Staff sees: "…across your assigned locations")

### Filter Bar

The filter bar appears as a card above the review list. All filters apply additively (AND logic). "Clear Filters" button resets all filters.

| **Filter** | **Type** | **Options** |
| --- | --- | --- |
| Store | Dropdown | All Stores (default), or any shop in the user's accessible scope |
| Rating | Dropdown | All Ratings (default), 5 Stars, 4 Stars, 3 Stars, 2 Stars, 1 Star |
| Sentiment | Dropdown | All Sentiments (default), Positive, Neutral, Negative |
| Reply Status | Dropdown | All (default), Replied, Not Replied |
| From Date | Date picker | Filters reviews on or after this date (by Google review date, not enrichment date) |
| To Date | Date picker | Filters reviews on or before this date |
| Search | Text input | Searches review text (full-text); searches on reviewer name; case-insensitive substring match |

### Live Result Count

- Below the filter bar: "Showing X of Y reviews"
- X = current page count; Y = total matching the active filters
- Updates immediately when any filter changes (debounced 300ms for the search input)

### Sort

- Default: Newest first (by Google review date)
- Selector with options: Newest first, Oldest first, Lowest rating first, Highest rating first

### Pagination

- Standard 10/25/50/100 selector (default 10), matches Phase 1 / 2 pattern
- Bottom-right of the list: "Showing X–Y of Z" plus first / previous / next / last controls

## 6.3 Review Card

Each review renders as a card in a single column. Cards have generous spacing, white background with subtle shadow, and a yellow left accent border that intensifies for replies-pending state.

### Card Header

- Reviewer name (bold) + small avatar (Google profile image if available, otherwise initials in a yellow circle)
- Star rating (5 yellow stars, filled to indicate the rating)
- Source shop badge — Region / Shop name (e.g., "North District • Downtown Store"); clickable, filters the list to that shop
- Review date in human-readable format (e.g., "3 days ago"; on hover shows full timestamp)

### Card Body

- Review text — full content, no truncation. If extremely long (>1000 chars), a "Show more" toggle appears.
- Sentiment badge — Positive (green) / Neutral (gray) / Negative (red); shown only when enrichment_status is SUCCESS.
- Tag chips — list of tags extracted by GPT, color-coded by polarity. If enrichment is pending, shows a small "Analyzing..." pill instead.
- Action items extracted — small chips with the action item title; clickable, opens the Action Item modal popup.
- If enrichment failed permanently, a small red exclamation icon with tooltip: "AI analysis failed. The review is still listed."

### Card Footer — Reply Section

The reply section is the most prominent part of the card after the review text itself.

- If a reply has been posted: shows "Replied on {date}" with a yellow check icon, followed by the reply text in a slightly indented box. No edit/delete options (out of scope, §1.2).
- If no reply: shows a single "Reply" button (secondary).
- Clicking Reply expands an inline composition area below the review (comment-to-post pattern):
- Textarea with placeholder "Write a reply..." and a small character counter (max 4000)
- Two buttons: Cancel (secondary, collapses the composer) and Post Reply (primary)
- On submit: button shows a spinner; reply is posted to Google synchronously; on success, the composer is replaced with the posted reply view; on failure, an inline error banner appears above the composer.

## 6.4 Empty States

### Empty State — Org Has No Connected Shops

- Centred MessageSquare icon
- Heading: "No reviews yet"
- Body: "Connect a shop to Google Business Profile to start syncing reviews."
- CTA button (Org Admin / Manager only): "Go to Shops"

### Empty State — Shops Connected, No Reviews Yet

- Centred MessageSquare icon
- Heading: "No reviews to display"
- Body: "Reviews will appear here as they're synced from Google. The first sync runs automatically when a shop is connected."

### Empty State — Filters Match Nothing

- Centred Filter icon
- Heading: "No reviews match your filters"
- Body: "Try adjusting your filters or clearing them to see more reviews."
- CTA button: "Clear Filters"

## 6.5 Reply Validation and Limits

- Reply text minimum: 1 character (Google rejects empty replies)
- Reply text maximum: 4000 characters (Google's hard limit)
- Replies are plain text only. Markdown is not rendered. URLs are linkified by Google's display layer, not ours.
- HTML is escaped on display.
- Rate limit: 30 reply submissions per minute per user (DRF throttle)

# 7. AI Enrichment Pipeline (Phase 3b-i)

## 7.1 Goal

Every review fetched from Google is processed by GPT-4o-mini to extract structured information: sentiment, tags, and action items (with shop or brand scope). Enrichment runs asynchronously in the ai-enrichment Celery queue; the Reviews list displays enrichment results as they become available.

## 7.2 Single Combined Prompt

All enrichment outputs come from a single GPT call per review, returning structured JSON. This minimises cost and latency compared to running multiple specialised calls.

### Prompt Inputs

- Brand name — equal to the Organisation Name
- Shop name — name of the shop the review is for
- Shop address — for additional context
- Review text
- Review rating (1–5)

### Required JSON Output Shape

{

"sentiment": "positive" | "neutral" | "negative",

"tags": [ { "label": "clean", "polarity": "positive" }, ... ],

"action_items": [

{

"title": "Address staff rudeness at Downtown Store",

"scope": "shop" | "brand",

"priority": "high" | "medium" | "low"

}

]

}

### Scope Detection Rules

- scope = shop when the review's complaint or praise is location-specific ("this Downtown Store was filthy", "the manager at Mall Location is rude")
- scope = brand when the issue applies to the organisation overall ("Acme Coffee has gone downhill in general", "your prices are too high everywhere")
- If ambiguous, default to scope = shop (since the review came from a specific shop)

### Tag Generation

- Phase 3b-i: free-text tags. GPT generates whatever tags are relevant; no canonical vocabulary enforcement.
- Each tag has a polarity field: positive, negative, or neutral.
- Tag count cap: maximum 5 tags per review (enforced in the prompt).
- Tags are stored as JSONB on the Review row.
- Canonical tag vocabulary is a separate phase (Phase 3b.5 or Phase 4); the data model leaves room for it via an optional canonical_tag_id field on each tag (not populated in Phase 3b-i).

## 7.3 Cost Tracking

Every OpenAI call writes a row to the AiUsageLog table. Cost is calculated server-side using configurable rates from the AiPricing table — never relying on OpenAI's billing data, which is not real-time and not per-call.

### AiUsageLog Fields

- id (PK, UUID)
- organisation_id (FK, indexed for billing reports)
- request_type — REVIEW_ENRICHMENT (only value in Phase 3; future expansions reserved)
- model — exact model identifier (e.g., gpt-4o-mini-2024-07-18)
- review_id (FK, nullable — set for review enrichment)
- prompt_tokens, completion_tokens, cached_tokens, total_tokens
- estimated_cost_usd (decimal, 6 dp)
- latency_ms
- langsmith_trace_id
- status — SUCCESS | FAILURE | RETRYING
- error_code, error_message (nullable)
- created_at
- Indexes: (organisation_id, created_at), (review_id), (status)

### AiPricing Fields

- id (PK)
- model — exact model identifier
- input_token_price_per_1m — decimal, USD per 1 million input tokens
- output_token_price_per_1m — decimal, USD per 1 million output tokens
- cached_token_price_per_1m — decimal, USD per 1 million cached tokens
- effective_from — datetime
- effective_to — datetime, nullable (null = current)
- Unique constraint: (model, effective_from)

### Cost Calculation

- On every successful OpenAI call, look up the AiPricing row for the model where effective_from <= now AND (effective_to IS NULL OR effective_to > now).
- Compute estimated_cost_usd = (prompt_tokens - cached_tokens) / 1_000_000 * input_price + cached_tokens / 1_000_000 * cached_price + completion_tokens / 1_000_000 * output_price.
- Persist the computed cost on the AiUsageLog row. The cost is locked-in at log time — historical pricing changes do NOT retroactively change historical costs.

### Pricing Maintenance

- Pricing rows are managed by Superadmin via a future admin UI (out of scope for Phase 3 — for now, managed via Django admin or seed data)
- Adding a new pricing row updates all subsequent calls; never edit a historical row in place
- Initial seed data: GPT-4o-mini pricing as of model release; values stored as decimals to avoid floating-point drift

## 7.4 LangSmith Tracing

- Every OpenAI call is wrapped with LangSmith's Python SDK
- LangSmith API key in env / Secret Manager
- Trace metadata includes: organisation_id, review_id, shop_id, model, request_type
- On successful trace, the langsmith_trace_id is captured from the SDK response and persisted on AiUsageLog (so support can cross-reference traces from a usage log row)
- If LangSmith is unreachable, the OpenAI call still proceeds — tracing is best-effort, not blocking

## 7.5 Failure Handling

- On OpenAI rate limit (429) or 5xx: retry up to 3 times with exponential backoff (30s, 2 minutes, 10 minutes).
- On OpenAI 4xx other than rate limit (e.g., context length exceeded): no retry; mark Review.enrichment_status = FAILED with error code; record the failure on AiUsageLog.
- On JSON parse failure (GPT returned malformed JSON): retry once. If still bad, mark FAILED.
- Failed enrichments do NOT block the review from appearing in the Reviews list. The card displays with a small "AI analysis failed" indicator.
- A scheduled retry job (every 6 hours) re-attempts FAILED enrichments up to 3 times total before giving up permanently.

## 7.6 Idempotency

- enrich_review(review_id) acquires Redis lock lock:enrich:review:{review_id} (5-minute TTL)
- If the review's enrichment_status is already SUCCESS, the task exits immediately (no work needed, no cost incurred)
- If status is IN_PROGRESS (set by another worker), the task exits silently
- If status is PENDING or FAILED, the task transitions it to IN_PROGRESS, performs the enrichment, then transitions to SUCCESS or FAILED
- All status transitions occur within transaction.atomic() with select_for_update on the Review row

# 8. Action Items Module (Phase 3b-ii)

## 8.1 Sidebar and Navigation

**Route:** /admin/org/action-items/

**Access:** All roles. Staff queryset filtered to (assigned shops AND scope = SHOP). Brand-scoped action items are hidden from Staff.

**Sidebar item:** Action Items (CheckSquare icon)

## 8.2 Action Items List Page

### Page Header

- Card title: "Action Items"
- Card subtitle: "Track and complete improvements identified from customer reviews"
- Top-right primary action: "+ New Action Item" button (manual creation)

### Filter Bar

| **Filter** | **Type** | **Options** |
| --- | --- | --- |
| Store | Dropdown | All Stores (default), or any shop in the user's accessible scope. When Brand-only is checked, this filter is disabled and ignored. |
| Status | Dropdown | All (default), To Do, In Progress, Complete, Won't Do |
| Scope | Toggle: Shop / Brand / All | Org Admin / Manager only. Default "All". Setting to Brand filters to scope = BRAND. Hidden completely from Staff. |
| Assignee | Dropdown | All (default), Assigned to me, Unassigned, or any team member name |
| From Date | Date picker | Filters by created_at |
| To Date | Date picker | Filters by created_at |
| Search | Text input | Searches title and notes; case-insensitive substring match |

### Table Columns

| **Column** | **Display** |
| --- | --- |
| Title | Bold; clickable — opens the Action Item modal |
| Status | Badge — gray (To Do), blue (In Progress), green (Complete), neutral dark (Won't Do) |
| Scope | Pill — "Shop" or "Brand" |
| Shop | Region / Shop name; "—" for brand-scoped items |
| Assignee | Avatar + name; "Unassigned" with a placeholder avatar if none |
| Due Date | Date in M/D/YYYY format; gray for future, red for overdue, "—" for no due date |
| Created | Date in M/D/YYYY format |
| Source | Small icon — Robot icon for AI-extracted, User icon for manually-created |
| Actions | Three-dot menu |

### Row Actions Menu

- View Details (opens the Action Item modal)
- Edit (opens edit mode within the modal)
- Change Status — submenu with the four status options
- Assign to me / Unassign me / Reassign — context-dependent
- View source review (only for AI-extracted items)

### Pagination, Search, Sort

- Pagination: standard 10/25/50/100 selector (default 25 — action items lists are typically longer than reviews lists)
- Default sort: Newest first by created_at
- Sort selector: Newest first, Oldest first, Due Date (ascending — soonest first), Status (To Do first), Priority (high first)

## 8.3 Action Item Modal (View / Edit / Source Review)

A single modal serves three purposes via tabs or distinct sections: viewing details, editing, and seeing the source review (if any). Tabs are used to keep the modal compact.

### Modal Header

- Title: the action item title (truncated if very long)
- Subtitle: the scope and shop context
- Close (X) button

### Tabs

- Details (default) — shows all fields read-only with an Edit button
- Notes — free-text notes timeline, with an "Add note" composer at the bottom
- Source Review — only visible for AI-extracted items; shows the source review card inline (read-only) and a deep-link to open it on the Reviews page

### Details Tab — Fields

- Title (text)
- Status (badge)
- Scope (Shop / Brand)
- Shop (Region / Shop name) — only for shop-scoped
- Priority (High / Medium / Low) — set by GPT for AI-extracted items, optional for manually-created
- Assignee (avatar + name) with "Reassign" link
- Due date with "Set due date" link if not set
- Created at, created by
- Last updated at

### Edit Mode

- Editable fields: Title, Priority, Due Date, Assignee
- Status is changed via dedicated buttons or the row actions menu, not as a free dropdown in edit mode (to make status transitions auditable)
- Scope and Shop are NOT editable on AI-extracted items (would invalidate the source review's link). They are editable on manually-created items.
- Footer buttons: Cancel / Save Changes

### Notes Tab

- Each note shows: author avatar, author name, timestamp, note text
- Most recent first
- Composer at bottom: textarea + "Add note" button
- Notes cannot be edited or deleted (audit trail)

### Source Review Tab

- Renders a read-only review card identical in structure to the Reviews page card
- "Open in Reviews" link navigates to /admin/org/reviews/?id={review_id} which opens the Reviews list scrolled to that review

## 8.4 Status Workflow

- Four statuses: To Do, In Progress, Complete, Won't Do
- Any-to-any transitions allowed (no enforced order — a user can mark something Won't Do directly without ever moving through In Progress)
- Status changes write to the audit log with old and new status
- Default status on creation: To Do

## 8.5 Manual Action Item Creation

**Trigger:** "+ New Action Item" button on the Action Items list page

**Title:** Create Action Item

**Subtitle:** Add an action item that didn't come from a customer review.

### Fields

| **Field** | **Type** | **Required** | **Validation** |
| --- | --- | --- | --- |
| Title | Text input | Yes | 5–200 characters |
| Scope | Toggle Shop / Brand | Yes | Brand option visible only to Org Admin / Manager |
| Shop | Dropdown | Yes (when Scope = Shop) | One of the user's accessible shops |
| Priority | Dropdown — High / Medium / Low | No | Default: Medium |
| Assignee | Dropdown — team members | No | Default: Unassigned |
| Due Date | Date picker | No | Must be today or future |
| Initial note | Textarea | No | 0–2000 characters |

### Footer Buttons

- Cancel (secondary)
- Create (primary)

### Success Behaviour

- Toast: "Action item created."
- Action Items list refreshes; new row appears at the top

## 8.6 Notification Bell

The notification bell in the top bar gains active behaviour in Phase 3. Until now, it has been a placeholder.

### Counter Behaviour

- Bell shows a small red dot or numeric badge when there are unread notifications
- Click bell — opens a popover panel listing recent notifications
- Notifications are role-scoped: Staff only see notifications for their accessible shops

### Notification Types in Phase 3

| **Type** | **Trigger** | **Recipients** |
| --- | --- | --- |
| new_review | A new review is fetched from Google | Org Admin / Manager (always); Staff if review's shop is in their access scope |
| new_action_item | A new action item is created (AI-extracted or manual) | Org Admin / Manager (always); Staff if action item is shop-scoped to their accessible shop |
| action_item_assigned | An action item is assigned to the user | The assignee only |

### Notification Popover

- Lists last 10 unread notifications, newest first
- Each item: icon (review or action item), short summary, timestamp
- Click a notification — navigates to the relevant page (review or action item) and marks the notification read
- "Mark all as read" link at the top of the popover
- "View all notifications" link at the bottom — navigates to a full notifications page (lightweight; can be deferred if not built in Phase 3)

### Counter Computation

- Counter = count of NotificationDelivery rows for the user where read_at IS NULL
- Counter is fetched via standard HTTP polling every 60 seconds (no WebSocket — see §3.3 scope discipline)
- Counter also refreshes immediately after the user acts on a notification (mark as read, click through)

# 9. Data Model Additions

Phase 3 adds the following entities. All are scoped by organisation_id and follow the conventions established in CLAUDE.md (UUID primary keys, created_at/updated_at, soft-delete where applicable, indexed foreign keys).

## 9.1 Review

- id (PK, UUID)
- organisation_id (FK to Organisation, indexed)
- shop_id (FK to Shop, indexed)
- google_review_id (string) — Google's stable identifier for the review
- reviewer_name, reviewer_avatar_url
- rating (integer 1–5)
- text (text, nullable — Google sometimes returns ratings without text)
- review_created_at, review_updated_at — timestamps from Google's review payload
- sentiment — POSITIVE | NEUTRAL | NEGATIVE | NULL (null when enrichment is pending or failed)
- tags — JSONB array of { label, polarity } objects
- enrichment_status — PENDING | IN_PROGRESS | SUCCESS | FAILED
- enrichment_attempted_at, enrichment_completed_at
- enrichment_error (string, nullable)
- enrichment_version (integer) — increments when the platform's prompt or model is upgraded; allows future bulk re-enrichment if scope expands
- deleted_at (datetime, nullable) — soft delete when Google removes a review
- created_at, updated_at
- Unique constraint: (shop_id, google_review_id)
- Indexes: (organisation_id, review_created_at), (shop_id, review_created_at), (organisation_id, sentiment), (enrichment_status)

## 9.2 ReviewReply

- id (PK, UUID)
- review_id (FK to Review, unique — at most one reply per review)
- text (text, 1–4000 chars)
- posted_by_user_id (FK to User)
- posted_at
- status — POSTED (only success state is persisted; failures don't create rows)
- google_reply_updated_at — timestamp Google reports for the reply
- created_at, updated_at

## 9.3 ActionItem

- id (PK, UUID)
- organisation_id (FK to Organisation, indexed)
- source — AI_EXTRACTED | MANUAL
- source_review_id (FK to Review, nullable, indexed) — populated for AI-extracted items
- scope — SHOP | BRAND
- shop_id (FK to Shop, nullable, indexed) — populated for SHOP scope, NULL for BRAND
- title (string, 5–200 chars)
- priority — HIGH | MEDIUM | LOW
- status — TODO | IN_PROGRESS | COMPLETE | WONT_DO
- assignee_id (FK to User, nullable, indexed)
- due_date (date, nullable)
- created_by_user_id (FK to User)
- created_at, updated_at
- status_changed_at — updated transactionally with each status change
- Constraint: scope = BRAND implies shop_id IS NULL; scope = SHOP implies shop_id IS NOT NULL
- Indexes: (organisation_id, status), (assignee_id, status), (shop_id, status), (scope, organisation_id)

## 9.4 ActionItemNote

- id (PK)
- action_item_id (FK to ActionItem, indexed)
- author_id (FK to User)
- text (text, 1–2000 chars)
- created_at
- Notes are immutable — no update or delete API endpoint

## 9.5 AiUsageLog

Schema documented in detail in §7.3.

## 9.6 AiPricing

Schema documented in detail in §7.3.

## 9.7 Notification

- id (PK)
- organisation_id (FK, indexed)
- type — NEW_REVIEW | NEW_ACTION_ITEM | ACTION_ITEM_ASSIGNED
- payload — JSONB containing the data needed to render the notification (review_id, action_item_id, summary text, etc.)
- created_at

## 9.8 NotificationDelivery

Junction model representing one notification's delivery to a specific user. Allows the same Notification to be unread for one user and read for another.

- id (PK)
- notification_id (FK)
- user_id (FK, indexed)
- read_at (datetime, nullable)
- created_at
- Indexes: (user_id, read_at) for the unread-counter query

## 9.9 Updates to Existing Entities

- Shop — add: initial_sync_started_at, initial_sync_completed_at, last_synced_at, last_sync_error (string, nullable)
- AuditLog — add new actions: review.fetched, review.replied, review.reply_failed, review.enriched, review.enrichment_failed, action_item.created, action_item.status_changed, action_item.assigned, action_item.note_added, ai.usage_logged, sync.started, sync.completed, sync.failed

# 10. Tech Design Updates

## 10.1 Service and Selector Layout

Phase 3 follows the services-and-selectors pattern from CLAUDE.md §5. New service modules:

- apps/reviews/services/sync.py — Google review fetching (initial backfill, incremental sync)
- apps/reviews/services/replies.py — Reply submission and Google posting
- apps/reviews/services/enrichment.py — OpenAI enrichment pipeline orchestration
- apps/reviews/selectors/reviews.py — list/filter/search query primitives
- apps/action_items/services/lifecycle.py — Create, status transitions, assignment, notes
- apps/action_items/services/extraction.py — Convert GPT action item JSON into ActionItem rows
- apps/action_items/selectors/items.py — list/filter primitives, with built-in scope filtering
- apps/notifications/services/dispatch.py — Fan out a Notification to NotificationDelivery rows for the right recipients
- apps/integrations/openai/client.py — Thin wrapper around the OpenAI SDK with LangSmith tracing
- apps/integrations/openai/pricing.py — Cost calculator

## 10.2 Celery Task Layout

| **Task** | **Queue** | **Schedule** |
| --- | --- | --- |
| enqueue_incremental_syncs | google-sync | Beat: every hour at minute 0 |
| sync_shop_reviews(shop_id) | google-sync | Triggered by enqueue_incremental_syncs and by initial backfill |
| initial_backfill(shop_id) | google-sync | Triggered after Google OAuth completion |
| enrich_review(review_id) | ai-enrichment | Triggered after a review is persisted |
| retry_failed_enrichments | ai-enrichment | Beat: every 6 hours |
| dispatch_notification(notification_id) | default | Triggered by services that create Notifications |

## 10.3 API Endpoints

| **Method + Path** | **Purpose** | **Permissions** |
| --- | --- | --- |
| GET /api/v1/reviews/ | List reviews with filters/search/pagination | Authenticated; queryset filtered by user.organisation_id and (for Staff) shop access |
| GET /api/v1/reviews/{id}/ | Single review detail | Same as list |
| POST /api/v1/reviews/{id}/reply/ | Submit a reply | User must have access to the review's shop |
| GET /api/v1/action-items/ | List action items with filters/search/pagination | Authenticated; brand-scoped items hidden from Staff |
| POST /api/v1/action-items/ | Create action item manually | Authenticated; brand scope requires Org Admin/Manager |
| GET /api/v1/action-items/{id}/ | Single action item detail | Authenticated; same scope rules |
| PATCH /api/v1/action-items/{id}/ | Edit action item (title, priority, assignee, due date) | Same as get |
| POST /api/v1/action-items/{id}/status/ | Change status | Same |
| POST /api/v1/action-items/{id}/notes/ | Add a note | Same |
| GET /api/v1/notifications/ | List user's notifications | Authenticated |
| POST /api/v1/notifications/mark-read/ | Mark notifications read (single or bulk) | Authenticated |
| GET /api/v1/sync/progress/?shop_id= | Snapshot of current sync state for a shop | Authenticated; user must have access to shop |
| WS /ws/sync-progress/?shop_id= | WebSocket subscription for real-time sync events | Authenticated session; user must have access to shop |

## 10.4 Query Optimisation Requirements

- GET /api/v1/reviews/ must use select_related on shop and reply, prefetch_related on action_items, and resolve all displayed data in <= 5 SQL queries regardless of page size.
- GET /api/v1/action-items/ must use select_related on shop, assignee, source_review.shop, and resolve in <= 5 queries.
- Filter by Sentiment, Status, Reply Status, etc., all use indexed columns (see §9.1, §9.3 indexes).
- Search uses Postgres full-text search on review.text (with a tsvector column auto-maintained by trigger or migration).
- Notification counter query uses the (user_id, read_at) index for fast retrieval.
- Every list endpoint has a CaptureQueriesContext test asserting the query-count ceiling, per CLAUDE.md §6.9.

## 10.5 Redis Usage Additions

| **Key Pattern** | **Purpose** | **TTL** |
| --- | --- | --- |
| lock:google_sync:shop:{shop_id} | Distributed lock during shop sync | 5 minutes |
| lock:enrich:review:{review_id} | Distributed lock during review enrichment | 5 minutes |
| sync:progress:{shop_id} | Current sync progress snapshot for WebSocket and snapshot API | 24 hours |
| rate:openai:org:{organisation_id} | Per-org OpenAI call counter (token bucket) | Rolling 1 minute |
| rate:google:project | Global Google API call counter (token bucket) | Rolling 1 minute |

## 10.6 Settings Additions

- OPENAI_API_KEY (env var, GCP Secret Manager in prod)
- OPENAI_MODEL (default: gpt-4o-mini-2024-07-18)
- LANGSMITH_API_KEY (env var, GCP Secret Manager in prod)
- LANGSMITH_PROJECT (default: review-platform-{environment})
- CELERY_BROKER_URL, CELERY_RESULT_BACKEND (Redis URLs)
- CHANNEL_LAYERS configuration (Redis URL)
- INITIAL_SYNC_PAGE_SIZE (default: 50 reviews per Google API page)
- ENRICHMENT_BATCH_SIZE (default: 10 — used to throttle progress event emission)
- INCREMENTAL_SYNC_INTERVAL_HOURS (default: 6)
- INCREMENTAL_SYNC_JITTER_MINUTES (default: 30)

# 11. Phase 3 Acceptance Criteria

Each sub-phase has its own acceptance criteria. The full Phase 3 milestone is complete when all four sub-phases meet theirs.

## 11.1 Phase 3a-i — Infrastructure Foundation

- Celery worker and Beat services are running in dev, staging, and production.
- Two named queues (google-sync, ai-enrichment) are configured with separate worker pools.
- A scaffolding task on each queue can be enqueued and executed end-to-end (e.g., a hello-world task that writes to the audit log).
- Flower is running in dev and staging only; production deployment does not expose Flower.
- Django Channels is configured; the SyncProgressConsumer accepts authenticated connections and rejects unauthenticated or cross-tenant ones.
- Redis lock helper utility is implemented and unit-tested (acquire, release, TTL expiry).
- Retry/backoff decorator is implemented; demonstrated with a deliberately failing test task that retries 3 times then fails.
- Sentry integration captures both web and Celery worker exceptions.
- CI passes — including a smoke test that verifies a Celery task completes within 30 seconds in the test runner.

## 11.2 Phase 3a-ii — Reviews Fetching, Display, Reply

- After a shop completes Google OAuth, the initial backfill task is dispatched and runs to completion.
- All historical reviews available from Google are fetched and persisted with no duplicates.
- The Progress Modal opens after OAuth completes, displays both progress bars, and updates in real time via WebSocket.
- Closing the modal collapses to the persistent top-bar indicator; clicking the indicator re-opens the modal.
- Incremental sync runs every 6 hours per shop, jittered, with no duplicates.
- The Reviews list page displays reviews with filters, search, sort, and pagination behaving per spec.
- Filtering by Store, Rating, Reply Status, From Date, and To Date returns correct results; Sentiment filter is present but values are null until Phase 3b-i ships.
- Inline reply UI accepts up to 4000 characters, posts to Google synchronously, and shows the posted reply on success.
- Reply failures show a clear error and do not persist a local row.
- Audit log entries exist for sync.started, sync.completed, review.fetched, review.replied, review.reply_failed.
- All list endpoints render within the query-count ceilings in CI tests.
- Staff users see only reviews for shops in their access scope.

## 11.3 Phase 3b-i — AI Enrichment Pipeline

- OpenAI client wrapper is implemented with retry logic, error handling, and LangSmith tracing.
- Enrichment task processes a review, calls GPT-4o-mini with the combined prompt, parses the JSON response, and writes sentiment + tags + action items to the database.
- Existing reviews from Phase 3a-ii are enriched after deployment (one-time job).
- Each call writes one row to AiUsageLog with all token counts, latency, status, and computed cost.
- AiPricing seed data is loaded for GPT-4o-mini at the model's published rates.
- Cost calculation matches a hand-computed reference within 0.01 USD on a verification dataset.
- LangSmith traces appear in the configured project for every successful enrichment.
- On enrichment failure, the review is marked FAILED, an audit log entry is written, and the retry job picks it up on the next 6-hour cycle.
- Reviews list page now shows sentiment badges and tag chips for enriched reviews.
- Concurrent enrichment of the same review is prevented by the Redis lock.

## 11.4 Phase 3b-ii — Action Items Module

- Each enriched review's action_items are converted into ActionItem rows with correct scope and shop_id linking.
- Brand-scoped items have shop_id IS NULL; shop-scoped items have a non-null shop_id matching the source review's shop.
- Action Items list page displays the table with all specified columns, filters, search, and pagination.
- The Brand-scope filter is visible to Org Admin / Manager and hidden from Staff.
- Staff cannot see brand-scoped action items even by direct URL access (403 returned).
- Action Item modal shows Details, Notes, and Source Review tabs; the Source Review tab is hidden for manually-created items.
- Edit modal saves changes to title, priority, due date, and assignee.
- Status transitions in any direction are allowed and are written to the audit log.
- Manual action item creation works end to end; brand-scope is unavailable to Staff.
- Notes are append-only; existing notes cannot be edited or deleted.
- Notification bell shows unread count and lists recent notifications; click navigates and marks read.
- Notifications respect role and shop scoping (Staff don't see brand action item notifications).

## 11.5 Cross-Cutting Acceptance Criteria

- All routes added in Phase 3 enforce role + tenant scoping at the permission layer.
- All forms enforce the validation rules in this document.
- All pages are responsive at desktop / tablet / mobile breakpoints per the Phase 1 design contract.
- All destructive or sensitive actions show a confirmation popup with consistent copy.
- All audit log events listed in §9.9 are written and queryable.
- Every list endpoint has a CaptureQueriesContext query-count ceiling test in CI.
- Sentry receives errors from both web and Celery workers.
- LangSmith receives traces for every OpenAI call attempted.
- CLAUDE.md has been updated to document Celery, Channels, OpenAI integration, and AI cost tracking conventions.

# 12. Risks and Mitigations

Phase 3 is the largest milestone to date and introduces several new failure modes. The following risks are surfaced explicitly so they can be tracked through implementation and review.

| **Risk** | **Mitigation** |
| --- | --- |
| OpenAI cost runs higher than expected | AI cost is logged per call with token breakdown; an AI usage dashboard for Superadmin (out of scope for Phase 3) will land in a follow-up phase. In the meantime, daily cost reports can be generated by ad-hoc query. |
| Google Business Profile API quota limits halt sync | Token bucket in Redis prevents bursts; per-shop locks prevent duplicate calls; failed shops are logged and retried in the next cycle. Escalation: monitor quota usage in dashboards and request quota increase from Google before scale milestones. |
| GPT returns malformed JSON | Retry once, then mark FAILED. The combined prompt instructs the model to return valid JSON only. JSON schema validation runs server-side. |
| GPT mis-classifies a review's scope (shop vs brand) | Org Admin can edit manually-created items but NOT change scope of AI-extracted items. If GPT routinely mis-classifies, the prompt is iterated. Future enhancement: allow Org Admin to override GPT scope decisions. |
| WebSocket scaling under many concurrent initial syncs | Each shop's progress is published to one Channels group; group membership is small (only the Org Admin's tabs). Redis channel layer handles thousands of concurrent groups without issue. Load test required before launching with > 100 simultaneous initial syncs. |
| Celery worker memory leaks from long-running OpenAI calls | Soft and hard time limits per task. Worker concurrency is small (8 per pod) so a leak doesn't cascade. Worker pods auto-restart based on queue depth; max-memory-per-child setting prevents unbounded growth. |
| Free-text tags create unfilterable noise | Phase 3b-i intentionally ships free-text only; canonical tag normalisation is a planned follow-up. Filter UI for tags is intentionally NOT built in Phase 3 — adding it later requires only canonical tags. |
| Reply posting silently fails to reach Google | Synchronous post means the user sees the failure immediately. If Google later rejects the reply (rare), no automatic re-post — the user retries manually. |
