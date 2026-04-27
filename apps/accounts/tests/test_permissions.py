from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, IsSuperadmin, org_admin_required
from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def _req(user):
    r = APIRequestFactory().get("/")
    r.user = user
    return r


def test_superadmin_role_allowed():
    assert IsSuperadmin().has_permission(_req(UserFactory(role="SUPERADMIN")), None) is True


def test_org_admin_role_denied():
    assert (
        IsSuperadmin().has_permission(_req(UserFactory(email="a@b.com", role="ORG_ADMIN")), None)
        is False
    )


def test_staff_admin_role_denied():
    assert (
        IsSuperadmin().has_permission(_req(UserFactory(email="s@b.com", role="STAFF_ADMIN")), None)
        is False
    )


def test_anonymous_user_denied():
    assert IsSuperadmin().has_permission(_req(AnonymousUser()), None) is False


def test_none_user_denied():
    assert IsSuperadmin().has_permission(_req(None), None) is False


def _django_req(user):
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user
    return req


def test_is_org_admin_allows_org_admin_with_organisation() -> None:
    org = OrganisationFactory()
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org)
    assert IsOrgAdmin().has_permission(_django_req(user), None) is True


def test_is_org_admin_rejects_org_admin_without_organisation() -> None:
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=None)
    assert IsOrgAdmin().has_permission(_django_req(user), None) is False


def test_is_org_admin_rejects_superadmin() -> None:
    user = UserFactory(role=User.Role.SUPERADMIN)
    assert IsOrgAdmin().has_permission(_django_req(user), None) is False


def test_is_org_admin_rejects_staff_admin() -> None:
    org = OrganisationFactory()
    user = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    assert IsOrgAdmin().has_permission(_django_req(user), None) is False


def test_is_org_admin_rejects_anonymous() -> None:
    assert IsOrgAdmin().has_permission(_django_req(AnonymousUser()), None) is False


def test_org_admin_required_decorator_returns_403_for_superadmin() -> None:
    @org_admin_required
    def _view(request):
        return HttpResponse("OK")

    user = UserFactory(role=User.Role.SUPERADMIN)
    req = RequestFactory().get("/")
    req.user = user
    response = _view(req)
    assert response.status_code == 403


def test_org_admin_required_decorator_allows_org_admin() -> None:
    @org_admin_required
    def _view(request):
        return HttpResponse("OK")

    org = OrganisationFactory()
    user = UserFactory(role=User.Role.ORG_ADMIN, organisation=org)
    req = RequestFactory().get("/")
    req.user = user
    response = _view(req)
    assert response.status_code == 200
    assert response.content == b"OK"
