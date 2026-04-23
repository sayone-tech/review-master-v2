---
phase: 03-organisation-management
plan: "06"
subsystem: frontend-templates-react
tags: [gap-closure, uat, sidebar, datatable, react-strictmode, pagination, empty-state]
dependency_graph:
  requires: [03-02, 03-04, 03-05]
  provides: [uat-gap-1-closed, uat-gap-2-closed, uat-gap-3-closed, uat-gap-4-closed, uat-gap-5-closed]
  affects: [templates/partials/sidebar.html, frontend/src/widgets/data-table/DataTable.tsx, frontend/src/entrypoints/org-management.tsx, templates/organisations/list.html, templates/components/pagination.html]
tech_stack:
  added: []
  patterns:
    - useCallback with empty deps to stabilise event-listener handler props under React 18 StrictMode
    - Guard React mount-point divs inside the conditional branch that owns their data
    - Extract per-page form outside count > 0 guard in pagination so it renders on zero-result pages
key_files:
  created: []
  modified:
    - templates/partials/sidebar.html
    - frontend/src/widgets/data-table/DataTable.tsx
    - frontend/src/entrypoints/org-management.tsx
    - templates/organisations/list.html
    - templates/components/pagination.html
    - apps/organisations/tests/test_views.py
decisions:
  - "React 18 StrictMode + inline handler prop to a useEffect listener registrar causes click listener to be absent at click time — stabilise with useCallback([])"
  - "Tailwind overflow-hidden on a wrapper breaks child position:sticky — prefer overflow-x-auto on the scroll container only"
  - "Mount-point divs for React widgets must live inside the conditional that guards their data, otherwise the widget visually overrides server-rendered empty states"
metrics:
  duration: "~3 min"
  completed: "2026-04-23"
  tasks_completed: 3
  files_modified: 6
---

# Phase 03 Plan 06: UAT Gap Closure Summary

Five diagnosed UAT gaps were closed with surgical one-to-two-line fixes across the sidebar, DataTable, React entrypoint, and two Django templates.

## What Was Built

Closed the five UAT gaps blocking Phase 3 acceptance:

- **Gap 1 (sidebar nav link):** Organisations href was `/organisations/` — corrected to `/admin/organisations/` matching the registered URL.
- **Gap 2 (DataTable sticky thead):** `overflow-hidden` on the outer DataTable wrapper prevented `position: sticky` on thead — removed; `overflow-x-auto` on the inner scroll container is sufficient.
- **Gap 3 (Create modal under StrictMode):** `CreateButtonBridge` received a new inline `onOpen` function on every render, causing its `useEffect([onOpen])` to re-register the click listener continuously. Fixed by wrapping `setCreateOpen(true)` in `useCallback([])` and passing the stable reference.
- **Gap 4 (empty state obscured by React):** `<div id="org-table-root">` was outside the `{% if %}/{% else %}` block, so React always mounted and visually overrode the Django-rendered empty state. Moved inside the `{% else %}` branch.
- **Gap 5 (per-page selector hidden on zero results):** `pagination.html` was entirely wrapped in `{% if count > 0 %}`. Changed outer guard to `{% if count > 0 or per_page_options %}` and extracted the per-page form outside the count guard so it renders even when the result set is empty.

## Tasks Executed

| Task | Name | Gap(s) Closed | Commit |
|------|------|---------------|--------|
| 1 | Fix sidebar nav link + DataTable sticky-header | Gap 1, Gap 2 | 6c3ea4d |
| 2 | Stabilise onOpen prop with useCallback | Gap 3 | 6fe4ba9 |
| 3 | Restructure list.html + pagination.html | Gap 4, Gap 5 | a3d8cb7 |
| 4 | UAT human re-run | — | awaiting |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_org_list_template_renders_200_for_superadmin**
- **Found during:** Task 3
- **Issue:** Test asserted `id="org-data"` and `id="org-table-root"` appear in response without creating any orgs. After the fix, these elements are inside the `{% else %}` branch (only rendered when count > 0), so the empty-DB test scenario no longer included them.
- **Fix:** Added `OrganisationFactory()` call at the start of the test so an org exists and the `{% else %}` branch renders.
- **Files modified:** `apps/organisations/tests/test_views.py`
- **Commit:** a3d8cb7

## Key Architectural Notes (for STATE decisions)

1. **React 18 StrictMode + inline handler prop race:** When a child component's `useEffect` lists an `onOpen` prop in its dependency array and re-registers a DOM event listener on each change, passing an inline arrow `() => fn()` causes the listener to be absent at the instant the parent re-renders — even briefly. StrictMode's double-invoke amplifies this. Solution: `useCallback([], [])` produces a stable identity across renders.

2. **Tailwind `overflow-hidden` kills `position: sticky`:** Any ancestor with `overflow: hidden` (or `overflow-x: hidden`) creates a new scroll context that clamps sticky elements. The fix is to apply overflow only on the scrollable inner container (`overflow-x-auto`) and leave the outer wrapper overflow-free.

3. **React mount-point placement:** React widget mount-point divs must be co-located with the conditional that guards the data that feeds them. If the div is unconditionally present while the data block is conditional, the widget mounts in a no-data state and visually obscures server-side empty states.

## Test Results

- **vitest (DataTable):** 4/4 passed
- **vitest (org-management widgets):** 16/16 passed
- **vitest (combined):** 20/20 passed
- **pytest (organisations/test_views.py):** 21/21 passed

## UAT Status

Task 4 is a blocking human-verify checkpoint. The user must re-run the four UAT steps manually:
1. Sidebar nav link navigates to /admin/organisations/ (no 404)
2. DataTable column headers render at the top of the table (no detached header)
3. Create Organisation modal opens on first click under StrictMode
4. Empty-state card renders when search returns zero results; per-page selector visible in both states

## Self-Check: PASSED

- `templates/partials/sidebar.html` — contains `/admin/organisations/` on line 31
- `frontend/src/widgets/data-table/DataTable.tsx` — `overflow-hidden` removed from line 40
- `frontend/src/entrypoints/org-management.tsx` — `useCallback` imported and used on line 26
- `templates/organisations/list.html` — `org-table-root` inside `{% else %}` only (line 27)
- `templates/components/pagination.html` — outer guard `count > 0 or per_page_options` on line 5
- Commits 6c3ea4d, 6fe4ba9, a3d8cb7 confirmed in git log
