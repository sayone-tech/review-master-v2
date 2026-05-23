---
phase: 21
slug: audit-log-viewer
audit_date: 2026-05-24
overall_score: 18/24
screenshots: not captured (no dev server detected)
---

# Phase 21 — UI Review: Audit Log Viewer

**Audited:** 2026-05-24
**Baseline:** UI-SPEC.md (approved, status: approved)
**Screenshots:** Not captured — no dev server running on ports 3000/5173/8080. Code-only audit.

---

## Score Summary

| Pillar | Score | Grade |
|--------|-------|-------|
| Copywriting | 4/4 | Excellent |
| Visuals | 3/4 | Good |
| Color | 3/4 | Good |
| Typography | 2/4 | Needs work |
| Spacing | 3/4 | Good |
| Experience Design | 3/4 | Good |
| **Overall** | **18/24** | Good |

---

## Top 3 Priority Fixes

1. **`font-medium` used in select controls instead of spec-required `font-semibold`** — Typography contract violation: the `selectCls` constant in `AuditLogFilters.tsx:9` uses `font-medium text-[14px]`. The spec mandates only `font-normal` (400) and `font-semibold` (600) — no `font-medium` (500). Change to `font-normal` to match cell text weight or `font-semibold` if that matches ActionItemFilters intent, then align across all filter widgets.

2. **`text-[11.5px]` used for filter label caps — off-spec size** — The `FilterLabel` component at `AuditLogFilters.tsx:60` renders at `text-[11.5px]`. The spec declares exactly three sizes: 20px, 14px, and 12px — with the note "13px and 11.5px are collapsed into 12px." Change to `text-[12px]` to comply.

3. **DataTable `<thead>` uses `font-medium` and `bg-[#FBFBFB]` instead of spec-required `font-semibold` and `bg-[#FAFAFA]`** — `DataTable.tsx:111` renders header cells as `font-medium bg-[#FBFBFB]`. The spec explicitly states: "Table header row: `bg-[#FAFAFA] text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]`". This is a shared DataTable component so the fix impacts all widgets; change `font-medium` to `font-semibold` and `bg-[#FBFBFB]` to `bg-[#FAFAFA]` in DataTable thead.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

All visible strings match the UI-SPEC copywriting contract exactly. No generic labels, no placeholder copy.

**Verified matches (exact):**

| Element | Spec | Actual | Match |
|---------|------|--------|-------|
| Page heading | "Activity Log" | "Activity Log" (`AuditLogWidget.tsx:66`) | PASS |
| Nav label | "Activity Log" | "Activity Log" (`sidebar_org.html:41`) | PASS |
| Page title (Django) | "Activity Log" | "Activity Log" (`views.py:210`) | PASS |
| Type default option | "All types" | "All types" (`AuditLogFilters.tsx:135`) | PASS |
| Type option: review | "Replies" | "Replies" (`AuditLogFilters.tsx:136`) | PASS |
| Type option: action_item | "Action Items" | "Action Items" (`AuditLogFilters.tsx:137`) | PASS |
| Actor default option | "All actors" | "All actors" (`AuditLogFilters.tsx:197`) | PASS |
| Actor system option | "System" | "System" (`AuditLogFilters.tsx:198`) | PASS |
| Apply button | "Apply" | "Apply" (`AuditLogFilters.tsx:215`) | PASS |
| Reset button | "Reset" | "Reset" (`AuditLogFilters.tsx:221`) | PASS |
| Empty heading (no data) | "No activity logged yet" | exact (`AuditLogTable.tsx:52`) | PASS |
| Empty body (no data) | "Activity will appear here as your team replies to reviews and manages action items." | exact (`AuditLogTable.tsx:53-56`) | PASS |
| Empty heading (filtered) | "No activity matches your filters" | exact (`AuditLogTable.tsx:64`) | PASS |
| Empty body (filtered) | "Try adjusting the type, date range, or actor filter." | exact (`AuditLogTable.tsx:65-67`) | PASS |
| Empty action (filtered) | "Clear filters" | exact (`AuditLogTable.tsx:73`) | PASS |
| Error heading | "Could not load activity log" | exact (`AuditLogTable.tsx:83`) | PASS |
| Error body | "Something went wrong. Please try again." | exact (`AuditLogTable.tsx:84`) | PASS |
| Error action | "Retry" | exact (`AuditLogTable.tsx:89`) | PASS |
| Expand aria-label | "Show details" / "Hide details" | exact (`AuditLogTable.tsx:35`) | PASS |
| Pagination prev aria-label | "Previous page" | exact (`AuditLogWidget.tsx:109`) | PASS |
| Pagination next aria-label | "Next page" | exact (`AuditLogWidget.tsx:118`) | PASS |
| Pagination rows aria-label | "Rows per page" | exact (`AuditLogWidget.tsx:95`) | PASS |
| System actor display | italic `text-muted` "System" | exact (`AuditLogTable.tsx:133-135`) | PASS |

**D-20 ACTION_LABEL map** — all 8 entries present and correct in `types.ts:35-44`. Unknown action fallback to raw string in `text-muted` implemented at `AuditLogTable.tsx:148-153`.

No generic "Submit", "Click Here", "Cancel", "OK" labels found anywhere in the widget.

---

### Pillar 2: Visuals (3/4)

The structural visual contract is substantially met. Three deviations noted.

**PASS items:**
- Sidebar nav item present: `{% include "partials/_nav_item.html" with href="/admin/org/activity-log/" icon="clock" label="Activity Log" %}` at `sidebar_org.html:41`. Placement is correct — outside the `{% if user.role != "STAFF_ADMIN" %}` guard, at the bottom of the single `<ul>`.
- Five columns present: Date / Time, Actor, Type, Action, Details — matches spec exactly (`AuditLogTable.tsx:111-168`).
- TypePill renders Reply (blue) and Action Item (amber) as specified.
- Expandable caret present with ChevronRight/ChevronDown toggle.
- Empty states: ClipboardList icon for no-data, Search icon for filtered — both match spec icons.
- Error state: AlertCircle icon with retry button — matches spec.
- Filter bar: 4-column grid with Type, Date Range, Actor, Apply/Reset.

**WARNING — DataTable thead background incorrect:** Spec states `bg-[#FAFAFA]` for table header rows. `DataTable.tsx:94,111` use `bg-[#FBFBFB]`. This means the thead merges visually with the pagination footer (also `bg-[#FBFBFB]`) rather than reading as a distinct, slightly-lighter header zone against the white body rows.

**WARNING — DataTable row hover incorrect:** Spec states `hover:bg-line-soft` (`#F4F4F5`). `DataTable.tsx:172` uses `hover:bg-[#FBFBFB]` (`#FBFBFB`). The hover contrast ratio versus white rows (#FFFFFF) is approximately 1.04:1 — effectively invisible on most displays. `line-soft` (#F4F4F5) provides a more perceptible 1.06:1 and matches the established pattern name.

**WARNING — Loading skeleton count is 6 rows, not 8:** Spec states "Show 8 skeleton rows on initial load." `DataTable.tsx:126` renders `Array.from({ length: 6 })`. The audit-log widget does not override this — it uses the shared DataTable default. The visual difference is minor but it deviates from the spec.

---

### Pillar 3: Color (3/4)

Token usage is mostly correct. Two hardcoded hex values appear in widget code; one is outside the token set.

**PASS items:**
- `bg-yellow text-black border-yellow-hover` on Apply button — correct.
- `bg-blue-tint text-blue` on Reply pill — correct.
- `bg-amber-tint text-amber` on Action Item pill — correct.
- `bg-[#FAFAFA]` on expanded detail panel — matches spec (equals `bg` token).
- `bg-[#FBFBFB]` on pagination footer — matches spec (pre-existing widget pattern).
- All semantic tokens (`text-ink`, `text-text`, `text-muted`, `text-subtle`, `text-faint`, `border-line`, `bg-line-soft`) used correctly throughout.

**WARNING — `hover:border-[#D4D4D8]` is not a design token:** `AuditLogFilters.tsx:9` (the `selectCls` constant) uses `hover:border-[#D4D4D8]`. This hex value does not appear in `tailwind.config.js`. It is between `line` (#E4E4E7) and `subtle` (#71717A) — a grey not in the semantic palette. However, this value is copied verbatim from the existing `ActionItemFilters.tsx:14` and `ReviewFilters.tsx`, so it is a pre-existing inconsistency shared across all filter widgets, not introduced by Phase 21. Severity: LOW for this phase; warrants a cross-widget token cleanup in a future phase.

**WARNING — `focus:shadow-[0_0_0_3px_rgba(10,10,10,0.05)]` uses rgba not a token:** Same line (`AuditLogFilters.tsx:9`). The focus ring is an arbitrary CSS value. Same pre-existing pattern from ActionItemFilters. LOW severity for this phase.

**PASS — No new out-of-token hex values introduced by Phase 21.** The `bg-[#FAFAFA]`, `bg-[#FBFBFB]` values are spec-sanctioned exceptions.

---

### Pillar 4: Typography (2/4)

Two violations against the strict two-size, two-weight contract.

**Spec contract:** Three sizes only (20px, 14px, 12px). Two weights only (font-normal 400, font-semibold 600). font-medium (500) prohibited.

**BLOCKER — `font-medium` used in select elements:** `AuditLogFilters.tsx:9` (`selectCls` constant) applies `font-medium` to all three `<select>` controls (Type, Actor, and the page-size select in the widget root reuses the same approach). This directly violates the spec: "font-normal (400) and font-semibold (600) only. font-medium (500) is not used." The impact is that select control text renders at an intermediate weight that breaks the two-weight hierarchy. Mitigating factor: this is the same `selectCls` string used in ActionItemFilters and ReviewFilters — it is a pre-existing pattern, not a Phase 21 regression.

**WARNING — `text-[11.5px]` used for filter label caps:** `AuditLogFilters.tsx:60` (`FilterLabel` component) uses `text-[11.5px]`. The spec explicitly states: "Size summary: 20px, 14px, 12px — three sizes. 13px and 11.5px are collapsed into 12px." The correct class is `text-[12px]`.

**WARNING — DataTable base table text is `text-[13.5px]`:** `DataTable.tsx:89` sets the table's base font to `text-[13.5px]`. While individual cell accessors in `AuditLogTable.tsx` explicitly override with `text-[14px]` / `text-[12px]` on the content spans, any text rendered directly in a `<td>` without an explicit size override will inherit 13.5px — a size not in the spec's declared set.

**WARNING — DataTable `<thead>` uses `font-medium` not `font-semibold`:** `DataTable.tsx:111` renders `font-medium text-subtle`. Spec mandates `font-semibold`. The column headers should be visually more prominent than body text to create hierarchy; `font-medium` weakens this separation.

Font size distribution across audit-log widget files:
- `text-[20px]` — 1 use (page heading) — CORRECT
- `text-[14px]` — 12 uses (body, filter labels, state text) — CORRECT
- `text-[12px]` — 8 uses (pills, pagination, presets) — CORRECT
- `text-[11.5px]` — 1 use (FilterLabel caps) — VIOLATION
- `text-[13.5px]` — 0 uses in audit-log widget itself (inherited from DataTable)

Weight distribution:
- `font-semibold` — 5 uses — CORRECT
- `font-normal` — 0 explicit uses (acceptable as default reset)
- `font-medium` — 1 use in `selectCls` — VIOLATION
- `font-mono` — 1 use (JSON panel) — CORRECT per spec

---

### Pillar 5: Spacing (3/4)

Most spacing is on-grid. Three off-grid values identified; one is in the new widget code, two are in the shared DataTable.

**PASS items:**
- Filter bar container: `p-4` (16px) — correct.
- Filter grid: `gap-4` (16px) — correct.
- Pagination footer: `px-4 py-3` (16px / 12px) — correct.
- Expanded panel: `px-4 py-3` — correct.
- Empty states: `px-4 py-12` — correct.
- Preset buttons: `px-2 py-1` — correct.
- Apply/Reset buttons: `px-4 py-2` — correct.
- Caret button: `w-8 h-8` (32px) — correct.
- Pagination chevron icons: `w-4 h-4` (16px) — matches spec exactly. The spec identified this as a potential deviation to check; the implementation is correct.
- `space-y-4` widget container — correct.

**WARNING — `gap-1.5` (6px) used for filter label icon gaps and column stacking:** `AuditLogFilters.tsx:60, 124, 144, 146, 188` use `gap-1.5` (6px). The spec spacing scale has `gap-1` (4px) for icon-to-text gaps in pills and `gap-2` (8px) for compact controls. 6px is between grid steps. Mitigating factor: the spec notes this as a correction needed ("gap-1.5 (6px) should be gap-2") — the spec checker pre-identified this as a risk and the implementation still landed at the off-grid value. Change to `gap-2` (8px) for label-to-input column stacking, and `gap-1` (4px) for icon-to-label text gaps inside `FilterLabel`.

**WARNING — `py-[10px]` (10px) in `selectCls`:** `AuditLogFilters.tsx:9` uses `py-[10px]`. 10px is not a 4px-grid value (grid: 8px, 12px). This is again the shared ActionItemFilters pattern. Should be `py-2` (8px) or `py-3` (12px). Pre-existing cross-widget issue.

**WARNING — `py-[11px]` in DataTable thead:** `DataTable.tsx:94,111,118` use `py-[11px]`. 11px is off the 4px grid. Spec table cell padding is `px-4 py-3` (12px vertical). Should be `py-3`.

---

### Pillar 6: Experience Design (3/4)

Core interaction flows are all implemented. Three gaps against the spec.

**PASS items:**
- Draft-then-apply filter pattern — implemented correctly in `AuditLogFilters.tsx`. Changing a select updates draft state only; Apply commits to URL and refetches.
- Preset quick-picks (7d/30d/90d) auto-apply immediately by calling `onApply(next)` in `selectPreset()` — correct.
- Custom preset leaves date inputs active and requires Apply — correct.
- URL param sync on Apply/Reset via `window.history.pushState` — implemented in `useAuditLog.ts:39-49`.
- URL params read on mount to initialise filter state — `readUrlFilters()` at `useAuditLog.ts:22-37`.
- Only one row expanded at a time — `expandedId` state in `useAuditLog.ts`, expanding a new row collapses the previous via `onExpand(expandedId === row.id ? null : row.id)` at `AuditLogTable.tsx:164`.
- Cursor pagination — Previous/Next wired correctly. Cursor stack with server-cursor fallback for hot-reload case.
- Relative dates — `formatRelativeDate` copied from `ReviewTable.tsx` per spec instruction.
- Absolute datetime in `title` attribute on `<time>` element — `AuditLogTable.tsx:119` uses `new Date(row.created_at).toLocaleString()`.
- Actor dropdown populated from server-rendered JSON — `audit-log-actors-data` json_script read in entrypoint.
- Retry button in error state — `refetch()` exposed and wired.
- Staff scoping — handled by the backend selector (D-03); frontend receives already-filtered data.
- `aria-expanded`, `aria-controls`, `role="region"` on expand panel — all correct.
- `<nav aria-label="Pagination">` — correct.

**WARNING — Loading skeleton row count is 6, not 8:** Spec: "Show 8 skeleton rows on initial load." `DataTable.tsx:126` hardcodes 6 rows. The audit-log widget does not pass a `skeletonRowCount` prop (none exists on `DataTableProps`). The table will show 6 skeleton rows during initial load. This is a minor experience shortfall — fewer skeleton rows means a more dramatic height jump when data loads.

**WARNING — `<table>` is missing `<caption className="sr-only">Activity log</caption>`:** The accessibility contract at UI-SPEC §Accessibility explicitly requires `<caption className="sr-only">Activity log</caption>`. This caption is not present in `DataTable.tsx` and is not injected by `AuditLogTable.tsx`. Screen reader users navigating to the table will not hear a table summary before interacting with it.

**WARNING — `<th>` elements lack `scope="col"`:** UI-SPEC §Accessibility requires `<th scope="col">` on every header cell. `DataTable.tsx:109-121` renders `<th>` without scope attributes. This is a shared DataTable omission that affects every widget using DataTable; Phase 21 did not regress it but did not fix it either.

---

## Registry Safety

No shadcn (`components.json` not present). No third-party registries used. Registry audit not applicable.

---

## Files Audited

**Frontend widget files:**
- `frontend/src/widgets/audit-log/AuditLogWidget.tsx`
- `frontend/src/widgets/audit-log/AuditLogFilters.tsx`
- `frontend/src/widgets/audit-log/AuditLogTable.tsx`
- `frontend/src/widgets/audit-log/TypePill.tsx`
- `frontend/src/widgets/audit-log/types.ts`
- `frontend/src/widgets/audit-log/useAuditLog.ts`
- `frontend/src/widgets/audit-log/utils.ts`
- `frontend/src/widgets/audit-log/api.ts`
- `frontend/src/entrypoints/audit-log.tsx`
- `frontend/src/widgets/data-table/DataTable.tsx` (shared dependency)
- `frontend/src/widgets/action-items/ActionItemFilters.tsx` (reference for selectCls pattern)

**Template files:**
- `templates/org-admin/audit-log.html`
- `templates/partials/sidebar_org.html`

**Backend files (context only):**
- `apps/common/views.py` (audit_log_view page_title)

**Config files:**
- `frontend/tailwind.config.js` (token verification)

**Design contract:**
- `.planning/phases/21-audit-log-viewer/21-UI-SPEC.md`
- `.planning/phases/21-audit-log-viewer/21-CONTEXT.md`
- `.planning/phases/21-audit-log-viewer/21-01-SUMMARY.md` through `21-04-SUMMARY.md`
