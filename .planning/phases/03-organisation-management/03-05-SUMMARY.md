---
phase: 03-organisation-management
plan: "05"
subsystem: frontend/org-management
tags: [react, modal, destructive-actions, disable, enable, delete, store-allocation, vitest]
dependency_graph:
  requires:
    - 03-03  # DRF endpoints: PATCH status, PATCH number_of_stores, DELETE
    - 03-04  # api.ts, types.ts, useOrgs.ts, ConfirmModal widget
  provides:
    - DisableConfirmModal component
    - EnableConfirmModal component
    - DeleteConfirmModal component
    - StoreAllocationModal component
    - Fully wired org-management entrypoint (all row actions functional)
  affects:
    - frontend/src/entrypoints/org-management.tsx
    - frontend/src/widgets/org-management/
tech_stack:
  added: []
  patterns:
    - Amber/blue/red ConfirmModal variant per action type
    - requireTypeToConfirm for destructive soft-delete flows
    - Two-step modal pattern (input step + confirmation step)
    - currentOrg const capture after null guard for TS strict-null safety
key_files:
  created:
    - frontend/src/widgets/org-management/DisableConfirmModal.tsx
    - frontend/src/widgets/org-management/EnableConfirmModal.tsx
    - frontend/src/widgets/org-management/DeleteConfirmModal.tsx
    - frontend/src/widgets/org-management/DeleteConfirmModal.test.tsx
    - frontend/src/widgets/org-management/StoreAllocationModal.tsx
    - frontend/src/widgets/org-management/StoreAllocationModal.test.tsx
  modified:
    - frontend/src/entrypoints/org-management.tsx
decisions:
  - "Store allocation upper cap set at 1000 to match CreateOrgModal client-side validation (consistency)"
  - "API error handling emits generic toast and keeps modal open for retry (no onClose on error path)"
  - "DeleteConfirmModal uses if (!org) return null guard to force re-mount on open — resets ConfirmModal internal typed state to empty on each new delete flow"
  - "StoreAllocationModal captures org in currentOrg const after null guard to satisfy TypeScript strict null checks inside async handleConfirm closure"
  - "onOpenResend remains an explicit Phase 4 info-toast placeholder (INVT-01 out of scope)"
  - "Empty string check added to isInt guard (raw.trim() !== '') to prevent Number('') === 0 false-positive"
metrics:
  duration: "26m"
  completed: "2026-04-23"
  tasks: 2
  files: 7
---

# Phase 3 Plan 05: Destructive Modals + Entrypoint Wiring Summary

Shipped the destructive modal set (Disable / Enable / Delete / Store Allocation) and wired all four into the org-management entrypoint, replacing the Plan 04 `notImplemented` stubs. Every row action in the organisations table is now fully functional end-to-end.

## Components Added

### DisableConfirmModal
- Wraps `ConfirmModal` with `variant="amber"`, title "Disable Organisation"
- Calls `updateOrg(org.id, { status: "DISABLED" })` on confirm
- Dispatches exact toast: `"{name} has been disabled."`
- Error path: generic toast shown, modal stays open for retry

### EnableConfirmModal
- Wraps `ConfirmModal` with `variant="blue"`, title "Enable Organisation"
- Calls `updateOrg(org.id, { status: "ACTIVE" })` on confirm
- Dispatches exact toast: `"{name} has been enabled."`

### DeleteConfirmModal
- Wraps `ConfirmModal` with `variant="red"`, `requireTypeToConfirm={org.name}`
- Uses `if (!org) return null` guard so ConfirmModal remounts (and resets internal `typed` state) on each new delete open
- Calls `deleteOrg(org.id)` — maps to server-side soft_delete (DORG-02 satisfied by backend, no client-side purge code)
- Dispatches exact toast: `"{name} has been deleted."`

### StoreAllocationModal
- Two-step flow: Step 1 = `Modal` with `size="sm"` + number input; Step 2 = `ConfirmModal` with `variant="blue"`
- Pre-fills input with `org.number_of_stores`; renders "Currently using X of Y stores." helper
- Validation: amber inline warning + disabled Update button when new value < `active_stores` (STOR-02)
- Confirms old → new allocation values in Step 2 message (STOR-03)
- Calls `updateOrg(org.id, { number_of_stores: parsed })` on final confirm
- Dispatches exact toast: `"Store allocation updated to {N}."`

## Entrypoint Wiring Changes

`frontend/src/entrypoints/org-management.tsx` was updated:
- Removed: `notImplemented` factory and all 5 call sites that used it
- Added: `disableRow`, `enableRow`, `deleteRow`, `storeRow` state variables
- Added: `setDisableRow`, `setEnableRow`, `setDeleteRow`, `setStoreRow` handlers wired to `OrgTable.handlers`
- Added: Four destructive modal components mounted in render tree, each with `onDone={async () => { await refresh(); }}`
- Retained: `handleResendPlaceholder` info toast explicitly referencing Phase 4 (INVT-01 deferred)

## Test Coverage

| File | Tests | Scope |
|------|-------|-------|
| OrgTable.test.tsx (Plan 04) | 5 | Table rendering, row actions menu |
| CreateOrgModal.test.tsx (Plan 04) | 3 | Form validation, API success/error |
| DeleteConfirmModal.test.tsx | 4 | requireTypeToConfirm disable/enable, success, API error |
| StoreAllocationModal.test.tsx | 4 | Helper text, warning+disabled state, step transition, confirm success |
| **Total** | **16** | All pass |

## Requirements Closed

| Requirement | Coverage |
|-------------|----------|
| ENBL-01 | DisableConfirmModal: amber confirm, PATCH status=DISABLED, success toast |
| ENBL-02 | EnableConfirmModal: blue confirm, PATCH status=ACTIVE, success toast |
| DORG-01 | DeleteConfirmModal: red confirm, requireTypeToConfirm, DELETE, success toast |
| DORG-02 | No client-side purge code; DELETE maps to soft_delete on server |
| STOR-01 | StoreAllocationModal Step 1: "Currently using X of Y stores." helper |
| STOR-02 | Input below active_stores: amber warning + disabled Update button |
| STOR-03 | Step 2 blue ConfirmModal with old/new counts; success toast |

## Deviations from Plan

None — plan executed exactly as written.

All UI-SPEC copywriting contract strings are verbatim. The `isInt` guard includes a `raw.trim() !== ""` check to prevent `Number("")` evaluating as 0 and showing a false warning — this is a correctness fix that the plan prose implied but did not explicitly write in the pseudocode.

## Self-Check: PASSED

All 7 key files confirmed on disk. Both task commits (58d7f9d, cf7737f) confirmed in git log.
