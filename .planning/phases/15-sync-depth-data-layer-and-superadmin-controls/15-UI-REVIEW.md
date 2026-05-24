# Phase 15 — UI Review

**Audited:** 2026-05-24
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md for this phase; design token rules from `<design_system_rules>` in review prompt)
**Screenshots:** Not captured (no dev server — port 5173 returned 302/redirect, not a renderable UI endpoint)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Error fallback copy is generic ("Something went wrong.") but CTAs and labels are specific and conversational |
| 2. Visuals | 3/4 | Toggle layout and dt/dd rows are structurally sound; ViewOrgModal uses raw inline style object instead of Tailwind; ShopDetailsModal has button weight inconsistency |
| 3. Color | 2/4 | Three hardcoded hex clusters in ShopDetailsModal (Region badge, Status pill active, Status pill inactive) bypassing semantic token system |
| 4. Typography | 2/4 | Six distinct pixel sizes in use (4 is the spec max); `font-medium` appears 13 times across the new and modified files — the spec allows only `font-normal` and `font-semibold` |
| 5. Spacing | 2/4 | `mt-0.5` (2px) introduced in new ToggleSwitch.tsx; `mb-0.5`, `gap-1.5`, `px-3.5`, `py-[3px]` are off the 4px base grid across modified files |
| 6. Experience Design | 3/4 | Toggle has correct ARIA role, checked state, and label association; submitting spinner present; empty shop state handled; no keyboard-specific handling needed (button handles space/enter natively) |

**Overall: 15/24**

---

## Top 3 Priority Fixes

1. **`font-medium` on every button in the org and shop modals** — Violates the two-weight constraint (font-normal / font-semibold only). With 13 occurrences across CreateOrgModal, EditOrgModal, ViewOrgModal, and ShopDetailsModal the system is systematically off-spec. Fix: replace `font-medium` with `font-semibold` on all buttons. The Close button in ShopDetailsModal (line 105) already correctly uses `font-semibold` — the other four buttons in that file should match.

2. **Hardcoded hex colors in ShopDetailsModal (lines 121, 134–137)** — Region badge uses `#F3F4F6`/`#374151`; active status pill uses `#F0FDF4`/`#16A34A`; inactive pill uses `#F9FAFB`/`#6B7280`. These bypass the semantic token system and will not respect future brand changes. Fix: map to semantic tokens or introduce named Tailwind custom classes (`bg-status-active`, `text-status-active`) in the Tailwind config. Hardcoding brand-adjacent greens inside a product that could be white-labelled is high risk.

3. **Six distinct arbitrary pixel font sizes across the new and modified files** — The spec caps at four. The six sizes in use are `text-[11px]`, `text-[11.5px]`, `text-[12px]`, `text-[12.5px]`, `text-[13px]`, `text-[13.5px]`. The 0.5px increments (`text-[11.5px]` in ShopDetailsModal dtCls, `text-[12.5px]` on Place ID `<code>`) are not meaningful visual steps and add cognitive noise. Fix: collapse to a four-step scale, e.g. `text-[11px]` (badge), `text-[12px]` (label), `text-[13.5px]` (body), and one larger for headings.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**WARNING — generic error fallback is the established pattern, not a new regression**

The error fallback copy `"Something went wrong. / Please try again. If the problem persists, contact support."` is repeated across CreateOrgModal (lines 91–92), EditOrgModal (lines 83–84), and pre-existing modals. This copy is not specific to the action being performed. While it is not ideal, it is consistent with the project's pre-existing error pattern, not a regression introduced by phase 15.

Phase 15 new copy is specific and correct:
- CTA label: "Create Organisation" (action-specific, not "Submit") — CreateOrgModal line 133
- CTA label: "Save Changes" (not "Save") — EditOrgModal line 125
- Toggle label: "Allow configurable sync depth" — per spec, sentence case after uppercase transform via CSS
- Toggle description: "When enabled, Org Admins can choose how far back to sync reviews when adding a new shop." — conversational, accurate
- View row label: "Configurable sync depth" — matches CONTEXT.md decision exactly
- View row values: "Enabled" / "Disabled" — plain text per spec decision (no badge)
- Shop row label: "Review history" — conversational, matches CONTEXT.md decision
- Shop row values: "Last 1 year" / "Last 2 years" / "All time" — matches `SYNC_DEPTH_LABELS` map

No empty state or loading state copy was added for the new fields — both are display-only (no async call triggered by viewing them), so this is not a gap.

Score justification: Copy for the phase 15 additions is specific and aligned with the design decisions. The "Something went wrong" pattern is a pre-existing codebase choice, not introduced here.

---

### Pillar 2: Visuals (3/4)

**WARNING — inline style object in ViewOrgModal; button weight inconsistency in ShopDetailsModal**

**ViewOrgModal dl layout (line 67):**
```
style={{ display: "grid", gridTemplateColumns: "140px 1fr", columnGap: 16, rowGap: 12 }}
```
This uses raw inline style with unitless pixel numbers (16, 12) instead of Tailwind tokens. The pre-existing rows already used this approach, and the new "Configurable sync depth" row correctly follows the existing pattern. However, the inline style is a brittleness issue — `columnGap: 16` is not on the 4px scale (it is 16px, which is valid), but `rowGap: 12` is 12px (also valid at 4px grid). The issue is not the values but the medium: CSS-in-JS inline style bypasses the design token system. Fix: migrate to `grid grid-cols-[140px_1fr] gap-x-4 gap-y-3` (Tailwind equivalent).

**ShopDetailsModal Close button (line 105) vs other buttons:**
The Close/primary-action button uses `font-semibold` but the Reconnect Google, Edit, Activate/Deactivate buttons use `font-medium`. This creates an inconsistency where the yellow CTA (Reconnect Google, line 73) reads visually lighter than the Close button even though Close is semantically lower priority. This inconsistency is pre-existing to phase 15 but is present in a file modified by phase 15.

**Toggle switch visual design:**
The ToggleSwitch component is correctly structured: `bg-yellow` when checked, `bg-line` when unchecked, white knob with shadow, smooth transition. The `role="switch"` with `aria-checked` is correct for a toggle semantics. The label association via `htmlFor`/`id` pair gives the button an accessible name. No visual defects found in the toggle component itself.

**"Review history" row placement in ShopDetailsModal:**
Placed after "Connection Status" and before "Created" (lines 156–157). This is a config-adjacent field placed next to connection config — coherent grouping.

---

### Pillar 3: Color (2/4)

**WARNING — three hardcoded hex color clusters in ShopDetailsModal bypass the semantic token system**

ShopDetailsModal lines 120–137 contain:
- Region badge: `style={{ backgroundColor: "#F3F4F6", color: "#374151" }}` — gray-100 / gray-700 approximation, not mapped to any semantic token
- Active status pill: `{ backgroundColor: "#F0FDF4", color: "#16A34A" }` — green-50 / green-600 approximation
- Inactive status pill: `{ backgroundColor: "#F9FAFB", color: "#6B7280" }` — gray-50 / gray-500 approximation

These were pre-existing before phase 15 but are present in a file that phase 15 modified (the "Review history" row was added). The new "Review history" row itself has no color issues — plain text via semantic `text-ink` — and is correctly implemented.

The phase 15 new colors used correctly:
- `bg-yellow` / `bg-line` for toggle states — semantic tokens, correct
- `text-subtle`, `text-muted`, `text-ink` for label/value hierarchy — semantic tokens, correct
- Error state: `text-red` via `border-red` — semantic token, correct

The toggle's `focus:ring-2 focus:ring-black/10` uses a Tailwind opacity modifier rather than a semantic token. This is a minor gap but not a blocker.

Score justification: Phase 15 additions are clean. The pre-existing hardcoded hex clusters are a codebase-wide problem that phase 15 did not fix and did not worsen (the new row is clean). Score is 2 because the audited files contain the violations.

---

### Pillar 4: Typography (2/4)

**BLOCKER-class issue — six distinct pixel sizes and systemic `font-medium` violations**

**Font size audit:**

| Size | Count | Location |
|------|-------|----------|
| `text-[11px]` | 1 | ShopDetailsModal Region badge (line 120) |
| `text-[11.5px]` | 1 | ShopDetailsModal dtCls constant (line 18) |
| `text-[12px]` | 23 | Labels throughout all files |
| `text-[12.5px]` | 1 | ShopDetailsModal Place ID code element (line 145) |
| `text-[13px]` | 9 | ViewOrgModal dd elements throughout |
| `text-[13.5px]` | 16 | Body text and buttons throughout |

Six distinct sizes exceeds the four-size maximum by two steps. The `text-[11.5px]` on the shop detail label constant and `text-[12.5px]` on the Place ID badge are 0.5px increments that add no meaningful visual distinction. They should be collapsed into neighboring sizes.

**Font weight audit:**

The design system allows only `font-normal` (400) and `font-semibold` (600). `font-medium` (500) is explicitly a violation.

`font-medium` occurrences in phase 15 files:
- CreateOrgModal.tsx: lines 118, 127 (Discard and Create Organisation buttons)
- EditOrgModal.tsx: lines 106, 115 (Discard Changes and Save Changes buttons)
- ViewOrgModal.tsx: lines 42, 50, 59 (Close, Resend Invitation, Edit buttons)
- ShopDetailsModal.tsx: lines 73, 81, 89, 97, 133 (Reconnect Google, Edit, Activate, Deactivate, Status pill)

Total: 12 button instances + 1 pill = 13 occurrences. All are pre-existing button patterns the phase 15 executor copied. The ToggleSwitch label correctly uses `font-semibold`, which is the right call. The inconsistency is that every button element in the codebase uses `font-medium` despite the spec requiring `font-semibold`.

Note that `text-[13px]` vs `text-[13.5px]` creates two sizes 0.5px apart on ViewOrgModal — dt labels at 13px and dd values at 13.5px. The distinction is imperceptible in most browser renderings and should collapse to a single body size.

---

### Pillar 5: Spacing (2/4)

**WARNING — multiple off-grid values; one new violation introduced by phase 15 in ToggleSwitch.tsx**

The project uses a 4px base grid. Valid values: 4, 8, 12, 16, 20, 24, 32px (Tailwind: 1, 2, 3, 4, 5, 6, 8).

**New violation (introduced in phase 15):**
- `mt-0.5` (2px) in ToggleSwitch.tsx line 41 — description paragraph top margin. Fix: change to `mt-1` (4px).

**Pre-existing violations present in audited files:**
- `mb-0.5` (2px) in ShopDetailsModal dtCls constant (line 18) — label bottom margin
- `gap-1.5` (6px) in ViewOrgModal Org Admin status row (line 109), ShopDetailsModal Region row (line 118), ShopDetailsModal Review history area — these are in the Row helper `gap-1.5`
- `px-3.5` (14px) on every modal button across all four files — the established button pattern is off-grid
- `px-1.5` / `py-0.5` (6px, 2px) in ShopDetailsModal Region badge (line 120)
- `py-[3px]` (3px) in ShopDetailsModal Status pill (line 133)
- `gap-x-6` (24px) / `gap-y-4` (16px) in ShopDetailsModal dl grid (line 113) — these values ARE on the 4px grid (24px and 16px), so this is not a violation despite the `gap-x-6` naming

**Valid spacing used correctly in phase 15 additions:**
- `gap-3` (12px) in ToggleSwitch flex container — on grid
- `mt-4` (16px) wrapper around ToggleSwitch in form — on grid
- `space-y-4` (16px) form field gap — on grid
- `mt-1` (4px) on error message paragraphs in form fields — on grid
- `gap-4` in ShopDetailsModal dl grid — on grid

The systemic `px-3.5` on buttons is the largest single-pattern violation by count but was not introduced by phase 15.

---

### Pillar 6: Experience Design (3/4)

**WARNING — minor gaps; core interaction patterns are solid**

**Toggle switch interaction quality:**
- `role="switch"` with `aria-checked` is correct ARIA semantics for a toggle
- `<button>` type ensures keyboard activation (space/enter) works natively — no custom `onKeyDown` needed
- `htmlFor`/`id` pair gives the button an accessible name from the label element
- `focus:outline-none focus:ring-2 focus:ring-black/10` provides visible focus indicator
- Transition classes (`transition-colors duration-200`, `transition duration-200`) give smooth animation

**Loading state:**
- Submit buttons show an animated spinner (`animate-spin`) while `submitting` is true and `disabled={submitting}` prevents double-submit — correct for CreateOrgModal (line 130) and EditOrgModal (line 119)
- No loading state needed for ViewOrgModal or ShopDetailsModal read-only rows

**Error state:**
- Field-level validation errors render below each field with `role="alert"` — correct
- API error fallback uses generic copy (see Pillar 1) but does show the error to the user

**Empty state:**
- ShopDetailsModal renders `"No shop selected."` (line 161) when `shop` is null — handled
- ViewOrgModal and EditOrgModal return `null` when `org` is null — acceptable guard

**Missing confirmation for destructive actions:**
- The EditOrgModal "Discard Changes" button fires `onClose` immediately without confirmation — if the user has modified the toggle or any field, the changes are silently discarded. This is pre-existing behavior across all modals and is not specific to phase 15.

**Toggle state persistence after modal close:**
- CreateOrgModal calls `reset()` in `onClose`, which calls `setAllowCustomSyncDepth(false)` — the toggle resets correctly on dismiss
- EditOrgModal re-initializes from `org.allow_custom_sync_depth ?? false` in `useEffect([org])` — correct

---

## Files Audited

**New files (created in phase 15):**
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/org-management/ToggleSwitch.tsx`

**Modified files (phase 15 additions audited in context of full file):**
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/org-management/types.ts`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/org-management/CreateOrgModal.tsx`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/org-management/EditOrgModal.tsx`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/org-management/ViewOrgModal.tsx`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/shop-management/types.ts`
- `/Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/shop-management/ShopDetailsModal.tsx`

**Planning documents read:**
- `.planning/phases/15-sync-depth-data-layer-and-superadmin-controls/15-CONTEXT.md`
- `.planning/phases/15-sync-depth-data-layer-and-superadmin-controls/15-01-PLAN.md` through `15-04-PLAN.md`
- `.planning/phases/15-sync-depth-data-layer-and-superadmin-controls/15-01-SUMMARY.md` through `15-04-SUMMARY.md`
