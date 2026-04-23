from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.accounts.permissions import IsSuperadmin
from apps.accounts.tests.factories import UserFactory

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
