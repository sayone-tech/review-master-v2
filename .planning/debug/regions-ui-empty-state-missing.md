---
status: verifying
trigger: "regions-ui-empty-state-missing: React widget content area is blank — no DataTable, no empty state"
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
---

## Current Focus
<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: CONFIRMED — region-table-root div gated behind {% if regions_count > 0 %}, so with zero regions the div never exists and React never mounts
test: read template + entrypoint side by side
expecting: ids match, but div conditionally absent
next_action: fix applied — region-table-root moved outside the conditional; region-data script tag still conditional (only present when regions exist)

## Symptoms
<!-- Written during gathering, then IMMUTABLE -->

expected: When no regions exist, React widget renders empty state: MapPin icon, "No regions yet" heading, "Create your first region" CTA (per RGN-02)
actual: Content area below page header is completely blank — no table, no empty state, no spinner
errors: No new 404 errors. JS bundle loads. Unknown console errors.
reproduction: Navigate to /admin/org/regions/ as Org Admin with no regions created yet
started: After fixing vite_asset path ({% vite_asset 'src/entrypoints/region-management.tsx' %})
prior_fix: templates/regions/region_list.html had wrong vite_asset argument — now fixed

## Eliminated
<!-- APPEND only - prevents re-investigating -->

## Evidence
<!-- APPEND only - facts discovered -->

- timestamp: 2026-04-29T00:01:00Z
  checked: templates/regions/region_list.html lines 19-22
  found: region-table-root div is inside {% if regions_count > 0 %} block
  implication: div never rendered when 0 regions → document.getElementById("region-table-root") returns null → createRoot never called → no React content

- timestamp: 2026-04-29T00:01:00Z
  checked: frontend/src/entrypoints/region-management.tsx lines 28-35
  found: entrypoint does getElementById("region-table-root") and skips if null — no error, just silent no-op
  implication: confirms blank content with no console error

- timestamp: 2026-04-29T00:01:00Z
  checked: frontend/src/widgets/region-management/RegionTable.tsx
  found: RegionTableWidget renders RegionTable which passes <RegionEmptyState /> to DataTable's emptyState prop
  implication: empty state is fully implemented and would render correctly if the mount div existed

- timestamp: 2026-04-29T00:01:00Z
  checked: frontend/src/widgets/region-management/RegionEmptyState.tsx
  found: MapPin icon + "No regions yet" heading + "Create your first region" CTA — matches RGN-02 requirement exactly
  implication: empty state component is correct; only problem was the missing mount div

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause: In templates/regions/region_list.html the <div id="region-table-root"> was wrapped inside {% if regions_count > 0 %}. When an Org Admin has no regions, the div is never emitted into the HTML. The React entrypoint's document.getElementById("region-table-root") returns null and silently skips mounting, leaving a blank content area.
fix: Moved <div id="region-table-root"></div> outside the conditional. The {% if regions_count > 0 %} block now only guards the json_script tag (which seeds the initial rows), not the mount div itself. RegionTableWidget receives initialRows=[] and the DataTable's emptyState prop renders RegionEmptyState as intended.
verification: With 0 regions: region-table-root div is always present → React mounts → RegionTableWidget receives [] → DataTable renders RegionEmptyState (MapPin, "No regions yet", "Create your first region" CTA). With N>0 regions: region-data script tag present → initialRows parsed → table rows shown. The {% if %} guard on the script tag prevents a JSON parse of undefined when count is 0.
files_changed:
  - templates/regions/region_list.html
