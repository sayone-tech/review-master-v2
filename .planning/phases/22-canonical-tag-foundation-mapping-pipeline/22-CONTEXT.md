# Phase 22: Canonical Tag Foundation & Mapping Pipeline - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the per-organisation **canonical tag vocabulary** inside the existing single GPT enrichment call. Deliverables:
- A new `OrgCanonicalTag` model (per-org, Title Case label ≤3 words, `polarity_type`, timestamps, direct `organisation` FK, unique `(organisation, label)`).
- A new **nullable `canonical_tag` FK on the relational `ReviewTag` model** (no `Review.tags` JSONB — that was dropped in v0.6 Phase 17).
- The enrichment prompt injects the org's current canonical vocabulary; GPT maps each generated tag to an existing canonical label or proposes a new one (with a `polarity_type`) **in the same single call** — no extra OpenAI call, no vector DB.
- Post-enrichment lookup/insert that populates `canonical_tag` and creates new `OrgCanonicalTag` rows, all inside the existing `_persist_success` `transaction.atomic()` block.
- A global, configurable Celery rate limit (~500/min) on the enrichment task (QUEUE-02).

Maps requirements **CTAG-01…08, QUEUE-02**.

**NOT in this phase** (later v0.8 phases): the four-step initial sync + seed/bulk phases + the `ai-enrichment-high`/`-low`/`tag-merge` queue split (Phase 23); the weekly polarity auto-reclassification job + reclassification visibility (Phase 24); the Org Admin Tags page / rename / merge + dashboard polarity split (Phase 25); the Superadmin data reset (Phase 26).

</domain>

<decisions>
## Implementation Decisions

### Polarity at creation (Phase 22 ↔ 24 boundary)
- **D-01:** Phase 22 **captures and stores GPT's `polarity_type`** for each newly proposed canonical tag. The prompt + Pydantic parser change to return `polarity_type` (`always_positive` / `always_negative` / `mixed`) lands here, and `OrgCanonicalTag.polarity_type` is populated at creation. Phase 24 adds ONLY the weekly DB-only reclassification job and reclassification visibility — it does NOT touch the prompt/parser again. Rationale: the `polarity_type` column and CTAG-04 already require it in P22; keeping the prompt change in one place avoids touching it twice.

### Vocabulary injection
- **D-02:** Inject the org's canonical vocabulary into the prompt **capped to the top-N by `review_count`**, where N is a configurable Django setting with a generous default (~200). This is a safety valve against unbounded prompt-token growth as a vocabulary matures; rarely-used tags that fall outside the cap can still be re-proposed and matched via the new-canonical path. (Spec's "inject the list" is honoured; the cap is an operational guardrail.)

### review_count semantics
- **D-03:** `review_count` is **derived on read** — computed via an aggregate over `ReviewTag → canonical_tag` on the (bounded, cached) tag-list query — rather than maintained as a hot counter. This sidesteps drift from the delete-then-`bulk_create` re-enrichment write path entirely (a review re-enriched would otherwise double-count). A denormalized `review_count` column MAY exist as a cache, but if so it is refreshed by the weekly job / merge task, never incremented inline. No re-enrichment bookkeeping in the enrichment hot path.

### Canonical label storage & format
- **D-04:** Store the **FK only** — `ReviewTag.canonical_tag` → `OrgCanonicalTag`. The canonical label string lives ONLY on `OrgCanonicalTag`, never denormalized onto `ReviewTag`. This makes a future rename (Phase 25 / TMGT-03) an **O(1)** update of one `OrgCanonicalTag` row instead of fanning out across every mapped `ReviewTag` (the spec's "update all ReviewTag rows" was an artifact of the old JSONB design and is superseded). Reads resolve the label via the indexed FK join.
- **D-05:** Enforce the canonical label format — **Title Case, ≤3 words** — **server-side** via a normalizer/validator on `OrgCanonicalTag` (mirroring the existing `EnrichmentResult.max_five_tags` validator pattern), not by trusting the prompt alone. Raw `ReviewTag.label` stays as-is (lowercase 2–4 words, `.title()`-cased per Phase 17); the canonical label is a separate, normalized value.

### Rate limiting (QUEUE-02) — corrected by research
- **D-06:** Celery's `rate_limit` is **per-worker, not global** (research-verified vs Celery docs; the spec §11.2 "global across all workers" claim is wrong). Phase 22 ships the per-worker `rate_limit` on the enrichment task with a configurable env setting, set to `target ÷ expected_workers` (so the platform aggregate ≈ ~500/min), and **documents the per-worker caveat**. A **true cross-worker global limiter (Redis token bucket) is deferred to Phase 23**, where the queue split + OpenAI rate-limit management already live (spec §11.2). Do NOT claim global semantics in P22 code/comments.

### Claude's Discretion
The following were left to implementation judgement (technical, no product trade-off) and the architect/planner should decide concretely:
- **New-canonical creation race:** use `get_or_create` (or equivalent) with an `IntegrityError` catch against the `(organisation, label)` unique constraint, so concurrent workers proposing the same new label converge safely. No new Redis lock needed beyond the existing per-review enrichment lock.
- **Rate limit (QUEUE-02) — see D-06 (corrected by research):** NOT global. Celery `rate_limit` is per-worker.
- **Prompt version:** bump `ENRICHMENT_PROMPT_VERSION` (currently 3) when the canonical instructions are added; do NOT trigger any bulk re-enrichment (deferred, as in prior phases).
- **Migration:** add `OrgCanonicalTag` + the nullable `canonical_tag` FK in one migration; **no backfill** of existing reviews (criterion 5 — old rows stay valid with null canonical_tag).
- **Where the post-enrichment mapping runs:** inside the existing `_persist_success` `transaction.atomic()` in `apps/reviews/services/enrichment.py`, alongside the current `ReviewTag` delete-then-`bulk_create`, resolving org via `review.organisation_id` (already `select_related("shop__organisation")`).
- Exact placement of the canonical model (new `apps/reviews` model vs a dedicated module) — keep tenant scoping via a direct `organisation` FK regardless.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone spec & reconciliation
- `docs/in-progress/ReviewBee_Canonical_Tag_Requirements_v1.0.md` — the source spec (v1.0, Final). §3 solution principles, §4 data model (NOTE: written against the old JSONB model — superseded by the relational reconciliation below), §6 AI pipeline changes, §6.4 token cost. **Read with the reconciliation — do not take §4's JSONB/`canonical_tag_id` claims literally.**
- `.planning/research/SUMMARY.md` — codebase reconciliation of the spec vs the live schema. The authoritative correction: tags are relational `ReviewTag`, no `canonical_tag_id` exists; canonical mapping attaches as a new model + nullable FK. **Read this first.**
- `.planning/REQUIREMENTS.md` §"v0.8 Requirements" — CTAG-01…08, QUEUE-02 (the locked requirements for this phase).
- `.planning/ROADMAP.md` → "Phase 22" — goal + 5 success criteria.

### Code this phase modifies / extends
- `apps/integrations/openai/parser.py` — `Tag` (gains `canonical` + `polarity_type`) and `EnrichmentResult` Pydantic schemas; existing `max_five_tags` validator is the pattern to mirror for canonical-label normalization.
- `apps/integrations/openai/prompts.py` — `SYSTEM_PROMPT` + `build_enrichment_messages` (inject the capped canonical vocabulary; English-only rule already present); `ENRICHMENT_PROMPT_VERSION`.
- `apps/reviews/services/enrichment.py` — `_persist_success` `transaction.atomic()` block (the `ReviewTag` delete-then-`bulk_create` + `AiUsageLog` write where canonical lookup/insert is folded in); `enrich_review` three-layer idempotency wrapper.
- `apps/reviews/models.py` — `ReviewTag` model (add nullable `canonical_tag` FK); add `OrgCanonicalTag` model here (or adjacent).
- `apps/integrations/openai/models.py` — `AiUsageLog` (one row per call invariant — must remain exactly one).
- `apps/organisations/models.py` — `Organisation` (FK target for `OrgCanonicalTag`).

### Governing conventions
- `CLAUDE.md` §6 (no-N+1 + query-count ceilings), §9 (tenant scoping — `OrgCanonicalTag` carries a direct `organisation` FK), §14 (one AiUsageLog per OpenAI call, three-layer idempotency, time-versioned pricing), §16 (test conventions: mock OpenAI, factory-boy, query-count tests).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EnrichmentResult.max_five_tags` field_validator (`parser.py`) — pattern for the server-side canonical-label normalizer (Title Case, ≤3 words) per D-05.
- `_persist_success` `transaction.atomic()` (`enrichment.py:~91-128`) — the single write block; canonical lookup/insert + FK population fold in here so a failure rolls back the whole enrichment write (CTAG-06).
- `enrich_review` idempotency wrapper (`enrichment.py:~407+`) — Redis lock `lock:enrich:review:{id}` + `select_for_update` + status short-circuit; canonical work inherits this, no new lock needed.
- `ReviewTag` unique `(review, label, polarity)` constraint + delete-then-`bulk_create` (`models.py:~144`, Phase 17) — existing race guard; the new `canonical_tag` FK must not break it.
- `select_related("shop__organisation")` already loaded in `enrich_review` — org id available for `OrgCanonicalTag` lookup without extra queries.

### Established Patterns
- Tags are relational `ReviewTag` rows, labels `.title()`-cased; canonical label is a SEPARATE normalized value on `OrgCanonicalTag`.
- Prompt context is brand + shop name + review text + star rating only — NO address, NO reviewer name (Phase 12 locked). Canonical vocabulary injection is additive to the existing user payload / system prompt.
- English-only output for tags/sentiment/action-items is already enforced in `SYSTEM_PROMPT` (CTAG-05 largely satisfied; extend to canonical labels).
- AiUsageLog written once inside the same atomic block — canonicalisation must add ZERO extra OpenAI calls (CTAG-07).

### Integration Points
- New `OrgCanonicalTag` model → migration (with the nullable `ReviewTag.canonical_tag` FK), no backfill.
- Prompt/parser extension feeds the post-enrichment mapping step in `_persist_success`.
- Celery enrichment task gains a global `rate_limit` (QUEUE-02) — task decorator + env setting.

</code_context>

<specifics>
## Specific Ideas

- Canonical labels: **Title Case, ≤3 words** (e.g. "Staff & Service", "Food Quality"). Raw tags remain lowercase 2–4 words.
- `polarity_type` enum values: `always_positive` / `always_negative` / `mixed` — GPT picks one when proposing a NEW canonical tag (D-01).
- Vocabulary cap default ~200 tags by `review_count` (D-02) — a configurable setting, not a hardcoded constant.

</specifics>

<deferred>
## Deferred Ideas

- **Weekly polarity auto-reclassification** (`always_*` → `mixed` at 15%/30d) + reclassification logging/visibility — Phase 24 (POL-01…03). Phase 22 only captures the initial `polarity_type`.
- **Four-step initial sync, seed/bulk phases, queue split** (`ai-enrichment-high`/`-low`, `tag-merge`) — Phase 23 (SEED, DSYNC, QUEUE-01).
- **Org Admin Tags page, inline rename, merge, dashboard polarity split** — Phase 25 (TMGT, TDASH). D-04 (FK-only) deliberately makes the rename there O(1).
- **Superadmin data reset + re-sync** — Phase 26 (RESET).
- **Bulk re-enrichment to a new prompt version** — out of scope across the milestone (prompt version bumps without backfill, as in prior phases).

</deferred>

---

*Phase: 22-canonical-tag-foundation-mapping-pipeline*
*Context gathered: 2026-06-10*
