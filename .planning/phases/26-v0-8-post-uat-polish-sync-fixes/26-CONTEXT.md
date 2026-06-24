# Phase 26: v0.8 Post-UAT Polish & Sync Fixes - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning
**Source:** Captured from the Phase 22–25 UAT conversation (decisions made interactively with the Org Admin / product owner); cadence decision delegated to Claude's recommendation.

<domain>
## Phase Boundary

Close the small UX gaps and the one sync-progress defect surfaced while UAT-testing
Phases 22–25, so the canonical-tag surface and initial-sync experience feel finished —
**without new capabilities**. Four requirements:

- **TMGT-07** — Tags page label **search filter**
- **TMGT-08** — Tags page **header count** + **pagination footer** (match `/admin/org/team/`)
- **SEED-05** — sync progress **"Fetching from Google"** label + **per-stage completion timing**
- **SEED-06** — **fix**: incremental/manual sync must not clobber the initial-sync progress modal (§13.2)

**NOT in this phase:** any new tag/sync capability; the Superadmin data reset (Phase 27, deferred);
the finalise-countdown→Celery-chord rework (separately deferred tech debt — see sync.py Phase 4 comment).
</domain>

<decisions>
## Implementation Decisions

> Settled with the product owner during UAT. LOCKED for planning.

### TMGT-07 — Tags page search filter
- **D-01:** Add a **label search filter** to the Tags page, matching the `/admin/org/team/`
  search UX ("Search name or email…" input). **Server-side, debounced**, case-insensitive
  `label__icontains`, **org-scoped**, on the existing paginated/query-count-bounded endpoint
  (add a `search` query param to the `OrgCanonicalTagViewSet` list / its FilterSet — do NOT
  add an unbounded `__` lookup; §8). The React `tag-management` widget gains a search box
  cloned from the **`team-management`** widget. Keep the list endpoint's fixed query-count
  ceiling (add/extend the query-count test, §6.9).

### TMGT-08 — Tags page header count + pagination footer
- **D-02:** The Tags page shows a **header count** — "Tags (N)" where N is the org's total
  canonical-tag count — mirroring "Team (1)". And a **"Showing X–Y of N · Rows: N"**
  pagination footer with the rows-per-page selector + page controls, mirroring the team
  page. Clone both from the **`team-management`** widget; total count comes from the
  existing paginated response (`count`). No new endpoint.

### SEED-05 — Sync progress UX
- **D-03:** Rename the progress modal's **step-1 label** "Fetched from Google" →
  **"Fetching from Google"** (gerund-consistent with "Building Tag Vocabulary",
  "Analysing…", "Finalising"). Frontend label change only.
- **D-04:** **Per-stage completion timing** — when each of the 4 stages finishes, show its
  wall-clock duration (e.g. **"Building Tag Vocabulary · 10m 16s"** next to the completed
  stage). Backend: record a per-step **start timestamp** at each transition in the sync
  snapshot and compute each step's duration when the next step starts (finalising already
  computes its own `duration_seconds`; fetch duration is already in the audit). Surface the
  per-step durations in the snapshot so the React modal renders them. Exact visual format is
  Claude's discretion (finalise in the UI), but it must read each stage's real elapsed time.

### SEED-06 — Incremental clobber fix (the bug)
- **D-05:** **The progress snapshot + ProgressModal are initial-sync ONLY (§13.2).** Gate
  ALL progress-snapshot writes/clears AND `emit_progress_event` calls inside
  `fetch_and_persist_reviews` on **`trigger == "initial"`** — incremental/manual syncs run
  **silently** (matching `_emit_enrichment_progress`, which already returns silently when no
  snapshot). This stops an overlapping incremental from clearing/resetting an in-progress
  initial-sync modal back to "0 of N". Re-enable the `enqueue_incremental_syncs` beat after
  the fix lands (it was disabled during UAT as a mitigation).
- **D-06 (cadence — delegated to Claude):** Set the incremental sync cadence to
  **every 6 hours** (`0 */6 * * *` UTC), aligning the beat schedule with the existing
  `INCREMENTAL_SYNC_INTERVAL_HOURS=6` setting — this also **resolves the hourly-vs-6h doc/impl
  drift** (the beat was hourly `0 * * * *` while the setting implied 6h). Rationale: SEED-06
  removes the clobber motivation, so cadence is now purely freshness-vs-cost; 6h gives ~6h
  review freshness (fine for review response) at a quarter of the API/OpenAI load. No special
  timezone needed (it runs 4×/day regardless). Update the beat schedule via the
  django-celery-beat data migration / seed.

### Claude's Discretion
- Exact debounce interval for the search box (~250–300ms), the search-empty state copy, the
  exact per-stage-timing visual treatment, and whether the rows-per-page options match the
  team page's set verbatim.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 26" — goal + 4 success criteria + the cadence open-decision note.
- `.planning/REQUIREMENTS.md` — TMGT-07, TMGT-08, SEED-05, SEED-06.

### Analogs to clone (the team page = the reference UX)
- `frontend/src/widgets/team-management/` — **search input, header count ("Team (N)"), and
  "Showing X–Y of N · Rows: N" pagination footer** → clone into `tag-management`.
- `frontend/src/widgets/tag-management/` — the Tags widget being extended (TagTable, useTagList, TagManagementWidget).
- `templates/org-admin/team*.html` vs `templates/org-admin/tags.html` — header/count markup parity.

### Codebase touch points
- `apps/reviews/views.py` `OrgCanonicalTagViewSet` + `apps/reviews/selectors/canonical_tags.py`
  `list_canonical_tags_for_org` — add the `search` filter (org-scoped, query-count-bounded).
- `apps/reviews/services/sync.py` `fetch_and_persist_reviews` — the SEED-06 trigger gate
  (snapshot writes/clears/emits at lines ~309, 332, 469, 511, 524, 564 + their emits).
- `apps/reviews/services/progress.py` (snapshot schema) + `apps/reviews/services/finalise.py`
  (finalising snapshot) — per-step timing fields.
- The sync ProgressModal React component (consumes the snapshot) — labels + per-stage timing display.
- The `enqueue_incremental_syncs` Beat schedule (django-celery-beat data migration) — set to 6-hourly + re-enable.

### Conventions (CLAUDE.md)
- §6/§6.9 no-N+1 + query-count test (search filter must keep the fixed ceiling); §8 DRF
  (explicit FilterSet, no arbitrary `__` lookups); §9/§22 org-scoping; §13.2 progress modal is
  initial-sync only; §13.5 sync snapshot/step schema; §18 migration naming; §26 React widget pattern.
</canonical_refs>

<specifics>
## Specific Ideas
- Search filter: like team's "Search name or email…", server-side debounced `label__icontains`, org-scoped.
- Header "Tags (N)" + "Showing X–Y of N · Rows: N" footer — clone team-management.
- "Fetching from Google" label; per-stage "· 10m 16s" completion time when a stage goes green.
- SEED-06: gate `fetch_and_persist_reviews` progress writes/emits on `trigger == "initial"`; re-enable the beat.
- Cadence → 6-hourly (`0 */6 * * *` UTC); fixes the hourly-vs-6h doc drift.
</specifics>

<deferred>
## Deferred Ideas
- **Finalise countdown → Celery chord** (so finalising fires only after bulk completes, fixing premature "complete" + partial counts on large syncs) — acknowledged tech debt in `sync.py` Phase 4 comment; NOT in this phase.
- **Superadmin data reset** — Phase 27 (deferred, pre-launch).
- Real-time progress for incremental syncs — out of scope (§13.2 keeps the modal initial-only).
</deferred>

---

*Phase: 26-v0-8-post-uat-polish-sync-fixes*
*Context gathered: 2026-06-24 from Phase 22–25 UAT conversation*
