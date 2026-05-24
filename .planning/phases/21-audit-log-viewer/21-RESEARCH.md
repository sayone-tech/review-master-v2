# Phase 21: Audit Log Viewer - Research

**Researched:** 2026-05-23
**Domain:** Django REST Framework read-only API + CursorPagination + django-filter + React frontend widget
**Confidence:** HIGH

## Summary

Phase 21 adds a read-only Activity Log page to the Org Admin UI. The `AuditLog` model already exists in `apps/common/models.py` with all required fields and the composite index that covers the primary query shape. Phase 18 (`merge_action_items`) already writes `action_item.merged` entries, so no data pipeline work is needed. The primary work is: one new selector module, one new FilterSet, one new ViewSet in the already-existing `apps/common/views.py`, URL registration, a Django template, and a new React widget.

**Critical finding — `IsStaffAdmin` does not exist.** The CONTEXT.md D-06 calls for `IsAuthenticated & (IsOrgAdmin | IsStaffAdmin)`, but `apps/accounts/permissions.py` only defines `IsOrgAdmin`, `IsSuperadmin`, and decorator helpers. The correct existing permission for "Org Admin OR Staff Admin" is `IsOrgScoped` from `apps/common/permissions.py`. The planner MUST use `IsOrgScoped` instead of composing non-existent `IsStaffAdmin`.

**Critical finding — CursorPagination is not used anywhere in this codebase.** This is a first-time introduction. The planner must include a new `AuditLogCursorPagination` class definition in `apps/common/pagination.py` alongside the existing `DefaultPageNumberPagination`.

**Critical finding — `action_item.merged` AuditLog `after_data` does NOT include a `count` field.** CONTEXT.md D-23 says `after_data={"merged_ids": [...], "count": N}`, but the live Phase 18 code at line 419 of `apps/action_items/services/lifecycle.py` writes `after_data={"merged_ids": list(duplicate_ids)}` only — no `count` key. The frontend must not assume `count` is present; the planner should note this discrepancy.

**Primary recommendation:** Use `IsOrgScoped` permission class (already covers both ORG_ADMIN and STAFF_ADMIN), build `AuditLogCursorPagination` in `apps/common/pagination.py`, register the ViewSet on the existing SimpleRouter in `config/urls.py`, and wire the frontend entrypoint following the action-items entrypoint pattern exactly.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Viewer shows only `entity_type="review"` with `action IN ("reply_posted", "reply_deleted", "reply_failed")` and `entity_type="action_item"` with `action LIKE "action_item.%"`.
- **D-02:** Filter in selector: `Q(entity_type="action_item") | Q(entity_type="review", action__in=["reply_posted", "reply_deleted", "reply_failed"])`.
- **D-03:** Staff Admin scope — two-step: fetch accessible entity IDs, apply `.filter(entity_id__in=entity_ids)`.
- **D-04:** `AuditLogViewSet(GenericViewSet, ListModelMixin)` in `apps/common/views.py` (existing file — must append, not replace).
- **D-05:** URL `GET /api/v1/audit-logs/` registered on `v1_router` in `config/urls.py`.
- **D-06:** Permission `IsAuthenticated & (IsOrgAdmin | IsStaffAdmin)` — **see critical finding: use `IsOrgScoped` instead**.
- **D-07:** django-filter FilterSet with `entity_type`, `actor`, `date_from`, `date_to`, `shop` params.
- **D-08:** `CursorPagination` `page_size=50` ordered by `-created_at`.
- **D-09:** `throttle_scope = "audit_log_list"` with `"audit_log_list": "120/minute"` added to `DEFAULT_THROTTLE_RATES`.
- **D-10:** `AuditLogReadSerializer` fields: `id`, `created_at`, `entity_type`, `entity_id`, `action`, `actor_id`, `actor_name`, `after_data`. No `before_data`.
- **D-11:** No `before_data` in response.
- **D-12:** "Activity Log" nav item in sidebar, appended at bottom of `<ul>` in `templates/partials/sidebar_org.html`.
- **D-13:** `templates/org-admin/audit-log.html` extending `base_org.html`, React widget at `#audit-log-root`.
- **D-14:** `frontend/src/entrypoints/audit-log.tsx` → `frontend/src/widgets/audit-log/`.
- **D-15–D-19:** Table columns, filter bar, empty state, error state, no export.
- **D-20:** Action label map in frontend `types.ts`.
- **D-21:** Existing composite index `audit_org_entity_date_idx` — no migration needed.
- **D-22:** `select_related("actor")` on queryset.
- **D-23:** Phase 18 must write `action_item.merged` — **already done, see critical finding about `count` field**.
- **D-24:** Phase 19 does NOT write AuditLog.
- **D-25:** Phase 20 does NOT write AuditLog.

### Claude's Discretion
None explicitly stated — all implementation decisions locked.

### Deferred Ideas (OUT OF SCOPE)
- CSV/Excel export
- Diff viewer (before_data / after_data comparison)
- Notification on sensitive events
- Superadmin cross-org audit viewer
- Retention policy
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-01 | API endpoint `GET /api/v1/audit-logs/` scoped to org with cursor pagination | D-04, D-05, D-08 — ViewSet + router registration + CursorPagination class |
| REQ-02 | Staff Admin sees only entries from accessible shops/SHOP-scope items | D-03 — two-step entity_ids pattern from `get_accessible_shop_ids` |
| REQ-03 | django-filter FilterSet with entity_type, actor, date_from, date_to, shop | D-07 — pattern from `ActionItemFilterSet` |
| REQ-04 | AuditLogReadSerializer without before_data | D-10, D-11 — field list confirmed against model |
| REQ-05 | Throttle at 120/minute, scoped to audit_log_list | D-09 — settings update + throttle_scope |
| REQ-06 | Activity Log nav item in sidebar_org.html | D-12 — `_nav_item.html` partial pattern |
| REQ-07 | Django template + React widget with DataTable, filters, cursor pagination | D-13–D-19, UI-SPEC |
| REQ-08 | Vite entrypoint registered in vite.config.ts | D-14 — existing pattern |
| REQ-09 | No new migration required | D-21 — confirmed by model inspection |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Org scoping + Staff scoping | API / Backend | — | Enforced at selector layer; never delegated to frontend |
| Cursor pagination | API / Backend | — | DRF CursorPagination returns next/previous cursor URLs |
| Filter validation | API / Backend | — | django-filter validates query params server-side |
| Action label display | Browser / Client | — | D-20 explicitly assigns label mapping to frontend |
| Filter state / URL sync | Browser / Client | — | Draft-then-apply with `window.history.pushState` |
| Actor dropdown data | Frontend Server (SSR) | Browser / Client | Server renders JSON via `json_script`; React reads it |
| Sidebar nav | Frontend Server (SSR) | — | Django template include, `is_active_route` tag |

---

## Standard Stack

### Core — All Verified in Codebase

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `djangorestframework` | installed | ViewSet, serializer, DRF CursorPagination | Already used project-wide |
| `django-filter` | installed | `AuditLogFilterSet` | Already used in `ReviewFilterSet`, `ActionItemFilterSet` |
| `django_filters.rest_framework.DjangoFilterBackend` | installed | Wire filter to ViewSet | Same import as `ActionItemViewSet` |
| `rest_framework.pagination.CursorPagination` | part of DRF | First cursor-paginated endpoint in this codebase | Required by D-08 |
| `rest_framework.mixins.ListModelMixin` | part of DRF | Read-only list endpoint | D-04 |
| `rest_framework.viewsets.GenericViewSet` | part of DRF | Base for ViewSet composition | D-04 |

[VERIFIED: project codebase — all imports confirmed in existing app code]

### Frontend — All Verified in Codebase

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `lucide-react` | installed | Icons — `Clock`, `ChevronRight`, `ChevronDown`, `AlertCircle`, `RefreshCw`, `ClipboardList`, `Search`, `Tag`, `Calendar`, `Users` | Already used across all widgets |
| `DataTable<T>` | local | Table rendering with `renderExpanded` | `frontend/src/widgets/data-table/DataTable.tsx` — existing component |
| Tailwind CSS | configured | All styling | Project standard — no shadcn/Radix |

[VERIFIED: project codebase]

### No New Packages Required

This phase installs zero new npm or Python packages. All dependencies are already present.

---

## Package Legitimacy Audit

> No external packages are installed in this phase. The audit is trivially clean.

| Package | Registry | Disposition |
|---------|----------|-------------|
| — | — | No new packages |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (GET /admin/org/activity-log/)
  → Django template view (audit_log_view)
    → Renders audit-log.html
      → json_script: audit-log-actors-data (distinct actors query)
      → json_script: audit-log-user-role
    → React widget mounts at #audit-log-root

Browser (GET /api/v1/audit-logs/?entity_type=&date_from=&date_to=&actor=)
  → AuditLogViewSet.list()
    → IsOrgScoped.has_permission() — role guard
    → AuditLogFilterSet — validates params
    → list_audit_logs_for_org() OR list_audit_logs_for_staff()
        → AuditLog.objects.filter(organisation=org)
            → Q(entity_type="action_item") | Q(entity_type="review", action__in=[...])
            → .filter(entity_id__in=accessible_ids)  [Staff only]
            → .select_related("actor")
    → AuditLogCursorPagination (page_size=50, ordering="-created_at")
    → AuditLogReadSerializer(many=True)
    → Response: {next, previous, results: [...]}
```

### Recommended Project Structure

```
apps/common/
├── selectors/               # NEW directory
│   ├── __init__.py          # NEW
│   └── audit_logs.py        # NEW — list_audit_logs_for_org(), list_audit_logs_for_staff()
├── filters.py               # NEW — AuditLogFilterSet
├── serializers.py           # NEW — AuditLogReadSerializer
├── views.py                 # MODIFY — append AuditLogViewSet + audit_log_view
├── pagination.py            # MODIFY — append AuditLogCursorPagination
└── tests/
    ├── test_audit_log_selectors.py   # NEW
    ├── test_audit_log_api.py         # NEW
    └── factories.py                  # Note: AuditLogFactory already in apps/reviews/tests/factories.py

templates/
└── org-admin/               # NEW directory
    └── audit-log.html       # NEW

templates/partials/
└── sidebar_org.html         # MODIFY — append Activity Log nav item

config/
├── urls.py                  # MODIFY — router.register + path for template view
└── settings/
    └── base.py              # MODIFY — add "audit_log_list": "120/minute"

frontend/
├── vite.config.ts           # MODIFY — add "audit-log" entrypoint
└── src/
    ├── entrypoints/
    │   └── audit-log.tsx    # NEW
    └── widgets/
        └── audit-log/       # NEW directory
            ├── AuditLogWidget.tsx
            ├── AuditLogFilters.tsx
            ├── AuditLogTable.tsx
            ├── TypePill.tsx
            ├── types.ts
            ├── utils.ts     # formatRelativeDate (copy from ReviewTable — no cross-widget import)
            ├── api.ts
            └── useAuditLog.ts
```

### Pattern 1: Selector with Staff Scoping (Two-Step)

The Staff scoping pattern is established in `apps/action_items/selectors/items.py`. For audit logs, D-03 uses a different approach: fetch entity IDs then filter. This is because audit log entries point to reviews (shop-scoped) and action items (SHOP-scope only) separately.

```python
# apps/common/selectors/audit_logs.py
from __future__ import annotations
from django.db.models import Q, QuerySet
from apps.common.models import AuditLog

AUDIT_ENTITY_FILTER = Q(entity_type="action_item") | Q(
    entity_type="review",
    action__in=["reply_posted", "reply_deleted", "reply_failed"],
)

def list_audit_logs_for_org(*, organisation_id: int) -> QuerySet[AuditLog]:
    return (
        AuditLog.objects.filter(organisation_id=organisation_id)
        .filter(AUDIT_ENTITY_FILTER)
        .select_related("actor")
    )

def list_audit_logs_for_staff(*, organisation_id: int, user) -> QuerySet[AuditLog]:
    from apps.reviews.selectors.reviews import get_accessible_shop_ids
    from apps.reviews.models import Review
    from apps.action_items.models import ActionItem

    accessible_shop_ids = get_accessible_shop_ids(user_id=user.pk)

    review_ids = list(
        Review.objects.filter(
            organisation_id=organisation_id,
            shop_id__in=accessible_shop_ids,
            deleted_at__isnull=True,
        ).values_list("id", flat=True)
    )
    action_item_ids = list(
        ActionItem.objects.filter(
            organisation_id=organisation_id,
            scope=ActionItem.Scope.SHOP,
            shop_id__in=accessible_shop_ids,
        ).values_list("id", flat=True)
    )

    accessible_entity_ids = [str(pk) for pk in review_ids + action_item_ids]

    return (
        AuditLog.objects.filter(organisation_id=organisation_id)
        .filter(AUDIT_ENTITY_FILTER)
        .filter(entity_id__in=accessible_entity_ids)
        .select_related("actor")
    )
```

[VERIFIED: project codebase — pattern mirrors `list_action_items` + `get_accessible_shop_ids`]

### Pattern 2: CursorPagination Setup — First Use in Codebase

```python
# apps/common/pagination.py — append alongside DefaultPageNumberPagination
from rest_framework.pagination import CursorPagination

class AuditLogCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"
```

**Important:** DRF CursorPagination requires the `ordering` field to be indexed. The existing `audit_org_entity_date_idx` index covers `(organisation, entity_type, created_at)`. Since the queryset always filters by `organisation_id`, the cursor on `created_at` within that filtered set uses this index. [VERIFIED: project codebase — model index confirmed]

### Pattern 3: ViewSet Appended to apps/common/views.py

`apps/common/views.py` already exists and contains `ScalarDocsView`, `healthz`, `readyz`, `home`, and `showcase`. The `AuditLogViewSet` MUST be appended, not placed in a new file. D-04 specifies `apps/common/views.py` explicitly.

```python
# Append to apps/common/views.py
from rest_framework import mixins, viewsets
from rest_framework.throttling import ScopedRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from apps.common.filters import AuditLogFilterSet
from apps.common.pagination import AuditLogCursorPagination
from apps.common.permissions import IsOrgScoped
from apps.common.selectors.audit_logs import list_audit_logs_for_org, list_audit_logs_for_staff
from apps.common.serializers import AuditLogReadSerializer
from apps.common.models import AuditLog
from apps.accounts.models import User

class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    serializer_class = AuditLogReadSerializer
    pagination_class = AuditLogCursorPagination
    filter_backends = [DjangoFilterBackend]  # noqa: RUF012
    filterset_class = AuditLogFilterSet
    throttle_scope = "audit_log_list"
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    queryset = AuditLog.objects.none()

    def get_queryset(self):
        user = self.request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return AuditLog.objects.none()
        if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
            return list_audit_logs_for_staff(organisation_id=org_id, user=user)
        return list_audit_logs_for_org(organisation_id=org_id)
```

[VERIFIED: project codebase — imports confirmed from existing view files]

### Pattern 4: FilterSet for AuditLog

```python
# apps/common/filters.py — new file
import django_filters
from apps.common.models import AuditLog

class AuditLogFilterSet(django_filters.FilterSet):
    entity_type = django_filters.CharFilter(field_name="entity_type")
    actor = django_filters.CharFilter(method="filter_actor")
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    shop = django_filters.NumberFilter(method="filter_shop")

    class Meta:
        model = AuditLog
        fields = []

    def filter_actor(self, qs, name, value):
        if value == "system":
            return qs.filter(actor__isnull=True)
        try:
            return qs.filter(actor_id=int(value))
        except (TypeError, ValueError):
            return qs

    def filter_shop(self, qs, name, value):
        # Applies only to review entries — review entity_ids are the Review PKs
        # whose shop matches. Two-step: get matching review IDs, filter by entity_id.
        from apps.reviews.models import Review
        review_ids = list(
            Review.objects.filter(
                shop_id=value, deleted_at__isnull=True
            ).values_list("id", flat=True)
        )
        return qs.filter(entity_type="review", entity_id__in=[str(pk) for pk in review_ids])
```

[VERIFIED: project codebase — pattern mirrors `ActionItemFilterSet` and `ReviewFilterSet`]

### Pattern 5: Serializer

```python
# apps/common/serializers.py — new file
from rest_framework import serializers
from apps.common.models import AuditLog

class AuditLogReadSerializer(serializers.ModelSerializer):
    actor_id = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "entity_type", "entity_id", "action",
                  "actor_id", "actor_name", "after_data"]

    def get_actor_id(self, obj):
        return obj.actor_id

    def get_actor_name(self, obj):
        actor = obj.actor
        if actor is None:
            return None
        full_name = getattr(actor, "full_name", "") or ""
        return str(full_name) if full_name else None
```

[VERIFIED: project codebase — `full_name` field confirmed on `apps/accounts/models.User` line 26; pattern mirrors `ActionItemNoteSerializer`]

### Pattern 6: URL Registration

```python
# config/urls.py — add alongside existing router.register calls
from apps.common.views import AuditLogViewSet  # add to existing imports

router.register(r"api/v1/audit-logs", AuditLogViewSet, basename="audit-log")
```

Template view URL goes in `apps/common/urls.py`:
```python
# apps/common/urls.py — append
from apps.common.views import audit_log_view
path("admin/org/activity-log/", audit_log_view, name="audit_log_list"),
```

[VERIFIED: project codebase — existing pattern from `apps/action_items/urls.py` and `apps/reviews/urls.py`]

### Pattern 7: Django Template

```html
{# templates/org-admin/audit-log.html #}
{% extends "base_org.html" %}
{% load static django_vite %}

{% block content %}
  <div id="audit-log-root"
       data-user-role="{{ user_role }}"></div>
  {{ actors_json|json_script:"audit-log-actors-data" }}
{% endblock %}

{% block extra_js %}
  {% vite_asset 'src/entrypoints/audit-log.tsx' %}
{% endblock %}
```

**Note:** `templates/org-admin/` directory does NOT yet exist and must be created. [VERIFIED: project codebase — `ls /templates/` confirmed no `org-admin/` subdirectory]

### Pattern 8: Sidebar Nav Item

Appended to `templates/partials/sidebar_org.html` inside the `<ul role="list">`, after the closing `{% endif %}` of the Org-Admin-only block:

```html
{% include "partials/_nav_item.html" with href="/admin/org/activity-log/" icon="clock" label="Activity Log" %}
```

No role guard — both ORG_ADMIN and STAFF_ADMIN can access (API filters their data). [VERIFIED: project codebase — `_nav_item.html` confirmed, `is_active_route` tag handles active state automatically]

### Pattern 9: Vite Config Addition

```typescript
// frontend/vite.config.ts — add to rollupOptions.input
"audit-log": resolve(__dirname, "src/entrypoints/audit-log.tsx"),
```

[VERIFIED: project codebase — existing pattern]

### Pattern 10: Entrypoint

```tsx
// frontend/src/entrypoints/audit-log.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuditLogWidget } from "../widgets/audit-log/AuditLogWidget";

function mount() {
  const root = document.getElementById("audit-log-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  const userRole = root.dataset.userRole ?? "STAFF_ADMIN";
  const actors = JSON.parse(
    document.getElementById("audit-log-actors-data")?.textContent ?? "[]"
  );
  createRoot(root).render(
    <StrictMode>
      <AuditLogWidget userRole={userRole} actors={actors} />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
```

[VERIFIED: project codebase — matches action-items-management.tsx pattern exactly]

### Anti-Patterns to Avoid

- **Using `DefaultPageNumberPagination` for audit logs:** The log can grow unboundedly; offset pagination degrades. CursorPagination is mandatory (D-08).
- **Creating a new `apps/common/views.py`:** The file already exists. Append the `AuditLogViewSet` and `audit_log_view` template view.
- **Importing `formatRelativeDate` from `ReviewTable`:** The UI-SPEC explicitly requires copying this function into `audit-log/utils.ts` — no cross-widget imports.
- **Composing `IsOrgAdmin | IsStaffAdmin`:** `IsStaffAdmin` does not exist. Use `IsOrgScoped` from `apps/common/permissions.py`.
- **Adding a `count` field to `action_item.merged` AuditLog entries:** Phase 18 already wrote this data without `count`; existing rows cannot be patched retroactively. The frontend must read `after_data.merged_ids.length` instead.
- **Creating `apps/common/selectors/` without `__init__.py`:** Django requires the `__init__.py` for the directory to be importable.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cursor-based pagination | Custom `next`/`previous` token encoding | `rest_framework.pagination.CursorPagination` | Handles ordering, encoding, edge cases |
| Query param filtering | Manual `request.GET.get()` in view | `django_filters.FilterSet` + `DjangoFilterBackend` | Validated, consistent with all other endpoints |
| Org scoping | Manual `filter(organisation_id=...)` in view | `IsOrgScoped` permission + selector pattern | Belt-and-braces: permission + selector both scope |
| Staff shop access list | Custom shop-access query | `get_accessible_shop_ids(user_id=...)` from `apps/reviews/selectors/reviews.py` | Already handles SHOP + REGION scope types |
| Table rendering | Custom `<table>` in React | `DataTable<AuditLogRow>` from `../data-table/DataTable` | Existing component with skeleton, empty, expand support |

---

## Runtime State Inventory

> Not applicable. This is a greenfield read-only viewer phase. No renames, refactors, or migrations.

---

## Common Pitfalls

### Pitfall 1: `IsStaffAdmin` Does Not Exist
**What goes wrong:** Planner or executor writes `IsOrgAdmin | IsStaffAdmin` and the Django check fails at startup with `ImportError` or `NameError`.
**Why it happens:** CONTEXT.md D-06 refers to `IsStaffAdmin` but this class was never implemented — `IsOrgScoped` (in `apps/common/permissions.py`) already handles both ORG_ADMIN and STAFF_ADMIN.
**How to avoid:** Use `permission_classes = [IsOrgScoped]` — identical to `ReviewViewSet` and `ActionItemViewSet`.
**Warning signs:** `ImportError: cannot import name 'IsStaffAdmin'` on startup.

### Pitfall 2: `templates/org-admin/` Directory Missing
**What goes wrong:** `TemplateDoesNotExist` error at runtime when navigating to `/admin/org/activity-log/`.
**Why it happens:** The directory does not exist yet — every existing org-admin template lives directly in a named app folder (`templates/reviews/`, `templates/action_items/`, etc.) or at the top level. D-13 specifies a new `templates/org-admin/` path.
**How to avoid:** `mkdir -p templates/org-admin/` before writing `audit-log.html`.
**Warning signs:** 500 error with `TemplateDoesNotExist: org-admin/audit-log.html`.

### Pitfall 3: CursorPagination Requires Stable Ordering Field
**What goes wrong:** DRF raises `InvalidCursor` errors or returns inconsistent pages if the `ordering` field has ties (i.e., many rows with the same `created_at` timestamp).
**Why it happens:** CursorPagination encodes the last-seen value of the ordering field; ties make the cursor ambiguous.
**How to avoid:** Add `id` as a tiebreaker: `ordering = ("-created_at", "id")`. The `id` field is auto-increment and unique, guaranteeing cursor stability. Update `AuditLogCursorPagination.ordering` accordingly.
**Warning signs:** Duplicate rows appearing across pages, or `InvalidCursor` exceptions.

### Pitfall 4: Staff Scope Two-Step Creates Large `IN` Clause
**What goes wrong:** An org with many reviews or action items produces a very large `entity_id__in=[...]` list, degrading query performance.
**Why it happens:** The two-step approach materialises all entity IDs in Python before filtering.
**How to avoid:** The selector returns IDs capped by shop scope — Staff users are typically restricted to a small number of shops. For Phase 21 this is acceptable. Monitor with `CaptureQueriesContext` tests. If it becomes a problem in a future phase, use a subquery with `OuterRef`.
**Warning signs:** Slow response times for Staff users with broad shop access.

### Pitfall 5: `after_data.count` Does Not Exist on Merged Entries
**What goes wrong:** Frontend code that reads `row.after_data.count` gets `undefined` for all `action_item.merged` entries because Phase 18 wrote `{"merged_ids": [...]}` without `count`.
**Why it happens:** CONTEXT.md D-23 specified `count` but the live Phase 18 implementation omitted it.
**How to avoid:** In the frontend's expanded JSON panel, render `JSON.stringify(row.after_data, null, 2)` directly. Do not extract specific keys. The `count` can be derived as `row.after_data?.merged_ids?.length` if needed.
**Warning signs:** `undefined` displayed for count in the detail panel.

### Pitfall 6: `apps/common/selectors/` Import Fails
**What goes wrong:** `ModuleNotFoundError: No module named 'apps.common.selectors'`.
**Why it happens:** `apps/common/selectors/` does not exist — the directory AND `__init__.py` must both be created.
**How to avoid:** Create both `apps/common/selectors/__init__.py` and `apps/common/selectors/audit_logs.py`.
**Warning signs:** Import error at startup or in tests.

### Pitfall 7: Actors JSON in Template View — N+1 Risk
**What goes wrong:** The actors dropdown requires a list of distinct users who have written audit log entries for the org. A naïve `.values("actor_id", "actor__full_name")` will hit the User table once per distinct actor.
**Why it happens:** Without explicit annotation, Django ORM may not batch the lookups.
**How to avoid:** Use `.select_related("actor")` and then `.values("actor_id", "actor__full_name")` on the filtered queryset — this generates a JOIN, not N lookups. Alternatively, fetch distinct `actor_id` values, then batch-load users in one query.
**Warning signs:** High query count in `django-debug-toolbar` on the template view.

---

## Code Examples

### Verified AuditLog Model Fields
```python
# apps/common/models.py — confirmed fields
class AuditLog(TimeStampedModel):
    organisation = ForeignKey("organisations.Organisation", ...)  # ✓
    actor = ForeignKey(settings.AUTH_USER_MODEL, null=True, ...)  # ✓ actor FK exists
    entity_type = CharField(max_length=50)                         # ✓
    entity_id = CharField(max_length=200)                          # ✓
    action = CharField(max_length=100)                             # ✓
    before_data = JSONField(null=True)                             # ✓ (not in serializer)
    after_data = JSONField(null=True)                              # ✓
    # Inherited from TimeStampedModel:
    created_at = DateTimeField(auto_now_add=True)                  # ✓
    updated_at = DateTimeField(auto_now=True)                      # not exposed
```

[VERIFIED: project codebase — `apps/common/models.py` read directly]

### Existing Composite Index
```python
# Confirmed in apps/common/models.py AuditLog.Meta
models.Index(
    fields=["organisation", "entity_type", "created_at"],
    name="audit_org_entity_date_idx",
)
```
[VERIFIED: project codebase]

### Phase 18 actual `action_item.merged` AuditLog write
```python
# apps/action_items/services/lifecycle.py lines 412–420
AuditLog.objects.create(
    organisation_id=primary.organisation_id,
    actor=actor if getattr(actor, "is_authenticated", False) else None,
    entity_type="action_item",
    entity_id=str(primary.pk),
    action="action_item.merged",
    before_data={},
    after_data={"merged_ids": list(duplicate_ids)},  # NO "count" key
)
```
[VERIFIED: project codebase — D-23 discrepancy confirmed]

### `retry_failed_enrichments_task` — D-25 compliance
```python
# apps/reviews/tasks.py lines 233–239
ids = list(
    Review.objects.filter(
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version__lt=MAX_TOTAL_ENRICH_ATTEMPTS,
        deleted_at__isnull=True,
    ).values_list("id", flat=True)[:500]
)
```
D-25 states Phase 20 moderation does NOT write AuditLog — confirmed. The retry task does not exclude `content_moderated` entries explicitly because `enrichment_error_code` is the mechanism (Phase 20 sets this on content-moderated failures). The retry task does NOT need changes for Phase 21.
[VERIFIED: project codebase]

### AuditLogFactory (already exists, import from correct location)
```python
# apps/reviews/tests/factories.py — already exists
class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog
    organisation = factory.SubFactory(OrganisationFactory)
    actor = None
    entity_type = "review"
    entity_id = factory.Sequence(lambda n: str(n))
    action = "reply_posted"
    before_data = None
    after_data = factory.LazyFunction(lambda: {"reply_text": "ok"})
```
[VERIFIED: project codebase — `apps/reviews/tests/factories.py` lines 47–57]

### `formatRelativeDate` — copy verbatim
```typescript
// frontend/src/widgets/review-management/ReviewTable.tsx lines 37–49
function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return "today";
  if (diffDays === 1) return "1 day ago";
  if (diffDays < 30) return `${diffDays} days ago`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths === 1) return "1 month ago";
  if (diffMonths < 12) return `${diffMonths} months ago`;
  const diffYears = Math.floor(diffMonths / 12);
  return diffYears === 1 ? "1 year ago" : `${diffYears} years ago`;
}
// Copy to: frontend/src/widgets/audit-log/utils.ts
```
[VERIFIED: project codebase]

### `DataTable` `renderExpanded` prop interface
```typescript
// frontend/src/widgets/data-table/DataTable.tsx line 30
renderExpanded?: (row: T) => ReactNode;
// colSpan computed as: columns.length + (renderRowActions ? 1 : 0) + (hasSelection ? 1 : 0)
// For audit log: no renderRowActions, no selection → colSpan = 5
```
[VERIFIED: project codebase]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual `request.GET` param handling | `django-filter` FilterSet | Phase 11 | All new FilterSets follow this pattern |
| `PageNumberPagination` everywhere | `CursorPagination` for large unbounded tables | Phase 21 (new) | First cursor-paginated endpoint — new class needed |
| Template data via `data-*` attributes | `json_script` Django tag for structured JSON | Phase 11 | `readJsonScript<T>()` pattern in React widgets |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Staff two-step selector (materialise entity IDs) is acceptable performance for Phase 21 | Architecture Patterns - Pattern 1 | If Staff users have very large shop sets, `IN` clause could be slow. Mitigate: add `CaptureQueriesContext` test. |
| A2 | `audit_org_entity_date_idx` with tiebreaker `id` is sufficient for cursor pagination stability | Architecture Patterns - Pattern 2 | If DRF requires the tiebreaker field to be in the model's `Meta.ordering`, a migration may be needed. But DRF CursorPagination ordering is set on the pagination class, not the model. |

---

## Open Questions

1. **`action_item.merged` `count` discrepancy**
   - What we know: D-23 says `after_data={"merged_ids": [...], "count": N}` but Phase 18 wrote `{"merged_ids": [...]}` only.
   - What's unclear: Is the planner expected to patch the Phase 18 write, or accept the existing data shape?
   - Recommendation: Accept the existing data. Patching Phase 18 code is out of scope for Phase 21. The frontend renders raw JSON in the expanded panel — no `count` extraction needed.

2. **Actors dropdown data volume**
   - What we know: The actors dropdown is populated server-side via `json_script`. Distinct actors per org could be many.
   - What's unclear: Should the actors list be truncated? The CONTEXT.md says "distinct actors in the log for this org" with no cap.
   - Recommendation: Fetch distinct actors with `.values("actor_id", "actor__full_name").distinct()` ordered by `full_name`. No cap unless performance testing shows issues.

---

## Environment Availability

> This phase is code/config-only with no new external dependencies.

Step 2.6: SKIPPED (no external dependencies — all packages already installed)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django |
| Config file | `pyproject.toml` |
| Quick run command | `pytest apps/common/tests/test_audit_log_api.py -x` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-01 | `GET /api/v1/audit-logs/` returns 200 for ORG_ADMIN | API | `pytest apps/common/tests/test_audit_log_api.py::test_list_audit_logs_org_admin -x` | ❌ Wave 0 |
| REQ-01 | Cursor pagination returns `next`/`previous` | API | `pytest apps/common/tests/test_audit_log_api.py::test_cursor_pagination -x` | ❌ Wave 0 |
| REQ-01 | Query count ≤ 5 for list of 50 audit logs | API (query count) | `pytest apps/common/tests/test_audit_log_api.py::test_list_query_count -x` | ❌ Wave 0 |
| REQ-02 | Staff Admin sees only entries from accessible shops/items | API | `pytest apps/common/tests/test_audit_log_api.py::test_staff_scope -x` | ❌ Wave 0 |
| REQ-02 | Staff cannot see brand-scope action item entries | API | `pytest apps/common/tests/test_audit_log_api.py::test_staff_cannot_see_brand_items -x` | ❌ Wave 0 |
| REQ-03 | `entity_type` filter returns correct subset | API | `pytest apps/common/tests/test_audit_log_api.py::test_filter_entity_type -x` | ❌ Wave 0 |
| REQ-03 | `date_from`/`date_to` filter range | API | `pytest apps/common/tests/test_audit_log_api.py::test_filter_date_range -x` | ❌ Wave 0 |
| REQ-03 | `actor=system` returns null-actor entries | API | `pytest apps/common/tests/test_audit_log_api.py::test_filter_actor_system -x` | ❌ Wave 0 |
| REQ-04 | Serializer includes `actor_name`, excludes `before_data` | unit | `pytest apps/common/tests/test_audit_log_selectors.py::test_serializer_fields -x` | ❌ Wave 0 |
| REQ-05 | 120/min throttle scope active | API | `pytest apps/common/tests/test_audit_log_api.py::test_throttle_scope -x` | ❌ Wave 0 |
| REQ-06 | Superadmin gets 403 | API | `pytest apps/common/tests/test_audit_log_api.py::test_superadmin_forbidden -x` | ❌ Wave 0 |
| REQ-09 | No pending migrations | check | `python manage.py makemigrations --check --dry-run` | ✅ existing CI |

### Sampling Rate
- **Per task commit:** `pytest apps/common/tests/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `apps/common/tests/test_audit_log_api.py` — API tests (REQ-01 through REQ-06)
- [ ] `apps/common/tests/test_audit_log_selectors.py` — selector unit tests (REQ-02, REQ-04)
- [ ] `apps/common/selectors/__init__.py` — package init
- [ ] `apps/common/selectors/audit_logs.py` — selector module
- [ ] `apps/common/filters.py` — FilterSet
- [ ] `apps/common/serializers.py` — serializer
- [ ] `templates/org-admin/` directory

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `IsOrgScoped` requires authenticated user |
| V3 Session Management | yes | Django session auth (same as all template views) |
| V4 Access Control | yes | `IsOrgScoped` role guard + selector-layer org scoping + Staff two-step scope |
| V5 Input Validation | yes | `django-filter` validates all query params |
| V6 Cryptography | no | Read-only view, no crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-org data access (IDOR) | Information Disclosure | `IsOrgScoped.has_object_permission` + `filter(organisation_id=org_id)` in selector |
| Staff accessing brand-scope action item audit entries | Information Disclosure | Staff two-step: only `entity_id__in` of accessible SHOP-scope items |
| Superadmin accessing org-scoped audit data | Elevation of Privilege | `IsOrgScoped` denies Superadmin (role not in `ORG_ADMIN, STAFF_ADMIN`) |
| Unbounded pagination abuse | Denial of Service | `CursorPagination.max_page_size = 100` + `"audit_log_list": "120/minute"` throttle |

---

## Sources

### Primary (HIGH confidence)
- `apps/common/models.py` — AuditLog model fields, indexes, confirmed directly
- `apps/common/permissions.py` — `IsOrgScoped` confirmed; `IsStaffAdmin` confirmed absent
- `apps/action_items/services/lifecycle.py` — Phase 18 `action_item.merged` write confirmed at lines 412–420
- `apps/action_items/selectors/items.py` — Staff scoping pattern `get_accessible_shop_ids` confirmed
- `apps/action_items/filters.py` — FilterSet pattern confirmed
- `apps/common/views.py` — file confirmed to exist; viewset must be appended
- `apps/common/pagination.py` — `DefaultPageNumberPagination` confirmed; `CursorPagination` absent
- `config/urls.py` — SimpleRouter pattern confirmed; `api_urlpatterns` include pattern confirmed
- `frontend/src/widgets/data-table/DataTable.tsx` — `renderExpanded`, `skeletonWidth`, `colSpan` confirmed
- `frontend/src/widgets/review-management/ReviewTable.tsx` — `formatRelativeDate` function confirmed
- `frontend/vite.config.ts` — entrypoint pattern confirmed
- `templates/partials/sidebar_org.html` — nav item placement confirmed
- `templates/partials/_nav_item.html` — include syntax confirmed
- `apps/reviews/tasks.py` — `retry_failed_enrichments_task` confirmed; no `content_moderated` exclusion needed for Phase 21
- `apps/reviews/tests/factories.py` — `AuditLogFactory` confirmed at lines 47–57

### Secondary (MEDIUM confidence)
- DRF CursorPagination tiebreaker pattern — standard DRF practice; `ordering = ("-created_at", "id")` is well-documented

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all confirmed in codebase, no new packages
- Architecture: HIGH — all patterns verified against existing implementations
- Pitfalls: HIGH — `IsStaffAdmin` absence and `templates/org-admin/` gap confirmed by direct file inspection
- Frontend widget structure: HIGH — DataTable interface read directly, UI-SPEC fully developed

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (stable codebase, no fast-moving dependencies)
