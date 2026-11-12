from __future__ import annotations

import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.accounts.tests.factories import UserFactory
from apps.organisations.admin import OrganisationAdmin
from apps.organisations.models import Organisation

pytestmark = pytest.mark.django_db


def test_admin_lists_monthly_credit_allocation_as_read_only():
    """D-22: Django admin must not bypass CRED-06 materialisation or the audit row."""
    request = RequestFactory().get("/admin/organisations/organisation/")
    request.user = UserFactory(is_superuser=True, is_staff=True)

    model_admin = OrganisationAdmin(Organisation, admin.site)

    assert "monthly_credit_allocation" in model_admin.get_readonly_fields(request)
