from __future__ import annotations

import pytest
from django.core.cache import caches
from django.test import Client

from apps.accounts.tests.factories import UserFactory

# Re-export shared fixtures so they auto-discover for any test in apps/accounts/tests/.
from apps.common.tests.fixtures import (  # noqa: F401
    assert_query_ceiling,
    two_orgs_two_admins,
)


@pytest.fixture(autouse=True)
def clear_throttle_cache() -> None:
    """Clear the throttle cache before every test so rate-limit tests do not bleed."""
    caches["throttle"].clear()


@pytest.fixture
def superadmin(db):
    """A Superadmin user with password 'testpass1234'."""
    return UserFactory(email="super@example.com", role="SUPERADMIN")


@pytest.fixture
def client_logged_in(superadmin) -> Client:
    c = Client()
    c.force_login(superadmin)
    return c


@pytest.fixture
def anon_client() -> Client:
    return Client()
