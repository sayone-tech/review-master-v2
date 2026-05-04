---
phase: 12-ai-enrichment-pipeline
plan: "08"
subsystem: ui
tags: [react, websocket, typescript, progress-modal, topbar-bell, sync-progress]

requires:
  - phase: 12-ai-enrichment-pipeline/12-06
    provides: Backend emits sync.enrichment.progress events + gates sync.complete until enriched >= fetched
  - phase: 12-ai-enrichment-pipeline/12-01
    provides: Frontend type foundations (ExtractedActionItem, ReviewRow types)

provides:
  - ProgressModal handles sync.enrichment.progress: updates snapshot.enriched, sets status='enriching' or optimistically 'success'
  - ProgressModal shows 'Starting AI analysis…' before first enrichment event; live counter takes over after
  - ProgressModal 'Sync complete' banner correctly waits for status='success' (now gated by backend Plan 12-06)
  - TopbarBell per-shop stage Map derived from sync.fetch.progress / sync.enrichment.progress events
  - TopbarBell popover row shows 'Fetching reviews from Google…' (yellow spinner) or 'Analysing reviews with AI…' (green spinner)
  - TopbarBell removes shops from active list only on sync.complete

affects:
  - Phase 12 validation (12-VALIDATION.md row 2 UAT)

tech-stack:
  added: []
  patterns:
    - "Optimistic local status flip in ProgressModal: when enriched >= fetched, set status='success' immediately as UX safety net for slow WebSocket round-trips; sync.complete re-confirms duration_seconds"
    - "Stage regression guard in TopbarBell: sync.fetch.progress only sets stage='fetching' if stage !== 'enriching' — defensive against stale/out-of-order events"
    - "Conditional sub-label via snapshot.enriched === 0: 'Starting AI analysis…' hidden after first event to avoid UI clutter with redundant text alongside live counter"

key-files:
  created: []
  modified:
    - frontend/src/widgets/review-management/ProgressModal.tsx
    - frontend/src/widgets/review-management/TopbarSyncIndicator.tsx

key-decisions:
  - "Local optimistic flip in ProgressModal sync.enrichment.progress handler: when enriched >= fetched, status flips to 'success' immediately — UX safety net for slow networks; the backend sync.complete event still arrives and re-sets duration_seconds + total_fetched"
  - "'Starting AI analysis…' only renders while snapshot.enriched === 0 — once events flow, the live counter above the bar is the primary indicator; redundant subtext would clutter the UI"
  - "TopbarBell guards against stage regression in sync.fetch.progress handler — a late fetch event after enrich has started must not flip the spinner colour back to yellow"
  - "Ordering of ws.onmessage branches in TopbarBell: sync.enrichment.progress checked BEFORE sync.fetch.progress so a single message can never set both"

patterns-established:
  - "Two-stage WebSocket progress: enrichment events update snapshot.enriched; status 'enriching' set on first event; UI sub-labels and spinner colours distinguish fetch vs enrich stages"

requirements-completed:
  - ENRCH-14

duration: 2min
completed: "2026-05-02"
---

# Phase 12 Plan 08: Progress UI — Two-Stage WebSocket Wiring Summary

**Wired ProgressModal and TopbarBell to sync.enrichment.progress events: live green AI bar, 'Starting AI analysis…' pre-event placeholder, stage-aware bell popover rows (yellow/green spinner), and sync.complete banner correctly gated behind both bars reaching 100%.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-02T14:25:08Z
- **Completed:** 2026-05-02T14:27:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- ProgressModal now listens to `sync.enrichment.progress` and updates the green AI bar in real time; removes the static "Will be processed after sync completes" placeholder
- ProgressModal shows "Starting AI analysis…" sub-label only before the first enrichment event; once events flow, the live counter above the bar takes over
- "Sync complete" banner correctly waits for `status === 'success'`, which is now set by the backend's `sync.complete` event (Plan 12-06 gates it until enriched >= fetched)
- TopbarBell extended with per-shop `stage` field: `sync.fetch.progress` sets 'fetching', `sync.enrichment.progress` sets 'enriching' (non-reversible)
- Bell popover rows now show stage-aware copy and Loader2 colour: yellow + "Fetching reviews from Google…" or green + "Analysing reviews with AI…"
- TypeScript type-check passes for both files (`npx tsc --noEmit`)

## Task Commits

1. **Task 1: ProgressModal enrichment progress handler + Starting AI analysis sub-label** - `520beeb` (feat)
2. **Task 2: TopbarBell stage-aware popover rows + sync.complete-only shop removal** - `cc9df88` (feat)

## Files Created/Modified

- `frontend/src/widgets/review-management/ProgressModal.tsx` — Added `sync.enrichment.progress` branch in ws.onmessage; replaced static AI sub-label with conditional "Starting AI analysis…"
- `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` — Added `stage?` to SyncingShop; added sync.fetch.progress + sync.enrichment.progress handlers; replaced hardcoded "Syncing reviews…" row with stage-aware rendering

## Decisions Made

**1. Optimistic local status flip in ProgressModal**
When `sync.enrichment.progress` arrives and `data.enriched >= prev.fetched`, the local snapshot status flips to `"success"` immediately. This is a UX safety net for slow WebSocket round-trips — the backend `sync.complete` event still arrives a moment later and re-sets `duration_seconds` + `total_fetched`. Without this flip, on slow networks the user might see 100% bars but no "Sync complete" banner until the final event arrives.

**2. "Starting AI analysis…" shows only while snapshot.enriched === 0**
Once the first `sync.enrichment.progress` event arrives, the live counter `{enriched} of {fetched}` above the bar becomes the primary progress indicator. The bottom sub-label is removed to avoid redundant copy cluttering the modal. "Starting AI analysis…" acts as a pre-event placeholder confirming the pipeline is queued.

**3. Stage regression guard in TopbarBell**
The `sync.fetch.progress` handler only sets `stage: "fetching"` if `s.stage !== "enriching"`. This is a defensive guard: once a shop has transitioned to enriching, a stale or out-of-order fetch event must not flip the spinner colour back to yellow. The stage transition is strictly one-directional (fetching → enriching) per Plan 12-06's lifecycle.

**4. Branch ordering in TopbarBell ws.onmessage**
`sync.enrichment.progress` is checked BEFORE `sync.fetch.progress` in the if-else chain. This ensures a single message can only trigger one state update and cannot partially match both branches. The backend never sends both types simultaneously, but explicit ordering makes the logic self-documenting.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — both files compiled cleanly on first edit. TypeScript type-check passed immediately after each task.

## User Setup Required

None — no external service configuration required. This plan only consumes WebSocket events that Plan 12-06 already emits.

## Next Phase Readiness

- Phase 12 UI complete: ProgressModal and TopbarBell both reflect the full two-stage sync lifecycle
- ENRCH-14 UI half closed; ENRCH-14 data half provided by Plans 12-02 through 12-06
- Manual UAT (12-VALIDATION.md row 2) can now verify the full end-to-end flow: yellow bar fills → green bar fills → "Sync complete" banner; bell shows "Fetching reviews from Google…" → "Analysing reviews with AI…" through the full lifecycle

## Self-Check: PASSED

- `frontend/src/widgets/review-management/ProgressModal.tsx` — exists
- `frontend/src/widgets/review-management/TopbarSyncIndicator.tsx` — exists
- `.planning/phases/12-ai-enrichment-pipeline/12-08-SUMMARY.md` — exists
- Commit `520beeb` (Task 1) — found
- Commit `cc9df88` (Task 2) — found
- TypeScript: `npx tsc --noEmit` exits 0

---
*Phase: 12-ai-enrichment-pipeline*
*Completed: 2026-05-02*
