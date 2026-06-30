---
phase: 25
plan: "03"
subsystem: frontend
tags: [react, tag-management, merge, polling, tailwind, vite]
dependency_graph:
  requires: ["25-02"]
  provides: [tag-management-widget, merge-progress-poll]
  affects: [frontend/vite.config.ts, frontend/src/entrypoints/]
tech_stack:
  added: []
  patterns:
    - Vite-per-entrypoint widget (audit-log clone)
    - 2s HTTP poll hook (useNotifications clone)
    - Two-step pick/confirm merge modal (MergeModal clone)
    - Inline rename with server-error surfacing
    - DataTable<OrgCanonicalTagRow> reuse
key_files:
  created:
    - frontend/src/widgets/tag-management/types.ts
    - frontend/src/widgets/tag-management/api.ts
    - frontend/src/widgets/tag-management/PolarityBadge.tsx
    - frontend/src/widgets/tag-management/RenameInput.tsx
    - frontend/src/widgets/tag-management/TagActionsMenu.tsx
    - frontend/src/widgets/tag-management/TagTable.tsx
    - frontend/src/widgets/tag-management/useTagList.ts
    - frontend/src/widgets/tag-management/TagMergeModal.tsx
    - frontend/src/widgets/tag-management/useMergeProgress.ts
    - frontend/src/widgets/tag-management/MergeProgressBanner.tsx
    - frontend/src/widgets/tag-management/TagManagementWidget.tsx
    - frontend/src/entrypoints/tag-management.tsx
  modified:
    - frontend/vite.config.ts
decisions:
  - "emitToast uses {kind, title, msg} not {kind, title, body} — matched actual lib/toast.ts signature"
  - "TagManagementWidget uses local useState for optimistic rename rows rather than a hook extension"
  - "useMergeProgress tracks dismissed state locally; FAILED jobs are dismissed via API so they don't reappear"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-16"
  tasks_completed: 3
  tasks_total: 3
  files_created: 12
  files_modified: 1
---

# Phase 25 Plan 03: Tag Management Widget Summary

Tag management UI with sortable/paginated table, inline rename, searchable merge modal, and 2s HTTP-polled progress banner — mounted at `#tag-management-root`.

## What Was Built

### Task 1: types + api + PolarityBadge + entrypoint + vite entry (commit d085b91)

- `types.ts`: `PolarityType`, `OrgCanonicalTagRow`, `TagMergeJobRow`, `FetchTagsParams`, `PaginatedTagResponse`
- `api.ts`: `fetchTags`, `renameTag`, `startMerge`, `fetchActiveJob`, `dismissMergeJob` against 25-02 endpoints; `ApiError` class with status + data for 400/409 detection
- `PolarityBadge.tsx`: BADGE map → always_positive (green-tint), always_negative (red-tint), mixed (amber-tint) with text labels for accessibility
- `tag-management.tsx` entrypoint: clones audit-log pattern (`#tag-management-root`, `dataset.mounted`, `turbo:load`)
- `vite.config.ts`: `"tag-management"` entry added after `"audit-log"`

### Task 2: TagTable + useTagList + RenameInput + TagActionsMenu (commit 76ebc21)

- `useTagList.ts`: ordering/page/pageSize state, `toggleOrdering` for column header toggling, `refetch`, `hasPrev`/`hasNext`/`totalPages`
- `RenameInput.tsx`: inline input with `aria-label="Rename tag"`, Enter/Escape keyboard handling, server error mapping (400 duplicate → "A tag with that name already exists. Use Merge to combine tags.", generic → "Could not rename. Please try again."), `role="alert"` error paragraph
- `TagActionsMenu.tsx`: `MoreHorizontal` trigger with `aria-label="Tag actions"`, dropdown with Rename + Merge into… actions, click-outside dismiss
- `TagTable.tsx`: `DataTable<OrgCanonicalTagRow>` with 5 columns (label/polarity/review_count/first_seen/actions), `SortHeader` with `aria-sort`, skeleton, empty state, error state with "Reload Tags" CTA

### Task 3: TagMergeModal + useMergeProgress + MergeProgressBanner + TagManagementWidget (commit 7fea4e1)

- `TagMergeModal.tsx`: two-step pick/confirm state machine cloned from MergeModal; step 1 fetches `page_size=200` tags, client-side search filter, radio picker with selected highlight; step 2 AlertTriangle confirm with "Re-map N reviews..." text; 409-conflict and generic error mapping; `dismissible={!submitting}`
- `useMergeProgress.ts`: clones `useNotifications` pattern; `fetchJob` via `fetchActiveJob`; `setInterval(2_000)` while PENDING/IN_PROGRESS, clears on SUCCESS/FAILED; local `dismissed` state for in-progress; PATCH dismiss for FAILED; `kickoff()` for immediate poll start
- `MergeProgressBanner.tsx`: `role="status" aria-live="polite"` in-progress banner (Loader2, progressbar with `aria-valuenow`, indeterminate fallback); PENDING "Queued — waiting to start"; `role="alert"` failure banner with dismiss → PATCH; SUCCESS auto-dismisses and calls `emitToast`
- `TagManagementWidget.tsx`: root shell (space-y-4, h1 "Tags", border card + pagination footer); composes all components; `localRows` optimistic state for rename; `handleMergeComplete` triggers refetch

## Decisions Made

- `emitToast` takes `{kind, title, msg}` (not `body`) — matched the actual `lib/toast.ts` signature
- Optimistic rename uses a `localRows` `useState` in the widget rather than a hook extension pattern, cleared on next `refetch()`
- FAILED job dismissal calls `dismissMergeJob(id)` via API (durable); PENDING/IN_PROGRESS dismiss is local session-only
- `useMergeProgress` stops the interval when `job?.status === "PENDING" || "IN_PROGRESS"` evaluates false, relying on `job?.status` as the `useEffect` dependency

## Deviations from Plan

None — plan executed exactly as written with one minor adaptation: `emitToast` `body` parameter name corrected to `msg` per the actual API (Rule 1 inline fix during implementation, no behavior change).

## Known Stubs

None — all data is fetched from the 25-02 API endpoints at runtime. No hardcoded empty values flow to UI rendering.

## Threat Flags

None beyond what's documented in the plan's threat model. The grep gate confirmed zero WebSocket usage in the tag-management widget directory.

## Self-Check: PASSED

Files exist:
- `frontend/src/widgets/tag-management/TagManagementWidget.tsx` ✓
- `frontend/src/widgets/tag-management/useMergeProgress.ts` ✓ (contains `setInterval`)
- `frontend/src/entrypoints/tag-management.tsx` ✓ (contains `tag-management-root`)

Commits exist:
- d085b91 feat(25-03): types + api + PolarityBadge + entrypoint + vite entry ✓
- 76ebc21 feat(25-03): TagTable + useTagList + RenameInput + TagActionsMenu ✓
- 7fea4e1 feat(25-03): TagMergeModal + useMergeProgress + MergeProgressBanner + TagManagementWidget ✓

Build: `npm run build` succeeded ✓
TypeScript: `npx tsc --noEmit` clean ✓
WebSocket grep: no matches in tag-management/ ✓
