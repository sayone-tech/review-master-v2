---
phase: 18-action-item-duplicate-merge
plan: 03
subsystem: frontend
tags: [frontend, react, action-items, merge, multi-select, modal]
dependency_graph:
  requires:
    - "18-02 backend contract: POST /api/v1/action-items/merge/, list duplicate_count, detail.duplicates"
  provides:
    - "Multi-select checkbox column on the action-items list (Org Admin only)"
    - "Merge toolbar visible when ≥2 AI items are selected"
    - "MergeModal: pick-primary radio step → inline confirm step → server call"
    - "Shared frontend types: ActionItemListRow.duplicate_count, ActionItemDuplicate, MergePayload, ActionItemDetail.duplicates/canonical_id (also consumed by plan 18-04)"
  affects:
    - "frontend/src/widgets/data-table/DataTable.tsx — gains optional multi-select props (additive; no existing consumer affected)"
    - "frontend/src/widgets/action-items/ActionItemTable.tsx — adds +N badge on title and forwards checkbox props"
    - "frontend/src/widgets/action-items/ActionItemManagementWidget.tsx — selection state + toolbar + MergeModal integration"
tech-stack:
  added: []
  patterns:
    - "Optional-prop extension on a shared primitive (DataTable): all new props are optional and unused consumers see zero rendered diff"
    - "Local Set<number> selection state with explicit invalidation effect on filter/page change"
    - "Two-step modal flow inside a single Modal shell with footer-driven step transitions"
key-files:
  created:
    - frontend/src/widgets/action-items/MergeModal.tsx
  modified:
    - frontend/src/widgets/action-items/types.ts
    - frontend/src/widgets/action-items/api.ts
    - frontend/src/widgets/data-table/DataTable.tsx
    - frontend/src/widgets/action-items/ActionItemTable.tsx
    - frontend/src/widgets/action-items/ActionItemManagementWidget.tsx
decisions:
  - "DataTable extension is purely additive — checkbox column only renders when selectedIds is defined, preserving every existing call site."
  - "isRowSelectable is gated on isOrgAdmin && source==='AI' at the ActionItemTable layer, so Staff and MANUAL rows can never be selected even if the toolbar somehow surfaced."
  - "Item meta inside MergeModal shows scope ('Brand') or 'Shop · {shop_name}' — list rows already carry shop_name, so no extra fetch is needed."
metrics:
  duration: "~25 minutes"
  completed: "2026-05-22"
---

# Phase 18 Plan 03: List view multi-select + Merge toolbar + MergeModal Summary

Wired the entire list-side merge UX in one wave: shared frontend types (also used by plan 18-04), the API client function, the generic DataTable checkbox column, the action-item-specific +N badge and selectable gating, plus the merge toolbar and two-step MergeModal in the management widget.

## What shipped

### Task 1 — Types, API, DataTable, ActionItemTable (`ad17c68`)

- **`types.ts`** — added `duplicate_count: number` to `ActionItemListRow`; added new `ActionItemDuplicate` interface (id, title, shop_name, source_review_date, source_review_rating) for plan 18-04's picker; added `duplicates: ActionItemDuplicate[]` and `canonical_id: number | null` to `ActionItemDetail`; added the `MergePayload` request type.
- **`api.ts`** — added `mergeActionItems(payload: MergePayload): Promise<ActionItemDetail>` using the existing `fetch` + `headers("POST")` + `handle()` pattern. Sends to `/api/v1/action-items/merge/` with `credentials: "same-origin"`. CSRF is supplied by the existing `headers()` helper, satisfying T-18-03-02.
- **`DataTable.tsx`** — added four optional props: `selectedIds?: Set<string>`, `onToggleRow?`, `onToggleAll?`, `isRowSelectable?`. When `selectedIds` is defined, renders a leading `<th>`/`<td>` column with a 40px width. Header checkbox has correct indeterminate state via a ref + `useEffect`. Disabled checkboxes use `opacity-40 cursor-not-allowed`. Skeleton + empty-state rows account for the extra column in their `colSpan` and skeleton cells. **No existing consumer needs any change.**
- **`ActionItemTable.tsx`** — added `selectedIds?: Set<number>`, `onToggleRow?`, `onToggleAll?`, `isOrgAdmin?` props. Title cell wrapped in `flex items-center gap-2` with a conditional `+N` badge styled `bg-amber-tint text-amber text-[11px] font-semibold` (badge has an aria-label for screen readers). `isRowSelectable` is `(r) => r.source === "AI"` only when `isOrgAdmin` is true. Number-string ID conversion happens at this layer so DataTable can stay generic.

### Task 2 — MergeModal + ActionItemManagementWidget (`dbf4e92`)

- **`MergeModal.tsx` (new)** — props `{ open, selectedItems, onClose, onMerged }`. Internal state: `primaryId: number | null`, `step: "pick" | "confirm"`, `saving: boolean`. A `useEffect([open])` resets all three when the modal transitions to open. **Pick step** renders a `role="radiogroup"` with one label per selected item, selected row gets `border-yellow bg-yellow-tint`, item meta shows `Brand` or `Shop · {shop_name}`. **Confirm step** replaces the radio list with the amber `AlertTriangle` icon block + "Confirm merge" title + the exact UI-SPEC message. Footer changes per step. The "Merge items" button on the confirm step is `aria-busy={saving}` and shows `"Merging…"` during the call. On success: `emitToast({kind:"success", title:"Items merged successfully"})` then `onMerged()` then `onClose()`. On error: `emitToast({kind:"error", title:"Could not merge items. Please try again."})` and stays on the confirm step so the user can retry without re-picking. `dismissible={!saving}` blocks the user from closing the modal mid-request.
- **`ActionItemManagementWidget.tsx`** — added `selectedIds: Set<number>` and `mergeModalOpen: boolean` state. A new `useEffect` clears `selectedIds` whenever any list-shaping param changes (page, shop, status, scope, category, assignee, from_date, to_date, search). `handleToggleRow` and `handleToggleAll` mutate the set immutably. The toolbar renders **only when `isOrgAdmin && selectedIds.size >= 2`** with the exact UI-SPEC copywriting ("{N} items selected", "Clear selection", "Merge duplicates"). The table receives `selectedIds`, `onToggleRow`, `onToggleAll`, `isOrgAdmin` so the +N badge is visible to all users but checkboxes are only interactive for Org Admin on AI rows. The MergeModal is fed `selectedItems` filtered from the current page's rows; on merge it clears the selection and refetches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Worktree path safety] Initial edits accidentally landed in the main repo**

- **Found during:** Task 1, first commit attempt.
- **Issue:** The first round of Edit/Write calls used absolute paths starting with `/Users/renjith/Documents/Accounts/review-master/frontend/...` (derived from the orchestrator-context `pwd`), but this executor is running inside the Claude worktree at `/Users/renjith/.../worktrees/agent-a856e57e9c39b312c`. Absolute paths bypassed the worktree and wrote to the main repo's working tree — the worktree's `git status` came back clean and the commit failed with "nothing to commit".
- **Fix:** Copied the four modified files from the main repo into the worktree at the equivalent relative paths, ran `git checkout --` on the main repo to restore it, then re-staged from inside the worktree. All subsequent edits used absolute paths *rooted at the worktree root* and the symlink `frontend/node_modules → /Users/renjith/.../review-master/frontend/node_modules` was created so `npx tsc` resolves correctly inside the worktree.
- **Files modified:** Same four files as planned — recovery left zero functional difference.
- **Commit:** rolled into `ad17c68` (the recovered first commit). Per the worktree-path-safety reference, this is the documented hazard for `#3099`.

**2. [Rule 2 — Auto-add missing functionality] Selection clears on `category` filter change too**

- **Found during:** Task 2.
- **Issue:** The plan listed `params.page, params.shop, params.status, params.scope, params.search` as the dependency list for clearing the selection. The widget also has a `category` filter (Phase 13) and an `assignee` / `from_date` / `to_date` filter group; if a user selected rows then changed any of those, the selection would persist over rows that no longer match.
- **Fix:** Expanded the `useEffect` dependency list to cover all list-shaping params (`category`, `assignee`, `from_date`, `to_date`). Same intent as the plan — every filter mutation should clear selection — just complete coverage.
- **Files modified:** `ActionItemManagementWidget.tsx`.
- **Commit:** `dbf4e92`.

No architectural changes (Rule 4) and no auth gates.

## Threat Surface

No new threat surface beyond the plan's STRIDE register:

- **T-18-03-02 (CSRF):** `headers("POST")` already sends `X-CSRFToken` from the `csrftoken` cookie — same pattern as every other mutating call in `api.ts`.
- **T-18-03-03 (MANUAL items in merge):** `isRowSelectable=(r)=>r.source==="AI"` disables the checkbox client-side; backend (plan 18-02) rejects MANUAL items with HTTP 400 regardless.
- **T-18-03-01 (Toolbar visibility):** Toolbar render is gated on `isOrgAdmin`; backend enforces `IsOrgAdmin` on `/merge/` (plan 18-02), so Staff cannot merge even by replaying the request.

## Verification

- `cd frontend && npx tsc --noEmit` → zero errors (both commits)
- All five must-have artifact paths exist with the expected `contains` substrings (verified in self-check below)
- DataTable backward-compat: every existing consumer (organisation tables, store tables, reviews tables) imports DataTable without passing the new props — runtime behavior is bit-identical to pre-change

## Self-Check: PASSED

Files exist and commits are on the worktree branch:

- `frontend/src/widgets/action-items/types.ts` — FOUND (contains `duplicate_count`, `MergePayload`)
- `frontend/src/widgets/action-items/api.ts` — FOUND (contains `mergeActionItems`)
- `frontend/src/widgets/data-table/DataTable.tsx` — FOUND (contains `selectedIds`)
- `frontend/src/widgets/action-items/ActionItemTable.tsx` — FOUND (contains `duplicate_count`)
- `frontend/src/widgets/action-items/MergeModal.tsx` — FOUND (contains `MergeModal`)
- `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` — FOUND (contains `selectedIds`)
- Commit `ad17c68` — FOUND on `worktree-agent-a856e57e9c39b312c`
- Commit `dbf4e92` — FOUND on `worktree-agent-a856e57e9c39b312c`

## Commits

| # | Task | Commit |
|---|------|--------|
| 1 | Types + API + DataTable + ActionItemTable checkbox & +N badge | `ad17c68` |
| 2 | MergeModal + ActionItemManagementWidget toolbar & integration | `dbf4e92` |

## Downstream contract

`mergeActionItems()`, `ActionItemDuplicate`, `MergePayload`, and `ActionItemDetail.duplicates`/`canonical_id` are now stable for plan 18-04 (detail-view DuplicatePickerModal). The DataTable multi-select props are also generic enough to be reused by any future bulk-action surface without further modification.
