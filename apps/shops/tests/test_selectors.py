from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.selectors.shops import (
    get_accessible_shop_for_credits,
    get_allocation_status,
    get_has_regions,
    list_shops,
)
from apps.shops.serializers import ShopReadSerializer
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


@pytest.mark.django_db
class TestListShopsStaffScopeAndCredits:
    def test_list_shops_returns_only_in_scope_shops_with_virtual_credits_when_staff(self) -> None:
        org = OrganisationFactory(monthly_credit_allocation=40)
        shop_a = ShopFactory(organisation=org)
        ShopFactory(organisation=org)
        staff = StaffAdminFactory(organisation=org)
        StaffAccessScope.objects.create(
            user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop_a
        )
        balances_before = ShopCreditBalance.objects.count()

        rows = list(list_shops(organisation_id=org.pk, user=staff, with_credits=True))

        assert [s.pk for s in rows] == [shop_a.pk]
        assert rows[0].credit_remaining == 40
        assert rows[0].credit_materialized is False
        assert ShopCreditBalance.objects.count() == balances_before
        assert CreditTransaction.objects.count() == 0


def _staff(org, *, shops=(), regions=()):  # type: ignore[no-untyped-def]
    staff = StaffAdminFactory(organisation=org)
    for shop in shops:
        StaffAccessScope.objects.create(
            user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop
        )
    for region in regions:
        StaffAccessScope.objects.create(
            user=staff, scope_type=StaffAccessScope.ScopeType.REGION, region=region
        )
    return staff


@pytest.mark.django_db
class TestListShopsScopeMatrix:
    def _ids(self, org, staff):  # type: ignore[no-untyped-def]
        return {s.pk for s in list_shops(organisation_id=org.pk, user=staff)}

    def test_returns_union_when_staff_has_shop_and_region_scope(self) -> None:
        org = OrganisationFactory()
        region = RegionFactory(organisation=org)
        shop_a = ShopFactory(organisation=org)
        shop_c = ShopFactory(organisation=org, region=region)
        shop_d = ShopFactory(organisation=org, region=region)
        ShopFactory(organisation=org)
        assert self._ids(org, _staff(org, shops=[shop_a])) == {shop_a.pk}
        assert self._ids(org, _staff(org, regions=[region])) == {shop_c.pk, shop_d.pk}
        both = _staff(org, shops=[shop_a], regions=[region])
        assert self._ids(org, both) == {shop_a.pk, shop_c.pk, shop_d.pk}

    def test_returns_empty_list_when_staff_has_no_scope_rows(self) -> None:
        org = OrganisationFactory()
        ShopFactory.create_batch(3, organisation=org)
        assert list(list_shops(organisation_id=org.pk, user=_staff(org))) == []

    def test_does_not_leak_foreign_org_shops_when_region_scope_is_foreign(self) -> None:
        org = OrganisationFactory()
        other = OrganisationFactory()
        foreign_region = RegionFactory(organisation=other)
        ShopFactory.create_batch(2, organisation=other, region=foreign_region)
        own = ShopFactory(organisation=org)
        staff = _staff(org, shops=[own], regions=[foreign_region])
        assert self._ids(org, staff) == {own.pk}

    def test_org_admin_sees_every_own_shop_and_nothing_foreign(self) -> None:
        org = OrganisationFactory()
        active = ShopFactory(organisation=org, is_active=True)
        inactive = ShopFactory(organisation=org, is_active=False)
        ShopFactory(organisation=OrganisationFactory())
        admin = OrgAdminFactory(organisation=org)
        assert self._ids(org, admin) == {active.pk, inactive.pk}


@pytest.mark.django_db
class TestListShopsCredits:
    def test_rows_have_no_credit_attributes_and_serializer_emits_null_without_credits(
        self,
    ) -> None:
        org = OrganisationFactory()
        ShopFactory(organisation=org)
        row = next(iter(list_shops(organisation_id=org.pk)))
        assert not hasattr(row, "credit_remaining")
        data = ShopReadSerializer(row).data
        for key in ("credits_allocated", "credits_bonus", "credits_remaining", "credits_total"):
            assert data[key] is None

    def test_filters_return_same_rows_when_credits_enabled(self) -> None:
        org = OrganisationFactory()
        region = RegionFactory(organisation=org)
        ShopFactory(organisation=org, name="Acme Cafe", region=region, is_active=True)
        ShopFactory(organisation=org, name="Beta Bistro", is_active=False)
        ShopFactory(organisation=org, name="Acme Two", is_active=False)
        for kwargs in (
            {"search": "Acme"},
            {"status": "active"},
            {"status": "inactive"},
            {"region_id": region.pk},
            {},
        ):
            plain = [s.pk for s in list_shops(organisation_id=org.pk, **kwargs)]
            with_credits = [
                s.pk for s in list_shops(organisation_id=org.pk, with_credits=True, **kwargs)
            ]
            assert plain == with_credits

    def test_uses_materialised_current_month_row_and_ignores_previous_month(self) -> None:
        org = OrganisationFactory(monthly_credit_allocation=40)
        shop = ShopFactory(organisation=org)
        other = ShopFactory(organisation=org)
        ShopCreditBalanceFactory(
            shop=shop, allocated_credits=100, bonus_credits=20, consumed_credits=30
        )
        # previous-month row on the other shop is ignored -> virtual current month
        ShopCreditBalanceFactory(
            shop=other,
            period_year=2000,
            period_month=1,
            allocated_credits=7,
            bonus_credits=3,
            consumed_credits=1,
        )
        rows = {s.pk: s for s in list_shops(organisation_id=org.pk, with_credits=True)}
        data = ShopReadSerializer(rows[shop.pk]).data
        assert data["credits_remaining"] == 90
        assert data["credits_total"] == 120
        assert data["credits_allocated"] == 100
        assert data["credits_bonus"] == 20
        virtual = ShopReadSerializer(rows[other.pk]).data
        assert (virtual["credits_remaining"], virtual["credits_total"]) == (40, 40)

    @pytest.mark.parametrize("n", [1, 20])
    def test_issues_one_query_when_credits_enabled_for_org_admin(self, n: int) -> None:
        org = OrganisationFactory()
        region = RegionFactory(organisation=org)
        ShopFactory.create_batch(n, organisation=org, region=region)
        admin = OrgAdminFactory(organisation=org)
        with CaptureQueriesContext(connection) as ctx:
            rows = list(list_shops(organisation_id=org.pk, user=admin, with_credits=True))
            for r in rows:
                _ = r.region.name, r.credit_remaining
        assert len(rows) == n
        assert len(ctx.captured_queries) == 1


@pytest.mark.django_db
class TestGetAccessibleShopForCredits:
    def test_returns_shop_for_org_admin_of_active_and_inactive_shops(self) -> None:
        org = OrganisationFactory()
        active = ShopFactory(organisation=org, is_active=True)
        inactive = ShopFactory(organisation=org, is_active=False)
        admin = OrgAdminFactory(organisation=org)
        assert get_accessible_shop_for_credits(user=admin, shop_id=active.pk) == active
        assert get_accessible_shop_for_credits(user=admin, shop_id=inactive.pk) == inactive

    def test_applies_staff_scope_when_user_is_staff(self) -> None:
        org = OrganisationFactory()
        in_scope = ShopFactory(organisation=org)
        out_scope = ShopFactory(organisation=org)
        staff = _staff(org, shops=[in_scope])
        assert get_accessible_shop_for_credits(user=staff, shop_id=in_scope.pk) == in_scope
        assert get_accessible_shop_for_credits(user=staff, shop_id=out_scope.pk) is None

    def test_returns_none_when_user_is_cross_org_superadmin_or_shop_unknown(self) -> None:
        from apps.accounts.tests.factories import UserFactory

        org = OrganisationFactory()
        shop = ShopFactory(organisation=org)
        other_admin = OrgAdminFactory(organisation=OrganisationFactory())
        superadmin = UserFactory()
        own_admin = OrgAdminFactory(organisation=org)
        assert get_accessible_shop_for_credits(user=other_admin, shop_id=shop.pk) is None
        assert get_accessible_shop_for_credits(user=superadmin, shop_id=shop.pk) is None
        assert get_accessible_shop_for_credits(user=own_admin, shop_id=999999) is None
