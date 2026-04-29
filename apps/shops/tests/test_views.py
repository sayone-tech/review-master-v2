from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.models import Shop, ShopAuditLog
from apps.shops.tests.factories import ShopFactory

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_OAUTH_SETTINGS = {
    "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
    "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
    "GOOGLE_OAUTH_REDIRECT_URI": "http://testserver/oauth/google/callback/",
}

# Fake test API keys — never real secrets. gitleaks:allow below.
_API_KEY_A = "AIzaSyBSECRETKEY123"  # gitleaks:allow
_API_KEY_TAIL = "AIzaXYZTAIL"  # gitleaks:allow
_API_KEY_VALID_1 = "AIzaXYZVALIDKEY0001"  # gitleaks:allow
_API_KEY_VALID_2 = "AIzaXYZVALIDKEY0002"  # gitleaks:allow
_API_KEY_BROKEN = "AIzaXYZBROKENKEY000"  # gitleaks:allow
_API_KEY_VALID_3 = "AIzaXYZVALIDKEY0003"  # gitleaks:allow
_API_KEY_SHORT = "AIzaNEWKEY"  # gitleaks:allow
_API_KEY_REVEAL = "AIzaXYZ"  # gitleaks:allow
_API_KEY_AUDIT = "AIzaAUDIT"  # gitleaks:allow
_API_KEY_OLD_1 = "AIzaOLDKEY1234567"  # gitleaks:allow
_API_KEY_NEW_1 = "AIzaNEWKEY9876543"  # gitleaks:allow
_API_KEY_OLD_2 = "AIzaOLDKEY1234568"  # gitleaks:allow
_API_KEY_BAD_1 = "AIzaBADKEY9876541"  # gitleaks:allow
_API_KEY_ORIGINAL = "AIzaORIGINAL1234567"  # gitleaks:allow
_API_KEY_NEW_2 = "AIzaNEWKEY9876542"  # gitleaks:allow


@pytest.fixture
def org_and_admin(db):
    org = OrganisationFactory(number_of_stores=10)
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=admin)
    return org, admin, client


def _seed_session(client: APIClient, key: str, value: object) -> None:
    """Seed a session key for an APIClient (DRF test client)."""
    session = client.session  # type: ignore[attr-defined]
    session[key] = value
    session.save()


# ---------------------------------------------------------------------------
# 1. TestShopsListAllocation (SHOP-01)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsListAllocation:
    def test_response_includes_allocation_status(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory.create_batch(2, organisation=org, region=region)
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        assert "allocation_status" in resp.data
        alloc = resp.data["allocation_status"]
        assert alloc["current"] == 2
        assert alloc["max"] == 10
        assert alloc["at_limit"] is False

    def test_at_limit_flag_true_when_full(self, db):
        org = OrganisationFactory(number_of_stores=2)
        admin = UserFactory(role="ORG_ADMIN", organisation=org)
        region = RegionFactory(organisation=org)
        ShopFactory.create_batch(2, organisation=org, region=region)
        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        assert resp.data["allocation_status"]["at_limit"] is True

    def test_response_includes_has_regions_true(self, org_and_admin):
        org, _, client = org_and_admin
        RegionFactory(organisation=org)
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        assert resp.data["has_regions"] is True

    def test_response_includes_has_regions_false(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        assert resp.data["has_regions"] is False


# ---------------------------------------------------------------------------
# 2. TestShopSerializerFields (SHOP-13)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopSerializerFields:
    def test_read_serializer_excludes_google_refresh_token(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.GOOGLE_OAUTH,
            google_refresh_token="1//super-secret-token",
        )
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        result = resp.data["results"][0]
        assert "google_refresh_token" not in result

    def test_read_serializer_excludes_raw_api_key(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.MANUAL,
            api_key=_API_KEY_A,
        )
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        result = resp.data["results"][0]
        # Raw api_key must NOT be present
        assert "api_key" not in result
        # Masked version MUST be present
        assert "api_key_masked" in result

    def test_api_key_masked_format(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.MANUAL,
            api_key=_API_KEY_TAIL,
        )
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        masked = resp.data["results"][0]["api_key_masked"]
        assert masked == "••••TAIL"

    def test_api_key_masked_empty_for_no_key(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory(organisation=org, region=region, api_key="")
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        assert resp.data["results"][0]["api_key_masked"] == ""


# ---------------------------------------------------------------------------
# 3. TestShopsApiCreate (SHOP-08, SHOP-14)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsApiCreate:
    def test_create_with_region_succeeds(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "Test Shop",
                "connection_method": "NOT_CONNECTED",
                "region": region.pk,
            },
        )
        assert resp.status_code == 201
        assert resp.data["name"] == "Test Shop"
        assert "id" in resp.data

    def test_create_without_region_fails(self, org_and_admin):
        _, _, client = org_and_admin
        resp = client.post(
            "/api/v1/shops/",
            {"name": "Test Shop", "connection_method": "NOT_CONNECTED"},
        )
        assert resp.status_code == 400
        assert "region" in resp.data

    def test_create_with_other_org_region_returns_400(self, db, two_orgs_two_admins):
        d = two_orgs_two_admins
        region_b = RegionFactory(organisation=d["org_b"])
        client_a = APIClient()
        client_a.force_authenticate(user=d["admin_a"])
        resp = client_a.post(
            "/api/v1/shops/",
            {
                "name": "Hacked Shop",
                "connection_method": "NOT_CONNECTED",
                "region": region_b.pk,
            },
        )
        assert resp.status_code == 400

    def test_create_at_limit_returns_400(self, db):
        org = OrganisationFactory(number_of_stores=1)
        admin = UserFactory(role="ORG_ADMIN", organisation=org)
        region = RegionFactory(organisation=org)
        ShopFactory(organisation=org, region=region)  # fills the limit
        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "Over Limit",
                "connection_method": "NOT_CONNECTED",
                "region": region.pk,
            },
        )
        assert resp.status_code == 400
        assert any(
            "Shop allocation limit reached." in str(err)
            for err in resp.data.get("non_field_errors", [])
        )

    @patch("apps.shops.services.shops.validate_place_id")
    def test_create_manual_validates_via_places_api(self, mock_validate, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        mock_validate.return_value = None
        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "Manual Shop",
                "connection_method": "MANUAL",
                "region": region.pk,
                "place_id": "ChIJ123",
                "api_key": _API_KEY_VALID_1,
            },
        )
        assert resp.status_code == 201
        mock_validate.assert_called_once()

    @patch("apps.shops.services.shops.validate_place_id")
    def test_create_manual_invalid_place_id_returns_field_error(self, mock_validate, org_and_admin):
        from apps.integrations.google.exceptions import PlaceIDNotFoundError

        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        mock_validate.side_effect = PlaceIDNotFoundError()
        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "Bad Place",
                "connection_method": "MANUAL",
                "region": region.pk,
                "place_id": "ChIJBAD",
                "api_key": _API_KEY_VALID_2,
            },
        )
        assert resp.status_code == 400
        assert "place_id" in resp.data

    @patch("apps.shops.services.shops.validate_place_id")
    def test_create_manual_invalid_api_key_returns_field_error(self, mock_validate, org_and_admin):
        from apps.integrations.google.exceptions import APIKeyInvalidError

        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        mock_validate.side_effect = APIKeyInvalidError()
        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "Bad Key",
                "connection_method": "MANUAL",
                "region": region.pk,
                "place_id": "ChIJOK",
                "api_key": _API_KEY_BROKEN,
            },
        )
        assert resp.status_code == 400
        assert "api_key" in resp.data

    @patch("apps.shops.services.shops.validate_place_id")
    def test_create_manual_unreachable_returns_non_field_error(self, mock_validate, org_and_admin):
        from apps.integrations.google.exceptions import GoogleUnreachableError

        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        mock_validate.side_effect = GoogleUnreachableError()
        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "Unreachable",
                "connection_method": "MANUAL",
                "region": region.pk,
                "place_id": "ChIJOK",
                "api_key": _API_KEY_VALID_3,
            },
        )
        assert resp.status_code == 400
        assert "non_field_errors" in resp.data


# ---------------------------------------------------------------------------
# 3a. TestShopsApiCreateOAuthStateResolution (SHOP-13 — security-sensitive)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsApiCreateOAuthStateResolution:
    @patch("apps.shops.views.create_shop")
    def test_oauth_create_resolves_refresh_token_from_session(
        self, mock_create_shop, org_and_admin
    ):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)

        # Seed the session: state -> actual refresh token
        _seed_session(client, "oauth_token:STATE-XYZ", "1//actual-refresh-token")

        # Mock create_shop to return a Shop-like object
        fake_shop = ShopFactory.build(
            organisation=org,
            region=region,
            name="OAuth Shop",
            connection_method=Shop.ConnectionMethod.GOOGLE_OAUTH,
        )
        mock_create_shop.return_value = fake_shop

        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "OAuth Shop",
                "region": region.pk,
                "connection_method": "GOOGLE_OAUTH",
                "place_id": "ChIJOAUTH",
                # Frontend sends the OAuth state string here, NOT the raw token (SHOP-13)
                "google_refresh_token": "STATE-XYZ",
            },
        )
        assert resp.status_code == 201
        # Verify create_shop was called with the RESOLVED token, not the state string
        call_kwargs = mock_create_shop.call_args[1]
        assert call_kwargs["google_refresh_token"] == "1//actual-refresh-token"
        assert call_kwargs["google_refresh_token"] != "STATE-XYZ"

    @patch("apps.shops.views.create_shop")
    def test_oauth_create_consumes_session_token_after_use(self, mock_create_shop, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)

        _seed_session(client, "oauth_token:STATE-XYZ", "1//actual-refresh-token")

        fake_shop = ShopFactory.build(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.GOOGLE_OAUTH,
        )
        mock_create_shop.return_value = fake_shop

        client.post(
            "/api/v1/shops/",
            {
                "name": "OAuth Shop",
                "region": region.pk,
                "connection_method": "GOOGLE_OAUTH",
                "place_id": "ChIJOAUTH",
                "google_refresh_token": "STATE-XYZ",
            },
        )
        # Token must be consumed (single-use)
        session = client.session  # type: ignore[attr-defined]
        assert session.get("oauth_token:STATE-XYZ") is None

    def test_oauth_create_with_missing_session_state_returns_400(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)

        # No session key for "UNKNOWN-STATE"
        resp = client.post(
            "/api/v1/shops/",
            {
                "name": "OAuth Shop",
                "region": region.pk,
                "connection_method": "GOOGLE_OAUTH",
                "place_id": "ChIJOAUTH",
                "google_refresh_token": "UNKNOWN-STATE",
            },
        )
        assert resp.status_code == 400
        assert any("OAuth session expired" in str(e) for e in resp.data.get("non_field_errors", []))


# ---------------------------------------------------------------------------
# 4. TestShopsApiUpdate (SHOP-16)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsApiUpdate:
    def test_patch_name_succeeds(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(organisation=org, region=region, name="Old Name")
        resp = client.patch(f"/api/v1/shops/{shop.pk}/", {"name": "New Name"})
        assert resp.status_code == 200
        assert resp.data["name"] == "New Name"

    def test_patch_connection_method_rejected(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(organisation=org, region=region)
        resp = client.patch(f"/api/v1/shops/{shop.pk}/", {"connection_method": "MANUAL"})
        assert resp.status_code == 400
        assert "connection_method" in resp.data
        assert "cannot be modified" in str(resp.data["connection_method"][0]).lower()

    def test_patch_place_id_rejected(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(organisation=org, region=region)
        resp = client.patch(f"/api/v1/shops/{shop.pk}/", {"place_id": "ChIJLOCKED"})
        assert resp.status_code == 400
        assert "place_id" in resp.data

    def test_patch_api_key_rejected(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(organisation=org, region=region)
        resp = client.patch(f"/api/v1/shops/{shop.pk}/", {"api_key": _API_KEY_SHORT})
        assert resp.status_code == 400
        assert "api_key" in resp.data


# ---------------------------------------------------------------------------
# 5. TestShopsApiActions (SHOP-17/18/19/20/21)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsApiActions:
    def test_deactivate_action_returns_200(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(organisation=org, region=region, is_active=True)
        resp = client.post(f"/api/v1/shops/{shop.pk}/deactivate/")
        assert resp.status_code == 200
        assert resp.data["is_active"] is False
        shop.refresh_from_db()
        assert shop.is_active is False

    def test_activate_action_returns_200(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(organisation=org, region=region, is_active=False)
        resp = client.post(f"/api/v1/shops/{shop.pk}/activate/")
        assert resp.status_code == 200
        assert resp.data["is_active"] is True
        shop.refresh_from_db()
        assert shop.is_active is True

    def test_reveal_key_returns_decrypted_for_manual_shop(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.MANUAL,
            api_key=_API_KEY_REVEAL,
        )
        resp = client.post(f"/api/v1/shops/{shop.pk}/reveal_key/")
        assert resp.status_code == 200
        assert resp.data["api_key"] == _API_KEY_REVEAL

    def test_reveal_key_returns_400_for_oauth_shop(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.GOOGLE_OAUTH,
        )
        resp = client.post(f"/api/v1/shops/{shop.pk}/reveal_key/")
        assert resp.status_code == 400

    def test_reveal_key_writes_audit_log(self, org_and_admin):
        org, _admin, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.MANUAL,
            api_key=_API_KEY_AUDIT,
        )
        assert not ShopAuditLog.objects.filter(
            shop=shop, action=ShopAuditLog.Action.API_KEY_REVEALED
        ).exists()
        resp = client.post(f"/api/v1/shops/{shop.pk}/reveal_key/")
        assert resp.status_code == 200
        assert ShopAuditLog.objects.filter(
            shop=shop, action=ShopAuditLog.Action.API_KEY_REVEALED
        ).exists()

    @patch("apps.shops.services.shops.validate_place_id")
    def test_rotate_key_validates_via_places_api(self, mock_validate, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.MANUAL,
            place_id="ChIJROTATE",
            api_key=_API_KEY_OLD_1,
        )
        mock_validate.return_value = None
        resp = client.post(
            f"/api/v1/shops/{shop.pk}/rotate_key/",
            {"new_api_key": _API_KEY_NEW_1},
        )
        assert resp.status_code == 200
        mock_validate.assert_called_once()

    @patch("apps.shops.services.shops.validate_place_id")
    def test_rotate_key_invalid_returns_field_error(self, mock_validate, org_and_admin):
        from apps.integrations.google.exceptions import APIKeyInvalidError

        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.MANUAL,
            place_id="ChIJROTATE",
            api_key=_API_KEY_OLD_2,
        )
        mock_validate.side_effect = APIKeyInvalidError()
        resp = client.post(
            f"/api/v1/shops/{shop.pk}/rotate_key/",
            {"new_api_key": _API_KEY_BAD_1},
        )
        assert resp.status_code == 400
        assert "api_key" in resp.data

    @patch("apps.shops.services.shops.validate_place_id")
    def test_rotate_key_unreachable_does_not_replace(self, mock_validate, org_and_admin):
        from apps.integrations.google.exceptions import GoogleUnreachableError

        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        shop = ShopFactory(
            organisation=org,
            region=region,
            connection_method=Shop.ConnectionMethod.MANUAL,
            place_id="ChIJROTATE",
            api_key=_API_KEY_ORIGINAL,
        )
        mock_validate.side_effect = GoogleUnreachableError()
        resp = client.post(
            f"/api/v1/shops/{shop.pk}/rotate_key/",
            {"new_api_key": _API_KEY_NEW_2},
        )
        assert resp.status_code == 400
        assert "non_field_errors" in resp.data
        shop.refresh_from_db()
        # Original key must still be intact
        assert shop.api_key == _API_KEY_ORIGINAL


# ---------------------------------------------------------------------------
# 6. TestShopsListQueryCountCeiling (XMOD-04 / no N+1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsListQueryCountCeiling:
    def test_query_count_ceiling_25_shops(self, org_and_admin, assert_query_ceiling):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory.create_batch(25, organisation=org, region=region)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        assert_query_ceiling(ctx, max_queries=10)


# ---------------------------------------------------------------------------
# 7. TestShopsCrossTenantIsolation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsCrossTenantIsolation:
    def test_admin_a_cannot_list_org_b_shops(self, two_orgs_two_admins):
        d = two_orgs_two_admins
        ShopFactory(organisation=d["org_b"], name="OrgBOnly")
        ShopFactory(organisation=d["org_a"], name="OrgAOnly")
        client_a = APIClient()
        client_a.force_authenticate(user=d["admin_a"])
        resp = client_a.get("/api/v1/shops/")
        assert resp.status_code == 200
        names = [r["name"] for r in resp.data["results"]]
        assert "OrgAOnly" in names
        assert "OrgBOnly" not in names

    def test_admin_a_get_org_b_shop_returns_404(self, two_orgs_two_admins):
        d = two_orgs_two_admins
        shop_b = ShopFactory(organisation=d["org_b"])
        client_a = APIClient()
        client_a.force_authenticate(user=d["admin_a"])
        resp = client_a.get(f"/api/v1/shops/{shop_b.pk}/")
        assert resp.status_code == 404

    def test_admin_a_patch_org_b_shop_returns_404(self, two_orgs_two_admins):
        d = two_orgs_two_admins
        shop_b = ShopFactory(organisation=d["org_b"])
        client_a = APIClient()
        client_a.force_authenticate(user=d["admin_a"])
        resp = client_a.patch(f"/api/v1/shops/{shop_b.pk}/", {"name": "Hacked"})
        assert resp.status_code == 404

    def test_admin_a_deactivate_org_b_shop_returns_404(self, two_orgs_two_admins):
        d = two_orgs_two_admins
        shop_b = ShopFactory(organisation=d["org_b"])
        client_a = APIClient()
        client_a.force_authenticate(user=d["admin_a"])
        resp = client_a.post(f"/api/v1/shops/{shop_b.pk}/deactivate/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. TestOAuthStartView (SHOP-11)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOAuthStartView:
    @override_settings(**_OAUTH_SETTINGS)
    def test_returns_redirect_to_google(self, org_and_admin):
        _org, admin, _ = org_and_admin
        dj_client = Client()
        dj_client.force_login(admin)
        resp = dj_client.get("/oauth/google/start/")
        assert resp.status_code == 302
        assert resp["Location"].startswith("https://accounts.google.com")

    @override_settings(**_OAUTH_SETTINGS)
    def test_response_has_coop_header(self, org_and_admin):
        _org, admin, _ = org_and_admin
        dj_client = Client()
        dj_client.force_login(admin)
        resp = dj_client.get("/oauth/google/start/")
        assert resp["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"

    @override_settings(**_OAUTH_SETTINGS)
    def test_state_stored_in_session(self, org_and_admin):
        _org, admin, _ = org_and_admin
        dj_client = Client()
        dj_client.force_login(admin)
        resp = dj_client.get("/oauth/google/start/")
        assert resp.status_code == 302
        assert "oauth_state" in dj_client.session


# ---------------------------------------------------------------------------
# 9. TestOAuthCallbackView (SHOP-11/12)
# ---------------------------------------------------------------------------


MOCK_LISTINGS = [
    {"name": "My Cafe", "address": "123 Main St", "place_id": "ChIJCAFE"},
    {"name": "My Bakery", "address": "456 Elm St", "place_id": "ChIJBAKERY"},
]


@pytest.mark.django_db
class TestOAuthCallbackView:
    def _dj_client_with_session(self, user: object, session_data: dict) -> Client:
        c = Client()
        c.force_login(user)  # type: ignore[arg-type]
        session = c.session
        for k, v in session_data.items():
            session[k] = v
        session.save()
        return c

    @patch("apps.shops.views.exchange_code_for_token")
    @patch("apps.shops.views.list_business_locations")
    def test_callback_no_listings_renders_error(self, mock_list_locs, mock_exchange, org_and_admin):
        _org, admin, _ = org_and_admin
        mock_exchange.return_value = {"refresh_token": "1//TOKENX"}
        mock_list_locs.return_value = []

        dj_client = self._dj_client_with_session(admin, {"oauth_state": "TESTSTATE"})
        resp = dj_client.get(
            "/oauth/google/callback/",
            {"state": "TESTSTATE", "code": "AUTH-CODE"},
        )
        assert resp.status_code == 200
        assert b"no_listings" in resp.content
        assert resp["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"

    @patch("apps.shops.views.exchange_code_for_token")
    @patch("apps.shops.views.list_business_locations")
    def test_callback_single_listing_renders_auto_close_script(
        self, mock_list_locs, mock_exchange, org_and_admin
    ):
        _org, admin, _ = org_and_admin
        mock_exchange.return_value = {"refresh_token": "1//TOKENX"}
        mock_list_locs.return_value = [MOCK_LISTINGS[0]]

        dj_client = self._dj_client_with_session(admin, {"oauth_state": "TESTSTATE"})
        resp = dj_client.get(
            "/oauth/google/callback/",
            {"state": "TESTSTATE", "code": "AUTH-CODE"},
        )
        assert resp.status_code == 200
        assert b"window.opener" in resp.content
        assert b"oauth_success" in resp.content
        assert b"setTimeout" in resp.content
        assert resp["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"

    @patch("apps.shops.views.exchange_code_for_token")
    @patch("apps.shops.views.list_business_locations")
    def test_callback_multiple_listings_renders_picker(
        self, mock_list_locs, mock_exchange, org_and_admin
    ):
        _org, admin, _ = org_and_admin
        mock_exchange.return_value = {"refresh_token": "1//TOKENX"}
        mock_list_locs.return_value = MOCK_LISTINGS  # 2 listings

        dj_client = self._dj_client_with_session(admin, {"oauth_state": "TESTSTATE"})
        resp = dj_client.get(
            "/oauth/google/callback/",
            {"state": "TESTSTATE", "code": "AUTH-CODE"},
        )
        assert resp.status_code == 200
        assert b"<form" in resp.content
        assert b"My Cafe" in resp.content
        assert b"My Bakery" in resp.content

    def test_callback_user_denied_renders_error(self, org_and_admin):
        _org, admin, _ = org_and_admin
        dj_client = self._dj_client_with_session(admin, {"oauth_state": "TESTSTATE"})
        resp = dj_client.get(
            "/oauth/google/callback/",
            {"state": "TESTSTATE", "error": "access_denied"},
        )
        assert resp.status_code == 200
        assert b"denied" in resp.content

    def test_callback_state_mismatch_renders_error(self, org_and_admin):
        _org, admin, _ = org_and_admin
        dj_client = self._dj_client_with_session(admin, {"oauth_state": "REAL-STATE"})
        resp = dj_client.get(
            "/oauth/google/callback/",
            {"state": "WRONG-STATE", "code": "AUTH-CODE"},
        )
        assert resp.status_code == 200
        assert b"auth_error" in resp.content


# ---------------------------------------------------------------------------
# 9a. TestOAuthResultEndpoint (SHOP-11 polling fallback)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOAuthResultEndpoint:
    @patch("apps.shops.views.get_redis_connection")
    def test_oauth_result_falls_back_to_session_state_when_no_query_param(
        self, mock_redis, org_and_admin
    ):
        _, _, client = org_and_admin
        _seed_session(client, "oauth_state", "STATE-X")

        redis_data = json.dumps({"type": "oauth_success", "state": "STATE-X", "listings": []})
        mock_conn = MagicMock()
        mock_conn.get.return_value = redis_data.encode()
        mock_redis.return_value = mock_conn

        # No ?state= query param — relies on session fallback
        resp = client.get("/api/v1/shops/oauth_result/")
        assert resp.status_code == 200
        assert resp.data["type"] == "oauth_success"
        # Verify Redis was queried with the session state (not some other state)
        mock_conn.get.assert_called_once_with("oauth:result:STATE-X")

    def test_oauth_result_no_state_anywhere_returns_204(self, org_and_admin):
        _, _, client = org_and_admin
        with patch("apps.shops.views.get_redis_connection") as mock_redis:
            mock_conn = MagicMock()
            mock_conn.get.return_value = None
            mock_redis.return_value = mock_conn
            resp = client.get("/api/v1/shops/oauth_result/")
        assert resp.status_code == 204

    @patch("apps.shops.views.get_redis_connection")
    def test_oauth_result_query_param_takes_priority_over_session(self, mock_redis, org_and_admin):
        _, _, client = org_and_admin
        # Seed session with a different state
        _seed_session(client, "oauth_state", "SESSION-STATE")

        redis_data = json.dumps({"type": "oauth_success", "state": "PARAM-STATE", "listings": []})
        mock_conn = MagicMock()
        mock_conn.get.return_value = redis_data.encode()
        mock_redis.return_value = mock_conn

        # Pass ?state= query param — should take priority
        resp = client.get("/api/v1/shops/oauth_result/?state=PARAM-STATE")
        assert resp.status_code == 200
        # Redis must be queried with the QUERY PARAM state, not the session state
        mock_conn.get.assert_called_once_with("oauth:result:PARAM-STATE")


# ---------------------------------------------------------------------------
# 10. TestShopsListPagination (SHOP-06)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestShopsListPagination:
    def test_default_page_size_10(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory.create_batch(15, organisation=org, region=region)
        resp = client.get("/api/v1/shops/")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 10
        assert resp.data["count"] == 15

    def test_page_size_query_param_overrides(self, org_and_admin):
        org, _, client = org_and_admin
        region = RegionFactory(organisation=org)
        ShopFactory.create_batch(15, organisation=org, region=region)
        resp = client.get("/api/v1/shops/?page_size=25")
        assert resp.status_code == 200
        # All 15 fit in a single page of 25
        assert len(resp.data["results"]) == 15
