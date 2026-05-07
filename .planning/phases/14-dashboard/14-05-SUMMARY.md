---
phase: 14-dashboard
plan: "05"
subsystem: frontend/dashboard
tags: [react, typescript, filter-state, url-sync, session-storage]
dependency_graph:
  requires: ["14-04"]
  provides: ["frontend/src/widgets/dashboard/types.ts", "frontend/src/widgets/dashboard/api.ts", "frontend/src/widgets/dashboard/useFilterState.ts", "frontend/src/widgets/dashboard/FilterBar.tsx", "frontend/src/widgets/dashboard/index.ts"]
  affects: ["14-06", "14-07", "14-08"]
tech_stack:
  added: []
  patterns: ["controlled FilterBar component", "URL-precedence filter state", "sessionStorage persistence", "date-only query string (DASH-C2 prevention)"]
key_files:
  created:
    - frontend/src/widgets/dashboard/types.ts
    - frontend/src/widgets/dashboard/api.ts
    - frontend/src/widgets/dashboard/useFilterState.ts
    - frontend/src/widgets/dashboard/FilterBar.tsx
    - frontend/src/widgets/dashboard/index.ts
  modified: []
decisions:
  - "buildDateOnlyQs used for top-performing/highlights/your-store endpoints — no region/shop params (DASH-C2 prevention)"
  - "history.replaceState (not pushState) to sync filter state to URL — no history pollution (FILT-06)"
  - "URL params take strict precedence over sessionStorage on mount (FILT-07)"
  - "FilterBar is a pure controlled component — receives filters + callbacks; all state in useFilterState"
metrics:
  duration_minutes: 1
  completed_date: "2026-05-07"
  tasks_completed: 3
  files_created: 5
  files_modified: 0
---

# Phase 14 Plan 05: Dashboard Filter Bar + Type Contracts Summary

React filter bar with TypeScript type contracts, API fetch wrappers, URL+sessionStorage filter state hook, and controlled FilterBar component — canonical contracts consumed by plans 14-06, 14-07, 14-08.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Define types.ts + api.ts (contracts and fetch wrappers) | 71115dc |
| 2 | Implement useFilterState hook (URL + sessionStorage + presets) | d45739a |
| 3 | Implement FilterBar component + barrel index.ts | 81a976f |

## What Was Built

### types.ts
Canonical TypeScript interfaces: `Region`, `Shop`, `DateRangePreset`, `DashboardFilters`, `KpisResponse`, `SentimentResponse`, `TopPerformingResponse`, `HighlightsResponse`, `YourStoreResponse`, `DashboardBootstrap`. Keys match the Python selector return dicts exactly.

### api.ts
Five async fetch wrappers:
- `fetchKpis` + `fetchSentiment` use `buildFullQs` (region + store + date params)
- `fetchTopPerforming` + `fetchHighlights` + `fetchYourStore` use `buildDateOnlyQs` (date params only — enforces DASH-C2 at the call site)
- `ApiError` class with `status` + `message`; generic `handle<T>` for error extraction

### useFilterState.ts
- `useState` initialiser reads URL params first, falls back to sessionStorage, then defaults (FILT-07)
- `syncToUrl` calls `window.history.replaceState` — no `pushState` (FILT-06)
- `presetToAbsoluteDates` converts 7d/30d/90d presets to UTC ISO date strings
- `DEFAULT_FILTERS` exported as the canonical default state (30d preset)
- `isDefault` helper for Clear Filters disabled state
- `clearOutOfScope(kind)` for 403 inline filter error recovery

### FilterBar.tsx
Controlled component receiving `filters`, `regions`, `shops`, and action callbacks:
- Region select (`aria-label="Filter by region"`) — default "All Regions"
- Store select (`aria-label="Filter by store"`) — cascades from selected region
- Date Range select (`aria-label="Filter by date range"`) — 7d/30d/90d/Custom range
- Custom date panel (absolutely positioned, conditionally rendered when `range === "custom"`) with two date inputs, inline error, Apply button
- Client-side validation: from > to → "End date must be after start date.", span > 365d → "Date range cannot exceed 365 days."
- Clear Filters button disabled with `opacity-40 cursor-not-allowed pointer-events-none` when at defaults
- "All dates in UTC" notice `ml-auto self-center`

### index.ts
Barrel re-exporting all public symbols for downstream plan consumption.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created:
- frontend/src/widgets/dashboard/types.ts: FOUND
- frontend/src/widgets/dashboard/api.ts: FOUND
- frontend/src/widgets/dashboard/useFilterState.ts: FOUND
- frontend/src/widgets/dashboard/FilterBar.tsx: FOUND
- frontend/src/widgets/dashboard/index.ts: FOUND

Commits:
- 71115dc: feat(14-05): define dashboard types.ts and api.ts contracts — FOUND
- d45739a: feat(14-05): implement useFilterState hook — FOUND
- 81a976f: feat(14-05): implement FilterBar component and barrel index.ts — FOUND

TypeScript: `npx tsc --noEmit` exits 0 — PASSED
