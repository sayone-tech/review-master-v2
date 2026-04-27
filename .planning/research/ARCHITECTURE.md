# Architecture Patterns

**Domain:** Multi-tenant SaaS review management — v0.2 Org Admin module integration
**Researched:** 2026-04-27
**Confidence:** HIGH (derived from direct codebase reading + existing patterns)

---

## System Overview (post v0.2)

```
Browser
  ├─ Django Template Pages (server-rendered HTML)
  │    └─ Tailwind CSS + Alpine.js (shell interactivity)
  │    └─ React widgets mounted on <div id="..."> via Vite bundles
  │
  ├─ DRF JSON API  /api/v1/   (called by React widgets + OAuth callback coordination)
  │
  └─ Static assets (WhiteNoise / CDN)

Django (Cloud Run)
  ├─ config/              Project wiring: settings, urls, wsgi/asgi
  ├─ apps/accounts/       User model, auth, invitations, RBAC permissions
  ├─ apps/organisations/  Organisation CRUD (Superadmin)
  ├─ apps/regions/        NEW — Region model, auto-ID generation, CRUD
  ├─ apps/shops/          NEW — Shop model, OAuth + manual Place ID, API key mgmt
  ├─ apps/integrations/   Google Business Profile OAuth client, Places API validation
  └─ apps/common/         TimeStampedModel, email service, base permissions/mixins

PostgreSQL 16  — Primary datastore
Redis 7        — Cache (DB0), Throttle (DB1), Sessions (DB2)
Amazon SES     — Transactional email via django-ses
GCP Secret Manager — All credentials at runtime
```

---

## Existing Architecture (confirmed from codebase)

### What exists in v1.0

**apps/accounts/models.py**
- `User` — AbstractBaseUser; fields: email, full_name, role (SUPERADMIN|ORG_ADMIN|STAFF_ADMIN),
  organisation FK (null for superadmins), email_suppressed, is_active
- `InvitationToken` — token_hash (SHA-256), is_used, expires_at, organisation FK, invited_user OneToOne

**apps/organisations/models.py**
- `Organisation` — name, org_type, email, address, number_of_stores, status (ACTIVE|DISABLED|DELETED),
  created_by FK; soft-delete via `.soft_delete()`

**apps/accounts/permissions.py**
- `IsSuperadmin` — checks `user.role == User.Role.SUPERADMIN`

**config/urls.py**
- SimpleRouter registers `api/v1/organisations/` → OrganisationViewSet
- `admin/organisations/` → Superadmin list template view
- `admin/org-dashboard/` → stub Org Admin dashboard (in organisations/views.py)
- `admin/profile/` → accounts profile view

**Route namespace reality:** There is NO `accounts/login/` prefix — auth URLs are at root level
(`/login/`, `/logout/`, `/password-reset/`). Template views are at `/admin/*`. Org Admin stub is
already at `/admin/org-dashboard/`.

**Frontend widget pattern:**
- Vite entrypoints in `frontend/src/entrypoints/`
- Each entrypoint mounts one or more React roots onto `<div id="...">` elements injected by Django templates
- `window._orgModalHandlers` used as cross-root communication bus (established pattern)
- `window.dispatchEvent(new CustomEvent("org:refresh"))` for mutation → re-fetch signalling
- CSRF token read from cookie via `document.cookie` (not from data attribute)
- `app-shell.ts` loads Alpine.js + Lucide icons globally on every page

---

## New Components: Placement and Import Rules

### (a) Where New Apps Live and How They Import

**New apps:**

```
apps/
  regions/          # NEW bounded context
  shops/            # NEW bounded context
  integrations/     # EXPAND — google/ sub-package referenced in CLAUDE.md but not yet created
```

**Dependency direction (strict acyclic):**

```
apps/common         ← imported by everything; imports nothing from other apps
apps/accounts       ← imported by organisations, regions, shops; imports only common
apps/organisations  ← imported by regions, shops; imports accounts + common
apps/regions        ← imported by shops (region FK on Shop); imports accounts + organisations + common
apps/shops          ← imports regions + organisations + accounts + common + integrations
apps/integrations   ← imports only common (no domain models); called by shops service layer
```

**Circular import risk points and mitigations:**

1. `apps/accounts` services reference `apps/organisations` (existing: `Organisation` FK on User).
   The existing code uses string label `"organisations.Organisation"` in the FK definition —
   this is the correct pattern. Services that cross boundaries use TYPE_CHECKING guards:
   ```python
   if TYPE_CHECKING:
       from apps.organisations.models import Organisation
   ```
   This pattern is already established in `apps/organisations/services/organisations.py`.

2. `apps/shops` services will call `apps/integrations/google/` for OAuth and Places validation.
   `apps/integrations/google/` must NOT import from `apps/shops` — it receives data as parameters,
   returns plain values. No model imports in integrations/.

3. `apps/accounts/services/` will add team invitation functions for v0.2. These services will need
   to reference `Region` and `Shop` models (for StaffAccessScope). Use TYPE_CHECKING guards:
   ```python
   if TYPE_CHECKING:
       from apps.regions.models import Region
       from apps.shops.models import Shop
   ```
   Do not import Region/Shop models at module level in accounts/services — call sites in
   team service functions will import lazily inside the function or use string model references.

**Recommended import pattern for cross-app services:**

```python
# apps/shops/services/shops.py
from __future__ import annotations
from typing import TYPE_CHECKING
from apps.common.models import TimeStampedModel
from apps.organisations.models import Organisation   # OK: shops → organisations is one-way

if TYPE_CHECKING:
    from apps.accounts.models import User  # type-checking only (User passed as param)
```

### New App Structure

```
apps/regions/
  __init__.py
  apps.py
  models.py            # Region model
  managers.py
  admin.py
  permissions.py       # IsOrgAdminForRegion (delegates to IsOrgScoped)
  serializers.py       # RegionReadSerializer, RegionCreateSerializer
  views.py             # RegionViewSet (TenantScopedViewSet)
  urls.py
  services/
    __init__.py
    regions.py         # create_region, update_region, delete_region, generate_region_id
  selectors/
    __init__.py
    regions.py         # list_regions_for_org, get_region_for_org
  migrations/
  tests/
    __init__.py
    factories.py
    test_models.py
    test_services.py
    test_selectors.py
    test_views.py

apps/shops/
  __init__.py
  apps.py
  models.py            # Shop model, EncryptedTokenField
  managers.py
  admin.py
  serializers.py       # ShopReadSerializer, ShopCreateSerializer, ShopUpdateSerializer
  views.py             # ShopViewSet (TenantScopedViewSet) + OAuthInitiateView
  urls.py
  services/
    __init__.py
    shops.py           # create_shop_oauth, create_shop_manual, connect_shop, etc.
    api_keys.py        # generate_api_key, rotate_api_key
  selectors/
    __init__.py
    shops.py           # list_shops_for_org, get_shop_for_org
  migrations/
  tests/
    __init__.py
    factories.py
    test_services.py
    test_selectors.py
    test_views.py

apps/integrations/
  __init__.py
  google/
    __init__.py
    client.py          # BusinessProfileClient — wraps API calls with retry + backoff
    oauth.py           # OAuthFlow — initiate, callback, refresh
    places.py          # PlacesAPI — validate Place ID, fetch place details
    exceptions.py      # GoogleAPIError, TokenExpiredError, InvalidPlaceIdError
```

---

## (b) Google OAuth Popup Flow Architecture

The OAuth flow for connecting a Shop to Google Business Profile is browser-popup based.
The canonical pattern for this, matching the existing Django + React widget approach:

### Flow diagram

```
Org Admin clicks "Connect via Google" button in React Shop modal
  │
  ├─ React calls GET /api/v1/shops/{id}/oauth/initiate/
  │    └─ ShopViewSet.oauth_initiate() action
  │         └─ integrations.google.oauth.OAuthFlow.build_authorization_url(
  │              shop_id=shop.id,
  │              state=sign_state(shop.id, request.user.id)   # TimestampSigner
  │            )
  │         → returns {auth_url: "https://accounts.google.com/o/oauth2/auth?..."}
  │
  ├─ React opens popup: window.open(auth_url, "google-oauth", "width=600,height=700")
  │
  ├─ User authorises in Google popup
  │
  ├─ Google redirects popup to: /integrations/google/oauth/callback/?code=...&state=...
  │    └─ GoogleOAuthCallbackView (Django TemplateView — NOT a DRF view)
  │         └─ integrations.google.oauth.OAuthFlow.exchange_code(code, state)
  │               ├─ Verify state signature (TimestampSigner, 10-minute max age)
  │               ├─ Exchange code → access_token + refresh_token
  │               ├─ Fernet-encrypt refresh_token
  │               └─ shops.services.shops.connect_shop_oauth(shop_id, tokens)  # writes DB
  │         └─ Returns minimal HTML page that calls window.opener.postMessage(...)
  │
  └─ React parent window receives postMessage:
       {type: "google-oauth-success", shopId: 42} or {type: "google-oauth-error", reason: "..."}
     → closes popup, triggers shop list refresh
```

### Callback view implementation

```python
# apps/integrations/google/views.py
from django.http import HttpRequest, HttpResponse
from django.views import View
from django.utils.html import escape

class GoogleOAuthCallbackView(View):
    """Handles Google OAuth callback in a popup window.

    This is a Django TemplateView, NOT a DRF APIView — it must render HTML
    so the popup can call window.opener.postMessage().

    Security: never trust the `state` parameter without signature verification.
    """
    def get(self, request: HttpRequest) -> HttpResponse:
        code = request.GET.get("code", "")
        state = request.GET.get("state", "")

        if not code or not state:
            return self._postmessage_response(success=False, reason="missing_params")

        try:
            from apps.integrations.google.oauth import OAuthFlow
            shop_id, user_id = OAuthFlow.verify_state(state)  # raises on tamper/expiry
            tokens = OAuthFlow.exchange_code(code)
            from apps.shops.services.shops import connect_shop_oauth
            connect_shop_oauth(
                shop_id=shop_id,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
            )
        except Exception as exc:
            return self._postmessage_response(success=False, reason=str(exc))

        return self._postmessage_response(success=True, shop_id=shop_id)

    def _postmessage_response(
        self, *, success: bool, reason: str = "", shop_id: int | None = None
    ) -> HttpResponse:
        if success:
            payload = f'{{"type":"google-oauth-success","shopId":{shop_id}}}'
        else:
            reason_escaped = escape(reason)
            payload = f'{{"type":"google-oauth-error","reason":"{reason_escaped}"}}'
        html = f"""<!DOCTYPE html>
<html><head><title>Connecting...</title></head>
<body>
<script>
  window.opener && window.opener.postMessage({payload}, window.location.origin);
  window.close();
</script>
</body></html>"""
        return HttpResponse(html, content_type="text/html")
```

### React popup listener

```typescript
// In ShopConnectionModal or ShopViewSet action component
function openGoogleOAuth(shopId: number, authUrl: string) {
  const popup = window.open(authUrl, "google-oauth", "width=600,height=700,noopener=0");
  if (!popup) {
    emitToast({ kind: "error", title: "Popup blocked", msg: "Allow popups for this site." });
    return;
  }

  const handler = (event: MessageEvent) => {
    if (event.origin !== window.location.origin) return;
    const data = event.data as { type: string; shopId?: number; reason?: string };
    if (data.type === "google-oauth-success") {
      window.removeEventListener("message", handler);
      // Trigger shop list refresh
      window.dispatchEvent(new CustomEvent("shop:refresh"));
      emitToast({ kind: "success", title: "Google account connected" });
    } else if (data.type === "google-oauth-error") {
      window.removeEventListener("message", handler);
      emitToast({ kind: "error", title: "Connection failed", msg: data.reason });
    }
  };
  window.addEventListener("message", handler);
}
```

### URL registration for OAuth callback

```python
# config/urls.py addition
from apps.integrations.google.views import GoogleOAuthCallbackView

urlpatterns = [
    ...
    path("integrations/google/oauth/callback/", GoogleOAuthCallbackView.as_view(),
         name="google_oauth_callback"),
]
```

**Security notes:**
- `state` parameter signed with `TimestampSigner` (max_age=600, 10 minutes) — same pattern as invitation tokens
- Callback view does NOT require `@login_required` because the Google redirect lands in a popup without session cookie (SameSite=Lax blocks cookie on cross-site redirect); instead, user identity is encoded in the signed `state` parameter alongside `shop_id`
- `window.opener.postMessage` uses `window.location.origin` as targetOrigin — prevents message interception by other origins
- CSP must allow `'self'` for script-src to execute the postMessage script inline. Use a nonce if CSP strict mode is enabled in a future phase

---

## (c) IsOrgScoped Permission Base Class

### Design

The `IsOrgScoped` permission class enforces two things simultaneously:
1. The user has an org-level role (ORG_ADMIN or STAFF_ADMIN)
2. Every queryset returned by the view is scoped to `request.user.organisation_id`

The scoping enforcement belongs in the **queryset layer**, not only in the permission class.
`IsOrgScoped` handles authentication/role check; `TenantScopedViewSet` handles queryset filtering.
Both must exist — permission class alone does not prevent data leaks if `get_queryset` is miscoded.

### Permission class

```python
# apps/accounts/permissions.py  (add alongside IsSuperadmin)
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.accounts.models import User


class IsSuperadmin(BasePermission):
    """Allow only authenticated users whose role is SUPERADMIN."""
    message = "Superadmin role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(getattr(user, "role", None) == User.Role.SUPERADMIN)


class IsOrgAdmin(BasePermission):
    """Allow only authenticated ORG_ADMIN users who have an organisation."""
    message = "Organisation Admin role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(
            getattr(user, "role", None) == User.Role.ORG_ADMIN
            and user.organisation_id is not None
        )


class IsOrgScoped(BasePermission):
    """Allow ORG_ADMIN or STAFF_ADMIN users who belong to an organisation.

    This is the base for all Org Admin and Staff Admin endpoints. It does NOT
    filter querysets — that is TenantScopedViewSet's responsibility. This class
    only gates the request.

    Use this as the permission_classes base for all /org-admin/* viewsets.
    Compose with role-specific checks for more restrictive endpoints:

        permission_classes = [IsOrgScoped, IsOrgAdmin]   # managers only
        permission_classes = [IsOrgScoped]                # all org members
    """
    message = "Organisation membership required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role = getattr(user, "role", None)
        if role not in (User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN):
            return False
        return bool(user.organisation_id is not None)
```

### TenantScopedViewSet base

```python
# apps/common/views.py  (add to existing file)
from rest_framework.viewsets import GenericViewSet
from django.db.models import QuerySet


class TenantScopedViewSet(GenericViewSet):
    """Base for ALL Org Admin and Staff Admin viewsets.

    Ensures every get_queryset() call is filtered to the authenticated user's
    organisation. Superadmin viewsets must NOT inherit this — they use a
    different queryset shape.

    Subclasses call super().get_queryset() from their own get_queryset(), then
    apply additional filters (e.g., search, status).

    NEVER override this filter without an explicit comment explaining why
    the tenant scope is being relaxed — doing so silently creates data leaks.
    """

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        org_id = self.request.user.organisation_id  # type: ignore[union-attr]
        if org_id is None:
            return qs.none()  # safety: no org → no data
        return qs.filter(organisation_id=org_id)
```

### Staff access scoping (StaffAccessScope)

Staff Admins have a narrower scope than Org Admins: they can only access regions and shops
assigned to them via `StaffAccessScope`. This is a **data-layer filter**, not just a permission check.

```python
# apps/accounts/models.py (new model to add in Phase 6 migration)
class StaffAccessScope(TimeStampedModel):
    class ScopeType(models.TextChoices):
        REGION = "REGION", "Region"
        SHOP = "SHOP", "Shop"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="access_scopes",
        limit_choices_to={"role": User.Role.STAFF_ADMIN},
    )
    scope_type = models.CharField(max_length=10, choices=ScopeType.choices, db_index=True)
    region = models.ForeignKey(
        "regions.Region",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="staff_scopes",
    )
    shop = models.ForeignKey(
        "shops.Shop",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="staff_scopes",
    )

    class Meta:
        db_table = "accounts_staff_access_scope"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(scope_type="REGION", region__isnull=False, shop__isnull=True)
                    | models.Q(scope_type="SHOP", shop__isnull=False, region__isnull=True)
                ),
                name="staff_scope_xor_region_shop",
            )
        ]
        indexes = [
            models.Index(fields=["user", "scope_type"], name="staff_scope_user_type_idx"),
        ]
```

**StaffAccessScope placement:** Model lives in `apps/accounts/` (it's about user access).
Its FKs reference `regions.Region` and `shops.Shop` using string labels — this avoids
circular imports since accounts is imported by regions and shops.

**Queryset filtering for Staff Admin:** shops and regions viewsets must branch on role:

```python
# apps/shops/selectors/shops.py
def list_shops_for_user(*, user: User) -> QuerySet[Shop]:
    qs = Shop.objects.filter(organisation_id=user.organisation_id)
    if user.role == User.Role.STAFF_ADMIN:
        scoped_shop_ids = (
            StaffAccessScope.objects
            .filter(user=user, scope_type=StaffAccessScope.ScopeType.SHOP)
            .values_list("shop_id", flat=True)
        )
        qs = qs.filter(id__in=scoped_shop_ids)
    return qs.select_related("region", "organisation").order_by("name")
```

---

## (d) Route Separation: Superadmin vs Org Admin

### Existing URL structure (confirmed)

```
/login/                             accounts/views.py — CustomLoginView
/logout/                            accounts/views.py — LogoutView
/admin/organisations/               organisations/views.py — Superadmin list (template)
/admin/org-dashboard/               organisations/views.py — Org Admin dashboard stub
/admin/profile/                     accounts/views.py — profile (shared across roles)
/invite/accept/<token>/             accounts/views.py — invite_accept_view
/api/v1/organisations/              config/urls.py — OrganisationViewSet (Superadmin)
```

### Target URL structure for v0.2

The existing `/admin/` prefix is used by BOTH Superadmin and Org Admin views.
This is a naming problem that is too costly to fix in v0.2 (would break existing URLs in production).
Instead, distinguish by sub-path:

```
SUPERADMIN routes (existing):
  /admin/organisations/
  /admin/profile/                    # shared — but Org Admins will use /org/profile/ in v0.2

ORG ADMIN routes (new):
  /org/dashboard/                    # replaces /admin/org-dashboard/ stub
  /org/profile/                      # Org Admin profile (reuses same view, different template namespace)
  /org/regions/                      # Regions list (Django template + React widget)
  /org/shops/                        # Shops list
  /org/team/                         # Team management

API routes (new, Org Admin):
  /api/v1/regions/                   # RegionViewSet (IsOrgScoped)
  /api/v1/shops/                     # ShopViewSet (IsOrgScoped)
  /api/v1/shops/{id}/oauth/initiate/ # OAuth initiation action
  /api/v1/team/                      # TeamViewSet (IsOrgAdmin — managers only)

Integration routes (new):
  /integrations/google/oauth/callback/  # GoogleOAuthCallbackView (public — state-signed)
```

**config/urls.py additions:**

```python
# config/urls.py
from rest_framework.routers import SimpleRouter
from apps.organisations.views import OrganisationViewSet
from apps.regions.views import RegionViewSet
from apps.shops.views import ShopViewSet
from apps.accounts.views import TeamViewSet

router = SimpleRouter()
router.register(r"api/v1/organisations", OrganisationViewSet, basename="organisation")
router.register(r"api/v1/regions", RegionViewSet, basename="region")
router.register(r"api/v1/shops", ShopViewSet, basename="shop")
router.register(r"api/v1/team", TeamViewSet, basename="team-member")

urlpatterns = [
    path("", include(router.urls)),
    path("", include("apps.organisations.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.common.urls")),
    path("", include("apps.regions.urls")),    # /org/regions/
    path("", include("apps.shops.urls")),      # /org/shops/
    path("integrations/google/oauth/callback/",
         GoogleOAuthCallbackView.as_view(), name="google_oauth_callback"),
    path("admin/", admin.site.urls),
]
```

**Redirect from old stub:** The existing `/admin/org-dashboard/` route in `organisations/urls.py`
should be preserved for the activation redirect (it's hardcoded in `invite_accept_view`) but
immediately redirects to `/org/dashboard/` once the new view exists. This avoids a breaking change
in the activation flow.

### Template namespace convention

```
templates/
  base.html              # Superadmin shell (existing)
  base_org.html          # Org Admin shell (existing, already has sidebar_org.html)
  organisations/         # Superadmin org management templates
  accounts/              # Auth templates (shared)
  regions/               # NEW — Org Admin region templates
    list.html
  shops/                 # NEW — Org Admin shop templates
    list.html
  team/                  # NEW — Org Admin team templates
    list.html
  org/                   # NEW — Org Admin shell pages
    dashboard.html       # replaces organisations/org_dashboard.html
    profile.html         # Org Admin profile (same view, org shell)
  emails/
    team_invitation.html  # NEW
    team_invitation.txt   # NEW
```

---

## Data Model Additions (Phase 6)

### Models to add / modify

**MODIFY: apps/accounts/models.py — User**
Add fields (new migration required):
```python
invited_by = models.ForeignKey(
    "accounts.User",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="invited_users",
)
invited_at = models.DateTimeField(null=True, blank=True)
accepted_at = models.DateTimeField(null=True, blank=True)
```

**MODIFY: apps/accounts/models.py — InvitationToken**
Current `InvitationToken` is tightly coupled to `Organisation` (not the invited user directly).
For team invitations (ORG_ADMIN inviting STAFF_ADMIN), the pattern needs to extend to invite
a user to a role, not an org. Options:

Option A (recommended): Add `purpose` enum + nullable `invited_for_role` to existing `InvitationToken`:
```python
class InvitationToken(TimeStampedModel):
    class Purpose(models.TextChoices):
        ORG_ADMIN = "ORG_ADMIN", "Org Admin Setup"
        TEAM_MEMBER = "TEAM_MEMBER", "Team Member Invitation"

    purpose = models.CharField(
        max_length=20, choices=Purpose.choices, default=Purpose.ORG_ADMIN, db_index=True
    )
    # existing: organisation FK, invited_user, token_hash, is_used, expires_at
    # new: invited_for_role (null = ORG_ADMIN purpose; populated for TEAM_MEMBER)
    invited_for_role = models.CharField(
        max_length=20, choices=User.Role.choices, null=True, blank=True
    )
```

This preserves backward compatibility with existing activation flow (purpose=ORG_ADMIN is default).
Team invite services create tokens with purpose=TEAM_MEMBER and populate `invited_for_role`.

Option B: Separate `TeamInvitationToken` model. Simpler model but duplicates the signing/expiry logic.
Reject: violates DRY and creates two token-hash lookup paths.

**NEW: apps/regions/models.py**
```python
class Region(TimeStampedModel):
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="regions",
    )
    name = models.CharField(max_length=100)
    region_id = models.CharField(max_length=20, db_index=True)  # auto-generated, org-scoped unique
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "regions_region"
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "region_id"],
                name="region_org_id_unique",
            )
        ]
        indexes = [
            models.Index(fields=["organisation", "is_active"], name="region_org_active_idx"),
        ]
```

**NEW: apps/shops/models.py**
```python
class Shop(TimeStampedModel):
    class ConnectionStatus(models.TextChoices):
        NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"
        CONNECTED = "CONNECTED", "Connected"
        EXPIRED = "EXPIRED", "Expired"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="shops",
    )
    region = models.ForeignKey(
        "regions.Region",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shops",
    )
    name = models.CharField(max_length=200, db_index=True)
    place_id = models.CharField(max_length=300, blank=True, db_index=True)
    connection_status = models.CharField(
        max_length=15,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.NOT_CONNECTED,
        db_index=True,
    )
    # Encrypted at rest — use django-cryptography EncryptedCharField
    google_refresh_token = models.TextField(blank=True)  # Fernet-encrypted
    api_key_hash = models.CharField(max_length=64, blank=True)  # SHA-256 of API key
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "shops_shop"
        indexes = [
            models.Index(
                fields=["organisation", "is_active", "connection_status"],
                name="shop_org_active_conn_idx",
            ),
        ]
```

**NEW: apps/accounts/models.py — StaffAccessScope** (see schema above in permission section)

---

## Build Order Within Each Phase

### Phase 6: Shell + Data Model Migrations

Sequential dependencies within Phase 6:

```
Step 6.1 — Data model migrations (BLOCKING for all subsequent phases)
  ├─ Modify User: add invited_by, invited_at, accepted_at + migration
  ├─ Modify InvitationToken: add purpose, invited_for_role + migration
  ├─ Create apps/regions/ + Region model + migration
  ├─ Create apps/shops/ + Shop model + migration (depends on regions migration)
  └─ Create StaffAccessScope in accounts + migration (depends on regions + shops)

Step 6.2 — Permission classes (depends on 6.1 — StaffAccessScope model)
  ├─ Add IsOrgAdmin, IsOrgScoped to apps/accounts/permissions.py
  └─ Add TenantScopedViewSet to apps/common/views.py

Step 6.3 — Org Admin shell (depends on 6.2)
  ├─ Update sidebar_org.html — full nav items (Dashboard, Shops, Regions, Team, Profile)
  ├─ Create templates/org/dashboard.html (replaces org_dashboard.html stub)
  ├─ Add /org/dashboard/ URL (new), keep /admin/org-dashboard/ as redirect
  └─ Wire @login_required + IsOrgAdmin decorator/mixin on dashboard view

Step 6.4 — Profile page reuse for Org Admin (depends on 6.3)
  └─ /org/profile/ URL → same profile services, base_org.html shell

Step 6.5 — Router + URL wiring skeleton (depends on 6.2)
  └─ Register RegionViewSet + ShopViewSet stubs in config/urls.py
     (empty viewsets that return 501 are fine — needed so URL names resolve for templates)
```

Phases 6.2 and 6.3 can be parallelised after 6.1 completes.

### Phase 7: Regions Module

Sequential within Phase 7 (depends on Phase 6 complete):

```
Step 7.1 — Region selectors + services (no UI dependency)
  ├─ apps/regions/selectors/regions.py
  ├─ apps/regions/services/regions.py — including generate_region_id()
  └─ Full test suite for selectors + services

Step 7.2 — Region API (depends on 7.1)
  ├─ apps/regions/serializers.py
  ├─ apps/regions/views.py — RegionViewSet (TenantScopedViewSet + IsOrgScoped)
  ├─ Register in config/urls.py router (replaces 6.5 stub)
  └─ API tests including query-count assertion

Step 7.3 — Region list template + React widget (depends on 7.2)
  ├─ templates/regions/list.html
  ├─ frontend/src/widgets/region-management/ — RegionTable, CreateRegionModal, etc.
  ├─ frontend/src/entrypoints/region-management.tsx
  └─ /org/regions/ URL → apps/regions/views.py template view

Step 7.4 — Delete guard (depends on 7.2)
  └─ delete_region() service checks shops assigned before deletion; raises BusinessRuleViolation
```

7.1 must precede 7.2. 7.3 and 7.4 can be parallelised after 7.2.

### Phase 8: Shops Module (depends on Phase 7 complete)

```
Step 8.1 — Google integrations layer (no UI dependency; can start in parallel with 7.x)
  ├─ apps/integrations/google/__init__.py, client.py, oauth.py, places.py, exceptions.py
  └─ Full test suite with mocked HTTP (responses library)

Step 8.2 — Shop selectors + services (depends on 8.1 for oauth/places services)
  ├─ apps/shops/selectors/shops.py — list_shops_for_user (branches on role)
  ├─ apps/shops/services/shops.py — create_shop_oauth, create_shop_manual,
  │     connect_shop_oauth, disconnect_shop, activate_shop, deactivate_shop
  ├─ apps/shops/services/api_keys.py — generate_api_key, rotate_api_key
  └─ Full test suite

Step 8.3 — Shop API (depends on 8.2)
  ├─ apps/shops/serializers.py
  ├─ apps/shops/views.py — ShopViewSet + oauth_initiate action
  ├─ apps/integrations/google/views.py — GoogleOAuthCallbackView
  ├─ Register in config/urls.py (shops router + oauth callback URL)
  └─ API tests including query-count assertions

Step 8.4 — Shop list template + React widget (depends on 8.3)
  ├─ templates/shops/list.html
  ├─ frontend/src/widgets/shop-management/ — ShopTable, CreateShopModal,
  │     ConnectShopModal (OAuth popup flow), ManageApiKeyModal
  └─ frontend/src/entrypoints/shop-management.tsx
```

8.1 can run in parallel with Phase 7. 8.2 depends on 8.1. 8.3 depends on 8.2. 8.4 depends on 8.3.

### Phase 9: Team Module (depends on Phase 7 + Phase 8 complete)

```
Step 9.1 — Team invitation service (modifies apps/accounts/)
  ├─ apps/accounts/services/team.py — invite_team_member, update_team_scope,
  │     enable_team_member, disable_team_member, remove_team_member, resend_team_invitation
  ├─ templates/emails/team_invitation.html + team_invitation.txt (NEW email templates)
  └─ Full test suite including email outbox assertions

Step 9.2 — Team acceptance flow (depends on 9.1)
  ├─ Extend invite_accept_view to handle purpose=TEAM_MEMBER tokens
  ├─ Separate template: templates/accounts/team_invite_accept.html
  └─ Redirect to /org/dashboard/ after acceptance (not /admin/org-dashboard/)

Step 9.3 — Team API (depends on 9.1)
  ├─ apps/accounts/serializers.py — TeamMemberReadSerializer, TeamMemberInviteSerializer
  ├─ apps/accounts/views.py — TeamViewSet (IsOrgAdmin for write actions, IsOrgScoped for read)
  ├─ Register in config/urls.py router
  └─ API tests

Step 9.4 — Team list template + React widget (depends on 9.3)
  ├─ templates/team/list.html
  ├─ frontend/src/widgets/team-management/ — TeamTable, InviteTeamMemberModal,
  │     EditScopeModal (region+shop multi-select), enable/disable modals
  └─ frontend/src/entrypoints/team-management.tsx
```

9.1 and 9.2 must precede 9.3. 9.4 depends on 9.3.

---

## Key Architecture Decisions (v0.2 additions)

| Decision | Rationale | Confidence |
|----------|-----------|------------|
| New apps (`regions/`, `shops/`) as separate bounded contexts | Avoids the ">8 models" split rule being violated; each has its own selectors/services | HIGH |
| `IsOrgScoped` in `apps/accounts/permissions.py` | Permissions are an accounts concern; avoids cross-app permission imports | HIGH |
| `TenantScopedViewSet` in `apps/common/views.py` | Cross-cutting base class; common/ is the right owner | HIGH |
| `StaffAccessScope` in `apps/accounts/` | It's about user access grants, not about shops or regions directly; avoids circular FK import | HIGH |
| OAuth callback as Django TemplateView (not DRF) | Must render HTML for postMessage; DRF JSON response cannot drive popup close | HIGH |
| `state` parameter signed with TimestampSigner | Reuses existing invitation token pattern; no new signing libraries | HIGH |
| Extend `InvitationToken` with `purpose` enum | Reuses 48h expiry, single-use, hash-in-DB infrastructure; avoids duplication | HIGH |
| `/org/*` URL prefix for new Org Admin views | Clean separation from `/admin/*` Superadmin views; `/admin/org-dashboard/` preserved as redirect | HIGH |
| React entrypoint per module (not one SPA) | Matches existing pattern; each module loads independently; no shared state problems | HIGH |
| `google_refresh_token` stored Fernet-encrypted in Shop.google_refresh_token | CLAUDE.md §11 requirement; key from GCP Secret Manager | HIGH |

---

## Anti-Patterns to Avoid (v0.2 specific)

| Anti-Pattern | Why Bad | Instead |
|---|---|---|
| Importing `Shop` or `Region` models at module level in `apps/accounts/` | Creates circular import (accounts ← regions ← accounts) | Use string FK labels in model definitions; use TYPE_CHECKING in service functions |
| Putting StaffAccessScope in `apps/regions/` or `apps/shops/` | Creates circular import — accounts imports these apps | StaffAccessScope lives in accounts/; references regions/shops via string FK labels |
| Putting OAuth callback view in apps/shops/ | shops/ is a domain app; OAuth callback is an integration concern | Put callback in apps/integrations/google/views.py |
| `window.opener.postMessage("*")` | Broadcasts to any origin; any page opened by the user can intercept | Always use `window.location.origin` as targetOrigin |
| Using `@login_required` on GoogleOAuthCallbackView | Google redirect lands in popup without session cookie (SameSite=Lax); login check fails | Verify identity via signed `state` parameter instead |
| Sharing state between shop-management and region-management React widgets | Different entrypoints; stale data, tight coupling | Use `window.dispatchEvent(new CustomEvent("shop:refresh"))` pattern; each widget is self-contained |
| Applying `TenantScopedViewSet` to superadmin viewsets | Superadmin views must see all orgs | `OrganisationViewSet` does NOT inherit TenantScopedViewSet |
| Omitting `organisation_id` filter in Staff Admin querysets | Relying solely on StaffAccessScope without org scoping still leaks if scope table is misconfigured | Always filter by `organisation_id` first, then apply scope filter for STAFF_ADMIN |

---

## Sources

- Direct codebase reading: `apps/accounts/models.py`, `apps/organisations/models.py`, `apps/accounts/permissions.py`, `apps/accounts/urls.py`, `apps/organisations/views.py`, `config/urls.py`, `apps/organisations/services/organisations.py`, `frontend/src/entrypoints/org-management.tsx`, `frontend/src/lib/toast.ts`, `templates/partials/sidebar_org.html`, `templates/base_org.html`
- CLAUDE.md §9 (tenant scoping), §11 (Google OAuth per-store, encrypted tokens), §5 (services/selectors pattern), §3 (app layout rules)
- `.planning/PROJECT.md` — v0.2 target feature list
- Existing `.planning/research/ARCHITECTURE.md` — Phase 1 patterns (confirmed still valid for v0.2)
