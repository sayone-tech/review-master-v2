# Phase 25: Org Admin Tag Management & Dashboard Polarity - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Org Admins curate their org's canonical vocabulary directly: a **Tags page**
(`/admin/org/tags/`) to view (sortable, paginated, query-bounded), **inline
rename**, and **merge** canonical tags (modal + searchable target picker +
batched Celery task with HTTP-polled progress and a rollback path); plus a
**polarity-aware dashboard** tag chart. Consumes the Phase 22 canonical model,
the Phase 23 `tag-merge` queue + merge primitives, and the Phase 24
`polarity_type` (for the badge + dashboard split).

Maps **TMGT-01..06, TDASH-01..02**.

**NOT in this phase:** changing the GPT prompt/parser (Phase 22); the
reclassification job (Phase 24); the Superadmin data reset (Phase 26); any new
WebSocket consumer (merge progress is HTTP polling per §13.2).
</domain>

<decisions>
## Implementation Decisions

> The user delegated all four discussed gray areas to Claude's judgment.
> Decisions below are LOCKED for planning.

### Tags page access + list (TMGT-01, TMGT-02)
- **D-01:** Tags page at **`/admin/org/tags/`**, sidebar nav under Settings
  (alongside the existing org nav items). Access: **`ORG_ADMIN` only** —
  "Manager" is merely the **UI display label for `ORG_ADMIN`**
  (`apps/accounts/serializers.py`); **`STAFF_ADMIN` cannot** reach it. Enforce at
  BOTH the view/permission layer (403 for Staff) AND the sidebar (nav item hidden
  for Staff) — §9/§22.
- **D-02:** Tag list = a **paginated, query-count-bounded** endpoint (CLAUDE.md
  §6.9 — fixed query ceiling regardless of page size; add a query-count test),
  **sortable by column**. Columns: **Label, Polarity Type badge** (always_positive
  / always_negative / mixed, colored), **Review Count, First Seen** (`created_at`),
  **Actions menu** (rename, merge). Built as a React data-table widget reusing the
  `audit-log` / `data-table` widget pattern (Django bootstrap-data handoff).

### Rename (TMGT-03) — O(1), per D-04
- **D-03:** Rename updates **ONLY `OrgCanonicalTag.label`** — an **O(1)** write
  (Phase 22 **D-04**, carried forward). Mapped reviews reflect the new label via
  the indexed FK join; raw `ReviewTag.label` rows are **NOT touched**. TMGT-03's
  "update all mapped ReviewTag rows synchronously" is the superseded JSONB-era
  wording — the FK-only design makes it a single-row update that all reads resolve
  through the join.
- **D-04:** Rename validation: **1–100 chars**; **reject case-insensitive
  duplicates** within the org (consistent with the Phase 23 dedup rule) with a
  clear inline error — **rename NEVER silently merges** (merge is a separate
  explicit flow). Apply **Title-Case normalization** for display consistency, but
  do **NOT** enforce the GPT-era **≤3-word cap** (Phase 22 D-05) on a human admin
  rename — admins are trusted with longer labels. Save is synchronous/inline.

### Merge (TMGT-04, TMGT-05)
- **D-05:** Merge UX: a **modal** with a **searchable target picker** (search the
  org's other canonical tags) and an explicit **"re-maps N reviews, cannot be
  undone"** warning (N = source's mapped review count). **Irreversible** (no undo).
- **D-06:** Merge result: the **user-chosen TARGET is always kept** (admin intent
  governs — NOT the higher-`review_count` row as in Phase 23 auto-dedup). Source
  `ReviewTag.canonical_tag` FKs re-point to target in a **single bulk UPDATE** (no
  N+1), source tag deleted, merged tag keeps the **target's `polarity_type`**.
  `review_count` is **REFRESHED via aggregate** (reuse Phase 23
  `_refresh_review_counts`, honoring D-03 derive-on-read) — **NOT a naive sum**.
- **D-07:** Merge runs as a batched **`merge_canonical_tags(source_id, target_id)`**
  Celery task on the **`tag-merge` queue**, under a **per-org Redis lock**
  (`lock:tag_merge:org:{org_id}`, §7.6 — reuse the Phase 23 convention), reusing
  the Phase 23 FK-repoint + count-refresh primitives in `apps/reviews/services/
  finalise.py`. Posts a **completion notification** (existing notification
  dispatch). The whole merge is **`transaction.atomic` — all-or-nothing**; on
  failure it rolls back partial updates (no half-merged state).

### Merge progress (TMGT-06) — HTTP polling, durable
- **D-08:** Merge progress is tracked in a **new durable DB model**
  (`TagMergeJob`: organisation, source label (denormalized — source is deleted),
  target FK/label, `status` PENDING/IN_PROGRESS/SUCCESS/FAILED, `processed`/`total`,
  `error_message`, timestamps). Chosen over a Redis key because it **survives
  reload AND a Redis flush**, gives a durable completed/failed record, and yields
  a natural rollback/notification anchor. Polled over **HTTP (~2s while
  in-progress)** via a GET endpoint keyed by job id — **no new WebSocket consumer**
  (§13.2). UI: in-progress bar with **dismiss**, **state survives reload**
  (re-fetch job by id), **completion toast**, **failure path** surfaces the
  rollback. Org-scoped (a job is only visible to its org).

### Dashboard polarity (TDASH-01, TDASH-02)
- **D-09:** **Extend the existing dashboard tag chart**: one bar per canonical
  tag; `always_positive` / `always_negative` render a single count bar (colored by
  polarity); **`mixed` tags render a stacked/diverging bar split into positive vs
  negative** segments, computed from the `ReviewTag.polarity` distribution for
  that canonical tag.
- **D-10:** **TDASH-02:** ALL canonical aggregation queries include **only reviews
  where `canonical_tag` is set** (exclude null/unmapped). Org-scoped and
  query-bounded (no N+1).

### Claude's Discretion
- Exact React widget composition (reuse `audit-log`/`data-table`/`modal`/`reports`
  widgets + the chart lib already in `reports`), poll interval exact value (~2s),
  progress granularity (processed/total vs coarse states), the Tags sidebar icon
  (a lucide `tag`/`tags` glyph), and whether rename/merge are DRF viewset actions
  vs dedicated endpoints.
- Whether the list's `review_count` reads the denormalized column (refreshed by
  Phase 23/24 jobs) or a bounded aggregate — either is fine if query-bounded.
- The exact dashboard chart library/representation details (finalised in UI-SPEC).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 25" — goal + 5 success criteria.
- `.planning/REQUIREMENTS.md` — TMGT-01..06, TDASH-01..02.
- `.planning/phases/22-canonical-tag-foundation-mapping-pipeline/22-CONTEXT.md` — **D-04 (FK-only, rename O(1))**, D-05 (Title-Case ≤3-word format — GPT-era guardrail), D-03 (review_count derive-on-read).
- `.planning/phases/23-four-step-initial-sync-seeding-queue-split/23-CONTEXT.md` — tag-merge queue, per-org lock, case-insensitive dedup rule.
- `.planning/phases/24-polarity-auto-reclassification/24-CONTEXT.md` — `polarity_type` now self-maintaining (badge + dashboard split source).

### Codebase touch points
- `apps/reviews/models.py` — `OrgCanonicalTag` (label, polarity_type, review_count, created_at=First Seen), `ReviewTag` (canonical_tag FK, raw label).
- `apps/reviews/services/finalise.py` — `_merge_group`, `_refresh_review_counts` (reuse for manual merge FK-repoint + count refresh).
- `apps/reviews/tasks.py` + `config/settings/base.py` CELERY — `tag-merge` queue; add `merge_canonical_tags_task`.
- `apps/common/locks.py` — `distributed_lock` (`lock:tag_merge:org:{org_id}`, §7.6).
- `apps/accounts/` — `User.Role` (ORG_ADMIN="Manager" display), `permissions.py` (IsOrgAdmin); Staff exclusion.
- `apps/notifications/services/dispatch.py` + bell polling — merge-completion notification + the HTTP-poll precedent (60s bell).
- `templates/partials/sidebar_org.html` — add the Tags nav item (hidden for Staff).
- `apps/dashboard/views.py` + `frontend/src/widgets/dashboard` + `reports` (chart lib) — the polarity-aware tag chart.
- `frontend/src/widgets/` — `audit-log`/`data-table` (Tags table analog), `modal` (merge modal), `notif-bell` (polling analog).

### Conventions (CLAUDE.md)
- §6 no-N+1 + query-count tests (list endpoint + merge repoint + dashboard agg), §7.6 distributed locks, §8 DRF (pagination, FilterSet, viewsets, two-serializers), §9/§22 tenant scoping + RBAC (Staff 403 + nav hidden), §12 Celery (thin task, idempotency, tag-merge queue), §13.2 NO new WebSocket consumer (HTTP polling), §16 testing (incl. Channels-free), §26 brand/React-widget pattern.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 23 `finalise.py` `_merge_group` (FK re-point to winner) + `_refresh_review_counts` (aggregate) — the manual merge reuses both (target as winner, not higher-count).
- `tag-merge` Celery queue + `lock:tag_merge:org:{org_id}` distributed lock — already exist (Phase 23).
- React widgets `audit-log`/`data-table` (sortable paginated table), `modal` (merge modal), `notif-bell` (60s HTTP-poll pattern → merge-progress poll).
- `apps/notifications/services/dispatch.py` — merge-completion notification.
- `IsOrgAdmin` permission + sidebar role conditionals (Activity Log nav is the Staff-excluded analog).

### Established Patterns
- Query-count-bounded list endpoints with a CaptureQueriesContext test (§6.9) — the Tags list + dashboard agg follow it.
- HTTP polling (no WebSocket) for non-sync live state (notification bell) — merge progress mirrors it.
- review_count is aggregate-refreshed, never naive-summed (D-03) — merge refresh honors it.

### Integration Points
- New `TagMergeJob` model + GET poll endpoint; `merge_canonical_tags_task` on tag-merge queue.
- Tags React widget mounted in a new Django template at `/admin/org/tags/`.
- Dashboard tag chart extended for polarity split (mixed → stacked bar).
</code_context>

<specifics>
## Specific Ideas

- Tags page: `/admin/org/tags/`, ORG_ADMIN-only, columns Label / Polarity badge / Review Count / First Seen / Actions.
- Rename: O(1), 1–100 chars, reject case-insensitive dups, no silent merge.
- Merge: target wins, review_count via aggregate refresh, irreversible, tag-merge queue + per-org lock.
- Merge progress: `TagMergeJob` DB model, ~2s HTTP poll, dismiss + reload-survival + toast + rollback.
- Dashboard: mixed tags = stacked positive/negative bar; aggregation excludes null canonical_tag.
</specifics>

<deferred>
## Deferred Ideas

- **Merge undo / history beyond the TagMergeJob record** — out of scope (merge is irreversible by D-05).
- **Bulk multi-tag merge / split** — out of scope (single source → single target only).
- **Superadmin data reset** — Phase 26.
- **Auto re-promotion of mixed tags** — deferred from Phase 24; not revisited here.

None of the discussion drifted outside the phase scope.
</deferred>

---

*Phase: 25-org-admin-tag-management-dashboard-polarity*
*Context gathered: 2026-06-16*
