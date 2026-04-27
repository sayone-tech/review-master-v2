from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.common.permissions import IsOrgScoped
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def _req(user):
    rf = RequestFactory()
    r = rf.get("/")
    r.user = user
    return r


def test_is_org_scoped_allows_org_admin() -> None:
    org = OrganisationFactory()
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org)
    assert IsOrgScoped().has_permission(_req(user), None) is True


def test_is_org_scoped_allows_staff_admin() -> None:
    org = OrganisationFactory()
    user = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    assert IsOrgScoped().has_permission(_req(user), None) is True


def test_is_org_scoped_rejects_superadmin() -> None:
    user = UserFactory(role=User.Role.SUPERADMIN)
    assert IsOrgScoped().has_permission(_req(user), None) is False


def test_is_org_scoped_rejects_anonymous() -> None:
    assert IsOrgScoped().has_permission(_req(AnonymousUser()), None) is False


def test_is_org_scoped_object_permission_allows_same_org() -> None:
    org = OrganisationFactory()
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org)
    obj = SimpleNamespace(organisation_id=org.pk)
    assert IsOrgScoped().has_object_permission(_req(user), None, obj) is True


def test_is_org_scoped_object_permission_rejects_other_org() -> None:
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org_a)
    obj = SimpleNamespace(organisation_id=org_b.pk)
    assert IsOrgScoped().has_object_permission(_req(user), None, obj) is False


def test_is_org_scoped_object_permission_rejects_object_without_org() -> None:
    org = OrganisationFactory()
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org)
    obj = SimpleNamespace()  # no organisation_id attribute
    assert IsOrgScoped().has_object_permission(_req(user), None, obj) is False
