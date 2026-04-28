from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
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
        org, _admin, client = org_and_admin
        r1 = RegionFactory(organisation=org)
        r2 = RegionFactory(organisation=org)
        resp = client.get("/api/v1/regions/")
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.data["results"]]
        assert r1.pk in ids
        assert r2.pk in ids

    def test_list_returns_creation_order(self, org_and_admin):
        org, _admin, client = org_and_admin
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
    admin_a = two_orgs_two_admins["admin_a"]
    org_b = two_orgs_two_admins["org_b"]

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
# Template view (RGN-02 — empty state and with regions)
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
