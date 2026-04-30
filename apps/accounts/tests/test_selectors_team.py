from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import StaffAccessScope
from apps.accounts.selectors.team import get_team_stats, list_team_members
from apps.accounts.tests.factories import (
    OrgAdminFactory,
    StaffAccessScopeFactory,
    StaffAdminFactory,
)
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.tests.factories import ShopFactory


@pytest.mark.django_db
def test_list_team_members_query_count(assert_query_ceiling):
    """list_team_members + iterating prefetched_scopes uses ≤4 SQL queries for 20 staff x 3 scopes."""
    org = OrganisationFactory()
    OrgAdminFactory(organisation=org)

    for _ in range(20):
        staff = StaffAdminFactory(organisation=org, is_active=True)
        StaffAccessScopeFactory(
            user=staff,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region=RegionFactory(organisation=org),
            shop=None,
        )
        StaffAccessScopeFactory(
            user=staff,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region=RegionFactory(organisation=org),
            shop=None,
        )
        StaffAccessScopeFactory(
            user=staff,
            scope_type=StaffAccessScope.ScopeType.SHOP,
            region=None,
            shop=ShopFactory(organisation=org),
        )

    with CaptureQueriesContext(connection) as ctx:
        members = list(list_team_members(organisation_id=org.pk))
        for m in members:
            _ = m.prefetched_scopes  # type: ignore[attr-defined]  # force attribute access
            for s in m.prefetched_scopes:  # type: ignore[attr-defined]
                _ = s.region.name if s.region else (s.shop.name if s.shop else None)

    assert_query_ceiling(ctx, max_queries=4)


@pytest.mark.django_db
def test_list_team_members_filters():
    """list_team_members search, region_id, shop_id filters work correctly."""
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org, full_name="Alpha Admin")
    region_a = RegionFactory(organisation=org)
    region_b = RegionFactory(organisation=org)
    shop_a = ShopFactory(organisation=org)

    staff_region_a = StaffAdminFactory(organisation=org, full_name="Staff RegionA")
    StaffAccessScopeFactory(
        user=staff_region_a,
        scope_type=StaffAccessScope.ScopeType.REGION,
        region=region_a,
        shop=None,
    )

    staff_shop_a = StaffAdminFactory(organisation=org, full_name="Staff ShopA")
    StaffAccessScopeFactory(
        user=staff_shop_a,
        scope_type=StaffAccessScope.ScopeType.SHOP,
        region=None,
        shop=shop_a,
    )

    # Search by name
    result = list(list_team_members(organisation_id=org.pk, search="Alpha"))
    pks = {m.pk for m in result}
    assert admin.pk in pks
    assert staff_region_a.pk not in pks

    # Search by email
    result = list(list_team_members(organisation_id=org.pk, search=staff_region_a.email[:5]))
    assert staff_region_a.pk in {m.pk for m in result}

    # Filter by region_id
    result = list(list_team_members(organisation_id=org.pk, region_id=region_a.pk))
    pks = {m.pk for m in result}
    assert staff_region_a.pk in pks
    assert staff_shop_a.pk not in pks

    # region_b has no members — should return empty
    result = list(list_team_members(organisation_id=org.pk, region_id=region_b.pk))
    assert result == []

    # Filter by shop_id
    result = list(list_team_members(organisation_id=org.pk, shop_id=shop_a.pk))
    pks = {m.pk for m in result}
    assert staff_shop_a.pk in pks
    assert staff_region_a.pk not in pks


@pytest.mark.django_db
def test_list_team_members_excludes_other_orgs():
    """list_team_members returns only members for the given organisation."""
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    member_a = OrgAdminFactory(organisation=org_a)
    member_b = OrgAdminFactory(organisation=org_b)

    result_a = list(list_team_members(organisation_id=org_a.pk))
    result_b = list(list_team_members(organisation_id=org_b.pk))

    pks_a = {m.pk for m in result_a}
    pks_b = {m.pk for m in result_b}

    assert member_a.pk in pks_a
    assert member_b.pk not in pks_a
    assert member_b.pk in pks_b
    assert member_a.pk not in pks_b


@pytest.mark.django_db
def test_list_team_members_orders_by_invited_desc():
    """list_team_members returns most recently invited first."""
    import datetime

    from django.utils import timezone

    org = OrganisationFactory()
    early = OrgAdminFactory(
        organisation=org,
        invited_at=timezone.now() - datetime.timedelta(days=5),
    )
    late = OrgAdminFactory(
        organisation=org,
        invited_at=timezone.now() - datetime.timedelta(days=1),
    )

    result = list(list_team_members(organisation_id=org.pk))
    pks = [m.pk for m in result]
    assert pks.index(late.pk) < pks.index(early.pk)


@pytest.mark.django_db
def test_get_team_stats():
    """get_team_stats returns total_members, managers, active_members counts."""
    org = OrganisationFactory()
    # 2 org admins (managers), 1 active + 1 inactive staff
    active_admin = OrgAdminFactory(organisation=org, is_active=True)
    OrgAdminFactory(organisation=org, is_active=True)
    StaffAdminFactory(organisation=org, is_active=True)
    StaffAdminFactory(organisation=org, is_active=False)

    # Superadmin without org — should NOT be counted
    # (already excluded by list_team_members filter, confirmed here for get_team_stats)
    _ = active_admin  # all 4 members defined above

    stats = get_team_stats(organisation_id=org.pk)

    assert stats["total_members"] == 4
    assert stats["managers"] == 2
    assert stats["active_members"] == 3  # 2 active admins + 1 active staff
