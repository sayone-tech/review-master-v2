from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import current_period


class ShopCreditBalanceFactory(DjangoModelFactory):
    class Meta:
        model = ShopCreditBalance

    shop = factory.SubFactory("apps.shops.tests.factories.ShopFactory")
    organisation = factory.LazyAttribute(lambda o: o.shop.organisation)
    period_year = factory.LazyFunction(lambda: current_period().year)
    period_month = factory.LazyFunction(lambda: current_period().month)
    allocated_credits = 10
    bonus_credits = 0
    consumed_credits = 0


class CreditTransactionFactory(DjangoModelFactory):
    class Meta:
        model = CreditTransaction

    shop_credit_balance = factory.SubFactory(ShopCreditBalanceFactory)
    shop = factory.LazyAttribute(lambda o: o.shop_credit_balance.shop)
    organisation = factory.LazyAttribute(lambda o: o.shop_credit_balance.organisation)
    transaction_type = CreditTransaction.Type.CONSUMPTION
    status = CreditTransaction.Status.RESERVED
    credits_delta = -1
