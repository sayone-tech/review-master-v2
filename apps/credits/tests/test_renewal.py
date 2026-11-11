"""CREN-02: a new month starts from the live allocation with zero bonus.

No production code is needed: ``ensure_balance`` seeds every new month from the organisation's
live ``monthly_credit_allocation`` with ``bonus_credits=0``, and a lapse never mutates the
credit columns. These tests pin that contract. Explicit periods and an injected ``now`` are used
throughout, never the wall clock.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.balances import get_shop_credit_balance
from apps.credits.services.allocation import ensure_balance
from apps.credits.services.lapse import lapse_past_balances
from apps.credits.services.periods import Period
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

Type = CreditTransaction.Type


def _shop_with_prior_month(*, year=2026, month=2, allocation=10, bonus=3, consumed=4):
    org = OrganisationFactory(monthly_credit_allocation=allocation)
    shop = ShopFactory(organisation=org)
    prior = ShopCreditBalanceFactory(
        shop=shop,
        period_year=year,
        period_month=month,
        allocated_credits=allocation,
        bonus_credits=bonus,
        consumed_credits=consumed,
    )
    return org, shop, prior


def _set_allocation(org, value):
    org.monthly_credit_allocation = value
    org.save(update_fields=["monthly_credit_allocation"])


def test_new_month_starts_from_current_allocation_with_zero_bonus_when_prior_month_had_bonus_and_unused():
    org, shop, prior = _shop_with_prior_month()
    summary = lapse_past_balances(now=datetime(2026, 3, 1, 0, 5, tzinfo=UTC))
    assert summary.credits_lapsed == 9
    _set_allocation(org, 20)

    balance, created = ensure_balance(shop_id=shop.pk, period=Period(2026, 3))

    assert created is True
    assert (balance.allocated_credits, balance.bonus_credits, balance.consumed_credits) == (
        20,
        0,
        0,
    )
    assert balance.lapsed_at is None
    initial = CreditTransaction.objects.filter(
        shop_credit_balance=balance, transaction_type=Type.INITIAL_ALLOCATION
    )
    assert [row.credits_delta for row in initial] == [20]
    prior.refresh_from_db()
    assert (prior.allocated_credits, prior.bonus_credits, prior.consumed_credits) == (10, 3, 4)


def test_unused_and_bonus_do_not_carry_over_when_prior_month_is_not_lapsed_yet():
    org, shop, prior = _shop_with_prior_month()
    _set_allocation(org, 20)

    balance, created = ensure_balance(shop_id=shop.pk, period=Period(2026, 3))

    assert created is True
    assert (balance.allocated_credits, balance.bonus_credits, balance.consumed_credits) == (
        20,
        0,
        0,
    )
    prior.refresh_from_db()
    assert prior.lapsed_at is None
    assert (prior.allocated_credits, prior.bonus_credits, prior.consumed_credits) == (10, 3, 4)


def test_virtual_read_reports_live_allocation_and_zero_bonus_when_new_month_not_materialised():
    org, shop, _prior = _shop_with_prior_month()
    _set_allocation(org, 20)

    with CaptureQueriesContext(connection) as ctx:
        view = get_shop_credit_balance(shop_id=shop.pk, period=Period(2026, 3))

    assert (view.allocated, view.bonus, view.remaining) == (20, 0, 20)
    assert view.is_materialized is False
    writes = ("INSERT", "UPDATE", "DELETE")
    assert not [
        q["sql"] for q in ctx.captured_queries if q["sql"].lstrip().upper().startswith(writes)
    ]
    assert not ShopCreditBalance.objects.filter(
        shop=shop, period_year=2026, period_month=3
    ).exists()


def test_new_month_is_not_enabled_when_allocation_is_zero_even_if_prior_month_had_bonus():
    org, shop, _prior = _shop_with_prior_month()
    _set_allocation(org, 0)

    balance, created = ensure_balance(shop_id=shop.pk, period=Period(2026, 3))

    assert created is True
    assert (balance.allocated_credits, balance.bonus_credits) == (0, 0)
    assert not CreditTransaction.objects.filter(
        shop_credit_balance=balance, transaction_type=Type.INITIAL_ALLOCATION
    ).exists()
    assert get_shop_credit_balance(shop_id=shop.pk, period=Period(2026, 3)).is_enabled is False


def test_renewal_crosses_year_boundary_when_prior_month_is_december():
    org, shop, prior = _shop_with_prior_month(year=2025, month=12, bonus=2)
    summary = lapse_past_balances(now=datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    assert summary.lapsed == 1
    _set_allocation(org, 15)

    balance, created = ensure_balance(shop_id=shop.pk, period=Period(2026, 1))

    assert created is True
    assert (balance.allocated_credits, balance.bonus_credits, balance.consumed_credits) == (
        15,
        0,
        0,
    )
    prior.refresh_from_db()
    assert (prior.allocated_credits, prior.bonus_credits, prior.consumed_credits) == (10, 2, 4)
