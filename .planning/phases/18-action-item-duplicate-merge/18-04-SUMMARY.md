---
phase: 18-action-item-duplicate-merge
plan: 04
subsystem: frontend / action-items
tags: [frontend, react, action-items, duplicate-merge, modal]
requires:
  - 18-02 (backend merge endpoint + detail.duplicates)
  - 18-03 (MergeModal pattern, mergeActionItems API, types)
provides:
  - DuplicatePickerModal — debounced search picker for selecting a primary
  - ActionItemModal "Also reported in" section
  - ActionItemModal "Mark as duplicate of…" entry point + ConfirmModal merge flow
affects:
  - ActionItemManagementWidget (now passes isOrgAdmin to ActionItemModal)
tech-stack:
  added: []
  patterns:
    - Debounced (300ms) listActionItems fetch with abort-on-close cleanup
    - role=listbox / role=option pattern with selected state
    - ConfirmModal reused for D-20 confirmation copy
key-files:
  created:
    - frontend/src/widgets/action-items/DuplicatePickerModal.tsx
  modified:
    - frontend/src/widgets/action-items/ActionItemModal.tsx
    - frontend/src/widgets/action-items/ActionItemManagementWidget.tsx
decisions:
  - Used ConfirmModal (not MergeModal) for the detail-flow confirmation because the primary is already chosen by the picker — MergeModal's radio-selection UI would be confusing for the single-item case. This matches the plan's explicit guidance.
  - Closed the detail modal on successful merge (current item is now hidden by the list selector's canonical__isnull=True filter, so re-opening would 404 once refetch lands).
  - Symlinked frontend/node_modules from the main repo so `npx tsc` resolves in-worktree — same recovery the 18-03 executor used.
metrics:
  duration_minutes: 8
  completed: 2026-05-22
  tasks_completed: 2
  files_touched: 3
---

# Phase 18 Plan 04: Detail-view Duplicate Marking Summary

Adds the per-item "Mark as duplicate of…" entry point on the ActionItemModal detail view, the supporting DuplicatePickerModal search component, and the "Also reported in" duplicates list that surfaces existing duplicates on a canonical item.

## What shipped

### DuplicatePickerModal (new)
- Default-size Modal titled "Mark as duplicate of" with the current item title as subtitle.
- Search input with lucide `Search` icon, 300ms-debounced fetch via `listActionItems`.
- Fetches with `page=1, page_size=20, ordering="-created_at", scope=currentItem.scope` and optional `search=` query when the user types.
- Backend already filters to canonical-only rows (plan 18-02). Client further drops the current item and any non-AI row as defence-in-depth.
- Selectable list with `role="listbox"` / `role="option"` semantics, keyboard activation via Enter/Space, and yellow-tint background on the selected row.
- Loading / empty / results states use the exact UI-SPEC copy ("Loading…", "No matching items found.").
- "Select as primary" disabled until a row is selected; on click it calls `onPicked(primaryId, primaryItem)` and closes itself.

### ActionItemModal extensions
- New `isOrgAdmin: boolean` prop, plumbed in by ActionItemManagementWidget.
- New "Also reported in" section renders inside DetailsTab view mode after the dl grid, conditional on `item.duplicates.length > 0`. Each row shows shop name (bold), formatted date (`day numeric / month short / year numeric`), and amber star rating per UI-SPEC tokens.
- New "Mark as duplicate of…" link directly below "Edit Details", visible only when `isOrgAdmin && item.source === "AI" && item.canonical_id === null` — matches the D-19 visibility rule and gives belt-and-braces hardening on top of the server-side guard from plan 18-02.
- Picker → ConfirmModal handoff: `onPicked` stores the picked primary and opens a ConfirmModal with the exact D-20 confirmation copy: `Merge 2 items into "{primary.title}"? This cannot be undone.`
- On confirm: calls `mergeActionItems({primary_id: picked.id, duplicate_ids: [currentItem.id]})`, emits a "Marked as duplicate" success toast, calls `onChanged()` to refresh the parent list, and closes the detail modal (the merged item is filtered out of the parent list by the canonical selector).
- Error path emits the exact UI-SPEC toast: "Could not merge items. Please try again." Confirm button shows "Merging…" while the call is in flight; close is blocked during that window.

## Verification

| Check | Result |
|-------|--------|
| `cd frontend && npx tsc --noEmit` | **passes**, zero errors |
| `DuplicatePickerModal.tsx` exists and exports `DuplicatePickerModal` | yes |
| `ActionItemModal.tsx` contains `Also reported in` substring | yes |
| `ActionItemModal.tsx` contains `Mark as duplicate of` substring | yes |
| All consumers of ActionItemModal updated | yes — only ActionItemManagementWidget uses it |

## Deviations from Plan

**1. [Rule 2 — missing critical functionality] ActionItemModal had no `isOrgAdmin` prop**
- **Found during:** Task 2 — the plan assumed `isOrgAdmin` was already received; the existing component took no role-related prop and derived nothing from context.
- **Fix:** Added `isOrgAdmin: boolean` to the Props interface, threaded it through DetailsTab, and updated `ActionItemManagementWidget` to pass the already-computed `isOrgAdmin = userRole === "ORG_ADMIN"` flag.
- **Files modified:** `ActionItemModal.tsx`, `ActionItemManagementWidget.tsx`.
- **Commit:** rolled into `1d59602` (Task 2 commit).

**2. [Rule 3 — blocking environment issue] frontend/node_modules absent in worktree**
- **Found during:** Task 1 verification — `npx tsc --noEmit` failed because the worktree had no node_modules.
- **Fix:** Created a symlink `frontend/node_modules → /Users/renjith/Documents/Accounts/review-master/frontend/node_modules` (the same recovery 18-03 documented). The symlink is not committed (node_modules is gitignored).
- **Commit:** none — environment-only change.

## Threat Flags

None — no new network surface, no new auth path, no new file access. Reuses existing `mergeActionItems` POST endpoint (already in the threat register from plan 18-02).

## Self-Check

- `frontend/src/widgets/action-items/DuplicatePickerModal.tsx` — FOUND
- `frontend/src/widgets/action-items/ActionItemModal.tsx` — modified, FOUND
- `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` — modified, FOUND
- Commit `de09e5a` (Task 1) — FOUND in `git log`
- Commit `1d59602` (Task 2) — FOUND in `git log`

## Self-Check: PASSED
