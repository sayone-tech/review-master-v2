---
phase: 23-four-step-initial-sync-seeding-queue-split
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - apps/reviews/services/sync.py
  - apps/reviews/services/finalise.py
  - apps/reviews/services/enrichment.py
  - apps/reviews/services/progress.py
  - apps/reviews/selectors/canonical_tags.py
  - apps/reviews/selectors/sync_progress.py
  - apps/reviews/tasks.py
  - config/settings/base.py
  - frontend/src/widgets/review-management/ProgressModal.tsx
  - frontend/src/widgets/review-management/TopbarSyncIndicator.tsx
findings:
  critical: 4
  warning: 4
  info: 2
  total: 10
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-06-11
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

The four-step initial sync, queue split, and seeding pipeline are broadly sound:
the Redis lock layering is correct, the per-entity SELECT FOR UPDATE idempotency
pattern is preserved, the queue routing is consistent with settings, and the
sequential seed loop design is sensible. However, four critical defects were found:
a missing `total_fetched` / `total_enriched` / `duration_seconds` payload in the
`sync.complete` event emitted by `finalise.py` (breaking the completion UI for
both ProgressModal and TopbarSyncIndicator), orphaned `_dispatch_sync_complete_notifications`
dead code that results in the consolidated "N action items found" notification
being silently dropped for all initial syncs, a blocker-level N+1 in
`_backfill_stragglers` (up to 500 individual UPDATE queries), and an error-state
rendering bug in ProgressModal where all steps always appear "complete" when an
error occurs.

---

## Critical Issues

### CR-01: `sync.complete` payload from `finalise.py` is missing `total_fetched`, `total_enriched`, and `duration_seconds`

**File:** `apps/reviews/services/finalise.py:139-147`

**Issue:** `run_finalise_canonical_tags` emits `sync.complete` with only
`merged_groups` and `stragglers_backfilled`. Both frontend consumers expect
`total_fetched`, `total_enriched`, and `duration_seconds` on this event:

- `ProgressModal.tsx:132` sets `fetched: data.total_fetched` → `undefined`.
  `snapshot?.fetched ?? 0` renders "Fetched **0** reviews" on the completion banner.
- `TopbarSyncIndicator.tsx:115` sets `total_fetched: data.total_fetched ?? 0` → `0`,
  so the completed entry always displays "Sync complete" instead of
  "X reviews synced".
- `duration_seconds` is not surfaced on the completion banner even though the
  template at `ProgressModal.tsx:314-316` renders it when non-null.

The `sync.complete` payload contract is defined by CLAUDE.md §13.5 as
`{ shop_id, total_fetched, total_enriched, duration_seconds }`.

**Fix:** Thread `fetched` and `total_enriched` (from the Redis snapshot) and
`duration_seconds` (wall-clock from when `run_finalise_canonical_tags` was
entered) through to the `sync.complete` emit:

```python
# In _run_finalise — record start time at entry
import time as _time
_finalise_start = _time.monotonic()

# ... (existing merge / backfill / count-refresh steps) ...

# Read current snapshot to get accumulated fetched + enriched counts
from apps.reviews.services.progress import read_progress_snapshot
snap = read_progress_snapshot(shop_id=shop_id) or {}

emit_progress_event(
    shop_id=shop_id,
    payload={
        "type": "sync.complete",
        "shop_id": shop_id,
        "total_fetched": int(snap.get("fetched", 0)),
        "total_enriched": int(snap.get("enriched", 0)),
        "duration_seconds": round(_time.monotonic() - _finalise_start, 1),
        "merged_groups": merged_groups,
        "stragglers_backfilled": stragglers_backfilled,
    },
)
```

---

### CR-02: Orphaned `_dispatch_sync_complete_notifications` — action item notifications silently dropped for all initial syncs

**File:** `apps/reviews/services/enrichment.py:338-387`

**Issue:** `_dispatch_sync_complete_notifications` is defined but never called in
any production code path. It was previously called when `enriched >= fetched` in
Phase 12's `_emit_enrichment_progress`. Phase 23 moved `sync.complete` ownership
to `run_finalise_canonical_tags`, but `finalise.py` never calls
`_dispatch_sync_complete_notifications` (or any equivalent). The result is:

1. `accumulate_action_items` in `_schedule_action_item_promotion` (enrichment.py:236)
   writes counts to `sync:action_items:{shop_id}` during initial sync.
2. `pop_action_item_summary` (progress.py:175) is only called from inside
   `_dispatch_sync_complete_notifications`.
3. Since `_dispatch_sync_complete_notifications` is never called, the accumulated
   action item count is silently discarded when the `sync:action_items:{shop_id}`
   key expires (1 hour after success per `TTL_SUCCESS_SECONDS`).

Every initial sync that produces action items fails to dispatch the consolidated
"N action items found" notification. The "N reviews synced" notification is also
never sent for initial syncs.

**Fix:** Call `_dispatch_sync_complete_notifications` from `_run_finalise` after
emitting `sync.complete`, passing `total_fetched` from the snapshot. Keep it
conditional on there being a snapshot (to guard against edge cases):

```python
# At the end of _run_finalise, after emit_progress_event for sync.complete:
snap = read_progress_snapshot(shop_id=shop_id) or {}
total_fetched = int(snap.get("fetched", 0))

# Import a Review representative for the shop to pass to the helper,
# or refactor _dispatch_sync_complete_notifications to accept (shop_id, org_id)
# directly instead of a Review instance to remove the coupling.
from apps.reviews.models import Review as _Review
representative = (
    _Review.objects.filter(shop_id=shop_id, deleted_at__isnull=True)
    .only("id", "shop_id", "organisation_id")
    .first()
)
if representative:
    from apps.reviews.services.enrichment import _dispatch_sync_complete_notifications
    _dispatch_sync_complete_notifications(
        review=representative, total_fetched=total_fetched
    )
```

Note: the better long-term fix is to refactor `_dispatch_sync_complete_notifications`
to accept `(shop_id, org_id, total_fetched)` directly to eliminate the need for
a Review proxy object.

---

### CR-03: N+1 queries in `_backfill_stragglers` — up to `STRAGGLER_BATCH_SIZE` individual UPDATEs

**File:** `apps/reviews/services/finalise.py:230-236`

**Issue:** The straggler backfill loop issues one `UPDATE` per `ReviewTag` row:

```python
for rt in stragglers:
    canonical_id = vocab_map.get(rt.label.lower())
    if canonical_id is not None:
        ReviewTag.objects.filter(pk=rt.pk).update(canonical_tag_id=canonical_id)  # N queries
```

With `STRAGGLER_BATCH_SIZE = 500`, this is up to 500 individual UPDATE statements.
CLAUDE.md §6: "N+1 queries are a **blocker-level bug**." §6.10: "Use `bulk_create`,
`bulk_update`, `update()`, and `F()` expressions for batch writes."

**Fix:** Group stragglers by their resolved `canonical_tag_id` and execute one
bulk UPDATE per canonical tag:

```python
from collections import defaultdict

updated = 0
groups: dict[int, list[int]] = defaultdict(list)
for rt in stragglers:
    canonical_id = vocab_map.get(rt.label.lower())
    if canonical_id is not None:
        groups[canonical_id].append(rt.pk)

with transaction.atomic():
    for canonical_id, pk_list in groups.items():
        cnt = ReviewTag.objects.filter(pk__in=pk_list).update(
            canonical_tag_id=canonical_id
        )
        updated += cnt
```

This reduces the query count from O(n stragglers) to O(distinct canonical_tag_ids),
which in practice is far smaller.

---

### CR-04: ProgressModal error-state step rendering — all steps always show "complete" when an error occurs

**File:** `frontend/src/widgets/review-management/ProgressModal.tsx:202-213`

**Issue:** When `data.type === "sync.error"` fires, the handler sets
`step: "failed"` (line 150). In `getStepState`, `currentStep = "failed"` is at
index 5 in `stepOrder`. The error branch:

```typescript
if (isError) {
  if (stepIdx < currentStepIndex) return "complete";  // indices 0-3 < 5 → always "complete"
  if (stepIdx === currentStepIndex) return "active";  // only for "failed" itself (never passed)
  return "pending";
}
```

All four visible steps ("fetching"=0, "vocab"=1, "enriching"=2, "finalising"=3)
have `stepIdx < 5`, so `getStepState` returns `"complete"` for all of them. The
UI shows all steps as complete even when a fetch-phase auth error fires before
enrichment ever starts.

**Fix:** Preserve the step that was active when the error occurred as a separate
field on the snapshot (e.g. `error_at_step`) and use that to determine which
steps to mark complete:

```typescript
// In the sync.error handler:
} else if (data.type === "sync.error") {
  setSnapshot((prev) => ({
    ...
    status: "failed",
    step: "failed",
    error_at_step: prev?.step ?? "fetching",  // capture the pre-error step
    ...
  }));
}
```

```typescript
// In getStepState:
if (isError) {
  const errorAtIndex = stepOrder.indexOf(snapshot?.error_at_step ?? "fetching");
  if (stepIdx < errorAtIndex) return "complete";
  if (stepIdx === errorAtIndex) return "active";
  return "pending";
}
```

---

## Warnings

### WR-01: `get_org_vocabulary()` called in the seed loop but its return value is discarded — wasted DB query per seed review

**File:** `apps/reviews/services/sync.py:667-669`

**Issue:** In `run_initial_backfill`, each seed-loop iteration calls
`get_org_vocabulary(organisation_id=org_id, limit=...)` but discards the
return value. The vocabulary is re-fetched inside `enrich_review` → (enrichment.py:543)
`get_org_vocabulary(...)` is called again before the OpenAI prompt is built.

This results in 2 identical `SELECT … FROM orgcanonical_tag WHERE … ORDER BY
-review_count LIMIT 200` queries per seed review: one wasted no-op at line 667,
one actually used at line 543 of enrichment.py. For `SEED_PHASE_SIZE=50` that
is 50 redundant round-trips to the DB.

The comment "D-04: re-read org vocabulary each iteration" describes the intent
correctly, but it is already fulfilled by `enrich_review`'s internal call.

**Fix:** Remove the dead call:

```python
# DELETE lines 666-669 — this is already done inside enrich_review():
# get_org_vocabulary(
#     organisation_id=org_id, limit=getattr(settings, "CANONICAL_VOCAB_INJECT_LIMIT", 200)
# )
```

---

### WR-02: `initial_backfill_task` `soft_time_limit=540` is insufficient for large seed sets under rate-bucket exhaustion

**File:** `apps/reviews/tasks.py:43-55`

**Issue:** The task comment acknowledges this concern but the chosen value is still
too low. The seed loop runs up to `SEED_PHASE_SIZE=50` sequential calls to
`enrich_review`. Each call is preceded by `_wait_for_openai_token` which can
block up to `max_wait_seconds=30.0` (progress.py:257). In the worst case
(bucket depleted on every call): 50 × (30s wait + ~5s OpenAI call) = 1,750s,
far beyond the 540s soft limit.

When `SoftTimeLimitExceeded` is raised mid-loop, `autoretry_for=(Exception,)`
catches it and retries the entire task — including `fetch_and_persist_reviews`
(Phase 1). The per-shop Redis lock (TTL 300s) will have expired by the time the
retry fires (min backoff 30s), so the full fetch re-runs. For a large shop this
creates a tight loop: fetch → seed → timeout → retry → fetch → seed → timeout…

**Fix (short term):** Reduce `_wait_for_openai_token`'s `max_wait_seconds`
default for the seed path, or cap total wait budget for the whole seed loop
rather than per-call, so the time budget is predictable. Also consider raising
`soft_time_limit` to at least `SEED_PHASE_SIZE * (avg_openai_latency + max_wait_per_call)`.

**Fix (better):** Convert the seed loop to be resumable by persisting the last
processed index to Redis (`sync:seed_cursor:{shop_id}`), so a retry picks up
where it left off rather than re-fetching:

```python
cursor_key = f"sync:seed_cursor:{shop_id}"
# At start: resume_from = int(redis.get(cursor_key) or 0)
# After each enrich: redis.setex(cursor_key, TTL_ACTIVE_SECONDS, i)
```

---

### WR-03: `finalize_canonical_tags_task` `countdown=300` is a fixed guess — bulk enrichments may not complete in time, resulting in an inaccurate `review_count` refresh

**File:** `apps/reviews/services/sync.py:728-733`

**Issue:** `finalize_canonical_tags_task` is dispatched with a fixed 5-minute
countdown after dispatching all bulk enrichment tasks. For a shop with thousands
of reviews and a loaded `ai-enrichment-high` queue, 5 minutes is insufficient.
The finalising pass will run while many reviews are still `IN_PROGRESS` or
`PENDING`. The `_refresh_review_counts` step counts only existing `ReviewTag`
rows, so bulk-enriched reviews that haven't committed yet are excluded from the
count. The `review_count` cache will be stale immediately after finalisation.

`finalize_canonical_tags_task` has `max_retries=3` but only retries on
exceptions — a "completed too early" scenario is not an exception. There is no
mechanism to re-run the count refresh once bulk enrichments settle.

**Fix:** Either (a) use a Celery chord that fires `finalize_canonical_tags_task`
only after all bulk `enrich_review_task` subtasks complete, or (b) have
`_refresh_review_counts` be called on a Beat schedule (e.g., every 15 minutes)
rather than as a one-shot post-sync step, or (c) document the limitation and
lengthen the countdown to a conservative estimate based on observed p95 bulk
enrichment latency.

---

### WR-04: `_merge_group` `logger.debug` references `winner` and `losers` which are only defined inside the `with transaction.atomic()` scope — but is unreachable when candidates < 2 (false negative)

**File:** `apps/reviews/services/finalise.py:195-201`

**Issue:** The `logger.debug` call at line 195 is outside the `with transaction.atomic():` block and references `winner` (line 187) and `losers` (line 188), both of which are defined inside the `with` block. Python's scoping rules mean variables assigned inside `with` ARE visible after the block exits — so this code is safe when the block runs to completion.

However, the early `return` at line 185 (`if len(candidates) < 2: return`) exits
`_merge_group` before `winner` and `losers` are ever assigned. Since `logger.debug`
is unreachable in that code path, this is currently safe. It is fragile: if any
future editor refactors to remove the early return or adds a new early-exit path,
a `NameError` will be silently introduced (the debug log is skipped in production
anyway but will crash if the log level is raised).

**Fix:** Move the logger into the `with transaction.atomic():` block immediately
after the merge loop, where `winner` and `losers` are in-scope and the guard
`len(candidates) >= 2` is guaranteed:

```python
with transaction.atomic():
    candidates = list(...)
    if len(candidates) < 2:
        return
    winner = candidates[0]
    losers = candidates[1:]
    for loser in losers:
        ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)
        loser.delete()
    # Log inside the block where winner/losers are guaranteed to exist
    logger.debug(
        "_merge_group organisation_id=%s lower_label=%r winner_id=%s losers=%s",
        organisation_id,
        lower_label,
        winner.pk,
        [l.pk for l in losers],
    )
```

---

## Info

### IN-01: `_dispatch_sync_complete_notifications` function signature couples `finalise.py` to a Review proxy — refactor signature when fixing CR-02

**File:** `apps/reviews/services/enrichment.py:338`

**Issue:** `_dispatch_sync_complete_notifications(*, review: Review, total_fetched: int)`
takes a `Review` object purely to extract `review.shop_id` and `review.organisation_id`.
This couples the finalise service (which operates at org/shop level, not review level)
to a fabricated Review proxy. When fixing CR-02, prefer:

```python
def _dispatch_sync_complete_notifications(
    *, shop_id: int, organisation_id: int, total_fetched: int
) -> None:
```

And update callers accordingly.

---

### IN-02: `TopbarSyncIndicator` stage-regression guard is inconsistent — `vocab` and `finalising` can regress to `fetching`

**File:** `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx:97-105`

**Issue:** The `sync.fetch.progress` handler correctly prevents regression from
`enriching` back to `fetching`. However, it does not guard against regression
from `vocab` or `finalising`:

```typescript
} else if (data.type === "sync.fetch.progress") {
  setActive((prev) =>
    prev.map((s) =>
      s.shop_id === shop.shop_id && s.stage !== "enriching"  // ← only guards "enriching"
        ? { ...s, stage: "fetching" }
        : s,
    ),
  );
}
```

A stale or re-delivered `sync.fetch.progress` event after the vocab/finalising
stages would regress the sub-label from "Building tag vocabulary…" to "Fetching
reviews from Google…". In practice this is unlikely (events are ordered in the
channel layer) but the guard is incomplete.

**Fix:** Extend the guard to cover all later stages:

```typescript
const STAGE_ORDER = ["fetching", "vocab", "enriching", "finalising"];
} else if (data.type === "sync.fetch.progress") {
  setActive((prev) =>
    prev.map((s) => {
      const currentIdx = STAGE_ORDER.indexOf(s.stage ?? "fetching");
      const fetchingIdx = STAGE_ORDER.indexOf("fetching");
      return s.shop_id === shop.shop_id && currentIdx <= fetchingIdx
        ? { ...s, stage: "fetching" }
        : s;
    }),
  );
}
```

---

_Reviewed: 2026-06-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
