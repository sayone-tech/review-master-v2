---
phase: 17
slug: tag-rework-reviewtag-model-and-filter
audited: 2026-05-24
baseline: 17-UI-SPEC.md
screenshots: not captured (no dev server on port 3000/8080; port 5173 returned 302)
---

# Phase 17 — UI Review

**Audited:** 2026-05-24
**Baseline:** 17-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured — no accessible dev server (3000/8080 offline; 5173 redirected)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Missing "Could not load tags" error state; "No tags match" uses straight quotes vs spec's curly quotes; aria-label format diverges from spec |
| 2. Visuals | 3/4 | Badge and trigger visually correct; chip hover opacity present; no aria-pressed on chip buttons |
| 3. Color | 2/4 | Pagination bar uses `bg-[#FBFBFB]` (off-spec); empty-state text uses `text-muted` where spec requires `text-faint` |
| 4. Typography | 2/4 | `font-medium` used pervasively across all new components — spec prohibits it (allows only font-normal/font-semibold) |
| 5. Spacing | 2/4 | Filter grid gap is 14px (not 16px); panel padding is p-3.5 (14px, not 12px); chip padding px-1.5 py-0.5 (6px/2px) violates 4px grid; mb-[18px] is off-grid |
| 6. Experience Design | 2/4 | `hasAnyFilter` in ReviewManagementWidget omits `filters.tags` — tags-only filter shows wrong empty state; no "Could not load tags" error rendered to user |

**Overall: 13/24**

---

## Top 3 Priority Fixes

1. **`hasAnyFilter` omits `filters.tags` in ReviewManagementWidget.tsx** — When a user filters by tag only (no other filter active), zero results display the "No connected shops" or "No reviews yet" empty state instead of "No reviews match your filters." + "Clear filters" CTA. This is a flow-breaking interaction bug. Fix: add `|| (filters.tags && filters.tags.length > 0)` to the `hasAnyFilter` boolean at line 113 of `ReviewManagementWidget.tsx`.

2. **`font-medium` used throughout — spec prohibits it** — The design system allows only `font-normal` (400) and `font-semibold` (600). `font-medium` (500) appears on: `selectCls` (line 26, ReviewFilters), TagsFilter trigger (line 184), search input (line 331), Apply button (line 535), FilterLabel component (line 48), tag chip button (ReviewTable line 215), Shop column (ReviewTable line 258). Each instance is a typography contract violation. Replace all `font-medium` with `font-normal` on body text and `font-semibold` on labels/CTAs per each element's role.

3. **Filter grid gap is 14px, panel padding is 14px, chip padding is off-grid** — The spec declares `gap-4` (16px) for the filter grid and `p-3` (12px) for the filter panel. The implementation uses `gap: 14` inline (line 320) and `p-3.5` (14px, line 313). Tag chips use `px-1.5 py-0.5` (6px/2px, ReviewTable line 215) vs the spec's `px-2 py-1` (8px/4px). 6px and 2px are off the 4px grid. Fix: change `gap: 14` → `gap: 16` (or `gap-4` in Tailwind), `p-3.5` → `p-3`, `px-1.5 py-0.5` → `px-2 py-1`.

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**BLOCKER — Missing "Could not load tags" error state**
The spec declares: "Could not load tags. Refresh to retry." as the copy when the tag list API fails. `ReviewManagementWidget.tsx` (line 104–106) catches the error and sets `availableTags = []`. `TagsFilter` (ReviewFilters.tsx line 224–228) treats an empty `availableTags` array as "No tags yet" — it cannot distinguish a network failure from an org that genuinely has no tags yet. The user sees "No tags yet" when the API is down. The error copy is completely absent from the rendered UI.

**WARNING — Straight quotes in empty search state**
Spec copy: `No tags match "{query}"` (typographic curly quotes around query).
Implementation (ReviewFilters.tsx line 228): `` `No tags match "${query}"` `` (straight double-quotes).
Minor but diverges from the contract.

**WARNING — aria-label format diverges from spec**
Spec: `aria-label="Filter by {Label}"` on chip buttons.
Implementation (ReviewTable.tsx line 217): `aria-label={\`Filter by tag: ${tag.label}\`}`.
The additional "tag: " prefix is not specified and adds inconsistency with screen reader announcements.

**PASS — All other specified copy strings are present**
- "Any tag" trigger (line 121) ✓
- "{Label}" for 1 selected (line 122) ✓
- "{N} tags" for 2+ selected (line 123) ✓
- "Search tags…" placeholder (line 219) ✓
- "No tags yet" (line 227) ✓
- Filter section label "Tags" (line 171) ✓
- Apply / Reset labels present ✓

---

### Pillar 2: Visuals (3/4)

**PASS — Badge renders correctly for >=1 selection**
`selected.length > 0` condition (ReviewFilters.tsx line 190) triggers the yellow count badge with correct `w-4 h-4 bg-yellow text-black text-[10px] font-semibold rounded-full` classes. Badge is `aria-hidden="true"`. Trigger text correctly shows label (1 selected) or "{N} tags" (2+).

**PASS — Dropdown panel visual structure matches spec**
`absolute z-50 mt-1 left-0 right-0 bg-white border border-line rounded-[10px] shadow-md max-h-60 overflow-y-auto py-1` (line 207) matches the spec's positioning, border, rounding, and scroll constraints.

**PASS — Chip hover and focus styles present**
`hover:opacity-80 transition-opacity` and `focus-visible:ring-1 focus-visible:ring-ink focus-visible:ring-offset-1 focus-visible:outline-none` applied to chip buttons (ReviewTable.tsx line 215).

**WARNING — No aria-pressed on chip buttons**
Spec requires `aria-pressed={isActive}` on each chip button where `isActive = activeTags.includes(tag.label)`. The implementation has no `aria-pressed` attribute (ReviewTable.tsx line 208–219). Without it, screen reader users cannot tell whether a tag chip is currently active in the filter.

**WARNING — Selected state styling combined with hover state in option list**
The option row applies `bg-line-soft` when either selected OR keyboard-active (line 244: `isSelected || isActive ? "bg-line-soft" : "hover:bg-line-soft"`). This matches the spec's intent for persistent selected highlight but the hover class on unselected rows and the persistent class on selected rows produce the same visual, which is correct. Minor issue: keyboard-focused unselected rows show same bg as selected rows — no differentiation.

---

### Pillar 3: Color (2/4)

**WARNING — Pagination bar background off-spec**
`ReviewManagementWidget.tsx` line 202: `bg-[#FBFBFB]`. The design system specifies `#FAFAFA` (`bg`) as the dominant background token. `#FBFBFB` is a one-step-off variant not in the token set. Change to `bg-[#FAFAFA]` or use the `bg` semantic token if it maps correctly.

**WARNING — Empty-state text in TagsFilter uses wrong semantic token**
ReviewFilters.tsx line 225: `text-muted` on the "No tags yet" / "No tags match" empty state text. The spec's color table specifies `#A1A1AA (faint)` for "No-results text". The `text-faint` semantic token should be used here, not `text-muted`. Both are gray but they target different hierarchy levels — `text-faint` is lighter, matching the spec's `#A1A1AA`.

**PASS — Hardcoded colors in ReviewFilters are pre-existing and sanctioned**
`#D4D4D8` for hover border and `rgba(10,10,10,0.05)` for focus ring (lines 26, 184, 327) are pre-existing across the codebase and explicitly listed in the spec's color table. These are not new violations introduced in Phase 17.

**PASS — Accent yellow usage is correctly scoped**
`bg-yellow` appears only on: Apply button (line 535) and count badge (line 192). Both are explicitly declared accent usage per the spec. No accent creep onto decorative elements.

**PASS — TAG_STYLES polarity colors match spec exactly**
ReviewTable.tsx lines 52–55: positive `#DCFCE7/#15803D`, neutral `#F4F4F5/#52525B`, negative `#FEE2E2/#DC2626`. All three match the spec's locked values.

---

### Pillar 4: Typography (2/4)

**BLOCKER — font-medium used throughout, spec prohibits it**

The design system contract allows only `font-normal` (400) and `font-semibold` (600). `font-medium` (500) violations:

| File | Line | Element | Should Be |
|------|------|---------|-----------|
| ReviewFilters.tsx | 26 | `selectCls` — all native selects | `font-normal` |
| ReviewFilters.tsx | 48 | `FilterLabel` component — all section headings | `font-semibold` |
| ReviewFilters.tsx | 184 | TagsFilter trigger button text | `font-normal` |
| ReviewFilters.tsx | 331 | Search input text | `font-normal` |
| ReviewFilters.tsx | 454 | Date range separator "—" | `font-normal` |
| ReviewFilters.tsx | 535 | Apply button | `font-semibold` |
| ReviewTable.tsx | 215 | Tag chip button text | `font-normal` |
| ReviewTable.tsx | 258 | Shop name in shop column | `font-semibold` |

FilterLabel (line 48) is used for ALL filter section headings. The spec designates filter section headings as `font-semibold` (600). `font-medium` on the FilterLabel means every section heading in the filter panel is rendered at the wrong weight.

**WARNING — font-bold appears in ReviewTable (line 120 — avatar initials)**
`font-bold` is not in the two-weight spec. This is a pre-existing pattern, not introduced by Phase 17, but it contributes to weight sprawl. Noted, not scored separately.

**PASS — Font sizes used in new components**
New tag-related size classes: `text-[10px]` (badge), `text-[11px]` (count, chip), `text-[12px]` (empty state), `text-[13px]` (search input, option label), `text-[13.5px]` (reviewer name), `text-[14px]` (body). All within the four declared roles (body 14px, label 13.5px, micro 11px, filter heading 11.5px). The `text-[12px]` on the empty state text is a minor additional size not declared in the spec's four-role table.

---

### Pillar 5: Spacing (2/4)

**BLOCKER — Multiple off-grid spacing values introduced**

The spec requires a strict 4px base grid. Off-grid violations in Phase 17 code:

| File | Line | Class | Computed Value | Issue |
|------|------|-------|----------------|-------|
| ReviewFilters.tsx | 313 | `p-3.5` | 14px | Off-grid (should be `p-3` = 12px per spec) |
| ReviewFilters.tsx | 313 | `mb-[18px]` | 18px | Off-grid (no 18px in 4px scale) |
| ReviewFilters.tsx | 320 | `gap: 14` inline | 14px | Off-grid (spec declares `gap-4` = 16px) |
| ReviewFilters.tsx | 435 | `gap: 14` inline | 14px | Off-grid (Row 2 same violation) |
| ReviewTable.tsx | 215 | `px-1.5 py-0.5` | 6px / 2px | Off-grid (spec: `px-2 py-1` = 8px / 4px) |

The filter panel padding (`p-3.5`), the filter grid column gap (`gap: 14`), and the chip padding (`px-1.5 py-0.5`) are the most impactful. The chip padding in particular makes chips visually smaller than the spec (tighter than `px-2 py-1`), and 2px vertical padding is not on any 4px-grid step.

**WARNING — gap-1.5 (6px) used pervasively for label-to-control gaps**
`gap-1.5` (6px, off-grid) appears on every filter column's `flex flex-col gap-1.5` (lines 170, 325, 341, 367, 395, 440, 469, 495). The spec declares `xs = 4px` for the smallest step. 6px is between the xs (4px) and sm (8px) steps. All label-to-control gaps should be `gap-1` (4px) or `gap-2` (8px).

**PASS — Dropdown internals spacing matches spec**
Search input: `px-3 py-2` (12px/8px) per spec ✓. Option rows: `px-3 py-2` ✓. Panel: `py-1` ✓. Chip gap in table row: `gap-1` (4px) ✓.

---

### Pillar 6: Experience Design (2/4)

**BLOCKER — hasAnyFilter omits filters.tags; wrong empty state shown for tags-only filter**
`ReviewManagementWidget.tsx` lines 113–122: `hasAnyFilter` checks search, shop, rating, sentiment, is_replied, has_comment, from_date, to_date — but NOT `filters.tags`. When a user applies only a tag filter and gets zero results, `hasAnyFilter` is `false`. The code falls through to `EmptyStateB` ("No reviews yet" or similar) instead of `EmptyStateC` ("No reviews match your filters." + "Clear filters" CTA). This is a user task completion failure: the user cannot recover from a tags-only filter producing zero results without knowing to manually clear the tag filter.

Fix (ReviewManagementWidget.tsx line 121): add `|| (filters.tags && filters.tags.length > 0)` to the `hasAnyFilter` condition.

**BLOCKER — Error state for failed tag list fetch is unrendered**
`ReviewManagementWidget.tsx` (line 104–106): on fetch error, `setAvailableTags([])`. `TagsFilter` (ReviewFilters.tsx line 224–228) cannot distinguish an empty array from a successful "no tags" response. The spec-declared error copy "Could not load tags. Refresh to retry." is not displayed anywhere. The trigger goes to opacity-50 disabled state while loading (`loading = availableTags === undefined`) but once the error resolves to `[]`, the trigger re-enables and shows the empty dropdown with "No tags yet". The user does not know a fetch failure occurred.

Fix: introduce a separate error state (e.g. `availableTags` remains `undefined` after error, or add an `availableTagsError: boolean` state). Render the spec error copy inside the dropdown panel when error is set.

**PASS — Loading state correctly disables the trigger**
`const loading = availableTags === undefined` (line 89). Trigger button gets `disabled={loading}` and `opacity-50 cursor-not-allowed pointer-events-none` (line 185). Matches spec exactly.

**PASS — Chip click applies filter immediately (bypasses draft)**
`handleTagClick` (ReviewManagementWidget.tsx line 144) calls `applyFilters` directly, not `setDraft`. This implements the spec's "direct apply" interaction model for chip clicks correctly.

**PASS — Stats cards re-fetch when tags change**
`filters.tags` is in the `useEffect` dep array (line 97). Stats refresh on tag filter change.

**PASS — Reset clears tags**
`handleReset` (ReviewFilters.tsx line 297) sets `tags: []`. `onApply` mapping sends `tags: draft.tags?.length ? draft.tags : undefined` — empty array becomes `undefined`. ✓

**WARNING — No aria-pressed on chip buttons**
Covered in Pillar 2. Re-noted here as an experience design gap for keyboard/screen reader users who cannot determine whether a tag chip is currently active as a filter.

---

## Registry Safety

Registry audit: shadcn not initialized (`components.json` absent). No third-party registries declared in UI-SPEC.md. Registry audit skipped — not applicable.

---

## Files Audited

- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/ReviewFilters.tsx`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/ReviewTable.tsx`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/ReviewManagementWidget.tsx`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/api.ts`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/review-management/types.ts`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/17-tag-rework-reviewtag-model-and-filter/17-UI-SPEC.md`
- `/Users/renjith/Documents/Accounts/review-master/.planning/phases/17-tag-rework-reviewtag-model-and-filter/17-01-SUMMARY.md` through `17-04-SUMMARY.md`
