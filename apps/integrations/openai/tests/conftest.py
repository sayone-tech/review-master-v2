from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

# Re-export shared fixtures so they auto-discover for tests in this package.
from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.common.tests.fixtures import assert_query_ceiling  # noqa: F401


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def superadmin_client(db):
    client = APIClient()
    client.force_authenticate(UserFactory(role=User.Role.SUPERADMIN))
    return client
