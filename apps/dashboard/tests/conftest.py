"""Fixtures for apps.dashboard tests."""

import pytest

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory


@pytest.fixture
def org_admin_with_shops(db):
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)
    shop1 = ShopFactory(organisation=org)
    shop2 = ShopFactory(organisation=org)
    return {"user": user, "org": org, "shops": [shop1, shop2]}
