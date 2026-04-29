from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.selectors.shops import (
    get_allocation_status,
    get_has_regions,
    list_shops,
)
from apps.shops.tests.factories import ShopFactory


@pytest.mark.django_db
class TestListShopsScoping:
    def test_returns_only_for_organisation(self) -> None:
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        ShopFactory.create_batch(3, organisation=org_a)
        ShopFactory.create_batch(2, organisation=org_b)
        assert list_shops(organisation_id=org_a.pk).count() == 3

    def test_returns_in_creation_order_desc(self) -> None:
        org = OrganisationFactory()
        s1 = ShopFactory(organisation=org)
        s2 = ShopFactory(organisation=org)
        s3 = ShopFactory(organisation=org)
        result = list(list_shops(organisation_id=org.pk))
        assert [s.pk for s in result] == [s3.pk, s2.pk, s1.pk]


@pytest.mark.django_db
class TestListShopsFilters:
    def test_search_matches_name(self) -> None:
        org = OrganisationFactory()
        match = ShopFactory(organisation=org, name="Acme Cafe")
        ShopFactory(organisation=org, name="Beta Bistro")
        result = list(list_shops(organisation_id=org.pk, search="Acme"))
        assert [s.pk for s in result] == [match.pk]

    def test_search_matches_street_address(self) -> None:
        org = OrganisationFactory()
        match = ShopFactory(organisation=org, street_address="123 Main St")
        ShopFactory(organisation=org, street_address="9 Elm Rd")
        result = list(list_shops(organisation_id=org.pk, search="Main St"))
        assert [s.pk for s in result] == [match.pk]

    def test_search_matches_city(self) -> None:
        org = OrganisationFactory()
        match = ShopFactory(organisation=org, city="London")
        ShopFactory(organisation=org, city="Berlin")
        result = list(list_shops(organisation_id=org.pk, search="London"))
        assert [s.pk for s in result] == [match.pk]

    def test_status_active_only(self) -> None:
        org = OrganisationFactory()
        active = ShopFactory(organisation=org, is_active=True)
        ShopFactory(organisation=org, is_active=False)
        result = list(list_shops(organisation_id=org.pk, status="active"))
        assert [s.pk for s in result] == [active.pk]

    def test_status_inactive_only(self) -> None:
        org = OrganisationFactory()
        ShopFactory(organisation=org, is_active=True)
        inactive = ShopFactory(organisation=org, is_active=False)
        result = list(list_shops(organisation_id=org.pk, status="inactive"))
        assert [s.pk for s in result] == [inactive.pk]

    def test_region_filter(self) -> None:
        org = OrganisationFactory()
        region_a = RegionFactory(organisation=org)
        region_b = RegionFactory(organisation=org)
        match = ShopFactory(organisation=org, region=region_a)
        ShopFactory(organisation=org, region=region_b)
        result = list(list_shops(organisation_id=org.pk, region_id=region_a.pk))
        assert [s.pk for s in result] == [match.pk]

    def test_active_only_flag(self) -> None:
        org = OrganisationFactory()
        active = ShopFactory(organisation=org, is_active=True)
        ShopFactory(organisation=org, is_active=False)
        result = list(list_shops(organisation_id=org.pk, active_only=True))
        assert [s.pk for s in result] == [active.pk]


@pytest.mark.django_db
class TestListShopsQueryCount:
    def test_query_count_with_25_shops(self, assert_query_ceiling: object) -> None:
        from unittest.mock import MagicMock

        assert callable(assert_query_ceiling) or isinstance(assert_query_ceiling, MagicMock)
        org = OrganisationFactory()
        region = RegionFactory(organisation=org)
        ShopFactory.create_batch(25, organisation=org, region=region)
        with CaptureQueriesContext(connection) as ctx:
            shops = list(list_shops(organisation_id=org.pk))
            for s in shops:
                _ = s.region.name  # access select_related FK (no extra query)
        assert callable(assert_query_ceiling)
        assert_query_ceiling(ctx, max_queries=3)  # type: ignore[operator]


@pytest.mark.django_db
class TestGetHasRegions:
    def test_true_when_regions_exist(self) -> None:
        org = OrganisationFactory()
        RegionFactory(organisation=org)
        assert get_has_regions(organisation_id=org.pk) is True

    def test_false_for_org_with_no_regions(self) -> None:
        org = OrganisationFactory()
        assert get_has_regions(organisation_id=org.pk) is False


@pytest.mark.django_db
class TestGetAllocationStatus:
    def test_under_limit(self) -> None:
        org = OrganisationFactory(number_of_stores=5)
        ShopFactory.create_batch(2, organisation=org)
        result = get_allocation_status(organisation=org)
        assert result == {"current": 2, "max": 5, "at_limit": False}

    def test_at_limit(self) -> None:
        org = OrganisationFactory(number_of_stores=2)
        ShopFactory.create_batch(2, organisation=org)
        result = get_allocation_status(organisation=org)
        assert result["at_limit"] is True

    def test_over_limit_marks_at_limit(self) -> None:
        org = OrganisationFactory(number_of_stores=2)
        ShopFactory.create_batch(3, organisation=org)
        result = get_allocation_status(organisation=org)
        assert result["at_limit"] is True
