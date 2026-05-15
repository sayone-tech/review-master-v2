---
phase: 15-sync-depth-data-layer-and-superadmin-controls
plan: "04"
subsystem: frontend
tags: [react, typescript, org-management, shop-management, toggle-switch]
dependency_graph:
  requires:
    - phase: 15-sync-depth-data-layer-and-superadmin-controls
      plan: "01"
      provides: "Organisation.allow_custom_sync_depth + API endpoints"
    - phase: 15-sync-depth-data-layer-and-superadmin-controls
      plan: "02"
      provides: "Shop.sync_depth field + ShopReadSerializer"
  provides:
    - "allow_custom_sync_depth toggle in CreateOrgModal (default off)"
    - "allow_custom_sync_depth toggle in EditOrgModal (reflects current value)"
    - "Configurable sync depth dt/dd row in ViewOrgModal"
    - "SyncDepth union + SYNC_DEPTH_LABELS map in shop-management types"
    - "Review history dt/dd row in ShopDetailsModal"
  affects:
    - "Phase 16 (Org Admin shop creation selector depends on ShopRow.sync_depth)"
tech_stack:
  added: []
  patterns:
    - "ToggleSwitch extracted to dedicated widget-local component (ToggleSwitch.tsx)"
    - "SYNC_DEPTH_LABELS const map for label lookups"
key_files:
  created:
    - frontend/src/widgets/org-management/ToggleSwitch.tsx
  modified:
    - frontend/src/widgets/org-management/types.ts
    - frontend/src/widgets/org-management/CreateOrgModal.tsx
    - frontend/src/widgets/org-management/EditOrgModal.tsx
    - frontend/src/widgets/org-management/ViewOrgModal.tsx
    - frontend/src/widgets/shop-management/types.ts
    - frontend/src/widgets/shop-management/ShopDetailsModal.tsx
    - frontend/src/widgets/org-management/DeleteConfirmModal.test.tsx
    - frontend/src/widgets/org-management/OrgTable.test.tsx
    - frontend/src/widgets/org-management/ResendInvitationModal.test.tsx
    - frontend/src/widgets/org-management/StoreAllocationModal.test.tsx
    - frontend/src/widgets/shop-management/ShopModals.test.tsx
    - frontend/src/widgets/shop-management/ShopTable.test.tsx
key_decisions:
  - "ToggleSwitch extracted to ToggleSwitch.tsx in the org-management widget folder — imported by both CreateOrgModal and EditOrgModal; no shared global components folder exists"
  - "Toggle placed below Address field (last form field) in both Create and Edit modals, above footer submit row"
  - "ViewOrgModal Configurable sync depth row placed at end of dl (after Last invite) — plain text Enabled/Disabled per locked decision"
  - "ShopDetailsModal Review history row placed after Connection Status — adjacent to other config attributes"
  - "Test fixtures updated with new required fields: allow_custom_sync_depth: false (org fixtures) and sync_depth: TWO_YEARS (shop fixtures)"
metrics:
  duration: "~12 minutes"
  completed_date: "2026-05-15"
  tasks_completed: 2
  tasks_total: 2
requirements_completed: [SYNC-01, SYNC-02, SYNC-03, SDEP-03]
---

# Phase 15 Plan 04: Frontend Sync Depth Controls Summary

**ToggleSwitch component wired to allow_custom_sync_depth in Superadmin Create/Edit Org modals; ViewOrgModal shows Enabled/Disabled row; ShopDetailsModal shows Review history label via SYNC_DEPTH_LABELS lookup**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-05-15
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

### Task 1: Org management types + Create/Edit/View modals

- `allow_custom_sync_depth: boolean` added to `OrgRow`, `CreateOrgPayload`, and `UpdateOrgPayload` in `types.ts`
- `ToggleSwitch.tsx` created in the `org-management` widget folder — exported and shared between CreateOrgModal and EditOrgModal (no duplication)
- **CreateOrgModal**: `allowCustomSyncDepth` state (default `false`), toggle rendered below Address field above footer, field included in POST payload
- **EditOrgModal**: `allowCustomSyncDepth` state initialised from `org.allow_custom_sync_depth ?? false` (preserves stored `false`), toggle rendered in same position as Create modal, field included in PATCH payload
- **ViewOrgModal**: `Configurable sync depth` dt/dd row added at end of `<dl>`, showing plain text "Enabled" / "Disabled" with no badges or colour (locked decision)
- Four test fixtures updated to include `allow_custom_sync_depth: false` so TypeScript type check passes

### Task 2: Shop management types + ShopDetailsModal

- `SyncDepth = "ONE_YEAR" | "TWO_YEARS" | "ALL_TIME"` exported from `shop-management/types.ts`
- `SYNC_DEPTH_LABELS: Record<SyncDepth, string>` const map exported with human-readable labels
- `sync_depth: SyncDepth` added to `ShopRow` interface (adjacent to `connection_status`)
- **ShopDetailsModal**: `SYNC_DEPTH_LABELS` imported; `Review history` row rendered after Connection Status using existing `Row` helper with matching `dtCls`/`ddCls` classNames; plain text value
- Two shop test fixtures updated with `sync_depth: "TWO_YEARS"`

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Org types + Create/Edit/View modals with toggle and display row | e67c7cf | types.ts, ToggleSwitch.tsx, CreateOrgModal.tsx, EditOrgModal.tsx, ViewOrgModal.tsx + 4 test fixtures |
| 2 | Shop types + ShopDetailsModal Review history row | a331dcb | shop types.ts, ShopDetailsModal.tsx + 2 test fixtures |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixtures missing required new fields**
- **Found during:** TypeScript typecheck after Task 1 and Task 2
- **Issue:** `OrgRow.allow_custom_sync_depth` (required boolean) missing from 4 test fixture objects; `ShopRow.sync_depth` (required SyncDepth) missing from 2 shop test factory functions
- **Fix:** Added `allow_custom_sync_depth: false` to DeleteConfirmModal.test, OrgTable.test, ResendInvitationModal.test, StoreAllocationModal.test; added `sync_depth: "TWO_YEARS"` to ShopModals.test and ShopTable.test
- **Files modified:** 6 test files
- **Commits:** e67c7cf, a331dcb (inline with the respective feature tasks)

## ToggleSwitch Component Placement

The plan offered three options: inline definition in CreateOrgModal, copy into both modals, or extract to a shared file. Given no shared `components/` directory exists, the most consistent pattern for this project is extraction to a **widget-local shared file** (`frontend/src/widgets/org-management/ToggleSwitch.tsx`). Both Create and Edit modals import from this file. No logic duplication.

## Known Stubs

None. All form state changes are wired to API payloads and rendered from live API responses.

## Threat Flags

None. This plan touches only frontend TypeScript/React files. No new network endpoints, auth paths, or backend schema changes.

## Self-Check: PASSED

- [x] `frontend/src/widgets/org-management/ToggleSwitch.tsx` exists
- [x] `frontend/src/widgets/org-management/types.ts` has `allow_custom_sync_depth` in OrgRow, CreateOrgPayload, UpdateOrgPayload (3 occurrences)
- [x] `frontend/src/widgets/org-management/CreateOrgModal.tsx` contains `ToggleSwitch`, `role="switch"`, `Allow configurable sync depth`, description text
- [x] `frontend/src/widgets/org-management/EditOrgModal.tsx` contains `allow_custom_sync_depth` and `Allow configurable sync depth`
- [x] `frontend/src/widgets/org-management/ViewOrgModal.tsx` contains `Configurable sync depth` and `"Enabled" : "Disabled"`
- [x] `frontend/src/widgets/shop-management/types.ts` has `SyncDepth`, `SYNC_DEPTH_LABELS`, all three labels, `sync_depth: SyncDepth`
- [x] `frontend/src/widgets/shop-management/ShopDetailsModal.tsx` has `Review history` and `SYNC_DEPTH_LABELS[shop.sync_depth]`
- [x] `cd frontend && npx tsc --noEmit` exits 0
- [x] Commits e67c7cf and a331dcb exist in git log
