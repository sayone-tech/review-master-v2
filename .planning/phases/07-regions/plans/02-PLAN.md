---
plan: 2
phase: 7
slug: regions
wave: 2
depends_on: ["01"]
status: pending
requirements: [RGN-01, RGN-02, RGN-03, RGN-04, RGN-05, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02]
---

# Plan 2 — API Tests: Services, Selectors, ViewSet, Query Ceiling, Cross-Tenant

## Goal

Write the full pytest test suite for the Regions backend — service unit tests, selector unit tests, ViewSet API tests (all RGN requirements), query-count ceiling assertion, and cross-tenant isolation test.

## Wave 0 Dependencies

All files created by Plan 01 must exist before any import in these test files will compile:

- `apps/regions/exceptions.py` (`RegionHasShopsError`)
- `apps/regions/services/regions.py` (`create_region`, `update_region`, `delete_region`)
- `apps/regions/selectors/regions.py` (`list_regions`)
- `apps/regions/serializers.py` (`RegionReadSerializer`, etc.)
- `apps/regions/views.py` (`RegionViewSet`, `region_list`)
- `apps/regions/tests/factories.py` (fixed `region_id` — no hyphens)

Do not begin this plan until Plan 01 is committed.

---

## Tasks

### Task 7-02-01: Write service and selector unit tests

**Requirement:** RGN-03, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02

**Files:**
- `apps/regions/tests/test_services.py`
- `apps/regions/tests/test_selectors.py`

**Action:**

**`apps/regions/tests/test_services.py`** — Tests for all three service functions. Import `RegionFactory` and `OrganisationFactory` explicitly (no conftest auto-discovery across app boundaries):

```python
from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.exceptions import RegionHasShopsError
from apps.regions.models import Region
from apps.regions.services.regions import create_region, delete_region, update_region
from apps.regions.tests.factories import RegionFactory
from apps.shops.tests.factories import ShopFactory  # needed for delete guard test


@pytest.mark.django_db
class TestCreateRegion:
    def test_creates_region_with_correct_fields(self):
        org = OrganisationFactory()
        region = create_region(organisation=org, name="North West", region_id="NW001")
        assert region.pk is not None
        assert region.organisation == org
        assert region.name == "North West"
        assert region.region_id == "NW001"

    def test_duplicate_region_id_raises_integrity_error(self):
        org = OrganisationFactory()
        create_region(organisation=org, name="North West", region_id="NW001")
        with pytest.raises(IntegrityError):
            create_region(organisation=org, name="Another", region_id="NW001")

    def test_same_region_id_allowed_across_different_organisations(self):
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        r1 = create_region(organisation=org_a, name="Region A", region_id="NW001")
        r2 = create_region(organisation=org_b, name="Region B", region_id="NW001")
        assert r1.pk != r2.pk


@pytest.mark.django_db
class TestUpdateRegion:
    def test_updates_name_only(self):
        region = RegionFactory(name="Old Name")
        updated = update_region(region=region, name="New Name")
        region.refresh_from_db()
        assert region.name == "New Name"
        assert updated is region

    def test_updates_region_id_only(self):
        region = RegionFactory(region_id="OLD001")
        update_region(region=region, region_id="NEW001")
        region.refresh_from_db()
        assert region.region_id == "NEW001"

    def test_no_save_when_no_changes(self, django_assert_num_queries):
        region = RegionFactory()
        with django_assert_num_queries(0):
            update_region(region=region)

    def test_duplicate_region_id_raises_integrity_error(self):
        org = OrganisationFactory()
        RegionFactory(organisation=org, region_id="NW001")
        region2 = RegionFactory(organisation=org, region_id="SE002")
        with pytest.raises(IntegrityError):
            update_region(region=region2, region_id="NW001")


@pytest.mark.django_db
class TestDeleteRegion:
    def test_deletes_region_with_no_shops(self):
        region = RegionFactory()
        pk = region.pk
        delete_region(region=region)
        assert not Region.objects.filter(pk=pk).exists()

    def test_raises_region_has_shops_error_when_shops_assigned(self):
        region = RegionFactory()
        ShopFactory(region=region)
        ShopFactory(region=region)
        with pytest.raises(RegionHasShopsError) as exc_info:
            delete_region(region=region)
        assert exc_info.value.shop_count == 2

    def test_region_remains_in_db_when_delete_blocked(self):
        region = RegionFactory()
        ShopFactory(region=region)
        try:
            delete_region(region=region)
        except RegionHasShopsError:
            pass
        assert Region.objects.filter(pk=region.pk).exists()
```

Note: `ShopFactory` will exist after Phase 8; for Phase 7, the delete-guard tests that require a Shop instance can be written with `@pytest.mark.skip(reason="ShopFactory available in Phase 8")` OR the Shop can be created via `Region.objects.filter(...).update(...)` if the Shop model already has its migration in place from Phase 6. Check whether `apps/shops/tests/factories.py` exists: if it does, import it; if not, skip those specific tests with a comment.

Adjust the test file to use `pytest.importorskip` or a conditional skip at the top for `ShopFactory`. The important thing is that the file compiles cleanly regardless.

**`apps/regions/tests/test_selectors.py`**:

```python
from __future__ import annotations

import pytest

from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.selectors.regions import list_regions
from apps.regions.tests.factories import RegionFactory


@pytest.mark.django_db
class TestListRegions:
    def test_returns_only_regions_for_organisation(self):
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        RegionFactory.create_batch(3, organisation=org_a)
        RegionFactory.create_batch(2, organisation=org_b)
        result = list(list_regions(organisation_id=org_a.pk))
        assert len(result) == 3
        assert all(r.organisation_id == org_a.pk for r in result)

    def test_returns_regions_in_creation_order(self):
        org = OrganisationFactory()
        r1 = RegionFactory(organisation=org, name="First")
        r2 = RegionFactory(organisation=org, name="Second")
        r3 = RegionFactory(organisation=org, name="Third")
        result = list(list_regions(organisation_id=org.pk))
        assert [r.pk for r in result] == [r1.pk, r2.pk, r3.pk]

    def test_returns_empty_queryset_for_org_with_no_regions(self):
        org = OrganisationFactory()
        assert list_regions(organisation_id=org.pk).count() == 0

    def test_returns_all_regions_including_inactive(self):
        org = OrganisationFactory()
        RegionFactory(organisation=org, is_active=True)
        RegionFactory(organisation=org, is_active=False)
        assert list_regions(organisation_id=org.pk).count() == 2
```

**Test:** `pytest apps/regions/tests/test_services.py apps/regions/tests/test_selectors.py -x -q`

**Done:** All service and selector tests pass. `delete_region` guard, `update_region` no-op, `list_regions` cross-org isolation, and creation-order tests are all green.

---

### Task 7-02-02: Write ViewSet API tests (all RGN endpoints + query ceiling + cross-tenant)

**Requirement:** RGN-01, RGN-02, RGN-06, RGN-07, RGN-08, RGN-09, RGN-10, RGN-11, XMOD-02, XMOD-05

**Files:**
- `apps/regions/tests/test_views.py`

**Action:**

Create `apps/regions/tests/test_views.py`. Import fixtures explicitly — `assert_query_ceiling` and `two_orgs_two_admins` are NOT auto-discovered outside `apps/common/tests/`. Use `pytest.fixture` from `apps.common.tests.fixtures` directly:

```python
from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.common.tests.fixtures import assert_query_ceiling, two_orgs_two_admins  # noqa: F401 — pytest fixtures
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.models import Region
from apps.regions.tests.factories import RegionFactory


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org_and_admin(db):
    org = OrganisationFactory()
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=admin)
    return org, admin, client


# ---------------------------------------------------------------------------
# List (RGN-01)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegionsList:
    def test_regions_api_list(self, org_and_admin):
        org, admin, client = org_and_admin
        r1 = RegionFactory(organisation=org)
        r2 = RegionFactory(organisation=org)
        resp = client.get("/api/v1/regions/")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.data["results"]]
        assert r1.pk in ids
        assert r2.pk in ids

    def test_list_returns_creation_order(self, org_and_admin):
        org, admin, client = org_and_admin
        r1 = RegionFactory(organisation=org)
        r2 = RegionFactory(organisation=org)
        resp = client.get("/api/v1/regions/")
        assert resp.status_code == 200
        result_ids = [row["id"] for row in resp.data["results"]]
        assert result_ids.index(r1.pk) < result_ids.index(r2.pk)


# ---------------------------------------------------------------------------
# Create validation (RGN-03)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegionsApiCreateValidation:
    def test_regions_api_create_validation_name_too_short(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/regions/", {"name": "A", "region_id": "NW001"})
        assert resp.status_code == 400
        assert "name" in resp.data

    def test_regions_api_create_validation_name_too_long(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/regions/", {"name": "x" * 61, "region_id": "NW001"})
        assert resp.status_code == 400

    def test_regions_api_create_validation_region_id_has_hyphen(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/regions/", {"name": "North West", "region_id": "NW-001"})
        assert resp.status_code == 400
        assert "region_id" in resp.data

    def test_regions_api_create_validation_region_id_lowercase(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/regions/", {"name": "North West", "region_id": "nw001"})
        assert resp.status_code == 400

    def test_regions_api_create_validation_region_id_too_short(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/regions/", {"name": "North West", "region_id": "A"})
        assert resp.status_code == 400

    def test_regions_api_create_validation_region_id_too_long(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/regions/", {"name": "North West", "region_id": "ABCDE123456"})
        assert resp.status_code == 400

    def test_regions_api_create_returns_201(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post("/api/v1/regions/", {"name": "North West", "region_id": "NW001"})
        assert resp.status_code == 201
        assert resp.data["name"] == "North West"
        assert resp.data["region_id"] == "NW001"


# ---------------------------------------------------------------------------
# Duplicate Region ID (RGN-06)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegionsApiCreateDuplicateId:
    def test_regions_api_create_duplicate_id(self, org_and_admin):
        org, _, client = org_and_admin
        RegionFactory(organisation=org, region_id="NW001")
        resp = client.post("/api/v1/regions/", {"name": "Another", "region_id": "NW001"})
        assert resp.status_code == 400
        assert "region_id" in resp.data
        assert resp.data["region_id"][0] == "This Region ID is already in use."


# ---------------------------------------------------------------------------
# Edit (RGN-08 / RGN-09)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegionsApiPatch:
    def test_regions_api_patch(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org, name="Old Name", region_id="OLD001")
        resp = client.patch(f"/api/v1/regions/{region.pk}/", {"name": "New Name"})
        assert resp.status_code == 200
        region.refresh_from_db()
        assert region.name == "New Name"
        assert region.region_id == "OLD001"  # unchanged

    def test_regions_api_patch_returns_200(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org, region_id="AA001")
        resp = client.patch(f"/api/v1/regions/{region.pk}/", {"region_id": "BB002"})
        assert resp.status_code == 200
        region.refresh_from_db()
        assert region.region_id == "BB002"

    def test_patch_duplicate_region_id_returns_400(self, org_and_admin):
        org, _, client = org_and_admin
        RegionFactory(organisation=org, region_id="NW001")
        region2 = RegionFactory(organisation=org, region_id="SE002")
        resp = client.patch(f"/api/v1/regions/{region2.pk}/", {"region_id": "NW001"})
        assert resp.status_code == 400
        assert "region_id" in resp.data


# ---------------------------------------------------------------------------
# Delete guard (RGN-10 / RGN-11 / XMOD-02)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegionsApiDelete:
    def test_regions_api_delete_no_shops(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        resp = client.delete(f"/api/v1/regions/{region.pk}/")
        assert resp.status_code == 204
        assert not Region.objects.filter(pk=region.pk).exists()

    def test_regions_api_delete_blocked(self, org_and_admin):
        """RGN-10 / XMOD-02: delete with shops returns 409 with shop_count."""
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        # Create shops by direct ORM (ShopFactory available in Phase 8).
        # Use the Shop model directly if available; skip otherwise.
        try:
            from apps.shops.tests.factories import ShopFactory
            ShopFactory(region=region, organisation=org)
            ShopFactory(region=region, organisation=org)
            shop_count = 2
        except ImportError:
            pytest.skip("ShopFactory not yet available (Phase 8)")
        resp = client.delete(f"/api/v1/regions/{region.pk}/")
        assert resp.status_code == 409
        assert resp.data["shop_count"] == shop_count
        assert Region.objects.filter(pk=region.pk).exists()


# ---------------------------------------------------------------------------
# Query count ceiling (XMOD-05 / CI requirement)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_regions_list_query_count_ceiling(assert_query_ceiling, org_and_admin):
    """List endpoint must not exceed 5 queries regardless of result size."""
    org, _, client = org_and_admin
    RegionFactory.create_batch(20, organisation=org)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/api/v1/regions/")
    assert resp.status_code == 200
    assert_query_ceiling(ctx, max_queries=5)


# ---------------------------------------------------------------------------
# Cross-tenant isolation (IDOR guard)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_regions_cross_tenant_isolation(two_orgs_two_admins):
    """Org A admin cannot read or mutate Org B regions."""
    org_a, admin_a, org_b, admin_b = two_orgs_two_admins

    region_b = RegionFactory(organisation=org_b, region_id="RB001")

    client_a = APIClient()
    client_a.force_authenticate(user=admin_a)

    # Cannot list Org B regions
    resp = client_a.get("/api/v1/regions/")
    assert resp.status_code == 200
    result_ids = [row["id"] for row in resp.data.get("results", resp.data)]
    assert region_b.pk not in result_ids

    # Cannot mutate Org B region
    resp = client_a.patch(f"/api/v1/regions/{region_b.pk}/", {"name": "Hacked"})
    assert resp.status_code in (403, 404)

    resp = client_a.delete(f"/api/v1/regions/{region_b.pk}/")
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Template view (RGN-02 — empty state)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_region_list_template_empty_state(client, db):
    org = OrganisationFactory()
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    client.force_login(admin)
    resp = client.get("/admin/org/regions/")
    assert resp.status_code == 200
    assert b"region-modals-root" in resp.content
    assert b"region-table-root" not in resp.content  # no regions exist


@pytest.mark.django_db
def test_region_list_template_with_regions(client, db):
    org = OrganisationFactory()
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    RegionFactory.create_batch(3, organisation=org)
    client.force_login(admin)
    resp = client.get("/admin/org/regions/")
    assert resp.status_code == 200
    assert b"region-table-root" in resp.content
    assert b"region-data" in resp.content  # json_script tag present
```

**Test:** `pytest apps/regions/tests/test_views.py -x -q`

After all tests pass, run the full suite to confirm ≥85% coverage on the regions app:

`pytest apps/regions/ -x -q && pytest --cov=apps/regions --cov-fail-under=85`

**Done:**
- All `test_views.py` tests pass (list, create validation, duplicate ID, patch, delete guard, query ceiling, cross-tenant, template view empty state)
- `assert_query_ceiling(ctx, max_queries=5)` passes with 20 regions
- Cross-tenant test confirms Org A cannot read or mutate Org B regions
- Coverage on `apps/regions/` is ≥85%

---

## Requirements Coverage

| Requirement | Task | Status |
|-------------|------|--------|
| RGN-01 | 7-02-02 (list endpoint test, creation-order test) | pending |
| RGN-02 | 7-02-02 (template empty state test) | pending |
| RGN-03 | 7-02-02 (create validation tests) | pending |
| RGN-04 | Tested in Plan 03 (client-side logic) | pending |
| RGN-05 | Tested in Plan 03 (client-side logic) | pending |
| RGN-06 | 7-02-01 (service duplicate test) + 7-02-02 (API duplicate test) | pending |
| RGN-07 | 7-02-02 (201 create test) | pending |
| RGN-08 | 7-02-01 (service update test) + 7-02-02 (patch test) | pending |
| RGN-09 | 7-02-02 (patch 200 test) | pending |
| RGN-10 | 7-02-01 (RegionHasShopsError test) + 7-02-02 (409 delete blocked test) | pending |
| RGN-11 | 7-02-01 (delete service test) + 7-02-02 (delete 204 test) | pending |
| XMOD-02 | 7-02-02 (409 response shape test) | pending |
