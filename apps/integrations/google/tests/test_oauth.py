from __future__ import annotations

from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from django.test import override_settings

from apps.integrations.google.exceptions import GoogleAuthError, GoogleUnreachableError
from apps.integrations.google.oauth import (
    build_auth_url,
    exchange_code_for_token,
    list_business_locations,
)

SETTINGS = {
    "GOOGLE_OAUTH_CLIENT_ID": "test-client",
    "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
    "GOOGLE_OAUTH_REDIRECT_URI": "http://testserver/oauth/google/callback/",
}


def _resp(status_code: int, body: dict | None = None) -> Mock:
    m = Mock(spec=httpx.Response)
    m.status_code = status_code
    m.json.return_value = body or {}
    return m


class TestBuildAuthUrl:
    @override_settings(**SETTINGS)
    def test_contains_required_params(self):
        url = build_auth_url(state="abc123")
        parsed = urlparse(url)
        assert parsed.netloc == "accounts.google.com"
        assert parsed.path == "/o/oauth2/v2/auth"
        qs = parse_qs(parsed.query)
        assert qs["client_id"] == ["test-client"]
        assert qs["redirect_uri"] == ["http://testserver/oauth/google/callback/"]
        assert qs["response_type"] == ["code"]
        assert qs["scope"] == ["https://www.googleapis.com/auth/business.manage"]
        assert qs["access_type"] == ["offline"]
        assert qs["prompt"] == ["consent"]
        assert qs["state"] == ["abc123"]


class TestExchangeCodeForToken:
    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_returns_token_dict_on_200(self, mock_post):
        mock_post.return_value = _resp(200, {"refresh_token": "1//rt", "access_token": "ya29"})
        result = exchange_code_for_token(code="auth-code")
        assert result["refresh_token"] == "1//rt"

    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_4xx_raises_google_auth_error(self, mock_post):
        mock_post.return_value = _resp(
            400, {"error": "invalid_grant", "error_description": "Bad code"}
        )
        with pytest.raises(GoogleAuthError) as exc:
            exchange_code_for_token(code="bad")
        assert "Bad code" in exc.value.reason or "invalid_grant" in exc.value.reason

    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_transport_error_raises_google_unreachable_error(self, mock_post):
        mock_post.side_effect = httpx.TransportError("net")
        with pytest.raises(GoogleUnreachableError):
            exchange_code_for_token(code="auth-code")

    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_missing_refresh_token_raises_google_auth_error(self, mock_post):
        mock_post.return_value = _resp(200, {"access_token": "ya29"})
        with pytest.raises(GoogleAuthError) as exc:
            exchange_code_for_token(code="auth-code")
        assert exc.value.reason == "missing_refresh_token"


class TestListBusinessLocations:
    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.get")
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_returns_listings(self, mock_post, mock_get):
        mock_post.return_value = _resp(200, {"access_token": "ya29"})
        accounts_resp = _resp(200, {"accounts": [{"name": "accounts/123"}]})
        loc_resp = _resp(
            200,
            {
                "locations": [
                    {
                        "title": "ACME Cafe",
                        "storefrontAddress": {
                            "addressLines": ["123 Main St"],
                            "locality": "London",
                            "administrativeArea": "GBR",
                            "postalCode": "EC1",
                        },
                        "metadata": {"placeId": "ChIJabc"},
                    }
                ]
            },
        )
        mock_get.side_effect = [accounts_resp, loc_resp]
        result = list_business_locations(refresh_token="rt")
        assert len(result) == 1
        assert result[0]["name"] == "ACME Cafe"
        assert "London" in result[0]["address"]
        assert result[0]["place_id"] == "ChIJabc"

    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.get")
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_401_raises_google_auth_error_invalid_grant(self, mock_post, mock_get):
        mock_post.return_value = _resp(200, {"access_token": "ya29"})
        mock_get.return_value = _resp(401)
        with pytest.raises(GoogleAuthError) as exc:
            list_business_locations(refresh_token="rt")
        assert exc.value.reason == "invalid_grant"

    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_transport_error_raises_google_unreachable_error(self, mock_post):
        mock_post.side_effect = httpx.TransportError("net")
        with pytest.raises(GoogleUnreachableError):
            list_business_locations(refresh_token="rt")

    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.get")
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_listings_include_account_name_and_location_name(self, mock_post, mock_get):
        """Phase 11-08 Task 1: listings expose account_name and location_name."""
        mock_post.return_value = _resp(200, {"access_token": "ya29"})
        accounts_resp = _resp(200, {"accounts": [{"name": "accounts/123"}]})
        loc_resp = _resp(
            200,
            {
                "locations": [
                    {
                        "name": "locations/456",
                        "title": "ACME Cafe",
                        "storefrontAddress": {
                            "addressLines": ["123 Main St"],
                            "locality": "London",
                        },
                        "metadata": {"placeId": "ChIJabc"},
                    }
                ]
            },
        )
        mock_get.side_effect = [accounts_resp, loc_resp]
        result = list_business_locations(refresh_token="rt")
        assert len(result) == 1
        listing = result[0]
        assert listing["account_name"] == "accounts/123"
        assert listing["location_name"] == "accounts/123/locations/456"
        assert listing["place_id"] == "ChIJabc"

    @override_settings(**SETTINGS)
    @patch("apps.integrations.google.oauth.httpx.get")
    @patch("apps.integrations.google.oauth.httpx.post")
    def test_listing_location_name_already_full_path_not_duplicated(self, mock_post, mock_get):
        """If GBP returns full resource path in 'name', don't prepend account_name."""
        mock_post.return_value = _resp(200, {"access_token": "ya29"})
        accounts_resp = _resp(200, {"accounts": [{"name": "accounts/123"}]})
        loc_resp = _resp(
            200,
            {
                "locations": [
                    {
                        "name": "accounts/123/locations/789",
                        "title": "Full Path Cafe",
                        "storefrontAddress": {},
                        "metadata": {"placeId": "ChIJfull"},
                    }
                ]
            },
        )
        mock_get.side_effect = [accounts_resp, loc_resp]
        result = list_business_locations(refresh_token="rt")
        assert result[0]["location_name"] == "accounts/123/locations/789"
