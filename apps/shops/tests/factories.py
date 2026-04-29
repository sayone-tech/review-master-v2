from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.shops.models import Shop, ShopAuditLog


class ShopFactory(DjangoModelFactory):
    class Meta:
        model = Shop

    organisation = factory.SubFactory("apps.organisations.tests.factories.OrganisationFactory")
    region = factory.SubFactory("apps.regions.tests.factories.RegionFactory")
    name = factory.Sequence(lambda n: f"Shop {n}")
    phone = ""
    street_address = ""
    city = ""
    connection_method = Shop.ConnectionMethod.NOT_CONNECTED
    connection_status = Shop.ConnectionStatus.NOT_CONNECTED
    is_active = True


class ShopAuditLogFactory(DjangoModelFactory):
    class Meta:
        model = ShopAuditLog

    shop = factory.SubFactory("apps.shops.tests.factories.ShopFactory")
    actor = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    action = ShopAuditLog.Action.API_KEY_REVEALED
