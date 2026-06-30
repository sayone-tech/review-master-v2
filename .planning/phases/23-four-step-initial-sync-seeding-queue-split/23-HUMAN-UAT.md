---
status: partial
phase: 23-four-step-initial-sync-seeding-queue-split
source: [23-VERIFICATION.md, 23-04-PLAN.md]
started: 2026-06-11
updated: 2026-06-11
---

## Current Test

[awaiting human testing — requires full stack running end-to-end]

## Context

All automated verification passed (18/18 must-haves; SEED-01..04, DSYNC-01, QUEUE-01 covered;
backend pytest + frontend `tsc --noEmit` green; all 4 code-review Critical findings fixed and
confirmed). The only remaining gate is the live four-step progress UI verification deferred from
Plan 23-04 Task 3 — it could not run earlier because it needs the Wave-3 backend orchestration
(merged afterwards) emitting live events during a real initial sync.

## Setup

1. Run backend (web + Celery worker for `google-sync`, `ai-enrichment-high`, `ai-enrichment-low`,
   `tag-merge` queues + beat) and the frontend dev/build so WebSocket events flow end to end.
2. Trigger an initial sync for a store with **> 50 reviews** so seed (first 50) + bulk + finalising
   all occur.

## Tests

### UAT-23-01 — Four-step ProgressModal visual fidelity
- [ ] All four steps render from open: **Fetching Reviews** (yellow) → **Building Tag Vocabulary**
      (green) → **AI Enrichment** (green) → **Finalising** (amber).
- [ ] Steps not yet reached render dimmed (`opacity-60`) with a track-only bar and "–" counter.
- [ ] The active step shows live X/Y counters that advance.
- [ ] Steps complete in order: Fetching → Building Tag Vocabulary → AI Enrichment → Finalising.
- [ ] On completion the banner shows the real fetched count (not "Fetched 0 reviews") — confirms CR-01.

### UAT-23-02 — TopbarSyncIndicator four-stage sub-label/spinner
- [ ] Sub-label advances through "Fetching reviews from Google…", "Building tag vocabulary…",
      "Analysing reviews with AI…", "Finalising…".
- [ ] Spinner color matches the active stage; the label never regresses to an earlier stage.

### UAT-23-03 — Reconnect repaint restores correct step
- [ ] Reload the page mid-sync; the modal repaints the **correct current step** from the reconnect
      snapshot immediately, without waiting for the next live event.

### UAT-23-04 — (optional) Notification dispatch — confirms CR-02
- [ ] After a sync completes, the consolidated "N reviews synced" / "N action items found"
      notification(s) appear (no longer silently dropped).

## Gaps

(none — automated verification found no functional gaps; these items are manual-only by design.)
