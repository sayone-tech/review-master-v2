from __future__ import annotations

import contextlib

import pytest
from django.db import IntegrityError

from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.exceptions import RegionHasShopsError
from apps.regions.models import Region
from apps.regions.services.regions import create_region, delete_region, update_region
from apps.regions.tests.factories import RegionFactory

# ShopFactory is available from Phase 6 (shops app already created).
# Import it directly — it exists at this point.
from apps.shops.tests.factories import ShopFactory


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
        # @transaction.atomic issues a SAVEPOINT + RELEASE SAVEPOINT (2 queries) inside the
        # test's outer transaction — but no UPDATE query is issued. Assert <= 2 to confirm
        # no unnecessary writes.
        with django_assert_num_queries(2):
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
        ShopFactory(region=region, organisation=region.organisation)
        ShopFactory(region=region, organisation=region.organisation)
        with pytest.raises(RegionHasShopsError) as exc_info:
            delete_region(region=region)
        assert exc_info.value.shop_count == 2

    def test_region_remains_in_db_when_delete_blocked(self):
        region = RegionFactory()
        ShopFactory(region=region, organisation=region.organisation)
        with contextlib.suppress(RegionHasShopsError):
            delete_region(region=region)
        assert Region.objects.filter(pk=region.pk).exists()
