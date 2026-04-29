---
status: awaiting_human_verify
trigger: "Phase 7 Regions UI is broken. React widget never mounts. GET http://localhost:5173/static/dist/region-management net::ERR_ABORTED 404 (Not Found)"
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T14:00:00Z
---

## Current Focus
<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: CONFIRMED — region_list.html passes the Rollup input key ("region-management") to vite_asset instead of the source file path ("src/entrypoints/region-management.tsx")
test: Read both templates and vite.config.ts
expecting: django-vite constructs wrong URL from bare key, org-management uses full source path and works
next_action: Apply fix — change vite_asset argument to src/entrypoints/region-management.tsx

## Symptoms
<!-- Written during gathering, then IMMUTABLE -->

expected: /admin/org/regions/ shows a regions table (or empty state) with a working "+ Create Region" button that opens a modal
actual: Page loads with the shell (sidebar, header) but the React widget area is blank/empty. "+ Create Region" button does nothing.
errors: GET http://localhost:5173/static/dist/region-management net::ERR_ABORTED 404 (Not Found)
reproduction: Navigate to /admin/org/regions/ as an Org Admin. Open browser DevTools console.
started: Phase 7 was just completed — this is first browser test of the Regions UI

## Eliminated
<!-- APPEND only - prevents re-investigating -->

- hypothesis: Missing vite.config.ts entry for region-management
  evidence: vite.config.ts has "region-management" correctly listed as a rollupOptions input pointing to src/entrypoints/region-management.tsx
  timestamp: 2026-04-29T14:00:00Z

- hypothesis: Wrong entrypoint file (tsx vs ts extension)
  evidence: Both vite.config.ts and the working org-management pattern use .tsx; entrypoint file path is correct
  timestamp: 2026-04-29T14:00:00Z

## Evidence
<!-- APPEND only - facts discovered -->

- timestamp: 2026-04-29T14:00:00Z
  checked: frontend/vite.config.ts rollupOptions.input
  found: "region-management" key maps to src/entrypoints/region-management.tsx — entry is correctly defined
  implication: The Vite entrypoint exists; problem is not missing config

- timestamp: 2026-04-29T14:00:00Z
  checked: templates/organisations/list.html (working) vs templates/regions/region_list.html (broken)
  found: Working template uses {% vite_asset 'src/entrypoints/org-management.tsx' %} (full source path). Broken template uses {% vite_asset 'region-management' %} (bare Rollup input key, not a path).
  implication: django-vite's vite_asset tag requires the source file path relative to the frontend directory. Passing the bare Rollup key causes it to construct http://localhost:5173/static/dist/region-management which the Vite dev server does not serve — yielding the 404.

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause: templates/regions/region_list.html passed the bare Rollup input key ('region-management') to {% vite_asset %} instead of the source file path. django-vite constructs the dev server URL from the argument directly, so 'region-management' becomes /static/dist/region-management (404) rather than the correct http://localhost:5173/src/entrypoints/region-management.tsx.
fix: Changed {% vite_asset 'region-management' %} to {% vite_asset 'src/entrypoints/region-management.tsx' %} in templates/regions/region_list.html — matching the pattern used by the working org-management template.
verification: grep confirms the tag now reads {% vite_asset 'src/entrypoints/region-management.tsx' %}. Awaiting browser confirmation.
files_changed:
  - templates/regions/region_list.html
