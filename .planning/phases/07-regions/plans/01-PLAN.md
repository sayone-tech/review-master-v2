---
plan: 1
phase: 7
slug: regions
wave: 1
status: pending
requirements: [RGN-01, RGN-03, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02]
---

# Plan 1 — Backend: Services, Selectors, Serializers, ViewSet, URLs

## Goal

Create the complete Django backend for the Regions module: exceptions, services, selectors, serializers, ViewSet, template view, and URL wiring — everything the API tests in Plan 02 will exercise.

## Wave 0 Dependencies

The following files must exist before Plan 02 test imports will compile. This plan creates all of them:

- `apps/regions/exceptions.py` — `RegionHasShopsError`
- `apps/regions/services/__init__.py` + `apps/regions/services/regions.py`
- `apps/regions/selectors/__init__.py` + `apps/regions/selectors/regions.py`
- `apps/regions/serializers.py` — `RegionReadSerializer`, `RegionCreateSerializer`, `RegionUpdateSerializer`
- `apps/regions/views.py` — `region_list` template view + `RegionViewSet`
- `templates/regions/region_list.html`
- Fix `apps/regions/tests/factories.py` — `region_id` hyphen bug

Plan 02 must not be started until all files above are committed.

---

## Tasks

### Task 7-01-01: Fix RegionFactory region_id format and create service/selector/exception scaffolding

**Requirement:** RGN-03, RGN-10, XMOD-02

**Files:**
- `apps/regions/tests/factories.py`
- `apps/regions/exceptions.py`
- `apps/regions/services/__init__.py`
- `apps/regions/services/regions.py`
- `apps/regions/selectors/__init__.py`
- `apps/regions/selectors/regions.py`

**Action:**

**`apps/regions/tests/factories.py`** — Fix the `region_id` sequence to remove the hyphen (invalid per `[A-Z0-9]` constraint):
```python
region_id = factory.Sequence(lambda n: f"RGN{n:03d}")
```
(Was: `f"RGN-{n:03d}"`. Tests that POST through the API would receive a 400 validation error with the old format.)

**`apps/regions/exceptions.py`** — Create typed exception for the delete guard:
```python
from __future__ import annotations


class RegionHasShopsError(Exception):
    """Raised by delete_region() when the region has one or more shops assigned."""

    def __init__(self, shop_count: int) -> None:
        self.shop_count = shop_count
        super().__init__(f"Region has {shop_count} shop(s) assigned.")
```

**`apps/regions/services/__init__.py`** — Empty init.

**`apps/regions/services/regions.py`** — Three service functions following the project's `@transaction.atomic` + keyword-only args pattern. `create_region` wraps `Region.objects.create` (the DB `UniqueConstraint` handles duplicate-ID races atomically — no `select_for_update` needed). `update_region` uses `save(update_fields=...)` for efficiency. `delete_region` checks `region.shops.exists()` first and raises `RegionHasShopsError` if shops are assigned, otherwise calls `region.delete()`:

```python
from __future__ import annotations

from django.db import transaction

from apps.regions.exceptions import RegionHasShopsError
from apps.regions.models import Region


@transaction.atomic
def create_region(*, organisation: object, name: str, region_id: str) -> Region:
    return Region.objects.create(
        organisation=organisation,
        name=name,
        region_id=region_id,
    )


@transaction.atomic
def update_region(
    *,
    region: Region,
    name: str | None = None,
    region_id: str | None = None,
) -> Region:
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

**`apps/regions/selectors/__init__.py`** — Empty init.

**`apps/regions/selectors/regions.py`** — Single selector returning the org-filtered queryset ordered by `created_at` (the model's default `Meta.ordering`). No `select_related` needed since `RegionReadSerializer` only reads fields on the `Region` table itself:

```python
from __future__ import annotations

from django.db.models import QuerySet

from apps.regions.models import Region


def list_regions(*, organisation_id: int) -> QuerySet[Region]:
    """Return all regions for the organisation, ordered by created_at (model default)."""
    return Region.objects.filter(organisation_id=organisation_id)
```

**Test:** `pytest apps/regions/tests/test_services.py apps/regions/tests/test_selectors.py -x -q` (tests created in Plan 02; this task establishes the code under test)

**Done:** All six files exist. `RegionFactory.region_id` generates `RGN000`, `RGN001`, etc. (no hyphen). `delete_region` raises `RegionHasShopsError` when shops exist. `update_region` only saves changed fields.

---

### Task 7-01-02: Create serializers, ViewSet, template view, URLs, and Django template

**Requirement:** RGN-01, RGN-03, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02

**Files:**
- `apps/regions/serializers.py`
- `apps/regions/views.py`
- `apps/organisations/urls.py`
- `config/urls.py`
- `templates/regions/region_list.html`

**Action:**

**`apps/regions/serializers.py`** — Three serializers. `RegionReadSerializer` is the output shape (used by list, template view, and POST/PATCH response). `RegionCreateSerializer` validates name (2–60 chars) and region_id (`[A-Z0-9]`, 2–10 chars). `RegionUpdateSerializer` makes both fields optional (PATCH semantics):

```python
from __future__ import annotations

import re

from rest_framework import serializers

from apps.regions.models import Region

REGION_ID_RE = re.compile(r"^[A-Z0-9]{2,10}$")


class RegionReadSerializer(serializers.ModelSerializer[Region]):
    class Meta:
        model = Region
        fields = ["id", "name", "region_id", "created_at"]
        read_only_fields = ["id", "created_at"]


class RegionCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=60)
    region_id = serializers.CharField(min_length=2, max_length=10)

    def validate_region_id(self, value: str) -> str:
        if not REGION_ID_RE.match(value):
            raise serializers.ValidationError(
                "Region ID must be uppercase letters and digits only (2–10 characters)."
            )
        return value


class RegionUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    name = serializers.CharField(min_length=2, max_length=60, required=False)
    region_id = serializers.CharField(min_length=2, max_length=10, required=False)

    def validate_region_id(self, value: str) -> str:
        if not REGION_ID_RE.match(value):
            raise serializers.ValidationError(
                "Region ID must be uppercase letters and digits only (2–10 characters)."
            )
        return value
```

**`apps/regions/views.py`** — Template view + DRF ViewSet. The ViewSet uses `GenericViewSet` + explicit mixins (NOT `ModelViewSet` — do not expose `retrieve`). `permission_classes = [IsOrgAdmin, IsOrgScoped]` on the ViewSet. Override `destroy()` to catch `RegionHasShopsError` and return 409. Catch `IntegrityError` in `perform_create` and `perform_update` to return 400 with the duplicate-ID field error:

```python
from __future__ import annotations

from django.db import IntegrityError
from django.shortcuts import render
from rest_framework import mixins, serializers, status
from rest_framework.response import Response

from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet
from apps.regions.exceptions import RegionHasShopsError
from apps.regions.models import Region
from apps.regions.selectors.regions import list_regions
from apps.regions.serializers import (
    RegionCreateSerializer,
    RegionReadSerializer,
    RegionUpdateSerializer,
)
from apps.regions.services.regions import create_region, delete_region, update_region


@org_admin_required
def region_list(request):  # type: ignore[no-untyped-def]
    regions_qs = list_regions(organisation_id=request.user.organisation_id)
    regions_data = list(RegionReadSerializer(regions_qs, many=True).data)
    return render(
        request,
        "regions/region_list.html",
        {
            "regions_json": regions_data,
            "regions_count": len(regions_data),
        },
    )


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

    def get_serializer_class(self):  # type: ignore[override]
        if self.action == "create":
            return RegionCreateSerializer
        if self.action == "partial_update":
            return RegionUpdateSerializer
        return RegionReadSerializer

    def perform_create(self, serializer: RegionCreateSerializer) -> None:  # type: ignore[override]
        try:
            region = create_region(
                organisation=self.request.user.organisation,
                **serializer.validated_data,
            )
        except IntegrityError:
            raise serializers.ValidationError(
                {"region_id": ["This Region ID is already in use."]}
            )
        serializer.instance = region

    def perform_update(self, serializer: RegionUpdateSerializer) -> None:  # type: ignore[override]
        try:
            update_region(region=serializer.instance, **serializer.validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {"region_id": ["This Region ID is already in use."]}
            )

    def destroy(self, request, *args, **kwargs):  # type: ignore[override]
        region = self.get_object()
        try:
            delete_region(region=region)
        except RegionHasShopsError as exc:
            return Response({"shop_count": exc.shop_count}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

**`apps/organisations/urls.py`** — Replace the `org_stub_view` import and stub for `/admin/org/regions/` with the real `region_list` view imported from `apps.regions.views`. Keep URL name `org_regions` unchanged (sidebar template and dashboard CTA depend on it):

Find the line importing `org_stub_view` and the line:
```python
path("admin/org/regions/", org_stub_view, ..., name="org_regions"),
```
Replace ONLY the view function for that path — import `region_list` from `apps.regions.views` and swap it in. The `org_stub_view` import remains if other stubs (shops, team) still use it.

**`config/urls.py`** — Register `RegionViewSet` on the existing `router`. Add after the existing `router.register` line:
```python
from apps.regions.views import RegionViewSet
router.register(r"api/v1/regions", RegionViewSet, basename="region")
```

**`templates/regions/region_list.html`** — Create the template directory and file. The template extends `base_org.html`, outputs the page heading + yellow CTA button, always mounts `#region-modals-root`, and conditionally mounts `#region-table-root` when `regions_count > 0`. Serialize the initial regions data using Django's `json_script` filter:

```html
{% extends "base_org.html" %}
{% load static %}

{% block page_title %}Regions{% endblock %}

{% block content %}
<div class="flex items-center justify-between mb-6">
  <h1 class="text-[18px] font-semibold text-ink">Regions</h1>
  <button
    id="open-create-region"
    class="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
  >
    + Create Region
  </button>
</div>

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

**Test:** `pytest apps/regions/ -x -q` after commit (Plan 02 tests will also use these files)

**Done:**
- `RegionViewSet` responds: `GET /api/v1/regions/` → 200, `POST /api/v1/regions/` → 201, `PATCH /api/v1/regions/{id}/` → 200, `DELETE /api/v1/regions/{id}/` → 204 (or 409 with shops)
- `GET /admin/org/regions/` renders `regions/region_list.html` (not the stub)
- URL name `org_regions` still resolves correctly
- `RegionFactory` generates IDs like `RGN000` without hyphens

---

## Requirements Coverage

| Requirement | Task | Status |
|-------------|------|--------|
| RGN-01 | 7-01-02 (list endpoint + serializer) | pending |
| RGN-03 | 7-01-02 (create serializer validation) | pending |
| RGN-06 | 7-01-02 (IntegrityError → 400 field error) | pending |
| RGN-07 | 7-01-02 (201 on create) | pending |
| RGN-08 | 7-01-02 (update serializer, patch endpoint) | pending |
| RGN-09 | 7-01-02 (200 on update) | pending |
| RGN-10 | 7-01-01 (RegionHasShopsError) + 7-01-02 (409 response) | pending |
| RGN-11 | 7-01-01 (delete_region hard delete) + 7-01-02 (destroy override) | pending |
| XMOD-02 | 7-01-01 (shop guard in service) + 7-01-02 (409 in viewset) | pending |
