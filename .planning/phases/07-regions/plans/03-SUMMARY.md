---
phase: 07-regions
plan: "03"
subsystem: ui
tags: [react, typescript, vite, tailwindcss, lucide-react, vitest]

# Dependency graph
requires:
  - phase: 07-regions-01
    provides: Django template with region-modals-root + region-table-root mount points and region-data json_script
  - phase: 07-regions-02
    provides: Backend REST API at /api/v1/regions/ (list, create, patch, delete with 409 guard)
provides:
  - React region-management widget with full CRUD UI
  - CreateRegionModal with autoMode auto-ID state machine (RGN-04/RGN-05)
  - EditRegionModal with no auto-ID (RGN-08)
  - Delete-blocked amber popup for 409 responses (RGN-10)
  - Red ConfirmModal delete confirmation (RGN-11)
  - region-management Vite entrypoint bundled in static/dist
affects: [08-shops, 09-team]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - two-root entrypoint (region-modals-root always + region-table-root when rows > 0)
    - CreateButtonBridge pattern for Django-template buttons bridging to React modals
    - autoMode state machine: derives region_id from name until user manually edits it, resumes on clear
    - 409-as-data: deleteRegion returns RegionBlockedError object instead of throwing, caller decides popup

key-files:
  created:
    - frontend/src/widgets/region-management/types.ts
    - frontend/src/widgets/region-management/api.ts
    - frontend/src/widgets/region-management/useRegions.ts
    - frontend/src/widgets/region-management/RegionIdBadge.tsx
    - frontend/src/widgets/region-management/RegionEmptyState.tsx
    - frontend/src/widgets/region-management/RegionTable.tsx
    - frontend/src/widgets/region-management/CreateRegionModal.tsx
    - frontend/src/widgets/region-management/EditRegionModal.tsx
    - frontend/src/widgets/region-management/RegionModals.tsx
    - frontend/src/widgets/region-management/RegionModals.test.tsx
    - frontend/src/entrypoints/region-management.tsx
  modified:
    - frontend/vite.config.ts

key-decisions:
  - "07-03: DataTable used with accessor/label/rowKey API (not render/header) — adapted plan spec to real component interface"
  - "07-03: emitToast uses kind (not type) and msg (not message) — corrected from plan spec to match actual lib/toast.ts API"
  - "07-03: Action buttons use DataTable renderRowActions wrapper (opacity-35 group-hover:opacity-100 already applied by DataTable row) — cleaner than embedding in a column accessor"
  - "07-03: Delete-blocked popup uses Modal directly with amber icon block (not ConfirmModal) — matches plan: single Got it button, ConfirmModal forces two-button footer"
  - "07-03: data-auto-mode uses String(autoMode) to render 'true'/'false' string attributes for testability"

patterns-established:
  - "autoMode state machine: set autoMode=false on non-empty regionId change, set autoMode=true on empty clear, run deriveRegionId on name change only when autoMode=true"
  - "409-as-data pattern: async function returns union type void|BlockedError, callers use 'shop_count in result' type guard"

requirements-completed: [RGN-01, RGN-02, RGN-03, RGN-04, RGN-05, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11]

# Metrics
duration: 3min
completed: 2026-04-28
---

# Phase 7 Plan 3: Frontend Region Management Widget Summary

**React region-management widget with autoMode auto-ID state machine, DataTable integration, amber/red delete popups, and Vite entrypoint bundled at 12.7 kB**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-28T07:19:01Z
- **Completed:** 2026-04-28T07:22:11Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Built complete region-management widget (11 files) matching the UI-SPEC exactly
- All 4 Vitest tests pass: auto-ID populates, stops on manual edit, resumes on clear (RGN-05), edit mode no-auto (RGN-08)
- `npm run build` succeeds with `region-management` entrypoint in manifest (12.70 kB gzipped 4.06 kB)

## Task Commits

Each task was committed atomically:

1. **Task 7-03-01: Types, API layer, data hook, Vite entrypoint registration** - `a640c95` (feat)
2. **Task 7-03-02: Region table, badges, empty state, create/edit modals, delete popups** - `8a17ff8` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `frontend/src/widgets/region-management/types.ts` - RegionRow, CreateRegionPayload, UpdateRegionPayload, RegionBlockedError
- `frontend/src/widgets/region-management/api.ts` - CRUD API: listRegions, createRegion, updateRegion, deleteRegion (409→data)
- `frontend/src/widgets/region-management/useRegions.ts` - Data hook with region:refresh event listener
- `frontend/src/widgets/region-management/RegionIdBadge.tsx` - Monospace pill badge (font-mono, bg-line-soft text-muted)
- `frontend/src/widgets/region-management/RegionEmptyState.tsx` - MapPin icon, "No regions yet", yellow CTA
- `frontend/src/widgets/region-management/RegionTable.tsx` - DataTable wrapper + RegionTableWidget event dispatcher
- `frontend/src/widgets/region-management/CreateRegionModal.tsx` - Modal with autoMode state machine + deriveRegionId
- `frontend/src/widgets/region-management/EditRegionModal.tsx` - Modal pre-filled, no autoMode (RGN-08)
- `frontend/src/widgets/region-management/RegionModals.tsx` - Orchestrator: CreateButtonBridge, all modal state, delete guards
- `frontend/src/widgets/region-management/RegionModals.test.tsx` - 4 Vitest tests (auto-ID mechanic + edit-no-auto)
- `frontend/src/entrypoints/region-management.tsx` - Two-root entrypoint (modals-root always, table-root when rows)
- `frontend/vite.config.ts` - Added region-management to rollupOptions.input

## Decisions Made

- **DataTable API adaptation:** The plan specified `render`/`header` column props but the actual `DataTable` component uses `accessor`/`label`/`rowKey`. Adapted all column definitions to match the real interface.
- **emitToast signature:** Plan used `type`/`message` but actual `lib/toast.ts` uses `kind`/`msg`. Fixed throughout.
- **renderRowActions for action buttons:** Used `DataTable`'s `renderRowActions` prop which already provides the `opacity-35 group-hover:opacity-100` wrapper, rather than embedding action buttons in a regular column accessor.
- **Delete-blocked popup as plain Modal:** Used `Modal` directly with a manual amber icon block matching `ConfirmModal`'s visual. This gives a single "Got it" button footer (ConfirmModal forces two buttons).
- **data-auto-mode as string attribute:** Used `String(autoMode)` so the HTML attribute value is `"true"`/`"false"` for reliable test assertions with `toHaveAttribute`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected DataTable column prop names**
- **Found during:** Task 7-03-02 (RegionTable implementation)
- **Issue:** Plan code used `render`/`header` prop names but actual `DataTable` uses `accessor`/`label` with required `rowKey` prop
- **Fix:** Updated RegionTable column definitions to use `accessor`, `label`, `rowKey`
- **Files modified:** `frontend/src/widgets/region-management/RegionTable.tsx`
- **Verification:** TypeScript compilation passed, build succeeded
- **Committed in:** `8a17ff8` (Task 7-03-02 commit)

**2. [Rule 1 - Bug] Corrected emitToast API signature**
- **Found during:** Task 7-03-02 (CreateRegionModal, EditRegionModal, RegionModals)
- **Issue:** Plan used `{ type, message }` but `lib/toast.ts` exports `emitToast({ kind, title, msg })`
- **Fix:** Replaced `type` → `kind`, `message` → `msg` across all three modal files
- **Files modified:** `frontend/src/widgets/region-management/CreateRegionModal.tsx`, `EditRegionModal.tsx`, `RegionModals.tsx`
- **Verification:** TypeScript compilation passed, no type errors
- **Committed in:** `8a17ff8` (Task 7-03-02 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - mismatches between plan spec and actual component/library APIs)
**Impact on plan:** Both fixes required for correct TypeScript compilation. No scope creep.

## Issues Encountered

None beyond the two API signature mismatches documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Region management widget is complete and bundled. Django template from Plan 01 can load the `region-management` Vite bundle.
- Phase 8 (Shops) can reference this module's patterns: two-root entrypoint, autoMode state machine, 409-as-data delete guard, CreateButtonBridge.
- Visual check at `/admin/org/regions/` requires the Django server with Plan 01 and Plan 02 complete.

---
*Phase: 07-regions*
*Completed: 2026-04-28*
