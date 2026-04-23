---
phase: 03-organisation-management
plan: "04"
subsystem: frontend/react
tags: [react, vite, typescript, data-table, modals, crud, organisation-management]
dependency_graph:
  requires: [03-02, 03-03]
  provides: [org-management-widget, org-management-entrypoint]
  affects: [03-05]
tech_stack:
  added: []
  patterns:
    - React entrypoint mounting into server-rendered DOM element
    - JSON blob hydration (no initial fetch)
    - useOrgs hook with refresh-on-mutation
    - DataTable composition with renderRowActions
    - Portal-based Modal with FocusTrap
    - ApiError class for typed field-error handling
    - CreateButtonBridge listening to DOM-rendered button click
key_files:
  created:
    - frontend/src/entrypoints/org-management.tsx
    - frontend/src/widgets/org-management/types.ts
    - frontend/src/widgets/org-management/api.ts
    - frontend/src/widgets/org-management/useOrgs.ts
    - frontend/src/widgets/org-management/OrgTable.tsx
    - frontend/src/widgets/org-management/RowActionsMenu.tsx
    - frontend/src/widgets/org-management/CreateOrgModal.tsx
    - frontend/src/widgets/org-management/ViewOrgModal.tsx
    - frontend/src/widgets/org-management/EditOrgModal.tsx
    - frontend/src/widgets/org-management/OrgTable.test.tsx
    - frontend/src/widgets/org-management/CreateOrgModal.test.tsx
  modified:
    - frontend/vite.config.ts
decisions:
  - EditOrgModal uses `const currentOrg = org` after early null-return guard to satisfy TypeScript strict null checks inside async submit closure
  - CreateOrgModal test uses form.dispatchEvent(submit) instead of clicking the footer button because jsdom does not support the HTML form= attribute (cross-element form association)
  - Actions column in OrgTable satisfied by DataTable's auto-emitted `<th aria-label="Actions">` when renderRowActions is provided — no explicit DataTableColumn added
metrics:
  duration: "~10 min"
  completed_date: "2026-04-23"
  tasks_completed: 2
  files_created: 11
  files_modified: 1
---

# Phase 03 Plan 04: React OrgManagement Widget Summary

React OrgManagement widget with Vite entrypoint, DataTable composition, JSON blob hydration, and 3 non-destructive modals (Create, View, Edit) wired to DRF endpoints.

## What Was Built

### Component Tree & Data Flow

```
org-management.tsx (entrypoint)
└── OrgManagement (root component)
    ├── useOrgs() → reads #org-data blob on mount; refresh() fetches GET /api/v1/organisations/ stripping page param
    ├── OrgTable (rows, loading, handlers)
    │   ├── DataTable<OrgRow> (6 data columns + auto-emitted Actions th)
    │   └── RowActionsMenu (per-row: View/Edit/Resend/Stores/Disable/Enable/Delete)
    ├── CreateOrgModal (open, onClose, onCreated → POST /api/v1/organisations/)
    ├── ViewOrgModal (org, onClose, onEdit, onResend)
    ├── EditOrgModal (org, onClose, onUpdated → PATCH /api/v1/organisations/{id}/)
    └── CreateButtonBridge (listens for #open-create-org click via useEffect)
```

### Exports Plan 05 Will Consume

From `frontend/src/widgets/org-management/`:

| Export | File | Plan 05 Usage |
|--------|------|---------------|
| `OrgRow` interface | `types.ts` | Destructive modal prop types |
| `updateOrg` | `api.ts` | Status toggle (ACTIVE/DISABLED) + store count |
| `deleteOrg` | `api.ts` | Soft delete |
| `refresh()` from `useOrgs` | `useOrgs.ts` | Refresh after destructive mutations |
| `OrgTableHandlers.onOpenEnable/Disable/Delete/Stores` | `OrgTable.tsx` | Replace notImplemented callbacks |

### Plan 05 TODO

Replace these 4 `notImplemented` callbacks in `org-management.tsx`:
- `onOpenResend` → Resend invitation service (PATCH /api/v1/organisations/{id}/resend/)
- `onOpenAdjustStores` → AdjustStoresModal (PATCH number_of_stores)
- `onOpenEnable` / `onOpenDisable` → ConfirmModal (PATCH status)
- `onOpenDelete` → ConfirmModal with type-to-confirm (DELETE /api/v1/organisations/{id}/)

### Exact Toast Copy

| Action | Toast |
|--------|-------|
| Create success | `Organisation created. Invitation email sent to {email}.` |
| Edit success | `Organisation updated.` |
| Any API error | `Something went wrong.` + `Please try again. If the problem persists, contact support.` |
| Duplicate email | Inline field error: `An organisation with this email already exists.` |

### Actions Column

ORGL-02 "Actions" column is satisfied by DataTable's auto-emitted `<th aria-label="Actions">` when `renderRowActions` is provided. No explicit DataTableColumn was added. Tests verify this via `screen.getByLabelText("Actions")`.

### Build Artefact

- Vite entrypoint: `src/entrypoints/org-management.tsx`
- Manifest entry key: `src/entrypoints/org-management.tsx`
- Output file: `static/dist/assets/org-management-{hash}.js`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypeScript null-check error in EditOrgModal submit closure**
- **Found during:** Task 1 (tsc --noEmit)
- **Issue:** `org` parameter typed as `OrgRow | null`; early `if (!org) return null` doesn't narrow the type inside the async `submit` function closure
- **Fix:** Captured `const currentOrg = org` after the early return guard; used `currentOrg` in the submit function
- **Files modified:** `frontend/src/widgets/org-management/EditOrgModal.tsx`
- **Commit:** 38e912f

**2. [Rule 1 - Bug] jsdom form= attribute not supported in CreateOrgModal test**
- **Found during:** Task 2 (vitest run)
- **Issue:** The "Create Organisation" submit button uses `form="create-org-form"` to submit a form in the modal body; jsdom does not support this cross-element form association, so `userEvent.click(submitBtn)` did not trigger the form's `onSubmit`
- **Fix:** Changed test to dispatch a native submit event on the form element directly via `form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))`
- **Files modified:** `frontend/src/widgets/org-management/CreateOrgModal.test.tsx`
- **Commit:** 4497173

## Self-Check: PASSED

Files verified:
- frontend/src/entrypoints/org-management.tsx: FOUND
- frontend/src/widgets/org-management/types.ts: FOUND
- frontend/src/widgets/org-management/api.ts: FOUND
- frontend/src/widgets/org-management/useOrgs.ts: FOUND
- frontend/src/widgets/org-management/OrgTable.tsx: FOUND
- frontend/src/widgets/org-management/RowActionsMenu.tsx: FOUND
- frontend/src/widgets/org-management/CreateOrgModal.tsx: FOUND
- frontend/src/widgets/org-management/ViewOrgModal.tsx: FOUND
- frontend/src/widgets/org-management/EditOrgModal.tsx: FOUND
- frontend/src/widgets/org-management/OrgTable.test.tsx: FOUND
- frontend/src/widgets/org-management/CreateOrgModal.test.tsx: FOUND

Commits verified:
- 38e912f: FOUND (Task 1)
- 4497173: FOUND (Task 2)

Test results: 8 vitest tests passing, 53 backend tests passing, tsc clean, build emits org-management asset.
