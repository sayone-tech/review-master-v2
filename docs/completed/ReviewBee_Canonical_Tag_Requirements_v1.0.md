**ReviewBee**

Canonical Tag System

Requirements Specification

| **Version** | v1.0 |
| --- | --- |
| **Date** | June 2026 |
| **Status** | Final |
| **Phase** | Phase 3b.5 — Tag Canonicalization |

# 1. Document Overview

This document specifies the Canonical Tag System for the ReviewBee multi-tenant review management platform. It covers the problem statement, architecture decisions, data model changes, AI pipeline changes, initial sync flow, daily sync behaviour, tag polarity handling, Org Admin tag management, infrastructure requirements, and cost analysis.

This is Phase 3b.5 and builds directly on Phase 3b-i (free-text tag generation). All prior conventions, infrastructure, and data models remain unchanged unless explicitly stated here.

# 2. Problem Statement

The current Phase 3b-i pipeline enriches each review in isolation. Because reviews are processed independently, GPT generates semantically equivalent but textually different tags:

| **Raw Tags Generated (same concept)** | **What They Should Map To** |
| --- | --- |
| good service | Staff & Service |
| Good Customer Service | Staff & Service |
| great staff | Staff & Service |
| Tasty food | Food Quality |
| tasty | Food Quality |
| Good Experience | Overall Experience |

This makes tag-based analytics — trending topics, dashboard charts, action item grouping — unreliable. The problem compounds as the platform onboards more organisations across different business categories.

| **Why Not a Hardcoded Tag List?** A fixed global tag list is not viable. Restaurants, electronics shops, and salons have fundamentally different vocabulary. The solution must self-organise per organisation without manual curation overhead. |
| --- |

# 3. Solution Overview

The canonical tag system leverages GPT's native language understanding to normalise tags within the existing enrichment prompt. No extra API calls. No vector database. No separate moderation pass.

### Core Principles

- One GPT call per review — canonical mapping is folded into the existing enrichment prompt.
- Per-org canonical vocabulary — each organisation builds its own tag list that fits its business category naturally.
- Auto-evolving — new canonical tags are added automatically when GPT identifies a genuinely new theme. No admin approval required.
- English-only canonical tags — reviews may be in any language; tags are always normalised to English.
- No vector database — the canonical tag table is a standard Postgres table. No pgvector, no external service.
- Horizontally scalable — Celery workers scale behind the existing ALB. No architectural changes required.

# 4. Data Model

### 4.1 OrgCanonicalTag Table

One new table stores the canonical vocabulary per organisation.

| **Column** | **Type** | **Constraints** | **Description** |
| --- | --- | --- | --- |
| id | UUID | PK | Primary key |
| organisation_id | FK → Organisation | NOT NULL, INDEX | Owning organisation |
| label | VARCHAR(100) | NOT NULL | Canonical label e.g. "Staff & Service". Title Case. Max 3 words. |
| polarity_type | ENUM | NOT NULL | always_positive / always_negative / mixed. See §5. |
| review_count | INTEGER | DEFAULT 0 | Total reviews mapped to this canonical tag. |
| created_at | TIMESTAMPTZ | NOT NULL | When this canonical tag was first created. |
| updated_at | TIMESTAMPTZ | NOT NULL | Last time a review was mapped to this tag. |

### 4.2 Review Tags JSONB — Updated Shape

The existing tags JSONB column on the Review table gains two new fields. The canonical_tag_id field already present in the schema is now populated from Phase 3b.5 onward.

// Phase 3b-i (current)

{ "label": "good service", "polarity": "positive" }

// Phase 3b.5 (updated)

{ "label": "good service", "polarity": "positive",

"canonical": "Staff & Service", "canonical_tag_id": "uuid-here" }

| **Backward Compatibility** Existing reviews without canonical mapping remain valid. canonical and canonical_tag_id are nullable. Dashboard queries filter to reviews where canonical_tag_id IS NOT NULL when canonical aggregation is needed. |
| --- |

# 5. Tag Polarity Handling

Not all canonical tags carry an inherent polarity. There are three distinct types that must be handled differently in analytics and on the dashboard.

### 5.1 Three Polarity Types

| **polarity_type** | **Example Tags** | **Why** | **Dashboard Behaviour** |
| --- | --- | --- | --- |
| always_positive | Staff & Service, Cleanliness | Vocabulary inherently positive — no one says "Staff & Service" as a complaint | Simple count. No polarity split. |
| always_negative | Long Wait Time, Wrong Order | Vocabulary inherently negative — always a complaint theme | Simple count. No polarity split. |
| mixed | Falooda, Biryani, Parking | Topic-based tag. Polarity depends entirely on what the reviewer said about it. | Split by positive / negative count. |

### 5.2 How polarity_type Is Assigned

GPT assigns polarity_type when it first creates a new canonical tag. This is added to the enrichment prompt:

"When proposing a new canonical tag, also return its polarity_type:

always_positive — if the concept is inherently a positive attribute

always_negative — if the concept is inherently a complaint or negative attribute

mixed — if the concept is a topic that can be either positive or negative"

GPT is reliable at this classification. "Staff & Service" is always positive. "Long Wait Time" is always negative. "Falooda" is a product name — clearly mixed.

### 5.3 Auto-Reclassification (Weekly Celery Job)

A canonical tag may start as always_positive but accumulate negative instances over time as the vocabulary matures. A weekly background job detects and corrects this automatically.

- For each OrgCanonicalTag where polarity_type is always_positive or always_negative:
- Check the polarity distribution of reviews mapped to this tag over the last 30 days.
- If the opposite polarity exceeds 15% of total mapped reviews → reclassify to mixed.
- No GPT call required — pure database aggregation query.
- Reclassification is logged in the system. Org Admin can see updated polarity_type on the tag list page.

| **Per-Review Polarity Already Stored** The raw tag JSON already stores "polarity": "positive/negative/neutral" per review. No data change is needed on reviews. The polarity_type on OrgCanonicalTag only controls how the dashboard presents the data — split or unsplit. |
| --- |

# 6. AI Enrichment Pipeline Changes

### 6.1 What Changes in the GPT Prompt

The existing single GPT call (sentiment + tags + action items) is extended with three additions:

- Inject the org's existing canonical tags into the prompt context.
- Instruct GPT to map each generated tag to a canonical tag or propose a new one with a polarity_type.
- Enforce English output for all tags regardless of review language.

"Language rule: Always generate raw tags and canonical tags in English,

regardless of the language of the review text."

"Existing canonical tags for this organisation:

["Staff & Service", "Food Quality", "Ambience", "Wait Time", ...]

For each tag you generate:

- If it matches an existing canonical tag semantically → use that label exactly.

- If no match → propose a new canonical label (Title Case, max 3 words, English)

and include its polarity_type: always_positive | always_negative | mixed."

### 6.2 Updated JSON Output Shape

{

"sentiment": "positive",

"tags": [

{ "label": "good service", "polarity": "positive",

"canonical": "Staff & Service", "polarity_type": null },

{ "label": "falooda was bad", "polarity": "negative",

"canonical": "Falooda", "polarity_type": "mixed" }

],

"action_items": [ ... ]

}

polarity_type is null when the canonical tag already exists in OrgCanonicalTag. It is populated only when GPT proposes a new canonical tag.

### 6.3 Post-Enrichment Processing (per review)

- For each tag in the GPT response, look up canonical label in OrgCanonicalTag for this organisation.
- If found — populate canonical_tag_id. Done.
- If not found (new canonical proposed) — insert new OrgCanonicalTag row with the polarity_type from GPT, then populate canonical_tag_id.
- Increment review_count on the matched or newly created OrgCanonicalTag row.
- Save updated tags JSONB and canonical_tag_id on the Review row.

### 6.4 Token Cost Impact

Injecting the canonical tag list adds approximately 150–300 extra input tokens per review depending on org vocabulary maturity. This is the only cost increase.

| **Metric** | **Current** | **With Canonical Tags** |
| --- | --- | --- |
| Tokens per review | ~800 | ~950–1,100 |
| Extra tokens per review | — | ~150–300 |
| Extra cost per review (GPT-4o-mini) | — | ~$0.000056–$0.000113 |
| Extra API calls | — | Zero |
| Context window risk | — | None (300 tags ≈ 1,800 tokens, well within 128k limit) |

| **No Extra API Calls** Canonical tag creation, lookup, and polarity assignment all happen within the existing single GPT call. Post-enrichment steps are pure database operations. |
| --- |

# 7. Initial Sync Flow

### 7.1 Four-Step Progress UI

The existing two-step progress UI (Fetch Reviews, AI Enrichment) is replaced with four steps. Progress is shown per store — stores are typically onboarded one at a time.

| **#** | **Step Label** | **Progress Text** | **Notes** |
| --- | --- | --- | --- |
| 1 | Fetching Reviews | Fetched 340 of 500 reviews | Existing step — unchanged. Pulls from Google Business Profile. |
| 2 | Building Tag Vocabulary | Analysing review 34 of 50… | NEW — Seed phase. First 50 reviews processed sequentially so each review sees tags from all previous ones. Vocabulary stabilises quickly. |
| 3 | AI Enrichment | Enriched 280 of 450 reviews | Existing step — enhanced. Remaining reviews in parallel with the stable vocabulary from Step 2. |
| 4 | Finalising | Cleaning up… | NEW — Dedup pass. Any remaining tag duplicates resolved via string match. Backfills canonical_tag_id on stragglers. Short (~seconds). |

| **Why Show Step 2 Separately?** Without a dedicated "Building Tag Vocabulary" step, users see the enrichment bar stuck on the first 50 reviews for longer than expected and assume something is broken. The named step sets the correct expectation. |
| --- |

### 7.2 Seed Phase (Step 2)

- Process exactly 50 reviews sequentially — one at a time, not in parallel.
- After each review the canonical tag table is updated before the next review starts.
- 50 reviews is sufficient to establish ~80% of the vocabulary for most business types.
- If the store has fewer than 50 reviews, the seed phase processes all of them sequentially.
- Seed phase runs on the ai-enrichment-high Celery queue.

### 7.3 Bulk Phase (Step 3)

- All remaining reviews (after the seed 50) are processed in parallel.
- Each review receives the current canonical tag list at the time of the call.
- New canonical tags may still be added during bulk phase and propagate to subsequent reviews.
- Bulk phase runs on the ai-enrichment-high queue during initial sync.

# 8. Daily Sync Flow

During daily incremental sync, new reviews are enriched using the same updated pipeline. The org's existing canonical vocabulary is injected into the prompt automatically.

- New review arrives from Google.
- Enrichment task fetches the org's current OrgCanonicalTag list.
- GPT maps each generated tag to an existing canonical tag, or proposes a new one with polarity_type.
- If a new canonical tag is proposed — auto-added to OrgCanonicalTag without any review or approval.
- review_count updated on matched or new canonical tag.
- Review saved with updated tags JSONB and canonical_tag_id.

For an established store, the vocabulary is stable. New canonical tags are rarely added. Daily sync runs on the ai-enrichment-low Celery queue so it does not compete with initial sync tasks from newly onboarding stores.

# 9. Org Admin Tag Management

### 9.1 Access

- Route: /admin/org/tags/
- Roles: Org Admin and Manager.
- Sidebar: Tags (tag icon) under the Settings group.

### 9.2 Tag List Page

| **Column** | **Type** | **Sortable** | **Notes** |
| --- | --- | --- | --- |
| Tag Label | Text | Yes | Editable inline on click. |
| Polarity Type | Badge | Yes | always_positive / always_negative / mixed. |
| Review Count | Number | Yes | Total reviews using this canonical tag. |
| First Seen | Date | Yes | created_at date. |
| Actions | Menu | No | Rename / Merge. |

### 9.3 Rename a Tag

- Inline edit on Tag Label cell — click to edit, press Enter or click away to save.
- Validation: 1–100 characters, unique within the org.
- On save: updates OrgCanonicalTag.label and all Review tags JSONB rows synchronously (row count is small — direct DB update, no Celery task needed).
- Toast: "Tag renamed successfully."

### 9.4 Merge Tags

Allows the Org Admin to merge two canonical tags into one. All reviews mapped to the source tag are re-pointed to the target tag.

### 9.4.1 Trigger

- Row action menu → "Merge into another tag".
- Modal: "Merge [Source Tag] into…" with a searchable dropdown of all other canonical tags for the org.
- Warning in modal: "This will re-map all [N] reviews currently tagged [Source] to [Target]. This cannot be undone."
- Confirm button: "Merge Tags".

### 9.4.2 Celery Task

- On confirm, a merge_canonical_tags Celery task is enqueued on the tag-merge queue.
- Task processes reviews in batches, updating canonical and canonical_tag_id in the tags JSONB.
- Progress is pushed to the UI via WebSocket (Django Channels) — same pattern as shop sync.
- Progress state persists through page dismiss or reload — UI reconnects via WebSocket on return.
- On completion:
- Source OrgCanonicalTag row deleted.
- All mapped Review tags JSONB updated to point to target tag.
- review_count on target tag updated to combined total.
- Notification bell: "Tag merge complete. [N] reviews updated."

### 9.4.3 Progress States

| **State** | **UI Behaviour** |
| --- | --- |
| In progress | Progress bar: "Updating reviews… X of N". Dismiss button available. |
| After dismiss | Persistent status indicator in header (same pattern as shop sync). Reconnects on reload. |
| Complete | Toast: "Tag merge complete. N reviews updated." Progress indicator removed. |
| Failed | Notification bell entry with error. Partial updates rolled back. |

# 10. Multilingual Review Support

ReviewBee operates in markets where reviews may be written in any language. The canonical tag system handles this transparently.

| **Layer** | **Behaviour** |
| --- | --- |
| Review text | Any language. Stored as-is. GPT understands content regardless of language. |
| Raw tag label | Always English. Enforced by prompt instruction. |
| Canonical tag label | Always English. OrgCanonicalTag.label is always English. |
| Sentiment | Language-agnostic — positive / neutral / negative. No change. |
| Action items | Generated in English regardless of review language. Same prompt instruction. |

| **No Extra Cost for Multilingual** GPT-4o-mini natively understands and generates across languages. No translation step, no separate language detection call. The single enrichment prompt handles all languages. |
| --- |

# 11. Infrastructure & Scalability

### 11.1 Celery Queue Structure

Three priority queues are introduced to prevent initial sync tasks from starving daily sync, and to isolate long-running merge jobs.

| **Queue** | **Used For** | **Notes** |
| --- | --- | --- |
| ai-enrichment-high | Initial sync (seed + bulk phases) | Higher worker allocation. Ensures new store onboarding completes fast. |
| ai-enrichment-low | Daily incremental sync | Standard worker allocation. Runs continuously throughout the day. |
| tag-merge | Canonical tag merge tasks | Isolated queue to prevent long-running merges affecting enrichment throughput. |

### 11.2 OpenAI Rate Limit Management

At scale, with multiple stores onboarding simultaneously, all enrichment tasks across all workers share a global Celery rate limit to stay within OpenAI's per-minute token limits.

@app.task(rate_limit="500/m")

def enrich_review_task(review_id):

...

500 tasks per minute is a safe default. This is a configuration value — it should be tuned against the actual TPM (tokens per minute) limit on the OpenAI account dashboard. If 10 stores onboard simultaneously with 500-review backlogs each, the rate limiter ensures the total GPT call rate stays within limits regardless of how many Celery workers are running.

| **Rate Limit Is Global Across All Workers** The Celery rate_limit applies per task type globally, not per worker instance. Adding more ALB instances or Celery workers does not bypass this limit — it is enforced at the task queue level. |
| --- |

### 11.3 Horizontal Scaling

- Web layer: scales horizontally behind existing ALB — no change.
- Celery workers: scaled by adding instances, distributed across the three queues.
- OrgCanonicalTag reads (injecting tag list into prompt): simple indexed SELECT. Postgres handles this easily at 1,000+ stores.
- OrgCanonicalTag writes (new canonical tag creation): rare after initial sync. No concurrency issues.
- No vector database, no embedding service, no new infrastructure required.

# 12. Data Reset — Existing 56-Store Brand

The existing 56-store brand has approximately 224,000 reviews with free-text tags and no canonical mapping. All data will be wiped and re-synced from scratch through the updated pipeline.

| **Full Data Wipe Confirmed** All data — reviews, enrichment results, tags, action items, and any existing OrgCanonicalTag rows — will be deleted for this organisation. Re-sync will pull all reviews fresh from Google Business Profile and run them through the new pipeline including canonical tag generation and polarity type assignment. |
| --- |

### 12.1 Reset Steps

- Superadmin triggers the data reset for the organisation via the Superadmin panel.
- All Review, AiUsageLog, ActionItem, and OrgCanonicalTag rows for the organisation are deleted.
- Each store's sync status is reset to "Not synced".
- Org Admin initiates re-sync per store individually through the normal store sync flow.
- Each store runs the full four-step initial sync: Fetch → Build Tag Vocabulary → AI Enrichment → Finalising.

### 12.2 Estimated Re-sync Cost & Time

| **Item** | **Estimate** |
| --- | --- |
| Total reviews to re-enrich | 56 × ~4,000 = ~224,000 reviews |
| Cost per review (enrichment + canonical) | ~$0.000356 |
| Total one-time re-enrichment cost | ~$79.74 |
| Estimated time at 500 tasks/min | ~7.5 hours (parallelised across stores) |

# 13. Cost Analysis

### 13.1 Monthly Cost — 56-Store Brand (Current Scale)

| **Item** | **Cost** |
| --- | --- |
| 56 stores × ~45 reviews/week × 4 weeks = 10,080 reviews/month |   |
| Current enrichment cost | ~$6.05 / month |
| Extra for canonical tag injection (~150 tokens/review) | ~$0.60 / month |
| New total monthly AI cost | **~$6.65 / month** |

### 13.2 Monthly Cost — 1,000 Stores (Target Scale)

| **Item** | **Cost** |
| --- | --- |
| 1,000 stores × 300 reviews/month = 300,000 reviews/month |   |
| Enrichment + canonical tag injection | ~$106.80 / month |
| Polarity reclassification job (weekly, DB only) | $0.00 |
| Total monthly AI cost at 1,000 stores | **~$106.80 / month** |

| **Revenue vs AI Cost** At ₹299/store/month across 1,000 stores, revenue is ₹2,99,000/month (~$3,600 USD). Total AI cost of ~$107/month represents under 3% of revenue. |
| --- |

# 14. Delivery Plan

| **Phase** | **Label** | **Scope** |
| --- | --- | --- |
| 3b.5 | Canonical Tag Foundation | OrgCanonicalTag table, polarity_type field, GPT prompt changes, post-enrichment processing, four-step progress UI, three Celery queues, OpenAI rate limit config, data reset for 56-store brand. |
| 3b.5 (cont.) | Auto-Reclassification | Weekly Celery Beat job to reclassify fixed polarity tags to mixed when opposite polarity exceeds 15% threshold. |
| 4 | Tag Management UI | Org Admin tag list page, inline rename, merge with Celery task and WebSocket progress persisting through dismiss/reload. Tag-based charts on dashboard with polarity split for mixed tags. |
| 5 | Cross-Org Insights | Top canonical tags across all orgs in a category. Superadmin analytics. Benchmarking between orgs. Deferred — low priority. |

# 15. Out of Scope

- Vector database or pgvector — not required.
- Superadmin approval workflow for new canonical tags — auto-add is sufficient.
- Platform-level shared canonical tag vocabulary across orgs.
- Cross-org tag benchmarking — deferred to Phase 5.
- Manual override of polarity_type by Org Admin — auto-assignment and auto-reclassification handle this.
- Hard delete of canonical tags — Org Admin must use merge instead.
- Canonical tags for action items — action items remain free text; canonical tags apply to review tags only.
- Migration of existing orgs other than the 56-store brand — not in scope for Phase 3b.5.

End of Document
