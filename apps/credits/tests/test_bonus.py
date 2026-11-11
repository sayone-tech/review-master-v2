"""Bonus allocation service (CSUP-01)."""

from __future__ import annotations

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.credits.models import CreditTransaction
from apps.credits.services.bonus import allocate_bonus
from apps.credits.services.periods import current_period
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

Type = CreditTransaction.Type


def test_allocate_bonus_increments_bonus_and_returns_snapshot_when_period_is_current():
    actor = UserFactory()
    org = OrganisationFactory(monthly_credit_allocation=100)
    shop = ShopFactory(organisation=org)

    result = allocate_bonus(
        shop_id=shop.pk, amount=50, reason=None, period=current_period(), actor_id=actor.pk
    )

    assert (result.allocated, result.bonus, result.consumed, result.remaining) == (100, 50, 0, 150)
    assert (result.period_year, result.period_month) == tuple(current_period())
    tx = CreditTransaction.objects.get(pk=result.transaction_id)
    assert tx.transaction_type == Type.BONUS_ALLOCATION
    assert tx.note is None
