from __future__ import annotations

import pytest
from django.db.utils import IntegrityError

from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.models import Region
from apps.regions.tests.factories import RegionFactory

pytestmark = pytest.mark.django_db


def test_region_str_includes_region_id() -> None:
    region = RegionFactory(name="North", region_id="NTH-001")
    assert str(region) == "North (NTH-001)"


def test_region_id_unique_within_organisation() -> None:
    org = OrganisationFactory()
    RegionFactory(organisation=org, region_id="DUP-001")
    with pytest.raises(IntegrityError):
        Region.objects.create(organisation=org, name="Other", region_id="DUP-001")


def test_region_id_allowed_across_different_organisations() -> None:
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    RegionFactory(organisation=org_a, region_id="SAME-001")
    # Should NOT raise — uniqueness is org-scoped
    RegionFactory(organisation=org_b, region_id="SAME-001")
    assert Region.objects.filter(region_id="SAME-001").count() == 2
