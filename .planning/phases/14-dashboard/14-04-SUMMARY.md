---
phase: 14-dashboard
plan: "04"
subsystem: dashboard-frontend-scaffold
tags: [dashboard, frontend, react, vite, npm, bootstrap-data]
dependency_graph:
  requires: ["14-03"]
  provides: ["dashboard-html-surface", "dashboard-npm-packages", "dashboard-vite-entrypoint"]
  affects: ["templates/organisations/org_dashboard.html", "apps/organisations/views.py", "frontend/vite.config.ts"]
tech_stack:
  added: ["recharts@3.8.1", "@tanstack/react-query@5.100.9"]
  patterns: ["json_script bootstrap data", "React island hydration via div#dashboard-root"]
key_files:
  created: []
  modified:
    - apps/organisations/views.py
    - templates/organisations/org_dashboard.html
    - frontend/vite.config.ts
    - frontend/package.json
    - frontend/package-lock.json
decisions:
  - "get_accessible_shop_ids uses user_id (not user object) — function signature preserved from Phase 11"
  - "org_id type narrowed to int via explicit None check on both organisation and organisation_id for mypy strict compliance"
  - "recharts and @tanstack/react-query installed with ^ semver range (npm default) — patch versions locked in package-lock.json"
metrics:
  duration: "7m"
  completed_date: "2026-05-07"
  tasks_completed: 2
  files_changed: 5
---

# Phase 14 Plan 04: Dashboard HTML Surface + npm Packages Summary

**One-liner:** React-ready dashboard page with json_script bootstrap data, recharts + @tanstack/react-query installed, and dashboard vite entrypoint registered.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update org_admin_dashboard view + replace template | 3168134 | apps/organisations/views.py, templates/organisations/org_dashboard.html |
| 2 | Install npm packages + register vite entrypoint | d31d05e | frontend/package.json, frontend/package-lock.json, frontend/vite.config.ts |

## What Was Built

**org_admin_dashboard view** now builds scoped bootstrap context:
- `accessible_shop_ids` fetched via `get_accessible_shop_ids(user_id=user.pk)` (staff-scoped)
- `shops_json`: id/name/region_id for accessible shops, ordered by name
- `regions_json`: id/name for regions containing accessible shops
- `is_single_shop`: boolean controlling filter panel visibility in React

**org_dashboard.html** replaced:
- Extends `base_org.html`, loads `django_vite`
- Embeds `regions_json|json_script:"dashboard-regions"` and `shops_json|json_script:"dashboard-shops"`
- Mounts `<div id="dashboard-root" data-is-single-shop="...">` for React island
- `{% vite_asset 'src/entrypoints/dashboard.tsx' %}` in `{% block extra_js %}`

**Vite config**: `dashboard` entry added pointing to `src/entrypoints/dashboard.tsx` (file created in plan 14-08).

**npm packages**: recharts@3.8.1 and @tanstack/react-query@5.100.9 installed as production dependencies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type error on organisation_id**
- **Found during:** Task 1 pre-commit hook (mypy strict)
- **Issue:** `user.organisation_id` typed as `int | None`, causing error at `organisation_id=org_id` Shop filter
- **Fix:** Added `or user.organisation_id is None` to the existing None guard, then typed `org_id: int`
- **Files modified:** apps/organisations/views.py
- **Commit:** 3168134

**2. [Rule N/A] Plan references apps/stores — actual project uses apps/shops**
- The plan spec referenced `apps/stores/models.py` and `apps/stores/models.Region` — these don't exist. The project uses `apps/shops/models.Shop` and `apps/regions/models.Region` (already imported in the file). Import adjusted in the view accordingly. No deviation tracking needed — auto-corrected inline.

## Self-Check

### Files exist
- [x] `templates/organisations/org_dashboard.html` — contains `id="dashboard-root"`, `dashboard-regions`, `dashboard-shops`
- [x] `apps/organisations/views.py` — contains `regions_json`, `is_single_shop`, `get_accessible_shop_ids`
- [x] `frontend/vite.config.ts` — contains `src/entrypoints/dashboard.tsx`

### Commits exist
- [x] 3168134 — feat(14-04): update org_admin_dashboard view with bootstrap context and replace dashboard template
- [x] d31d05e — chore(14-04): install recharts + @tanstack/react-query and register dashboard vite entrypoint

### Verification
- `python manage.py check` → System check identified no issues (0 silenced)
- `npm ls recharts @tanstack/react-query` → recharts@3.8.1, @tanstack/react-query@5.100.9

## Self-Check: PASSED
