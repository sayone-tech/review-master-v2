# Phase 3: Organisation Management - Research

**Researched:** 2026-04-23
**Domain:** Django DRF + React hybrid — organisation CRUD, invitation token creation, email dispatch, server-side pagination with React table widget
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**React widget scope**
- Hybrid approach: Django template (`organisations/list.html`) extends `base.html` (sidebar + topbar), renders the existing `filter_bar.html` component for search/filter, and uses a server-side `pagination.html` component. A single React `OrgManagement` entrypoint mounts inside `<div id="org-table-root">` and owns the DataTable rows + all modal dialogs.
- Filter bar (search, status filter, type filter) uses the existing `filter_bar.html` GET form — submits trigger a page reload.
- Pagination uses the existing server-side `pagination.html` — extended with a rows-per-page selector (see below).
- React does NOT own search, filters, or pagination controls. It owns: table rows (with row-action menus), all modal dialogs.

**Initial data loading**
- Django view queries organisations and serialises the first page into a JSON blob embedded in the template: `<script id="org-data" type="application/json">{{ orgs_json|safe }}</script>`
- React reads that blob on mount — no initial fetch, instant first render.
- Subsequent mutations call DRF to refresh the table in-place.

**Filter state and page reloads**
- Applying a filter or search submits the GET form → Django re-renders the template with filtered data in the JSON blob → React re-mounts with the new data. No React state to sync with URL params for filters.
- React reads `window.location.search` on mount to know the current filter params (needed for post-mutation refresh calls).

**Rows-per-page selector**
- Server-side: `per_page` GET param added to `pagination.html` (extended with a `<select>` for 10/25/50/100, default 10).
- Django view reads `per_page` from GET params and passes it to `Paginator`. Per-page selection persists via URL param across page navigation.
- Default: 10 rows/page per ORGL-06.

**Confirmation modal patterns**
- All confirmations use React portals — no Alpine.js for any modal in this page.
- React OrgManagement widget owns all dialogs: create, view, edit, enable, disable, delete, and store allocation.
- Delete modal (DORG-01): Requires typing the exact organisation name before Delete button enables.
- Enable/disable modals (ENBL-01/02): Simple confirmation popups with amber/blue variants.
- Store allocation modal (STOR-01/02/03): Inline validation (amber warning when value < current usage, Update button blocked), then confirmation popup.

**Table refresh after mutations**
- After any successful mutation (create, edit, enable, disable, delete, store allocation change), React calls `GET /api/v1/organisations/` with the current URL search params.
- React updates its local state — no page reload.

**API layer**
- DRF ViewSet at `/api/v1/organisations/` (list, create, retrieve, update, partial_update, destroy).
- List endpoint must support query params: `search`, `status`, `type`, `page`, `per_page`.
- Write operations each have their own serializer shapes per CLAUDE.md §8.
- Strict no-N+1: list endpoint CI query-count ceiling test required (ORGL-08).

### Claude's Discretion
- Exact modal animation (fade/slide, duration)
- Row-action three-dot menu implementation (Alpine.js dropdown is the established pattern; React may use a Radix/headless dropdown or a simple positioned div)
- Loading spinner on action buttons while DRF call is in-flight
- Toast message copy for each action (beyond what REQUIREMENTS.md specifies exactly)
- DRF serializer field names and nesting depth

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 3 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ORGL-01 | Superadmin sees organisations list as default landing page at /admin/organisations | `LOGIN_REDIRECT_URL = "/admin/organisations/"` already set in base.py; replace placeholder view with real template view |
| ORGL-02 | List displays columns: Name, Type, Email, # Stores (used/allocated), Status, Created Date, Actions | `DataTable` widget supports generic columns; `annotate_store_counts()` stub exists in `OrganisationQuerySet`; serializer must expose these 7 fields |
| ORGL-03 | Search by name or email (real-time, debounced via filter_bar GET form) | `filter_bar.html` already handles GET params; Django view applies `Q(name__icontains=...) \| Q(email__icontains=...)` filter; Alpine.js debounce on search input |
| ORGL-04 | Filter by status (All / Active / Disabled) | `OrganisationQuerySet.not_deleted()` excludes Deleted; status filter in Django list view; filter_bar status_options context var |
| ORGL-05 | Filter by type (All / Retail / Restaurant / Pharmacy / Supermarket) | `OrgType` choices on model; filter_bar type_options context var |
| ORGL-06 | Pagination with rows-per-page selector (10/25/50/100, default 10) | Django `Paginator` with `per_page` GET param; `pagination.html` needs `per_page` select added |
| ORGL-07 | Skeleton loading state and empty state with CTA | `DataTable` built-in `loading=true` renders 6 skeleton rows; `empty_state.html` component exists |
| ORGL-08 | Fixed number of SQL queries regardless of result size (CI ceiling test) | `CaptureQueriesContext` pattern established (CLAUDE.md §6.9); `annotate_store_counts()` + `select_related("created_by")` in selector; ceiling ≤ 3 queries |
| CORG-01 | Open "Create Organisation" modal from list page header | React `Modal` component (size=default) triggered by "Create Organisation" button in OrgManagement widget |
| CORG-02 | Create form with validation: name 2-100, type required, address optional max 500, email unique+required, stores 1-1000 | DRF `OrganisationCreateSerializer` with field-level validators; unique email check raises 400 with inline error |
| CORG-03 | Success toast and list refresh on create | `emitToast` via `app:toast` CustomEvent; React re-fetches GET /api/v1/organisations/ |
| CORG-04 | Generate 48-hour invitation token and send activation email on create | `create_organisation` service: `@transaction.atomic` wraps org create + `InvitationToken` creation + email dispatch; `send_transactional_email` via `apps/common/...` path |
| VORG-01 | View Details modal via name click or row action | React `Modal` (size=default) opened with org data already in local state |
| VORG-02 | Details modal fields including Org Admin activation status and last invitation timestamp | Serializer must expose `activation_status` (computed from InvitationToken), `last_invited_at` |
| VORG-03 | "Resend Invitation" button only when Org Admin not yet activated | Conditional render in React based on `activation_status !== 'active'` |
| EORG-01 | Edit modal with all fields pre-filled | React `Modal` sharing same form layout as Create; populated from local row state |
| EORG-02 | Email field disabled in edit mode | Serializer: email excluded from `update()`; React renders field with `disabled` styling |
| EORG-03 | Success toast + list refresh on edit | Same pattern as CORG-03 |
| ENBL-01 | Disable with amber ConfirmModal | `ConfirmModal` variant="amber"; PATCH /api/v1/organisations/{id}/ with `{"status": "DISABLED"}` |
| ENBL-02 | Enable with blue ConfirmModal | `ConfirmModal` variant="blue"; PATCH /api/v1/organisations/{id}/ with `{"status": "ACTIVE"}` |
| DORG-01 | Delete with red ConfirmModal + type-to-confirm | `ConfirmModal` variant="red" with `requireTypeToConfirm={org.name}`; DELETE /api/v1/organisations/{id}/ |
| DORG-02 | Soft-delete on DELETE (status change, not row removal) | `Organisation.soft_delete()` method exists; DRF `destroy()` override calls `soft_delete()` instead of `.delete()` |
| STOR-01 | Adjust Store Count via row action menu — input shows current usage | Two-step: React `Modal` (size=sm) for input, then `ConfirmModal` (blue) for confirmation |
| STOR-02 | Amber inline warning when new value < current in-use count | React inline validation; Update button disabled; uses `form_fields.html` `warn` color pattern |
| STOR-03 | Confirmation popup with old/new count; success toast on confirm | PATCH /api/v1/organisations/{id}/ with `{"number_of_stores": new_value}` |
</phase_requirements>

---

## Summary

Phase 3 implements full Superadmin CRUD for the organisation roster. The architecture is a proven hybrid: Django renders the page shell and embeds the initial data JSON blob; a single React `OrgManagement` entrypoint owns all table rows and seven modal dialogs; Django template components (filter_bar, pagination, badges) handle the surrounding chrome. No new libraries are required — all components exist from Phases 1-2.

The backend work follows the established services/selectors pattern: a `create_organisation` service (atomic: org create + InvitationToken + email dispatch), an `update_organisation` service, a `list_organisations` selector, and a DRF `OrganisationViewSet` at `/api/v1/organisations/`. The `Organisation` model, `OrganisationQuerySet`, and `InvitationToken` model are already in place. `django-filter` is NOT currently installed — the list endpoint filters are simple enough to implement manually with `Q()` objects in the selector, which is the correct pattern per CLAUDE.md §8.

The single integration complexity is CORG-04: the `create_organisation` service must create an `InvitationToken`, build a signed token, and dispatch the invitation email, all within a `transaction.atomic` block. The `send_transactional_email` helper exists in `apps/common/` but needs to be created as it was referenced in CLAUDE.md §12.4 but not yet built. Email templates must be created. The Vite entrypoint `org-management.tsx` is new and must be wired into `vite.config.ts`.

**Primary recommendation:** Implement in four logical waves: (1) backend model/selector/service/viewset, (2) Django list template + Vite entrypoint registration, (3) React `OrgManagement` component, (4) invitation email service and template. The existing model, querysets, widgets, and component library make this straightforward — the risk areas are the transactional email service, the N+1 query ceiling test, and properly wiring `per_page` through the pagination component without breaking the existing URL structure.

---

## Standard Stack

### Core (all already installed — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.2 | Template view + Paginator | Locked in project |
| djangorestframework | 3.17.1 | OrganisationViewSet, serializers | Locked in project |
| drf-spectacular | 0.28.0 | OpenAPI schema generation | Already in INSTALLED_APPS |
| React | 19.2.5 | OrgManagement widget + all modals | Locked in project |
| lucide-react | 1.8.0 | Icons (MoreHorizontal, Eye, Pencil, etc.) | Established in DataTable.tsx |
| focus-trap-react | 12.0.0 | Modal focus management | Established in Modal.tsx |
| django-vite | 3.1.0 | Vite manifest integration | Already configured |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| factory-boy | 3.3.3 | OrganisationFactory (exists), InvitationTokenFactory (exists) | Tests only |
| pytest-django | 4.9.0 | All tests | Tests only |
| django-redis | 5.4.0 | Cache for list views, distributed locks | Already configured |

### Not Required

`django-filter` is NOT needed — the `OrganisationViewSet` list filtering is simple `Q()` logic handled directly in the `list_organisations` selector, consistent with the selectors pattern. Installing `django-filter` would add complexity without benefit for three known filter dimensions.

**Installation:** No new packages — all dependencies already present in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

New files to create:

```
apps/organisations/
├── services/
│   ├── __init__.py
│   └── organisations.py           # create_organisation, update_organisation, enable/disable/delete_organisation, adjust_store_allocation
├── selectors/
│   ├── __init__.py
│   └── organisations.py           # list_organisations, get_organisation_detail
├── serializers.py                 # OrganisationListSerializer, OrganisationCreateSerializer, OrganisationUpdateSerializer, OrganisationDetailSerializer
├── views.py                       # OrganisationListView (template) + OrganisationViewSet (DRF)
├── urls.py                        # Updated: template URL + DRF router
└── tests/
    ├── factories.py               # OrganisationFactory (exists)
    ├── test_models.py             # (exists)
    ├── test_services.py           # NEW: test create/update/enable/disable/delete/adjust_stores
    ├── test_selectors.py          # NEW: test list_organisations query count ceiling (ORGL-08)
    └── test_views.py              # NEW: test DRF viewset endpoints + Django template view

apps/common/services/
├── __init__.py
└── email.py                       # send_transactional_email (new — referenced in CLAUDE.md §12.4 but not yet built)

templates/organisations/
└── list.html                      # NEW: extends base.html; renders filter_bar + org-table-root + pagination

templates/emails/
├── invitation.html                # NEW: invitation email HTML template
└── invitation.txt                 # NEW: invitation email plain text

frontend/src/entrypoints/
└── org-management.tsx             # NEW: OrgManagement React widget

frontend/vite.config.ts            # ADD: "org-management" input entry
config/urls.py                     # ADD: DRF router registration for /api/v1/organisations/
```

### Pattern 1: Services/Selectors Split

The `create_organisation` service is the most complex — it must be atomic.

```python
# apps/organisations/services/organisations.py
from __future__ import annotations

import secrets

from django.db import transaction

from apps.accounts.models import InvitationToken
from apps.common.services.email import send_transactional_email
from apps.organisations.models import Organisation


@transaction.atomic
def create_organisation(
    *,
    name: str,
    org_type: str,
    email: str,
    address: str = "",
    number_of_stores: int,
    created_by: "User",
) -> tuple[Organisation, str]:
    """Create org, generate invitation token, dispatch email.

    Returns (org, raw_token) so caller can confirm email dispatch.
    """
    org = Organisation.objects.create(
        name=name,
        org_type=org_type,
        email=email,
        address=address,
        number_of_stores=number_of_stores,
        created_by=created_by,
    )
    raw_token = secrets.token_urlsafe(32)
    InvitationToken.objects.create(
        organisation=org,
        token_hash=InvitationToken.hash_token(raw_token),
    )
    send_transactional_email(
        to=[email],
        subject=f"You're invited to manage {name}",
        template_base="emails/invitation",
        context={"organisation": org, "accept_url": _build_accept_url(raw_token)},
    )
    return org, raw_token
```

The list selector:

```python
# apps/organisations/selectors/organisations.py
from __future__ import annotations

from django.db.models import Q

from apps.organisations.models import Organisation


def list_organisations(
    *,
    search: str = "",
    status: str = "",
    org_type: str = "",
) -> "QuerySet[Organisation]":
    qs = (
        Organisation.objects
        .not_deleted()
        .select_related("created_by")
        .annotate_store_counts()
    )
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))
    if status and status in Organisation.Status.values:
        qs = qs.filter(status=status)
    if org_type and org_type in Organisation.OrgType.values:
        qs = qs.filter(org_type=org_type)
    return qs.order_by("-created_at")
```

### Pattern 2: Django Template View with Embedded JSON Blob

```python
# apps/organisations/views.py
import json
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from apps.organisations.selectors.organisations import list_organisations
from apps.organisations.serializers import OrganisationListSerializer

_PER_PAGE_OPTIONS = [10, 25, 50, 100]

@login_required
def organisation_list(request: HttpRequest) -> HttpResponse:
    per_page = int(request.GET.get("per_page", 10))
    if per_page not in _PER_PAGE_OPTIONS:
        per_page = 10
    qs = list_organisations(
        search=request.GET.get("search", ""),
        status=request.GET.get("status", ""),
        org_type=request.GET.get("type", ""),
    )
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    orgs_json = json.dumps(OrganisationListSerializer(page_obj.object_list, many=True).data)
    return render(request, "organisations/list.html", {
        "page_obj": page_obj,
        "orgs_json": orgs_json,
        "per_page": per_page,
        "per_page_options": _PER_PAGE_OPTIONS,
        "status_options": [("", "All Statuses"), ("ACTIVE", "Active"), ("DISABLED", "Disabled")],
        "type_options": [("", "All Types")] + list(Organisation.OrgType.choices),
        "total_count": paginator.count,
    })
```

### Pattern 3: DRF ViewSet

```python
# apps/organisations/views.py (continued)
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsSuperadmin

class OrganisationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSuperadmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return OrganisationListSerializer
        elif self.action == "create":
            return OrganisationCreateSerializer
        elif self.action in ("update", "partial_update"):
            return OrganisationUpdateSerializer
        return OrganisationDetailSerializer

    def get_queryset(self):
        return list_organisations(
            search=self.request.query_params.get("search", ""),
            status=self.request.query_params.get("status", ""),
            org_type=self.request.query_params.get("type", ""),
        )

    def perform_create(self, serializer):
        create_organisation(**serializer.validated_data, created_by=self.request.user)

    def perform_destroy(self, instance):
        delete_organisation(organisation=instance)  # calls soft_delete()
```

### Pattern 4: Vite Entrypoint Registration

Add `"org-management"` to `vite.config.ts` `rollupOptions.input`:

```typescript
// frontend/vite.config.ts
rollupOptions: {
  input: {
    "app-shell": resolve(__dirname, "src/entrypoints/app-shell.ts"),
    "showcase": resolve(__dirname, "src/entrypoints/showcase.tsx"),
    "org-management": resolve(__dirname, "src/entrypoints/org-management.tsx"),
  },
},
```

Then in `organisations/list.html`:
```html
{% load django_vite %}
{% vite_asset 'org-management.tsx' %}
```

### Pattern 5: DRF Router URL Registration

```python
# config/urls.py — add DRF router
from rest_framework.routers import DefaultRouter
from apps.organisations.views import OrganisationViewSet

router = DefaultRouter()
router.register("api/v1/organisations", OrganisationViewSet, basename="organisation")

urlpatterns = [
    path("", include(router.urls)),
    path("", include("apps.organisations.urls")),
    ...
]
```

### Pattern 6: `send_transactional_email` Service

This service is specified in CLAUDE.md §12.4 but not yet built. Must be created in `apps/common/services/email.py`:

```python
# apps/common/services/email.py
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def send_transactional_email(
    *,
    to: list[str],
    subject: str,
    template_base: str,
    context: dict,
    reply_to: list[str] | None = None,
    tags: list[str] | None = None,
) -> None:
    text_body = render_to_string(f"{template_base}.txt", context)
    html_body = render_to_string(f"{template_base}.html", context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or [settings.DEFAULT_REPLY_TO],
    )
    msg.attach_alternative(html_body, "text/html")
    if tags and getattr(settings, "AWS_SES_CONFIGURATION_SET", None):
        msg.extra_headers["X-SES-MESSAGE-TAGS"] = ", ".join(f"category={t}" for t in tags)
        msg.extra_headers["X-SES-CONFIGURATION-SET"] = settings.AWS_SES_CONFIGURATION_SET
    msg.send(fail_silently=False)
```

### Anti-Patterns to Avoid

- **Calling `Organisation.objects.filter()` directly from views:** Use `list_organisations` selector instead.
- **Business logic in serializers:** Serializers validate and shape data only. `create_organisation` service does the work.
- **React tracking filter state:** Filter state lives in URL (`window.location.search`). React never duplicates it.
- **Fetching on mount before embedded JSON:** Read from `<script id="org-data">` blob first; no initial API call.
- **Page reload after mutations:** React calls `GET /api/v1/organisations/` with current params, updates state in-place.
- **Hard-deleting on `destroy()`:** Override `perform_destroy` to call `org.soft_delete()`, not `instance.delete()`.
- **Skipping `select_related("created_by")`:** Every list query must include this to avoid N+1 on `created_by` FK access.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Focus trapping in modals | Custom focus trap | `focus-trap-react` 12.0.0 (already installed) | Browser quirks with tab order, hidden elements, SVGs |
| Token signing/hashing | Custom crypto | `hashlib.sha256` + `secrets.token_urlsafe` (already used in InvitationToken) | Existing pattern; consistent with Phase 1 |
| Pagination | Custom page math | Django `Paginator` | Edge cases: empty page, out-of-range, per-page changes |
| Email sending | Direct `smtplib` | `EmailMultiAlternatives` → `django-ses` backend | SES headers, config set, fail_silently control |
| Query filtering | Raw SQL | `Q()` objects in selector | Django ORM handles escaping, index hints |

---

## Common Pitfalls

### Pitfall 1: N+1 on `activation_status` field in list serializer
**What goes wrong:** The list serializer computes `activation_status` by querying `InvitationToken` for each organisation row separately.
**Why it happens:** `SerializerMethodField` that calls `InvitationToken.objects.filter(organisation=obj)` for each row.
**How to avoid:** Use `prefetch_related("invitation_tokens")` in the `list_organisations` selector; the `activation_status` method field checks `obj.invitation_tokens.all()` which hits the prefetch cache.
**Warning signs:** Query count test fails; `nplusone` fires in dev.

### Pitfall 2: `per_page` param breaks existing pagination link `href="?page=N"` format
**What goes wrong:** The existing `pagination.html` generates `?page=N` links which drop all other GET params (search, status, type, per_page) on navigation.
**Why it happens:** Hardcoded `href="?page=..."` in `pagination.html` ignores existing query params.
**How to avoid:** Extend `pagination.html` to build page links by merging `request.GET.urlencode()` with updated `page=N`. Use a template tag or pass `base_url` context variable.
**Warning signs:** Navigating to page 2 loses filter/per_page state.

### Pitfall 3: Embedded JSON blob XSS via `|safe`
**What goes wrong:** `{{ orgs_json|safe }}` renders unescaped JSON directly into a script tag. If org names contain `</script>`, the page breaks.
**Why it happens:** `|safe` bypasses Django's escaping.
**How to avoid:** Use Django's `json_script` template tag instead of raw `|safe` in a script tag: `{{ orgs_json|json_script:"org-data" }}`. React reads via `JSON.parse(document.getElementById("org-data").textContent)`.
**Warning signs:** Org name with `</` in it breaks the page.

### Pitfall 4: `destroy()` deletes the row permanently
**What goes wrong:** DRF's default `destroy()` calls `instance.delete()` which hard-deletes.
**Why it happens:** ModelViewSet inherits `DestroyModelMixin.destroy()` which calls `.delete()`.
**How to avoid:** Override `perform_destroy` to call `delete_organisation(organisation=instance)` which calls `instance.soft_delete()`.
**Warning signs:** Organisation disappears from the database entirely instead of showing `status=DELETED`.

### Pitfall 5: `IsSuperadmin` permission class missing
**What goes wrong:** `apps/accounts/permissions.py` does not exist yet (file not found in Phase 2 code scan).
**Why it happens:** Permission classes were referenced in CLAUDE.md and CONTEXT.md but not yet created.
**How to avoid:** Create `apps/accounts/permissions.py` with `IsSuperadmin` as Wave 0 gap. All viewset actions must set `permission_classes = [IsAuthenticated, IsSuperadmin]`.
**Warning signs:** Importing `IsSuperadmin` raises `ImportError`.

### Pitfall 6: `send_transactional_email` not yet built
**What goes wrong:** CLAUDE.md §12.4 specifies `apps.common.services.email.send_transactional_email` but the file does not exist.
**Why it happens:** It was designed in CLAUDE.md but not implemented in earlier phases.
**How to avoid:** Create `apps/common/services/email.py` as Wave 0 gap before the `create_organisation` service references it.
**Warning signs:** `ImportError` when running tests that touch `create_organisation`.

### Pitfall 7: `OrganisationListSerializer` exposes `activation_status` without prefetch
**What goes wrong:** Computing `activation_status` requires checking the latest `InvitationToken` for the org. Without prefetch this is O(N) queries.
**Why it happens:** Serializer `SerializerMethodField` is a common pattern but requires explicit prefetch setup.
**How to avoid:** In `list_organisations` selector, add `prefetch_related("invitation_tokens")`. In the serializer method, use `obj.invitation_tokens.all()` (hits prefetch cache).

### Pitfall 8: React `window.location.search` includes `page=N` in refresh calls after mutation
**What goes wrong:** After create/edit/delete, React re-fetches with `?page=3` — if the current page disappears (e.g., deleted last item on page 3), the DRF response returns empty results.
**Why it happens:** React naively passes `window.location.search` including `page`.
**How to avoid:** Strip `page` param from the refresh call after mutations (go back to page 1). Only preserve `search`, `status`, `type`, `per_page`.

---

## Code Examples

### Query-Count Ceiling Test (ORGL-08)

```python
# apps/organisations/tests/test_selectors.py
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from apps.organisations.tests.factories import OrganisationFactory
from apps.organisations.selectors.organisations import list_organisations

pytestmark = pytest.mark.django_db

def test_list_organisations_fixed_query_count():
    OrganisationFactory.create_batch(20)
    with CaptureQueriesContext(connection) as ctx:
        result = list(list_organisations())
    assert len(result) == 20
    assert len(ctx.captured_queries) <= 3  # 1 org query + 1 prefetch invitation_tokens + 1 count
```

### DRF ViewSet Query-Count API Test

```python
# apps/organisations/tests/test_views.py
def test_organisation_list_fixed_query_count(superadmin_client, db):
    OrganisationFactory.create_batch(25)
    with CaptureQueriesContext(connection) as ctx:
        resp = superadmin_client.get("/api/v1/organisations/")
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5  # auth + org list + prefetch + count + session
```

### Soft-Delete in perform_destroy

```python
# apps/organisations/views.py
def perform_destroy(self, instance: Organisation) -> None:
    delete_organisation(organisation=instance)
```

```python
# apps/organisations/services/organisations.py
def delete_organisation(*, organisation: Organisation) -> None:
    organisation.soft_delete()
```

### JSON Blob Using json_script (XSS-safe)

```html
{# templates/organisations/list.html #}
{% load django_vite %}
{{ orgs_json|json_script:"org-data" }}
<div id="org-table-root"></div>
{% vite_asset 'org-management.tsx' %}
```

```typescript
// frontend/src/entrypoints/org-management.tsx
const el = document.getElementById("org-data");
const initialOrgs: OrgRow[] = el ? JSON.parse(el.textContent ?? "[]") : [];
```

### Pagination URL Preservation (filter state + per_page)

In the Django view, build a `page_url_params` context:

```python
# apps/organisations/views.py
def _page_url_params(request: HttpRequest, per_page: int) -> str:
    """Build GET param string for pagination links that preserves filters."""
    params = request.GET.copy()
    params["per_page"] = str(per_page)
    params.pop("page", None)  # removed; pagination.html adds page=N
    return params.urlencode()
```

Pass `page_url_params` to template; `pagination.html` links become `href="?{{ page_url_params }}&page=N"`.

### InvitationToken Prefetch for activation_status

```python
# apps/organisations/selectors/organisations.py
def list_organisations(*, search="", status="", org_type=""):
    from django.db.models import Prefetch
    from apps.accounts.models import InvitationToken

    qs = (
        Organisation.objects
        .not_deleted()
        .select_related("created_by")
        .annotate_store_counts()
        .prefetch_related(
            Prefetch(
                "invitation_tokens",
                queryset=InvitationToken.objects.order_by("-created_at"),
                to_attr="prefetched_tokens",
            )
        )
    )
    ...
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Render full page on every row action | Embedded JSON + React in-place refresh | No full page reload on mutations |
| Alpine.js modals | React portals with focus-trap | Consistent focus management, no double-init |
| `filter_bar.html` with JS debounce | GET form submit (server-side) | Filter state canonical in URL, no React state sync |

---

## Open Questions

1. **`IsSuperadmin` permission class location**
   - What we know: Referenced throughout CLAUDE.md and CONTEXT.md as `apps.accounts.permissions.IsSuperadmin`. File `apps/accounts/permissions.py` does not exist.
   - What's unclear: Whether it was created as part of Phase 2 work not yet committed, or genuinely missing.
   - Recommendation: Create it in Wave 0 of planning. Definition: `class IsSuperadmin(BasePermission): def has_permission(self, request, view): return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.SUPERADMIN)`

2. **`_build_accept_url` for invitation email**
   - What we know: The activation page is Phase 4 (`/invite/accept/<token>/`). The email needs a URL pointing to it.
   - What's unclear: The URL name and path are Phase 4 scope. Phase 3 must still include the URL in the email.
   - Recommendation: Hardcode `{request.get_host()}/invite/accept/{raw_token}/` as a relative path for now; Phase 4 will register the named URL.

3. **`annotate_store_counts` uses stubs (returns zeros)**
   - What we know: `OrganisationQuerySet.annotate_store_counts()` returns `total_stores=0, active_stores=0` in the Phase 1 stub. The `Store` model doesn't exist yet.
   - What's unclear: Whether to update the stub in Phase 3 or leave it (CONTEXT.md says Phase 3 uses the stubs).
   - Recommendation: Leave the stubs as-is per CONTEXT.md. The `# Stores` column in the list shows "0 used of {number_of_stores} allocated" which is correct for this phase.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.3 + pytest-django 4.9.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest apps/organisations/tests/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ORGL-01 | GET /admin/organisations/ returns 200, redirects anon to login | integration | `pytest apps/organisations/tests/test_views.py::test_org_list_authenticated -x` | ❌ Wave 0 |
| ORGL-02 | JSON blob contains all required columns (name, type, email, stores, status, created_at) | unit | `pytest apps/organisations/tests/test_selectors.py::test_list_serializer_fields -x` | ❌ Wave 0 |
| ORGL-03 | Search by name filters correctly; search by email filters correctly | unit | `pytest apps/organisations/tests/test_selectors.py::test_list_search -x` | ❌ Wave 0 |
| ORGL-04 | Status filter returns only ACTIVE or DISABLED rows | unit | `pytest apps/organisations/tests/test_selectors.py::test_list_status_filter -x` | ❌ Wave 0 |
| ORGL-05 | Type filter returns only matching org_type rows | unit | `pytest apps/organisations/tests/test_selectors.py::test_list_type_filter -x` | ❌ Wave 0 |
| ORGL-06 | per_page=10 default; per_page=25 respected; invalid per_page falls back to 10 | integration | `pytest apps/organisations/tests/test_views.py::test_per_page_param -x` | ❌ Wave 0 |
| ORGL-07 | Empty queryset renders empty state template fragment | integration | `pytest apps/organisations/tests/test_views.py::test_empty_state -x` | ❌ Wave 0 |
| ORGL-08 | list_organisations() produces ≤ 3 queries for N=20 rows | unit | `pytest apps/organisations/tests/test_selectors.py::test_list_query_count -x` | ❌ Wave 0 |
| CORG-01 | POST /api/v1/organisations/ creates org and returns 201 | integration | `pytest apps/organisations/tests/test_views.py::test_create_org -x` | ❌ Wave 0 |
| CORG-02 | Duplicate email returns 400 with error on email field | integration | `pytest apps/organisations/tests/test_views.py::test_create_org_duplicate_email -x` | ❌ Wave 0 |
| CORG-04 | create_organisation creates InvitationToken + dispatches email | unit | `pytest apps/organisations/tests/test_services.py::test_create_organisation_sends_invite -x` | ❌ Wave 0 |
| VORG-02 | OrganisationDetailSerializer exposes activation_status and last_invited_at | unit | `pytest apps/organisations/tests/test_selectors.py::test_detail_serializer_activation_status -x` | ❌ Wave 0 |
| EORG-02 | PATCH /api/v1/organisations/{id}/ with email in payload does not change email | integration | `pytest apps/organisations/tests/test_views.py::test_update_org_email_immutable -x` | ❌ Wave 0 |
| ENBL-01 | PATCH status=DISABLED disables org | integration | `pytest apps/organisations/tests/test_views.py::test_disable_org -x` | ❌ Wave 0 |
| ENBL-02 | PATCH status=ACTIVE enables org | integration | `pytest apps/organisations/tests/test_views.py::test_enable_org -x` | ❌ Wave 0 |
| DORG-01 | DELETE /api/v1/organisations/{id}/ soft-deletes (status=DELETED, row remains) | integration | `pytest apps/organisations/tests/test_views.py::test_delete_org_soft -x` | ❌ Wave 0 |
| STOR-01 | PATCH number_of_stores updates allocation | integration | `pytest apps/organisations/tests/test_views.py::test_adjust_store_allocation -x` | ❌ Wave 0 |
| STOR-02 | create_organisation service is atomic — DB rolls back if email fails | unit | `pytest apps/organisations/tests/test_services.py::test_create_org_atomic_rollback -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest apps/organisations/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/accounts/permissions.py` — `IsSuperadmin` permission class (missing, referenced everywhere)
- [ ] `apps/common/services/__init__.py` + `apps/common/services/email.py` — `send_transactional_email`
- [ ] `apps/organisations/services/__init__.py` + `apps/organisations/services/organisations.py`
- [ ] `apps/organisations/selectors/__init__.py` + `apps/organisations/selectors/organisations.py`
- [ ] `apps/organisations/serializers.py`
- [ ] `apps/organisations/tests/test_services.py` — covers CORG-04, STOR-02 (atomicity)
- [ ] `apps/organisations/tests/test_selectors.py` — covers ORGL-02-08, VORG-02
- [ ] `apps/organisations/tests/test_views.py` — covers CORG-01/02, EORG-02, ENBL-01/02, DORG-01, STOR-01, ORGL-01/06/07
- [ ] `templates/organisations/list.html` — new template
- [ ] `templates/emails/invitation.html` + `templates/emails/invitation.txt`
- [ ] `frontend/src/entrypoints/org-management.tsx` — new React entrypoint
- [ ] `frontend/vite.config.ts` — add `"org-management"` input

---

## Sources

### Primary (HIGH confidence)

- Direct code inspection: `apps/organisations/models.py`, `apps/organisations/managers.py`, `apps/accounts/models.py` — confirmed existing model structure, QuerySet methods, InvitationToken fields
- Direct code inspection: `frontend/src/widgets/data-table/DataTable.tsx`, `frontend/src/widgets/modal/ConfirmModal.tsx` — confirmed widget APIs, props, variants
- Direct code inspection: `frontend/src/lib/toast.ts` — confirmed `emitToast` API
- Direct code inspection: `frontend/package.json` — confirmed installed React/Lucide/focus-trap versions
- Direct code inspection: `frontend/vite.config.ts` — confirmed entrypoint registration pattern
- Direct code inspection: `config/settings/base.py` — confirmed REST_FRAMEWORK config, no `django-filter` installed
- Direct code inspection: `pyproject.toml` — confirmed all dependency versions
- Direct code inspection: `templates/components/filter_bar.html`, `pagination.html`, `badges.html` — confirmed template API
- CLAUDE.md §5, §6, §8, §12 — services/selectors pattern, N+1 policy, DRF conventions, email service spec

### Secondary (MEDIUM confidence)

- `.planning/phases/03-organisation-management/03-CONTEXT.md` — locked architectural decisions
- `.planning/phases/03-organisation-management/03-UI-SPEC.md` — component usage, modal specifications, copywriting contract
- `.planning/REQUIREMENTS.md` — exact requirement text for all ORGL/CORG/VORG/EORG/ENBL/DORG/STOR IDs

### Tertiary (LOW confidence)

- None — all findings verified against source code.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies verified against `pyproject.toml` and `package.json`
- Architecture: HIGH — verified against existing code patterns in Phase 1/2 files
- Pitfalls: HIGH — identified from direct code inspection (missing permissions.py, missing common/services/email.py, existing pagination.html URL format, annotate_store_counts stub)
- Test patterns: HIGH — established pattern from `apps/accounts/tests/test_views.py` and CLAUDE.md §6.9

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (stable project; no fast-moving dependencies)
