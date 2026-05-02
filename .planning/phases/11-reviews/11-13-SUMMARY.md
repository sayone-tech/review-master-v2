---
phase: "11"
plan: "13"
subsystem: frontend/topbar
tags: [react, websocket, real-time, sync-indicator, topbar]
dependency_graph:
  requires: ["11-08", "11-09"]
  provides: [topbar-sync-indicator widget, sync badge, per-shop WS subscriptions]
  affects: [templates/partials/topbar.html, frontend/vite.config.ts]
tech_stack:
  added: []
  patterns: [React useState/useRef/useEffect, WebSocket per-shop, vite entrypoint mount]
key_files:
  created:
    - frontend/src/widgets/review-management/TopbarSyncIndicator.tsx
    - frontend/src/entrypoints/topbar-sync-indicator.tsx
  modified:
    - frontend/vite.config.ts
    - templates/partials/topbar.html
decisions:
  - "Alpine.js dropdown replaced by React state (open/setOpen) — the widget is already a React root so Alpine is unnecessary here; plan CONTEXT.md mentioned Alpine compatibility but React open= state is simpler, equivalent, and avoids mixing two reactive systems in one island"
  - "SyncingShop interface defined locally in component — types.ts already exports SyncingShop/SyncingResponse for api.ts; local interface used to keep component self-contained without re-exporting shared types"
  - "Failure entries kept as local FailureEntry[] state — not pushed back to active[], so badge color logic (hasFailures) is a simple failures.length > 0 check"
metrics:
  duration_seconds: 95
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 4
---

# Phase 11 Plan 13: Topbar Sync Indicator Summary

TopbarSyncIndicator React widget — yellow spinner badge for active syncs, red badge on permanent failure, per-shop WebSocket subscriptions, dropdown with View progress / View error links — mounted in topbar via dedicated Vite entrypoint.

## State Machine

```
mount
  └─> fetchSyncingShops()                 // GET /api/v1/shops/syncing/
        └─> setActive(data.shops)
        └─> for each shop: connectToShop(shop)
              └─> new WebSocket(ws/sync-progress/{shop_id}/)
                    ├─> sync.complete  → remove from active[], remove from failures[]
                    │                   close WS, delete from sockets ref
                    ├─> sync.error    → remove from active[]
                    │                   add to failures[] with error_code/error_message
                    │                   close WS, delete from sockets ref
                    └─> sync.fetch.progress → ignored by topbar

unmount
  └─> close all open WebSocket connections, clear sockets Map
```

## Badge Rendering Logic

| Condition | Badge colour | Icon |
|---|---|---|
| `totalCount === 0` | hidden (returns null) | — |
| `totalCount > 0` and no failures | `bg-yellow text-black` | Loader2 (spin) |
| `failures.length > 0` | `bg-red text-white` | AlertTriangle |
| `totalCount > 1` | count number shown | same as above |

## URL Contract for "View progress" Links

Active shops: `/admin/org/shops/?open_progress={shop_id}` — labelled "View progress"
Failed shops: `/admin/org/shops/?open_progress={shop_id}` — labelled "View error"

Both use the same URL contract defined in Plan 08 and consumed by Plan 12's ProgressModal.
The Shops page reads `?open_progress` on mount to auto-open the progress modal for the given shop.

## Vite Entrypoint Registration

`topbar-sync-indicator` entry added to `vite.config.ts` rollupOptions.input.
`{% vite_asset 'src/entrypoints/topbar-sync-indicator.tsx' %}` added at end of topbar.html.
Mount point `<div id="sync-indicator-root">` inserted before the notifications bell button.
`{% load django_vite %}` added at top of topbar.html.

## Deviations from Plan

### Auto-selected Pattern Change

**Alpine.js dropdown replaced by React state**

- **Found during:** Task 1 — plan CONTEXT.md specified Alpine.js-compatible dropdown
- **Rationale:** The widget is a standalone React root; mixing Alpine and React in the same island adds unnecessary complexity. React `useState(open)` achieves identical UX with no Alpine dependency.
- **Impact:** No functional difference; dropdown opens/closes on button click. Accessibility attributes (`aria-expanded`, `aria-haspopup`, `role="menu"`) are set correctly.

None — plan executed exactly as written for all acceptance criteria.

## Self-Check: PASSED

Files exist:
- frontend/src/widgets/review-management/TopbarSyncIndicator.tsx — FOUND
- frontend/src/entrypoints/topbar-sync-indicator.tsx — FOUND
- frontend/vite.config.ts contains "topbar-sync-indicator" — FOUND
- templates/partials/topbar.html contains "sync-indicator-root" — FOUND
- templates/partials/topbar.html contains "topbar-sync-indicator.tsx" — FOUND

Commits exist:
- 9e76078 feat(11-13): add TopbarSyncIndicator component — FOUND
- 27a9bf2 feat(11-13): wire entrypoint, Vite registration, and topbar mount point — FOUND
