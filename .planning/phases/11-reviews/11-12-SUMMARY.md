---
phase: 11-reviews
plan: "12"
subsystem: frontend
tags: [react, websocket, progress-modal, shop-management]
dependency_graph:
  requires: ["11-09"]
  provides: [ProgressModal, open_progress URL handoff]
  affects: [frontend/src/widgets/review-management, frontend/src/widgets/shop-management, frontend/src/entrypoints/shop-management.tsx]
tech_stack:
  added: []
  patterns: [WebSocket lifecycle in useEffect, URL param read on mount, modal portal via shared Modal component]
key_files:
  created:
    - frontend/src/widgets/review-management/ProgressModal.tsx
  modified:
    - frontend/src/widgets/shop-management/ShopTable.tsx
    - frontend/src/entrypoints/shop-management.tsx
decisions:
  - "ProgressModal mounts inside ShopTableWidget (not a portal root) — consistent with how ShopModals manages other modals"
  - "URL param ?open_progress= cleared via history.replaceState immediately after modal opens — prevents re-open on refresh"
  - "ETA calculation guards page_count >= 2 — first page has no elapsed time ratio to extrapolate from"
  - "WebSocket opened only when open=true and shopId set — effect cleanup closes ws on unmount or close"
metrics:
  duration: "2 minutes"
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_modified: 3
---

# Phase 11 Plan 12: ProgressModal — WebSocket Sync Progress UI Summary

**One-liner:** ProgressModal connects to /ws/sync-progress/{shopId}/ via WebSocket, renders fetching/complete/error states, and auto-opens from the Shops page when ?open_progress= is present in the URL.

## What Was Built

### Task 1: ProgressModal component (`frontend/src/widgets/review-management/ProgressModal.tsx`)

New component wrapping the shared `Modal` with WebSocket-driven sync progress display. Key design points:

**WebSocket lifecycle:** A single `useEffect([open, shopId])` opens the WebSocket when the modal opens and closes it on unmount or when `open` becomes false. `wsRef` holds the ref but is not used as state — the effect is the single source of truth for the ws lifecycle.

**Message-type switch:**
- `sync.fetch.progress` — increments fetched/total_estimate, bumps page_count
- `sync.complete` — transitions to `success` status with final totals + duration
- `sync.error` — transitions to `failed` with error_code and error_message
- Initial snapshot (no `type` field, has `status` field) — replaces entire state

**ETA formula:** Guards `page_count >= 2` before computing. Uses elapsed time since `started_at` + current fetch rate (reviews/sec) to estimate remaining time. Returns null if rate is 0 or if insufficient data.

**Three render states:**
- **Fetching:** Two progress bars — yellow ("Fetched from Google") and green ("Processed with AI") — with live percentage, count, and ETA.
- **Complete:** CheckCircle icon + total fetched + duration.
- **Error:** AlertTriangle + "Sync paused" copy. `invalid_grant` error shows "Reconnect Google" CTA.

**Footer:**
- "Run in background" visible only during fetching — closes modal, sync continues.
- "View Shop Details" disabled (`pointer-events-none`) until terminal state (complete or error).

**Last-update tick:** A second `useEffect([snapshot])` runs a 1-second interval to display "Last updated N seconds ago" using `snapshot.last_update_at`.

### Task 2: ShopTable + entrypoint wiring

**ShopTable.tsx changes:**
- `openProgressShopId?: number | null` added to `ShopTableWidgetProps`
- `progressShopId` + `progressShopName` state initialised from prop
- `useEffect([progressShopId, rows])` resolves shop name from rows and clears `?open_progress` from URL via `window.history.replaceState`
- `<ProgressModal>` rendered inside the widget's return tree — uses portal internally via `Modal`, so renders over the full viewport

**shop-management.tsx changes:**
- `readOpenProgressShopId()` function reads `?open_progress` from `window.location.search` at init time
- Result passed as `openProgressShopId` prop to `ShopTableWidget`

**URL handoff convention:** When OAuth completes (Plan 11-08), the backend redirects to `/admin/org/shops/?open_progress=<shop_id>`. The entrypoint reads this on mount, passes to ShopTableWidget, which opens ProgressModal and clears the param — so a page refresh after the modal is dismissed does not reopen it.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check

- [x] `frontend/src/widgets/review-management/ProgressModal.tsx` created and contains all required strings
- [x] TypeScript compiles cleanly (zero errors)
- [x] Task 1 commit: `13607d1`
- [x] Task 2 commit: `93e45f6`
