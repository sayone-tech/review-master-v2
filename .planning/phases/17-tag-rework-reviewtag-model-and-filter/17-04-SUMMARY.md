---
phase: 17-tag-rework-reviewtag-model-and-filter
plan: 04
status: complete
requirements:
  - TAG-03
key_files:
  modified:
    - frontend/src/widgets/review-management/types.ts
    - frontend/src/widgets/review-management/api.ts
    - frontend/src/widgets/review-management/ReviewFilters.tsx
    - frontend/src/widgets/review-management/ReviewTable.tsx
    - frontend/src/widgets/review-management/ReviewManagementWidget.tsx
---

# Plan 17-04 Summary — Frontend Tags Filter

## What was built

Delivered the user-facing half of TAG-03: a 5th filter column (Tags multi-select dropdown with search), clickable tag chips on review rows, and full wiring through the review management widget. UI matches `17-UI-SPEC.md`.

## Commits

- `d853879` feat(17-04): add TagOption type, fetchTagList API, and tags query serialisation
- `a3cb7e7` feat(17-04): add TagsFilter dropdown and clickable tag chips
- `35ace9e` feat(17-04): wire ReviewManagementWidget — fetch tags, chip click, applyFilters

## Task 1 — Types and API client

- `types.ts`: added `tags?: string[]` to `ReviewFilterParams`; added `TagOption { label: string; count: number }`.
- `api.ts`: added `fetchTagList(shopId?)` calling `/api/v1/reviews/tags/` (returns `TagOption[]`). `buildQs` serialises `tags` as comma-joined string.

## Task 2 — Filter dropdown + chip buttons

- `ReviewFilters.tsx`:
  - `DraftFilters.tags?: string[]`, `availableTags?: TagOption[]` prop.
  - Filter grid expanded to 5 columns: `minmax(0,1.6fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)` (Search, Store, Rating, Sentiment, **Tags**).
  - New `TagsFilter` custom dropdown component — `role="combobox" + aria-haspopup="listbox" + aria-multiselectable`, trigger shows "Any tag" / label / "{N} tags" with yellow count badge, loading state when `availableTags === undefined`. Panel: search input (client-side filter, no API call on keystroke), max-h-60 scroll, checkmark indicator + count, hover/selected `bg-line-soft`, empty states "No tags yet" / "No tags match \"{query}\"".
  - Keyboard: Enter/Space toggle open, ArrowUp/Down navigate options, Enter on option toggles, Escape/Tab close.
  - `hasActiveFilters` and `handleReset` updated for the tags slice.
- `ReviewTable.tsx`:
  - `onTagClick?: (label: string) => void` prop added.
  - Tag chips converted from `<span>` to `<button type="button">` with `onClick` calling `e.stopPropagation()` then `onTagClick?.(tag.label)`, `cursor-pointer hover:opacity-80 transition-opacity focus-visible:ring-1 focus-visible:ring-ink focus-visible:ring-offset-1 focus-visible:outline-none`, `aria-label="Filter by tag: {label}"`. `TAG_STYLES` and chip layout preserved.

## Task 3 — Widget wiring

- `ReviewManagementWidget.tsx`:
  - Imports `fetchTagList` from `./api`, `TagOption` from `./types`.
  - `availableTags` state (`TagOption[] | undefined`). `useEffect` fetches tag list on mount and when `filters.shop` changes; on error sets `[]`.
  - `handleTagClick(label)`: pulls `filters.tags ?? []`, toggles `label`, calls `applyFilters({ ...filters, tags: newTags.length ? newTags : undefined })` — bypasses the Apply-button draft (Pitfall 6).
  - `<ReviewFilters>` receives `availableTags`; `onApply` mapping now includes `tags: draft.tags?.length ? draft.tags : undefined`.
  - `<ReviewTable>` receives `onTagClick={handleTagClick}`.
  - Stats `useEffect` dep array gains `filters.tags` so the stat cards refresh when tag filter changes.

## Verification

- `npx tsc --noEmit` from `frontend/`: clean (zero errors).
- All five `files_modified` paths touched per the plan.
- `key_links` satisfied:
  - `Widget → ReviewTable` via `onTagClick={handleTagClick}` ✓
  - `Widget → ReviewFilters` via `availableTags` prop ✓
  - `api.ts → /api/v1/reviews/tags/` via `fetchTagList` ✓

## Must-haves check

| Must-have | Status |
|---|---|
| Tags multi-select dropdown with search in filter panel | ✓ |
| Lists all distinct tags for the org (shop-scoped when shop filter active) | ✓ (via `fetchTagList(filters.shop)`) |
| Apply sends `?tags=A,B` to the review list API | ✓ (buildQs join + onApply mapping) |
| Tag chips are clickable buttons that add/toggle the label immediately | ✓ (handleTagClick + applyFilters) |
| Trigger shows "Any tag" / label / "{N} tags" with yellow count badge | ✓ |
| Reset clears tags along with all other filters | ✓ |
| `hasActiveFilters` is true when at least one tag is selected | ✓ |

## Deviations

- **Resume after stalls.** The executor agent stalled twice (stream idle timeout) — once mid-plan (after Tasks 1+2 commits) and again at the resumption attempt for Task 3. The two completed commits (d853879, a3cb7e7) survived intact in the worktree. The orchestrator authored and committed Task 3 directly (`35ace9e`) following the plan's specification verbatim, then wrote this SUMMARY.md. No behavioural deviation from the plan; only the agent execution path differed.
- The user approved the human-verify checkpoint (between Tasks 2 and 3) on the strength of the staged commits and the visual/ARIA description; no console errors were reported during inspection.

## Hands off to

- Phase 17 verification — must-haves and TAG-03 requirement traceability.
- Future: stats endpoint may want to accept the tags filter parameter too (currently the dep array triggers refetch but the backend `fetchReviewStats` signature is unchanged — verify whether the stats endpoint honours `tags` server-side, otherwise the cards will not reflect tag-scoped counts).
