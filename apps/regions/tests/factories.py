from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.regions.models import Region


class RegionFactory(DjangoModelFactory):
    class Meta:
        model = Region

    organisation = factory.SubFactory("apps.organisations.tests.factories.OrganisationFactory")
    name = factory.Sequence(lambda n: f"Region {n}")
    region_id = factory.Sequence(lambda n: f"RGN-{n:03d}")
    is_active = True
