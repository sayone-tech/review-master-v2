---
phase: 09-team
plan: 05
subsystem: ui
tags: [react, vitest, typescript, custom-events, modals, team-management]

# Dependency graph
requires:
  - phase: 09-04
    provides: TeamTable CustomEvent bus, api.ts team CRUD functions, types.ts (TeamMemberRow, RegionOption, ShopOption), ConfirmModal component
provides:
  - DisableMemberModal (amber ConfirmModal wrapper, dispatches team:member-toggled)
  - RemoveMemberModal (red ConfirmModal wrapper, dispatches team:member-removed)
  - ResendMemberInviteModal (blue ConfirmModal wrapper, dispatches team:member-toggled)
  - TeamModals orchestrator (replaces Plan 04 stub — subscribes to all 6 team:open-* events, handles enable inline)
affects: [team-management entrypoint, future team-related UI changes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ConfirmModal wrapper pattern for destructive/confirmable actions (amber/red/blue variants)
    - TeamModals event bus orchestrator pattern (subscribe once in useEffect, dispatch after API success)
    - Inline enable flow (no modal, direct API call from event handler)

key-files:
  created:
    - frontend/src/widgets/team-management/DisableMemberModal.tsx
    - frontend/src/widgets/team-management/DisableMemberModal.test.tsx
    - frontend/src/widgets/team-management/RemoveMemberModal.tsx
    - frontend/src/widgets/team-management/RemoveMemberModal.test.tsx
    - frontend/src/widgets/team-management/ResendMemberInviteModal.tsx
    - frontend/src/widgets/team-management/ResendMemberInviteModal.test.tsx
    - frontend/src/widgets/team-management/TeamModals.test.tsx
  modified:
    - frontend/src/widgets/team-management/TeamModals.tsx

key-decisions:
  - "ConfirmModal uses open= prop (not isOpen=) — modal files adapted to match real component API"
  - "TeamModals prefixes unused props with _ (_currentUserId, _managerCount) to satisfy TypeScript without lint errors"
  - "Enable flow is inline in TeamModals (no confirmation modal) — single useEffect handles API call and toast directly"

patterns-established:
  - "ConfirmModal wrappers: thin wrapper with useState(loading), catch ApiError.data.detail for error toast"
  - "CustomEvent success dispatch: window.dispatchEvent(new CustomEvent('team:member-*')) immediately after API success, before onClose()"

requirements-completed:
  - TEAM-06
  - TEAM-07
  - TEAM-08
  - TEAM-09
  - TEAM-10
  - TEAM-11
  - TEAM-13
  - TEAM-14
  - TEAM-15
  - TEAM-16

# Metrics
duration: ~15min (resumed from interrupted executor)
completed: 2026-04-30
---

# Phase 09 Plan 05: Team Modal Layer Summary

**TeamModals orchestrator + 3 ConfirmModal wrappers (amber/red/blue) completing the full team management CustomEvent bus — all 6 team:open-* events handled, 58 vitest tests passing**

## Performance

- **Duration:** ~15 min (continuation of interrupted executor — files were pre-built, verified and committed)
- **Started:** 2026-04-30T09:30:00Z
- **Completed:** 2026-04-30T09:33:00Z
- **Tasks:** 2 (Task 1 completed in prior commit 44afaa0; Task 2 completed in this session ac0588f)
- **Files modified:** 8

## Accomplishments

- DisableMemberModal, RemoveMemberModal, ResendMemberInviteModal implemented as thin ConfirmModal wrappers with amber/red/blue variants respectively
- TeamModals orchestrator replaced the Plan 04 stub — subscribes to all 6 team:open-* events (add, edit, disable, enable, remove, resend); enable is handled inline (no confirmation dialog)
- Page-header "+ Add Team Member" button wired via DOM getElementById("open-add-team-member") click listener
- All 58 vitest tests pass across 11 test files (including ScopeSection, AddTeamMemberModal, EditTeamMemberModal from Task 1)

## Task Commits

Each task was committed atomically:

1. **Task 1: ScopeSection + AddTeamMemberModal + EditTeamMemberModal** - `44afaa0` (feat)
2. **Task 2: Confirm modals + TeamModals orchestrator** - `ac0588f` (feat)

**Plan metadata:** `(next commit)` (docs: complete team modal layer plan)

## Modal Component Inventory

| Component | Event subscribed to | ConfirmModal variant | API call | Success dispatch |
|-----------|--------------------|--------------------|----------|-----------------|
| DisableMemberModal | team:open-disable | amber | disableTeamMember(id) | team:member-toggled |
| RemoveMemberModal | team:open-remove | red | removeTeamMember(id) | team:member-removed |
| ResendMemberInviteModal | team:open-resend | blue | resendTeamInvitation(id) | team:member-toggled |
| (inline in TeamModals) | team:open-enable | none (direct API) | enableTeamMember(id) | team:member-toggled |

## ScopeSection Contract

```tsx
interface ScopeSectionProps {
  regions: RegionOption[];
  activeShops: ShopOption[];
  selectedRegionIds: Set<number>;
  selectedShopIds: Set<number>;
  onChangeRegions: (next: Set<number>) => void;
  onChangeShops: (next: Set<number>) => void;
  validationError?: string;
}
```

- Validates: Staff role requires at least one region OR one store selected
- Error message (rendered via `validationError` prop): "Please select at least one region or store."
- Active shops only — filtered by caller (entrypoint seed, XMOD-03)
- Empty state: "No regions to assign — create regions first." / "No active stores to assign."

## Toast Strings (verbatim from UI-SPEC)

| Action | Toast title |
|--------|------------|
| Add (invitation sent) | `Invitation sent to {email}.` |
| Edit (updated) | `Team member updated.` |
| Disable | `{Name} disabled.` |
| Enable | `{Name} enabled.` |
| Remove | `{Name} removed from team.` |
| Resend invitation | `Invitation resent to {email}.` |

## API Error Handling Strategy

All modal components catch `ApiError` and surface `e.data.detail` as the error toast message. This means server-supplied messages like "Cannot remove the last Manager." or "A user with this email already exists." are shown directly to the user. AddTeamMemberModal additionally maps field-level errors (`email`, `full_name`, `non_field_errors`) to inline form error state.

## Page Header "+ Add Team Member" Button Wiring

TeamModals registers a click listener on `document.getElementById("open-add-team-member")` in a dedicated `useEffect`. This is the DOM id set by the Django template on the page-header button. The listener calls `setOpen({ kind: "add" })` — same path as the `team:open-add` CustomEvent.

## Files Created/Modified

- `frontend/src/widgets/team-management/DisableMemberModal.tsx` — Amber ConfirmModal for disable action
- `frontend/src/widgets/team-management/DisableMemberModal.test.tsx` — 2 tests
- `frontend/src/widgets/team-management/RemoveMemberModal.tsx` — Red ConfirmModal for remove action
- `frontend/src/widgets/team-management/RemoveMemberModal.test.tsx` — 3 tests (including 403 last-manager error)
- `frontend/src/widgets/team-management/ResendMemberInviteModal.tsx` — Blue ConfirmModal for resend action
- `frontend/src/widgets/team-management/ResendMemberInviteModal.test.tsx` — 2 tests
- `frontend/src/widgets/team-management/TeamModals.tsx` — Replaces Plan 04 stub with full orchestrator
- `frontend/src/widgets/team-management/TeamModals.test.tsx` — 7 tests covering all event subscriptions + inline enable

## Decisions Made

- ConfirmModal wrapper components use `open=` prop (not `isOpen=`) matching the real ConfirmModal API; the outer components accept `isOpen` for consistency with Modal.tsx conventions and map it to `open=` when calling ConfirmModal.
- TeamModals prefixes unused props with `_` (`_currentUserId`, `_managerCount`) to satisfy TypeScript without triggering lint warnings — these props are kept for future use (e.g., last-minute revalidation).
- Enable flow has no confirmation dialog — inline API call in TeamModals event handler per plan spec.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all tests passed on first run after file verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 09 plan 05 complete — all team management React UI is wired end-to-end
- TeamTable (Plan 04) + TeamModals (Plan 05) together deliver the full team management widget
- The team-management entrypoint (also Plan 04) mounts both components; once the Django template is rendering the entrypoint, the entire team UI is live
- No blockers for Phase 10+ or post-v0.2 work

---
*Phase: 09-team*
*Completed: 2026-04-30*
