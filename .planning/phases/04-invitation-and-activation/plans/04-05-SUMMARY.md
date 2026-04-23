---
phase: 04-invitation-and-activation
plan: 05
subsystem: frontend
tags: [react, modal, invitation, resend, vitest, tdd]
requirements: [INVT-01, INVT-02]
dependency_graph:
  requires: [04-04]
  provides: [ResendInvitationModal, resendInvitation API function, org-management entrypoint wiring]
  affects: [frontend/src/entrypoints/org-management.tsx, frontend/src/widgets/org-management/]
tech_stack:
  added: []
  patterns: [ConfirmModal variant="blue" (yellow primary), TDD RED/GREEN, window._orgModalHandlers bridge]
key_files:
  created:
    - frontend/src/widgets/org-management/ResendInvitationModal.tsx
    - frontend/src/widgets/org-management/ResendInvitationModal.test.tsx
  modified:
    - frontend/src/widgets/org-management/api.ts
    - frontend/src/entrypoints/org-management.tsx
decisions:
  - "ConfirmModal variant='blue' maps to yellow primary button — used as specified in CONTEXT.md"
  - "emitToast import removed from entrypoint after both Phase 3 stubs were replaced"
  - "setViewRow(null) called before setResendRow(r) in ViewOrgModal.onResend so view modal closes before resend modal opens"
  - "ResendInvitationModal placed after EnableConfirmModal in JSX for logical grouping"
metrics:
  duration: "~12 minutes"
  completed_date: "2026-04-23"
  tasks_completed: 2
  files_modified: 4
---

# Phase 04 Plan 05: Resend Invitation Frontend Modal Summary

**One-liner:** ResendInvitationModal wires the resend DRF endpoint to a ConfirmModal (variant="blue"/yellow primary) with locked copy, replacing Phase 3 info-toast stubs in the org-management entrypoint.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing ResendInvitationModal tests | 2c8d01b | ResendInvitationModal.test.tsx |
| 1 (GREEN) | Implement ResendInvitationModal + resendInvitation API | 03e519c | api.ts, ResendInvitationModal.tsx, ResendInvitationModal.test.tsx |
| 2 | Wire entrypoint — replace stubs, mount modal, fix types | e73c561 | org-management.tsx |

## What Was Built

### Task 1: ResendInvitationModal component + API function

**`frontend/src/widgets/org-management/api.ts`** — Added `resendInvitation(id: number): Promise<void>`:
- Sends `POST /api/v1/organisations/<id>/resend-invitation/` with `X-CSRFToken` header and `credentials: same-origin`
- Reuses existing `headers()` helper and `handle()` error normalizer
- On non-200: throws `ApiError` (caught by modal's error handler)

**`frontend/src/widgets/org-management/ResendInvitationModal.tsx`** — New component mirroring `DisableConfirmModal` structure:
- Props: `{ org: OrgRow | null; onClose: () => void }`
- `open={org !== null}` — passes null check to ConfirmModal's open prop
- `variant="blue"` — maps to yellow primary button (`bg-yellow text-black`) per ConfirmModal mapping
- Locked copy: title "Resend Invitation", message with bolded email + name, "The previous invitation link will be invalidated."
- Submitting state: label toggles "Resend Invitation" → "Sending…"
- Double-click guard: `if (!org || submitting) return` prevents re-entry
- Success: `emitToast({ kind: "success", title: "Invitation resent to ${org.email}." })` + `onClose()`
- Error: `emitToast({ kind: "error", title: "Something went wrong.", msg: "..." })` — modal stays open

**`frontend/src/widgets/org-management/ResendInvitationModal.test.tsx`** — 8 vitest tests:
1. Renders nothing visually when org is null
2. Shows title and locked message when org is set
3. Confirm button label is "Resend Invitation" initially
4. Clicking confirm calls resendInvitation with org.id
5. Success path: emits success toast and calls onClose
6. Failure path: emits error toast and does NOT call onClose
7. Submitting: confirm label becomes "Sending…" while API is in flight
8. Double-click guard: clicking confirm twice only calls API once

### Task 2: Entrypoint wiring

**`frontend/src/entrypoints/org-management.tsx`** — 8 surgical edits:
1. Added `import { ResendInvitationModal }` (line 11)
2. Added `const [resendRow, setResendRow] = useState<OrgRow | null>(null)` inside OrgModals
3. Updated `_orgModalHandlers.onOpenResend` type: `() => void` → `(r: OrgRow) => void`
4. Replaced Phase 3 stub `onOpenResend: () => emitToast(...)` with `(r) => setResendRow(r)`
5. Replaced `ViewOrgModal.onResend` stub with `(r) => { setViewRow(null); setResendRow(r); }`
6. Mounted `<ResendInvitationModal org={resendRow} onClose={() => setResendRow(null)} />` after EnableConfirmModal
7. Updated `OrgTableWidget` getHandlers local type: `onOpenResend: () => void` → `(r: OrgRow) => void`
8. Updated handler bridge: `(_r) => getHandlers()?.onOpenResend()` → `(r) => getHandlers()?.onOpenResend(r)`
9. Removed now-unused `emitToast` import

## Requirements Covered

| Requirement | Status | Evidence |
|-------------|--------|---------|
| INVT-01 | Complete | Clicking Resend opens ResendInvitationModal; confirm calls POST /api/v1/organisations/<id>/resend-invitation/; success toast "Invitation resent to {email}." emitted |
| INVT-02 | Verified (not regressed) | OrgTable.tsx and ViewOrgModal.tsx visibility rules unchanged; Resend action only shown when activation_status !== 'active' |

## Verification Results

| Check | Result |
|-------|--------|
| vitest full suite | 36/36 tests pass (7 test files) |
| ResendInvitationModal tests | 8/8 pass |
| tsc --noEmit | 0 errors (TypeScript strict mode clean) |
| Phase 4 stubs removed | 0 occurrences of "Resend Invitation arrives in Phase 4." |
| onOpenResend Pitfall 5 | Fixed — signature is now (r: OrgRow) => void in both type locations |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ambiguous getByText("Resend Invitation") in test**
- **Found during:** Task 1 GREEN phase
- **Issue:** `getByText("Resend Invitation")` matched both the h3 title and the confirm button text, causing "multiple elements found" error
- **Fix:** Changed to `getAllByText("Resend Invitation").length >= 1` — semantically equivalent and robust
- **Files modified:** `ResendInvitationModal.test.tsx`
- **Commit:** 03e519c

None beyond the above test robustness fix — plan executed as written.

## Self-Check: PASSED

Files created/modified exist:
- FOUND: frontend/src/widgets/org-management/ResendInvitationModal.tsx
- FOUND: frontend/src/widgets/org-management/ResendInvitationModal.test.tsx
- FOUND: frontend/src/widgets/org-management/api.ts (resendInvitation added)
- FOUND: frontend/src/entrypoints/org-management.tsx (wired)

Commits exist:
- FOUND: 2c8d01b (test RED)
- FOUND: 03e519c (feat GREEN)
- FOUND: e73c561 (feat task 2)
