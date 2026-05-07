---
phase: 14-dashboard
plan: 08
subsystem: ui
tags: [react, dashboard, tailwind, typescript, vite, tanstack-query, error-pages]

# Dependency graph
requires:
  - phase: 14-05
    provides: FilterBar, useFilterState, DashboardFilters types
  - phase: 14-06
    provides: TopPerformingSection, PerformanceHighlights, YourStore widgets
  - phase: 14-07
    provides: KpiCards, SentimentDonut widgets

provides:
  - DashboardWidget React root component with QueryClientProvider + two-filter-objects pattern
  - dashboard.tsx Vite entrypoint mounting DashboardWidget via createRoot
  - templates/404.html branded not-found page with auth-aware CTA
  - templates/500.html branded server-error page with auth-aware CTA

affects: [frontend-build, error-handling, dashboard-template]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "two-filter-objects: fullFilters for KpiCards+SentimentDonut, dateOnlyFilters for TopPerformingSection+Highlights+YourStore (DASH-C2 prevention)"
    - "readBootstrap: reads regions/shops/isSingleShop from DOM script tags on mount via useMemo"
    - "standalone error templates: no base_org.html, own CSS link, auth-aware CTA via request.user.is_authenticated"

key-files:
  created:
    - frontend/src/widgets/dashboard/DashboardWidget.tsx
    - frontend/src/entrypoints/dashboard.tsx
    - templates/404.html
    - templates/500.html
  modified:
    - frontend/src/widgets/dashboard/index.ts

key-decisions:
  - "DashboardWidget wraps DashboardInner in QueryClientProvider; queryClient is module-level singleton to survive re-renders"
  - "readBootstrap called inside useMemo with [] to read DOM once on mount — safe since script tags are static"
  - "shopNameIfSingle derived from bootstrap.shops[0].name only when isSingleShop && shops.length===1"
  - "StrictMode added to dashboard entrypoint, matching pattern from org-management.tsx"
  - "Error templates use static CSS (css/tailwind.css) not django_vite tag — safe for error page rendering when vite manifest may not be loaded"

patterns-established:
  - "two-filter-objects pattern: fullFilters vs dateOnlyFilters derived from useFilterState"
  - "standalone error page: {% load static %} + own head, no template inheritance"

requirements-completed:
  - FILT-01
  - FILT-02
  - FILT-03
  - FILT-04
  - FILT-05
  - FILT-06
  - FILT-07
  - STORE-01
  - TECH-05
  - TECH-06
  - ERR-01
  - ERR-02

# Metrics
duration: 5min
completed: 2026-05-07
---

# Phase 14 Plan 08: Dashboard Final Wiring Summary

**React DashboardWidget root composing all 5 widgets under one QueryClientProvider with two-filter-objects DASH-C2 prevention, Vite entrypoint via createRoot, and branded 404/500 error pages with auth-aware CTAs**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-07T08:58:00Z
- **Completed:** 2026-05-07T09:00:24Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- DashboardWidget reads bootstrap data from DOM script tags (regions/shops/isSingleShop) via useMemo on mount
- Two-filter-objects pattern: fullFilters passed to KpiCards+SentimentDonut; dateOnlyFilters passed to TopPerformingSection/PerformanceHighlights/YourStore (prevents DASH-C2 cross-contamination)
- isSingleShop branching: YourStore replaces TopPerformingSection+PerformanceHighlights for single-shop tenants
- dashboard.tsx entrypoint mounts DashboardWidget via React 19 createRoot + StrictMode; vite build succeeds
- Branded 404 and 500 standalone templates with logo, auth-aware CTA, no template inheritance

## Task Commits

Each task was committed atomically:

1. **Task 1: DashboardWidget + entrypoint** - `630c7e5` (feat)
2. **Task 2: Branded 404 + 500 templates** - `653516a` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `frontend/src/widgets/dashboard/DashboardWidget.tsx` - React root with QueryClientProvider, bootstrap reading, filter composition, isSingleShop branching
- `frontend/src/entrypoints/dashboard.tsx` - Vite entrypoint mounting DashboardWidget via createRoot + StrictMode
- `frontend/src/widgets/dashboard/index.ts` - Added DashboardWidget export
- `templates/404.html` - Branded 404 standalone page with auth-aware CTA
- `templates/500.html` - Branded 500 standalone page with auth-aware CTA

## Decisions Made
- queryClient defined at module level (outside component) to prevent recreation on re-renders
- readBootstrap wrapped in useMemo([]) — DOM script tags are static, safe to read once
- Error templates use `{% static 'css/tailwind.css' %}` directly (not django_vite tag) for reliability during error rendering
- StrictMode added to entrypoint, consistent with org-management.tsx pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- DjHTML pre-commit hook auto-reformatted 404.html and 500.html indentation on first commit attempt; re-staged and committed successfully on second attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 5 dashboard widgets are wired under DashboardWidget with shared filter state
- Error pages complete the user-facing surface for Phase 14
- Phase 14 (dashboard) is now fully implemented: backend APIs (plans 01-04) + frontend widgets (plans 05-07) + root component + error pages (plan 08)
- 40 backend tests pass; Vite build succeeds with dashboard entry

---
*Phase: 14-dashboard*
*Completed: 2026-05-07*
