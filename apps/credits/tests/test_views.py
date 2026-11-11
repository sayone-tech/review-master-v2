"""Superadmin credit endpoints: bonus allocation and shop list (CSUP-01, CSUP-02)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.core.cache import caches
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import Period, current_period
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.organisations.models import Organisation
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


def _counts() -> tuple[int, int, int]:
    return (
        ShopCreditBalance.objects.count(),
        CreditTransaction.objects.count(),
        AuditLog.objects.count(),
    )


def _body(amount=5, reason="", period=None, **overrides):
    p = period or current_period()
    body = {"amount": amount, "reason": reason, "period_year": p.year, "period_month": p.month}
    body.update(overrides)
    return body


@pytest.fixture
def org_shop():
    org = OrganisationFactory(monthly_credit_allocation=100)
    return org, ShopFactory(organisation=org)


@pytest.mark.parametrize("delta", [-1, 1], ids=["previous_month", "future_month"])
def test_bonus_returns_409_without_writing_when_period_is_not_current(
    superadmin_client, org_shop, delta
):
    _, shop = org_shop
    cur = current_period()
    total = cur.year * 12 + (cur.month - 1) + delta
    stale = Period(total // 12, total % 12 + 1)
    before = _counts()

    resp = superadmin_client.post(
        _bonus_url(shop.pk),
        _body(period=stale),
        format="json",
    )

    assert resp.status_code == 409
    body = resp.json()
    assert set(body) == {"code", "detail", "period", "balance"}
    assert body["code"] == "period_mismatch"
    assert body["period"] == {"year": cur.year, "month": cur.month}
    assert set(body["balance"]) == {"shop_id", "allocated", "bonus", "consumed", "remaining"}
    assert body["balance"]["remaining"] == 100
    assert _counts() == before


def test_bonus_returns_409_with_new_month_balance_when_month_rolled_over(
    superadmin_client, org_shop
):
    _, shop = org_shop
    nov = datetime(2026, 11, 30, 23, 59, 50, tzinfo=UTC)
    dec = datetime(2026, 12, 1, 0, 0, 30, tzinfo=UTC)
    with patch("apps.credits.services.periods.utc_now", return_value=nov):
        displayed = current_period()
    before = _counts()

    with patch("apps.credits.services.periods.utc_now", return_value=dec):
        resp = superadmin_client.post(_bonus_url(shop.pk), _body(period=displayed), format="json")

    assert resp.status_code == 409
    body = resp.json()
    assert body["period"] == {"year": 2026, "month": 12}
    assert body["balance"]["remaining"] == 100
    assert _counts() == before
    assert not ShopCreditBalance.objects.filter(period_month=12).exists()


@pytest.mark.parametrize("case", ["inactive", "unknown", "deleted_org"])
def test_bonus_returns_404_without_writing_when_shop_unavailable(superadmin_client, case):
    if case == "inactive":
        shop_id = ShopFactory(is_active=False).pk
    elif case == "unknown":
        shop_id = 999999
    else:
        shop_id = ShopFactory(
            organisation=OrganisationFactory(status=Organisation.Status.DELETED)
        ).pk
    before = _counts()

    resp = superadmin_client.post(_bonus_url(shop_id), _body(), format="json")

    assert resp.status_code == 404
    assert resp.json() == {"code": "shop_unavailable", "detail": "This shop is no longer active."}
    assert _counts() == before


def test_bonus_succeeds_when_organisation_disabled(superadmin_client):
    org = OrganisationFactory(monthly_credit_allocation=10, status=Organisation.Status.DISABLED)
    shop = ShopFactory(organisation=org)

    resp = superadmin_client.post(_bonus_url(shop.pk), _body(amount=7), format="json")

    assert resp.status_code == 201
    assert resp.json()["bonus"] == 7


def test_bonus_accepts_boundaries_and_has_no_cumulative_cap(superadmin_client, org_shop):
    _, shop = org_shop

    assert (
        superadmin_client.post(_bonus_url(shop.pk), _body(amount=1), format="json").status_code
        == 201
    )
    for _ in range(2):
        resp = superadmin_client.post(_bonus_url(shop.pk), _body(amount=10000), format="json")
        assert resp.status_code == 201

    assert ShopCreditBalance.objects.get(shop=shop).bonus_credits == 20001


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"amount": 0}, "amount"),
        ({"amount": 10001}, "amount"),
        ({"amount": "abc"}, "amount"),
        ({"amount": 1.5}, "amount"),
        ({"reason": "x" * 256}, "reason"),
        ({"period_month": 0}, "period_month"),
        ({"period_month": 13}, "period_month"),
    ],
)
def test_bonus_returns_400_without_writing_when_input_invalid(
    superadmin_client, org_shop, overrides, field
):
    _, shop = org_shop
    before = _counts()

    resp = superadmin_client.post(_bonus_url(shop.pk), _body(**overrides), format="json")

    assert resp.status_code == 400
    assert field in resp.json()
    assert _counts() == before


def test_bonus_returns_400_without_writing_when_amount_missing(superadmin_client, org_shop):
    _, shop = org_shop
    body = _body()
    del body["amount"]
    before = _counts()

    resp = superadmin_client.post(_bonus_url(shop.pk), body, format="json")

    assert resp.status_code == 400
    assert "amount" in resp.json()
    assert _counts() == before


def test_bonus_stores_no_reason_text_in_audit_when_reason_given(superadmin_client, org_shop):
    _, shop = org_shop

    resp = superadmin_client.post(
        _bonus_url(shop.pk), _body(reason="  Secret goodwill  "), format="json"
    )

    assert resp.status_code == 201
    audit = AuditLog.objects.get(action="shop.credits.bonus_allocated")
    assert "Secret goodwill" not in json.dumps(audit.before_data)
    assert "Secret goodwill" not in json.dumps(audit.after_data)
    assert CreditTransaction.objects.get(pk=resp.json()["transaction_id"]).note == "Secret goodwill"


def test_bonus_returns_403_without_writing_when_org_admin(org_shop):
    org, shop = org_shop
    client = APIClient()
    client.force_authenticate(user=OrgAdminFactory(organisation=org))
    before = _counts()

    resp = client.post(_bonus_url(shop.pk), _body(), format="json")

    assert resp.status_code == 403
    assert _counts() == before


def test_bonus_returns_403_without_writing_when_staff_user(org_shop):
    org, shop = org_shop
    client = APIClient()
    client.force_authenticate(user=StaffAdminFactory(organisation=org))
    before = _counts()

    resp = client.post(_bonus_url(shop.pk), _body(), format="json")

    assert resp.status_code == 403
    assert _counts() == before


def test_bonus_is_refused_when_anonymous(org_shop):
    _, shop = org_shop
    before = _counts()

    resp = APIClient().post(_bonus_url(shop.pk), _body(), format="json")

    assert resp.status_code in (401, 403)
    assert _counts() == before


def test_bonus_returns_429_when_write_rate_exceeded(superadmin_client, org_shop, monkeypatch):
    _, shop = org_shop
    monkeypatch.setattr(
        ScopedRateThrottle, "THROTTLE_RATES", {"superadmin_credits_write": "2/minute"}
    )

    codes = [
        superadmin_client.post(_bonus_url(shop.pk), _body(amount=1), format="json").status_code
        for _ in range(3)
    ]

    assert codes == [201, 201, 429]
