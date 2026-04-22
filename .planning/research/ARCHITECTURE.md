# Architecture Patterns

**Domain:** Multi-tenant SaaS review management platform — Phase 1 Superadmin module
**Researched:** 2026-04-22
**Confidence:** HIGH

---

## System Overview

```
Browser
  ├─── Django Template Pages (server-rendered HTML)
  │       └─── Tailwind CSS
  │       └─── React widgets (mounted on <div id="..."> via JS bundle)
  │
  ├─── DRF JSON API  /api/v1/  (called by React widgets)
  │
  └─── Static assets (WhiteNoise / CDN)

Django (Cloud Run)
  ├─── config/           Project wiring: settings, urls, wsgi/asgi
  ├─── apps/accounts/    User model, session auth, invitations, RBAC
  ├─── apps/organisations/ Organisation CRUD, store allocation
  ├─── apps/stores/      Phase 2 (scaffolded in Phase 1)
  ├─── apps/reviews/     Phase 4 (scaffolded in Phase 1)
  ├─── apps/integrations/ Google API client (Phase 2+)
  └─── apps/common/      TimeStampedModel, UUIDModel, email service

PostgreSQL 16  — Primary datastore
Redis 7        — Cache (DB0), Throttle (DB1), Sessions (DB2)
Amazon SES     — Transactional email via django-ses
GCP Secret Manager — All credentials at runtime
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Does NOT Touch |
|-----------|---------------|-------------------|----------------|
| `apps/accounts` | Custom User model, session auth, password management, invitation token lifecycle, RBAC permission classes | `apps/organisations` (org FK on User), `apps/common` (email service) | Google API, reviews |
| `apps/organisations` | Organisation model, store allocation counter, status lifecycle, org-type enum | `apps/accounts` (invitation on create), `apps/stores` (Phase 2) | Reviews, integrations |
| `apps/stores` | Store model, org FK, Google Place linkage (Phase 2) | `apps/organisations`, `apps/integrations` | User auth, invitations |
| `apps/reviews` | Google review storage, sync state | `apps/stores`, `apps/integrations` | User management |
| `apps/integrations/google` | Google Business Profile API client, OAuth tokens per-store | `apps/stores`, `apps/reviews` | User model, organisations directly |
| `apps/common` | `TimeStampedModel`, `UUIDModel`, base pagination, exception classes, `send_transactional_email()` | All apps import FROM common; common imports from nothing | Business domain models |
| `config/` | Django project wiring: settings, urls, wsgi/asgi, celery (Phase 2) | All apps | Business logic of any kind |
| `frontend/` | React source for complex widgets. Compiled to `static/js/` bundles | Calls DRF API via fetch | Django templates directly; imports no Python |

---

## Data Flow

### 1. Superadmin page load (server-rendered shell, React widget for table)

```
Browser GET /organisations/
  → Django URL router
  → OrganisationListView (TemplateView)
      → Renders HTML shell with <div id="org-table-root" data-api-url="..." data-csrf-token="..."/>
  → Browser receives HTML
  → JS bundle loads, React mounts on #org-table-root
  → React fetches GET /api/v1/organisations/?search=&status=&page=1
      → DRF OrganisationViewSet.list()
          → selector: list_organisations_for_superadmin(search, status, type)
              → ORM: .select_related("created_by").prefetch_related("stores").annotate_store_counts()
          → Paginate → OrganisationReadSerializer → JSON response
  → React renders table
```

### 2. Create organisation flow

```
Browser POST /api/v1/organisations/  (React form submits JSON)
  → DRF OrganisationViewSet.create()
      → OrganisationCreateSerializer.is_valid()     # validation only, no DB calls
      → perform_create → create_organisation(**validated_data, created_by=request.user)
          @transaction.atomic:
          ├── Organisation.objects.create(...)
          └── send_org_admin_invitation(organisation=org)
                  ├── token = TimestampSigner.sign(org.email)
                  ├── InvitationToken.objects.create(token_hash=sha256(token), used_at=None)
                  └── send_transactional_email(to=[org.email], template="emails/invitation")
                          → EmailMultiAlternatives → django_ses backend → SES API
  → 201 response with OrganisationReadSerializer data
  → cache.delete_pattern("organisations:list:*")
```

### 3. Invitation activation flow

```
Browser GET /activate/<token>/
  → AccountActivationView (TemplateView)
      → TimestampSigner.unsign(token, max_age=172800)   # 48h; raises BadSignature if expired
      → InvitationToken.objects.get(token_hash=sha256(token), used_at__isnull=True)
      → Renders activation form (name + password fields)

Browser POST /activate/<token>/
  → activate_org_admin_account(token, name, password)  # service
      @transaction.atomic + select_for_update():
      ├── Re-verify token (idempotent guard)
      ├── User.objects.create(role=ORG_ADMIN, organisation=org, name=name, ...)
      ├── InvitationToken: mark used_at=now()
      └── login(request, user)
  → Redirect to stub Org Admin dashboard
```

### 4. RBAC enforcement

```
Incoming API request
  → SessionAuthentication verifies session cookie
  → Permission class:
      IsSuperadmin: request.user.is_authenticated AND request.user.role == Role.SUPERADMIN
      IsOrgAdmin:   request.user.is_authenticated AND request.user.role == Role.ORG_ADMIN
  → Tenant scoping (Org Admin + Staff Admin views only):
      TenantScopedViewSet.get_queryset() adds .filter(organisation_id=request.user.organisation_id)
  → View proceeds
```

### 5. Cache flow

```
GET /api/v1/organisations/?search=acme&status=active&page=2
  → key = f"organisations:list:{hash((search, status, page))}"
  → cache.get(key) — HIT → return cached response immediately
  → MISS → run selector → paginate → serialize → cache.set(key, result, 300)

POST/PATCH/DELETE on any organisation
  → service mutates DB
  → cache.delete_pattern("organisations:detail:<id>")
  → cache.delete_pattern("organisations:list:*")
```

---

## Key Code Patterns

### Pattern 1: Thin ViewSet with two serializers

```python
class OrganisationViewSet(GenericViewSet, CreateModelMixin, RetrieveModelMixin,
                          UpdateModelMixin, ListModelMixin):
    permission_classes = [IsAuthenticated & IsSuperadmin]
    pagination_class = StandardPageNumberPagination

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return OrganisationCreateSerializer
        return OrganisationReadSerializer

    def get_queryset(self):
        return list_organisations_for_superadmin(
            search=self.request.query_params.get("search", ""),
            status=self.request.query_params.get("status"),
            org_type=self.request.query_params.get("type"),
        )

    def perform_create(self, serializer):
        create_organisation(**serializer.validated_data, created_by=self.request.user)
```

### Pattern 2: Tenant scoping base class (for Phase 2+ non-superadmin views)

```python
# apps/common/views.py
class TenantScopedViewSet(GenericViewSet):
    """All Org Admin and Staff Admin viewsets inherit this. Superadmin viewsets do NOT."""
    def get_queryset(self):
        return super().get_queryset().filter(organisation_id=self.request.user.organisation_id)
```

### Pattern 3: Invitation token — sign + hash for storage

```python
import hashlib
from django.core import signing

SALT = "invitation-v1"

def _make_token(email: str) -> str:
    return signing.TimestampSigner(salt=SALT).sign(email)

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def send_org_admin_invitation(*, organisation: Organisation) -> str:
    token = _make_token(organisation.email)
    InvitationToken.objects.create(
        organisation=organisation,
        token_hash=_hash_token(token),
    )
    send_transactional_email(...)
    return token  # returned so tests can assert; never stored raw
```

### Pattern 4: React widget mounting — CSRF threaded from template

```html
<!-- templates/organisations/list.html -->
<div
  id="org-table-root"
  data-api-url="{% url 'api:organisations-list' %}"
  data-csrf-token="{{ csrf_token }}"
></div>
<script type="module" src="{% static 'js/org-table.bundle.js' %}"></script>
```

```typescript
// frontend/src/entrypoints/org-table.tsx
const root = document.getElementById("org-table-root")!;
ReactDOM.createRoot(root).render(
  <OrgTable apiUrl={root.dataset.apiUrl!} csrfToken={root.dataset.csrfToken!} />
);
```

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Instead |
|---|---|---|
| Business logic in serializers | Bypasses `@transaction.atomic`; side-effects skipped | Serializer validates only. `perform_create` calls a service |
| Direct ORM in views | Guarantees N+1; untestable | All ORM calls through selectors |
| Per-view tenant filter | One missed filter = cross-tenant data leak | `TenantScopedViewSet` base class |
| Raw invitation tokens in DB | DB compromise lets attacker activate any invitation | Store `token_hash = sha256(token)` |
| Shared state between React widgets | Widgets load independently; stale state; tight coupling | Each widget is fully self-contained |
| Hard-delete cascades on organisations | Irreversible; violates audit requirements | Soft-delete + scheduled purge |

---

## Build Order (Phase 1 Dependency Graph)

```
Step 1: Foundation layer
  ├── apps/common/ — TimeStampedModel, UUIDModel, exceptions, pagination
  └── config/settings/ — split into base/local/production/test

Step 2: User model  [CRITICAL: must precede first `manage.py migrate`]
  └── apps/accounts/ — custom User, Role enum, AUTH_USER_MODEL setting + migration 0001

Step 3: Organisation model
  └── apps/organisations/ — Organisation, managers, QuerySet + migration

Step 4: RBAC permission classes
  ├── apps/accounts/permissions.py — IsSuperadmin, IsOrgAdmin, IsStaffAdmin
  └── apps/common/views.py — TenantScopedViewSet base

Step 5: Authentication views
  └── apps/accounts/ — login, logout, password-reset templates + views

Step 6: Invitation system
  ├── apps/accounts/ — InvitationToken model + migration
  ├── apps/accounts/services/invitations.py
  ├── apps/common/services/email.py — send_transactional_email()
  └── templates/emails/invitation.html + invitation.txt

Step 7: Organisation API (depends on Steps 4, 5, 6)
  ├── apps/organisations/services/organisations.py
  ├── apps/organisations/selectors/organisations.py
  ├── apps/organisations/serializers.py (Read + Create + Update)
  ├── apps/organisations/views.py
  └── apps/organisations/urls.py

Step 8: Account activation flow (depends on Step 6)
  ├── apps/accounts/ — activation TemplateView + form
  └── apps/accounts/services/activation.py

Step 9: Frontend shell (depends on Step 7)
  ├── templates/base.html — sidebar layout, Tailwind, brand tokens
  ├── Django template views — thin wrappers + React mount points
  └── Vite config + React org-table widget

Step 10: Superadmin profile (depends on Step 5)
  └── apps/accounts/services/profile.py — update_name, change_password

Step 11: CI/CD + Observability
  ├── GitHub Actions CI (lint, typecheck, test, coverage gate)
  ├── Sentry SDK in production settings
  ├── RequestContextMiddleware (request_id, user_id, organisation_id)
  └── Docker build + /healthz/ + /readyz/ endpoints
```

**Critical path:** Steps 1→2→3 are strictly sequential. Step 2 (User model) must precede ANY migration. Steps 7 and 9 can be built in parallel after Step 6 completes.

---

## Key Architecture Decisions

| Decision | Rationale | Confidence |
|----------|-----------|------------|
| Services/selectors over fat models | Testable in isolation; `@transaction.atomic` is explicit; views stay thin | HIGH |
| Two serializers per resource | Input validation != output shaping | HIGH |
| `TimestampSigner` + SHA-256 hash | No extra dependencies; expiry enforced by Django core; raw token never in DB | HIGH |
| React widgets as islands, not SPA | Django session auth/CSRF works naturally | HIGH |
| Soft-delete for organisations | Audit trail; mistake recovery window | HIGH |
| `TenantScopedViewSet` base class | Single enforcement point; prevents data leaks | HIGH |
| `apps/common/` owns email service | Email is cross-cutting; accounts/stores/reviews all send email | MEDIUM |
