# Phase 6: Org Admin Shell - Research

**Researched:** 2026-04-27
**Domain:** Multi-tenant Django 6 shell — RBAC permissions, tenant isolation, data model migrations, field encryption, sequence generation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Dashboard welcome card**
- Heading: "Welcome, {first name}" — split `user.full_name` on first space for first name; fall back to the part before `@` in `user.email` if full_name is blank
- Supporting text (when regions exist): org name displayed as subtitle + "Manage your shops, regions and team from here."
- Both rendered in a single white card, max-w-[560px], matching the existing stub card shell

**Zero-regions setup banner (SHEL-03)**
- Yellow info banner — appears only when the organisation has zero Regions (dynamic check: `Region.objects.filter(organisation=user.organisation).count() == 0` in the view, passed as `show_setup_banner=True` in template context)
- Banner copy: "Get started by creating your first region…" + "Create Region" CTA
- CTA links to `/admin/org/regions/` (stub page in Phase 6; becomes real Regions list in Phase 7)
- Once org has ≥1 Region the banner is gone; no user-dismissal required

**URL structure**
- All new Org Admin pages use the `/admin/org/*` prefix namespace
- Alias approach for dashboard URL: register both `/admin/org-dashboard/` (existing name `org_admin_dashboard`) AND `/admin/org/dashboard/` pointing to the same view. `invite_accept_view` continues to call `reverse("org_admin_dashboard")` → unchanged. All new links (sidebar, login redirect) use `/admin/org/dashboard/`.
- Separate profile URL: `/admin/org/profile/` for Org Admin; Superadmin keeps `/admin/profile/`. Both reuse the same profile services.
- Org Admin profile view extends `base_org.html`; Superadmin profile view extends `base.html`.
- Final stub URLs registered in Phase 6: `/admin/org/regions/` (name: `org_regions`), `/admin/org/shops/` (name: `org_shops`), `/admin/org/team/` (name: `org_team`)

**Sidebar (SHEL-01)**
- Update `templates/partials/sidebar_org.html` to six items in order: Dashboard, Shops, Regions, Team, Profile (top nav group) + Logout (bottom-pinned)
- Icons: layout-dashboard, store, map-pin, users, user, log-out (Lucide)
- Yellow active state on current page — reuse existing `_nav_item.html` active-state logic
- Sidebar structure (HTML, Alpine.js, mobile drawer) is already complete — only nav items change

**Stub pages for Shops / Regions / Team**
- One shared stub view `org_stub_view(request, section: str)` in `apps/organisations/views.py`
- Renders `organisations/org_stub.html` extending `base_org.html`; template receives `section` as display title
- Uses the existing `components/empty_state.html` component: icon + "{section}" heading + "This section is coming soon." subtext
- Three URL patterns registered: `/admin/org/regions/`, `/admin/org/shops/`, `/admin/org/team/`

**Login redirect for direct logins**
- `CustomLoginView.form_valid()` overridden: check `user.role` and redirect:
  - `SUPERADMIN` → `/admin/organisations/`
  - `ORG_ADMIN` → `/admin/org/dashboard/`
  - Anything else (including `STAFF_ADMIN`) → `settings.LOGIN_REDIRECT_URL` (fallback)
- `LOGIN_REDIRECT_URL` remains `/dashboard/` as ultimate fallback

**Permission classes**
- `IsOrgAdmin` (new, `apps/accounts/permissions.py`): rejects non-ORG_ADMIN roles with 403
- `IsOrgScoped` (new, `apps/common/permissions.py`): rejects requests where `user.organisation_id` doesn't match queryset tenant scope; returns 403 (not redirect)
- Both Org Admin template views AND DRF viewsets enforce `IsOrgAdmin` + `IsOrgScoped`
- Staff Admins hitting Org Admin-only pages → 403

**TenantScopedViewSet**
- Base class in `apps/common/viewsets.py`; overrides `get_queryset()` to filter by `organisation_id=self.request.user.organisation_id`
- All Phase 7–9 DRF viewsets inherit from this
- Cross-tenant isolation test fixture lives in `apps/common/tests/fixtures.py`

**CI query-count ceiling fixture (XMOD-05)**
- Shared pytest fixture `assert_query_ceiling(response, max_queries)` in `apps/common/tests/fixtures.py` (or `conftest.py`)
- Every Phase 7–9 list endpoint test imports this fixture and asserts a fixed ceiling

**Profile page reuse (SHEL-04)**
- New view `org_profile_view` in `apps/accounts/views.py` (or `apps/organisations/views.py`)
- Requires `IsOrgAdmin` permission
- Renders `accounts/org_profile.html` extending `base_org.html`
- Same form classes (`ProfileNameForm`, `ProfilePasswordChangeForm`), same services, same Alpine.js strength indicator pattern
- New URLs: `/admin/org/profile/update-name/`, `/admin/org/profile/change-password/`

### Claude's Discretion
- Exact migration file names (follow project naming convention — descriptive, not auto-generated)
- django-sequences Django 6 smoke test implementation (simple management command or pytest autouse fixture that calls `get_next_value("test")` and fails fast if it errors)
- FERNET_KEYS settings loading pattern (env var in local, GCP Secret Manager in production) — now confirmed as `SALT_KEY`
- `StaffAccessScope` model detail (scope_type enum values, nullable fields) — follows research notes
- Exact `InvitationToken.purpose` enum values for step 1 of expand-contract

### Deferred Ideas (OUT OF SCOPE)
- Staff Admin dashboard and login redirect — Phase 9
- Hard delete for org admin profile — not in scope
- HTMX partial updates for profile name — deferred (Phase 5 decision carried forward)

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SHEL-01 | Org Admin sidebar shows six items (Dashboard, Shops, Regions, Team, Profile, Logout) with correct icons and yellow active state | Sidebar HTML exists with two items; research confirms `_nav_item.html` active state logic is reusable; four items to add with Lucide icons |
| SHEL-02 | Org Admin lands on /admin/org/dashboard after login with "Welcome, {Name}" card | `org_admin_dashboard` view and `org_dashboard.html` stub both exist; alias URL pattern + `CustomLoginView.form_valid()` override documented |
| SHEL-03 | Dashboard displays yellow info banner "Get started by creating your first region…" with "Create Region" CTA when org has zero Regions | Requires `Region` model to exist (migration in this phase); Region.objects.filter() in view context; yellow banner pattern from design system |
| SHEL-04 | Profile page at /admin/org/profile reuses Phase 1 two-card layout (name edit-in-place, password change with strength indicator) | `profile.html` and profile services fully built; org profile is a copy-and-extend with `base_org.html` and `IsOrgAdmin` permission |
| XMOD-05 | All Phase 2 list endpoints render within query-count ceilings asserted in CI tests (no N+1 regardless of result size) | Infrastructure phase: `assert_query_ceiling` fixture + `TenantScopedViewSet` + cross-tenant isolation test in `apps/common/tests/`; actual enforcement in Phase 7–9 |

</phase_requirements>

---

## Summary

Phase 6 is an **infrastructure and shell phase** — no feature modules are completed, but it establishes every shared foundation that Phases 7–9 depend on. The deliverables split into five clusters:

1. **Data model migrations** — five additive migrations (User extensions, InvitationToken purpose column, Region app, Shop app, StaffAccessScope) creating the v0.2 schema without breaking the v1.0 activation flow.
2. **Security foundation** — `IsOrgAdmin`, `IsOrgScoped` (with `has_object_permission`), `TenantScopedViewSet`, cross-tenant isolation test fixture, and CI query-count ceiling fixture. These must all exist before the first Org Admin viewset in Phase 7.
3. **Org Admin navigation shell** — six-item sidebar, personalised dashboard (welcome card + conditional zero-regions banner), login redirect by role, and stub pages for Shops/Regions/Team.
4. **Profile page reuse** — org profile view at `/admin/org/profile/` sharing the same services and form classes as the Superadmin profile, rendered inside `base_org.html`.
5. **Package installation + smoke tests** — `django-fernet-encrypted-fields==0.4.0` installed with `SALT_KEY` loaded from GCP Secret Manager; `django-sequences==3.0` Django 6 smoke test (confirmed compatible).

**CRITICAL CORRECTION from prior STACK.md research:** The jazzband `django-fernet-encrypted-fields` package uses `SALT_KEY` (not `FERNET_KEYS`) as the settings key. The import path is `from encrypted_fields.fields import EncryptedTextField` (not `fernet_encrypted_fields`). Version 0.4.0 (released Apr 14, 2026) adds explicit Django 6.0 support and should be pinned instead of 0.3.1.

**Primary recommendation:** Implement in strict dependency order — migrations first (all five in a single wave), then permission infrastructure (IsOrgAdmin + IsOrgScoped + TenantScopedViewSet + test fixtures), then shell UI, then profile. Never start a Phase 7 viewset before the permission infrastructure is committed.

---

## Standard Stack

### Core (existing — do not re-add)

| Library | Version | Purpose |
|---------|---------|---------|
| `django` | 6.0.2 | Framework |
| `djangorestframework` | 3.17.1 | API layer |
| `django-redis` | 5.4.0 | Cache + locks |
| `psycopg[binary]` | 3.2.3 | PostgreSQL driver |

### New Packages for This Phase

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| `django-fernet-encrypted-fields` | `==0.4.0` | `EncryptedTextField` for Shop google_refresh_token + api_key (models created in migrations this phase) | HIGH — verified Django 6.0 tested, released Apr 2026 |
| `django-sequences` | `==3.0` | Gapless per-org region ID generation (Region model created this phase; actual use in Phase 7) | HIGH — confirmed Django 6.0 supported per official docs |

**CRITICAL: `SALT_KEY` is the correct settings name** (not `FERNET_KEYS`). The import path is `from encrypted_fields.fields import EncryptedTextField`.

### Installation

```bash
# Production dependencies
uv add django-fernet-encrypted-fields==0.4.0
uv add django-sequences==3.0
```

```toml
# pyproject.toml additions
[project]
dependencies = [
  # ... existing pins ...
  "django-fernet-encrypted-fields==0.4.0",
  "django-sequences==3.0",
]
```

### mypy overrides to add

```toml
[[tool.mypy.overrides]]
module = ["encrypted_fields.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["sequences.*"]
ignore_missing_imports = true
```

### Settings additions

```python
# config/settings/base.py

# Field-level encryption — SALT_KEY is the correct setting for django-fernet-encrypted-fields
# Key loaded from GCP Secret Manager in production; from env in local/test
ENCRYPTED_FIELD_MODE = "ENCRYPT_AND_DECRYPT"  # default, explicit for clarity
SALT_KEY = env("FERNET_SALT_KEY")  # list supported for rotation: env.list("FERNET_SALT_KEY")
```

```python
# config/settings/local.py
SALT_KEY = "development-only-salt-key-not-for-production-use"

# config/settings/test.py
SALT_KEY = "test-only-salt-key-replace-in-prod"
```

---

## Architecture Patterns

### Recommended New File Structure (Phase 6 only)

```
apps/
  accounts/
    permissions.py          # ADD: IsOrgAdmin class
    views.py                # MODIFY: CustomLoginView.form_valid(), org_profile_view (new)
    urls.py                 # MODIFY: add /admin/org/profile/ URL patterns
    migrations/
      0003_user_invitationtoken_v02.py   # User extensions + InvitationToken purpose
      0004_staffaccessscope.py           # StaffAccessScope (depends on 0003 + regions + shops)

  common/
    permissions.py          # NEW: IsOrgScoped
    viewsets.py             # NEW: TenantScopedViewSet
    tests/
      conftest.py           # MODIFY or NEW: assert_query_ceiling fixture
      fixtures.py           # NEW: cross_tenant_isolation test fixtures

  organisations/
    views.py                # MODIFY: org_admin_dashboard (personalised), org_stub_view (new)
    urls.py                 # MODIFY: add /admin/org/dashboard/, stub URLs

  regions/                  # NEW APP (entire directory)
    __init__.py
    apps.py
    models.py               # Region model only (no services/selectors until Phase 7)
    migrations/
      0001_initial.py       # Region model

  shops/                    # NEW APP (entire directory)
    __init__.py
    apps.py
    models.py               # Shop model only (no services/selectors until Phase 8)
    migrations/
      0001_initial.py       # Shop model (depends on regions 0001)

templates/
  accounts/
    org_profile.html        # NEW: copy of profile.html, {% extends "base_org.html" %}
  organisations/
    org_stub.html           # NEW: stub page template
```

### Pattern 1: IsOrgAdmin Permission Class

**What:** Role check that rejects anyone who is not `ORG_ADMIN` or lacks an `organisation_id`.
**When to use:** All Org Admin template views and DRF viewsets. Compose with `IsOrgScoped` for DRF.
**File:** `apps/accounts/permissions.py` (alongside existing `IsSuperadmin`)

```python
# apps/accounts/permissions.py
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
```

**For template views:** Use a decorator/mixin wrapping `@login_required` + role check + redirect 403.

```python
# apps/accounts/permissions.py (Django template view decorator)
from functools import wraps
from django.http import HttpResponseForbidden

def org_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not isinstance(user, User):
            return redirect("/login/")
        if user.role != User.Role.ORG_ADMIN or user.organisation_id is None:
            return HttpResponseForbidden("Organisation Admin role required.")
        return view_func(request, *args, **kwargs)
    return wrapper
```

### Pattern 2: IsOrgScoped Permission Class

**What:** Checks `user.organisation_id` is non-null and (for object-level) verifies `obj.organisation_id == user.organisation_id`.
**When to use:** All DRF viewsets accessed by Org Admin or Staff Admin. Implement BOTH `has_permission` and `has_object_permission`.
**File:** `apps/common/permissions.py` (new file — `common/` owns cross-cutting concerns)

```python
# apps/common/permissions.py
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.accounts.models import User


class IsOrgScoped(BasePermission):
    """Allow ORG_ADMIN or STAFF_ADMIN with an organisation.

    CRITICAL: Implements has_object_permission to prevent IDOR on mutations.
    has_object_permission is only called when has_permission returns True.
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

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        """Verify the object belongs to the requesting user's organisation."""
        user = request.user
        obj_org_id = getattr(obj, "organisation_id", None)
        if obj_org_id is None:
            return False
        return bool(obj_org_id == user.organisation_id)
```

**Why `has_object_permission` is required:**
DRF's `has_object_permission` defaults to `True`. Without an explicit override, any ORG_ADMIN can PATCH/DELETE objects belonging to other organisations via `PATCH /api/v1/shops/42/` even when `get_queryset()` is correctly scoped. The queryset scope prevents leaks on list endpoints; `has_object_permission` prevents IDOR on detail/mutation endpoints.

### Pattern 3: TenantScopedViewSet

**What:** Base viewset that injects `organisation_id` filter into every `get_queryset()` call.
**When to use:** All Org Admin DRF viewsets in Phases 7–9.
**File:** `apps/common/viewsets.py` (new file)

```python
# apps/common/viewsets.py
from __future__ import annotations
from rest_framework.viewsets import GenericViewSet
from django.db.models import QuerySet


class TenantScopedViewSet(GenericViewSet):
    """Base for ALL Org Admin and Staff Admin DRF viewsets.

    Filters every get_queryset() to the authenticated user's organisation.
    Superadmin viewsets MUST NOT inherit this class.

    NEVER override get_queryset() without calling super() first, and NEVER
    remove the organisation_id filter without an explicit comment.
    """

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()
        org_id = self.request.user.organisation_id  # type: ignore[union-attr]
        if org_id is None:
            return qs.none()  # safety net: no org → no data
        return qs.filter(organisation_id=org_id)
```

### Pattern 4: CustomLoginView.form_valid() Override

**What:** Role-based redirect after successful login.
**When to use:** Already exists in `apps/accounts/views.py`; extend `form_valid()`.
**Critical:** The session expiry logic must be preserved exactly as-is.

```python
# apps/accounts/views.py — extend existing form_valid
def form_valid(self, form: CustomAuthenticationForm) -> HttpResponse:
    remember = self.request.POST.get("remember_me")
    # Call super() FIRST (authenticates + sets session)
    response = super().form_valid(form)
    # Set session expiry AFTER super() (super sets a session)
    if remember:
        self.request.session.set_expiry(SESSION_AGE_30D)
    else:
        self.request.session.set_expiry(SESSION_AGE_24H)
    # Role-based redirect OVERRIDES Django's get_success_url()
    user = self.request.user
    if not isinstance(user, User):
        return response
    if user.role == User.Role.SUPERADMIN:
        return redirect("/admin/organisations/")
    if user.role == User.Role.ORG_ADMIN and user.organisation_id is not None:
        return redirect("/admin/org/dashboard/")
    return response  # fallback to LOGIN_REDIRECT_URL
```

**Important:** `super().form_valid()` calls `auth.login()` internally, so `self.request.user` is the authenticated user after the call. The redirect must come AFTER `super()` to get the correct user.

### Pattern 5: Data Models — Migration Order

Migration dependency chain (strict ordering required):

```
accounts/0003  — User (invited_by, invited_at, accepted_at) + InvitationToken (purpose, invited_for_role)
  ↓
regions/0001   — Region model (FK to organisations.Organisation)
  ↓
shops/0001     — Shop model (FK to regions.Region + organisations.Organisation)
  ↓
accounts/0004  — StaffAccessScope (FK to accounts.User + regions.Region + shops.Shop via string labels)
```

**Why StaffAccessScope is last:** It FKs to both regions and shops (as string labels in the model definition to avoid circular imports), so the Region and Shop tables must already exist in the DB.

### Pattern 6: InvitationToken Expand-Contract (Step 1)

**What:** Add `purpose` and `invited_for_role` as nullable columns to preserve backward compatibility with live tokens. DO NOT make `purpose` non-null yet.

```python
# apps/accounts/migrations/0003_user_invitationtoken_v02.py
# Schema changes ONLY — no data migration in step 1

class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_organisation_invitationtoken")]

    operations = [
        # User extensions
        migrations.AddField(
            model_name="user",
            name="invited_by",
            field=models.ForeignKey(
                "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                related_name="invited_users",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="invited_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="accepted_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        # InvitationToken purpose (nullable for backward compat — step 1 of 3)
        migrations.AddField(
            model_name="invitationtoken",
            name="purpose",
            field=models.CharField(
                max_length=20,
                choices=[("ORG_ADMIN", "Org Admin Setup"), ("TEAM_MEMBER", "Team Member Invitation")],
                null=True,  # null until backfill in Phase 9
                blank=True,
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="invitationtoken",
            name="invited_for_role",
            field=models.CharField(
                max_length=20,
                choices=[("SUPERADMIN", "Superadmin"), ("ORG_ADMIN", "Org Admin"), ("STAFF_ADMIN", "Staff Admin")],
                null=True,
                blank=True,
            ),
        ),
    ]
```

**Activation view compatibility:** The existing `invite_accept_view` reads `token.organisation` and `token.is_used` — it does NOT read `purpose`. Adding `purpose=NULL` columns does not break the existing activation flow. Step 2 (backfill + non-null) happens in Phase 9.

### Pattern 7: Region Model

```python
# apps/regions/models.py
from django.db import models
from apps.common.models import TimeStampedModel


class Region(TimeStampedModel):
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="regions",
    )
    name = models.CharField(max_length=100)
    region_id = models.CharField(max_length=20, db_index=True)  # e.g., "ABC-001"
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

    def __str__(self) -> str:
        return f"{self.name} ({self.region_id})"
```

**No services/selectors/views in Phase 6** — the Region app is scaffolded with models and migrations only. Phase 7 adds business logic.

### Pattern 8: Shop Model

```python
# apps/shops/models.py
from django.db import models
from encrypted_fields.fields import EncryptedTextField  # jazzband package
from apps.common.models import TimeStampedModel


class Shop(TimeStampedModel):
    class ConnectionMethod(models.TextChoices):
        GOOGLE_OAUTH = "GOOGLE_OAUTH", "Google OAuth"
        MANUAL = "MANUAL", "Manual API Key"
        NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"

    class ConnectionStatus(models.TextChoices):
        CONNECTED = "CONNECTED", "Connected"
        EXPIRED = "EXPIRED", "Connection Expired"
        ERROR = "ERROR", "Connection Error"
        QUOTA_EXCEEDED = "QUOTA_EXCEEDED", "Quota Exceeded"
        NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"

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
    phone = models.CharField(max_length=20, blank=True)
    street_address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    place_id = models.CharField(max_length=300, blank=True, db_index=True)
    connection_method = models.CharField(
        max_length=15,
        choices=ConnectionMethod.choices,
        default=ConnectionMethod.NOT_CONNECTED,
        db_index=True,
    )
    connection_status = models.CharField(
        max_length=15,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.NOT_CONNECTED,
        db_index=True,
    )
    # Encrypted at rest — SALT_KEY in settings drives Fernet encryption
    google_refresh_token = EncryptedTextField(blank=True)
    api_key = EncryptedTextField(blank=True)  # manual fallback only
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "shops_shop"
        indexes = [
            models.Index(
                fields=["organisation", "is_active", "connection_status"],
                name="shop_org_active_conn_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.name
```

**Note on `EncryptedTextField`:** Unlike `CharField`, `EncryptedTextField` stores ciphertext as text. The field is transparent on read/write — no special handling needed. Do NOT add `db_index` to encrypted fields — they cannot be indexed (ciphertext is per-row unique).

### Pattern 9: StaffAccessScope Model

```python
# apps/accounts/models.py — new model added to existing file
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
    # String FK labels to avoid circular imports (accounts → regions, accounts → shops)
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

**Placement rationale:** `StaffAccessScope` lives in `apps/accounts/` because it's about user access grants. Its FKs to `regions.Region` and `shops.Shop` use string labels — Django resolves these at app-load time, avoiding import-time circular dependency.

### Pattern 10: Dashboard View (Personalised)

```python
# apps/organisations/views.py — extend existing org_admin_dashboard
@login_required
def org_admin_dashboard(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not isinstance(user, User):
        return redirect("/login/")
    if user.role == User.Role.SUPERADMIN:
        return redirect("/admin/organisations/")
    if user.role != User.Role.ORG_ADMIN or user.organisation is None:
        return HttpResponseForbidden()  # 403, not login redirect

    # First name extraction per CONTEXT.md decision
    first_name = ""
    if user.full_name:
        first_name = user.full_name.split()[0]
    elif user.email:
        first_name = user.email.split("@")[0]

    # Zero-regions banner check
    from apps.regions.models import Region
    show_setup_banner = not Region.objects.filter(
        organisation=user.organisation
    ).exists()  # .exists() is faster than .count() == 0

    return render(
        request,
        "organisations/org_dashboard.html",
        {
            "organisation": user.organisation,
            "first_name": first_name,
            "show_setup_banner": show_setup_banner,
        },
    )
```

**Note:** `.exists()` is used instead of `.count() == 0` — it short-circuits at the first row and is faster in PostgreSQL. Functionally identical for the banner condition.

### Pattern 11: Org Profile View

```python
# apps/accounts/views.py — new view alongside existing profile()
@login_required
def org_profile(request: HttpRequest) -> HttpResponse:
    """Org Admin profile page — /admin/org/profile/"""
    user = request.user
    if not isinstance(user, User):
        return redirect("/login/")
    if user.role != User.Role.ORG_ADMIN or user.organisation_id is None:
        return HttpResponseForbidden()
    return render(request, "accounts/org_profile.html")
```

Profile form POST handlers (`org_update_name_view`, `org_change_password_view`) mirror the existing `update_name_view` and `change_password_view` exactly, redirecting to `org_profile` instead of `profile`, calling the same services.

### Pattern 12: django-sequences Smoke Test

**What:** Verify `get_next_value()` works against the PostgreSQL database under Django 6. Runs once per test session.
**Implementation:** `pytest` autouse session-scoped fixture in `apps/common/tests/conftest.py`.

```python
# apps/common/tests/conftest.py (or apps/regions/tests/conftest.py)
import pytest

@pytest.fixture(scope="session", autouse=True)
def verify_django_sequences_compatibility(django_db_setup, django_db_blocker):
    """Smoke test: verify django-sequences works with Django 6 + PostgreSQL.

    If this fails, the fallback is a select_for_update() pattern on
    a dedicated Sequence model (see apps/regions/services/sequences.py).
    """
    with django_db_blocker.unblock():
        try:
            from django.db import transaction
            from sequences import get_next_value

            with transaction.atomic():
                val = get_next_value("phase6_smoke_test")
            assert isinstance(val, int) and val >= 1
        except Exception as exc:  # noqa: BLE001
            import warnings
            warnings.warn(
                f"django-sequences Django 6 smoke test FAILED: {exc}. "
                "Use select_for_update() fallback in regions.services.",
                stacklevel=2,
            )
```

**Select-for-update fallback** (only if smoke test fails):

```python
# apps/regions/services/sequences.py — fallback if django-sequences fails
from django.db import models, transaction
from apps.common.models import TimeStampedModel


class SequenceCounter(TimeStampedModel):
    """Fallback sequence counter using select_for_update().
    Only use if django-sequences fails Django 6 smoke test.
    """
    name = models.CharField(max_length=100, unique=True)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "common_sequence_counter"


@transaction.atomic
def get_next_sequence_value(name: str) -> int:
    counter, _ = SequenceCounter.objects.select_for_update().get_or_create(name=name)
    value = counter.next_value
    counter.next_value += 1
    counter.save(update_fields=["next_value", "updated_at"])
    return value
```

**Result:** django-sequences 3.0 supports Django 6.0 (confirmed HIGH confidence from official GitHub). The smoke test is still worthwhile as regression insurance. The fallback model adds ~30 lines and is trivially correct.

### Anti-Patterns to Avoid

- **Importing `Region` or `Shop` at module level in `apps/accounts/`:** Use string FK labels in model definitions; use `TYPE_CHECKING` guards in service functions that cross app boundaries.
- **Applying `TenantScopedViewSet` to `OrganisationViewSet`:** Superadmin views must see all orgs — `OrganisationViewSet` does NOT inherit `TenantScopedViewSet`.
- **Omitting `has_object_permission` from `IsOrgScoped`:** DRF's default `has_object_permission` returns `True`. Without override, any Org Admin can mutate another org's objects on detail endpoints.
- **Calling `Region.objects.count()` instead of `.exists()` for banner check:** `.count()` always executes a full `COUNT(*)`. `.exists()` short-circuits at the first row. Use `.exists()` for boolean "any records?" checks.
- **Renaming `InvitationToken` table in this phase:** Step 1 of expand-contract adds columns only. Table rename is Step 3, a post-v0.2 operation.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gapless region ID sequences | `max() + 1` counter | `django-sequences==3.0` | `max() + 1` is not atomic; races under concurrent creates produce duplicates; `UniqueConstraint` is backstop only |
| Field-level encryption | Custom `Fernet` in `save()` / `from_db_value()` | `django-fernet-encrypted-fields==0.4.0` | Handles key rotation, field transparency, migration compatibility; DIY breaks on schema changes |
| Per-row sequence locks | Advisory locks or app-level locks | `select_for_update()` on `SequenceCounter` (fallback) or `django-sequences` | `select_for_update()` is the only correct locking primitive for this; Redis locks don't protect DB-level sequences |

---

## Common Pitfalls

### Pitfall 1: SALT_KEY vs FERNET_KEYS

**What goes wrong:** Prior STACK.md research named the settings key `FERNET_KEYS`. The jazzband `django-fernet-encrypted-fields` package uses `SALT_KEY`. Setting `FERNET_KEYS` has no effect — the package silently falls back to using Django's `SECRET_KEY`, which means: (a) key rotation via GCP Secret Manager doesn't work, (b) Django `SECRET_KEY` rotation wipes all encrypted data.

**Prevention:** Set `SALT_KEY` in `config/settings/base.py`. In production, load from GCP Secret Manager. In test, use a fixed test-only string. Verify by calling `from encrypted_fields.fields import EncryptedTextField` in the Django shell and creating a model instance with an encrypted field — check that the DB column contains ciphertext, not plaintext.

**Detection:** `FERNET_KEYS` set in settings has no effect; `SALT_KEY` absent; encrypted field silently using Django `SECRET_KEY`.

### Pitfall 2: IsOrgScoped Missing has_object_permission

**What goes wrong:** `IsOrgScoped` implements only `has_permission`. Any Org Admin can `PATCH /api/v1/shops/42/` even if Shop 42 belongs to a different org. `has_object_permission` is never called for list endpoints, and its default return value in DRF is `True`. The queryset filter on list endpoints does not protect detail/mutation endpoints.

**Prevention:** Implement `has_object_permission` in `IsOrgScoped` as described in Pattern 2. The cross-tenant isolation test MUST include `PATCH` and `DELETE` requests with cross-org IDs.

**Detection:** `IsOrgScoped` class without `has_object_permission` method. Cross-tenant test returns 200 instead of 403 on PATCH.

### Pitfall 3: Login Redirect Breaks Remember-Me

**What goes wrong:** `CustomLoginView.form_valid()` is overridden and the session expiry logic is lost. Remember-me checkbox no longer extends the session.

**Prevention:** Call `super().form_valid(form)` first, then set session expiry, then check role for redirect. Return the role-specific redirect ONLY for Superadmin and Org Admin — let the `response = super().form_valid()` handle the default case so Django's `get_success_url()` logic for `next=` params remains intact.

**Warning signs:** After login, session expires at browser close regardless of remember-me checkbox state.

### Pitfall 4: `invite_accept_view` redirect to org_admin_dashboard

**What goes wrong:** `invite_accept_view` calls `reverse("org_admin_dashboard")` after successful activation. If the URL named `org_admin_dashboard` is changed or removed (instead of aliased), activation links break.

**Prevention:** Register BOTH URLs: the existing `/admin/org-dashboard/` keeps the name `org_admin_dashboard`, and the new `/admin/org/dashboard/` is a second route to the same view function. `invite_accept_view` is NOT modified — it continues calling `reverse("org_admin_dashboard")` which resolves to `/admin/org-dashboard/`. The login redirect and sidebar use `/admin/org/dashboard/` (the new URL).

**Detection:** `NoReverseMatch: org_admin_dashboard not found` if the old URL pattern is removed.

### Pitfall 5: StaffAccessScope FK App Label Not Using String Label

**What goes wrong:** `apps/accounts/models.py` imports `Region` or `Shop` at module level to define the ForeignKey. Django loads `accounts` before `regions` and `shops` (apps list order matters), raising `AppRegistryNotReady` or circular import errors.

**Prevention:** Always use string FK labels: `"regions.Region"`, `"shops.Shop"`. Django resolves these lazily during app registry setup. Do NOT use `from apps.regions.models import Region` at module level in `apps/accounts/`.

**Detection:** `AppRegistryNotReady` or `ImportError: cannot import name 'Region'` on server start.

### Pitfall 6: Shop EncryptedTextField Cannot Be Filtered

**What goes wrong:** A developer tries to add `db_index=True` to `google_refresh_token` or `api_key`, or writes a queryset `.filter(google_refresh_token=value)`. Encrypted field values are Fernet ciphertext — they are per-row unique even for identical plaintexts. Indexing and filtering are impossible.

**Prevention:** Never add `db_index` to encrypted fields. Never filter on encrypted fields. If lookup is needed (e.g., "find shop by API key"), store a HMAC/SHA-256 hash in a separate non-encrypted `CharField` and filter on the hash.

---

## Code Examples

### SALT_KEY Configuration Pattern

```python
# config/settings/base.py — correct setting name
SALT_KEY = env("FERNET_SALT_KEY")  # single key as str; list for rotation

# config/settings/local.py
SALT_KEY = "dev-salt-key-do-not-use-in-production-32ch"

# config/settings/test.py
SALT_KEY = "test-salt-key-for-unit-tests-only-32chars"
```

For key rotation (production):
```python
# config/settings/production.py
SALT_KEY = [
    env("FERNET_SALT_KEY_NEW"),  # encrypts new data
    env("FERNET_SALT_KEY_OLD"),  # decrypts old data
]
```

### Using django-sequences for Region ID

```python
# apps/regions/services/regions.py (Phase 7 — referenced here for planning context)
from django.db import transaction
from sequences import get_next_value
from apps.regions.models import Region
from apps.organisations.models import Organisation


@transaction.atomic
def generate_region_id(organisation: Organisation) -> str:
    """Generate a gapless, org-scoped region ID like 'ABC-001'.

    Uses django-sequences to prevent race conditions under concurrent creates.
    The sequence name is org-scoped to prevent cross-org collision.
    """
    seq = get_next_value(f"region_ids_org_{organisation.pk}")
    # Extract initials from org name (up to 3 uppercase letters)
    initials = "".join(c for c in organisation.name.upper() if c.isalpha())[:3] or "RGN"
    return f"{initials}-{seq:03d}"
```

### Cross-Tenant Isolation Test Fixture

```python
# apps/common/tests/fixtures.py
import pytest
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.db import connection
from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory


@pytest.fixture
def two_orgs_two_admins(db):
    """Two organisations with one Org Admin each — for cross-tenant isolation tests."""
    org_a = OrganisationFactory(name="Org A")
    org_b = OrganisationFactory(name="Org B")
    admin_a = UserFactory(role="ORG_ADMIN", organisation=org_a)
    admin_b = UserFactory(role="ORG_ADMIN", organisation=org_b)
    return {"org_a": org_a, "org_b": org_b, "admin_a": admin_a, "admin_b": admin_b}


@pytest.fixture
def assert_query_ceiling():
    """Assert a response was served within a fixed query count.

    Usage in list endpoint tests:
        def test_my_list(client, assert_query_ceiling):
            with CaptureQueriesContext(connection) as ctx:
                response = client.get("/api/v1/regions/")
            assert_query_ceiling(ctx, max_queries=5)
    """
    def _assert(ctx: CaptureQueriesContext, max_queries: int) -> None:
        count = len(ctx.captured_queries)
        assert count <= max_queries, (
            f"Query count {count} exceeds ceiling {max_queries}. "
            f"Queries: {[q['sql'][:100] for q in ctx.captured_queries]}"
        )
    return _assert
```

### Cross-Tenant Isolation Test (Phase 6 establishes, Phases 7–9 use)

```python
# apps/common/tests/test_tenant_isolation.py (scaffold — actual endpoints added per phase)
import pytest
from django.test import Client
from apps.common.tests.fixtures import two_orgs_two_admins  # noqa: F401


pytestmark = pytest.mark.django_db


def test_cross_tenant_template_view_forbidden(two_orgs_two_admins):
    """Org A admin cannot reach Org B's dashboard (role check only in Phase 6)."""
    client = Client()
    client.force_login(two_orgs_two_admins["admin_a"])
    # Each org admin should only see their own content
    response = client.get("/admin/org/dashboard/")
    assert response.status_code == 200
    # Verify context is scoped to org_a (not org_b)
    assert response.context["organisation"].pk == two_orgs_two_admins["org_a"].pk
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `django-cryptography` (abandoned 2022) | `django-fernet-encrypted-fields==0.4.0` | Django 6 + Python 3.12 support; active maintenance |
| `FERNET_KEYS` setting (from old package) | `SALT_KEY` setting (jazzband package) | Critical naming difference — wrong name silently falls back to SECRET_KEY |
| `from fernet_encrypted_fields.fields import ...` | `from encrypted_fields.fields import ...` | Correct import path for jazzband package |
| `django-cryptography`'s `encrypt=True` kwarg | `EncryptedTextField()` field class | Field class approach; no kwarg needed |
| django-sequences 3.0 tested through Django 5.0 | django-sequences 3.0 explicitly supports Django 6.0 | Confirmed HIGH confidence; no fallback needed but smoke test still useful |
| `django-fernet-encrypted-fields==0.3.1` (Nov 2025) | `==0.4.0` (Apr 2026) — adds explicit Django 6.0 support | Update the pin from prior STACK.md research |

---

## Open Questions

1. **`apps/common/permissions.py` vs `apps/accounts/permissions.py` for IsOrgScoped**
   - What we know: CONTEXT.md says `IsOrgScoped` in `apps/common/permissions.py`; prior ARCHITECTURE.md also suggests this. `IsOrgAdmin` stays in `apps/accounts/permissions.py` (alongside `IsSuperadmin`).
   - What's unclear: Whether a single `apps/common/permissions.py` file should contain both `IsOrgScoped` and import `IsOrgAdmin` for convenience, or whether they stay in separate files.
   - Recommendation: Follow CONTEXT.md exactly. `IsOrgAdmin` in `apps/accounts/permissions.py`, `IsOrgScoped` in `apps/common/permissions.py`. Both files import from `apps.accounts.models` which is fine (common → accounts is allowed in the dependency graph).

2. **Org profile view location**
   - What we know: CONTEXT.md says "in `apps/accounts/views.py` (or `apps/organisations/views.py`)"
   - What's unclear: Which app owns it
   - Recommendation: `apps/accounts/views.py` — profile is an accounts concern; the view uses accounts services. Org-specific template in `templates/accounts/org_profile.html`.

3. **SequenceCounter model for fallback**
   - What we know: django-sequences 3.0 is confirmed Django 6 compatible. The fallback is only needed if the smoke test fails.
   - Recommendation: Create the `SequenceCounter` model definition in `apps/common/models.py` and add its migration (no-cost insurance), but only call it from regions services if the smoke test fails. The migration adds a table that is never populated unless the fallback is activated.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `pytest apps/common/ apps/accounts/ apps/organisations/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SHEL-01 | Sidebar renders 6 items in correct order with yellow active state | Template render test | `pytest apps/organisations/tests/test_views.py::test_org_dashboard_sidebar -x` | ❌ Wave 0 |
| SHEL-02 | Org Admin lands on /admin/org/dashboard after login; welcome card shows first name | View test (role redirect + context) | `pytest apps/accounts/tests/test_views.py::test_login_redirect_by_role -x` | ❌ Wave 0 |
| SHEL-03 | Zero-regions banner shown when no regions; hidden when ≥1 region exists | View test (context flag) | `pytest apps/organisations/tests/test_views.py::test_org_dashboard_setup_banner -x` | ❌ Wave 0 |
| SHEL-04 | Org profile page renders correctly; name update and password change work | View + service tests | `pytest apps/accounts/tests/test_views.py::test_org_profile -x` | ❌ Wave 0 |
| XMOD-05 (infra) | `assert_query_ceiling` fixture available; TenantScopedViewSet filters by org | Unit tests for TenantScopedViewSet + isolation fixture | `pytest apps/common/tests/ -x` | ❌ Wave 0 |
| XMOD-05 (isolation) | Cross-tenant test asserts Org A admin gets 403/empty on Org B resources | Integration test | `pytest apps/common/tests/test_tenant_isolation.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest apps/common/tests/ apps/accounts/tests/ apps/organisations/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/common/tests/fixtures.py` — `two_orgs_two_admins` fixture, `assert_query_ceiling` fixture (REQ: XMOD-05)
- [ ] `apps/common/tests/conftest.py` — extend with `verify_django_sequences_compatibility` smoke test
- [ ] `apps/common/tests/test_tenant_isolation.py` — cross-tenant isolation scaffold (REQ: XMOD-05)
- [ ] `apps/accounts/tests/test_views.py` — add `test_login_redirect_by_role`, `test_org_profile` (REQ: SHEL-02, SHEL-04)
- [ ] `apps/organisations/tests/test_views.py` — add `test_org_dashboard_*` tests (REQ: SHEL-01, SHEL-03)
- [ ] `apps/regions/tests/` — minimal `__init__.py` + `factories.py` (no service tests until Phase 7)
- [ ] `apps/shops/tests/` — minimal `__init__.py` + `factories.py` (no service tests until Phase 8)
- [ ] `apps/accounts/tests/factories.py` — add `StaffAccessScopeFactory`

---

## Sources

### Primary (HIGH confidence)
- Direct codebase reading: `apps/accounts/models.py`, `apps/accounts/permissions.py`, `apps/accounts/views.py`, `apps/organisations/views.py`, `apps/organisations/urls.py`, `apps/accounts/urls.py`, `config/urls.py`, `apps/common/views.py`, `apps/common/models.py`, `templates/partials/sidebar_org.html`, `templates/organisations/org_dashboard.html`, `templates/accounts/profile.html`, `templates/partials/_nav_item.html`, `templates/base_org.html`
- [django-sequences GitHub](https://github.com/aaugustin/django-sequences) — Django 6.0 confirmed in supported versions list
- [jazzband/django-fernet-encrypted-fields GitHub](https://github.com/jazzband/django-fernet-encrypted-fields) — `SALT_KEY` setting name confirmed; `from encrypted_fields.fields import EncryptedTextField` import path
- [django-fernet-encrypted-fields PyPI](https://pypi.org/project/django-fernet-encrypted-fields/) — v0.4.0 released Apr 14, 2026; Django 6.0 explicitly tested

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` — pre-confirmed StaffAccessScope placement, TenantScopedViewSet pattern, import graph
- `.planning/research/PITFALLS.md` — NEW-C4 (cross-tenant IDOR), M6 (has_object_permission gap), NEW-C5 (expand-contract)
- `.planning/research/STACK.md` — package selection rationale (with correction: FERNET_KEYS → SALT_KEY, 0.3.1 → 0.4.0)

### Tertiary (LOW confidence — needs validation)
- None for Phase 6 core scope

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against PyPI and GitHub
- Architecture: HIGH — derived from direct codebase reading
- Permission patterns: HIGH — mirrors existing `IsSuperadmin` pattern exactly
- Migration order: HIGH — dependency graph is deterministic from FK structure
- SALT_KEY setting: HIGH — confirmed from jazzband GitHub README and PyPI page
- django-sequences Django 6: HIGH — confirmed from official project GitHub supported versions

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (30 days for stable patterns; package versions may update)

**CRITICAL CORRECTION from prior STACK.md:**
- `FERNET_KEYS` → correct setting is `SALT_KEY`
- `from fernet_encrypted_fields.fields import ...` → correct import is `from encrypted_fields.fields import ...`
- Version pin `==0.3.1` → update to `==0.4.0` (explicit Django 6.0 support added Apr 2026)
