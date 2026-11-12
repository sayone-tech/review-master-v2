"""Tenant shop-credits read: GET /api/v1/shops/{id}/credits/ (CVIS-01, SCOPE-01)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.core.cache import caches
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import (
    current_period,
    next_period_start,
    period_label,
)
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.credits.views import ShopCreditsView
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.tests.factories import ShopFactory
from apps.shops.views import ShopViewSet

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    caches["throttle"].clear()
    yield
    caches["throttle"].clear()


def _url(shop_id: int) -> str:
    return f"/api/v1/shops/{shop_id}/credits/"


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _row_counts() -> tuple[int, int, int]:
    return (
        ShopCreditBalance.objects.count(),
        CreditTransaction.objects.count(),
        AuditLog.objects.count(),
    )


def test_staff_reads_in_scope_shop_credits_and_gets_404_out_of_scope():
    org = OrganisationFactory(monthly_credit_allocation=40)
    shop_a = ShopFactory(organisation=org)
    shop_b = ShopFactory(organisation=org)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop_a
    )
    client = _client(staff)
    before = _row_counts()

    resp = client.get(_url(shop_a.pk))

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "shop_id",
        "period",
        "period_label",
        "renews_on",
        "allocated",
        "bonus",
        "consumed",
        "remaining",
        "total",
        "is_enabled",
    }
    period = current_period()
    assert body["shop_id"] == shop_a.pk
    assert body["period"] == {"year": period.year, "month": period.month}
    assert body["period_label"] == period_label(period)
    assert body["renews_on"] == next_period_start(period).date().isoformat()
    assert (body["allocated"], body["bonus"], body["consumed"]) == (40, 0, 0)
    assert (body["remaining"], body["total"], body["is_enabled"]) == (40, 40, True)
    assert resp["Cache-Control"] == "no-store"
    assert _row_counts() == before

    denied = client.get(_url(shop_b.pk))

    assert denied.status_code == 404
    assert denied.json() == {"code": "shop_not_found", "detail": "Shop not found."}
    assert _row_counts() == before


def _scoped_staff(org, shop):
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop
    )
    return staff


def _patched_now(year, month, day, hour=0, minute=0, second=0):
    return patch(
        "apps.credits.services.periods.utc_now",
        return_value=datetime(year, month, day, hour, minute, second, tzinfo=UTC),
    )


# --- calendar -------------------------------------------------------------------------------


def test_returns_december_period_and_january_renewal_when_last_second_of_year():
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)

    with _patched_now(2026, 12, 31, 23, 59, 59):
        body = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk)).json()

    assert body["period"] == {"year": 2026, "month": 12}
    assert body["period_label"] == "December 2026"
    assert body["renews_on"] == "2027-01-01"


def test_returns_january_period_and_february_renewal_when_first_instant_of_year():
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)

    with _patched_now(2027, 1, 1):
        body = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk)).json()

    assert body["period"] == {"year": 2027, "month": 1}
    assert body["renews_on"] == "2027-02-01"


# --- balance shapes -------------------------------------------------------------------------


def test_returns_not_enabled_when_organisation_allocation_and_bonus_are_zero():
    org = OrganisationFactory(monthly_credit_allocation=0)
    shop = ShopFactory(organisation=org)

    body = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk)).json()

    assert body["is_enabled"] is False
    assert (body["total"], body["remaining"]) == (0, 0)


def test_returns_enabled_when_allocation_zero_but_current_month_bonus_present():
    org = OrganisationFactory(monthly_credit_allocation=0)
    shop = ShopFactory(organisation=org)
    ShopCreditBalanceFactory(shop=shop, allocated_credits=0, bonus_credits=5)

    body = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk)).json()

    assert body["is_enabled"] is True
    assert body["total"] == 5


def test_returns_materialised_numbers_when_row_exists():
    org = OrganisationFactory(monthly_credit_allocation=40)
    shop = ShopFactory(organisation=org)
    ShopCreditBalanceFactory(
        shop=shop, allocated_credits=100, bonus_credits=20, consumed_credits=30
    )
    before = _row_counts()

    body = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk)).json()

    assert (body["allocated"], body["bonus"], body["consumed"]) == (100, 20, 30)
    assert (body["remaining"], body["total"]) == (90, 120)
    assert _row_counts() == before


def test_returns_virtual_current_month_when_only_previous_month_row_exists():
    org = OrganisationFactory(monthly_credit_allocation=40)
    shop = ShopFactory(organisation=org)
    ShopCreditBalanceFactory(
        shop=shop,
        period_year=2026,
        period_month=10,
        allocated_credits=7,
        consumed_credits=7,
    )

    with _patched_now(2026, 11, 15):
        body = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk)).json()

    assert (body["allocated"], body["bonus"], body["consumed"], body["remaining"]) == (40, 0, 0, 40)


def test_org_admin_and_staff_receive_identical_payload():
    org = OrganisationFactory(monthly_credit_allocation=40)
    shop = ShopFactory(organisation=org)
    ShopCreditBalanceFactory(shop=shop, allocated_credits=40, bonus_credits=5, consumed_credits=3)

    admin_body = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk)).json()
    staff_body = _client(_scoped_staff(org, shop)).get(_url(shop.pk)).json()

    assert admin_body == staff_body
    assert admin_body["allocated"] == 40
    assert admin_body["bonus"] == 5


def test_returns_200_when_shop_is_inactive():
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org, is_active=False)

    resp = _client(OrgAdminFactory(organisation=org)).get(_url(shop.pk))

    assert resp.status_code == 200


def test_never_writes_rows_for_any_role_or_materialisation_state():
    org = OrganisationFactory(monthly_credit_allocation=10)
    plain = ShopFactory(organisation=org)
    materialised = ShopFactory(organisation=org)
    ShopCreditBalanceFactory(shop=materialised, allocated_credits=10)
    admin = _client(OrgAdminFactory(organisation=org))
    staff = _client(_scoped_staff(org, plain))
    before = _row_counts()

    for client in (admin, staff):
        for shop in (plain, materialised):
            client.get(_url(shop.pk))

    assert _row_counts() == before


# --- negative matrix ------------------------------------------------------------------------


def test_returns_404_when_org_admin_of_another_organisation():
    owner = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=owner)
    other_admin = OrgAdminFactory(organisation=OrganisationFactory())

    resp = _client(other_admin).get(_url(shop.pk))

    assert resp.status_code == 404
    assert resp.json()["code"] == "shop_not_found"


def test_returns_identical_404_body_when_shop_unknown_or_out_of_scope():
    org = OrganisationFactory(monthly_credit_allocation=10)
    mine = ShopFactory(organisation=org)
    theirs = ShopFactory(organisation=org)
    client = _client(_scoped_staff(org, mine))

    unknown = client.get(_url(999999))
    out_of_scope = client.get(_url(theirs.pk))

    assert unknown.status_code == out_of_scope.status_code == 404
    assert unknown.json() == out_of_scope.json()


def test_returns_404_when_staff_has_no_scope_rows():
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)

    resp = _client(StaffAdminFactory(organisation=org)).get(_url(shop.pk))

    assert resp.status_code == 404


def test_returns_200_when_staff_scoped_by_region():
    org = OrganisationFactory(monthly_credit_allocation=10)
    region = RegionFactory(organisation=org)
    shop = ShopFactory(organisation=org, region=region)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.REGION, region=region
    )

    resp = _client(staff).get(_url(shop.pk))

    assert resp.status_code == 200


def test_returns_403_without_writing_when_superadmin():
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    before = _row_counts()

    resp = _client(UserFactory()).get(_url(shop.pk))

    assert resp.status_code == 403
    assert _row_counts() == before


def test_is_refused_when_anonymous():
    shop = ShopFactory()

    resp = APIClient().get(_url(shop.pk))

    assert resp.status_code in (401, 403)


# --- throttle, routing, query ceiling -------------------------------------------------------


def test_is_throttled_on_its_own_scope(settings):
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["shop_credits"] == "120/minute"
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    client = _client(OrgAdminFactory(organisation=org))

    with patch.object(ScopedRateThrottle, "THROTTLE_RATES", {**rates, "shop_credits": "1/minute"}):
        first = client.get(_url(shop.pk))
        second = client.get(_url(shop.pk))

    assert first.status_code == 200
    assert second.status_code == 429


def test_route_resolves_to_view_without_colliding_with_shop_viewset():
    assert resolve("/api/v1/shops/5/credits/").func.view_class is ShopCreditsView
    assert resolve("/api/v1/shops/5/").func.cls is ShopViewSet


@pytest.mark.parametrize("materialised", [False, True], ids=["unmaterialised", "materialised"])
@pytest.mark.parametrize("role", ["org_admin", "staff"])
def test_query_count_stays_within_ceiling(role, materialised, assert_query_ceiling):
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    if materialised:
        ShopCreditBalanceFactory(shop=shop, allocated_credits=10)
    user = OrgAdminFactory(organisation=org) if role == "org_admin" else _scoped_staff(org, shop)
    client = _client(user)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(_url(shop.pk))

    assert resp.status_code == 200
    assert_query_ceiling(ctx, 5)
