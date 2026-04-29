---
status: awaiting_human_verify
trigger: "Fix three Org Admin UI bugs: empty-state CTA not clickable, root URL shows wrong UI, profile page scroll/clip issues"
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
symptoms_prefilled: true
---

## Current Focus

hypothesis: Previous fix added `h-full overflow-hidden` to the aside which (a) caused `overflow-hidden` to clip the bottom section and paint the background only to content height (white gap on short pages) and (b) `h-full` in flex context is redundant — `align-items: stretch` handles height. Also, the nav lacked `min-h-0` allowing it to grow beyond its flex allocation and push the bottom section out.
test: Remove `h-full overflow-hidden` from aside, add `min-h-0` to nav, add `shrink-0` to bottom section
expecting: Sidebar fills full height on all pages (no white gap), bottom section always visible
next_action: Human verify in browser

## Symptoms

expected: (1) Empty state CTA opens Create Region modal; (2) "/" redirects Org Admin to /admin/org/dashboard/; (3) Profile page sidebar stays fixed, main content doesn't scroll independently
actual: (1) CTA button does nothing; (2) "/" renders wrong UI with hardcoded sidebar links; (3) Right side scrolls, sidebar bottom clipped
errors: No JS errors mentioned; no server errors mentioned
reproduction: (1) Visit regions page with no regions; (2) Visit "/" as Org Admin; (3) Visit /admin/org/profile/
started: Unknown — likely introduced during development

## Eliminated

- hypothesis: RegionEmptyState missing onCreateClick prop entirely
  evidence: RegionModals.tsx has CreateButtonBridge which uses document.getElementById — the mechanism exists, it's just a timing race
  timestamp: 2026-04-29

- hypothesis: sidebar_org.html has hardcoded wrong URLs causing Bug 2
  evidence: sidebar_org.html correctly uses /admin/org/... paths; the wrong sidebar shown at "/" is sidebar.html (base.html shell), which has hardcoded /stores/ /reviews/ for ORG_ADMIN
  timestamp: 2026-04-29

## Evidence

- timestamp: 2026-04-29
  checked: region-management.tsx entrypoint
  found: Two separate createRoot calls — modals root first, then table root. Both mount independently.
  implication: CreateButtonBridge useEffect runs when modals root mounts, but empty-state button doesn't exist in DOM yet (it's inside the table root which hasn't rendered)

- timestamp: 2026-04-29
  checked: apps/common/views.py home() + apps/common/urls.py
  found: path("", home) renders pages/placeholder.html which extends base.html (superadmin shell) with sidebar.html that has ORG_ADMIN branch pointing to /stores/ and /reviews/
  implication: Authenticated Org Admin visiting "/" gets the wrong shell with stale hardcoded URLs, no redirect

- timestamp: 2026-04-29
  checked: templates/partials/shell_org_open.html + templates/base_org.html
  found: Wrapper div uses min-h-screen (allows page to grow beyond viewport). Main has no overflow-y-auto. Sidebar has no h-full or overflow-hidden.
  implication: On long-content pages (profile), the whole page scrolls. Sidebar bottom section gets clipped by viewport rather than being constrained within a fixed-height container.

## Resolution

root_cause: |
  Bug 1: CreateButtonBridge in RegionModals.tsx queries DOM for #open-create-region-empty by ID in a useEffect on mount. Because region-modals-root and region-table-root are two independent React createRoot trees initialised sequentially in the entrypoint, the empty-state button (rendered inside the table tree) is not yet in the DOM when the modals tree's useEffect fires. Result: no click listener is ever attached to the empty-state CTA.

  Bug 2: apps/common/views.home() renders pages/placeholder.html (which extends base.html / superadmin shell with a sidebar.html that contains hardcoded /stores/ and /reviews/ links for ORG_ADMIN). No role-based redirect exists. Any authenticated Org Admin visiting "/" sees the wrong UI.

  Bug 3 (original): shell_org_open.html used min-h-screen (not h-screen overflow-hidden), main had no overflow-y-auto.

  Bug 3 (regression from first fix): The first fix added `h-full overflow-hidden` to the aside. `overflow-hidden` on the aside element causes two problems: (1) it clips the aside's own painted background to the content height rather than the flex-stretched height, producing a white gap on pages with few nav items; (2) it can clip the bottom section (logout + user name) when the nav pushes the bottom section to exactly the border of the aside box. Additionally, `min-h-0` was missing from the nav, allowing it to grow beyond its flex allocation in some browsers and push the bottom section out of visible bounds.

fix: |
  Bug 1: RegionEmptyState button now dispatches window CustomEvent "region:open-create" on click. CreateButtonBridge updated to listen for that event (race-free) instead of querying DOM by ID for the empty-state button. Header button (#open-create-region) still wired by ID at mount (it's in the Django template DOM, always present).

  Bug 2: home() now redirects: unauthenticated → login; SUPERADMIN → organisation_list; ORG_ADMIN/STAFF_ADMIN → org_admin_dashboard_v02.

  Bug 3 (final): sidebar_org.html aside — removed `h-full overflow-hidden` (flex stretch via align-items:stretch handles full height without overflow-hidden side effects). nav — added `min-h-0` (prevents flex-1 item from growing beyond its allocated space, enabling overflow-y-auto). Bottom section div — added `shrink-0` (prevents it from being squeezed out when nav fills flex space). shell_org_open.html outer div remains `h-screen overflow-hidden flex`. base_org.html main remains `flex-1 overflow-y-auto`.

verification: Structure traced to confirm all three mechanisms are addressed
files_changed:
  - frontend/src/widgets/region-management/RegionEmptyState.tsx
  - frontend/src/widgets/region-management/RegionModals.tsx
  - apps/common/views.py
  - templates/partials/shell_org_open.html
  - templates/base_org.html
  - templates/partials/sidebar_org.html
