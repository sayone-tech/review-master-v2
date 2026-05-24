# Mobile API — JWT Authentication & API Documentation

**Date:** 2026-05-09
**Status:** Approved
**Scope:** JWT authentication for mobile clients, mobile API scoping, Scalar/ReDoc docs

---

## 1. Context

The platform is adding a mobile app for Org Admins and Staff Admins. The existing API is at
`/api/v1/` and is currently session-authenticated (web only). Three additions are needed:

1. JWT authentication so mobile clients can log in and call all existing endpoints
2. Mobile-specific scoping — shop and region mutations blocked for JWT clients
3. Superadmin-only API documentation via Scalar (interactive) and ReDoc (read-only)

No new API prefix, no duplicated viewsets. All changes are additive.

---

## 2. JWT Authentication

### 2.1 New dependency

`djangorestframework-simplejwt` — planned in CLAUDE.md §9 ("token auth (SimpleJWT) only if a
separate client is added later").

Add to `pyproject.toml` dependencies and `INSTALLED_APPS`:
- `rest_framework_simplejwt`
- `rest_framework_simplejwt.token_blacklist` — required for refresh token rotation/blacklisting

### 2.2 Token strategy

| Token | Lifetime | Notes |
|---|---|---|
| Access | 60 minutes | Sent as `Authorization: Bearer <token>` header |
| Refresh | 30 days | Used to obtain a new access + refresh pair |
| Rotation | On | Every `/token/refresh/` call issues a new refresh token |
| Blacklist | On | Old refresh token is blacklisted after rotation |

Refresh token rotation means a stolen refresh token can only be used once before it's invalid.
Blacklisting adds one DB table (`outstanding_tokens`, `blacklisted_tokens`) via a migration.

### 2.3 Endpoints

```
POST /api/v1/auth/token/         ← obtain (login: email + password → access + refresh)
POST /api/v1/auth/token/refresh/ ← silent refresh (refresh token → new access + refresh)
```

No verify endpoint — not needed for mobile. Token decode is done client-side (JWT is self-contained).

### 2.4 Email-based login

The User model uses `email` as the login identifier, not `username`. A custom
`MobileTokenObtainPairSerializer` overrides the default to:

- Accept `email` + `password` (not `username`)
- Reject Superadmin accounts (`user.organisation_id is None`) with HTTP 403:
  `"Mobile access is not available for superadmin accounts."`
- Inject custom claims (see §2.5)

Lives in `apps/accounts/serializers.py` alongside existing serializers.
A corresponding `MobileTokenObtainPairView` in `apps/accounts/api_urls.py` wires it up.

### 2.5 Custom JWT claims

The access token payload includes extra claims so the mobile app has user context immediately
after login without a separate `/api/v1/me/` call:

```json
{
  "token_type": "access",
  "exp": 1234567890,
  "user_id": 42,
  "email": "user@example.com",
  "full_name": "Renjith Raj",
  "role": "ORG_ADMIN",
  "organisation_id": 7
}
```

### 2.6 Settings

Added to `config/settings/base.py`:

```python
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.MobileTokenObtainPairSerializer",
}
```

### 2.7 Authentication classes

`JWTAuthentication` added alongside `SessionAuthentication` in `DEFAULT_AUTHENTICATION_CLASSES`.
Web app continues to work unchanged — sessions are tried first, JWT second.

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    ...
}
```

---

## 3. Mobile API Scoping

### 3.1 Scope summary

| Resource | Mobile (JWT) | Web (Session) |
|---|---|---|
| Reviews | Full (list, retrieve, reply) | Full |
| Action Items | Full | Full |
| Notifications | Full | Full |
| Dashboard | Full | Full |
| Reply Templates | Full | Full |
| Team | Full | Full |
| Shops | **List + retrieve only** | Full |
| Regions | **List only** | Full |
| Sync progress / WebSocket | Not exposed | Full |

### 3.2 RequiresSessionAuth permission

New permission class in `apps/common/permissions.py`:

```python
class RequiresSessionAuth(BasePermission):
    """Grants access only to session-authenticated requests (web clients).
    JWT-authenticated mobile clients receive 403.
    """
    def has_permission(self, request, view):
        from rest_framework.authentication import SessionAuthentication
        return isinstance(request.successful_authenticator, SessionAuthentication)
```

### 3.3 ShopViewSet permission override

```python
def get_permissions(self):
    if self.action in ("create", "update", "partial_update"):
        return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
    return [IsOrgScoped()]
```

`list` and `retrieve` open to both roles on mobile. Mutations web-only for all users.

### 3.4 RegionViewSet permission override

```python
def get_permissions(self):
    if self.action in ("create", "update", "partial_update", "destroy"):
        return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
    return [IsOrgScoped()]
```

`list` open to both roles on mobile. Mutations web-only for all users.

### 3.5 Schema annotations

Mutating actions on Shop and Region are annotated with `@extend_schema(exclude=True)` so they
do not appear in the Scalar/ReDoc docs. The mobile developer sees only the endpoints they can
actually call.

---

## 4. API Documentation

### 4.1 Access control

All documentation URLs are restricted to **Superadmin only** via the existing `IsSuperadmin`
permission class. Org Admins and Staff Admins accessing these URLs receive 403.
Superadmin authenticates via the standard web session (no JWT needed for docs access).

### 4.2 URLs

```
GET /api/v1/schema/         ← raw OpenAPI 3.0 JSON (for Claude consumption)
GET /api/v1/schema/scalar/  ← Scalar interactive docs (Superadmin only)
GET /api/v1/schema/redoc/   ← ReDoc read-only docs (Superadmin only)
```

### 4.3 Scalar integration

drf-spectacular does not ship Scalar natively. A minimal custom Django view serves an HTML
page that loads Scalar from CDN and points it at `/api/v1/schema/`:

```python
# apps/common/views.py
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.permissions import IsSuperadmin

class ScalarDocsView(APIView):
    permission_classes = [IsSuperadmin]  # DRF handles 403 automatically
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "api_docs/scalar.html"

    def get(self, request):
        return Response()
```

Template at `templates/api_docs/scalar.html`:

```html
<!doctype html>
<html>
<head>
  <title>Review Bee API</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
  <script
    id="api-reference"
    data-url="/api/v1/schema/"
    data-proxy-url="https://proxy.scalar.com"
  ></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>
```

### 4.4 ReDoc

Served via drf-spectacular's built-in `SpectacularRedocView` with `permission_classes=[IsSuperadmin]`.
Zero extra template needed.

### 4.5 Raw schema endpoint

`SpectacularAPIView` with `permission_classes=[IsSuperadmin]` serves the raw OpenAPI JSON at
`/api/v1/schema/`. Used by Scalar as its data source and by Claude when building the mobile app.

### 4.6 SPECTACULAR_SETTINGS

Added to `config/settings/base.py`:

```python
SPECTACULAR_SETTINGS = {
    "TITLE": "Review Bee API",
    "DESCRIPTION": "Internal API for web and mobile clients. Not for external use.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"jwtAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "jwtAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}
```

### 4.7 Claude consumption workflow

Export the live schema to a static file whenever the API changes:

```bash
python manage.py spectacular --file schema.json
```

Commit `schema.json` to the repo. When building the mobile app with Claude:
> "Here's our OpenAPI schema — `schema.json`. Use it as the API reference."

Claude reads the file directly. No authenticated HTTP calls needed.

No sidebar link — docs are a developer tool. Navigate directly to `/api/v1/schema/scalar/`.

---

## 5. Testing

All tests live in `apps/accounts/tests/test_jwt.py`, `apps/shops/tests/test_views.py`,
`apps/regions/tests/test_views.py`, and `apps/common/tests/test_permissions.py`.
No real JWT calls — `APIClient` sets tokens directly via `credentials()`.

### 5.1 JWT token obtain (`POST /api/v1/auth/token/`)

| Test | Expected |
|---|---|
| Valid Org Admin email + password | 200 — returns `access` and `refresh` tokens |
| Valid Staff Admin email + password | 200 — returns `access` and `refresh` tokens |
| Wrong password | 401 |
| Non-existent email | 401 |
| Inactive user | 401 |
| Superadmin credentials | 403 — `"Mobile access is not available for superadmin accounts."` |
| Missing email field | 400 |
| Missing password field | 400 |

### 5.2 JWT claims

| Test | Expected |
|---|---|
| Decode access token after Org Admin login | Contains `user_id`, `email`, `full_name`, `role="ORG_ADMIN"`, `organisation_id` |
| Decode access token after Staff Admin login | Contains `role="STAFF_ADMIN"`, correct `organisation_id` |

### 5.3 JWT token refresh (`POST /api/v1/auth/token/refresh/`)

| Test | Expected |
|---|---|
| Valid refresh token | 200 — returns new `access` and new `refresh` token |
| Old refresh token after rotation | 401 — blacklisted |
| Tampered/invalid refresh token | 401 |
| Missing refresh field | 400 |

### 5.4 JWT access on protected endpoints

| Test | Expected |
|---|---|
| `GET /api/v1/reviews/` with valid `Bearer` access token | 200 |
| `GET /api/v1/reviews/` with expired access token | 401 |
| `GET /api/v1/reviews/` with no token and no session | 401 |
| `GET /api/v1/reviews/` with valid session cookie (web) | 200 — session auth still works |

### 5.5 RequiresSessionAuth — shop mutations

| Test | Setup | Expected |
|---|---|---|
| Staff Admin + JWT → `GET /api/v1/shops/` | JWT auth | 200 — list allowed |
| Org Admin + JWT → `GET /api/v1/shops/` | JWT auth | 200 — list allowed |
| Staff Admin + JWT → `POST /api/v1/shops/` | JWT auth | 403 |
| Org Admin + JWT → `POST /api/v1/shops/` | JWT auth | 403 |
| Org Admin + JWT → `PATCH /api/v1/shops/{id}/` | JWT auth | 403 |
| Org Admin + session → `POST /api/v1/shops/` | Session auth | 201 — web still works |
| Org Admin + session → `PATCH /api/v1/shops/{id}/` | Session auth | 200 — web still works |

### 5.6 RequiresSessionAuth — region mutations

| Test | Setup | Expected |
|---|---|---|
| Staff Admin + JWT → `GET /api/v1/regions/` | JWT auth | 200 — list allowed |
| Org Admin + JWT → `POST /api/v1/regions/` | JWT auth | 403 |
| Org Admin + JWT → `DELETE /api/v1/regions/{id}/` | JWT auth | 403 |
| Org Admin + session → `POST /api/v1/regions/` | Session auth | 201 — web still works |
| Org Admin + session → `DELETE /api/v1/regions/{id}/` | Session auth | 204 — web still works |

### 5.7 API documentation access

| Test | User | Expected |
|---|---|---|
| `GET /api/v1/schema/` | Superadmin (session) | 200 — OpenAPI JSON |
| `GET /api/v1/schema/scalar/` | Superadmin (session) | 200 — HTML page |
| `GET /api/v1/schema/redoc/` | Superadmin (session) | 200 — HTML page |
| `GET /api/v1/schema/scalar/` | Org Admin (session) | 403 |
| `GET /api/v1/schema/scalar/` | Staff Admin (session) | 403 |
| `GET /api/v1/schema/scalar/` | Unauthenticated | 403 |
| `GET /api/v1/schema/scalar/` | Org Admin (JWT) | 403 |

---

## 6. Files Changed

| File | Change |
|---|---|
| `pyproject.toml` | Add `djangorestframework-simplejwt` |
| `config/settings/base.py` | Add `SIMPLE_JWT`, `SPECTACULAR_SETTINGS`, update `REST_FRAMEWORK` auth classes, add apps to `INSTALLED_APPS` |
| `config/settings/test.py` | Add `rest_framework_simplejwt`, `rest_framework_simplejwt.token_blacklist` to `INSTALLED_APPS` |
| `config/urls.py` | Add token endpoints, schema/scalar/redoc URL routes |
| `apps/accounts/serializers.py` | Add `MobileTokenObtainPairSerializer` |
| `apps/accounts/api_urls.py` | Register `MobileTokenObtainPairView` |
| `apps/common/permissions.py` | Add `RequiresSessionAuth` |
| `apps/common/views.py` | Add `ScalarDocsView` |
| `apps/shops/views.py` | Add `get_permissions()` override, `@extend_schema(exclude=True)` on mutations |
| `apps/regions/views.py` | Add `get_permissions()` override, `@extend_schema(exclude=True)` on mutations |
| `templates/api_docs/scalar.html` | New template for Scalar UI |
| `schema.json` | Generated OpenAPI schema (via management command) |

New migration required for `rest_framework_simplejwt.token_blacklist`.

---

## 6. Out of Scope

- Mobile-specific serializer optimisation (response shapes stay identical to web)
- Push notifications for mobile
- Sync progress / WebSocket (no mobile use case)
- Shop / region create, update, destroy on mobile (web-only via `RequiresSessionAuth`)
- Superadmin mobile access (blocked at token obtain step)
