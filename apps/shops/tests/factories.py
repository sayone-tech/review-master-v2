from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.shops.models import Shop


class ShopFactory(DjangoModelFactory):
    class Meta:
        model = Shop

    organisation = factory.SubFactory("apps.organisations.tests.factories.OrganisationFactory")
    region = None
    name = factory.Sequence(lambda n: f"Shop {n}")
    phone = ""
    street_address = ""
    city = ""
    connection_method = Shop.ConnectionMethod.NOT_CONNECTED
    connection_status = Shop.ConnectionStatus.NOT_CONNECTED
    is_active = True
