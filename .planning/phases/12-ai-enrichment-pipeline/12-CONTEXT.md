---
phase: 12
phase_name: AI Enrichment Pipeline
status: context_complete
created_at: "2026-05-02"
---

# Phase 12 Context — AI Enrichment Pipeline

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the OpenAI GPT-4o-mini enrichment pipeline: enrich every fetched review with sentiment,
tags, and extracted action items; track costs at log time with immutable AiPricing; trace all
calls in LangSmith. Covers ENRCH-01 through ENRCH-14.

Phase 11 built the rendering scaffolding (SentimentBadge, tag chips, Review model fields).
Phase 12 makes those badges show real data.

Phase 13 owns the full ActionItem model, status workflow, and assignment UI.

</domain>

<decisions>
## Implementation Decisions

### Prompt design

- **Prompt context per review:** Organisation name (brand) + shop name + review text + star rating
- **No shop address** — shop name is sufficient for location disambiguation; address adds tokens without improving enrichment quality
- **Reviewer name excluded** — not needed for sentiment/tag/action-item quality
- **Action item tone:** Both SHOP-scoped (operational, specific: "Fix broken AC at this location") and BRAND-scoped (strategic pattern: "Staff training needed across all shops"). The `scope` field in the JSON output determines which applies naturally — no separate tone instruction needed
- **Tags:** Free-form — GPT generates the most relevant 1–5 tags from review content; no predefined category list
- **Language:** All output (tags, action item titles, sentiment label) in English regardless of review language; GPT handles translation internally

### Action items storage

- GPT-extracted action items stored in a new `extracted_action_items = JSONField(default=list)` on the Review model
- Phase 13 promotes these JSON entries to full ActionItem model rows (with assignee, due date, status workflow)
- **REVW-08 partial delivery in Phase 12:** Render action item chips on the review card from the `extracted_action_items` JSON field. Chips are non-interactive (no click/modal) in Phase 12. Phase 13 adds the full modal when ActionItem rows exist.

### Enrichment trigger timing

- **Inline per review, immediately after `fetch_and_persist` upserts the row:** `enrich_review_task` is enqueued for every upserted review (new or updated)
- Applies to both initial backfill AND incremental syncs — same trigger path for all syncs
- Updated reviews have `enrichment_status` reset to `PENDING` by SYNC-05, so they are re-enriched automatically without special-casing
- Enrichment starts in parallel with subsequent sync pages — fastest path to enriched data

### Two-stage progress modal (key Phase 12 change)

- **`sync.enrichment.progress` events** must be emitted from enrich_review_task back to the SyncProgressConsumer via channel layer. The ProgressModal's second progress bar (already scaffolded in Phase 11) is driven by these events in real time
- **`sync.complete` semantics CHANGE in Phase 12:** The event fires only when `total_enriched >= total_fetched` (both fetch AND enrichment done). This is a breaking change from Phase 11 where sync.complete fired after fetch only
- The "Sync complete" banner in the ProgressModal only appears once both progress bars hit 100%
- **"Run in background" behaviour unchanged:** clicking it closes the modal immediately at any stage (fetch or enrichment). The topbar bell keeps the shop active until `sync.complete` fires (i.e. until enrichment is also done)
- The topbar bell removes the shop from the active list only on `sync.complete` — so it correctly tracks the full two-stage lifecycle

### AiPricing and AiUsageLog

- Both models live in `apps/integrations/openai/` — consistent with CLAUDE.md §14
- AiPricing managed via Django admin only (no custom Superadmin UI in Phase 12)
- Rate changes are rare; Django admin is sufficient for Superadmin to add new pricing rows
- Seed data for GPT-4o-mini at published rates loaded via data migration

### Claude's Discretion

- Exact prompt wording and system/user message split
- LangSmith trace metadata structure (beyond the mandatory fields from ENRCH-11)
- Retry logic edge cases within the bounds of ENRCH-04
- How enrichment tasks publish progress back to the channel layer (channel name convention)
- One-time backfill management command internal structure (ENRCH-13)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### AI enrichment requirements
- `.planning/REQUIREMENTS.md` §Phase 12 — ENRCH-01 through ENRCH-14 (all pending)

### OpenAI integration architecture
- `CLAUDE.md` §14 — Full OpenAI integration spec: module layout, single combined prompt,
  AiUsageLog fields, AiPricing time-versioned model, cost formula, LangSmith tracing,
  failure handling, idempotency, settings additions, required dependencies, testing guidance

### Celery task conventions
- `CLAUDE.md` §12 — Task wrapper pattern, queue routing, retry config, idempotency layers

### Background task idempotency
- `CLAUDE.md` §12.4 — Three-layer idempotency: DB uniqueness + Redis lock + status flag +
  select_for_update. enrich_review follows this exactly

### Channels / WebSocket event contracts
- `CLAUDE.md` §13.5 — WebSocket event payload definitions including `sync.enrichment.progress`
  and `sync.complete` (Phase 12 changes sync.complete semantics: fires after enrichment done)

### Existing rendering scaffolding
- `frontend/src/widgets/review-management/SentimentBadge.tsx` — Already handles all three
  enrichment states (PENDING → "Analyzing...", SUCCESS → badge+chips, FAILED → red icon)
- `frontend/src/widgets/review-management/ProgressModal.tsx` — Two-stage modal already
  scaffolded; needs `sync.enrichment.progress` handler wired in Phase 12
- `frontend/src/widgets/review-management/types.ts` — `EnrichmentStatus`, `Sentiment`,
  `ReviewTag`, `TagPolarity` types already defined

### Review model
- `apps/reviews/models.py` — `Review.enrichment_status`, `Review.sentiment`, `Review.tags`
  fields already exist; Phase 12 adds `extracted_action_items = JSONField`
- `apps/reviews/serializers.py` — `ReviewReadSerializer` already includes enrichment fields

### Existing infrastructure
- `apps/common/locks.py` — `distributed_lock` helper; enrich_review uses `lock:enrich:review:{review_id}`
- `apps/common/retry.py` — `with_retry` decorator; not used for enrich (Celery autoretry_for handles it)
- `apps/integrations/google/` — Structure to mirror for `apps/integrations/openai/`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SentimentBadge` (`frontend/src/widgets/review-management/SentimentBadge.tsx`): fully
  built, renders correctly for PENDING/SUCCESS/FAILED states — no changes needed for enrichment
- `ProgressModal` (`frontend/src/widgets/review-management/ProgressModal.tsx`): two-stage
  scaffolding exists; add `sync.enrichment.progress` handler and update `sync.complete` timing
- `distributed_lock` (`apps/common/locks.py`): use for `lock:enrich:review:{review_id}`, 5-min TTL
- `apps/integrations/google/` structure: mirrors what `apps/integrations/openai/` should look like

### Established Patterns
- Celery task = thin wrapper over service function; business logic in `apps/reviews/services/enrichment.py`
- Three-layer idempotency: DB constraint + Redis lock + `select_for_update` status flag transition
- `@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, ...)` — follow Phase 10/11 pattern
- `apps/integrations/openai/` does NOT exist yet — create from scratch following google/ layout

### Integration Points
- `fetch_and_persist` service (`apps/reviews/services/sync.py`): add `enrich_review_task.delay(review.pk)` after each upsert
- `SyncProgressConsumer` (`apps/reviews/consumers.py`): add `sync.enrichment.progress` handler; change `sync.complete` firing condition
- `enrich_review_task`: routes to `ai-enrichment` queue (already configured in Celery settings)
- `Review.tags` (JSONField): already exists — populated by enrichment with sentiment tags
- New `Review.extracted_action_items` (JSONField): add via migration; populated by enrichment
- `ReviewReadSerializer`: add `extracted_action_items` field so chips render from API
- `ReviewTable.tsx`: add action item chips column from `extracted_action_items` (REVW-08 partial)

</code_context>

<specifics>
## Specific Ideas

- "The Progress Modal should not dismiss until AI enrichment is also complete" — `sync.complete`
  fires only after `total_enriched >= total_fetched`. The topbar bell keeps showing the shop
  until that point. "Run in background" still closes the modal immediately (user's choice).
- Action item chips on review card in Phase 12 are non-interactive (no modal). Just visual
  indicators of how many AI-extracted items exist. Phase 13 makes them clickable.
- Tags are free-form English regardless of review language — consistent aggregation across shops.

</specifics>

<deferred>
## Deferred Ideas

- AI cost dashboard for Superadmin — data model ships in Phase 12; UI deferred post-v0.3 (per REQUIREMENTS.md)
- Re-processing historical reviews on prompt version bump — `enrichment_version` field is ready; bulk re-enrichment deferred
- Per-org OpenAI rate cap / token budget enforcement — Redis `rate:openai:org:{organisation_id}` key defined in CLAUDE.md §7.7 but UI/enforcement logic is future
- Action item chips clicking to open detail modal — Phase 13 (needs ActionItem model rows)
- Reviewer name in prompt for personalised reply suggestions — future phase

</deferred>

---

*Phase: 12-ai-enrichment-pipeline*
*Context gathered: 2026-05-02*
