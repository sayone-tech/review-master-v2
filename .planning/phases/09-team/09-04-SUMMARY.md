---
phase: 09-team
plan: 04
subsystem: frontend/team-management
tags: [react, typescript, vitest, data-table, custom-events, rbac]
dependency_graph:
  requires: [09-02]
  provides: [team-ui-read-side, team-custom-event-bus, team-modal-stubs]
  affects: [09-05]
tech_stack:
  added: []
  patterns:
    - DataTable<TeamMemberRow> composition (mirrors ShopTable)
    - CustomEvent bus for modal coordination (team:open-*/team:member-*)
    - useTeam hook (mirrors useShops pattern)
    - TDD: tests written alongside implementation
key_files:
  created:
    - frontend/src/widgets/team-management/types.ts
    - frontend/src/widgets/team-management/api.ts
    - frontend/src/widgets/team-management/useTeam.ts
    - frontend/src/widgets/team-management/RoleBadge.tsx
    - frontend/src/widgets/team-management/AccessChips.tsx
    - frontend/src/widgets/team-management/EnabledToggle.tsx
    - frontend/src/widgets/team-management/TeamStatsCards.tsx
    - frontend/src/widgets/team-management/SoloMemberBanner.tsx
    - frontend/src/widgets/team-management/TeamEmptyState.tsx
    - frontend/src/widgets/team-management/TeamTable.tsx
    - frontend/src/widgets/team-management/TeamModals.tsx
    - frontend/src/widgets/team-management/ScopeSection.tsx
    - frontend/src/widgets/team-management/AddTeamMemberModal.tsx
    - frontend/src/widgets/team-management/EditTeamMemberModal.tsx
    - frontend/src/entrypoints/team-management.tsx
    - frontend/src/widgets/team-management/AccessChips.test.tsx
    - frontend/src/widgets/team-management/EnabledToggle.test.tsx
    - frontend/src/widgets/team-management/api.test.ts
    - frontend/src/widgets/team-management/TeamTable.test.tsx
    - frontend/src/widgets/team-management/ScopeSection.test.tsx
    - frontend/src/widgets/team-management/AddTeamMemberModal.test.tsx
    - frontend/src/widgets/team-management/EditTeamMemberModal.test.tsx
  modified:
    - frontend/vite.config.ts
decisions:
  - "ScopeSection/AddTeamMemberModal/EditTeamMemberModal implemented (not stubbed) because Plan 05 test files pre-existed in the directory and plan verification requires all tests in src/widgets/team-management/ to pass"
  - "AddTeamMemberModal validation errors consolidated into single role=alert banner (not per-field) to allow getByRole('alert') test assertion to work with a single element"
  - "EnabledToggle is a controlled switch that emits team:open-disable/team:open-enable CustomEvents — does NOT directly toggle state; real toggle happens in Plan 05 TeamModals after confirmation"
metrics:
  duration_minutes: 10
  completed_date: "2026-04-30"
  tasks_completed: 2
  files_created: 22
  tests_added: 44
---

# Phase 9 Plan 4: Team Management Read-Side Widget Summary

Built the complete read-side React widget for the Team module — DataTable composition, RoleBadge/AccessChips/EnabledToggle/TeamStatsCards/SoloMemberBanner sub-components, TeamTable with full self-protection and last-manager UI guards, CustomEvent bus, and Vite entrypoint.

## Component Inventory Built

### Task 1 — Types + API + Hook + Sub-components

| File | Purpose |
|------|---------|
| `types.ts` | TeamMemberRow, AccessScopeRow, TeamFilterParams, TeamListResponse, TeamStats, TeamCreatePayload, TeamUpdatePayload, RegionOption, ShopOption |
| `api.ts` | listTeam, createTeamMember, updateTeamMember, disableTeamMember, enableTeamMember, resendTeamInvitation, removeTeamMember, getTeamStats — CSRF + credentials='same-origin' |
| `useTeam.ts` | Filter state + paginated fetching hook (mirrors useShops). setSearch/setRegion/setShop/setPage/setPageSize/refetch |
| `RoleBadge.tsx` | Manager: inline hex `#F3E8FF`/`#7C3AED` (Tailwind JIT cannot generate dynamic purple). Staff: `bg-line-soft text-muted` |
| `AccessChips.tsx` | Manager: Crown + "All stores" amber pill. Staff: 0 scopes = "—"; up to 2 chips; +N more overflow chip |
| `EnabledToggle.tsx` | `role="switch"` controlled button — emits requests, NOT state. Disabled with `aria-disabled` + tooltip |
| `TeamStatsCards.tsx` | 3-card flex row: Total Members (Users icon), Managers (Crown icon), Active Members (CheckCircle icon) |
| `SoloMemberBanner.tsx` | Yellow tint banner visible when org admin is sole member; dispatches `team:open-add` |
| `TeamEmptyState.tsx` | Users icon + "No team members yet." + "+ Add Team Member" CTA dispatching `team:open-add` |

### Task 2 — TeamTable + Entrypoint + Plan 05 Pre-implementations

| File | Purpose |
|------|---------|
| `TeamTable.tsx` | Main grid: DataTable<TeamMemberRow> with 6 columns + actions cell; search debounce 300ms; region/store filter narrowing; pagination 10/25/50/100; stats cards; solo banner; empty state |
| `TeamModals.tsx` | Stub: `<div data-testid="team-modals-stub">`. Plan 05 replaces with real modal orchestrator |
| `team-management.tsx` | Vite entrypoint: mounts table root + modals root from `team-data`, `team-regions-data`, `team-active-shops-data`, `team-stats-data` JSON seeds |
| `ScopeSection.tsx` | Checkbox list for region + store access scope (pre-implemented for Plan 05 test compatibility) |
| `AddTeamMemberModal.tsx` | Full-name + email + role + scope form; POST to /api/v1/team/ (pre-implemented) |
| `EditTeamMemberModal.tsx` | Pre-filled edit form with locked email; PATCH to /api/v1/team/{id}/ (pre-implemented) |

## CustomEvent Bus Contract

### Events Dispatched by TeamTable

| Event | Trigger | Payload |
|-------|---------|---------|
| `team:open-edit` | Click Edit icon on non-own active row | `detail: TeamMemberRow` |
| `team:open-remove` | Click Remove icon (not own, not last manager) | `detail: TeamMemberRow` |
| `team:open-disable` | Click EnabledToggle ON state | `detail: TeamMemberRow` |
| `team:open-enable` | Click EnabledToggle OFF state | `detail: TeamMemberRow` |
| `team:open-resend` | Click Resend icon on PENDING row | `detail: TeamMemberRow` |
| `team:open-add` | Click "+ Add Team Member" CTA / solo banner link | none |

### Events Subscribed by TeamTable (triggers refetch)

| Event | Source |
|-------|--------|
| `team:member-added` | TeamModals (Plan 05) after invite sent |
| `team:member-updated` | TeamModals (Plan 05) after edit saved |
| `team:member-removed` | TeamModals (Plan 05) after removal confirmed |
| `team:member-toggled` | TeamModals (Plan 05) after enable/disable confirmed |

## Self-Protection and Last-Manager Guards

Both checks use the `currentUserId` prop read from `data-current-user-id` attribute on `#team-table-root`.

| Guard | Condition | Affected UI | Tooltip |
|-------|-----------|-------------|---------|
| Self-protection: edit | `row.id === currentUserId` | Edit button: `aria-disabled` + `opacity-40 cursor-not-allowed` | "You cannot edit yourself." |
| Self-protection: remove | `row.id === currentUserId` | Remove button: `aria-disabled` + disabled | "You cannot remove yourself." |
| Self-protection: toggle | `row.id === currentUserId` | EnabledToggle: `disabled` prop | "You cannot disable yourself." |
| Last-manager guard | `row.role === "ORG_ADMIN" && managerCount === 1` | Remove button: `aria-disabled` + disabled | "Cannot remove the last Manager." |

`managerCount` is derived from `stats.managers` (live from API refetch).

## Entrypoint Mounting Pattern

```
#team-table-root   [data-current-user-id="{id}"]
  → TeamTableWidget (reads team-data, team-regions-data, team-active-shops-data, team-stats-data JSON seeds)

#team-modals-root  [data-current-user-id="{id}"] [data-manager-count="{n}"]
  → TeamModals (stub until Plan 05)
```

Both roots are in `templates/team/team_list.html` (created in Plan 02).

## Plan 05 Dependency

TeamModals.tsx at `frontend/src/widgets/team-management/TeamModals.tsx` is currently a stub. Plan 05 must replace it with the real component implementing:
- AddTeamMemberModal (already pre-implemented — Plan 05 can refine)
- EditTeamMemberModal (already pre-implemented — Plan 05 can refine)
- DisableMemberModal (ConfirmModal variant=amber)
- RemoveMemberModal (ConfirmModal variant=red)
- ResendMemberInviteModal (ConfirmModal variant=blue)

## Test Results

All 44 tests in `src/widgets/team-management/` pass:

| Test File | Tests | Status |
|-----------|-------|--------|
| api.test.ts | 4 | PASS |
| AccessChips.test.tsx | 6 | PASS |
| EnabledToggle.test.tsx | 5 | PASS |
| ScopeSection.test.tsx | 6 | PASS |
| AddTeamMemberModal.test.tsx | 7 | PASS |
| EditTeamMemberModal.test.tsx | 4 | PASS |
| TeamTable.test.tsx | 12 | PASS |

## Deviations from Plan

### Auto-added Plan 05 Components (Rule 2 — Missing Critical Functionality)

**Found during:** Task 2 verification
**Issue:** Pre-generated test files `AddTeamMemberModal.test.tsx`, `EditTeamMemberModal.test.tsx`, and `ScopeSection.test.tsx` existed in the directory from the project linter. The plan verification command `pnpm vitest run src/widgets/team-management/` picks up all test files, causing TypeScript errors and test failures.
**Fix:** Implemented ScopeSection, AddTeamMemberModal, and EditTeamMemberModal fully (not as stubs) so all tests pass. These are Plan 05 components that are now available early.
**Files modified:** Added 3 component files + their test files to this commit.

### Auto-fix: AddTeamMemberModal Validation Alert (Rule 1 — Bug Fix)

**Found during:** Task 2 test run
**Issue:** Validation error `<p>` elements each had `role="alert"`, causing `getByRole("alert")` to throw "Found multiple elements" when both full_name and email validation failed simultaneously.
**Fix:** Consolidated all validation errors into a single `role="alert"` banner at the top of the form ("Please fix the errors below." for field errors; specific message for `non_field_errors`). Field-level errors rendered as plain `<p>` elements without `role="alert"`.

## Deferred Items

- Pre-existing failure in `src/widgets/shop-management/ShopTable.test.tsx` > "renders ConnectionStatusPill text for OAuth connected shop" — ConnectionStatusPill was removed from ShopTable in a previous plan but the test was not updated. Out of scope for Plan 04.

## Self-Check: PASSED

All 12 required files exist. All commits verified in git log:
- a64a111: feat(09-04): add team-management types, api, hook, and sub-components
- e510dc4: feat(09-04): add TeamTable, TeamModals stub, and team-management entrypoint
- 44afaa0: feat(09-05): add ScopeSection, AddTeamMemberModal, EditTeamMemberModal
