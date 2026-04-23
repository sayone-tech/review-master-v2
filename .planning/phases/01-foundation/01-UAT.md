---
status: diagnosed
phase: 01-foundation
source: 01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md
started: 2026-04-23T12:40:00Z
updated: 2026-04-23T13:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch with `docker-compose up -d`. All 5 services (web, db, redis, mailhog, vite) should start without errors. Migrations should run automatically on startup. Visit http://localhost:8000/healthz/ — it should return {"status": "ok"}.
result: pass

### 2. Health Endpoints
expected: Visit http://localhost:8000/healthz/ — returns JSON {"status": "ok"} with HTTP 200. Visit http://localhost:8000/readyz/ — returns JSON with status/database/cache fields and HTTP 200 when all dependencies are healthy.
result: pass

### 3. Home Page Shell Renders
expected: Visit http://localhost:8000/ — page loads with a black sidebar (240px wide on desktop) on the left and a light-grey/white main content area on the right. The page should not be blank or show a Django error. Geist font should load (text should look clean/modern).
result: pass

### 4. Sidebar Desktop Layout
expected: On a desktop browser (≥1280px), the sidebar is 240px wide with a black background. It contains nav items. At tablet width (~768px), the sidebar collapses to a narrow 64px rail showing only icons. At mobile width (~375px), the sidebar is hidden entirely and a hamburger menu button appears in the topbar.
result: pass

### 5. Mobile Sidebar Drawer
expected: On mobile width (resize browser to ~375px), the sidebar is hidden. Click the hamburger icon in the topbar — the sidebar should slide in as a drawer overlay. Clicking the backdrop or a nav item should close it.
result: issue
reported: "in mobile i can see a button on the top to invoke the sidebar but it is not working"
severity: major

### 6. Topbar Avatar Dropdown
expected: The topbar shows a notification bell icon and a user avatar/initials button. Clicking the avatar opens a dropdown menu with the user's name, role, and a "Sign out" link. Clicking outside the dropdown or pressing Escape should close it.
result: pass

### 7. Logout Stub
expected: Click "Sign out" in the avatar dropdown (or navigate to http://localhost:8000/logout/). The page should redirect to http://localhost:8000/ without an error. This is a Phase 1 stub — full session clearing comes in Phase 2.
result: pass

### 8. Component Showcase Page
expected: Visit http://localhost:8000/__ui__/ — page loads and shows all design system components rendered side-by-side: buttons (primary/secondary/danger/ghost), form fields (text/email/password/select), badges (7 colour variants), empty state, skeleton loaders, filter bar, pagination, and a React widget mount area.
result: pass

### 9. Modal Widget
expected: On the /__ui__/ showcase page, there should be a button to open the Modal. Clicking it opens a modal dialog with a title, close button (×), and dismisses on Escape key. Clicking the dark backdrop also closes it. While open, focus should be trapped inside the modal (Tab key cycles through modal elements only).
result: issue
reported: "no such button in the UI"
severity: major

### 10. ConfirmModal Type-to-Confirm
expected: On the /__ui__/ showcase page, there should be a ConfirmModal demo. The modal shows a confirmation prompt with a text input. The confirm button should be disabled until you type the exact required string into the input. Typing the correct text enables the button; clearing it disables it again.
result: issue
reported: "no such button or modal in that page"
severity: major

### 11. DataTable States
expected: On the /__ui__/ showcase page, the DataTable demo should show three states: (1) loading skeleton — 6 animated skeleton rows with a pulsing animation, (2) empty state — an empty state illustration/message when no data, (3) populated rows — actual data rows with a row-actions button that appears on hover.
result: issue
reported: "this is also missig"
severity: major

### 12. Toast Notification
expected: On the /__ui__/ showcase page, there should be a button to trigger a toast. Clicking it shows a toast notification (success/error/info/warning) that appears at the bottom/corner of the screen and auto-dismisses after a few seconds. Multiple toasts should stack.
result: issue
reported: "this is also missign in this page"
severity: major

## Summary

total: 12
passed: 7
issues: 5
pending: 0
skipped: 0

## Gaps

- truth: "Clicking the hamburger button on mobile opens the sidebar as a drawer overlay"
  status: failed
  reason: "User reported: in mobile i can see a button on the top to invoke the sidebar but it is not working"
  severity: major
  test: 5
  root_cause: "sidebar.html copies $store.nav.mobileOpen into a local Alpine variable at mount time; the :class binding reads the stale local copy instead of the live store, so hamburger clicks (which correctly mutate the store) never cause the sidebar to show"
  artifacts:
    - path: "templates/partials/sidebar.html"
      issue: "x-data on <aside> initialises local mobileOpen copy; :class reads that stale local instead of $store.nav.mobileOpen"
  missing:
    - "Remove mobileOpen from x-data on <aside>; change :class to read $store.nav.mobileOpen directly"
  debug_session: ".planning/debug/mobile-sidebar-hamburger-no-open.md"

- truth: "The /__ui__/ showcase page has a button to open the Modal widget"
  status: failed
  reason: "User reported: no such button in the UI"
  severity: major
  test: 9
  root_cause: "{% vite_react_refresh %} tag is missing from head.html; in dev mode @vitejs/plugin-react refuses to boot without the React Refresh preamble, so showcase.tsx never executes and the React root never mounts"
  artifacts:
    - path: "templates/partials/head.html"
      issue: "{% vite_react_refresh %} tag is missing; only {% vite_hmr_client %} is present"
    - path: "templates/pages/showcase.html"
      issue: "{% vite_asset 'src/entrypoints/showcase.tsx' %} is inside {% block content %} instead of a dedicated extra_js block after </main>"
  missing:
    - "Add {% vite_react_refresh %} immediately after {% vite_hmr_client %} in templates/partials/head.html"
    - "Move {% vite_asset 'src/entrypoints/showcase.tsx' %} out of {% block content %} into a {% block extra_js %} slot rendered after </main> in base.html"
  debug_session: ""

- truth: "The /__ui__/ showcase page has a ConfirmModal demo with type-to-confirm gate"
  status: failed
  reason: "User reported: no such button or modal in that page"
  severity: major
  test: 10
  root_cause: "Same root cause as test 9 — React entrypoint never mounts due to missing {% vite_react_refresh %}"
  artifacts: []
  missing: []
  debug_session: ""

- truth: "The /__ui__/ showcase page shows DataTable in loading skeleton, empty, and populated states"
  status: failed
  reason: "User reported: this is also missig"
  severity: major
  test: 11
  root_cause: "Same root cause as test 9 — React entrypoint never mounts due to missing {% vite_react_refresh %}"
  artifacts: []
  missing: []
  debug_session: ""

- truth: "The /__ui__/ showcase page has a button to trigger a toast notification"
  status: failed
  reason: "User reported: this is also missign in this page"
  severity: major
  test: 12
  root_cause: "Same root cause as test 9 — React entrypoint never mounts due to missing {% vite_react_refresh %}"
  artifacts: []
  missing: []
  debug_session: ""
