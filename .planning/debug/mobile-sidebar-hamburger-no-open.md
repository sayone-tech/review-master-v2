---
status: investigating
trigger: "Mobile sidebar hamburger button is visible but clicking it does nothing — the sidebar drawer doesn't open"
created: 2026-04-23T00:00:00Z
updated: 2026-04-23T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — sidebar has its own disconnected x-data scope that initialises mobileOpen from a one-time snapshot of $store.nav.mobileOpen, so store mutations via the hamburger button never flow into the sidebar's local mobileOpen variable
test: Traced data-flow from hamburger @click through Alpine store to sidebar :class binding
expecting: The :class binding reads local mobileOpen (stale), not $store.nav.mobileOpen (live)
next_action: DONE — root cause confirmed, returning diagnosis

## Symptoms

expected: On mobile (~375px), clicking the hamburger button sets Alpine.store('nav').mobileOpen = true, causing sidebar to appear as drawer overlay
actual: Button is visible but clicking it has no effect — sidebar stays hidden
errors: none reported
reproduction: Open app on mobile (~375px viewport), click hamburger button in topbar
started: unknown

## Eliminated

- hypothesis: app-shell.ts not loaded / Vite build missing
  evidence: static/dist/manifest.json exists and maps src/entrypoints/app-shell.ts → assets/app-shell-Cr_1Bw7o.js; head.html loads it via {% vite_asset %}
  timestamp: 2026-04-23

- hypothesis: Store name mismatch between registration and usage
  evidence: app-shell.ts registers Alpine.store("nav", ...), hamburger uses $store.nav.mobileOpen, backdrop uses $store.nav.mobileOpen — all consistent
  timestamp: 2026-04-23

- hypothesis: x-cloak blocks the sidebar from ever becoming visible
  evidence: [x-cloak] { display: none !important } is present; this is correct behaviour — Alpine removes x-cloak once it initialises. Not the cause.
  timestamp: 2026-04-23

## Evidence

- timestamp: 2026-04-23
  checked: templates/partials/topbar.html line 15
  found: @click="$store.nav.mobileOpen = true" — correct, directly mutates the Alpine store
  implication: The click handler itself is correct

- timestamp: 2026-04-23
  checked: templates/partials/sidebar.html lines 3 and 12
  found: x-data="{ mobileOpen: $store.nav?.mobileOpen ?? false, collapsed: false }" and :class="mobileOpen ? '!flex !fixed !w-[260px]' : ''"
  implication: The sidebar initialises a LOCAL variable mobileOpen that copies the store value at mount time (always false). The :class binding reads this LOCAL variable, not $store.nav.mobileOpen. When the hamburger button mutates $store.nav.mobileOpen, the local mobileOpen variable in the sidebar's scope is never updated — the :class condition stays false forever.

- timestamp: 2026-04-23
  checked: templates/partials/sidebar.html line 77
  found: backdrop uses x-show="$store.nav?.mobileOpen" (reads store directly)
  implication: The BACKDROP correctly reads the store live. The sidebar itself does not — proving the split: backdrop would appear when the button is clicked, but the sidebar would not open. This is the smoking gun confirming the root cause.

- timestamp: 2026-04-23
  checked: templates/partials/shell_open.html line 2
  found: <div class="min-h-screen flex" x-data> — outer wrapper has x-data with no store reference
  implication: The outer wrapper does not interfere; it is a valid Alpine scope container. Not a contributing factor.

- timestamp: 2026-04-23
  checked: static/dist/manifest.json
  found: app-shell.ts is present as an entry point with built output
  implication: Alpine and the store registration ARE loaded in production mode; this is not a build problem

## Resolution

root_cause: sidebar.html initialises a disconnected local Alpine variable `mobileOpen` from a one-time snapshot of the store value at mount time, then binds :class to that local variable instead of reading $store.nav.mobileOpen live — so store mutations from the hamburger button never update the sidebar's :class condition
fix: Replace the sidebar's :class binding to read $store.nav.mobileOpen directly (and remove the local mobileOpen copy), OR use x-bind:class="$store.nav.mobileOpen ? '...' : ''" and remove it from x-data entirely
verification:
files_changed: [templates/partials/sidebar.html]
