"""Superadmin credit endpoints: bonus allocation and shop list (CSUP-01, CSUP-02)."""

from __future__ import annotations

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import current_period
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

Type = CreditTransaction.Type


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    caches["throttle"].clear()
    yield
    caches["throttle"].clear()


@pytest.fixture
def superadmin():
    return UserFactory()


@pytest.fixture
def superadmin_client(superadmin):
    client = APIClient()
    client.force_authenticate(user=superadmin)
    return client


def _bonus_url(shop_id: int) -> str:
    return f"/api/v1/superadmin/shops/{shop_id}/credits/bonus/"


def test_bonus_post_allocates_credits_and_writes_ledger_and_audit_when_superadmin(
    superadmin_client, superadmin
):
    org = OrganisationFactory(monthly_credit_allocation=100)
    shop = ShopFactory(organisation=org)
    period = current_period()

    resp = superadmin_client.post(
        _bonus_url(shop.pk),
        {
            "amount": 50,
            "reason": "Goodwill",
            "period_year": period.year,
            "period_month": period.month,
        },
        format="json",
    )

    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {
        "shop_id",
        "period",
        "allocated",
        "bonus",
        "consumed",
        "remaining",
        "transaction_id",
    }
    assert body["shop_id"] == shop.pk
    assert body["period"] == {"year": period.year, "month": period.month}
    assert (body["allocated"], body["bonus"], body["consumed"], body["remaining"]) == (
        100,
        50,
        0,
        150,
    )

    balance = ShopCreditBalance.objects.get(shop=shop)
    assert (balance.period_year, balance.period_month) == period
    assert balance.bonus_credits == 50
    assert ShopCreditBalance.objects.filter(shop=shop).count() == 1
    initial = CreditTransaction.objects.filter(shop=shop, transaction_type=Type.INITIAL_ALLOCATION)
    assert [t.credits_delta for t in initial] == [100]
    bonus_rows = CreditTransaction.objects.filter(shop=shop, transaction_type=Type.BONUS_ALLOCATION)
    assert bonus_rows.count() == 1
    tx = bonus_rows.get()
    assert tx.pk == body["transaction_id"]
    assert tx.credits_delta == 50
    assert tx.status == CreditTransaction.Status.COMMITTED
    assert tx.actor_id == superadmin.pk
    assert tx.note == "Goodwill"

    audit = AuditLog.objects.filter(action="shop.credits.bonus_allocated")
    assert audit.count() == 1
    row = audit.get()
    assert row.entity_type == "shop"
    assert row.entity_id == str(shop.pk)
    assert row.actor_id == superadmin.pk
    assert row.organisation_id == org.pk
    assert row.before_data == {"bonus_credits": 0}
    assert set(row.after_data) == {
        "amount",
        "bonus_credits",
        "has_reason",
        "transaction_id",
        "period_year",
        "period_month",
    }
    assert row.after_data["has_reason"] is True
    assert_ledger_reconciles(balance)
