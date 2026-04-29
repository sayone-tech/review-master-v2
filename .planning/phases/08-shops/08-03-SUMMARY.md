---
phase: 08-shops
plan: 03
subsystem: shops/api
tags: [drf, viewset, oauth, coop, serializers, tests, security, tenant-isolation]
dependency_graph:
  requires:
    - 08-02 (shop services + selectors)
    - 07-02 (region services — RegionFactory used in tests)
    - 06-02 (TenantScopedViewSet, IsOrgScoped, IsOrgAdmin)
  provides:
    - ShopViewSet at /api/v1/shops/
    - GoogleOAuthStartView at /oauth/google/start/
    - GoogleOAuthCallbackView at /oauth/google/callback/
    - shop_list template view at /admin/org/shops/
    - ShopReadSerializer, ShopCreateSerializer, ShopUpdateSerializer, RotateKeySerializer
  affects:
    - config/urls.py (ShopViewSet registered, apps.shops.urls included)
    - apps/organisations/urls.py (shop_list replaces org_stub_view)
tech_stack:
  added: []
  patterns:
    - TenantScopedViewSet with allocation_status + has_regions in list envelope
    - OAuth state->session token resolution in perform_create (SHOP-13 pattern)
    - Cross-Origin-Opener-Policy per-view header on OAuth views only
    - gitleaks:allow on test constant declarations for fake API keys
key_files:
  created:
    - apps/shops/serializers.py
    - apps/shops/views.py
    - apps/shops/urls.py
    - apps/shops/tests/test_views.py
    - templates/shops/shop_list.html
    - templates/shops/oauth/start.html
    - templates/shops/oauth/callback.html
  modified:
    - apps/organisations/urls.py (shop_list replaces org_stub_view)
    - config/urls.py (ShopViewSet + apps.shops.urls registered)
decisions:
  - "ShopViewSet includes RetrieveModelMixin so GET /api/v1/shops/{id}/ returns 404 on cross-tenant (not 405)"
  - "Test API keys extracted to module-level constants with # gitleaks:allow to pass secret scanner"
  - "ShopUpdateSerializer LOCKED_FIELDS validate() raises field errors (not silently drops extra fields)"
  - "Redis best-effort in OAuth callback: postMessage is primary path, Redis failure is non-fatal"
metrics:
  duration_minutes: 23
  completed_date: "2026-04-29"
  tasks_completed: 2
  files_created: 7
  files_modified: 2
---

# Phase 8 Plan 03: Shop Views, Serializers, and OAuth Layer Summary

Wired the shop services layer to HTTP via DRF `ShopViewSet` with allocation envelope, COOP-scoped OAuth views with session-based token resolution, and full integration test suite proving no cross-tenant leakage and no N+1.

## API Endpoint Table

| URL Pattern | Methods | View Name | Requirements |
|---|---|---|---|
| `/api/v1/shops/` | GET | `ShopViewSet.list` | SHOP-01, SHOP-06, XMOD-04 |
| `/api/v1/shops/` | POST | `ShopViewSet.create` | SHOP-08, SHOP-10, SHOP-13, SHOP-14 |
| `/api/v1/shops/{id}/` | GET | `ShopViewSet.retrieve` | Cross-tenant isolation |
| `/api/v1/shops/{id}/` | PATCH | `ShopViewSet.partial_update` | SHOP-16 |
| `/api/v1/shops/{id}/activate/` | POST | `ShopViewSet.activate` | SHOP-17 |
| `/api/v1/shops/{id}/deactivate/` | POST | `ShopViewSet.deactivate` | SHOP-18 |
| `/api/v1/shops/{id}/reveal_key/` | POST | `ShopViewSet.reveal_key` | SHOP-19 |
| `/api/v1/shops/{id}/rotate_key/` | POST | `ShopViewSet.rotate_key` | SHOP-20 |
| `/api/v1/shops/{id}/reconnect/` | POST | `ShopViewSet.reconnect` | SHOP-21 |
| `/api/v1/shops/oauth_result/` | GET | `ShopViewSet.oauth_result` | SHOP-11 polling |
| `/oauth/google/start/` | GET | `GoogleOAuthStartView` | SHOP-11 |
| `/oauth/google/callback/` | GET, POST | `GoogleOAuthCallbackView` | SHOP-11, SHOP-12 |
| `/admin/org/shops/` | GET | `shop_list` | XMOD-01 |

## Custom @action Endpoints

| Action | URL | Method | Requirement |
|---|---|---|---|
| `activate` | `/{id}/activate/` | POST | SHOP-17 — sets is_active=True |
| `deactivate` | `/{id}/deactivate/` | POST | SHOP-18 — sets is_active=False |
| `reveal_key` | `/{id}/reveal_key/` | POST | SHOP-19 — returns decrypted api_key + audit log |
| `rotate_key` | `/{id}/rotate_key/` | POST | SHOP-20 — validates + replaces api_key |
| `reconnect` | `/{id}/reconnect/` | POST | SHOP-21 — replaces OAuth refresh token |
| `oauth_result` | `/oauth_result/` | GET | SHOP-11 — Redis polling fallback; state from session when no query param |

## Query Count Ceiling (XMOD-04)

List endpoint with 25 shops: ceiling set to 10, actual measured below ceiling. Auth (1), session (1), org (1), shops+select_related (1), pagination count (1), allocation count (1), has_regions exists check (1) = 7 core queries. 3 headroom allows for session/cache variations.

## Serializers

| Serializer | Purpose | Key Constraints |
|---|---|---|
| `ShopReadSerializer` | List/detail responses | Excludes `google_refresh_token` and `api_key` raw fields (SHOP-13); exposes `api_key_masked` only |
| `ShopCreateSerializer` | POST body validation | Region scoped to user's org in `__init__`; write-only fields for token + api_key |
| `ShopUpdateSerializer` | PATCH body validation | `LOCKED_FIELDS` validate() rejects `connection_method`, `place_id`, `google_refresh_token`, `api_key` changes with field errors (SHOP-16) |
| `RotateKeySerializer` | Rotate key body | `new_api_key` min 10 chars, write-only |

## OAuth State -> Token Resolution (SHOP-13 Security Pattern)

The frontend sends the OAuth `state` string in the `google_refresh_token` field (never the raw token). `ShopViewSet.perform_create` resolves the actual token from `request.session[f"oauth_token:{state}"]` and deletes it after use (single-use, via `contextlib.suppress(KeyError)`). This guarantees the refresh token never crosses the browser boundary.

## Cross-Tenant Test Results

`TestShopsCrossTenantIsolation` verifies 4 isolation scenarios:
- `test_admin_a_cannot_list_org_b_shops`: list returns only own-org shops
- `test_admin_a_get_org_b_shop_returns_404`: GET detail returns 404 (not 403 or 200)
- `test_admin_a_patch_org_b_shop_returns_404`: PATCH returns 404
- `test_admin_a_deactivate_org_b_shop_returns_404`: POST action returns 404

Isolation mechanism: `TenantScopedViewSet.get_queryset()` filters by `organisation_id`; `get_object()` raises 404 when cross-tenant PK is not in scoped queryset.

## Test Suite Summary

| Test Class | Tests | Covers |
|---|---|---|
| `TestShopsListAllocation` | 4 | SHOP-01 allocation envelope |
| `TestShopSerializerFields` | 4 | SHOP-13 encrypted field omission |
| `TestShopsApiCreate` | 8 | SHOP-08/14 create + error mapping |
| `TestShopsApiCreateOAuthStateResolution` | 3 | SHOP-13 session state resolution |
| `TestShopsApiUpdate` | 4 | SHOP-16 locked field rejection |
| `TestShopsApiActions` | 8 | SHOP-17/18/19/20/21 custom actions |
| `TestShopsListQueryCountCeiling` | 1 | XMOD-04 no N+1 |
| `TestShopsCrossTenantIsolation` | 4 | Cross-tenant 404 isolation |
| `TestOAuthStartView` | 3 | SHOP-11 COOP + session + redirect |
| `TestOAuthCallbackView` | 5 | SHOP-11/12 picker/auto-close/error |
| `TestOAuthResultEndpoint` | 3 | SHOP-11 polling fallback |
| `TestShopsListPagination` | 2 | SHOP-06 page_size=10 default |
| **Total** | **49** | |

Coverage: 89.58% (above 85% threshold).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RetrieveModelMixin missing from ShopViewSet**
- **Found during:** Task 2 (cross-tenant GET test expected 404, got 405)
- **Issue:** Plan's viewset spec omitted `RetrieveModelMixin`; without it, `GET /api/v1/shops/{id}/` returns 405 Method Not Allowed instead of 404 for cross-tenant requests
- **Fix:** Added `mixins.RetrieveModelMixin` to ShopViewSet inheritance chain
- **Files modified:** `apps/shops/views.py`
- **Commit:** 3cb4cd2

**2. [Rule 1 - Bug] Wrong patch target for mock in OAuth state resolution test**
- **Found during:** Task 2 first test run
- **Issue:** Test patched `apps.shops.services.shops.create_shop` but view imports and uses it via `apps.shops.views.create_shop` — mock wasn't intercepted
- **Fix:** Changed patch target to `apps.shops.views.create_shop`
- **Files modified:** `apps/shops/tests/test_views.py`
- **Commit:** 3cb4cd2

**3. [Rule 3 - Linting] Ruff SIM105 + Bandit B110 violations**
- **Found during:** Pre-commit hook at Task 1 commit
- **Issue:** `try/except KeyError: pass` in perform_create and reconnect actions; bare `except Exception: pass` for Redis in callback
- **Fix:** Used `contextlib.suppress(KeyError)` for KeyError cases; added `logger.warning()` + `# noqa: BLE001` for the Redis best-effort block
- **Files modified:** `apps/shops/views.py`
- **Commit:** ef67a5c

**4. [Rule 3 - Linting] Mypy union-attr errors on user.organisation access**
- **Found during:** Pre-commit mypy hook at Task 1 commit
- **Issue:** `request.user` is `User | AnonymousUser` so `.organisation` access fails mypy type check
- **Fix:** Added `isinstance(user, User) or user.organisation is None` guards in `list()` and `perform_create()`
- **Files modified:** `apps/shops/views.py`
- **Commit:** ef67a5c

**5. [Rule 3 - Secret Scanner] Gitleaks false positives on test API keys**
- **Found during:** Pre-commit gitleaks hook at Task 2 commit
- **Issue:** Test API key strings (`AIzaXYZ...`) triggered gitleaks generic-api-key rule
- **Fix:** Extracted all test API keys to module-level constants with `# gitleaks:allow` on each constant line
- **Files modified:** `apps/shops/tests/test_views.py`
- **Commit:** 3cb4cd2

## Self-Check: PASSED

All 8 key files found on disk. Both task commits (ef67a5c, 3cb4cd2) verified in git log.
