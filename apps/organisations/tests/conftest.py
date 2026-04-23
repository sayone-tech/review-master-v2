from __future__ import annotations

import pytest
from django.core.cache import caches
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory


@pytest.fixture(autouse=True)
def _clear_throttle_cache() -> None:
    """Clear the throttle cache before every test so rate-limit tests do not bleed."""
    caches["throttle"].clear()


@pytest.fixture
def superadmin(db):
    """A Superadmin user."""
    return UserFactory(email="super@example.com", role="SUPERADMIN")


@pytest.fixture
def org_admin(db):
    """An Org Admin user."""
    return UserFactory(email="orgadmin@example.com", role="ORG_ADMIN")


@pytest.fixture
def client_logged_in(superadmin) -> Client:
    """A Django test client logged in as the superadmin fixture."""
    c = Client()
    c.force_login(superadmin)
    return c


@pytest.fixture
def api_client_superadmin(superadmin) -> APIClient:
    """A DRF APIClient authenticated as superadmin."""
    c = APIClient()
    c.force_authenticate(user=superadmin)
    return c


@pytest.fixture
def api_client_orgadmin(org_admin) -> APIClient:
    """A DRF APIClient authenticated as an Org Admin."""
    c = APIClient()
    c.force_authenticate(user=org_admin)
    return c


@pytest.fixture
def anon_api_client() -> APIClient:
    """A DRF APIClient with no authentication."""
    return APIClient()


@pytest.fixture
def three_orgs(db):
    """Three organisations covering RETAIL/PHARMACY/RESTAURANT with ACTIVE/DISABLED/ACTIVE statuses."""
    from apps.organisations.models import Organisation

    return [
        OrganisationFactory(
            name="Alpha Retail",
            email="alpha@example.com",
            org_type=Organisation.OrgType.RETAIL,
            status=Organisation.Status.ACTIVE,
        ),
        OrganisationFactory(
            name="Beta Pharmacy",
            email="beta@example.com",
            org_type=Organisation.OrgType.PHARMACY,
            status=Organisation.Status.DISABLED,
        ),
        OrganisationFactory(
            name="Gamma Restaurant",
            email="gamma@example.com",
            org_type=Organisation.OrgType.RESTAURANT,
            status=Organisation.Status.ACTIVE,
        ),
    ]
