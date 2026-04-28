# Phase 7: Regions - Research

**Researched:** 2026-04-28
**Domain:** Django REST Framework CRUD viewset + React widget (region management with auto-ID mechanic and delete guard)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Auto-ID suffix**: Computed client-side from `regions.length + 1` (from already-loaded list). Zero extra API calls.
- **No separator**: Format is `ABCD001` (pure uppercase letters + digits), not `ABCD-001`. Matches `[A-Z0-9]` validation exactly.
- **No client-side skip logic**: If computed ID is taken, server returns RGN-06 duplicate error; client shows inline error only.
- **Auto-population in create mode**: Fires on every keystroke — first letter per word, uppercased, up to 4 letters, then 3-digit zero-padded suffix.
- **Edit mode Region ID**: Pre-filled, always editable. No auto-population. Clearing leaves field empty. Typing in Region Name does NOT update Region ID.
- **Shops pre-filter URL**: `/admin/org/shops/?region={region.pk}` (integer PK, not region_id string).
- **Delete guard**: `delete_region` service checks `region.shops.exists()` → raises `RegionHasShopsError` → view returns 409 with `{ "shop_count": N }`. Widget checks for 409, shows amber popup.
- **Hard delete**: No soft-delete for regions. Permanent delete when no shops.
- **Race safety**: `UniqueConstraint(["organisation", "region_id"])` at DB level is the authoritative guard. No `select_for_update()` needed. `django-sequences` is NOT used.

### Claude's Discretion

- Exact service exception class name and module location (`apps/regions/exceptions.py` or inline)
- Whether `list_regions` returns all regions or only active ones (return all — `is_active` reserved for future use)
- Vite entrypoint filename: `frontend/src/entrypoints/region-management.tsx`
- React widget directory: `frontend/src/widgets/region-management/`
- Django template: extends `base_org.html`, mounts React widget into `<div id="region-management-root">`

### Deferred Ideas (OUT OF SCOPE)

- Region `is_active` toggle / enable-disable — field exists in the model but not required in Phase 7
- Region search / filter — not in Phase 7 requirements
- Shops pre-filter implementation — Phase 8 reads `?region=<pk>`; Phase 7 only outputs the link
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RGN-01 | Org Admin sees a list of all regions (creation order) with columns: Region Name, Region ID (pill badge, monospace), Edit + Delete icon buttons | `list_regions` selector + `RegionViewSet` list action + `RegionTable.tsx` + `RegionIdBadge.tsx` |
| RGN-02 | Regions list shows empty state (Map icon, "No regions yet", CTA) when no regions exist | `DataTable` `emptyState` prop + `RegionEmptyState.tsx` |
| RGN-03 | Create modal: Region Name (2–60 chars, required), Region ID (uppercase + digits, 2–10 chars, unique within org, required) | `CreateRegionModal.tsx` + `RegionCreateSerializer` |
| RGN-04 | Auto-population of Region ID from Region Name as user types (first letter per word, up to 4, + 3-digit sequence) | `autoMode` state in `CreateRegionModal.tsx` |
| RGN-05 | Clearing a manually-edited Region ID resumes auto-population | `autoMode` toggled back to `true` on `onChange` when value becomes `""` |
| RGN-06 | Duplicate Region ID shows inline error "This Region ID is already in use." | DB `UniqueConstraint` raises `IntegrityError` → serializer returns 400 `{ "region_id": [...] }` → widget maps to inline error |
| RGN-07 | Successful create: close modal, toast "Region '{name}' created.", refresh list | `emitToast` + `refresh()` |
| RGN-08 | Edit modal: Region Name and Region ID both editable; typing name does NOT update ID | `EditRegionModal.tsx` with `autoMode` permanently `false` |
| RGN-09 | Successful edit: toast "Region updated.", refresh list | `emitToast` + `refresh()` |
| RGN-10 | Delete with shops assigned: amber blocking popup with shop count and Manage Shops link | 409 response from `delete_region` service → `BlockedDeleteModal` (amber `Modal`) |
| RGN-11 | Delete with no shops: red confirmation popup → permanent hard delete → toast "Region '{name}' deleted." | Red `ConfirmModal` + `deleteRegion` API + `emitToast` |
| XMOD-02 | Region deletion is blocked (info popup with shop count and "Manage Shops" link) when the Region has one or more Shops assigned | Implemented via `RegionHasShopsError` in `delete_region` service; view converts to 409 |
</phase_requirements>

---

## Summary

Phase 7 is a fully self-contained CRUD module for the `Region` model. The heavy backend infrastructure (model with `UniqueConstraint`, `TenantScopedViewSet`, `IsOrgScoped`, `RegionFactory`, `assert_query_ceiling`) was scaffolded in Phase 6 and is ready to extend. This phase adds the service/selector/viewset/serializer layer and the full React widget tree.

The most nuanced piece is the auto-ID mechanic (RGN-04/05): a client-side state machine with `autoMode: boolean` that the planner must treat carefully — it must only exist in `CreateRegionModal`, not `EditRegionModal`. The delete guard (RGN-10/XMOD-02) requires a deliberate 409 HTTP response path: the service raises a typed exception, the viewset catches it and returns 409, and the React widget's `api.ts` catches status 409 and dispatches the amber popup instead of the red one.

The entire frontend follows the established `org-management` widget pattern verbatim: two-root entrypoint, `CreateButtonBridge`, `window.dispatchEvent("region:refresh")`, data blob seeded via Django's `json_script`. No new libraries or build changes are required. The only Vite config change is adding `"region-management"` to `rollupOptions.input`.

**Primary recommendation:** Copy the `org-management` widget pattern as a structural template, then strip down to the Region-specific fields, replace the three-dot `RowActionsMenu` with direct Edit/Delete icon buttons, and wire the delete guard's 409 path carefully.

---

## Standard Stack

### Core (already installed — no new deps required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 6.0.x | Web framework + ORM | Project standard |
| DRF | latest | REST API viewsets, serializers | Project standard |
| React | 19.2.5 | Frontend widget | Already installed (`package.json`) |
| lucide-react | 1.8.0 | Icons (Pencil, Trash2, MapPin, AlertTriangle) | Already installed |
| focus-trap-react | 12.0.0 | Modal focus management | Already installed (Modal.tsx uses it) |
| vitest | 2.1.8 | Frontend unit tests | Already installed |
| pytest + pytest-django | current | Backend tests | Project standard |
| factory-boy | current | Test fixtures | Project standard |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `apps.common.viewsets.TenantScopedViewSet` | Phase 6 | Automatic org-scoped `get_queryset()` | Base class for `RegionViewSet` |
| `apps.common.permissions.IsOrgScoped` | Phase 6 | ORG_ADMIN + organisation_id permission check | Permission class for `RegionViewSet` |
| `apps.accounts.permissions.IsOrgAdmin` | Phase 6 | ORG_ADMIN-only permission | Stacked with `IsOrgScoped` on viewset |
| `apps.common.tests.fixtures.assert_query_ceiling` | Phase 6 | Query count ceiling assertions | Required for CI query-count test |
| `apps.common.tests.fixtures.two_orgs_two_admins` | Phase 6 | Cross-tenant isolation test fixture | Required for IDOR test |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct icon buttons for Edit/Delete | `RowActionsMenu` (three-dot) | RGN-01 explicitly requires direct icon buttons — no three-dot menu |
| 409 for delete guard | Custom error response in 200 body | 409 is semantically correct for "conflict with current state"; matches `07-UI-SPEC.md` API contract |
| `Modal` directly for amber block | `ConfirmModal` variant="amber" | `ConfirmModal` forces two-button footer; RGN-10 is info-only with single "Got it" button — use `Modal` directly |

**Installation:** No new packages required. All dependencies already installed.

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
apps/regions/
├── exceptions.py              # RegionHasShopsError
├── serializers.py             # RegionReadSerializer, RegionCreateSerializer, RegionUpdateSerializer
├── views.py                   # region_list (template view) + RegionViewSet
├── urls.py                    # /admin/org/regions/ (template) + /api/v1/regions/ (router)
├── selectors/
│   ├── __init__.py
│   └── regions.py             # list_regions()
├── services/
│   ├── __init__.py
│   └── regions.py             # create_region(), update_region(), delete_region()
└── tests/
    ├── test_services.py
    ├── test_selectors.py
    └── test_views.py          # includes query-count ceiling test

frontend/src/
├── entrypoints/
│   └── region-management.tsx  # two-root entrypoint
└── widgets/
    └── region-management/
        ├── types.ts
        ├── api.ts
        ├── useRegions.ts
        ├── RegionTable.tsx
        ├── RegionIdBadge.tsx
        ├── RegionEmptyState.tsx
        ├── CreateRegionModal.tsx
        └── EditRegionModal.tsx

templates/regions/
└── region_list.html           # extends base_org.html

vite.config.ts                 # add "region-management" entrypoint
config/urls.py                 # register RegionViewSet router
apps/organisations/urls.py     # replace org_stub_view for /admin/org/regions/
```

### Pattern 1: Services/Selectors (project standard)

**What:** All write-side logic in `services/regions.py`; all read-side logic in `selectors/regions.py`. The viewset calls these only — never `Region.objects.*` directly from views.

**When to use:** Every create/update/delete operation, every list query.

```python
# apps/regions/services/regions.py
from __future__ import annotations
from django.db import transaction
from apps.regions.models import Region
from apps.regions.exceptions import RegionHasShopsError

@transaction.atomic
def create_region(*, organisation, name: str, region_id: str) -> Region:
    return Region.objects.create(
        organisation=organisation,
        name=name,
        region_id=region_id,
    )

@transaction.atomic
def update_region(*, region: Region, name: str | None = None, region_id: str | None = None) -> Region:
    changed: list[str] = []
    if name is not None and region.name != name:
        region.name = name
        changed.append("name")
    if region_id is not None and region.region_id != region_id:
        region.region_id = region_id
        changed.append("region_id")
    if changed:
        changed.append("updated_at")
        region.save(update_fields=changed)
    return region

def delete_region(*, region: Region) -> None:
    if region.shops.exists():
        count = region.shops.count()
        raise RegionHasShopsError(shop_count=count)
    region.delete()
```

```python
# apps/regions/selectors/regions.py
from django.db.models import QuerySet
from apps.regions.models import Region

def list_regions(*, organisation_id: int) -> QuerySet[Region]:
    """Returns all regions for the organisation, ordered by created_at (model default)."""
    return Region.objects.filter(organisation_id=organisation_id)
```

### Pattern 2: TenantScopedViewSet + IntegrityError → ValidationError

**What:** `RegionViewSet` inherits `TenantScopedViewSet` (auto org-filter) and catches `IntegrityError` from the DB `UniqueConstraint` to return a 400 field error.

**When to use:** Whenever a serializer `create` or `update` action could trigger the `UniqueConstraint`.

```python
# apps/regions/views.py (DRF viewset portion)
from django.db import IntegrityError
from rest_framework import serializers, viewsets, mixins, status
from rest_framework.response import Response
from apps.accounts.permissions import IsOrgAdmin
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet
from apps.regions.exceptions import RegionHasShopsError
from apps.regions.models import Region
from apps.regions.selectors.regions import list_regions
from apps.regions.serializers import (
    RegionReadSerializer,
    RegionCreateSerializer,
    RegionUpdateSerializer,
)
from apps.regions.services.regions import create_region, update_region, delete_region

class RegionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgAdmin, IsOrgScoped]
    queryset = Region.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()  # TenantScopedViewSet applies org filter
        return qs  # list_regions selector not needed here; super() already filters

    def get_serializer_class(self):
        if self.action == "list":
            return RegionReadSerializer
        if self.action == "create":
            return RegionCreateSerializer
        if self.action == "partial_update":
            return RegionUpdateSerializer
        return RegionReadSerializer

    def perform_create(self, serializer):
        user = self.request.user
        try:
            region = create_region(
                organisation=user.organisation,
                **serializer.validated_data,
            )
        except IntegrityError:
            raise serializers.ValidationError(
                {"region_id": ["This Region ID is already in use."]}
            )
        serializer.instance = region

    def perform_update(self, serializer):
        try:
            update_region(region=serializer.instance, **serializer.validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {"region_id": ["This Region ID is already in use."]}
            )

    def destroy(self, request, *args, **kwargs):
        region = self.get_object()
        try:
            delete_region(region=region)
        except RegionHasShopsError as exc:
            return Response({"shop_count": exc.shop_count}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

### Pattern 3: Template view replaces org_stub_view

**What:** Phase 7 replaces the `org_stub_view` stub at `/admin/org/regions/` with a real Django template view that seeds the React widget via `json_script`.

**When to use:** Replacing the stub at the exact URL name `org_regions`.

```python
# apps/regions/views.py (template view portion)
from apps.accounts.permissions import org_admin_required

@org_admin_required
def region_list(request):
    from apps.regions.selectors.regions import list_regions
    from apps.regions.serializers import RegionReadSerializer
    regions_qs = list_regions(organisation_id=request.user.organisation_id)
    regions_data = list(RegionReadSerializer(regions_qs, many=True).data)
    return render(request, "regions/region_list.html", {
        "regions_json": regions_data,
        "regions_count": len(regions_data),
    })
```

```python
# apps/organisations/urls.py — replace stub with real view
# Change: org_stub_view → region_list imported from apps.regions.views
path("admin/org/regions/", region_list, name="org_regions"),
```

**Critical:** The URL name `org_regions` must remain unchanged. The sidebar template links to `{% url 'org_regions' %}` and the Phase 6 dashboard CTA uses `/admin/org/regions/` hardcoded.

### Pattern 4: Two-root React entrypoint

**What:** Entrypoint mounts two separate React roots — `#region-modals-root` (always present, holds all modals + CreateButtonBridge) and `#region-table-root` (present only when `regions_count > 0`, holds the table). Modal state is shared via `window._regionModalHandlers` (following `org-management` pattern).

**When to use:** Always — this is the established pattern for all Org Admin React widgets.

```typescript
// frontend/src/entrypoints/region-management.tsx (structural pattern)
// Mount modals root — always present
const modalsRoot = document.getElementById("region-modals-root");
if (modalsRoot) {
  createRoot(modalsRoot).render(<StrictMode><RegionModals /></StrictMode>);
}
// Mount table root — only present when regions_count > 0
const tableRoot = document.getElementById("region-table-root");
if (tableRoot) {
  createRoot(tableRoot).render(<StrictMode><RegionTableWidget /></StrictMode>);
}
```

### Pattern 5: RegionHasShopsError typed exception

**What:** A typed application exception (not a DRF exception) that carries `shop_count`. Raised by the service, caught in the viewset's `destroy()` override.

**When to use:** Delete guard — service signals the blocking condition; viewset decides the HTTP response.

```python
# apps/regions/exceptions.py
class RegionHasShopsError(Exception):
    def __init__(self, shop_count: int) -> None:
        self.shop_count = shop_count
        super().__init__(f"Region has {shop_count} shop(s) assigned.")
```

### Anti-Patterns to Avoid

- **Do NOT inherit `ModelViewSet` for `RegionViewSet`**: It would expose `retrieve` and `list`-with-detail endpoints not needed here. Use `GenericViewSet` + mixins or `TenantScopedViewSet` + explicit mixins.
- **Do NOT add `RowActionsMenu` (three-dot)**: RGN-01 requires direct Edit + Delete icon buttons in the row. No dropdown.
- **Do NOT add auto-population logic to `EditRegionModal`**: RGN-08 is explicit — edit mode has no auto-population at all, including no resume-on-clear.
- **Do NOT soft-delete regions**: The decision is hard delete (no `soft_delete()` method needed, just `region.delete()`).
- **Do NOT put `select_for_update()` on region creation**: The ID is user-controlled; the DB `UniqueConstraint` handles race conditions atomically without a row lock.
- **Do NOT register RegionViewSet under `apps/organisations/urls.py`**: API routes go through `config/urls.py` router to keep separation clean.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Org-scoped queryset | Manual `filter(organisation_id=...)` in every view | `TenantScopedViewSet.get_queryset()` | Already implemented and tested in Phase 6; skipping it risks IDOR |
| Duplicate ID uniqueness | Application-level check-before-insert | DB `UniqueConstraint` + catch `IntegrityError` | Race-condition-safe; DB-level constraint is the only reliable guard |
| Modal focus trap | Custom `document.addEventListener("keydown")` | `FocusTrap` via `Modal.tsx` | `focus-trap-react` already wired in `Modal.tsx`; don't duplicate |
| Cross-tenant isolation | Manual permission checks in every action | `IsOrgScoped.has_object_permission()` | Already prevents IDOR on detail/mutation endpoints; must be included in `permission_classes` |
| Query count assertion helper | Manual `len(ctx.captured_queries) <= N` per test | `assert_query_ceiling` fixture from `apps.common.tests.fixtures` | Must be imported explicitly (not auto-discovered outside `apps/common/tests/`) |
| Toast dispatch | Custom event system | `emitToast()` from `frontend/src/lib/toast.ts` | Alpine.js listener already wired in `components/toasts.html` |

**Key insight:** Every cross-cutting concern in this phase already has a tested, in-project solution from Phases 1–6. The job is wiring them together, not building new infrastructure.

---

## Common Pitfalls

### Pitfall 1: `two_orgs_two_admins` and `assert_query_ceiling` not auto-discovered

**What goes wrong:** Tests in `apps/regions/tests/` that use `two_orgs_two_admins` or `assert_query_ceiling` fixtures fail with `fixture 'two_orgs_two_admins' not found`.

**Why it happens:** `apps/common/tests/conftest.py` re-exports these fixtures, but pytest's `conftest.py` auto-discovery only covers the directory subtree where the conftest lives. `apps/regions/tests/` is outside that subtree.

**How to avoid:** Explicitly import fixtures at the top of each test file that needs them:
```python
from apps.common.tests.fixtures import assert_query_ceiling, two_orgs_two_admins
```
This is the project standard documented in STATE.md: "Phase 7-9 tests must explicitly import from apps.common.tests.fixtures".

**Warning signs:** `fixture not found` errors for fixtures that clearly exist in `apps/common/tests/`.

### Pitfall 2: `org_regions` URL name collision when replacing stub

**What goes wrong:** After Phase 7 replaces the stub view, any reverse lookup for `org_regions` breaks if the import path or URL name is changed.

**Why it happens:** The sidebar template (`partials/sidebar_org.html`) and the Phase 6 dashboard CTA both reference this URL. Renaming it breaks navigation.

**How to avoid:** Keep `name="org_regions"` in `apps/organisations/urls.py` when swapping the view function. Only the view function changes, not the URL pattern or name.

**Warning signs:** 404s or `NoReverseMatch` errors on the sidebar navigation after deploying.

### Pitfall 3: 409 vs 400 for delete guard — widget diverges

**What goes wrong:** The service raises `RegionHasShopsError` but the viewset returns a 400 or re-raises a DRF `ValidationError`. The React widget only checks for 409 to trigger the amber popup.

**Why it happens:** Default DRF error handling catches `Exception` subclasses and may coerce them. The viewset `destroy()` must explicitly override and return `Response({"shop_count": N}, status=409)`.

**How to avoid:** Override `destroy()` in `RegionViewSet` as shown in Pattern 2. Do not use DRF's exception handler for this path.

**Warning signs:** Delete with shops triggers the red confirmation popup (or a generic toast error) instead of the amber info popup.

### Pitfall 4: `autoMode` leaks into `EditRegionModal`

**What goes wrong:** Copying `CreateRegionModal.tsx` to create `EditRegionModal.tsx` without removing the auto-population logic. The edit modal then updates Region ID when the user types in Region Name.

**Why it happens:** Copy-paste; RGN-08 is easy to miss.

**How to avoid:** `EditRegionModal` initializes with `autoMode` conceptually always `false`. Simplest implementation: omit the `autoMode` state variable entirely from `EditRegionModal`; the `Region Name` field's `onChange` never touches the `region_id` state.

**Warning signs:** Test for RGN-08 — typing in Region Name during edit changes Region ID field value.

### Pitfall 5: Query count N+1 on list endpoint

**What goes wrong:** `RegionViewSet.list` issues one query per region to resolve `organisation`.

**Why it happens:** Serializer accesses `region.organisation.name` (or similar nested field) without a `select_related`.

**How to avoid:** The `list_regions` selector (or the viewset's `get_queryset`) must never join back to `organisation` data in the serializer. `RegionReadSerializer` only needs `id`, `name`, `region_id`, `created_at` — all on the `Region` table itself. No `select_related` needed for this minimal shape.

**Warning signs:** `assert_query_ceiling(ctx, max_queries=5)` fails with count > 5.

### Pitfall 6: Vite entrypoint not registered

**What goes wrong:** `region-management.tsx` bundle is never built. Django template loads the script but the file doesn't exist in the manifest.

**Why it happens:** `vite.config.ts` `rollupOptions.input` must be updated to include the new entrypoint.

**How to avoid:** Add `"region-management": resolve(__dirname, "src/entrypoints/region-management.tsx")` to `rollupOptions.input` in `vite.config.ts`.

**Warning signs:** Blank page or console error "Cannot find module" in the browser after deploy. Template's `{% vite_asset 'region-management' %}` (or equivalent) returns a 404.

### Pitfall 7: `RegionFactory.region_id` format incompatible with `[A-Z0-9]` validator

**What goes wrong:** `RegionFactory` generates `region_id = "RGN-001"` (with a hyphen). Serializer validation with `[A-Z0-9]` pattern rejects these in tests that use the factory to seed pre-existing data.

**Why it happens:** Factory uses `f"RGN-{n:03d}"` which includes a hyphen — invalid per RGN-03 constraint.

**How to avoid:** The serializer `RegionCreateSerializer` validates only on create/update. For tests that bypass the API and use `RegionFactory` directly (e.g., delete guard test seeding), the factory values pass directly to `Region.objects.create()` without serializer validation — hyphens are allowed at DB level. However, if tests POST through the API, factory-generated IDs with hyphens will fail validation. Update factory or use explicit `region_id="NW001"` in API-level tests.

**Warning signs:** Tests that POST through the API using factory-generated data get 400 validation errors for `region_id`.

---

## Code Examples

Verified patterns from existing codebase:

### RegionIdBadge — monospace pill (from OrgTable.tsx TypeBadge)
```typescript
// Source: frontend/src/widgets/org-management/OrgTable.tsx TypeBadge pattern
export function RegionIdBadge({ regionId }: { regionId: string }) {
  return (
    <span
      className="inline-flex items-center px-2 py-[3px] rounded-[999px] text-[12px] font-normal font-mono bg-line-soft text-muted"
      data-testid="region-id-badge"
    >
      {regionId}
    </span>
  );
}
```

### Auto-ID derivation logic (from UI-SPEC.md)
```typescript
// Source: 07-UI-SPEC.md §Surface 4 — Create Region Modal
function deriveRegionId(name: string, count: number): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const prefix = words
    .slice(0, 4)
    .map((w) => w[0].toUpperCase())
    .join("");
  const suffix = String(count + 1).padStart(3, "0");
  return prefix + suffix;
}
// Example: "North West", 3 existing regions → "NW004"
```

### autoMode state machine in CreateRegionModal
```typescript
// Source: 07-UI-SPEC.md §Surface 4 (auto-ID behavior)
const [autoMode, setAutoMode] = useState(true);
const [regionId, setRegionId] = useState("");

// Region Name onChange
const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  setName(e.target.value);
  if (autoMode) {
    setRegionId(deriveRegionId(e.target.value, rows.length));
  }
};

// Region ID onChange — user touched it
const handleRegionIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  const val = e.target.value;
  setRegionId(val);
  if (val === "") {
    setAutoMode(true);  // RGN-05: resume auto-population when cleared
  } else {
    setAutoMode(false); // RGN-04: stop auto-population on manual edit
  }
};
```

### Delete guard — 409 detection in api.ts
```typescript
// Source: frontend/src/widgets/org-management/api.ts ApiError pattern + 07-UI-SPEC.md
export async function deleteRegion(id: number): Promise<void | { shop_count: number }> {
  const resp = await fetch(`/api/v1/regions/${id}/`, {
    method: "DELETE",
    headers: headers("DELETE"),
    credentials: "same-origin",
  });
  if (resp.status === 409) {
    const body = await resp.json() as { shop_count: number };
    return body; // caller checks for object return to know it was blocked
  }
  await handle(resp); // throws ApiError on other non-2xx
}
```

### Query count ceiling test pattern
```python
# Source: apps/organisations/tests/test_views.py + apps/common/tests/fixtures.py
from django.db import connection
from django.test.utils import CaptureQueriesContext
from apps.common.tests.fixtures import assert_query_ceiling

def test_regions_list_query_count_ceiling(assert_query_ceiling, org_admin_client):
    RegionFactory.create_batch(20, organisation=org_admin_client.user.organisation)
    with CaptureQueriesContext(connection) as ctx:
        resp = org_admin_client.get("/api/v1/regions/")
    assert resp.status_code == 200
    assert_query_ceiling(ctx, max_queries=5)  # auth + session + region list + count + savepoint
```

### Service exception and viewset destroy override
```python
# Source: pattern derived from apps/organisations/views.py perform_create + IntegrityError handling
def destroy(self, request, *args, **kwargs):
    region = self.get_object()  # triggers IsOrgScoped.has_object_permission
    try:
        delete_region(region=region)
    except RegionHasShopsError as exc:
        return Response({"shop_count": exc.shop_count}, status=status.HTTP_409_CONFLICT)
    return Response(status=status.HTTP_204_NO_CONTENT)
```

### Template — two-root mount pattern
```html
<!-- Source: templates/organisations/list.html pattern adapted for regions -->
{% extends "base_org.html" %}
{% block content %}
  <div id="region-modals-root"></div>
  {% if regions_count > 0 %}
    {{ regions_json|json_script:"region-data" }}
    <div id="region-table-root"></div>
  {% endif %}
{% endblock %}
{% block extra_js %}
  {% vite_asset 'region-management' %}
{% endblock %}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `django-cryptography` for field encryption | `django-fernet-encrypted-fields==0.4.0` | Phase 6 init | No impact on Phase 7 (no encrypted fields) |
| `django-sequences` for auto-IDs | Client-side `regions.length + 1` | Phase 7 decision | Simpler; no DB sequence table; user controls the ID |
| Stub views for org sub-pages | Real page views per phase | Phase 7 onward | Replace stub; keep URL name |
| `ModelViewSet` for all CRUD | `GenericViewSet + mixins` when not all CRUD needed | Project standard | Use `ListModelMixin + CreateModelMixin + UpdateModelMixin + DestroyModelMixin` for RegionViewSet |

**Deprecated/outdated:**
- `org_stub_view` for `/admin/org/regions/`: replaced by `region_list` template view in Phase 7. The stub view remains in `apps/organisations/views.py` for `/admin/org/shops/` and `/admin/org/team/` until Phases 8 and 9.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django 8.3.3 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest apps/regions/ -x -q` |
| Full suite command | `pytest --cov=apps --cov-fail-under=85` |
| Frontend tests | `cd frontend && npm run test` (vitest) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RGN-01 | List endpoint returns all org regions in created_at order | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_list -x` | Wave 0 |
| RGN-02 | Template renders empty state when regions_count == 0 | integration | `pytest apps/regions/tests/test_views.py::test_region_list_template_empty_state -x` | Wave 0 |
| RGN-03 | Create endpoint validates name (2–60 chars) and region_id (`[A-Z0-9]`, 2–10 chars) | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_create_validation -x` | Wave 0 |
| RGN-04 | Auto-ID derivation logic (client-side) | unit (frontend) | `cd frontend && npm run test -- region-management` | Wave 0 |
| RGN-05 | autoMode resumes when region_id cleared | unit (frontend) | `cd frontend && npm run test -- region-management` | Wave 0 |
| RGN-06 | Duplicate region_id returns 400 with field error | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_create_duplicate_id -x` | Wave 0 |
| RGN-07 | Successful create returns 201 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_create_returns_201 -x` | Wave 0 |
| RGN-08 | Edit endpoint updates name and region_id independently | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_patch -x` | Wave 0 |
| RGN-09 | Successful edit returns 200 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_patch_returns_200 -x` | Wave 0 |
| RGN-10 / XMOD-02 | Delete with shops returns 409 with shop_count | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_delete_blocked -x` | Wave 0 |
| RGN-11 | Delete with no shops returns 204 | unit | `pytest apps/regions/tests/test_views.py::test_regions_api_delete_no_shops -x` | Wave 0 |
| CI ceiling | List endpoint query count <= 5 regardless of result size | performance | `pytest apps/regions/tests/test_views.py::test_regions_list_query_count_ceiling -x` | Wave 0 |
| Cross-tenant | Org A admin cannot read/mutate Org B regions | security | `pytest apps/regions/tests/test_views.py::test_regions_cross_tenant_isolation -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest apps/regions/ -x -q`
- **Per wave merge:** `pytest --cov=apps --cov-fail-under=85`
- **Phase gate:** Full suite green + `cd frontend && npm run test` before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/regions/tests/test_services.py` — covers create_region, update_region, delete_region, RegionHasShopsError
- [ ] `apps/regions/tests/test_selectors.py` — covers list_regions ordering and filtering
- [ ] `apps/regions/tests/test_views.py` — covers all API endpoints + template view + query ceiling
- [ ] `apps/regions/serializers.py` — must exist before test imports compile
- [ ] `apps/regions/services/__init__.py` + `apps/regions/services/regions.py` — service layer
- [ ] `apps/regions/selectors/__init__.py` + `apps/regions/selectors/regions.py` — selector layer
- [ ] `apps/regions/exceptions.py` — `RegionHasShopsError`
- [ ] `apps/regions/views.py` — `region_list` template view + `RegionViewSet`
- [ ] `apps/regions/urls.py` — URL patterns (or router registration in `config/urls.py`)
- [ ] `templates/regions/region_list.html` — Django template
- [ ] `frontend/src/widgets/region-management/` — all widget files
- [ ] `frontend/src/entrypoints/region-management.tsx` — entrypoint

---

## Open Questions

1. **`RegionFactory.region_id` contains hyphens (`RGN-001`)**
   - What we know: Factory generates `f"RGN-{n:03d}"` which includes `-`, invalid per RGN-03 `[A-Z0-9]` pattern.
   - What's unclear: Whether any Phase 7 test will POST through the API using factory-generated data (if so, validation rejects it).
   - Recommendation: Update `RegionFactory.region_id` to `factory.Sequence(lambda n: f"RGN{n:03d}")` as part of Wave 0. This is a safe change — the factory is only used in tests, and the model itself has no constraint against hyphens at the DB level.

2. **`region_list` template view URL registration location**
   - What we know: `apps/organisations/urls.py` currently holds the stub for `org_regions`. The CONTEXT.md says Phase 7 replaces it.
   - What's unclear: Whether to move the URL to a new `apps/regions/urls.py` and include it in `config/urls.py`, or keep it in `apps/organisations/urls.py` with the view imported from `apps.regions.views`.
   - Recommendation: Keep the URL declaration in `apps/organisations/urls.py` (it's a navigation URL, not a resource URL), but import the view from `apps.regions.views`. This avoids creating a new URL include while keeping view logic in the correct app.

3. **`RegionViewSet` URL registration — router in `config/urls.py`**
   - What we know: `OrganisationViewSet` is registered in `config/urls.py` via `SimpleRouter`. The same pattern should apply.
   - What's unclear: Whether to add `RegionViewSet` to the existing `router` in `config/urls.py` or add a second router.
   - Recommendation: Add `router.register(r"api/v1/regions", RegionViewSet, basename="region")` to the existing router in `config/urls.py`. Single router = single `include(router.urls)` call.

---

## Sources

### Primary (HIGH confidence)

- `apps/regions/models.py` — Region model with UniqueConstraint, is_active field, created_at ordering
- `apps/common/viewsets.py` — TenantScopedViewSet implementation (org_id filter + none() fallback)
- `apps/common/permissions.py` — IsOrgScoped with has_object_permission IDOR guard
- `apps/accounts/permissions.py` — IsOrgAdmin, org_admin_required decorator
- `apps/common/tests/fixtures.py` — assert_query_ceiling, two_orgs_two_admins fixtures
- `apps/organisations/views.py` — OrganisationViewSet (IntegrityError → ValidationError pattern, perform_create, perform_update)
- `apps/organisations/services/organisations.py` — service pattern (transaction.atomic, typed kwargs, update_fields)
- `apps/organisations/urls.py` — org_stub_view for regions slug; URL name `org_regions` confirmed
- `config/urls.py` — SimpleRouter registration pattern
- `frontend/src/widgets/org-management/` — canonical widget pattern (api.ts, useOrgs.ts, OrgTable.tsx, CreateOrgModal.tsx)
- `frontend/src/widgets/modal/ConfirmModal.tsx` — ConfirmModal props and variant system
- `frontend/src/lib/toast.ts` — emitToast API
- `frontend/src/entrypoints/org-management.tsx` — two-root entrypoint pattern, CreateButtonBridge, window event bus
- `frontend/vite.config.ts` — rollupOptions.input (must add region-management)
- `.planning/phases/07-regions/07-CONTEXT.md` — all locked decisions
- `.planning/phases/07-regions/07-UI-SPEC.md` — full surface specs, copywriting, component inventory
- `.planning/STATE.md` — fixture import decision, django-sequences smoke test result

### Secondary (MEDIUM confidence)

- `apps/regions/tests/factories.py` — RegionFactory (region_id format issue identified)
- `apps/regions/tests/test_models.py` — UniqueConstraint and cross-org tests (confirmed existing)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified directly in codebase files
- Architecture patterns: HIGH — derived from reading existing OrganisationViewSet, TenantScopedViewSet, and org-management widget source
- Pitfalls: HIGH — all pitfalls traced to actual codebase evidence (STATE.md decisions, factory definitions, conftest pattern)
- Frontend auto-ID mechanic: HIGH — fully specified in 07-UI-SPEC.md with exact state machine
- Delete guard 409 path: HIGH — confirmed in 07-UI-SPEC.md API contract section

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (stable stack — 30-day validity)
