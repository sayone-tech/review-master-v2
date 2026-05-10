# Mobile API — JWT Authentication & API Documentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT authentication for mobile clients (Org Admin + Staff Admin), lock shop/region mutations to web-only, and serve Scalar + ReDoc API docs restricted to Superadmin.

**Architecture:** `djangorestframework-simplejwt` is added alongside the existing `SessionAuthentication` — web clients continue using sessions, mobile clients send `Authorization: Bearer <token>`. A new `RequiresSessionAuth` permission gates shop/region mutations to session clients only. `drf-spectacular` (already installed) is wired to serve a raw schema, Scalar UI, and ReDoc — all behind `IsSuperadmin`.

**Tech Stack:** `djangorestframework-simplejwt`, `drf-spectacular` (existing), `@scalar/api-reference` (CDN), Django REST Framework, pytest.

---

## File Map

| File | Action | What changes |
|---|---|---|
| `pyproject.toml` | Modify | Add `djangorestframework-simplejwt` |
| `config/settings/base.py` | Modify | Add `SIMPLE_JWT`, `SPECTACULAR_SETTINGS`, `JWTAuthentication` to auth classes, `rest_framework_simplejwt` apps to `INSTALLED_APPS` |
| `config/settings/test.py` | Modify | Add `rest_framework_simplejwt`, `rest_framework_simplejwt.token_blacklist` to `INSTALLED_APPS` |
| `config/urls.py` | Modify | Add token endpoints and schema/scalar/redoc URL routes |
| `apps/common/permissions.py` | Modify | Add `RequiresSessionAuth` class |
| `apps/accounts/serializers.py` | Modify | Add `MobileTokenObtainPairSerializer` |
| `apps/accounts/api_urls.py` | Modify | Register `MobileTokenObtainPairView` at `auth/token/` and `auth/token/refresh/` |
| `apps/common/views.py` | Modify | Add `ScalarDocsView` |
| `apps/shops/views.py` | Modify | Add `get_permissions()` override, `@extend_schema(exclude=True)` on mutations |
| `apps/regions/views.py` | Modify | Add `get_permissions()` override, `@extend_schema(exclude=True)` on mutations |
| `templates/api_docs/scalar.html` | Create | Scalar CDN template |
| `apps/accounts/tests/test_jwt.py` | Create | All JWT obtain/refresh/claims/access tests |
| `apps/common/tests/test_permissions.py` | Modify | Add `RequiresSessionAuth` tests |
| `apps/shops/tests/test_views.py` | Modify | Add mobile scoping tests |
| `apps/regions/tests/test_views.py` | Modify | Add mobile scoping tests |
| `apps/common/tests/test_docs_access.py` | Create | Scalar/ReDoc/schema access control tests |
| `schema.json` | Create | Generated via management command |

---

## Task 1: Install dependency and configure settings

**Files:**
- Modify: `pyproject.toml`
- Modify: `config/settings/base.py`
- Modify: `config/settings/test.py`

- [ ] **Step 1: Add dependency to pyproject.toml**

In `pyproject.toml`, add `"djangorestframework-simplejwt==5.4.0"` to the `dependencies` list (after the `djangorestframework` line):

```toml
  "djangorestframework==3.17.1",
  "djangorestframework-simplejwt==5.4.0",
```

- [ ] **Step 2: Install the dependency**

```bash
uv sync
```

Expected: resolves and installs `djangorestframework-simplejwt`.

- [ ] **Step 3: Add SimpleJWT apps to INSTALLED_APPS in base.py**

In `config/settings/base.py`, in the `INSTALLED_APPS` list after `"rest_framework"`, add:

```python
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
```

- [ ] **Step 4: Add SIMPLE_JWT settings to base.py**

In `config/settings/base.py`, after the closing `}` of the `REST_FRAMEWORK` dict, add:

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

- [ ] **Step 5: Add JWTAuthentication to REST_FRAMEWORK auth classes in base.py**

In `config/settings/base.py`, update `DEFAULT_AUTHENTICATION_CLASSES` (currently line ~209):

```python
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
```

- [ ] **Step 6: Add SPECTACULAR_SETTINGS to base.py**

After the `SIMPLE_JWT` block, add:

```python
SPECTACULAR_SETTINGS = {
    "TITLE": "Review Master API",
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

- [ ] **Step 7: Add SimpleJWT apps to test.py INSTALLED_APPS**

In `config/settings/test.py`, in the `INSTALLED_APPS` list after `"rest_framework"`, add:

```python
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
```

- [ ] **Step 8: Run migration for token blacklist**

```bash
python manage.py migrate
```

Expected: applies `token_blacklist` migration creating `outstanding_tokens` and `blacklisted_tokens` tables.

- [ ] **Step 9: Verify import works**

```bash
python manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock config/settings/base.py config/settings/test.py
git commit -m "feat(jwt): install simplejwt, configure SIMPLE_JWT and SPECTACULAR_SETTINGS"
```

---

## Task 2: RequiresSessionAuth permission

**Files:**
- Modify: `apps/common/permissions.py`
- Modify: `apps/common/tests/test_permissions.py`

- [ ] **Step 1: Write the failing test**

In `apps/common/tests/test_permissions.py`, add at the end of the file:

```python
import pytest
from rest_framework.authentication import SessionAuthentication
from rest_framework.test import APIRequestFactory

from apps.accounts.tests.factories import UserFactory
from apps.common.permissions import RequiresSessionAuth


@pytest.fixture
def factory():
    return APIRequestFactory()


@pytest.mark.django_db
def test_requires_session_auth_allows_session(factory):
    """Session-authenticated requests are permitted."""
    user = UserFactory(role="ORG_ADMIN")
    request = factory.get("/")
    request.user = user
    request.successful_authenticator = SessionAuthentication()
    perm = RequiresSessionAuth()
    assert perm.has_permission(request, None) is True


@pytest.mark.django_db
def test_requires_session_auth_blocks_jwt(factory):
    """JWT-authenticated requests are denied."""
    from rest_framework_simplejwt.authentication import JWTAuthentication

    user = UserFactory(role="ORG_ADMIN")
    request = factory.get("/")
    request.user = user
    request.successful_authenticator = JWTAuthentication()
    perm = RequiresSessionAuth()
    assert perm.has_permission(request, None) is False


@pytest.mark.django_db
def test_requires_session_auth_blocks_no_auth(factory):
    """Requests with no authenticator are denied."""
    user = UserFactory(role="ORG_ADMIN")
    request = factory.get("/")
    request.user = user
    request.successful_authenticator = None
    perm = RequiresSessionAuth()
    assert perm.has_permission(request, None) is False
```

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest apps/common/tests/test_permissions.py::test_requires_session_auth_allows_session -v
```

Expected: `ImportError` or `AttributeError` — `RequiresSessionAuth` not defined yet.

- [ ] **Step 3: Add RequiresSessionAuth to apps/common/permissions.py**

At the end of `apps/common/permissions.py`, add:

```python
class RequiresSessionAuth(BasePermission):
    """Grants access only to session-authenticated requests (web clients).

    JWT-authenticated mobile clients receive 403. Used to gate shop and region
    mutations so they are only reachable from the web app.
    """

    message = "This action is only available via the web application."

    def has_permission(self, request: Request, view: APIView) -> bool:
        from rest_framework.authentication import SessionAuthentication

        return isinstance(request.successful_authenticator, SessionAuthentication)
```

- [ ] **Step 4: Run all three permission tests**

```bash
pytest apps/common/tests/test_permissions.py -k "requires_session" -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/common/permissions.py apps/common/tests/test_permissions.py
git commit -m "feat(permissions): add RequiresSessionAuth for web-only mutations"
```

---

## Task 3: MobileTokenObtainPairSerializer + token endpoints

**Files:**
- Modify: `apps/accounts/serializers.py`
- Modify: `apps/accounts/api_urls.py`
- Modify: `config/urls.py`
- Create: `apps/accounts/tests/test_jwt.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/accounts/tests/test_jwt.py`:

```python
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def org(db):
    return OrganisationFactory()


@pytest.fixture
def org_admin(org):
    return UserFactory(
        email="orgadmin@example.com",
        role="ORG_ADMIN",
        organisation=org,
        password="testpass1234",
    )


@pytest.fixture
def staff_admin(org):
    return UserFactory(
        email="staff@example.com",
        role="STAFF_ADMIN",
        organisation=org,
        password="testpass1234",
    )


@pytest.fixture
def superadmin(db):
    return UserFactory(
        email="super@example.com",
        role="SUPERADMIN",
        organisation=None,
        password="testpass1234",
    )


TOKEN_URL = "/api/v1/auth/token/"
REFRESH_URL = "/api/v1/auth/token/refresh/"


# --- obtain ---

@pytest.mark.django_db
def test_obtain_token_org_admin(api_client, org_admin):
    """Org Admin can obtain access + refresh tokens."""
    resp = api_client.post(TOKEN_URL, {"email": "orgadmin@example.com", "password": "testpass1234"})
    assert resp.status_code == 200
    assert "access" in resp.data
    assert "refresh" in resp.data


@pytest.mark.django_db
def test_obtain_token_staff_admin(api_client, staff_admin):
    """Staff Admin can obtain tokens."""
    resp = api_client.post(TOKEN_URL, {"email": "staff@example.com", "password": "testpass1234"})
    assert resp.status_code == 200
    assert "access" in resp.data


@pytest.mark.django_db
def test_obtain_token_wrong_password(api_client, org_admin):
    resp = api_client.post(TOKEN_URL, {"email": "orgadmin@example.com", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_obtain_token_nonexistent_email(api_client, db):
    resp = api_client.post(TOKEN_URL, {"email": "nobody@example.com", "password": "testpass1234"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_obtain_token_inactive_user(api_client, org, db):
    user = UserFactory(
        email="inactive@example.com", role="ORG_ADMIN", organisation=org,
        password="testpass1234", is_active=False,
    )
    resp = api_client.post(TOKEN_URL, {"email": user.email, "password": "testpass1234"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_obtain_token_superadmin_blocked(api_client, superadmin):
    """Superadmin is blocked from obtaining mobile tokens."""
    resp = api_client.post(TOKEN_URL, {"email": "super@example.com", "password": "testpass1234"})
    assert resp.status_code == 403
    assert "superadmin" in str(resp.data).lower()


@pytest.mark.django_db
def test_obtain_token_missing_email(api_client, db):
    resp = api_client.post(TOKEN_URL, {"password": "testpass1234"})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_obtain_token_missing_password(api_client, db):
    resp = api_client.post(TOKEN_URL, {"email": "x@example.com"})
    assert resp.status_code == 400


# --- claims ---

@pytest.mark.django_db
def test_access_token_claims_org_admin(api_client, org_admin, org):
    """Access token contains role, organisation_id, full_name, email, user_id."""
    import base64
    import json

    resp = api_client.post(TOKEN_URL, {"email": "orgadmin@example.com", "password": "testpass1234"})
    access = resp.data["access"]
    # Decode payload (middle segment, no signature verification needed here)
    payload_b64 = access.split(".")[1]
    # Pad base64 string
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.b64decode(payload_b64))

    assert payload["role"] == "ORG_ADMIN"
    assert payload["organisation_id"] == org.pk
    assert payload["email"] == "orgadmin@example.com"
    assert payload["full_name"] == org_admin.full_name
    assert payload["user_id"] == org_admin.pk


@pytest.mark.django_db
def test_access_token_claims_staff_admin(api_client, staff_admin, org):
    import base64
    import json

    resp = api_client.post(TOKEN_URL, {"email": "staff@example.com", "password": "testpass1234"})
    access = resp.data["access"]
    payload_b64 = access.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.b64decode(payload_b64))

    assert payload["role"] == "STAFF_ADMIN"
    assert payload["organisation_id"] == org.pk


# --- refresh ---

@pytest.mark.django_db
def test_refresh_token_returns_new_pair(api_client, org_admin):
    """Refresh token returns a new access + refresh token."""
    obtain = api_client.post(TOKEN_URL, {"email": "orgadmin@example.com", "password": "testpass1234"})
    refresh_token = obtain.data["refresh"]

    resp = api_client.post(REFRESH_URL, {"refresh": refresh_token})
    assert resp.status_code == 200
    assert "access" in resp.data
    assert "refresh" in resp.data
    assert resp.data["refresh"] != refresh_token  # rotation: new token issued


@pytest.mark.django_db
def test_refresh_token_old_token_blacklisted(api_client, org_admin):
    """After rotation, the old refresh token is blacklisted."""
    obtain = api_client.post(TOKEN_URL, {"email": "orgadmin@example.com", "password": "testpass1234"})
    old_refresh = obtain.data["refresh"]
    api_client.post(REFRESH_URL, {"refresh": old_refresh})  # consume

    resp = api_client.post(REFRESH_URL, {"refresh": old_refresh})  # reuse old
    assert resp.status_code == 401


@pytest.mark.django_db
def test_refresh_token_invalid(api_client, db):
    resp = api_client.post(REFRESH_URL, {"refresh": "not.a.token"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_refresh_token_missing_field(api_client, db):
    resp = api_client.post(REFRESH_URL, {})
    assert resp.status_code == 400


# --- JWT access on protected endpoint ---

@pytest.mark.django_db
def test_jwt_access_on_protected_endpoint(api_client, org_admin):
    """A valid Bearer token grants access to a protected endpoint."""
    obtain = api_client.post(TOKEN_URL, {"email": "orgadmin@example.com", "password": "testpass1234"})
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {obtain.data['access']}")
    resp = api_client.get("/api/v1/reviews/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_no_token_rejected(api_client, db):
    resp = api_client.get("/api/v1/reviews/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_session_auth_still_works(org_admin):
    """Session-authenticated web clients continue to work unchanged."""
    from django.test import Client
    c = Client()
    c.force_login(org_admin)
    resp = c.get("/api/v1/reviews/")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest apps/accounts/tests/test_jwt.py -v 2>&1 | head -30
```

Expected: most fail with `404` (URL not registered yet) or `ImportError`.

- [ ] **Step 3: Add MobileTokenObtainPairSerializer to apps/accounts/serializers.py**

At the end of `apps/accounts/serializers.py`, add:

```python
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token


class MobileTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT serializer for mobile clients.

    Accepts email + password (not username). Blocks Superadmin accounts.
    Injects role, organisation_id, full_name, email into the access token payload.
    """

    username_field = "email"

    def validate(self, attrs: dict) -> dict:  # type: ignore[override]
        data = super().validate(attrs)
        user = self.user
        if not isinstance(user, User):
            raise serializers.ValidationError("Invalid credentials.")
        if user.organisation_id is None:
            raise PermissionDenied(
                "Mobile access is not available for superadmin accounts."
            )
        return data

    @classmethod
    def get_token(cls, user: User) -> Token:  # type: ignore[override]
        token = super().get_token(user)
        token["email"] = user.email
        token["full_name"] = user.full_name or ""
        token["role"] = user.role
        token["organisation_id"] = user.organisation_id
        return token
```

Add the missing import at the top of `apps/accounts/serializers.py`:

```python
from rest_framework.exceptions import PermissionDenied
```

- [ ] **Step 4: Register token endpoints in apps/accounts/api_urls.py**

Replace the contents of `apps/accounts/api_urls.py` with:

```python
from __future__ import annotations

from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.serializers import MobileTokenObtainPairSerializer
from apps.accounts.views import TeamViewSet
from rest_framework_simplejwt.views import TokenObtainPairView


class MobileTokenObtainPairView(TokenObtainPairView):
    serializer_class = MobileTokenObtainPairSerializer


router = SimpleRouter()
router.register(r"team", TeamViewSet, basename="team")

urlpatterns = [
    *router.urls,
]

token_urlpatterns = [
    __import__("django.urls", fromlist=["path"]).path(
        "auth/token/", MobileTokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    __import__("django.urls", fromlist=["path"]).path(
        "auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
]
```

Wait — that's ugly. Use clean imports instead. Replace contents of `apps/accounts/api_urls.py` with:

```python
from __future__ import annotations

from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.serializers import MobileTokenObtainPairSerializer
from apps.accounts.views import TeamViewSet


class MobileTokenObtainPairView(TokenObtainPairView):
    serializer_class = MobileTokenObtainPairSerializer


router = SimpleRouter()
router.register(r"team", TeamViewSet, basename="team")

urlpatterns = [
    *router.urls,
    path("auth/token/", MobileTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
```

- [ ] **Step 5: Run the JWT tests**

```bash
pytest apps/accounts/tests/test_jwt.py -v
```

Expected: all tests PASS. If `test_jwt_access_on_protected_endpoint` fails with 404, check that `/api/v1/reviews/` is reachable in the test DB (may need review factory).

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/serializers.py apps/accounts/api_urls.py apps/accounts/tests/test_jwt.py
git commit -m "feat(jwt): add MobileTokenObtainPairSerializer with email login and custom claims"
```

---

## Task 4: Shop + Region mobile scoping

**Files:**
- Modify: `apps/shops/views.py`
- Modify: `apps/regions/views.py`
- Modify: `apps/shops/tests/test_views.py`
- Modify: `apps/regions/tests/test_views.py`

- [ ] **Step 1: Write failing shop scoping tests**

In `apps/shops/tests/test_views.py`, add at the end:

```python
import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory


@pytest.fixture
def scoping_org(db):
    return OrganisationFactory()


@pytest.fixture
def scoping_org_admin(scoping_org):
    return UserFactory(role="ORG_ADMIN", organisation=scoping_org)


@pytest.fixture
def scoping_staff(scoping_org):
    return UserFactory(role="STAFF_ADMIN", organisation=scoping_org)


def jwt_client(user):
    """Return an APIClient authenticated via JWT for the given user."""
    from apps.accounts.api_urls import MobileTokenObtainPairView  # noqa: F401
    from django.test import RequestFactory
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    # Manually inject custom claims (mirrors MobileTokenObtainPairSerializer.get_token)
    token["email"] = user.email
    token["full_name"] = user.full_name or ""
    token["role"] = user.role
    token["organisation_id"] = user.organisation_id

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token.access_token)}")
    return client


@pytest.mark.django_db
def test_shop_list_allowed_for_staff_jwt(scoping_staff, scoping_org):
    """Staff Admin with JWT can list shops."""
    ShopFactory(organisation=scoping_org)
    client = jwt_client(scoping_staff)
    resp = client.get("/api/v1/shops/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_shop_list_allowed_for_org_admin_jwt(scoping_org_admin, scoping_org):
    """Org Admin with JWT can list shops."""
    ShopFactory(organisation=scoping_org)
    client = jwt_client(scoping_org_admin)
    resp = client.get("/api/v1/shops/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_shop_create_blocked_for_jwt(scoping_org_admin):
    """Org Admin with JWT cannot create shops (web-only)."""
    client = jwt_client(scoping_org_admin)
    resp = client.post("/api/v1/shops/", {"name": "New Shop"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_shop_update_blocked_for_jwt(scoping_org_admin, scoping_org):
    """Org Admin with JWT cannot update shops (web-only)."""
    shop = ShopFactory(organisation=scoping_org)
    client = jwt_client(scoping_org_admin)
    resp = client.patch(f"/api/v1/shops/{shop.pk}/", {"name": "Updated"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_shop_create_allowed_for_session(scoping_org_admin, scoping_org):
    """Org Admin with session auth can still create shops (web path unchanged)."""
    from django.test import Client
    c = Client()
    c.force_login(scoping_org_admin)
    resp = c.post(
        "/api/v1/shops/",
        data={"name": "Session Shop", "google_place_id": "abc"},
        content_type="application/json",
    )
    # 400 (validation) is fine — what matters is NOT 403
    assert resp.status_code != 403
```

- [ ] **Step 2: Write failing region scoping tests**

In `apps/regions/tests/test_views.py`, add at the end:

```python
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory


def jwt_client(user):
    token = RefreshToken.for_user(user)
    token["email"] = user.email
    token["full_name"] = user.full_name or ""
    token["role"] = user.role
    token["organisation_id"] = user.organisation_id
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token.access_token)}")
    return client


@pytest.fixture
def r_org(db):
    return OrganisationFactory()


@pytest.fixture
def r_org_admin(r_org):
    return UserFactory(role="ORG_ADMIN", organisation=r_org)


@pytest.fixture
def r_staff(r_org):
    return UserFactory(role="STAFF_ADMIN", organisation=r_org)


@pytest.mark.django_db
def test_region_list_allowed_for_staff_jwt(r_staff, r_org):
    RegionFactory(organisation=r_org)
    client = jwt_client(r_staff)
    resp = client.get("/api/v1/regions/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_region_create_blocked_for_jwt(r_org_admin):
    client = jwt_client(r_org_admin)
    resp = client.post("/api/v1/regions/", {"name": "New Region"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_region_delete_blocked_for_jwt(r_org_admin, r_org):
    region = RegionFactory(organisation=r_org)
    client = jwt_client(r_org_admin)
    resp = client.delete(f"/api/v1/regions/{region.pk}/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_region_create_allowed_for_session(r_org_admin):
    from django.test import Client
    c = Client()
    c.force_login(r_org_admin)
    resp = c.post(
        "/api/v1/regions/",
        data={"name": "Web Region"},
        content_type="application/json",
    )
    assert resp.status_code != 403
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
pytest apps/shops/tests/test_views.py -k "jwt" -v 2>&1 | tail -15
pytest apps/regions/tests/test_views.py -k "jwt" -v 2>&1 | tail -15
```

Expected: `test_shop_create_blocked_for_jwt` and `test_region_create_blocked_for_jwt` fail with `201` or `400` instead of `403`.

- [ ] **Step 4: Add get_permissions() to ShopViewSet**

In `apps/shops/views.py`, add this import at the top (after existing imports):

```python
from drf_spectacular.utils import extend_schema
from apps.common.permissions import RequiresSessionAuth
```

Then inside `ShopViewSet`, add `get_permissions()` after `pagination_class`:

```python
    def get_permissions(self):  # type: ignore[override]
        if self.action in ("create", "update", "partial_update"):
            return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
        return [IsOrgScoped()]
```

And add `@extend_schema(exclude=True)` decorator above the `create` method and `partial_update` / `update` methods in `ShopViewSet`. Find the `create` method and add:

```python
    @extend_schema(exclude=True)
    def create(self, request, *args, **kwargs):
        ...  # existing body unchanged
```

Do the same for `partial_update` and `update` if they exist in `ShopViewSet`.

- [ ] **Step 5: Add get_permissions() to RegionViewSet**

In `apps/regions/views.py`, add imports at the top:

```python
from drf_spectacular.utils import extend_schema
from apps.common.permissions import RequiresSessionAuth
```

Inside `RegionViewSet`, add `get_permissions()` after `http_method_names`:

```python
    def get_permissions(self):  # type: ignore[override]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
        return [IsOrgScoped()]
```

And decorate the `create`, `partial_update`, `update`, `destroy` methods with `@extend_schema(exclude=True)`.

- [ ] **Step 6: Run scoping tests**

```bash
pytest apps/shops/tests/test_views.py -k "jwt or session" -v
pytest apps/regions/tests/test_views.py -k "jwt or session" -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/shops/views.py apps/regions/views.py \
        apps/shops/tests/test_views.py apps/regions/tests/test_views.py
git commit -m "feat(mobile): block shop/region mutations for JWT clients via RequiresSessionAuth"
```

---

## Task 5: API Documentation (Scalar + ReDoc)

**Files:**
- Modify: `apps/common/views.py`
- Create: `templates/api_docs/scalar.html`
- Modify: `config/urls.py`
- Create: `apps/common/tests/test_docs_access.py`

- [ ] **Step 1: Write failing access control tests**

Create `apps/common/tests/test_docs_access.py`:

```python
from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory


@pytest.fixture
def org(db):
    return OrganisationFactory()


@pytest.fixture
def superadmin(db):
    return UserFactory(role="SUPERADMIN", organisation=None)


@pytest.fixture
def org_admin(org):
    return UserFactory(role="ORG_ADMIN", organisation=org)


@pytest.fixture
def staff_admin(org):
    return UserFactory(role="STAFF_ADMIN", organisation=org)


DOCS_URLS = [
    "/api/v1/schema/",
    "/api/v1/schema/scalar/",
    "/api/v1/schema/redoc/",
]


@pytest.mark.parametrize("url", DOCS_URLS)
@pytest.mark.django_db
def test_superadmin_can_access_docs(superadmin, url):
    c = Client()
    c.force_login(superadmin)
    resp = c.get(url)
    assert resp.status_code == 200


@pytest.mark.parametrize("url", DOCS_URLS)
@pytest.mark.django_db
def test_org_admin_cannot_access_docs(org_admin, url):
    c = Client()
    c.force_login(org_admin)
    resp = c.get(url)
    assert resp.status_code == 403


@pytest.mark.parametrize("url", DOCS_URLS)
@pytest.mark.django_db
def test_staff_admin_cannot_access_docs(staff_admin, url):
    c = Client()
    c.force_login(staff_admin)
    resp = c.get(url)
    assert resp.status_code == 403


@pytest.mark.parametrize("url", DOCS_URLS)
@pytest.mark.django_db
def test_unauthenticated_cannot_access_docs(url):
    c = Client()
    resp = c.get(url)
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_org_admin_jwt_cannot_access_schema(org_admin):
    """JWT clients cannot access docs even with valid token."""
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(org_admin)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token.access_token)}")
    resp = client.get("/api/v1/schema/")
    assert resp.status_code == 403
```

- [ ] **Step 2: Run to verify tests fail**

```bash
pytest apps/common/tests/test_docs_access.py -v 2>&1 | head -20
```

Expected: `404` for all docs URLs (not registered yet).

- [ ] **Step 3: Add ScalarDocsView to apps/common/views.py**

At the end of `apps/common/views.py`, add:

```python
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSuperadmin


class ScalarDocsView(APIView):
    """Scalar interactive API docs — Superadmin only."""

    permission_classes = [IsSuperadmin]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "api_docs/scalar.html"
    authentication_classes = [  # type: ignore[assignment]
        __import__(
            "rest_framework.authentication",
            fromlist=["SessionAuthentication"],
        ).SessionAuthentication
    ]

    def get(self, request: Request) -> Response:
        return Response()
```

Actually, use clean imports. Add these at the top of `apps/common/views.py` (with existing imports):

```python
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response as DRFResponse
from rest_framework.authentication import SessionAuthentication
```

And the view at the end of the file:

```python
class ScalarDocsView(APIView):
    """Scalar interactive API docs — Superadmin only."""

    permission_classes = [IsSuperadmin]  # type: ignore[assignment]
    renderer_classes = [TemplateHTMLRenderer]  # type: ignore[assignment]
    authentication_classes = [SessionAuthentication]  # type: ignore[assignment]
    template_name = "api_docs/scalar.html"

    def get(self, request: Request) -> DRFResponse:
        return DRFResponse()
```

- [ ] **Step 4: Create the Scalar HTML template**

```bash
mkdir -p templates/api_docs
```

Create `templates/api_docs/scalar.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <title>Review Master API</title>
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

- [ ] **Step 5: Register all docs URLs in config/urls.py**

In `config/urls.py`, add these imports at the top:

```python
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView
from apps.accounts.permissions import IsSuperadmin
from apps.common.views import ScalarDocsView
```

Then add the docs URL patterns to `urlpatterns`:

```python
    path(
        "api/v1/schema/",
        SpectacularAPIView.as_view(permission_classes=[IsSuperadmin]),
        name="schema",
    ),
    path(
        "api/v1/schema/scalar/",
        ScalarDocsView.as_view(),
        name="schema-scalar",
    ),
    path(
        "api/v1/schema/redoc/",
        SpectacularRedocView.as_view(
            url_name="schema",
            permission_classes=[IsSuperadmin],
        ),
        name="schema-redoc",
    ),
```

- [ ] **Step 6: Run the docs access tests**

```bash
pytest apps/common/tests/test_docs_access.py -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/common/views.py templates/api_docs/scalar.html \
        config/urls.py apps/common/tests/test_docs_access.py
git commit -m "feat(docs): add Scalar + ReDoc API docs restricted to Superadmin"
```

---

## Task 6: Full test run + schema export

**Files:**
- Create: `schema.json`

- [ ] **Step 1: Run the full test suite**

```bash
pytest --tb=short -q
```

Expected: all tests pass. Fix any failures before continuing.

- [ ] **Step 2: Export the OpenAPI schema**

```bash
python manage.py spectacular --file schema.json --validate
```

Expected: `schema.json` created at repo root with no validation errors.

- [ ] **Step 3: Commit schema and migrations**

```bash
git add schema.json
git add apps/*/migrations/  # token_blacklist migration if not already staged
git commit -m "feat(docs): export OpenAPI schema for Claude mobile development reference"
```

---

## Verification

After all tasks, confirm:

```bash
# All tests pass
pytest -q

# Django system check passes
python manage.py check

# JWT token endpoint responds
curl -s -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"<org_admin_email>","password":"<password>"}' | python -m json.tool

# Schema endpoint returns JSON (as logged-in superadmin via browser or session cookie)
# Navigate to: http://localhost:8000/api/v1/schema/scalar/
```
