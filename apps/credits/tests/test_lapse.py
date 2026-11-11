"""CREN-01: the monthly lapse service and sweep (Phase 31).

Every test injects ``now=`` (no clock freezing); past/current boundaries are fixed around
``NOW``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.lapse import lapse_past_balances
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


def _balance(shop, year, month, **credits):
    return ShopCreditBalanceFactory(shop=shop, period_year=year, period_month=month, **credits)


def test_lapse_past_balances_lapses_one_past_balance_and_skips_current_when_now_is_injected():
    shop = ShopFactory()
    past = _balance(shop, 2026, 2, allocated_credits=10, consumed_credits=4)
    current = _balance(shop, 2026, 3, allocated_credits=10, consumed_credits=2)

    summary = lapse_past_balances(now=NOW)

    assert summary.lapsed == 1
    assert summary.credits_lapsed == 6
    lapsed_row = CreditTransaction.objects.get(shop_credit_balance=past, transaction_type="LAPSED")
    assert lapsed_row.credits_delta == -6
    assert AuditLog.objects.filter(action="shop.credits.lapsed").count() == 1
    past.refresh_from_db()
    current.refresh_from_db()
    assert past.lapsed_at == NOW
    assert current.lapsed_at is None
    assert not CreditTransaction.objects.filter(shop_credit_balance=current).exists()
    assert ShopCreditBalance.objects.count() == 2
