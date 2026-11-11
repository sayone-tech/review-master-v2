"""Tenant shop-credits read: GET /api/v1/shops/{id}/credits/ (CVIS-01, SCOPE-01)."""

from __future__ import annotations

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import StaffAdminFactory
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import current_period, next_period_start, period_label
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

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
