from __future__ import annotations

from unittest.mock import Mock, patch

import httpx
import pytest

from apps.integrations.google.exceptions import (
    APIKeyInvalidError,
    GoogleUnreachableError,
    PlaceIDNotFoundError,
)
from apps.integrations.google.places import validate_place_id


def _ok_response(json_body: dict) -> Mock:
    m = Mock(spec=httpx.Response)
    m.status_code = 200
    m.json.return_value = json_body
    return m


class TestValidatePlaceId:
    @patch("apps.integrations.google.places.httpx.get")
    def test_returns_result_on_ok_status(self, mock_get):
        mock_get.return_value = _ok_response({"status": "OK", "result": {"name": "ACME"}})
        assert validate_place_id(place_id="ChIJ123", api_key="AIza") == {"name": "ACME"}

    @patch("apps.integrations.google.places.httpx.get")
    def test_not_found_raises_place_id_not_found_error(self, mock_get):
        mock_get.return_value = _ok_response({"status": "NOT_FOUND"})
        with pytest.raises(PlaceIDNotFoundError):
            validate_place_id(place_id="bad", api_key="AIza")

    @patch("apps.integrations.google.places.httpx.get")
    def test_invalid_request_raises_place_id_not_found_error(self, mock_get):
        mock_get.return_value = _ok_response({"status": "INVALID_REQUEST"})
        with pytest.raises(PlaceIDNotFoundError):
            validate_place_id(place_id="x", api_key="AIza")

    @patch("apps.integrations.google.places.httpx.get")
    def test_request_denied_raises_api_key_invalid_error(self, mock_get):
        mock_get.return_value = _ok_response({"status": "REQUEST_DENIED"})
        with pytest.raises(APIKeyInvalidError):
            validate_place_id(place_id="ChIJ", api_key="bad")

    @patch("apps.integrations.google.places.httpx.get")
    def test_transport_error_raises_google_unreachable_error(self, mock_get):
        mock_get.side_effect = httpx.TransportError("network down")
        with pytest.raises(GoogleUnreachableError):
            validate_place_id(place_id="ChIJ", api_key="AIza")

    @patch("apps.integrations.google.places.httpx.get")
    def test_5xx_raises_google_unreachable_error(self, mock_get):
        m = Mock(spec=httpx.Response)
        m.status_code = 503
        mock_get.return_value = m
        with pytest.raises(GoogleUnreachableError):
            validate_place_id(place_id="ChIJ", api_key="AIza")

    @patch("apps.integrations.google.places.httpx.get")
    def test_retries_then_succeeds(self, mock_get):
        mock_get.side_effect = [
            httpx.TransportError("flaky"),
            httpx.TransportError("flaky"),
            _ok_response({"status": "OK", "result": {"name": "OK"}}),
        ]
        assert validate_place_id(place_id="ChIJ", api_key="AIza") == {"name": "OK"}
        assert mock_get.call_count == 3
