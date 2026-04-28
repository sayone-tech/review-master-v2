# Phase 8: Shops - Research

**Researched:** 2026-04-28
**Domain:** Django OAuth popup flow, Google Business Profile API, DRF viewsets, Fernet encryption, React multi-modal widget
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**GBP listing picker (SHOP-11)**
- Single listing → auto-select: popup calls `window.opener.postMessage` immediately + closes.
- Multiple listings → picker inside the popup: `/oauth/google/callback/` Django template with radio buttons / cards; user picks; page calls `window.opener.postMessage` + auto-closes.
- Listing card shows: Business name + formatted address only.
- After successful OAuth: "Connect Google Business Profile" button replaced by green success row (checkmark + connected listing name/address + "Change connection" link). Shop Name and Address auto-populate from listing data (SHOP-09); user may overwrite.

**Audit log (SHOP-19/20)**
- New `ShopAuditLog` model in `apps/shops/`: `shop` FK, `actor` FK to `AUTH_USER_MODEL`, `action` CharField (`shop.api_key.revealed` / `shop.api_key.rotated`), `created_at` (auto_now_add).
- New migration 0002 in `apps/shops/migrations/`.
- `reveal_api_key` and `rotate_api_key` write audit entry inside `transaction.atomic()`.

**Allocation counter mechanics (SHOP-01/02, XMOD-04)**
- X = `Shop.objects.filter(organisation=org).count()` — total by existence, regardless of `is_active`.
- Deactivate/activate does NOT change the counter.
- At limit: `total_shop_count >= org.number_of_stores`.
- API response envelope includes `allocation_status: {current: X, max: Y, at_limit: bool}`.
- No denormalized counter — live COUNT query at list time.

**Manual Place ID + API Key validation error handling (SHOP-10/20)**
- Google unreachable (timeout / 5xx) → hard fail, non-field error: "Could not reach Google to verify this API key. Please try again." Shop NOT saved.
- Place ID invalid → inline field error: "This Place ID was not found." (under place_id field only).
- API Key invalid → inline field error: "This API key is not valid." (under api_key field only).
- Rotate Key: same policy — existing key NOT replaced if Google unreachable.

### Claude's Discretion
- Exact Django template for listing picker inside OAuth callback (simple form, radio buttons, brand yellow CTA).
- `postMessage` payload: `{ listingName, address, placeId }` keys.
- Origin verification: `event.origin === window.location.origin` before processing.
- `ShopAuditLog` table name and index decisions (created_at index).
- Exact serializer fields for `allocation_status` envelope (nested vs flat).
- OAuth views as plain Django views (not DRF viewsets).
- `reveal_api_key`: backend returns decrypted key in API response; masks after 30s client-side.

### Deferred Ideas (OUT OF SCOPE)
- Shop hard-delete / freeing allocation slot — explicitly deferred.
- ShopAuditLog viewer UI — audit entries written but no list view.
- Google review fetching using connected Shop credentials — Phase 4.
- Staff Admin access to shop-scoped views — Phase 9.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SHOP-01 | Live allocation counter "Shops (X / Y)" in page header | Live COUNT query in `list_shops` selector; envelope field `allocation_status`; React reads `at_limit` |
| SHOP-02 | Disabled "+ Add Shop" at limit with tooltip | Frontend reads `at_limit` flag; clicking shows toast (no modal open); same as Org Management disabled-Create pattern |
| SHOP-03 | Search (Name+Address+City) + Status filter + Region filter | `list_shops` selector with Q() search + filter kwargs; DRF filtering via query params |
| SHOP-04 | Shops list columns: Name, Location, Region badge, Contact, Place ID, API Key (masked), Status, Connection Status, Created Date, Actions | ShopReadSerializer; DataTable columns config |
| SHOP-05 | Connection Status pill with 4 states | ConnectionStatus enum already on model; React pill component with color mapping |
| SHOP-06 | Pagination 10/25/50/100 rows-per-page | DRF PageNumberPagination with page_size_query_param; React pagination controls |
| SHOP-07 | Empty State A (no regions) + B (no shops) | Selector detects region count; API includes `has_regions` flag; React branches on empty state type |
| SHOP-08 | Create modal: connection method radio + common fields | React controlled form; field validation matches SHOP-08 spec |
| SHOP-09 | OAuth success auto-populates Name + Address (user can overwrite) | postMessage payload feeds form fields; React state update |
| SHOP-10 | Manual flow: Place ID + API Key fields; validated on submit | httpx call to Google Places API in service; inline field errors |
| SHOP-11 | OAuth popup flow: start/callback views, listing picker, postMessage | Plain Django views; COOP per-view override; synchronous window.open in React |
| SHOP-12 | Popup edge cases: closed/denied/error/no-listings messages | React window.open error handling; postMessage `type: "error"` payload |
| SHOP-13 | OAuth token + API key never transmitted to browser; Fernet-encrypted | EncryptedTextField already on model; service layer only decrypts for reveal endpoint |
| SHOP-14 | Create success: toast + list refresh + allocation counter increment | React refresh after POST; allocation_status re-read from new list response |
| SHOP-15 | Shop Details modal: read-only grid + Connection Status pill + footer buttons | ShopReadSerializer; React modal with two-column grid layout |
| SHOP-16 | Edit modal: pre-filled, locked connection_method + place_id | ShopUpdateSerializer excludes connection_method/place_id; React disabled fields |
| SHOP-17 | Deactivate: amber confirm + "slot remains used" text | ConfirmModal variant="amber"; PATCH is_active=False service |
| SHOP-18 | Activate: blue confirm | ConfirmModal variant="blue"; PATCH is_active=True service |
| SHOP-19 | Reveal API Key: confirm popup + 30s auto-mask + audit log | Dedicated `/shops/{id}/reveal_key/` DRF action; ShopAuditLog entry; React timer |
| SHOP-20 | Rotate Key modal: validate new key + atomic replace + audit log | Dedicated `/shops/{id}/rotate_key/` DRF action; httpx Places API validation; audit log |
| SHOP-21 | Reconnect Google: restart OAuth popup for error-state shops | Same OAuth popup flow; new refresh token replaces old; connection_status → CONNECTED |
| XMOD-01 | Cannot create shop without Region; disabled dropdown + link | `list_regions` called to populate dropdown; empty-region empty state A |
| XMOD-03 | Deactivated shops excluded from Team scope selectors | `list_shops(active_only=True)` selector used by Team module Phase 9 |
| XMOD-04 | Allocation counter transactional under concurrent sessions | `select_for_update()` on Organisation row inside `@transaction.atomic` in `create_shop` |
</phase_requirements>

---

## Summary

Phase 8 builds the complete Shops management module on an already-scaffolded Django/React stack. The model (`Shop`), encrypted fields (`EncryptedTextField`), factory, and first migration are already in place from Phase 6. No new model fields are needed on `Shop` itself — only a new `ShopAuditLog` model (migration 0002) for the API key audit trail.

The most technically complex part is the Google OAuth popup flow. The OAuth popup must open synchronously (`window.open` before any async call) for Safari compatibility, and postMessage communication between the popup and the parent must be verified by origin. The Django backend needs a scoped `Cross-Origin-Opener-Policy: same-origin-allow-popups` header on the OAuth initiation view only — the global production.py setting of `same-origin` must not be changed. When postMessage is unavailable (due to COOP mismatch with the Google auth domain in certain configurations), the app falls back to a 30-second Redis polling key.

The services/selectors/viewset pattern from Phase 7 (`apps/regions/`) is the direct template. The React widget structure follows `frontend/src/widgets/region-management/` exactly — types.ts, api.ts, hook, table component, modals component, entrypoint. The `RowActionsMenu` component in `org-management/` provides the three-dot menu pattern needed for Shop row actions. All modal infrastructure (Modal, ConfirmModal) is already built and reusable.

**Primary recommendation:** Follow the Phase 7 implementation order exactly — integrations layer first (Plan 08-01), then services/selectors + tests (08-02), then API viewset + URLs + COOP override (08-03), then React list widget (08-04), then React modals (08-05).

---

## Standard Stack

### Core (already installed — no new installs needed for most plans)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `django-fernet-encrypted-fields` | 0.4.0 | Fernet encryption for `google_refresh_token` and `api_key` fields | Already installed; `EncryptedTextField` on `Shop` model |
| `djangorestframework` | 3.17.1 | DRF viewsets, serializers, permissions, pagination | Project standard |
| `django-redis` | 5.4.0 | Redis polling fallback for COOP postMessage cases | Already installed |

### New Dependencies Required (Plan 08-01)

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `httpx` | 0.28.1 | Google Places API HTTP calls with timeout support | Sync-friendly, testable with `respx`; preferred over `requests` for new Python code |
| `tenacity` | 9.1.4 | Retry + exponential backoff on Google API calls | CLAUDE.md §11 explicit requirement; handles transient 5xx, rate limits |
| `responses` | 0.26.0 | Mock `httpx` calls in tests | Test isolation; CLAUDE.md §13 "Never hit external APIs in tests" |

**Installation (add to `pyproject.toml` `[project.dependencies]`):**
```bash
uv add httpx==0.28.1 tenacity==9.1.4
uv add --dev responses==0.26.0
```

**Version verification (confirmed 2026-04-28 via PyPI):**
- `httpx`: 0.28.1 (latest stable)
- `tenacity`: 9.1.4 (latest stable)
- `responses`: 0.26.0 (latest stable)

Note: `responses` library primarily targets `requests`. For mocking `httpx`, use `respx` (a dedicated httpx mock library) OR mock at the service function boundary using `unittest.mock.patch`. Given existing project patterns and the simplicity of the Google API calls here, patching at the service level with `unittest.mock.patch` is the simplest approach that avoids adding another dependency.

### Frontend (no new packages needed)

All required frontend packages are already installed: `react` 19.2.5, `lucide-react` 1.8.0, `focus-trap-react` 12.0.0, `vitest` 2.1.8, `@testing-library/react` 16.1.0. The `RowActionsMenu` from `org-management` needs to be genericised — it currently has `OrgRow` hardcoded. For Shops, either copy-adapt it or refactor to a generic version.

---

## Architecture Patterns

### Recommended Project Structure

```
apps/
└── shops/
    ├── models.py               # Shop + ShopAuditLog (new in migration 0002)
    ├── exceptions.py           # ShopAtLimitError, GoogleValidationError
    ├── serializers.py          # ShopReadSerializer, ShopCreateSerializer, ShopUpdateSerializer
    ├── views.py                # shop_list Django view + ShopViewSet DRF
    ├── urls.py                 # /api/v1/shops/ + OAuth views routed here
    ├── migrations/
    │   ├── 0001_initial.py     # existing
    │   └── 0002_shop_audit_log.py  # new
    ├── services/
    │   ├── __init__.py
    │   └── shops.py            # create_shop, update_shop, activate_shop, deactivate_shop,
    │                           # reveal_api_key, rotate_api_key
    ├── selectors/
    │   ├── __init__.py
    │   └── shops.py            # list_shops, get_shop
    └── tests/
        ├── __init__.py
        ├── conftest.py         # re-export assert_query_ceiling + two_orgs_two_admins
        ├── factories.py        # ShopFactory (extend existing), ShopAuditLogFactory
        ├── test_models.py      # existing + ShopAuditLog tests
        ├── test_services.py    # service unit tests with mocked Google client
        ├── test_selectors.py   # selector + query count tests
        └── test_views.py       # DRF viewset + template view tests

apps/
└── integrations/
    └── google/
        ├── __init__.py
        ├── oauth.py            # GoogleOAuthFlow: build_auth_url, exchange_code, list_locations
        ├── places.py           # PlacesAPIClient: validate_place_id (httpx + tenacity)
        ├── exceptions.py       # GoogleAuthError, GoogleAPIError, GoogleUnreachableError
        └── tests/
            ├── __init__.py
            ├── test_oauth.py
            └── test_places.py

templates/
└── shops/
    ├── shop_list.html          # extends base_org.html, json_script seeding, React root divs
    └── oauth/
        ├── start.html          # minimal: JS redirect to Google auth URL
        └── callback.html       # listing picker (radio cards) or auto-close (single listing)

frontend/
└── src/
    ├── entrypoints/
    │   └── shop-management.tsx         # two createRoot() calls (table + modals)
    └── widgets/
        └── shop-management/
            ├── types.ts                # ShopRow, ShopCreatePayload, AllocationStatus, etc.
            ├── api.ts                  # CSRF + fetch — copy pattern from region-management/api.ts
            ├── useShops.ts             # state hook (rows, loading, refresh, allocationStatus)
            ├── ShopTable.tsx           # DataTable columns + RowActionsMenu
            ├── ShopModals.tsx          # orchestrator (state + event routing)
            ├── ConnectionStatusPill.tsx # 4-state pill (green/blue/red/amber)
            ├── CreateShopModal.tsx     # radio + OAuth flow + manual flow
            ├── OAuthConnectionSection.tsx  # popup + postMessage + polling fallback
            ├── EditShopModal.tsx
            ├── ShopDetailsModal.tsx
            ├── RotateKeyModal.tsx
            └── ShopModals.test.tsx
```

### Pattern 1: TenantScopedViewSet + IsOrgAdmin + IsOrgScoped (Region pattern — copy directly)

```python
# apps/shops/views.py
from apps.common.viewsets import TenantScopedViewSet
from apps.accounts.permissions import IsOrgAdmin
from apps.common.permissions import IsOrgScoped
from rest_framework import mixins

class ShopViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgAdmin, IsOrgScoped]
    queryset = Shop.objects.select_related("region").all()
    http_method_names = ["get", "post", "patch", "head", "options"]
```

`TenantScopedViewSet.get_queryset()` already applies `organisation_id` filter — no override needed. `IsOrgScoped.has_object_permission()` handles IDOR prevention on detail endpoints.

### Pattern 2: Allocation Enforcement with select_for_update() (XMOD-04)

```python
# apps/shops/services/shops.py
from django.db import transaction
from apps.organisations.models import Organisation
from apps.shops.models import Shop

@transaction.atomic
def create_shop(*, organisation: Organisation, region, name: str, ...) -> Shop:
    # Lock the org row to prevent concurrent over-allocation
    org = Organisation.objects.select_for_update().get(pk=organisation.pk)
    current_count = Shop.objects.filter(organisation=org).count()
    if current_count >= org.number_of_stores:
        raise ShopAtLimitError()
    shop = Shop.objects.create(organisation=org, region=region, name=name, ...)
    return shop
```

This mirrors the `django-sequences` + `select_for_update()` allocation pattern established in Phase 6/7. The live COUNT query is safe at typical shop counts (tens, not millions).

### Pattern 3: COOP Per-View Override (SHOP-11)

The global `production.py` has no `Cross-Origin-Opener-Policy` header set explicitly (Django handles this differently — it is NOT in the current `production.py`). The requirement is that the OAuth initiation view responds with `Cross-Origin-Opener-Policy: same-origin-allow-popups` while all other views keep the default. Implement via a custom `dispatch()` override or a minimal middleware that checks `request.path`:

```python
# apps/shops/views.py — plain Django view
from django.views import View

class GoogleOAuthStartView(View):
    def get(self, request, *args, **kwargs):
        # Build auth URL and redirect
        auth_url = GoogleOAuthFlow.build_auth_url(...)
        response = redirect(auth_url)
        # Scoped COOP override: popup opener needs same-origin-allow-popups
        response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response
```

Both the start view AND the callback view need this header because the callback is what calls `window.opener.postMessage`. Apply it on the `HttpResponse` object returned by each view — no middleware needed.

### Pattern 4: Google Places API Validation (httpx + tenacity)

```python
# apps/integrations/google/places.py
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/details/json"

@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def validate_place_id(*, place_id: str, api_key: str) -> bool:
    """Returns True if valid, raises GoogleUnreachableError on network failure,
    raises PlaceIDNotFoundError on invalid place_id, raises APIKeyInvalidError
    on 403/INVALID_REQUEST_KEY response."""
    try:
        resp = httpx.get(
            PLACES_API_URL,
            params={"place_id": place_id, "key": api_key, "fields": "name"},
            timeout=10.0,
        )
    except httpx.TransportError as exc:
        raise GoogleUnreachableError() from exc
    # Parse response and raise domain errors
    ...
```

### Pattern 5: postMessage Popup Flow (SHOP-11/12)

**Safari requirement:** `window.open()` MUST be called synchronously — before any `await` or `.then()` — because Safari blocks popup windows opened in async callbacks. The pattern:

```typescript
// frontend/src/widgets/shop-management/OAuthConnectionSection.tsx
function handleConnectGoogle() {
  // MUST be synchronous — Safari blocks async window.open
  const popup = window.open("/oauth/google/start/", "google-oauth", "width=600,height=700");
  if (!popup) {
    // Blocked by browser — show error
    setError("Popup was blocked. Please allow popups for this site.");
    return;
  }
  // Listen for message from popup
  const handler = (event: MessageEvent) => {
    if (event.origin !== window.location.origin) return; // origin guard
    if (event.data?.type === "oauth_success") {
      setConnected({ listingName: event.data.listingName, address: event.data.address, placeId: event.data.placeId });
    } else if (event.data?.type === "oauth_error") {
      setError(OAUTH_ERROR_MESSAGES[event.data.code] ?? "Could not complete connection.");
    }
    window.removeEventListener("message", handler);
  };
  window.addEventListener("message", handler);
  // Polling fallback for COOP environments where postMessage is blocked
  startPollingFallback(popup);
}
```

### Pattern 6: Redis Polling Fallback (SHOP-11)

When `postMessage` is blocked by COOP (the Google auth domain's own COOP headers can affect the opener reference), the backend stores a 30-second Redis key after successful OAuth:

```python
# In the OAuth callback view, after successful token exchange:
from django_redis import get_redis_connection
import json, secrets

session_key = request.session.session_key  # or a state param from the OAuth flow
r = get_redis_connection("default")
r.setex(f"oauth:result:{session_key}", 30, json.dumps({
    "status": "success",
    "listingName": listing.name,
    "address": listing.address,
    "placeId": listing.place_id,
}))
```

Frontend polls `/api/v1/shops/oauth-result/` every 2 seconds for up to 30 seconds, then gives up with "Connection cancelled."

### Pattern 7: ShopAuditLog atomic write

```python
# apps/shops/services/shops.py
@transaction.atomic
def reveal_api_key(*, shop: Shop, actor: User) -> str:
    """Returns the decrypted key. Writes audit log inside the same transaction."""
    ShopAuditLog.objects.create(
        shop=shop,
        actor=actor,
        action=ShopAuditLog.Action.API_KEY_REVEALED,
    )
    return shop.api_key or ""  # EncryptedTextField auto-decrypts on access
```

### Pattern 8: Allocation Status in API Response Envelope

The Shops list endpoint wraps pagination in a response that includes `allocation_status`:

```python
# apps/shops/views.py
class ShopViewSet(...):
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        # Inject allocation_status into the envelope
        org = request.user.organisation
        total = Shop.objects.filter(organisation=org).count()
        response.data["allocation_status"] = {
            "current": total,
            "max": org.number_of_stores,
            "at_limit": total >= org.number_of_stores,
        }
        return response
```

### Pattern 9: Empty State Detection (SHOP-07)

```python
# apps/shops/selectors/shops.py
def list_shops(*, organisation_id: int, search: str = "", status: str = "", region_id: int | None = None, active_only: bool = False) -> QuerySet[Shop]:
    ...

def get_has_regions(*, organisation_id: int) -> bool:
    from apps.regions.models import Region
    return Region.objects.filter(organisation_id=organisation_id).exists()
```

The `list` response envelope also includes `"has_regions": bool` so the React widget can differentiate Empty State A (no regions → link to regions page) vs Empty State B (regions exist but no shops → "Add your first shop" CTA).

### Anti-Patterns to Avoid

- **Calling `window.open()` inside `.then()` or `async` handler**: Breaks in Safari — popup is blocked because it is not in a user gesture handler. Always call synchronously from the click handler.
- **Global COOP override**: Never set `same-origin-allow-popups` in `production.py` or base middleware — only on the two OAuth views (`start` and `callback`).
- **Transmitting the decrypted refresh token or API key in the list/detail serializer**: `ShopReadSerializer` must NOT include `google_refresh_token` or `api_key` fields. Only the dedicated `reveal_api_key` DRF action returns the decrypted key.
- **Using `ModelViewSet` for ShopViewSet**: Use `GenericViewSet` + mixins (no `DestroyModelMixin` — shops are deactivated, not deleted).
- **Allocation check without `select_for_update()`**: Two concurrent creates can both pass the count check and exceed the limit. Lock the org row.
- **httpx in tests hitting real Google**: All tests that touch the Google integration must mock at the `httpx.get` / `httpx.post` level or patch the service function.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fernet encryption for tokens/keys | Custom encryption | `EncryptedTextField` from `django-fernet-encrypted-fields` | Already on model; handles key rotation |
| HTTP retry with backoff | Manual try/except loop | `tenacity` `@retry` decorator | Handles jitter, configurable strategies, re-raise |
| HTTP calls to Google APIs | `urllib` / manual requests | `httpx` | Timeout support, clean API, sync-compatible |
| Concurrent allocation race condition | Application-level locking | `select_for_update()` inside `@transaction.atomic` | DB-level row lock; existing pattern from Phase 7 |
| Three-dot action menu | New component | Adapt `RowActionsMenu` from `org-management/` | Already handles scroll close, keyboard, positioning |
| Modal infrastructure | New components | `Modal` and `ConfirmModal` from `frontend/src/widgets/modal/` | Already built with focus-trap, size variants, footer slots |
| Pagination UI | Build from scratch | DRF `PageNumberPagination` + React pagination controls (same as Phase 7 pattern) | Consistent with project patterns |
| CSRF-aware fetch | Manual CSRF extraction | Copy `getCsrfToken()` + `headers()` from `region-management/api.ts` | Exact pattern to replicate |

**Key insight:** This phase is primarily assembly work — the hard infrastructure (encryption, tenant isolation, modal system, table system, toast system) is fully built. The complexity is in the OAuth popup flow and the allocation enforcement transaction, both of which have well-defined patterns to follow.

---

## Common Pitfalls

### Pitfall 1: Safari Popup Blocking
**What goes wrong:** `window.open()` called inside an `async` function or a `.then()` callback — Safari treats this as a non-user-gesture context and silently blocks the popup (returns `null`).
**Why it happens:** Safari's popup blocker is stricter than Chrome/Firefox. Any async boundary between the user click and the `window.open()` call breaks the user-gesture chain.
**How to avoid:** Call `window.open()` as the first synchronous statement in the click handler. Do not `await` anything before it. Pass the popup reference to an async function for result handling.
**Warning signs:** `popup === null` returned by `window.open()` in Safari; works in Chrome, fails in Safari.

### Pitfall 2: postMessage Origin Not Verified
**What goes wrong:** The React listener accepts messages from any origin, allowing any page opened in a popup to inject a fake OAuth success.
**Why it happens:** `window.addEventListener("message", handler)` without origin check.
**How to avoid:** Always check `event.origin === window.location.origin` before processing. The callback page is served from the same Django origin — same-origin postMessage is safe.
**Warning signs:** No origin guard in message handler.

### Pitfall 3: COOP Headers Applied Globally
**What goes wrong:** Setting `Cross-Origin-Opener-Policy: same-origin-allow-popups` on all responses. This breaks any other popup-based feature and is a security regression.
**Why it happens:** Setting the header in middleware or base settings.
**How to avoid:** Set the header only on `response` objects returned by `GoogleOAuthStartView` and `GoogleOAuthCallbackView`. Use `response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"` directly on the HttpResponse in the view function.

### Pitfall 4: Allocation Over-Count Race
**What goes wrong:** Two concurrent Org Admin sessions create shops simultaneously, both pass the `count < limit` check before either shop is written, resulting in one extra shop beyond the limit.
**Why it happens:** The count check and the insert are separate DB operations without a lock.
**How to avoid:** `select_for_update()` on the Organisation row at the start of `create_shop()` serialises concurrent creates for the same organisation. The lock releases at transaction end.
**Warning signs:** Integration test with concurrent creates (using `threading.Thread`) creating one extra shop.

### Pitfall 5: EncryptedTextField Serializer Leak
**What goes wrong:** `ShopReadSerializer(Meta.fields = "__all__")` inadvertently includes `google_refresh_token` and `api_key` in list/detail responses.
**Why it happens:** Auto-generated serializer fields include all model fields.
**How to avoid:** `ShopReadSerializer` must have an explicit `fields` list that excludes both encrypted fields. Only `ShopRevealKeySerializer` (returned by the `reveal_key` action) includes `api_key`.

### Pitfall 6: RowActionsMenu Generic Typing
**What goes wrong:** `RowActionsMenu` in `org-management/RowActionsMenu.tsx` is typed to `OrgRow`. Importing it in the Shop widget causes type errors because `ShopRow` does not match `OrgRow`.
**Why it happens:** The component was built org-specific.
**How to avoid:** Create a generic version: `RowActionsMenuGeneric<T extends { id: number; name: string }>`. Either refactor the existing one (careful — that changes org-management) or duplicate into `shop-management/RowActionsMenu.tsx` with `ShopRow` type. Duplication is safer in Phase 8; generalisation can be a refactor later.

### Pitfall 7: httpx Not in pyproject.toml
**What goes wrong:** `apps/integrations/google/places.py` imports `httpx` but it is not in `pyproject.toml`, so production Docker builds fail.
**Why it happens:** Developer has httpx globally installed locally, not noticing it is missing from project deps.
**How to avoid:** Add `httpx==0.28.1` and `tenacity==9.1.4` to `[project.dependencies]` in `pyproject.toml` as the first task in Plan 08-01. Also add a mypy override for `tenacity.*` stubs if needed.

### Pitfall 8: Missing conftest.py in apps/shops/tests/
**What goes wrong:** `assert_query_ceiling` and `two_orgs_two_admins` fixtures not auto-discovered for Shop tests.
**Why it happens:** Phase 6 decision: "Phase 7-9 tests must explicitly import from apps.common.tests.fixtures — conftest auto-discovers only within apps/common/tests/".
**How to avoid:** Create `apps/shops/tests/conftest.py` that re-exports both fixtures, exactly as done in `apps/regions/tests/conftest.py`. This is explicitly noted in STATE.md.

---

## Code Examples

### Shop Services — create_shop (with allocation lock)
```python
# apps/shops/services/shops.py
# Source: Phase 7 pattern (apps/regions/services/regions.py) + CONTEXT.md allocation spec
from django.db import transaction
from apps.organisations.models import Organisation
from apps.regions.models import Region
from apps.shops.models import Shop
from apps.shops.exceptions import ShopAtLimitError

@transaction.atomic
def create_shop(
    *,
    organisation: Organisation,
    region: Region,
    name: str,
    connection_method: str,
    place_id: str = "",
    google_refresh_token: str = "",
    api_key: str = "",
    phone: str = "",
    street_address: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
    connection_status: str = Shop.ConnectionStatus.NOT_CONNECTED,
) -> Shop:
    # Lock org row to serialise concurrent creates for same org (XMOD-04)
    org = Organisation.objects.select_for_update().get(pk=organisation.pk)
    current_count = Shop.objects.filter(organisation=org).count()
    if current_count >= org.number_of_stores:
        raise ShopAtLimitError()
    return Shop.objects.create(
        organisation=org,
        region=region,
        name=name,
        connection_method=connection_method,
        connection_status=connection_status,
        place_id=place_id,
        google_refresh_token=google_refresh_token or None,
        api_key=api_key or None,
        phone=phone,
        street_address=street_address,
        city=city,
        state=state,
        zip_code=zip_code,
    )
```

### Shop Selector — list_shops (with search/filter)
```python
# apps/shops/selectors/shops.py
# Source: CLAUDE.md §5 selectors pattern; Phase 7 list_regions pattern
from django.db.models import Q, QuerySet
from apps.shops.models import Shop

def list_shops(
    *,
    organisation_id: int,
    search: str = "",
    status: str = "",
    region_id: int | None = None,
    active_only: bool = False,
) -> QuerySet[Shop]:
    qs = (
        Shop.objects
        .filter(organisation_id=organisation_id)
        .select_related("region")
    )
    if active_only:
        qs = qs.filter(is_active=True)
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(street_address__icontains=search)
            | Q(city__icontains=search)
        )
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    if region_id is not None:
        qs = qs.filter(region_id=region_id)
    return qs  # ordering from model Meta: -created_at
```

### ShopAuditLog model (migration 0002)
```python
# apps/shops/models.py — append after Shop class
class ShopAuditLog(models.Model):
    class Action(models.TextChoices):
        API_KEY_REVEALED = "shop.api_key.revealed", "API Key Revealed"
        API_KEY_ROTATED = "shop.api_key.rotated", "API Key Rotated"

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="shop_audit_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "shops_shopauditlog"
        ordering: ClassVar[list[str]] = ["-created_at"]
```

### OAuth Callback template (listing picker)
```html
{# templates/shops/oauth/callback.html #}
{# Source: CONTEXT.md listing picker decision #}
<!DOCTYPE html>
<html>
<head><title>Connect Google Business Profile</title></head>
<body>
{% if listings|length == 0 %}
  <script>
    window.opener?.postMessage({ type: "oauth_error", code: "no_listings" }, window.location.origin);
    window.close();
  </script>
{% elif listings|length == 1 %}
  {# Single listing — auto-select, no picker shown #}
  <script>
    window.opener?.postMessage({
      type: "oauth_success",
      listingName: "{{ listings.0.name|escapejs }}",
      address: "{{ listings.0.address|escapejs }}",
      placeId: "{{ listings.0.place_id|escapejs }}"
    }, window.location.origin);
    window.close();
  </script>
{% else %}
  {# Multiple listings — render picker #}
  <form method="post">{% csrf_token %}
    {% for listing in listings %}
      <label><input type="radio" name="listing_index" value="{{ forloop.counter0 }}"> {{ listing.name }} — {{ listing.address }}</label>
    {% endfor %}
    <button type="submit" class="bg-yellow ...">Connect this listing</button>
  </form>
{% endif %}
</body>
</html>
```

### API.ts pattern for shop-management (copy from region-management)
```typescript
// frontend/src/widgets/shop-management/api.ts
// Source: frontend/src/widgets/region-management/api.ts — copy CSRF + handle pattern exactly
import type { ShopRow, ShopCreatePayload, ShopUpdatePayload, ShopsListResponse } from "./types";

export async function listShops(params?: Record<string, string>): Promise<ShopsListResponse> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  const resp = await fetch(`/api/v1/shops/${qs}`, {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  return (await handle(resp)) as ShopsListResponse;
}
```

### Vite entrypoint registration
```typescript
// frontend/vite.config.ts — add to rollupOptions.input:
"shop-management": resolve(__dirname, "src/entrypoints/shop-management.tsx"),
```

### pytest conftest.py for shops tests
```python
# apps/shops/tests/conftest.py
from apps.common.tests.fixtures import (  # noqa: F401
    assert_query_ceiling,
    two_orgs_two_admins,
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests` library | `httpx` for new code | 2023+ | Cleaner API, supports async future, better timeout control |
| `django-cryptography` | `django-fernet-encrypted-fields` | Phase 6 (Django 6 compat) | Already installed; no action needed |
| Django `window.open` COOP global | Per-view `response["Cross-Origin-Opener-Policy"]` header | Phase 8 requirement | Safer than global override |
| Polling-only OAuth callback | postMessage + polling fallback | Current best practice | postMessage is instant; polling handles COOP edge cases |

**Deprecated/outdated:**
- `django-cryptography`: No Django 6 support. Replaced by `django-fernet-encrypted-fields==0.4.0` in Phase 6. Already done.
- `django-oauth-toolkit` / `social-auth-app-django`: Overkill for this use case — a custom OAuth code exchange in ~50 lines is the right scope here.

---

## Open Questions

1. **Google Places API validation endpoint choice**
   - What we know: Google Places API (v1 or legacy) can validate a Place ID by fetching `place/details`; the response `status` field indicates validity.
   - What's unclear: The legacy `maps.googleapis.com/maps/api/place/details/json` endpoint vs the newer `places.googleapis.com/v1/places/{id}` endpoint. The new Places API (v1) uses a different auth model.
   - Recommendation: Use the legacy `maps.googleapis.com/maps/api/place/details/json` endpoint with `fields=name` (minimal billing) and `key=<api_key>`. This is the most stable and well-documented. The new Places API would require changes to auth that are out of scope.

2. **Google Business Profile OAuth scope and listing endpoint**
   - What we know: GBP uses `https://www.googleapis.com/auth/business.manage` scope. The listing endpoint is `https://mybusinessaccountmanagement.googleapis.com/v1/accounts/{accountId}/locations`.
   - What's unclear: Whether the sandbox/test account requires GBP API to be enabled in the Google Cloud Console, and whether the listing endpoint pagination or `readMask` parameter is needed.
   - Recommendation: Plan 08-01 should implement the OAuth code exchange + listing fetch with a clearly marked `# TODO: verify GBP API endpoint` comment. The GBP API approval blocker (noted in ROADMAP.md and STATE.md) means the integration will be tested against a dev GBP account first.

3. **Redis polling key scoping**
   - What we know: The fallback polls `/api/v1/shops/oauth-result/` with the session key as identifier.
   - What's unclear: Whether the session key is reliable in all cookie configurations, or whether a state parameter passed through the OAuth flow is safer.
   - Recommendation: Pass a `state` parameter through the OAuth flow (standard OAuth 2.0 `state` param) — use a random token stored in the session on start, verified on callback, and used as the Redis key suffix. This is more robust than relying on session_key directly.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `DJANGO_SETTINGS_MODULE = "config.settings.test"` |
| Quick run command | `pytest apps/shops/ apps/integrations/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |
| Frontend test command | `cd frontend && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SHOP-01 | Allocation counter in API response envelope | unit | `pytest apps/shops/tests/test_views.py::TestShopsListAllocation -x` | ❌ Wave 0 |
| SHOP-02 | `at_limit: true` when count >= max | unit | `pytest apps/shops/tests/test_services.py::TestShopAtLimit -x` | ❌ Wave 0 |
| SHOP-03 | Search + status + region filter | unit | `pytest apps/shops/tests/test_selectors.py::TestListShopsFilters -x` | ❌ Wave 0 |
| SHOP-10 | Google unreachable → hard fail, no save | unit | `pytest apps/integrations/google/tests/test_places.py -x` | ❌ Wave 0 |
| SHOP-11 | OAuth start view returns COOP header | unit | `pytest apps/shops/tests/test_views.py::TestOAuthStartView -x` | ❌ Wave 0 |
| SHOP-11 | OAuth callback single listing → postMessage script | unit | `pytest apps/shops/tests/test_views.py::TestOAuthCallbackSingleListing -x` | ❌ Wave 0 |
| SHOP-13 | Encrypted fields never in read serializer | unit | `pytest apps/shops/tests/test_views.py::TestShopSerializerFields -x` | ❌ Wave 0 |
| SHOP-19 | reveal_api_key writes audit log | unit | `pytest apps/shops/tests/test_services.py::TestRevealApiKey -x` | ❌ Wave 0 |
| SHOP-20 | rotate_api_key atomic replace + audit log | unit | `pytest apps/shops/tests/test_services.py::TestRotateApiKey -x` | ❌ Wave 0 |
| XMOD-04 | Allocation enforcement (select_for_update) | integration | `pytest apps/shops/tests/test_services.py::TestCreateShopAllocation -x` | ❌ Wave 0 |
| XMOD-04 | Query count ceiling for shops list | integration | `pytest apps/shops/tests/test_views.py::test_shops_list_query_count_ceiling -x` | ❌ Wave 0 |
| cross-tenant | Org A cannot read Org B shops | integration | `pytest apps/shops/tests/test_views.py::test_shops_cross_tenant_isolation -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest apps/shops/ apps/integrations/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (all must be created during implementation)
- [ ] `apps/integrations/google/__init__.py` — create `apps/integrations/` and `apps/integrations/google/` directories
- [ ] `apps/integrations/google/tests/__init__.py` — test directory
- [ ] `apps/shops/tests/conftest.py` — re-export `assert_query_ceiling`, `two_orgs_two_admins` (same as regions conftest pattern)
- [ ] `apps/shops/services/__init__.py` + `apps/shops/services/shops.py` — service layer
- [ ] `apps/shops/selectors/__init__.py` + `apps/shops/selectors/shops.py` — selector layer
- [ ] `apps/shops/exceptions.py` — `ShopAtLimitError`, domain errors
- [ ] `apps/shops/serializers.py` — read/create/update serializers
- [ ] `apps/shops/views.py` — `ShopViewSet`, `shop_list` template view, OAuth views
- [ ] `apps/shops/migrations/0002_shop_audit_log.py` — `ShopAuditLog` model migration
- [ ] `apps/shops/tests/test_services.py` — service unit tests
- [ ] `apps/shops/tests/test_selectors.py` — selector tests with query count
- [ ] `apps/shops/tests/test_views.py` — DRF + template view tests
- [ ] Frontend: `frontend/src/entrypoints/shop-management.tsx`
- [ ] Frontend: `frontend/src/widgets/shop-management/` directory + all component files
- [ ] Vite config: add `shop-management` entrypoint to `rollupOptions.input`

---

## Sources

### Primary (HIGH confidence)
- Codebase: `apps/shops/models.py` — `Shop` model fields, enums, `EncryptedTextField` usage confirmed
- Codebase: `apps/regions/views.py`, `apps/regions/services/regions.py`, `apps/regions/selectors/regions.py` — exact patterns to replicate
- Codebase: `apps/common/viewsets.py` — `TenantScopedViewSet` interface confirmed
- Codebase: `apps/common/permissions.py` — `IsOrgScoped` confirmed
- Codebase: `apps/common/tests/fixtures.py` — `assert_query_ceiling`, `two_orgs_two_admins` fixture signatures confirmed
- Codebase: `frontend/src/widgets/region-management/api.ts` — CSRF + fetch pattern to replicate
- Codebase: `frontend/src/widgets/modal/Modal.tsx`, `ConfirmModal.tsx` — component interfaces confirmed
- Codebase: `frontend/src/widgets/org-management/RowActionsMenu.tsx` — three-dot menu pattern confirmed
- Codebase: `frontend/src/widgets/data-table/DataTable.tsx` — `DataTableColumn` interface (accessor/label/rowKey API) confirmed
- Codebase: `config/settings/production.py` — no global COOP header present; per-view approach confirmed correct
- Codebase: `pyproject.toml` — `httpx`, `tenacity` NOT in current dependencies; must be added
- PyPI (verified 2026-04-28): httpx 0.28.1, tenacity 9.1.4, responses 0.26.0

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions — OAuth flow, audit log, allocation mechanics, error handling all locked
- ROADMAP.md plan breakdown — 5-plan structure confirmed
- STATE.md accumulated decisions — conftest pattern, encryption lib, select_for_update pattern confirmed
- CLAUDE.md §11 — Google integration requirements (encrypted tokens, tenacity retry, Redis lock)
- MDN / browser docs — Safari synchronous window.open requirement (widely documented behaviour)

### Tertiary (LOW confidence)
- Google Places API legacy endpoint (`maps.googleapis.com/maps/api/place/details/json`) — endpoint verified as current but billing/quota behaviour not confirmed against live account
- GBP listing endpoint (`mybusinessaccountmanagement.googleapis.com/v1/accounts/{id}/locations`) — API shape is documented but requires GBP API approval for production use

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies verified from pyproject.toml + PyPI
- Architecture: HIGH — directly derived from existing Phase 7 code patterns in codebase
- OAuth popup flow: HIGH — documented browser requirement (synchronous window.open), per-view COOP header confirmed
- Pitfalls: HIGH — most derived from direct codebase reading + confirmed STATE.md decisions
- Google API specifics: MEDIUM — endpoint shapes from documentation, not live-tested

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (stable stack; Google API endpoints are stable long-term)
