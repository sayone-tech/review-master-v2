from __future__ import annotations

import pytest

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.allocation import ensure_balance
from apps.credits.services.periods import Period, current_period
from apps.credits.tests.factories import CreditTransactionFactory, ShopCreditBalanceFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.models import Shop
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def _shop(allocation: int):
    return ShopFactory(organisation=OrganisationFactory(monthly_credit_allocation=allocation))


def test_seeds_balance_from_org_allocation_when_first_use():
    shop = _shop(7)

    balance, created = ensure_balance(shop_id=shop.pk)

    assert created is True
    assert (balance.period_year, balance.period_month) == tuple(current_period())
    assert balance.allocated_credits == 7
    assert balance.bonus_credits == 0
    assert balance.consumed_credits == 0

    tx = CreditTransaction.objects.get()
    assert tx.transaction_type == CreditTransaction.Type.INITIAL_ALLOCATION
    assert tx.status == CreditTransaction.Status.COMMITTED
    assert tx.credits_delta == 7
    assert tx.actor is None
    assert tx.shop_id == shop.pk
    assert tx.organisation_id == shop.organisation_id
    assert tx.shop_credit_balance_id == balance.pk

    audit = AuditLog.objects.get(action="shop.credits.allocated")
    assert audit.entity_type == "shop"
    assert audit.entity_id == str(shop.pk)
    assert audit.actor is None
    assert audit.organisation_id == shop.organisation_id
    assert set(audit.after_data) == {"period_year", "period_month", "allocated_credits"}
    assert audit.after_data["allocated_credits"] == 7


def test_returns_existing_row_without_writes_when_second_call():
    shop = _shop(7)
    first, _ = ensure_balance(shop_id=shop.pk)

    second, created = ensure_balance(shop_id=shop.pk)

    assert created is False
    assert second.pk == first.pk
    assert ShopCreditBalance.objects.count() == 1
    assert CreditTransaction.objects.count() == 1
    assert AuditLog.objects.filter(action="shop.credits.allocated").count() == 1


def test_writes_balance_only_when_allocation_is_zero():
    shop = _shop(0)

    balance, created = ensure_balance(shop_id=shop.pk)

    assert created is True
    assert balance.allocated_credits == 0
    assert CreditTransaction.objects.count() == 0
    assert AuditLog.objects.filter(action="shop.credits.allocated").count() == 0


def test_creates_separate_row_with_own_initial_when_next_month_period():
    shop = _shop(5)
    now = current_period()
    next_month = Period(now.year + now.month // 12, now.month % 12 + 1)

    first, _ = ensure_balance(shop_id=shop.pk, period=now)
    second, created = ensure_balance(shop_id=shop.pk, period=next_month)

    assert created is True
    assert second.pk != first.pk
    assert (second.period_year, second.period_month) == tuple(next_month)
    assert CreditTransaction.objects.filter(shop_credit_balance=second).count() == 1
    assert CreditTransaction.objects.count() == 2


def test_uses_live_org_value_when_allocation_changed_before_first_use():
    org = OrganisationFactory(monthly_credit_allocation=3)
    shop = ShopFactory(organisation=org)
    org.monthly_credit_allocation = 12
    org.save(update_fields=["monthly_credit_allocation"])

    balance, _ = ensure_balance(shop_id=shop.pk)

    assert balance.allocated_credits == 12
    assert CreditTransaction.objects.get().credits_delta == 12


def test_stamps_shop_organisation_on_balance():
    shop = _shop(2)

    balance, _ = ensure_balance(shop_id=shop.pk)

    assert balance.organisation_id == shop.organisation_id


def test_raises_does_not_exist_when_shop_missing():
    with pytest.raises(Shop.DoesNotExist):
        ensure_balance(shop_id=999_999)


def test_honours_prebuilt_balance_without_extra_writes_when_row_exists():
    org = OrganisationFactory(monthly_credit_allocation=50)
    shop = ShopFactory(organisation=org)
    balance = ShopCreditBalanceFactory(shop=shop)
    reservation = CreditTransactionFactory(shop_credit_balance=balance)

    result, created = ensure_balance(
        shop_id=shop.pk, period=Period(balance.period_year, balance.period_month)
    )

    assert created is False
    assert result.pk == balance.pk
    assert result.allocated_credits == 10  # prebuilt value, not the org's 50
    assert (
        CreditTransaction.objects.filter(
            transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
        ).count()
        == 0
    )
    assert AuditLog.objects.filter(action="shop.credits.allocated").count() == 0
    reservation.refresh_from_db()
    assert reservation.status == CreditTransaction.Status.RESERVED
    assert reservation.credits_delta == -1
    assert reservation.shop_id == shop.pk
    assert reservation.organisation_id == org.pk
    assert result.organisation_id == org.pk
