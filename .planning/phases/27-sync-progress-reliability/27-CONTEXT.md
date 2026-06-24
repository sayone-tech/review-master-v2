# Phase 27: Sync Progress Reliability - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning
**Source:** Captured from the Phase 22–25 UAT conversation (two sync-progress reliability defects found while testing; the org-admin / product owner asked to fix both).

<domain>
## Phase Boundary

Harden the initial-sync ProgressModal so it stays accurate without manual reopening, and make
the Finalising step fire promptly + visibly. Two requirements:

- **SYNC-REL-01** — ProgressModal **snapshot-poll fallback** + an org-scoped **GET endpoint**
  for the sync snapshot, so a missed/dropped WebSocket event no longer freezes the modal.
- **SYNC-REL-02** — `finalize_canonical_tags_task` **completion-gating** so Finalising fires
  when bulk enrichment actually completes, not on a fixed countdown.

**NOT in this phase:** new sync capabilities; changing the four-step flow itself; the
Superadmin reset (Phase 28, deferred); any new Channels consumer (§13.2 — the existing
`SyncProgressConsumer` stays; this adds an HTTP fallback, not a new socket).
</domain>

<decisions>
## Implementation Decisions

> Settled with the product owner during UAT. LOCKED for planning.

### SYNC-REL-01 — Poll fallback + snapshot GET endpoint
- **D-01:** Add a **GET endpoint** that returns the current `sync:progress:{shop_id}` snapshot
  (the same dict `read_progress_snapshot` returns; 404 or empty/`{}` when absent). **Org-scoped
  + shop-access-scoped** — reachable only by users who can see that shop's sync (mirror the
  consumer's auth in §13.4 / the reviews page access: authenticated + the shop belongs to the
  caller's org; Staff limited to their `StaffAccessScope`). Thin DRF view → `read_progress_snapshot`
  (a read; §5). Versioned URL under `/api/v1/`. Throttled (§8). It returns Redis state, not a DB
  query — no N+1 concern, but keep it cheap (single Redis GET).
- **D-02:** The **ProgressModal** polls that endpoint **every ~3–5s** as a fallback *alongside*
  the existing WebSocket (do NOT remove the WebSocket — it stays the primary, low-latency path).
  Merge rule: apply whichever update is newer by `last_update_at` so the poll only ever moves
  state forward (never overwrites a fresher WS event with a stale poll). Stop polling on a
  terminal state (`success`/`failed`) and on modal close. This makes the modal self-heal — the
  "reopen from the notification to refresh" workaround is no longer needed.

### SYNC-REL-02 — Finalise completion-gating
- **D-03:** Replace the **fixed countdown** dispatch of `finalize_canonical_tags_task` with
  **completion-gating**. Recommended mechanism (lower-risk than a full Celery chord): the task
  **self-reschedules** — at start, if any of the shop's reviews are still PENDING or IN_PROGRESS
  (enrichment not finished), it re-dispatches itself with a **short countdown** (e.g. 15–30s) and
  returns; once **all reviews are terminal** (SUCCESS/FAILED), it proceeds with the existing
  dedup → straggler-backfill → review_count-refresh → sync.complete. Bound the retries with a
  **max attempt count** (e.g. cap at a sensible ceiling so a permanently-stuck review can't loop
  forever — after the cap, proceed anyway so the sync always completes). Keep the per-org
  `lock:tag_merge:org:{org_id}` lock + idempotency (§7.6, §12.4). Effect: Finalising fires within
  seconds of bulk completing (no multi-minute wait) and the Finalising step is actually visible.
- **D-04:** This **supersedes** the deferred countdown→chord note in
  `apps/reviews/services/sync.py::run_initial_backfill` Phase 4 — the self-reschedule guard is the
  chosen approach; do not also build a chord. Update that comment.

### Claude's Discretion
- Exact poll interval (3–5s), the precise max-attempt ceiling + short-countdown value for the
  self-reschedule, the endpoint path shape, and whether the frontend poll uses `fetch`/the existing
  api helper. Whether the gating check counts IN_PROGRESS as "still working" (it should).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 27" — goal + 3 success criteria + the SYNC-REL-02 mechanism open-decision.
- `.planning/REQUIREMENTS.md` — SYNC-REL-01, SYNC-REL-02.

### Codebase touch points
- `apps/reviews/services/progress.py` `read_progress_snapshot` — the source of truth the new GET endpoint returns.
- `apps/reviews/consumers.py` `SyncProgressConsumer` + `apps/reviews/selectors/sync_progress.py` `get_progress_snapshot` — the existing WebSocket path + its auth (§13.4) to mirror for the endpoint's scoping.
- `apps/reviews/views.py` + `apps/reviews/urls.py` — add the snapshot GET view (thin, org+shop-scoped, throttled).
- `frontend/src/widgets/review-management/ProgressModal.tsx` — WebSocket-only today (`new WebSocket(/ws/sync-progress/...)`, a 1s display-only timer); add the poll fallback + merge-by-last_update_at.
- `apps/reviews/services/sync.py` `run_initial_backfill` Phase 4 — the current fixed-countdown dispatch of `finalize_canonical_tags_task` (the `_finalise_countdown` heuristic) → replace with completion-gating.
- `apps/reviews/services/finalise.py` `run_finalise_canonical_tags` / `_run_finalise` — add the PENDING/IN_PROGRESS gate + self-reschedule (bounded) at the top.
- `apps/reviews/tasks.py` `finalize_canonical_tags_task` — the thin wrapper; the self-reschedule re-dispatches this on the `tag-merge` queue.

### Conventions (CLAUDE.md)
- §5 thin views/services; §8 DRF (auth, throttling, versioned URL, no arbitrary lookups); §9/§22 tenant + shop scoping (the endpoint must not leak another org's / out-of-scope shop's progress); §13.2 NO new WebSocket consumer (HTTP fallback only); §13.4 consumer auth to mirror; §12.3/§12.4 thin idempotent Celery task; §7.6 per-org lock; §16 testing (incl. cross-tenant test for the endpoint).
</canonical_refs>

<specifics>
## Specific Ideas
- GET `/api/v1/reviews/sync-progress/{shop_id}/` (or similar) → returns the snapshot dict, org+shop-scoped, throttled; 404/empty when none.
- ProgressModal polls it ~3–5s alongside the WebSocket; merge forward by `last_update_at`; stop on terminal/close.
- finalize task self-reschedules (short countdown) while reviews PENDING/IN_PROGRESS; bounded max attempts; then runs.
- Replace the `_finalise_countdown` fixed dispatch + update the deferred-chord comment.
</specifics>

<deferred>
## Deferred Ideas
- A full **Celery chord** over the bulk-enrichment group — the heavier alternative to the self-reschedule guard; not built (D-03/D-04 chose self-reschedule).
- Real-time progress for **incremental** syncs — out of scope (§13.2 keeps the modal initial-only; incremental stays silent per SEED-06).
- Superadmin data reset — Phase 28 (deferred).
</deferred>

---

*Phase: 27-sync-progress-reliability*
*Context gathered: 2026-06-24 from Phase 22–25 UAT conversation*
