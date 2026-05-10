from __future__ import annotations

import datetime

import factory
from factory.django import DjangoModelFactory

from apps.shops.models import ReviewTarget, Shop, ShopAuditLog


class ShopFactory(DjangoModelFactory):
    class Meta:
        model = Shop

    organisation = factory.SubFactory("apps.organisations.tests.factories.OrganisationFactory")
    region = factory.SubFactory("apps.regions.tests.factories.RegionFactory")
    name = factory.Sequence(lambda n: f"Shop {n}")
    phone = ""
    street_address = ""
    connection_method = Shop.ConnectionMethod.NOT_CONNECTED
    connection_status = Shop.ConnectionStatus.NOT_CONNECTED
    is_active = True


class ShopAuditLogFactory(DjangoModelFactory):
    class Meta:
        model = ShopAuditLog

    shop = factory.SubFactory("apps.shops.tests.factories.ShopFactory")
    actor = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    action = ShopAuditLog.Action.API_KEY_REVEALED


class ReviewTargetFactory(DjangoModelFactory):
    class Meta:
        model = ReviewTarget

    organisation = factory.LazyAttribute(lambda o: o.shop.organisation)
    shop = factory.SubFactory("apps.shops.tests.factories.ShopFactory")
    period_type = ReviewTarget.PeriodType.MONTH
    period_start = factory.LazyFunction(lambda: datetime.date.today().replace(day=1))
    target_count = 100
    created_by = None
