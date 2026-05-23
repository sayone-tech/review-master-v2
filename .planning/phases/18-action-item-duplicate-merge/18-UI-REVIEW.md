---
phase: 18
slug: action-item-duplicate-merge
audited: 2026-05-24
baseline: 18-UI-SPEC.md (approved design contract)
screenshots: not captured (no dev server on ports 3000/8080; port 5173 returned 302)
---

# Phase 18 — UI Review

**Audited:** 2026-05-24
**Baseline:** 18-UI-SPEC.md design contract
**Screenshots:** Not captured (dev server not available on standard ports)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | 4 of 5 specified backend-driven error toasts are absent; detail-flow merge confirmation uses hardcoded "2 items" not the dynamic N |
| 2. Visuals | 3/4 | DuplicatePickerModal result rows omit shop_name from meta ("Shop" not "Shop · {name}"); confirm step layout is correct |
| 3. Color | 3/4 | Detail-flow ConfirmModal (amber variant) renders a red confirm button, diverging from the spec's yellow primary; `font-medium` used in DuplicatePickerModal footer buttons |
| 4. Typography | 2/4 | DuplicatePickerModal footer buttons use off-spec `text-[13.5px] font-medium` (spec: `text-[14px] font-normal`/`font-semibold`); `font-medium` appears in multiple components |
| 5. Spacing | 2/4 | DuplicatePickerModal footer buttons use `px-3.5 py-2` (off-spec 14px/10px → not 4px grid); results list missing `space-y-1`; pre-existing `gap-1.5` / `mr-1.5` present in widget |
| 6. Experience Design | 3/4 | ConfirmModal (detail flow) does not set `dismissible={false}` during merge in-flight; `aria-checked="mixed"` missing on header checkbox per spec |

**Overall: 16/24**

---

## Top 3 Priority Fixes

1. **DuplicatePickerModal footer buttons violate both the spacing scale and typography contract** — Users see a visually inconsistent Cancel and "Select as primary" button at `px-3.5 text-[13.5px] font-medium` while every other modal button uses `px-4 text-[14px] font-normal/semibold`. Fix: change `DuplicatePickerModal.tsx` lines 101 and 109 to `px-4 py-2 text-[14px]` with `font-normal` on Cancel and `font-semibold` on primary, matching the MergeModal footer exactly.

2. **Detail-flow ConfirmModal confirm button is red, not yellow** — The spec explicitly states the "Merge items" primary CTA must use `bg-yellow text-black` across both flows. But `ConfirmModal` with `variant="amber"` maps to `CONFIRM_BTN_CLASS.amber = "bg-red text-white"`. This breaks the 60/30/10 accent rule (red is reserved for destructive-delete; merge is a reorganisation, not deletion). Fix: either pass `variant="blue"` (which maps to yellow button) or create a dedicated `variant="amber-yellow"` that uses the yellow button; update `ActionItemModal.tsx` line 526.

3. **DuplicatePickerModal result row meta is truncated** — The spec specifies `"Shop · {shop_name}"` for SHOP-scope rows in the picker results, giving the user the specific shop name for disambiguation. The implementation renders only `"Shop"` (line 168). This degrades usefulness when an org has multiple shops with similarly titled action items. Fix: change line 168 to `{item.scope === "SHOP" ? (item.shop_name ? \`Shop · \${item.shop_name}\` : "Shop") : "Brand"}`.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**Passing strings (verified against spec):**
- Toolbar: `"{N} items selected"`, `"Clear selection"`, `"Merge duplicates"` — exact match.
- MergeModal title: `"Merge action items"` — exact match.
- MergeModal subtitle: `"{selectedItems.length} items selected"` — correct dynamic value.
- MergeModal section header: `"Pick the primary item"` — exact match.
- MergeModal instruction: `"The primary item will remain active. All others will be merged into it."` — exact match.
- MergeModal confirm title: `"Confirm merge"` — exact match.
- MergeModal buttons: `"Back"`, `"Cancel"`, `"Merge items"`, `"Merging…"` — exact match.
- Success toasts: `"Items merged successfully"` (list flow) and `"Marked as duplicate"` (detail flow) — exact match.
- Error toast: `"Could not merge items. Please try again."` — exact match.
- DuplicatePickerModal title: `"Mark as duplicate of"` — exact match.
- DuplicatePickerModal placeholder: `"Search action items…"` — exact match.
- DuplicatePickerModal empty: `"No matching items found."` — exact match.
- DuplicatePickerModal CTA: `"Select as primary"` — exact match.
- "Also reported in" section header — exact match.
- "Mark as duplicate of…" button — exact match.

**WARNING — Detail-flow confirmation message hardcodes "2":**
`ActionItemModal.tsx` line 528: `"Merge 2 items into "${pickedForMerge?.title ?? ""}"? This cannot be undone."` — the spec calls for `"Merge {N} items into '{primary title}'? This cannot be undone."` The detail flow always merges exactly 2 items, so this is functionally correct today. However, it is a copy literal departure from the spec and would be wrong if the detail flow were extended to support 3+ items. Classification: **WARNING** — not a user-visible error now, but a contract violation.

**WARNING — Spec-listed backend-error toasts not implemented in frontend:**
The copywriting contract specifies four distinct error toasts for API error cases:
- `"Items must have the same scope to merge."` (same-scope violation)
- `"Only AI-extracted items can be merged."` (manual-source violation)
Both the list-flow merge (`MergeModal.tsx` line 43–46) and detail-flow merge (`ActionItemModal.tsx` line 449–452) always emit the generic `"Could not merge items. Please try again."` regardless of the HTTP 400 error body. The backend returns distinct `ValidationError` messages for D-05 and D-06 failures, but the frontend does not parse or surface them. Users who select mixed-scope items through a hypothetical future UI path, or who encounter validation errors, receive no actionable guidance. Classification: **WARNING** — does not block the primary happy path, but degrades error UX.

**PASS — MergeModal confirm message uses typographic quotes (`&lsquo;`/`&rsquo;`):**
The spec uses straight single quotes. The implementation uses HTML entity curly quotes, which are visually superior. Not scored as a failure.

---

### Pillar 2: Visuals (3/4)

**Passing:**
- `+N` duplicate badge (`bg-amber-tint text-amber text-[11px] font-semibold`) correctly uses amber (not yellow) to distinguish from interactive elements — satisfies spec.
- Badge has `aria-label` for screen readers — correct.
- MergeModal confirm step: `AlertTriangle` icon in `w-11 h-11 rounded-[12px] bg-amber-tint` block — matches spec exactly.
- Radio list selected-row highlight: `border-yellow bg-yellow-tint` — exact spec match.
- "Also reported in" section separator and row layout — matches spec.
- Merge toolbar appears conditionally (`isOrgAdmin && selectedIds.size >= 2`) — correct visibility gate.

**WARNING — DuplicatePickerModal result row meta is degraded:**
`DuplicatePickerModal.tsx` line 168: `{item.scope === "SHOP" ? "Shop" : "Brand"}` — the spec requires `"Shop · {shop_name}"` to give contextual disambiguation. When an org has five shops each with an action item titled "Fix parking," the picker shows five undifferentiated rows all labeled "Shop." Visual hierarchy fails at the critical disambiguation point. Classification: **WARNING** — degrades the primary picker UX.

**WARNING — DuplicatePickerModal results list missing `space-y-1`:**
`DuplicatePickerModal.tsx` line 138: `"mt-2 max-h-[280px] overflow-y-auto border border-line rounded-md"` — spec requires `space-y-1` on the list container. The rows use `border-b border-line-soft` as separators instead; the visual difference is minor but the spec was not followed. Classification: **WARNING** (minor).

**PASS — Checkbox disabled states:**
MANUAL rows have `opacity-40 cursor-not-allowed`, AI rows are interactive — correct.

---

### Pillar 3: Color (3/4)

**Passing:**
- Yellow (`#FACC15`) is correctly reserved for: primary CTAs (Merge toolbar, MergeModal buttons), checkbox/radio checked state (`accent-[#FACC15]`), and focus rings (`focus:ring-yellow`).
- Amber (`#FEF3C7` / `#D97706`) used for `+N` badge and confirm step icon — correct.
- Yellow-tint (`#FEFCE8`) used for selected radio rows and selected picker rows — correct.
- `bg-[#FAFAFA]` used for table header background — matches spec note (spec notes `#FBFBFB` as pre-existing for table headers; actual impl uses `#FAFAFA` in DataTable headers and `#FBFBFB` in pagination row — this split is consistent with the existing codebase and is a pre-existing pattern, not a phase 18 introduction).
- Red is absent from merge CTAs in the list flow — correct.

**BLOCKER — Detail-flow "Merge items" confirm button renders red, not yellow:**
`ConfirmModal.tsx` line 20: `amber: "bg-red text-white border-transparent hover:bg-[#B91C1C]"`. ActionItemModal line 526 passes `variant="amber"`, causing the final merge confirmation button to render with a red destructive-action style. The spec explicitly states: "This is consistent with the existing ConfirmModal — the amber variant already maps to the red confirm button class" — but the UI-SPEC also states the confirm button must be `bg-yellow text-black font-semibold`. These two statements are contradictory in the spec. The net visual result is that the detail-flow merge confirmation looks like a delete operation (red button), breaking the non-destructive merge mental model. The list-flow uses a yellow button. This creates inconsistency between the two entry points. Classification: **BLOCKER** — color signals destruction when the operation is reorganisation.

**WARNING — `font-medium` used in DuplicatePickerModal footer:**
DuplicatePickerModal.tsx lines 101 and 109: `font-medium`. The spec prohibits weight 500 — only 400 (normal) and 600 (semibold) are permitted. This is a typography violation that also appears here under color since it affects the semantic token mapping of button weight. Classification: **WARNING**.

---

### Pillar 4: Typography (2/4)

**Permitted sizes in use (phase 18 new components):**
- `text-[11px]` — badge micro text — permitted per spec.
- `text-[12px]` — section headers, meta text — permitted.
- `text-[14px]` — body and labels — permitted.
- `text-[18px]` — modal title — permitted.

**These are within the 6-size inventory declared in the spec.**

**BLOCKER — `font-medium` (weight 500) used in multiple phase 18 elements:**
The spec prohibits weight 500 entirely. Violations found:

| File | Line | Usage |
|------|------|-------|
| `DuplicatePickerModal.tsx` | 101 | Cancel button: `text-[13.5px] font-medium` |
| `DuplicatePickerModal.tsx` | 109 | "Select as primary" button: `text-[13.5px] font-semibold` (weight ok but size off-spec) |
| `ActionItemManagementWidget.tsx` | 349, 368, 384 | Pagination prev/next/page buttons: `text-[13px] font-medium` |
| `ActionItemFilters.tsx` | 14, 76, 183, 378 | Filter controls: `font-medium` throughout |

Note: ActionItemFilters.tsx and pagination controls are pre-existing. The DuplicatePickerModal buttons are **new phase 18 code** and introduce `font-medium` directly in violation of the spec. Classification: **BLOCKER** on the DuplicatePickerModal buttons specifically; **WARNING** on pre-existing elements.

**WARNING — `text-[13.5px]` used in DuplicatePickerModal footer:**
`DuplicatePickerModal.tsx` lines 101 and 109: `text-[13.5px]`. This is not in the spec's declared type scale (11, 12, 14, 18px). The DuplicatePickerModal footer buttons are sized differently from the identically-functioned buttons in MergeModal (`text-[14px]`), creating visual inconsistency within the same feature. Classification: **WARNING**.

**PASS — MergeModal typography:**
All MergeModal text uses only `text-[12px]`, `text-[14px]`, `text-[18px]` with weights `font-normal` and `font-semibold` — fully compliant.

**PASS — ActionItemModal new sections:**
The "Also reported in" section uses `text-[12px] font-semibold` for the header and `text-[14px]` / `text-[12px]` for row content — fully compliant.

---

### Pillar 5: Spacing (2/4)

**Pre-existing violations (documented in spec as acceptable exceptions):**
- `py-[11px]` and `py-[14px]` on table header/row cells — spec explicitly permits these.
- `gap-1.5`, `mr-1.5`, `px-3.5` in ActionItemFilters and pagination — pre-existing, not introduced in phase 18.

**NEW phase 18 violations:**

**BLOCKER — DuplicatePickerModal footer buttons use off-spec padding:**
`DuplicatePickerModal.tsx` lines 101 and 109: `px-3.5 py-2`.
- `px-3.5` = 14px — not a multiple of 4px (14 is not on the 4px grid).
- The spec declares this button at `px-4 py-2` (16px / 8px).
- Identical buttons in MergeModal use `px-4 py-2` — same component family, different padding.

**WARNING — DuplicatePickerModal results list missing `space-y-1`:**
`DuplicatePickerModal.tsx` line 138: the results list container lacks `space-y-1`. Spec: `"mt-2 max-h-[280px] overflow-y-auto space-y-1 border border-line rounded-md"`. The omission is minor (rows use `border-b` separators instead) but is a direct spec deviation.

**WARNING — DuplicatePickerModal body adds redundant inner padding:**
`DuplicatePickerModal.tsx` line 118: `<div className="p-4 space-y-3">` inside the Modal component which already adds `px-6 py-5`. This creates `px-10` effective horizontal padding for the picker's content vs. `px-6` for all other modal content. All other modals (MergeModal, AssignModal) do not add the inner `p-4` wrapper and allow the Modal's `px-6 py-5` to set the padding directly. The DuplicatePickerModal is uniquely double-padded horizontally. Classification: **WARNING** — the visual is tight but the extra nesting is non-standard.

**PASS — MergeModal spacing:**
MergeModal body uses `space-y-4` and `gap-3` for radio items — all on the 4px grid. Confirm step uses `gap-4`, `mb-2` — compliant.

---

### Pillar 6: Experience Design (3/4)

**Passing:**
- Loading states: MergeModal "Merging…" text with `aria-busy={saving}` and button disabled — correct.
- Detail-flow loading: `mergingFromDetail` flag shows "Merging…" on ConfirmModal confirm button — correct.
- MergeModal blocks dismiss during save with `dismissible={!saving}` — correct.
- Detail-flow ConfirmModal partially blocks close: `onClose` checks `if (mergingFromDetail) return` — correct guard.
- Error states: Both flows emit error toasts and keep modals open on failure — correct.
- Empty state: "No matching items found." in DuplicatePickerModal — correct.
- Post-merge success: selection cleared, list refetched, modal closed — correct.
- Selection cleared on page/filter change via `useEffect` — correct.
- Two-step modal (pick → confirm) with "Back" returning to pick step with radio preserved — correct.

**WARNING — ConfirmModal (detail flow) does not set `dismissible={false}` during merge:**
`ActionItemModal.tsx` line 519–530: The ConfirmModal does not receive a `dismissible` prop and the `Modal` component defaults `dismissible=true`. During the in-flight merge call, the `onClose` handler checks `mergingFromDetail` and guards the state clear, but the Modal's backdrop-click path and Escape key path both still trigger `onClose` — meaning the ConfirmModal can be closed by pressing Escape or clicking the backdrop while the API call is in-flight. The close handler does guard the state reset, but the modal's visual dismissal still occurs. The MergeModal correctly uses `dismissible={!saving}`. Classification: **WARNING** — could cause user confusion (modal disappears but operation is still running).

**WARNING — Header checkbox missing `aria-checked="mixed"` for indeterminate state:**
`DataTable.tsx` line 99: The header checkbox does not set `aria-checked` attribute. The spec requires `aria-checked={...}` with `"mixed"` for indeterminate state. The `indeterminate` DOM property is set via ref (line 79) — this is correct for visual rendering — but `aria-checked="mixed"` is the ARIA mechanism for screen readers to announce partial selection. Without it, VoiceOver and NVDA announce the header checkbox as "unchecked" when some rows are selected. Classification: **WARNING** — accessibility gap.

**PASS — DuplicatePickerModal debounce and abort cleanup:**
300ms debounce via `clearTimeout` in cleanup function — correct per spec.

**PASS — Row-level checkbox accessibility:**
`aria-label={\`Select ${key}\`}` on each row checkbox — uses the rowKey (item ID as string) not the item title. The spec requires `aria-label={\`Select ${row.title}\`}`. This is a minor departure — the label says "Select 42" rather than "Select Fix parking lot lighting". Classification: **WARNING** (minor, already noted under experience design).

---

## Registry Safety

No third-party registries. `components.json` does not exist (shadcn not initialized). Registry audit: skipped — not applicable.

---

## Files Audited

| File | Status |
|------|--------|
| `frontend/src/widgets/action-items/MergeModal.tsx` | New — fully reviewed |
| `frontend/src/widgets/action-items/DuplicatePickerModal.tsx` | New — fully reviewed |
| `frontend/src/widgets/action-items/ActionItemModal.tsx` | Modified — new sections reviewed |
| `frontend/src/widgets/action-items/ActionItemManagementWidget.tsx` | Modified — toolbar and selection state reviewed |
| `frontend/src/widgets/action-items/ActionItemTable.tsx` | Modified — checkbox column and +N badge reviewed |
| `frontend/src/widgets/data-table/DataTable.tsx` | Modified — checkbox column implementation reviewed |
| `frontend/src/widgets/action-items/types.ts` | Modified — type additions verified against spec |
| `frontend/src/widgets/action-items/api.ts` | Modified — mergeActionItems function verified |
| `frontend/src/widgets/modal/Modal.tsx` | Reference — padding and structure verified |
| `frontend/src/widgets/modal/ConfirmModal.tsx` | Reference — button color classes verified |
| `.planning/phases/18-action-item-duplicate-merge/18-UI-SPEC.md` | Audit baseline |
| `.planning/phases/18-action-item-duplicate-merge/18-CONTEXT.md` | Reference |
| `.planning/phases/18-action-item-duplicate-merge/18-03-SUMMARY.md` | Reference |
| `.planning/phases/18-action-item-duplicate-merge/18-04-SUMMARY.md` | Reference |
