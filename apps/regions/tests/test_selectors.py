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
