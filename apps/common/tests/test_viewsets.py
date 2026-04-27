from __future__ import annotations

from typing import ClassVar

import pytest
from django.test import RequestFactory
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.common.viewsets import TenantScopedViewSet
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.models import Region
from apps.regions.tests.factories import RegionFactory

pytestmark = pytest.mark.django_db


class _RegionStubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields: ClassVar[list[str]] = ["id", "name"]


class _RegionViewSet(TenantScopedViewSet):
    queryset = Region.objects.all()
    serializer_class = _RegionStubSerializer


def _build_request(user) -> object:
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user
    return req


def test_tenant_scoped_viewset_filters_by_organisation_id() -> None:
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    RegionFactory(organisation=org_a, region_id="A-001")
    RegionFactory(organisation=org_b, region_id="B-001")

    admin_a = UserFactory(role=User.Role.ORG_ADMIN, organisation=org_a)
    viewset = _RegionViewSet()
    viewset.request = _build_request(admin_a)
    qs = viewset.get_queryset()
    assert qs.count() == 1
    assert qs.first().organisation_id == org_a.pk


def test_tenant_scoped_viewset_returns_none_when_user_has_no_organisation() -> None:
    RegionFactory()
    user = UserFactory(role=User.Role.SUPERADMIN, organisation=None)
    viewset = _RegionViewSet()
    viewset.request = _build_request(user)
    assert viewset.get_queryset().count() == 0
