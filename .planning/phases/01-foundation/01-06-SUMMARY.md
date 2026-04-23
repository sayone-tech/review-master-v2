---
phase: "01"
plan: "06"
subsystem: frontend-shell
tags: [alpine, vite, react, templates, gap-closure]
dependency_graph:
  requires: [01-04, 01-05]
  provides: [working-mobile-sidebar, react-widget-showcase]
  affects: [UAT-test-5, UAT-tests-9-12]
tech_stack:
  added: []
  patterns: [alpine-store-live-read, vite-react-refresh-preamble, extra-js-block-pattern]
key_files:
  created: []
  modified:
    - templates/partials/sidebar.html
    - templates/partials/head.html
    - templates/base.html
    - templates/pages/showcase.html
decisions:
  - "Alpine sidebar must read $store.nav.mobileOpen live — never copy store value into local x-data at mount time"
  - "{% vite_react_refresh %} must appear immediately after {% vite_hmr_client %} in head.html for @vitejs/plugin-react dev mode"
  - "{% block extra_js %} placed after </main> so script injection bypasses DOM ordering constraints from shell_close include"
  - "showcase.tsx vite_asset moved to block extra_js (not block content) so it loads after page DOM is ready"
metrics:
  duration: "~5 min"
  completed_date: "2026-04-23"
  tasks_completed: 2
  files_modified: 4
requirements_closed: [DSYS-04, DSYS-05]
---

# Phase 01 Plan 06: UAT Gap Closure — Sidebar + React Widgets Summary

**One-liner:** Fixed Alpine mobile sidebar stale-store-copy bug and added Vite React Refresh preamble so showcase.tsx React widgets mount correctly on /__ui__/.

## What Was Built

Two targeted template fixes closing UAT gaps 5, 9, 10, 11, and 12.

**Gap A — Mobile sidebar non-functional (UAT Test 5)**

The `<aside>` in `sidebar.html` was initialising a local Alpine variable `mobileOpen` by reading the store value at mount time. Subsequent store mutations from the hamburger button were never observed by the sidebar's `:class` binding. Fix: removed `mobileOpen` from `x-data`, changed `:class` to read `$store.nav?.mobileOpen` directly (live store read). The backdrop div already used the live store and was left unchanged.

**Gap B — React widgets not mounting on /__ui__/ (UAT Tests 9–12)**

Two sub-issues:

1. `{% vite_react_refresh %}` was missing from `head.html`. Without the React Refresh preamble, `@vitejs/plugin-react` aborts in dev mode before `showcase.tsx` executes. Added immediately after `{% vite_hmr_client %}`.

2. `{% vite_asset 'src/entrypoints/showcase.tsx' %}` was placed inside `{% block content %}` in `showcase.html`. This caused script loading before the showcase DOM was fully rendered. Added `{% block extra_js %}{% endblock %}` to `base.html` after `</main>`, then moved the `vite_asset` tag there in `showcase.html`.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Fix Alpine sidebar to read $store.nav.mobileOpen live | 3bcafc3 |
| 2 | Add vite_react_refresh, extra_js block, move showcase vite_asset | a8e4f6a |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files exist:
- templates/partials/sidebar.html — FOUND
- templates/partials/head.html — FOUND
- templates/base.html — FOUND
- templates/pages/showcase.html — FOUND

### Commits exist:
- 3bcafc3 — FOUND
- a8e4f6a — FOUND

## Self-Check: PASSED
