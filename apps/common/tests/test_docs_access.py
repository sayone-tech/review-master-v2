"""Tests for Superadmin-only API documentation access control (Task 5)."""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.organisations.tests.factories import OrganisationFactory


@pytest.mark.django_db
class TestDocsAccess:
    def setup_method(self) -> None:
        self.client = APIClient()

    # ------------------------------------------------------------------
    # Superadmin — must be able to reach all three doc endpoints
    # ------------------------------------------------------------------

    def test_superadmin_can_access_schema(self) -> None:
        superadmin = UserFactory()  # default role is SUPERADMIN
        self.client.force_authenticate(user=superadmin)
        response = self.client.get(reverse("schema"))
        assert response.status_code == 200

    def test_superadmin_can_access_scalar(self) -> None:
        superadmin = UserFactory()
        self.client.force_authenticate(user=superadmin)
        response = self.client.get(reverse("schema-scalar"), headers={"accept": "text/html"})
        assert response.status_code == 200

    def test_superadmin_can_access_redoc(self) -> None:
        superadmin = UserFactory()
        self.client.force_authenticate(user=superadmin)
        response = self.client.get(reverse("schema-redoc"))
        assert response.status_code == 200

    # ------------------------------------------------------------------
    # Non-superadmin roles — must be blocked (403)
    # ------------------------------------------------------------------

    def test_org_admin_cannot_access_scalar(self) -> None:
        org = OrganisationFactory()
        org_admin = OrgAdminFactory(organisation=org)
        self.client.force_authenticate(user=org_admin)
        response = self.client.get(reverse("schema-scalar"), headers={"accept": "text/html"})
        assert response.status_code == 403

    def test_staff_admin_cannot_access_scalar(self) -> None:
        org = OrganisationFactory()
        staff = StaffAdminFactory(organisation=org)
        self.client.force_authenticate(user=staff)
        response = self.client.get(reverse("schema-scalar"), headers={"accept": "text/html"})
        assert response.status_code == 403

    def test_unauthenticated_cannot_access_scalar(self) -> None:
        response = self.client.get(reverse("schema-scalar"), headers={"accept": "text/html"})
        # IsSuperadmin returns False for unauthenticated → DRF returns 403
        assert response.status_code in (401, 403)

    # ------------------------------------------------------------------
    # JWT bearer token (Org Admin) — must NOT grant access to Scalar
    # ScalarDocsView uses SessionAuthentication only, so a JWT-bearing
    # request is treated as anonymous → 403.
    # ------------------------------------------------------------------

    def test_jwt_authenticated_org_admin_cannot_access_scalar(self) -> None:
        org = OrganisationFactory()
        org_admin = OrgAdminFactory(organisation=org, password="testpass1234")
        # Obtain a real JWT for the org admin
        token_response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": org_admin.email, "password": "testpass1234"},
            format="json",
        )
        assert token_response.status_code == 200, token_response.data
        access_token = token_response.data["access"]

        # New unauthenticated client using only JWT Bearer header
        jwt_client = APIClient()
        jwt_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = jwt_client.get(reverse("schema-scalar"), HTTP_ACCEPT="text/html")
        # SessionAuthentication ignores the JWT header → user is anonymous → 403
        assert response.status_code == 403
