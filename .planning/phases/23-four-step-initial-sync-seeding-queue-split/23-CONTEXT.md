# Phase 23: Four-Step Initial Sync, Seeding & Queue Split - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Orchestrate a store's **initial review sync as four visible steps** —
Fetching Reviews → Building Tag Vocabulary → AI Enrichment → Finalising — built
on top of the Phase 22 canonical-tag pipeline. The seed phase enriches the first
N reviews **sequentially** (vocabulary stabilises), the bulk phase enriches the
rest **in parallel**, and a **finalising pass** merges residual duplicate
canonical tags + backfills stragglers. Daily incremental sync runs new reviews
through the same pipeline on a low-priority queue, and enrichment/merge work is
isolated across dedicated Celery queues (`ai-enrichment-high`, `ai-enrichment-low`,
`tag-merge`).

Maps requirements **SEED-01, SEED-02, SEED-03, SEED-04, DSYNC-01, QUEUE-01**.

**NOT in this phase:** Phase 24 (weekly polarity auto-reclassification job +
reclassification visibility); Phase 25 (Org Admin Tags page / rename / merge UI +
dashboard polarity split); Phase 26 (Superadmin data reset). No new WebSocket
consumer — the existing `SyncProgressConsumer` is **extended** 2→4 stages
(CLAUDE.md §13.2 scope discipline).
</domain>

<decisions>
## Implementation Decisions

> The user delegated all four discussed gray areas to Claude's judgment
> ("you decide the better approach"). The decisions below are Claude's, grounded
> in Phase 22 precedent (D-02/D-03/D-06) and the ROADMAP success criteria. They
> are LOCKED for planning unless the user revisits.

### Four-step mapping & seed UX (SEED-01, SEED-02, SEED-03)
- **D-01:** The four progress steps map to the pipeline as:
  **Fetching Reviews** = Google fetch (existing `sync.fetch.progress`);
  **Building Tag Vocabulary** = the **sequential seed phase** (first N reviews,
  real GPT enrichment, vocabulary grows one review at a time);
  **AI Enrichment** = the **parallel bulk phase** (remaining reviews);
  **Finalising** = the dedup/backfill/count-refresh pass.
  Rationale: the seed reviews ARE enriched (not a throwaway pre-pass), so this is
  the fewest GPT calls and the most faithful labelling — no review is enriched
  twice. Do NOT add a separate vocabulary-only pass that re-enriches the first N.
- **D-02:** Progress text is **per-step with counts**, e.g. `Building vocabulary
  12/50`, `Enriching 340/520`. Extend the `SyncProgressConsumer` and the
  `sync:progress:{shop_id}` Redis snapshot to carry a `step` discriminator and
  per-step counters. Add event types following CLAUDE.md §13.5 conventions
  (e.g. `sync.vocab.progress`, `sync.finalising.progress`) — same `type`-tagged
  JSON shape; keep `sync.complete` / `sync.error`. No new consumer.

### Seed selection & size (SEED-02)
- **D-03:** The seed set is the **newest N reviews** (most representative of
  current tag patterns), processed sequentially. If the store has fewer than N
  reviews, seed all of them.
- **D-04:** N is a **configurable Django setting** (`SEED_PHASE_SIZE`, default
  **50**), mirroring the D-02/Phase-22 configurable-setting precedent. The
  sequential loop re-reads the org vocabulary each iteration (the existing
  `get_org_vocabulary` selector already queries current state per call), so each
  seed review sees canonical tags added by earlier seed reviews — no extra
  machinery required.

### Finalising pass: dedup, merge winner & review_count (SEED-04, resolves D-03/P22)
- **D-05:** **Duplicate definition** — two `OrgCanonicalTag` rows in the same org
  are duplicates when their **normalized Title-Case labels match
  case-insensitively** (the 22-03 normalizer already enforces Title-Case ≤3
  words, so this is primarily a case/whitespace guard). No fuzzy/semantic
  matching this phase.
- **D-06:** **Merge winner = higher `review_count`** (tie → **earliest
  created**). Re-point the loser's `ReviewTag.canonical_tag` FKs to the winner,
  keep the **winner's `polarity_type`**, then delete the loser. Higher-usage
  label stays canonical (better UX than arbitrary first-created).
- **D-07:** The finalising pass also **backfills `canonical_tag` on null
  stragglers** and **refreshes the `review_count` cache** — this resolves the
  Phase 22 **D-03 deferral** (review_count is the derived/cached count, refreshed
  by a merge/finalising task, **never incremented inline**). Merge + backfill +
  count-refresh run on the dedicated **`tag-merge`** queue.

### Global rate limiter & queue split (QUEUE-01, DSYNC-01, resolves D-06/P22)
- **D-08:** **Build the true cross-worker global rate limiter now** — a **Redis
  token bucket** (using the existing `rate:openai:*` Redis convention,
  CLAUDE.md §7.7) that gates enrichment across ALL workers to a configurable
  aggregate (~500/min). The Phase-22 per-worker `rate_limit` stays as a
  **secondary guard**. This honors the Phase 22 **D-06** deferral ("true global
  limiter deferred to Phase 23") and matters precisely under parallel bulk
  enrichment hitting OpenAI TPM limits. Always-on (not opt-in) — the parallel
  bulk phase makes it load-bearing.
- **D-09:** **Queue split** — `ai-enrichment-high` (initial-sync seed + bulk
  enrichment), `ai-enrichment-low` (daily incremental enrichment), `tag-merge`
  (finalising/merge/count-refresh jobs). Update `CELERY_TASK_ROUTES`,
  `CELERY_QUEUE_NAMES`, and worker `-Q` args (CLAUDE.md §12.1/§20). The exact
  mechanism for routing the SAME `enrich_review_task` to high vs low (e.g.
  `apply_async(queue=...)` override vs context flag) is a planning/research
  choice — not locked here.
- **D-10:** Daily incremental sync (DSYNC-01) routes its enrichment to
  `ai-enrichment-low`; new canonical tags are **auto-added with no approval
  step** (consistent with the Phase 22 pipeline). No vocabulary cap change.

### Claude's Discretion
- Exact new event `type` names and Redis snapshot schema for the 4 steps (follow
  CLAUDE.md §13.5 payload conventions).
- The high-vs-low queue routing mechanism for `enrich_review_task` (D-09).
- Token-bucket implementation details (refill cadence, key TTL) within the
  CLAUDE.md §7.7 `rate:openai:*` convention.
- Beat-schedule wiring for the daily incremental fan-out (reuse the existing
  `enqueue_incremental_syncs_task` pattern).
- Whether `review_count` is a refreshed denormalized column vs computed-on-read
  aggregate (D-03/P22 permits either, as long as it is never incremented inline);
  pick the simpler one that satisfies the D-02 vocab cap ordering.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 23: Four-Step Initial Sync, Seeding & Queue Split" — goal + 5 success criteria.
- `.planning/REQUIREMENTS.md` §"v0.8 Requirements" — SEED-01..04, DSYNC-01, QUEUE-01 (and QUEUE-02 history).
- `.planning/phases/22-canonical-tag-foundation-mapping-pipeline/22-CONTEXT.md` — prior decisions D-02 (configurable cap), D-03 (review_count derive-on-read), D-04 (FK-only), D-06 (global limiter deferred HERE).
- `.planning/phases/22-canonical-tag-foundation-mapping-pipeline/22-VERIFICATION.md` — the two Phase-22 deferrals (review_count, global limiter) this phase resolves.

### Codebase touch points
- `apps/reviews/consumers.py` — `SyncProgressConsumer` (extend 2→4 stages; no new consumer).
- `apps/reviews/services/sync.py` — `run_initial_backfill`, `run_incremental_sync` (seed/bulk orchestration lands here).
- `apps/reviews/services/enrichment.py` — `enrich_review`, `_persist_success` (canonical fold-in from Phase 22; bulk/seed call this).
- `apps/reviews/selectors/canonical_tags.py` — `get_org_vocabulary` (re-queried per seed iteration).
- `apps/reviews/tasks.py` — `initial_backfill_task`, `sync_shop_reviews_task`, `enrich_review_task`, `retry_failed_enrichments_task`, `enqueue_incremental_syncs_task` (queue routing + new finalising/merge task).
- `config/settings/base.py` §"Celery" — `CELERY_TASK_ROUTES`, `CELERY_QUEUE_NAMES` (lines ~119-195); add `SEED_PHASE_SIZE` + global-rate-limit settings.
- `apps/reviews/models.py` — `OrgCanonicalTag` (review_count cache), `ReviewTag.canonical_tag`.

### Conventions (CLAUDE.md)
- §12 Celery (queues, routes, thin tasks, idempotency), §13 Channels (§13.2 scope discipline — extend, don't add consumers; §13.5 event payloads), §7.6/§7.7 Redis locks + `rate:openai:*` token bucket.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_org_vocabulary(*, organisation_id, limit)` — already re-queries live state; the sequential seed loop reuses it as-is (no new selector for seed coherence).
- `SyncProgressConsumer` + `sync:progress:{shop_id}` Redis snapshot — extend with a `step` discriminator rather than adding a consumer.
- `enqueue_incremental_syncs_task` Beat fan-out pattern — reuse for the daily DSYNC-01 fan-out.
- Phase-22 `enrich_review` / `_persist_success` — the seed and bulk phases both call this unchanged; canonical mapping already happens inside it.

### Established Patterns
- Celery `CELERY_TASK_ROUTES` + `CELERY_QUEUE_NAMES` + worker `-Q` (CLAUDE.md §12.1, §20) — the queue split follows this exact wiring.
- Configurable operational knobs as Django settings with generous defaults (Phase 22 D-02).
- review_count is a cache refreshed by a merge/finalising task, never incremented inline (Phase 22 D-03).

### Integration Points
- New `tag-merge` queue + finalising task hooks onto the end of `run_initial_backfill`.
- Global token-bucket limiter gates `enrich_review` (or its task) across workers.
- Daily incremental enrichment routes to `ai-enrichment-low`; initial sync to `ai-enrichment-high`.
</code_context>

<specifics>
## Specific Ideas

- Step labels are exactly: **Fetching Reviews → Building Tag Vocabulary → AI Enrichment → Finalising** (ROADMAP SC #1 — use verbatim).
- `SEED_PHASE_SIZE` default **50**; newest-first.
- Global enrichment aggregate target ~**500/min** (Redis token bucket), per-worker rate_limit retained as secondary guard.
</specifics>

<deferred>
## Deferred Ideas

- **Fuzzy/semantic duplicate merging** (beyond case-insensitive label match) — not this phase; the Phase 25 Tags page handles manual rename/merge, and Phase 24 handles polarity reclassification.
- **Weekly polarity auto-reclassification + reclassification visibility** — Phase 24.
- **Org Admin Tags page (rename/merge UI), dashboard polarity split** — Phase 25.
- **Superadmin data reset** — Phase 26.

None of the discussion drifted outside the phase scope.
</deferred>

---

*Phase: 23-four-step-initial-sync-seeding-queue-split*
*Context gathered: 2026-06-10*
