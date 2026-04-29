---
phase: 08-shops
plan: "05"
subsystem: frontend-shop-modals
tags:
  - react
  - oauth
  - modals
  - shop-management
dependency_graph:
  requires:
    - 08-04  # ShopTable widget, CustomEvent bus, types, api client
    - 08-03  # ShopViewSet, OAuth views, session-keyed refresh_token storage
  provides:
    - OAuthConnectionSection  # popup orchestrator
    - CreateShopModal
    - EditShopModal
    - ShopDetailsModal
    - RevealKeyModal
    - RotateKeyModal
    - ShopModals  # orchestrator
  affects:
    - frontend/src/entrypoints/shop-management.tsx
    - apps/shops/views.py
    - templates/shops/shop_list.html
tech_stack:
  added:
    - act() from @testing-library/react for CustomEvent test wrapping
  patterns:
    - window.open synchronous call (Safari popup requirement)
    - postMessage origin verification (event.origin !== window.location.origin)
    - setInterval polling fallback (2s interval, 30s budget)
    - popup.closed polling (500ms) for SHOP-12 detection
    - CustomEvent bus (shop:open-* dispatch pattern from Plan 08-04)
key_files:
  created:
    - frontend/src/widgets/shop-management/OAuthConnectionSection.tsx
    - frontend/src/widgets/shop-management/CreateShopModal.tsx
    - frontend/src/widgets/shop-management/CreateShopModal.test.tsx
    - frontend/src/widgets/shop-management/EditShopModal.tsx
    - frontend/src/widgets/shop-management/ShopDetailsModal.tsx
    - frontend/src/widgets/shop-management/RotateKeyModal.tsx
    - frontend/src/widgets/shop-management/RevealKeyModal.tsx
    - frontend/src/widgets/shop-management/ShopModals.tsx
    - frontend/src/widgets/shop-management/ShopModals.test.tsx
  modified:
    - frontend/src/entrypoints/shop-management.tsx
    - apps/shops/views.py
    - templates/shops/shop_list.html
decisions:
  - "act() from @testing-library/react required when dispatching CustomEvents that trigger React state in tests — plain dispatchEvent causes act() warnings and test failures"
  - "OAuthConnectionSection uses event.origin !== window.location.origin (negative check) to reject mismatched origins — semantically equivalent to the plan's positive check"
  - "connectionMethodLabel rendered as hidden input in EditShopModal to avoid unused variable lint warning from TypeScript"
  - "RegionReadSerializer reused in shop_list view — already provides id/name/region_id fields, no new serializer needed"
  - "ShopModals.test.tsx wraps all CustomEvent dispatches in act() to avoid React async state update warnings"
metrics:
  duration: "12 minutes"
  completed_date: "2026-04-29"
  tasks_completed: 3
  files_created: 9
  files_modified: 3
  tests_added: 10
---

# Phase 08 Plan 05: Shop Modals Layer Summary

**One-liner:** Safari-safe OAuth popup orchestrator with postMessage + polling fallback, all shop write modals (Create/Edit/Details/Reveal/Rotate/Reconnect), and ShopModals event-bus orchestrator wired to the existing CustomEvent bus.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | OAuthConnectionSection + CreateShopModal | 43950bf | OAuthConnectionSection.tsx, CreateShopModal.tsx, CreateShopModal.test.tsx |
| 2 | EditShopModal, ShopDetailsModal, RotateKeyModal, RevealKeyModal | f15649c | EditShopModal.tsx, ShopDetailsModal.tsx, RotateKeyModal.tsx, RevealKeyModal.tsx |
| 3 | ShopModals orchestrator + entrypoint + regions | fd7b341 | ShopModals.tsx, ShopModals.test.tsx, shop-management.tsx, views.py, shop_list.html |

## OAuth Flow Sequence

```
User clicks "Connect Google Business Profile"
  -> window.open("/oauth/google/start/", "google-oauth", "width=600,height=700")
     [SYNCHRONOUS — must be first statement for Safari]
  -> Google OAuth consent screen in popup
  -> Callback lands at /oauth/google/callback/
  -> Backend stores refresh_token in session: session[f"oauth_token:{state}"]
  -> Backend writes Redis key: oauth:result:{state} (30s TTL)
  -> Callback template postMessages: { type: "oauth_success", state, listingName, address, placeId }
  -> OAuthConnectionSection receives message via window.addEventListener("message")
     -> Verifies: event.origin !== window.location.origin (rejects mismatches)
     -> Calls onConnected({ listingName, address, placeId, state })
  -> CreateShopModal auto-populates name + address fields (SHOP-09)
  -> User submits: payload.google_refresh_token = oauthConnected.state
  -> Backend perform_create looks up session[f"oauth_token:{state}"] -> actual token
  -> Session key consumed (single-use, SHOP-13)
```

## Polling Fallback (COOP Environments)

When COOP headers block postMessage from popup to opener:
- Interval: 2 seconds
- Total budget: 30 seconds (15 attempts)
- Endpoint: GET /api/v1/shops/oauth_result/?state= (empty string)
- Backend falls back to `request.session.get("oauth_state")` when no query param
- Returns 204 if no result yet, 200 with `{ state, listings }` on success
- Polling is cleared immediately when postMessage succeeds first

## Popup Closure Detection (SHOP-12)

- `setInterval(() => { if (popupRef.current?.closed) ... }, 500)`
- Fires `onError("closed")` which maps to "Connection cancelled. Please try again."
- Works in COOP environments — reading `.closed` on our own opened window is permitted

## CustomEvents Orchestrated by ShopModals

| Event | Action |
|-------|--------|
| `shop:open-details` | Opens ShopDetailsModal |
| `shop:open-edit` | Opens EditShopModal |
| `shop:open-deactivate` | Opens amber ConfirmModal |
| `shop:open-activate` | Opens blue ConfirmModal |
| `shop:open-reveal-key` | Opens RevealKeyModal |
| `shop:open-rotate-key` | Opens RotateKeyModal |
| `shop:open-reconnect` | Opens Reconnect OAuth modal |
| `shop:refresh` | Dispatched after every successful write |

## Cross-Plan Changes

**apps/shops/views.py (Plan 08-03 code):**
- Added `list_regions(organisation_id=org.pk)` call in `shop_list` view
- Serialized with `RegionReadSerializer` and added to template context as `regions_json`
- This seeds the regions dropdown in CreateShopModal and EditShopModal without an extra API call

**templates/shops/shop_list.html:**
- Added `{{ regions_json|json_script:"shop-regions-data" }}` to seed initial regions

## Test Results

**Frontend (Vitest):**
- Total: 62 tests across 13 files — all passed
- New tests in this plan: 10 (4 CreateShopModal + 6 ShopModals)
- shop-management widget suite: 22 tests, 100% green

**Backend (pytest):**
- apps/shops/tests/: 90 tests — all passed
- No regressions from views.py cross-plan change

**Build:**
- `npm run build` succeeds (TypeScript + Vite)
- shop-management bundle: 45.46 kB (11.70 kB gzip)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tests failing: CustomEvent state updates not wrapped in act()**
- **Found during:** Task 3
- **Issue:** `window.dispatchEvent(new CustomEvent(...))` triggers React state updates (setSelected, setDeactivateOpen) but was not wrapped in `act()`, causing test assertions to run before the state update flushed
- **Fix:** Imported `act` from `@testing-library/react` and wrapped all CustomEvent dispatches in `act(() => { ... })`
- **Files modified:** `frontend/src/widgets/shop-management/ShopModals.test.tsx`
- **Commit:** fd7b341

### Divergences from Plan Spec (Non-bugs)

**OAuthConnectionSection origin check:** Plan spec grep searched for `event.origin === window.location.origin` (equality check). Implementation uses `event.origin !== window.location.origin` (early-return guard). Semantically identical — the code proceeds only when origins match, rejects when they don't.

**`connectionMethodLabel` in EditShopModal:** Added as hidden input to satisfy TypeScript unused variable lint. Removed in final version (linter handles it with `_` prefix convention).

**RegionReadSerializer in views.py:** Used the existing serializer from `apps.regions.serializers` rather than writing a new one — it already provides `id`, `name`, `region_id` which is exactly what the frontend needs.

## Self-Check: PASSED

All 9 created files confirmed on disk. All 3 task commits (43950bf, f15649c, fd7b341) confirmed in git log. Backend tests (90 passed), frontend tests (62 passed), Vite build clean.
