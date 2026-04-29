---
status: awaiting_human_verify
trigger: "The Regions page now mounts the React widget and shows an empty state, but the design is wrong. Compared to the working org-management page, the Regions page is missing: 1. The DataTable shell/chrome (table border, header row with column names) 2. The search/filter bar at the top of the table area 3. The overall layout doesn't match the org-management empty view design"
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — DataTable.tsx early-returns the emptyState node directly (bypassing all table chrome) when rows.length === 0 and emptyState prop is set. OrgTable never hits this path because it doesn't pass emptyState prop and is only mounted when rows > 0.
test: Read DataTable.tsx line 34-36 — confirmed early return: `if (!loading && rows.length === 0 && emptyState) return <>{emptyState}</>;`
expecting: Fix requires rendering emptyState inside a <tbody> spanning row instead of bailing out early
next_action: Fix DataTable.tsx to render emptyState inside table chrome

## Symptoms

expected: Regions page shows the same layout as org-management: search/filter bar at top, DataTable with column headers (Region Name, Region ID, Actions), empty state inside the table body when no rows exist
actual: Only the empty state content renders (MapPin icon, "No regions yet" text) with no table chrome, no search bar, no column headers — just raw empty state content floating in the page
errors: No JS errors. Visual/layout issue only.
reproduction: Navigate to /admin/org/regions/ as Org Admin with no regions.
started: Just fixed the mount div conditional. Empty state renders but layout is incomplete.

## Eliminated

- hypothesis: RegionTable doesn't use DataTable at all
  evidence: RegionTable.tsx line 34 — it does use DataTable and passes emptyState prop correctly
  timestamp: 2026-04-29T00:01:00Z

## Evidence

- timestamp: 2026-04-29T00:01:00Z
  checked: DataTable.tsx lines 34-36
  found: `if (!loading && rows.length === 0 && emptyState) { return <>{emptyState}</>; }` — early return escapes all table chrome
  implication: Any consumer that passes emptyState AND has zero rows gets back a naked emptyState node with no wrapping table structure

- timestamp: 2026-04-29T00:01:00Z
  checked: OrgTable.tsx and org-management.tsx
  found: OrgTable never passes emptyState prop to DataTable. The org-management template only mounts #org-table-root when regions_count > 0 (Django-side conditional), so DataTable's early return is never triggered.
  implication: The org page avoids the bug by never passing emptyState. The regions page hits the bug because it always mounts #region-table-root and passes emptyState.

- timestamp: 2026-04-29T00:01:00Z
  checked: region_list.html
  found: `<div id="region-table-root"></div>` is always rendered (no Django conditional), and RegionTableWidget always passes emptyState={<RegionEmptyState />} to DataTable via RegionTable
  implication: Confirms the exact path: always-mounted root → RegionTable passes emptyState → DataTable bails out early → no table chrome

## Resolution

root_cause: DataTable.tsx early-returns the emptyState node directly when rows is empty, bypassing all table chrome (border, header row, column labels). The fix is to remove the early return and instead render emptyState inside a full-width <tbody> spanning row so all table structure is preserved.
fix: Remove early-return block from DataTable.tsx; add a tbody row with a colspan cell that renders emptyState when !loading && rows.length === 0 && emptyState
verification: awaiting human confirmation
files_changed: [frontend/src/widgets/data-table/DataTable.tsx]
