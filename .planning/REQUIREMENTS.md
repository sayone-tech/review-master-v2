# Requirements: Multi-Tenant Review Management Platform

**Active milestone:** v0.8 — Canonical Tag System
**Source spec:** `docs/in-progress/ReviewBee_Canonical_Tag_Requirements_v1.0.md` (v1.0, Final), reconciled against the live schema (see `.planning/research/SUMMARY.md`).

---

## v0.8 Requirements — Canonical Tag System

### CTAG — Canonical tag model & mapping pipeline

- [x] **CTAG-01**: Org Admin's organisation accrues a per-org `OrgCanonicalTag` vocabulary (label Title Case ≤3 words, `polarity_type`, `review_count`, timestamps; unique per `(organisation, label)`)
- [x] **CTAG-02**: Each `ReviewTag` carries a nullable `canonical_tag` FK that is populated with its canonical label/id once mapped
- [x] **CTAG-03**: The single enrichment GPT call has the org's existing canonical vocabulary injected into its prompt
- [x] **CTAG-04**: GPT maps each generated tag to an existing canonical label, or proposes a new canonical label with a `polarity_type`, in one call (no extra API calls)
- [x] **CTAG-05**: All tags (raw + canonical) and action items are emitted in English regardless of the review's language
- [x] **CTAG-06**: Post-enrichment, each tag is looked up in `OrgCanonicalTag`; matched → populate FK; new → insert canonical row + `review_count++`; all inside the existing enrichment `transaction.atomic()`
- [x] **CTAG-07**: Every enrichment call still writes exactly one `AiUsageLog` row (canonicalisation adds no separate call)
- [x] **CTAG-08**: Reviews enriched before canonicalisation remain valid with a null canonical mapping (backward compatible)

### POL — Polarity types & auto-reclassification

- [x] **POL-01**: A new canonical tag is assigned one of `always_positive` / `always_negative` / `mixed` by GPT at creation time
- [x] **POL-02**: A weekly Celery Beat job reclassifies an `always_*` canonical tag to `mixed` when the opposite polarity exceeds 15% of its reviews over the last 30 days (pure DB aggregation, no GPT call)
- [x] **POL-03**: Reclassification events are logged and the current `polarity_type` is visible on the tag list page

### SEED — Four-step initial sync & vocabulary seeding

- [ ] **SEED-01**: Initial sync shows four steps per store — Fetching Reviews → Building Tag Vocabulary → AI Enrichment → Finalising — with progress text per step
- [ ] **SEED-02**: The seed phase processes the first 50 reviews sequentially (all of them if fewer than 50), updating the canonical vocabulary before each next review
- [ ] **SEED-03**: The bulk phase enriches the remaining reviews in parallel against the current vocabulary, still able to add new canonical tags
- [ ] **SEED-04**: The finalising pass resolves residual duplicate tags by string match and backfills `canonical_tag` on any stragglers

### DSYNC — Daily incremental sync

- [ ] **DSYNC-01**: Daily incremental sync enriches new reviews through the same canonical pipeline (vocabulary injected, new canonical tags auto-added without approval) on the low-priority enrichment queue

### QUEUE — Infrastructure (queues & rate limiting)

- [ ] **QUEUE-01**: Enrichment work is split across `ai-enrichment-high` (initial sync) and `ai-enrichment-low` (daily sync); a dedicated `tag-merge` queue isolates merge jobs
- [x] **QUEUE-02**: The enrichment task enforces a global, configurable Celery rate limit (default ~500/min) that holds across all workers to stay within OpenAI TPM limits

### TMGT — Org Admin tag management

- [x] **TMGT-01**: Org Admin and Manager can reach a Tags page at `/admin/org/tags/` (sidebar under Settings); Staff cannot
- [x] **TMGT-02**: The tag list shows Label, Polarity Type badge, Review Count, First Seen, and an Actions menu, sortable by column, on a paginated query-count-bounded endpoint
- [x] **TMGT-03**: A canonical tag can be renamed inline (1–100 chars, unique within the org); save updates `OrgCanonicalTag.label` and all mapped `ReviewTag` rows synchronously
- [x] **TMGT-04**: A canonical tag can be merged into another via a modal with a searchable target picker and an explicit "re-maps N reviews, cannot be undone" warning
- [x] **TMGT-05**: Merge runs as a batched `merge_canonical_tags` Celery task (tag-merge queue, per-org lock) that re-points all reviews, deletes the source tag, combines `review_count`, and posts a completion notification
- [x] **TMGT-06**: Merge progress is delivered via HTTP polling — in-progress bar with dismiss, state that survives page reload, a completion toast, and a failure path that rolls back partial updates

### TDASH — Dashboard polarity presentation

- [x] **TDASH-01**: Dashboard tag charts show a simple count for `always_positive`/`always_negative` canonical tags and a positive/negative split for `mixed` tags
- [x] **TDASH-02**: Canonical aggregation queries include only reviews where `canonical_tag` is set

### RESET — Superadmin data reset & re-sync (pre-production) — **DEFERRED**

> **Deferred 2026-06-16 (pre-launch).** No production deployment exists yet, so the §11
> soft-delete constraint that motivates an in-app Superadmin reset does not apply during
> testing — dev data is reset directly via `manage.py flush` / DB drop-recreate + `make
> migrate` + `make seed`, and Redis sync-state via `flushdb`. Building the Superadmin reset
> feature now would be over-engineering. Revisit **before go-live**, when hard-deleting one
> live org's data becomes a real operational need (e.g. the pre-production 56-store brand
> re-sync). v0.8 ships as Phases 22–25; Phase 27 (RESET) is parked, not cancelled.

- [~] **RESET-01** *(deferred)*: A Superadmin can trigger a full data reset for one organisation — hard-deleting its Review, AiUsageLog, ActionItem, and OrgCanonicalTag rows (documented one-time pre-production exception to the §11 soft-delete rule)
- [~] **RESET-02** *(deferred)*: The reset clears each store's sync state (Redis progress snapshot + `Shop.connection_status`) so stores read as "Not synced"
- [~] **RESET-03** *(deferred)*: After reset, the Org Admin re-syncs each store through the normal flow, running the full four-step initial sync

### POLISH — Post-UAT UX polish & sync fixes (Phase 26)

> Surfaced during v0.8 (Phases 22–25) UAT. Small, well-scoped enhancements plus one
> deferred sync-progress fix. To be planned/built via the GSD flow after UAT wraps.

- [x] **TMGT-07**: The Tags page provides a label **search filter** (server-side, debounced), matching the `/admin/org/team/` search UX
- [x] **TMGT-08**: The Tags page shows a **header count** ("Tags (N)") and a **"Showing X–Y of N · Rows: N"** pagination footer, matching `/admin/org/team/`
- [x] **SEED-05**: The sync progress modal uses a **"Fetching from Google"** label (gerund-consistent with the other steps) and shows each stage's **completion time** when it finishes
- [x] **SEED-06**: An incremental or manual sync must **not** clear or overwrite the initial-sync progress snapshot (§13.2) — fix `fetch_and_persist_reviews` so an overlapping incremental can't reset an in-progress initial-sync modal (UAT bug #4; mitigated for now by disabling the hourly incremental beat). *Open decision at planning:* the incremental **cadence** (hourly vs 6-hourly vs off-peak/daily) + timezone — independent of the fix; see Phase 26 ROADMAP "Open decisions".
- [x] **NAV-01** *(bundled with Phase 26)*: Org sidebar nav reordered by frequency-of-use — Dashboard · Reviews · Action Items · Reports · Shops · Regions · Tags · Templates · Team · Activity Log — moving Tags out of the stranded last slot and Team + Activity Log to the bottom (no grouping headers; the reorder collapses the three role-conditional blocks into one).

---

## Future Requirements (deferred)

- **Cross-Org Insights** (doc Phase 5): top canonical tags across all orgs in a category, Superadmin analytics, cross-org benchmarking. Low priority.

## Out of Scope (this milestone)

| Excluded | Reason |
|---|---|
| Vector database / pgvector | GPT-native language understanding + a standard Postgres table suffice |
| Superadmin approval workflow for new canonical tags | Auto-add is sufficient |
| Platform-level shared canonical vocabulary across orgs | Each org self-organises its own vocabulary |
| Cross-org tag benchmarking | Deferred to Future (doc Phase 5) |
| Manual `polarity_type` override by Org Admin | Auto-assignment + weekly auto-reclassification handle it |
| Hard delete of canonical tags | Org Admin must use merge instead |
| Canonical tags for action items | Action items remain free text; canonical applies to review tags only |
| Migration of orgs other than the pre-production 56-store brand | Not in scope for v0.8 |
| Tag-merge progress over WebSocket | HTTP polling chosen to keep the Channels surface narrow (§13.2) |

## Traceability

Every v0.8 requirement maps to exactly one phase. Phases 22–27 (continuing from v0.7's Phase 21).

**Coverage: 25/25 core requirements mapped ✓ — no orphans, no duplicates.** (Plus 4 post-UAT polish requirements added as Phase 26 — see POLISH below.)

**Delivery scope:** v0.8 ships as Phases 22–25 (22 of 25 core requirements). **Phase 26 (TMGT-07/08, SEED-05/06)** captures UX polish + one sync-progress fix surfaced during UAT — the next work after the testing round. **Phase 27 / RESET-01..03 are deferred to pre-launch** (no production deployment yet — see the RESET section above). The milestone closes on the canonical-tag system + dashboard polarity; the Superadmin reset is parked, not cancelled.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTAG-01 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| CTAG-02 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| CTAG-03 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| CTAG-04 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| CTAG-05 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| CTAG-06 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| CTAG-07 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| CTAG-08 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| QUEUE-02 | Phase 22 — Canonical Tag Foundation & Mapping Pipeline | Complete |
| SEED-01 | Phase 23 — Four-Step Initial Sync, Seeding & Queue Split | Pending |
| SEED-02 | Phase 23 — Four-Step Initial Sync, Seeding & Queue Split | Pending |
| SEED-03 | Phase 23 — Four-Step Initial Sync, Seeding & Queue Split | Pending |
| SEED-04 | Phase 23 — Four-Step Initial Sync, Seeding & Queue Split | Pending |
| DSYNC-01 | Phase 23 — Four-Step Initial Sync, Seeding & Queue Split | Pending |
| QUEUE-01 | Phase 23 — Four-Step Initial Sync, Seeding & Queue Split | Pending |
| POL-01 | Phase 24 — Polarity Auto-Reclassification | Complete |
| POL-02 | Phase 24 — Polarity Auto-Reclassification | Complete |
| POL-03 | Phase 24 — Polarity Auto-Reclassification | Complete |
| TMGT-01 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TMGT-02 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TMGT-03 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TMGT-04 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TMGT-05 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TMGT-06 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TDASH-01 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TDASH-02 | Phase 25 — Org Admin Tag Management & Dashboard Polarity | Complete |
| TMGT-07 | Phase 26 — v0.8 Post-UAT Polish & Sync Fixes | Planned |
| TMGT-08 | Phase 26 — v0.8 Post-UAT Polish & Sync Fixes | Planned |
| SEED-05 | Phase 26 — v0.8 Post-UAT Polish & Sync Fixes | Planned |
| SEED-06 | Phase 26 — v0.8 Post-UAT Polish & Sync Fixes | Planned |
| RESET-01 | Phase 27 — Superadmin Data Reset & Re-Sync | Deferred (pre-launch) |
| RESET-02 | Phase 27 — Superadmin Data Reset & Re-Sync | Deferred (pre-launch) |
| RESET-03 | Phase 27 — Superadmin Data Reset & Re-Sync | Deferred (pre-launch) |

**Note on CTAG-04 vs POL-01:** CTAG-04 (Phase 22) owns the in-call mapping behaviour — GPT mapping a tag to an existing canonical label *or proposing a new one*. POL-01 (Phase 24) owns the polarity-lifecycle requirement that the proposed new tag carries a GPT-assigned `polarity_type`. The phases share the same GPT call but the requirements are non-overlapping (mapping vs polarity assignment).

---

## Archived per-milestone requirement sets

All seven web milestones (Web Beta 1) are sealed. Frozen snapshots under `milestones/`:

| Milestone | Theme | Requirements file |
|---|---|---|
| v1.0 | Superadmin Module | [`v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md) |
| v0.2-org-admin | Organisation Admin Module | [`v0.2-org-admin-REQUIREMENTS.md`](milestones/v0.2-org-admin-REQUIREMENTS.md) |
| v0.3 | Reviews and Action Items | [`v0.3-REQUIREMENTS.md`](milestones/v0.3-REQUIREMENTS.md) |
| v0.4 | Dashboard | _(not formally archived; in git history)_ |
| v0.5 | Configurable Sync Depth | [`v0.5-REQUIREMENTS.md`](milestones/v0.5-REQUIREMENTS.md) |
| v0.6 | Tag Rework & Action Item Quality | [`v0.6-REQUIREMENTS.md`](milestones/v0.6-REQUIREMENTS.md) |
| v0.7 | AI Safety & Governance | [`v0.7-REQUIREMENTS.md`](milestones/v0.7-REQUIREMENTS.md) |
