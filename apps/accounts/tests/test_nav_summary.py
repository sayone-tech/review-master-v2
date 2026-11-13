"""Nav summary: sidebar badge counts + AI-credits meter (selector + endpoint)."""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope
from apps.accounts.selectors.nav_summary import NavSummary, get_nav_summary
from apps.accounts.tests.factories import (
    OrgAdminFactory,
    StaffAccessScopeFactory,
    StaffAdminFactory,
    UserFactory,
)
from apps.action_items.models import ActionItem
from apps.action_items.tests.factories import ActionItemFactory
from apps.credits.selectors.balances import CreditTotals
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def _staff(org, *, shop=None, region=None):
    user = StaffAdminFactory(organisation=org)
    if shop is not None:
        StaffAccessScopeFactory(
            user=user, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop, region=None
        )
    if region is not None:
        StaffAccessScopeFactory(
            user=user, scope_type=StaffAccessScope.ScopeType.REGION, region=region, shop=None
        )
    return user


def test_org_admin_counts_unreplied_reviews_of_active_shops_only():
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    active = ShopFactory(organisation=org)
    inactive = ShopFactory(organisation=org, is_active=False)
    ReviewFactory.create_batch(2, organisation=org, shop=active)
    ReviewFactory(organisation=org, shop=active, is_replied=True)
    ReviewFactory.create_batch(3, organisation=org, shop=inactive)

    assert get_nav_summary(user=admin).reviews_awaiting_reply == 2


def test_org_admin_open_action_items_include_brand_items_and_exclude_done_and_duplicates():
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    shop = ShopFactory(organisation=org)
    canonical = ActionItemFactory(organisation=org, shop=shop, status=ActionItem.Status.COMPLETE)
    ActionItemFactory(organisation=org, shop=shop, status=ActionItem.Status.TODO)
    ActionItemFactory(
        organisation=org,
        shop=None,
        scope=ActionItem.Scope.BRAND,
        status=ActionItem.Status.IN_PROGRESS,
    )
    ActionItemFactory(organisation=org, shop=shop, status=ActionItem.Status.COMPLETE)
    ActionItemFactory(organisation=org, shop=shop, status=ActionItem.Status.WONT_DO)
    ActionItemFactory(
        organisation=org, shop=shop, status=ActionItem.Status.TODO, canonical=canonical
    )

    assert get_nav_summary(user=admin).open_action_items == 2


def test_staff_counts_only_scoped_shops_and_no_brand_items():
    org = OrganisationFactory()
    shop_a = ShopFactory(organisation=org)
    shop_b = ShopFactory(organisation=org)
    staff = _staff(org, shop=shop_a)
    ReviewFactory(organisation=org, shop=shop_a)
    ReviewFactory.create_batch(2, organisation=org, shop=shop_b)
    ActionItemFactory(organisation=org, shop=shop_a)
    ActionItemFactory.create_batch(2, organisation=org, shop=shop_b)
    ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)

    summary = get_nav_summary(user=staff)

    assert summary.reviews_awaiting_reply == 1
    assert summary.open_action_items == 1


def test_staff_region_scope_excludes_inactive_shop_credits_and_reviews():
    org = OrganisationFactory(monthly_credit_allocation=10)
    region = RegionFactory(organisation=org)
    active = ShopFactory(organisation=org, region=region)
    inactive = ShopFactory(organisation=org, region=region, is_active=False)
    staff = _staff(org, region=region)
    ShopCreditBalanceFactory(shop=active, allocated_credits=10, consumed_credits=4)
    ShopCreditBalanceFactory(shop=inactive, allocated_credits=10, consumed_credits=0)
    ReviewFactory(organisation=org, shop=active)
    ReviewFactory.create_batch(2, organisation=org, shop=inactive)

    summary = get_nav_summary(user=staff)

    assert summary.reviews_awaiting_reply == 1
    assert summary.credits == CreditTotals(remaining=6, total=10)


def test_credits_sum_active_shops_and_null_when_disabled():
    org = OrganisationFactory(monthly_credit_allocation=0)
    admin = OrgAdminFactory(organisation=org)
    ShopFactory(organisation=org)
    assert get_nav_summary(user=admin).credits is None

    org2 = OrganisationFactory(monthly_credit_allocation=5)
    admin2 = OrgAdminFactory(organisation=org2)
    ShopFactory.create_batch(2, organisation=org2)
    ShopFactory(organisation=org2, is_active=False)
    assert get_nav_summary(user=admin2).credits == CreditTotals(remaining=10, total=10)


def test_credits_show_when_only_bonus_this_month():
    org = OrganisationFactory(monthly_credit_allocation=0)
    admin = OrgAdminFactory(organisation=org)
    shop = ShopFactory(organisation=org)
    ShopCreditBalanceFactory(shop=shop, allocated_credits=0, bonus_credits=5, consumed_credits=1)

    assert get_nav_summary(user=admin).credits == CreditTotals(remaining=4, total=5)


def test_user_with_no_shops_gets_zero_counts_and_null_credits():
    org = OrganisationFactory(monthly_credit_allocation=5)
    staff = _staff(org)
    ShopFactory(organisation=org)

    assert get_nav_summary(user=staff) == NavSummary(
        reviews_awaiting_reply=0, open_action_items=0, credits=None
    )


def test_other_organisation_data_never_counted():
    org = OrganisationFactory(monthly_credit_allocation=5)
    other = OrganisationFactory(monthly_credit_allocation=7)
    admin = OrgAdminFactory(organisation=org)
    other_shop = ShopFactory(organisation=other)
    ReviewFactory(organisation=other, shop=other_shop)
    ActionItemFactory(organisation=other, shop=other_shop)

    assert get_nav_summary(user=admin) == NavSummary(
        reviews_awaiting_reply=0, open_action_items=0, credits=None
    )


def test_superadmin_gets_empty_summary():
    assert get_nav_summary(user=UserFactory(role="SUPERADMIN")).credits is None


def test_endpoint_returns_payload_shape_for_org_admin():
    org = OrganisationFactory(monthly_credit_allocation=3)
    admin = OrgAdminFactory(organisation=org)
    shop = ShopFactory(organisation=org)
    ReviewFactory(organisation=org, shop=shop)
    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.get("/api/v1/me/nav-summary/")

    assert resp.status_code == 200
    assert resp.json() == {
        "reviews_awaiting_reply": 1,
        "open_action_items": 0,
        "credits": {"remaining": 3, "total": 3},
    }


def test_endpoint_forbidden_for_superadmin():
    client = APIClient()
    client.force_authenticate(user=UserFactory(role="SUPERADMIN"))

    assert client.get("/api/v1/me/nav-summary/").status_code == 403


def _query_count(user) -> int:
    with CaptureQueriesContext(connection) as ctx:
        get_nav_summary(user=user)
    return len(ctx.captured_queries)


def test_get_nav_summary_query_count_fixed():
    org1 = OrganisationFactory(monthly_credit_allocation=5)
    admin1 = OrgAdminFactory(organisation=org1)
    shop = ShopFactory(organisation=org1)
    ReviewFactory(organisation=org1, shop=shop)
    ActionItemFactory(organisation=org1, shop=shop)
    one = _query_count(admin1)

    org2 = OrganisationFactory(monthly_credit_allocation=5)
    admin2 = OrgAdminFactory(organisation=org2)
    for s in ShopFactory.create_batch(5, organisation=org2):
        ReviewFactory(organisation=org2, shop=s)
        ActionItemFactory(organisation=org2, shop=s)
    five = _query_count(admin2)

    assert one == five
    assert five <= 5
