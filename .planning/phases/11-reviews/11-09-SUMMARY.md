---
phase: 11-reviews
plan: "09"
subsystem: ui
tags: [react, typescript, vite, django-templates, fetch-api, cursor-pagination]

# Dependency graph
requires:
  - phase: 11-06
    provides: GET /api/v1/reviews/ cursor-paginated endpoint + ReviewReadSerializer fields
  - phase: 11-07
    provides: POST /api/v1/reviews/{id}/reply/ endpoint
  - phase: 11-08
    provides: GET /api/v1/shops/syncing/ endpoint
provides:
  - ReviewRow, ReviewFilterParams, ReviewListResponse, SyncingResponse, SortKey TypeScript types
  - listReviews, submitReply, fetchSyncingShops API client functions
  - useReviews hook with 7 filters, sort, page size, cursor pagination, search debounce
  - ReviewManagementWidget stub (replaced in Plan 10)
  - review-management.tsx entrypoint mounting stub widget
  - templates/reviews/review_list.html page shell with #review-management-root
  - review-management Vite entrypoint registered
affects: [11-10, 11-11, 11-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useReviews hook pattern: fetch on mount + filter setters + cursor pagination + replaceRow for optimistic update"
    - "API client pattern: getCsrfToken + headers() + ApiError class + buildQs() — mirrors shop-management/api.ts"
    - "Entrypoint pattern: dataset attributes on root div pass Django context to React"

key-files:
  created:
    - frontend/src/widgets/review-management/types.ts
    - frontend/src/widgets/review-management/api.ts
    - frontend/src/widgets/review-management/useReviews.ts
    - frontend/src/widgets/review-management/ReviewManagementWidget.tsx
    - frontend/src/entrypoints/review-management.tsx
    - templates/reviews/review_list.html
  modified:
    - frontend/vite.config.ts

key-decisions:
  - "Template uses base_org.html + extra_js block pattern (matching shop_list.html) — not base.html with shell includes"
  - "ReviewManagementWidget stub added so Plan 09 is independently buildable; Plan 10 replaces it"
  - "useReviews initial load always calls refresh(DEFAULT_PARAMS) on mount — no server-side seeded data (unlike shops pattern)"

patterns-established:
  - "Review management widget uses #review-management-root data-* attributes for Django context injection"
  - "extractCursor() parses next/previous URLs to extract cursor param for pagination"

requirements-completed: [REVW-01, REVW-03, REVW-04, REVW-05, REVW-11]

# Metrics
duration: 2min
completed: 2026-05-02
---

# Phase 11 Plan 09: Review Management Frontend Foundation Summary

**ReviewRow types + API client (listReviews/submitReply/fetchSyncingShops) + useReviews hook with 7 filters + cursor pagination + Django template shell wired to Vite entrypoint**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-02T04:57:45Z
- **Completed:** 2026-05-02T05:00:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Typed ReviewRow interface matching Plan 06 ReviewReadSerializer exactly — all 20 fields including sentiment, enrichment_status, is_replied
- API client with CSRF-aware fetch, ApiError class, and all three required functions wired to correct backend endpoints
- useReviews hook exposing all 7 filter setters, debounced search (300ms), cursor pagination (goNext/goPrev), clearFilters, replaceRow
- Django template page shell + Vite entrypoint stub so Plans 10/11/12 have a stable mount point

## Task Commits

Each task was committed atomically:

1. **Task 1: Types + API client + Django template + Vite entry registration** - `95ba02a` (feat)
2. **Task 2: useReviews hook** - `185ea69` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `frontend/src/widgets/review-management/types.ts` — ReviewRow, ReviewFilterParams, ReviewListResponse, SortKey, SyncingResponse, ShopOption types
- `frontend/src/widgets/review-management/api.ts` — listReviews, submitReply, fetchSyncingShops with CSRF header helper
- `frontend/src/widgets/review-management/useReviews.ts` — complete hook with debounced search, cursor pagination, replaceRow
- `frontend/src/widgets/review-management/ReviewManagementWidget.tsx` — stub component (Plan 10 replaces)
- `frontend/src/entrypoints/review-management.tsx` — React mount using dataset attrs for userRole and openProgressShopId
- `templates/reviews/review_list.html` — base_org.html extension with #review-management-root div
- `frontend/vite.config.ts` — review-management entrypoint added to rollup input

## Decisions Made
- Template uses `base_org.html` + `extra_js` block pattern (matching `shop_list.html`) rather than `base.html` with shell partials — consistent with all other org admin pages
- `useReviews` always fetches on mount with DEFAULT_PARAMS (no SSR seeding) — reviews table is too dynamic for server-side pre-population to be useful
- `ReviewManagementWidget` stub added with correct props interface so Plans 10/11/12 have a stable contract to implement against

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- DjHTML pre-commit hook reformatted `review_list.html` indentation on first commit attempt — re-staged and committed successfully.

## Next Phase Readiness
- Plan 10 (ReviewTable component) can import `useReviews`, `ReviewRow`, `ReviewFilterParams` directly
- Plan 11 (ReplyComposer) can use `submitReply` from api.ts and `replaceRow` from useReviews
- Plan 12 (SyncProgress banner) can use `fetchSyncingShops` from api.ts and openProgressShopId from entrypoint

---
*Phase: 11-reviews*
*Completed: 2026-05-02*
