# Phase 24: Polarity Auto-Reclassification - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

A **weekly, DB-only Celery Beat job** that keeps each canonical tag's
`polarity_type` honest: it flips an `always_positive` / `always_negative`
`OrgCanonicalTag` to `mixed` when the opposite polarity exceeds a threshold of
its reviews over a trailing window — **no GPT call, pure DB aggregation** — and
records each reclassification to the audit log.

Maps requirements **POL-01, POL-02, POL-03**. POL-01 (GPT assigns
`polarity_type` at tag creation) is **already shipped in Phase 22** (D-01); this
phase only re-confirms it and owns the reclassification lifecycle + logging.

**NOT in this phase:** the prompt/parser (Phase 22 owns it — D-01); the Org
Admin **Tags page** that renders `polarity_type` (Phase 25 — TMGT/TDASH); the
dashboard polarity split (Phase 25); manual rename/merge (Phase 25); data reset
(Phase 26). No new GPT calls, no new WebSocket/Channels surface.
</domain>

<decisions>
## Implementation Decisions

> The user delegated the "direction" and "threshold" gray areas to Claude's
> judgment and explicitly chose the visibility and log-sink options. Decisions
> below are LOCKED for planning.

### Reclassification direction (POL-02)
- **D-01:** **One-way only** — `always_positive` / `always_negative` → `mixed`.
  Once a tag is `mixed` it **stays `mixed`** (sticky); the weekly job **skips
  tags that are already `mixed`**. This matches POL-02's wording verbatim, avoids
  boundary flapping, and keeps the job idempotent. Auto re-promotion
  (`mixed` → `always_*`) is **out of scope** — any un-mixing is a manual action
  in the Phase 25 Tags page (or a future phase).

### Threshold computation (POL-02)
- **D-02:** For a candidate `always_*` tag, over the trailing window:
  - **Denominator** = count of `ReviewTag` rows mapped to that canonical tag
    (`canonical_tag` FK) whose `Review.review_create_time` falls in the window,
    **all polarities including neutral** (neutral dilutes the ratio — the literal
    reading of "opposite exceeds 15% **of its reviews**"). Soft-deleted reviews
    (`Review.deleted_at` set) are **excluded**.
  - **Numerator** = count of the **opposite** `ReviewTag.polarity` only —
    `always_positive` ← `negative`; `always_negative` ← `positive`. Neutral is
    **never** in the numerator.
  - **Flip to `mixed`** when `numerator / denominator > threshold` **AND**
    `denominator >= min_reviews` (a minimum-sample guard so a tag with 4 reviews
    and 1 opposite doesn't flip prematurely).
- **D-03:** The window is measured by **`Review.review_create_time`** (when the
  review happened on Google), not by enrichment/`ReviewTag` creation time.
- **D-04:** Threshold, window, and minimum-sample are **configurable Django
  settings** with sensible defaults (precedent: Phase 22 D-02, Phase 23
  `SEED_PHASE_SIZE`): `POLARITY_RECLASSIFY_THRESHOLD` (default **0.15**),
  `POLARITY_RECLASSIFY_WINDOW_DAYS` (default **30**),
  `POLARITY_RECLASSIFY_MIN_REVIEWS` (default **10**).

### The weekly job (POL-02)
- **D-05:** A **weekly Celery Beat** job (seeded via data migration, per CLAUDE.md
  §12.5) scans only `always_positive` / `always_negative` `OrgCanonicalTag` rows,
  **org-scoped** (aggregation filtered by `organisation_id` — tenant isolation
  §9/§22). **Pure DB aggregation, zero GPT calls** (POL-02). Idempotent: a second
  run in the same week re-evaluates and changes nothing for already-`mixed` tags.
  **`review_count` is NOT touched here** — that remains the finalising/merge job's
  concern (Phase 22 D-03 / Phase 23). No-N+1: the polarity distribution is a
  single grouped aggregate over `ReviewTag` (§6), not a per-tag loop of queries.

### Logging (POL-03)
- **D-06:** Each reclassification writes one row to the **existing `AuditLog`**
  model (`apps/common/models.py`, from Phase 21): `organisation` = the tag's org,
  `actor` = **null** (system/automated event), `entity_type = "canonical_tag"`,
  `entity_id` = the tag id, `action = "polarity_reclassified"`,
  `before_data = {"polarity_type": "<old>"}`,
  `after_data = {"polarity_type": "mixed", "opposite_ratio": <float>,
  "window_days": <int>, "reviews_in_window": <int>}`. This satisfies POL-03's
  "events are logged" and surfaces them in the Phase 21 Activity Log viewer for
  free — no new logging model.

### Visibility (POL-03)
- **D-07:** POL-03's "current `polarity_type` **visible on the tag list page**"
  is **deferred to Phase 25's Org Admin Tags page** (no tag-list UI built in
  Phase 24). Phase 24 guarantees `polarity_type` is **correct + auditable**; the
  Phase-25 Tags page renders it. The reclassification *events* are already
  visible via the Activity Log viewer (D-06), so POL-03's "logged" half is fully
  delivered here; only the per-tag current-value rendering moves to Phase 25.

### Claude's Discretion
- Exact Beat cadence (e.g. Sunday 03:00 UTC) and the queue for the weekly job
  (low-frequency/low-concurrency — `default` or a dedicated low queue; not
  `ai-enrichment-*`). Pick per CLAUDE.md §10/§12.
- Whether the job runs as one global task aggregating all orgs vs a per-org
  fan-out (mirroring `enqueue_incremental_syncs_task`) — a planning/research call;
  must stay org-scoped and no-N+1 either way.
- Whether a denormalized `polarity_reclassified_at` timestamp is added to
  `OrgCanonicalTag` (helps Phase 25 display) or whether the AuditLog row is the
  sole record — planner decides; AuditLog is authoritative regardless.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 24: Polarity Auto-Reclassification" — goal + 3 success criteria.
- `.planning/REQUIREMENTS.md` §"v0.8 Requirements" — POL-01..03 + the "Note on CTAG-04 vs POL-01" (mapping vs polarity assignment are non-overlapping).
- `.planning/phases/22-canonical-tag-foundation-mapping-pipeline/22-CONTEXT.md` — D-01 (polarity assigned at creation; "Phase 24 adds ONLY the weekly DB-only reclassification job and reclassification visibility"), D-03 (review_count derive-on-read).

### Codebase touch points
- `apps/reviews/models.py` — `OrgCanonicalTag` (PolarityType: always_positive/always_negative/mixed; `polarity_type`, `review_count`), `ReviewTag` (`polarity` positive/neutral/negative, `canonical_tag` FK), `Review` (`review_create_time` indexed, `deleted_at` soft-delete).
- `apps/common/models.py` — `AuditLog` (organisation, nullable actor, entity_type, entity_id, action, before_data, after_data) — the reclassification log sink.
- `apps/reviews/tasks.py` — `enqueue_incremental_syncs_task` Beat fan-out pattern to mirror for a per-org job.
- `config/settings/base.py` — `CELERY_BEAT_SCHEDULER` (django_celery_beat DatabaseScheduler); add the three `POLARITY_RECLASSIFY_*` settings.

### Conventions (CLAUDE.md)
- §6 no-N+1 (single grouped aggregate, query-count test), §9/§22 tenant scoping (org-filtered aggregation), §10 + §12.5 background jobs / Beat schedules seeded by data migration, §16 testing (pytest-django, factories, mock — no GPT in tests).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AuditLog` (Phase 21) + its Activity Log viewer — reused as the reclassification event store and visibility surface; no new model needed.
- `enqueue_incremental_syncs_task` — the Beat fan-out / per-shop dispatch pattern, adaptable to a per-org polarity job.
- `OrgCanonicalTag.PolarityType` + `ReviewTag.Polarity` enums — already define the value space; the job only transitions `always_*` → `mixed`.
- `Review.review_create_time` index + `(organisation, review_create_time)` composite index — supports the windowed aggregation cheaply.

### Established Patterns
- Beat schedules seeded via data migration (CLAUDE.md §12.5), DB-backed django_celery_beat.
- Configurable operational knobs as Django settings with defaults (Phase 22 D-02, Phase 23).
- review_count is job-refreshed, never inline (Phase 22 D-03) — this job does NOT touch it.

### Integration Points
- The weekly task aggregates `ReviewTag.polarity` grouped per `canonical_tag`, joined to `Review.review_create_time` window, org-scoped.
- Each flip writes an `AuditLog` row (system actor) and updates `OrgCanonicalTag.polarity_type` to `mixed`.
</code_context>

<specifics>
## Specific Ideas

- Defaults: threshold **0.15**, window **30 days**, min reviews **10**.
- Reclassification is **one-way** and **mixed is sticky**.
- AuditLog `action = "polarity_reclassified"`, `entity_type = "canonical_tag"`, system actor (null).
</specifics>

<deferred>
## Deferred Ideas

- **Auto re-promotion** (`mixed` → `always_*` when a tag tightens up) — out of scope; manual via Phase 25 Tags page or a future phase.
- **Rendering current `polarity_type` on the tag list page** — Phase 25 (TMGT/TDASH).
- **Dashboard polarity split for `mixed` tags** — Phase 25.
- **Per-tag reclassification-history view** — could read AuditLog rows; not required by POL-03, revisit if Phase 25 wants it.

None of the discussion drifted outside the phase scope.
</deferred>

---

*Phase: 24-polarity-auto-reclassification*
*Context gathered: 2026-06-11*
