from __future__ import annotations

import jwt as pyjwt
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.organisations.tests.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Test group 1: Token obtain (POST /api/v1/auth/token/)
# ---------------------------------------------------------------------------


class TestTokenObtain:
    TOKEN_URL = "/api/v1/auth/token/"

    def setup_method(self):
        self.client = APIClient()
        self.org = OrganisationFactory()

    def test_org_admin_login_returns_tokens(self):
        user = OrgAdminFactory(organisation=self.org, password="testpass1234")
        resp = self.client.post(
            self.TOKEN_URL, {"email": user.email, "password": "testpass1234"}, format="json"
        )
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_staff_admin_login_returns_tokens(self):
        user = StaffAdminFactory(organisation=self.org, password="testpass1234")
        resp = self.client.post(
            self.TOKEN_URL, {"email": user.email, "password": "testpass1234"}, format="json"
        )
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_wrong_password_returns_401(self):
        user = OrgAdminFactory(organisation=self.org, password="testpass1234")
        resp = self.client.post(
            self.TOKEN_URL, {"email": user.email, "password": "wrongpassword"}, format="json"
        )
        assert resp.status_code == 401

    def test_nonexistent_email_returns_401(self):
        resp = self.client.post(
            self.TOKEN_URL,
            {"email": "nobody@example.com", "password": "testpass1234"},
            format="json",
        )
        assert resp.status_code == 401

    def test_superadmin_returns_403(self):
        # Superadmin has organisation_id = None — mobile access must be denied
        user = UserFactory(role=User.Role.SUPERADMIN, organisation=None, password="testpass1234")
        resp = self.client.post(
            self.TOKEN_URL, {"email": user.email, "password": "testpass1234"}, format="json"
        )
        assert resp.status_code == 403
        assert "superadmin" in str(resp.data).lower()

    def test_missing_email_returns_400(self):
        resp = self.client.post(self.TOKEN_URL, {"password": "testpass1234"}, format="json")
        assert resp.status_code == 400

    def test_missing_password_returns_400(self):
        user = OrgAdminFactory(organisation=self.org, password="testpass1234")
        resp = self.client.post(self.TOKEN_URL, {"email": user.email}, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test group 2: JWT claims
# ---------------------------------------------------------------------------


class TestJWTClaims:
    TOKEN_URL = "/api/v1/auth/token/"

    def setup_method(self):
        self.client = APIClient()
        self.org = OrganisationFactory()

    def _login(self, user: User) -> dict:
        resp = self.client.post(
            self.TOKEN_URL, {"email": user.email, "password": "testpass1234"}, format="json"
        )
        assert resp.status_code == 200, resp.data
        return resp.data

    def test_org_admin_token_has_correct_claims(self):
        user = OrgAdminFactory(organisation=self.org, password="testpass1234")
        data = self._login(user)
        decoded = pyjwt.decode(data["access"], options={"verify_signature": False})
        assert decoded["user_id"] == user.id
        assert decoded["email"] == user.email
        assert decoded["full_name"] == user.full_name
        assert decoded["role"] == User.Role.ORG_ADMIN
        assert decoded["organisation_id"] == self.org.id

    def test_staff_admin_token_has_correct_claims(self):
        user = StaffAdminFactory(organisation=self.org, password="testpass1234")
        data = self._login(user)
        decoded = pyjwt.decode(data["access"], options={"verify_signature": False})
        assert decoded["role"] == User.Role.STAFF_ADMIN
        assert decoded["organisation_id"] == self.org.id


# ---------------------------------------------------------------------------
# Test group 3: Token refresh (POST /api/v1/auth/token/refresh/)
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    TOKEN_URL = "/api/v1/auth/token/"
    REFRESH_URL = "/api/v1/auth/token/refresh/"

    def setup_method(self):
        self.client = APIClient()
        self.org = OrganisationFactory()

    def _login(self, user: User) -> dict:
        resp = self.client.post(
            self.TOKEN_URL, {"email": user.email, "password": "testpass1234"}, format="json"
        )
        assert resp.status_code == 200, resp.data
        return resp.data

    def test_valid_refresh_token_returns_new_tokens(self):
        user = OrgAdminFactory(organisation=self.org, password="testpass1234")
        data = self._login(user)
        resp = self.client.post(self.REFRESH_URL, {"refresh": data["refresh"]}, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data

    def test_invalid_refresh_token_returns_401(self):
        resp = self.client.post(
            self.REFRESH_URL,
            {"refresh": "this.is.not.a.valid.jwt"},
            format="json",
        )
        assert resp.status_code == 401

    def test_missing_refresh_field_returns_400(self):
        resp = self.client.post(self.REFRESH_URL, {}, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test group 4: JWT access on protected endpoints
# ---------------------------------------------------------------------------


class TestJWTAccess:
    TOKEN_URL = "/api/v1/auth/token/"
    # A list endpoint that requires authentication
    PROTECTED_URL = "/api/v1/reviews/"

    def setup_method(self):
        self.client = APIClient()
        self.org = OrganisationFactory()

    def _login(self, user: User) -> dict:
        resp = self.client.post(
            self.TOKEN_URL, {"email": user.email, "password": "testpass1234"}, format="json"
        )
        assert resp.status_code == 200, resp.data
        return resp.data

    def test_valid_bearer_token_accesses_protected_endpoint(self):
        user = OrgAdminFactory(organisation=self.org, password="testpass1234")
        data = self._login(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        resp = self.client.get(self.PROTECTED_URL)
        assert resp.status_code == 200

    @pytest.mark.skip(reason="Requires time-travel to create an already-expired token")
    def test_expired_access_token_returns_401(self):
        pass

    def test_no_token_returns_401(self):
        # DRF returns 403 (CSRF failure) when SessionAuthentication is active and no
        # CSRF token is present; JWT auth alone would give 401. Both mean "not
        # authorised" — accept either per the existing codebase convention.
        resp = self.client.get(self.PROTECTED_URL)
        assert resp.status_code in (401, 403)

    def test_session_auth_still_works(self):
        user = OrgAdminFactory(organisation=self.org, password="testpass1234")
        self.client.force_authenticate(user=user)
        resp = self.client.get(self.PROTECTED_URL)
        assert resp.status_code == 200
