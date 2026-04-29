---
phase: 08-shops
plan: 04
subsystem: ui
tags: [react, typescript, tailwind, vite, vitest, custom-events]

# Dependency graph
requires:
  - phase: 08-03
    provides: ShopViewSet API endpoints, ShopReadSerializer response shape, shop_list.html placeholder, shops JSON seed in view context

provides:
  - "ConnectionStatusPill: 5-state inline pill (Google OAuth / API key / error / quota / not-connected)"
  - "ShopsEmptyStateA: no-regions empty state with Go to Regions CTA"
  - "ShopsEmptyStateB: no-shops empty state with Add your first shop CTA"
  - "ShopRowActionsMenu: three-dot dropdown typed to ShopRow dispatching 7 CustomEvents"
  - "ShopTableWidget: 9-column table with debounced search, status/region filter, pagination 10/25/50/100"
  - "useShops hook: URL ?region= pre-population, shop:refresh listener, full filter state machine"
  - "shop-management Vite bundle: entrypoint registered, build verified"
  - "shop_list.html: allocation counter (X/Y), disabled Add Shop at limit, json_script seeds, #shop-table-root, #shop-modals-root"
affects:
  - 08-05 (modals layer listens for shop:open-* CustomEvents dispatched here)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CustomEvent bus: ShopTable dispatches shop:open-{action} events; modals layer (08-05) subscribes — zero coupling between table and modal widgets"
    - "Inline hex colours for status pills: Tailwind JIT cannot purge dynamic class strings, so hex used via style prop for deterministic output"
    - "vi.stubGlobal('fetch', mock) for fetch mocking in Vitest: avoids global.fetch TypeScript error in browser-lib tsconfig"
    - "Debounced search with useRef<ReturnType<typeof setTimeout>>: avoids window.setTimeout type conflict in strict tsconfig"

key-files:
  created:
    - frontend/src/widgets/shop-management/ConnectionStatusPill.tsx
    - frontend/src/widgets/shop-management/ShopsEmptyStateA.tsx
    - frontend/src/widgets/shop-management/ShopsEmptyStateB.tsx
    - frontend/src/widgets/shop-management/ShopRowActionsMenu.tsx
    - frontend/src/widgets/shop-management/ShopTable.tsx
    - frontend/src/widgets/shop-management/ShopTable.test.tsx
  modified:
    - frontend/src/widgets/shop-management/api.test.ts
    - templates/shops/shop_list.html

key-decisions:
  - "Inline hex colours used in ConnectionStatusPill and status badge instead of Tailwind CSS tokens — Tailwind JIT cannot generate dynamic class names from string expressions; hex values are deterministic and spec-compliant"
  - "Empty State B condition: requires allocation.current === 0 AND hasRegions AND no filters — avoids false 'No shops yet' when user has shops but no matching results"
  - "Region filter dropdown derives options from current page rows (not a full region list fetch) — keeps widget self-contained; full region list fetch deferred as a TODO comment"
  - "vi.stubGlobal replaces global.fetch in api.test.ts — aligns with existing CreateOrgModal.test.tsx pattern and satisfies tsc --noEmit in browser lib mode"

patterns-established:
  - "ShopRowActionsMenu: duplication over generics — typed directly to ShopRow for clarity and simpler visible() callbacks"

requirements-completed:
  - SHOP-01
  - SHOP-02
  - SHOP-03
  - SHOP-04
  - SHOP-05
  - SHOP-06
  - SHOP-07
  - XMOD-01

# Metrics
duration: 15min
completed: 2026-04-29
---

# Phase 8 Plan 04: Shop Management React Widget Summary

**React shops list widget with 9-column DataTable, 5-state connection pills, dual empty states, three-dot action menu dispatching 7 CustomEvents, debounced search/filter/pagination, and shop_list.html fully wired to the Vite bundle**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-29T10:45:00Z
- **Completed:** 2026-04-29T10:58:00Z
- **Tasks:** 2
- **Files modified:** 8 (created 6, modified 2)

## Accomplishments

- `ShopTableWidget` mounts on `#shop-table-root` with full SHOP-04 column set, debounced search (300ms), Status/Region filters, pagination with 10/25/50/100 rows-per-page selector and "Showing X–Y of Z" display
- `ConnectionStatusPill` covers all 5 visual states using inline hex colours (no dynamic Tailwind class generation)
- `ShopRowActionsMenu` conditionally shows Reveal Key / Rotate Key for MANUAL shops and Reconnect Google for GOOGLE_OAUTH shops with ERROR/EXPIRED status; all actions dispatch window CustomEvents consumed by Plan 08-05
- `shop_list.html` upgraded with allocation counter `(X / Y)`, disabled `+ Add Shop` with tooltip at limit, all json_script data seeds, and `{% vite_asset 'shop-management' %}` tag
- Vite build succeeds, producing `shop-management-L4YzgQzF.js` (15.23 kB gzip: 5.10 kB)
- All 52 frontend tests pass (11 test files), zero regressions

## CustomEvents Emitted by ShopTable

| Event | Payload (detail) | Trigger |
|---|---|---|
| `shop:open-details` | `ShopRow` | Click shop name OR View Details menu item |
| `shop:open-edit` | `ShopRow` | Edit menu item |
| `shop:open-deactivate` | `ShopRow` | Deactivate (when `is_active=true`) |
| `shop:open-activate` | `ShopRow` | Activate (when `is_active=false`) |
| `shop:open-reveal-key` | `ShopRow` | Reveal Key (MANUAL shops only) |
| `shop:open-rotate-key` | `ShopRow` | Rotate Key (MANUAL shops only) |
| `shop:open-reconnect` | `ShopRow` | Reconnect Google (GOOGLE_OAUTH + ERROR/EXPIRED only) |

Plan 08-05 mounts on `#shop-modals-root` and subscribes to these events.

## Tailwind Colour Tokens vs Hex Fallbacks

| State | Approach | Value |
|---|---|---|
| Connected via Google | inline style | `bg: #F0FDF4`, `text/dot: #16A34A` |
| Connected via API key | inline style | `bg: #EFF6FF`, `text/dot: #2563EB` |
| Connection error | inline style | `bg: #FEF2F2`, `text/dot: #DC2626` |
| Quota exceeded | inline style | `bg: #FFFBEB`, `text/dot: #D97706` |
| Not connected | inline style | `bg: #F9FAFB`, `text/dot: #6B7280` |
| Active badge | inline style | `bg: #F0FDF4`, `text: #16A34A` |
| Inactive badge | inline style | `bg: #F9FAFB`, `text: #6B7280` |

Hex used throughout because Tailwind JIT cannot purge dynamic class names from ternary expressions.

## Task Commits

1. **Task 1: Types, API client, useShops hook, Vite config, entrypoint** — `f25c561` (feat)
2. **Task 2: ConnectionStatusPill, empty states, ShopRowActionsMenu, ShopTable, template** — `820cbf6` (feat)

## Files Created/Modified

- `frontend/src/widgets/shop-management/types.ts` — ConnectionMethod, ConnectionStatus, ShopRow, AllocationStatus, ShopsListResponse, ShopCreatePayload, ShopUpdatePayload, RotateKeyPayload, RevealKeyResponse, ShopFilterParams
- `frontend/src/widgets/shop-management/api.ts` — 9 API functions with CSRF helper and handle()
- `frontend/src/widgets/shop-management/useShops.ts` — hook with URL ?region= pre-population, shop:refresh listener, full filter+pagination state machine
- `frontend/src/widgets/shop-management/api.test.ts` — 3 Vitest tests; fixed global.fetch → vi.stubGlobal
- `frontend/src/widgets/shop-management/useShops.test.tsx` — 2 Vitest tests (setSearch, region pre-population from URL)
- `frontend/src/entrypoints/shop-management.tsx` — mounts ShopTableWidget on #shop-table-root; #shop-modals-root left for 08-05
- `frontend/vite.config.ts` — shop-management entry registered in rollupOptions.input
- `frontend/src/widgets/shop-management/ConnectionStatusPill.tsx` — 5-state pill with inline hex colours
- `frontend/src/widgets/shop-management/ShopsEmptyStateA.tsx` — no-regions card (Map icon + Go to Regions link)
- `frontend/src/widgets/shop-management/ShopsEmptyStateB.tsx` — no-shops card (Store icon + id=open-create-shop-empty button)
- `frontend/src/widgets/shop-management/ShopRowActionsMenu.tsx` — ShopRow-typed duplicate of org-management/RowActionsMenu
- `frontend/src/widgets/shop-management/ShopTable.tsx` — ShopTableWidget with 9 columns, filters, pagination, empty-state branching
- `frontend/src/widgets/shop-management/ShopTable.test.tsx` — 7 Vitest tests covering pills, empty states, CustomEvents, Reveal Key visibility
- `templates/shops/shop_list.html` — full page template with allocation counter, Add Shop button (disabled at limit), json_script seeds, vite_asset

## Decisions Made

- Inline hex colours in status pills and badges instead of Tailwind tokens — Tailwind JIT cannot generate dynamic class names; hex values are deterministic and spec-compliant
- Empty State B triggers only when `allocation.current === 0` (not just `rows.length === 0`) — prevents the empty state showing when user's page is filtered to zero but shops exist
- Region filter dropdown derives options from current page rows, not a full API fetch — TODO left in code comment for future follow-up
- `vi.stubGlobal("fetch", mock)` replaces `global.fetch =` in api.test.ts — browser lib tsconfig mode doesn't define `global`; `vi.stubGlobal` is the Vitest-idiomatic approach and matches CreateOrgModal.test.tsx

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed api.test.ts `global.fetch` → `vi.stubGlobal`**
- **Found during:** Task 2 verification (npm run build → tsc --noEmit)
- **Issue:** `api.test.ts` used `global.fetch = ...` which TypeScript rejects in browser lib mode (`Cannot find name 'global'`); build blocked
- **Fix:** Replaced all 3 occurrences of `global.fetch = mock` with `vi.stubGlobal("fetch", mock)` — idiomatic Vitest pattern that works in jsdom environment
- **Files modified:** `frontend/src/widgets/shop-management/api.test.ts`
- **Verification:** `npm run build` succeeds; all 3 api.test.ts tests still pass
- **Committed in:** `820cbf6` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug fix)
**Impact on plan:** Required for build to pass. No scope creep.

## Issues Encountered

None beyond the auto-fixed TypeScript error.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- Shop list page fully functional: search, filter, pagination, connection status pills, empty states, three-dot action menu
- All 7 CustomEvents defined and dispatched; Plan 08-05 can subscribe immediately
- `#shop-modals-root` div is present in the DOM, ready for Plan 08-05 to mount the modals widget
- Vite bundle `shop-management` verified in production build

---
*Phase: 08-shops*
*Completed: 2026-04-29*
