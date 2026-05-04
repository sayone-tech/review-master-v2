---
phase: 13-action-items-and-notifications
plan: 06
subsystem: action-items-frontend
tags: [react, vite, tailwind, datatable, action-items, list-page, three-dot-menu, rbac-layer-3]

requires:
  - phase: 13-04
    provides: ActionItem REST API (list/retrieve/create/update + transition-status/add-note custom actions); /admin/org/action-items/ template view + mount root
  - phase: 11-reviews
    provides: DataTable, emitToast, lucide-react icons, ReviewManagementWidget composition pattern, formatRelativeDate helper

provides:
  - frontend/src/widgets/action-items (StatusBadge, ScopePill, ActionItemFilters, ActionItemTable, ActionItemManagementWidget)
  - frontend/src/widgets/action-items/api.ts (list/get/create/update/transition-status/add-note clients)
  - frontend/src/widgets/action-items/useActionItems.ts (filters + 300ms-debounced search + pagination state)
  - frontend/src/entrypoints/action-items-management.tsx (mount point reading data-shops/data-team/data-user-role)
  - vite rollupOptions.input registration of `action-items-management` (and `notif-bell`, registered upfront for parallel-W4 safety)
  - Layer-3 RBAC: Scope filter hidden for STAFF_ADMIN; "+ New Action Item" button visible for both ORG_ADMIN and STAFF_ADMIN per ACTN-09

affects: [13-07]

tech-stack:
  added: []
  patterns:
    - "Widget composition mirrors ReviewManagementWidget — page heading + filters + DataTable + pagination footer"
    - "Three-dot row menu with status submenu rendered as a single dropdown (not a flyout); current status marked with a Check icon"
    - "Search field decoupled from other filters via local state + 300ms debounce in useActionItems; non-search filter changes apply immediately and reset page to 1"
    - "Modal state booleans (openModalId / createOpen) live in the widget but no UI is rendered — plan 13-07 wires the actual modals on top of these slots"

key-files:
  created:
    - frontend/src/widgets/action-items/types.ts
    - frontend/src/widgets/action-items/api.ts
    - frontend/src/widgets/action-items/useActionItems.ts
    - frontend/src/widgets/action-items/StatusBadge.tsx
    - frontend/src/widgets/action-items/ScopePill.tsx
    - frontend/src/widgets/action-items/ActionItemFilters.tsx
    - frontend/src/widgets/action-items/ActionItemTable.tsx
    - frontend/src/widgets/action-items/ActionItemManagementWidget.tsx
    - frontend/src/entrypoints/action-items-management.tsx
  modified:
    - frontend/vite.config.ts

key-decisions:
  - "STATUS_LABEL exported from types.ts (not StatusBadge.tsx) so plan 13-07's modal and our widget toast share one source of truth — discovered when 13-07 added an identical const to types.ts during parallel execution"
  - "STATUS_STYLE kept inside StatusBadge.tsx (declared as const Record on the component file) — the visual map only matters for the badge component"
  - "Sort dropdown lives inside the pagination footer (not above the table) — mirrors ReviewManagementWidget exactly"
  - "Brand option in scope filter uses amber-tint/amber per UI-SPEC; visually distinct from Shop's neutral pill"
  - "DataTable renderRowActions returns the three-dot button + dropdown component; click-outside handler attached only while menu is open to avoid global listener cost"
  - "pickEmptyState chooses one of three copy variants (no items / no results for filters / Staff sees nothing) based on filter state + role"
  - "vite.config.ts registers BOTH action-items-management AND notif-bell entrypoints in this commit per the coordination note — 13-08 doesn't need to touch vite.config.ts"

requirements-completed: [ACTN-02, ACTN-03, ACTN-04, ACTN-05, ACTN-08]

duration: 13min
completed: 2026-05-04
---

# Phase 13 Plan 06: Action Items List Page React Widget Summary

**React widget for /admin/org/action-items/ — DataTable with 8 columns, filter bar (Store/Status/Scope/Assignee/Date/Search), three-dot row menu with status submenu (any-to-any transition + toast + refetch), and pagination footer mirroring ReviewManagementWidget. Layer-3 RBAC hides Scope filter from Staff. Modal slots stubbed for plan 13-07.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-04T05:20:21Z
- **Completed:** 2026-05-04T05:33:41Z
- **Tasks:** 2
- **Files created:** 9 + 1 modified

## Accomplishments

- 9 new frontend files under `frontend/src/widgets/action-items/` and `frontend/src/entrypoints/`
- `useActionItems` hook owns filter/page/sort state, with the search input debounced at 300ms and all other filters applied immediately (resetting `page` to 1)
- `ActionItemTable` renders the 8 ACTN-04 columns plus a three-dot row menu whose status submenu shows a `Check` icon next to the current status; selecting any of the 4 statuses calls `transitionStatus` and refetches the list with a `Status updated to {Label}` toast
- `ActionItemFilters` renders 7 controls (Store/Status/Scope/Assignee/From/To/Search) plus a "Clear filters" link that appears when any filter is active. Scope filter renders only when `userRole === "ORG_ADMIN"` (Layer 3 of the three-layer Staff scope)
- Pagination footer is a near-verbatim port of `ReviewManagementWidget`'s footer (Rows 10/25/50/100 selector, Sort dropdown, page-number nav with ellipsis, "Showing X–Y of Z")
- `vite.config.ts` registers both `action-items-management` and `notif-bell` entrypoints in this commit, per the coordination note, so 13-08 doesn't have to touch the config
- Empty-state picker chooses among three copy variants (no items at all / filters match nothing / Staff sees nothing for their shops) per UI-SPEC §Copywriting
- TypeScript strict-mode and Vite production build both succeed; `action-items-management` bundle is 17.57 kB (5.42 kB gzip)

## Task Commits

1. **Task 1: types + api + useActionItems hook + entrypoint stub + Vite config** — `7a633bb` (feat)
2. **Task 2: StatusBadge + ScopePill + ActionItemFilters + ActionItemTable + Widget composition** — `5083c5f` (committed inside the parallel-running 13-08 docs commit; see deviations)

## Files Created/Modified

- `frontend/src/widgets/action-items/types.ts` — `ActionItemListRow`, `ActionItemDetail`, `ListParams`, `STATUS_LABEL`, role/scope/priority unions, payload shapes
- `frontend/src/widgets/action-items/api.ts` — `listActionItems`, `getActionItem`, `createActionItem`, `updateActionItem`, `transitionStatus`, `addNote` (CSRF cookie + same-origin fetch)
- `frontend/src/widgets/action-items/useActionItems.ts` — fetch + filter + paginate hook, 300ms search debounce
- `frontend/src/widgets/action-items/StatusBadge.tsx` — 4-status colour map (line-soft / blue-tint / green-tint / red-tint)
- `frontend/src/widgets/action-items/ScopePill.tsx` — Shop / Brand pill (amber-tint for Brand)
- `frontend/src/widgets/action-items/ActionItemFilters.tsx` — filter bar (Layer 3 Scope hide for Staff)
- `frontend/src/widgets/action-items/ActionItemTable.tsx` — DataTable wrapper with 8 columns + three-dot status submenu
- `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` — top-level composition + transition handler + pagination footer
- `frontend/src/entrypoints/action-items-management.tsx` — mount root with data-shops / data-team / data-user-role
- `frontend/vite.config.ts` — added `action-items-management` (and re-confirmed `notif-bell`) inputs

## Decisions Made

- **STATUS_LABEL is the single source of truth in `types.ts`.** Plan 13-07's modal and our widget toast both read from the same constant. Removed the duplicate I had initially placed in `StatusBadge.tsx` after 13-07's parallel commit added the canonical export.
- **STATUS_STYLE stays local to `StatusBadge.tsx`.** The visual map is a rendering concern, not an API contract.
- **Sort lives in the pagination footer, not above the table.** Matches ReviewManagementWidget exactly so the two list pages feel identical.
- **Brand option uses amber-tint / amber per UI-SPEC.** Visually distinct from Shop's neutral pill and consistent with Phase 12's AI-extracted content signals.
- **Three-dot menu uses a click-outside handler attached only while open.** Avoids paying a global listener cost on every row.
- **`pickEmptyState` is a pure function inside the widget.** Three branches based on filter presence + Staff role + total count; no need for a separate component file because each variant is < 10 lines.
- **`vite.config.ts` registers BOTH `action-items-management` and `notif-bell` upfront.** Per the coordination note this avoids 13-08 having to co-modify the config; Vite only reads `rollupOptions.input` at build time, so the missing `notif-bell.tsx` source is fine until 13-08 lands it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed duplicate STATUS_LABEL after parallel 13-07 added it to types.ts**

- **Found during:** Task 2 (writing `StatusBadge.tsx`)
- **Issue:** The plan snippet for `ActionItemManagementWidget.tsx` referenced `STATUS_LABEL`, and I initially defined it inside `StatusBadge.tsx`. Plan 13-07, running in parallel, added an identical export to `types.ts` (canonical home for shared constants). Two copies of the same map would have caused a long-term maintenance hazard.
- **Fix:** Deleted the local `export const STATUS_LABEL` from `StatusBadge.tsx`; imported it from `./types` instead. The visual `STATUS_STYLE` map stays in the badge file because it's a rendering concern.
- **Files modified:** `frontend/src/widgets/action-items/StatusBadge.tsx`
- **Verification:** `npx tsc --noEmit -p .` exits 0; `grep -n "STATUS_LABEL" frontend/src/widgets/action-items/types.ts` returns the canonical declaration.
- **Committed in:** `5083c5f` (Task 2)

**2. [Rule 3 - Blocking] vite.config.ts already had notif-bell input — coalesced into existing block**

- **Found during:** Task 1 (Vite config edit)
- **Issue:** The plan snippet asks for both `action-items-management` and `notif-bell` to be added in this commit, but 13-08 (running in parallel) had already landed `notif-bell` to `rollupOptions.input` by the time I read the file. A naive "add both" replace would have produced a duplicate key.
- **Fix:** Read the current state of `vite.config.ts`, applied a targeted edit that adds only the `action-items-management` entry alongside the existing `notif-bell` line. The end result is identical to what the plan asked for.
- **Files modified:** `frontend/vite.config.ts`
- **Verification:** `grep -n "action-items-management\|notif-bell" frontend/vite.config.ts` returns both entries; `npx vite build` produces both bundles in `static/dist/assets/`.
- **Committed in:** `7a633bb` (Task 1)

### Coordination notes (not deviations, but worth recording)

**Task 2 commit included inside a parallel agent's docs commit.** While I was running my Task 2 commit, plan 13-08's executor amended its docs commit to include the action-items widget files I had just staged (5083c5f). The files are correctly committed and tracked in git; the commit message just doesn't describe them. The bytes on disk match what this plan was supposed to ship. Hash `5083c5f` is recorded as the Task 2 commit in this Summary so traceability is preserved.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 - bug; 1 Rule 3 - blocking)
**Impact on plan:** Both fixes are local hygiene corrections forced by parallel-execution overlap with plans 13-07 and 13-08. No scope or contract changes. The action-items widget compiles, builds, and ships exactly the surface the plan asks for.

## Issues Encountered

- **Parallel-write race on `vite.config.ts` and `types.ts`.** Plans 13-07 and 13-08 ran in parallel against the same files. Edits were resolved by reading the current file state before each edit. No data loss; final state is the union of all three plans' contributions.
- **Vite build emits a chunk-size warning for `app-shell` (648 kB).** Pre-existing — not introduced by this plan; leaving as-is.

## User Setup Required

None — this is a frontend-only plan; no environment variables, secrets, or external services touched.

## Next Phase Readiness

- **Plan 13-07** can now wire `ActionItemModal` (already created) and `ActionItemCreateModal` into `ActionItemManagementWidget`. The widget already manages `openModalId` and `createOpen` state booleans; 13-07 just needs to render the modals when those are non-null/true.
- **Plan 13-07** has already added `ActionItemModal.tsx`, `NotesTab.tsx`, `SourceReviewTab.tsx`, `PriorityIndicator.tsx`, and the `createActionItemBackend` / `updateActionItemBackend` API helpers. The remaining wiring is small.
- **Plan 13-08** is independent and already complete (notif-bell shipped).
- **Manual verification (deferred to phase-level smoke test):** Visit `/admin/org/action-items/`, exercise filters, change a row status via the three-dot menu, confirm toast fires and table refetches.

## Self-Check

Verifying claimed artifacts:
- `frontend/src/widgets/action-items/types.ts` — FOUND
- `frontend/src/widgets/action-items/api.ts` — FOUND (5 clients + 2 backend variants from 13-07)
- `frontend/src/widgets/action-items/useActionItems.ts` — FOUND
- `frontend/src/widgets/action-items/StatusBadge.tsx` — FOUND
- `frontend/src/widgets/action-items/ScopePill.tsx` — FOUND
- `frontend/src/widgets/action-items/ActionItemFilters.tsx` — FOUND
- `frontend/src/widgets/action-items/ActionItemTable.tsx` — FOUND
- `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` — FOUND
- `frontend/src/entrypoints/action-items-management.tsx` — FOUND
- `frontend/vite.config.ts` — MODIFIED (action-items-management + notif-bell inputs registered)
- Commit `7a633bb` — FOUND
- Commit `5083c5f` — FOUND (contains Task 2 files; see coordination note above)
- `cd frontend && npx tsc --noEmit -p .` — exits 0
- `cd frontend && npx vite build` — exits 0; `action-items-management-ByBGFPw9.js` (17.57 kB / 5.42 kB gzip) emitted to `static/dist/assets/`

## Self-Check: PASSED

---
*Phase: 13-action-items-and-notifications*
*Completed: 2026-05-04*
