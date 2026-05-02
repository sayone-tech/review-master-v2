"""Phase 11 — GBP Reviews API client tests using httpx.MockTransport."""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from apps.integrations.google.exceptions import (
    GoogleAuthError,
    GoogleQuotaError,
    GoogleReplyError,
    GoogleUnreachableError,
)
from apps.integrations.google.reviews_client import list_reviews, post_reply


def _mock_get(status_code: int, body: dict | str = "") -> object:
    def transport(request: httpx.Request) -> httpx.Response:
        if isinstance(body, dict):
            return httpx.Response(status_code, json=body)
        return httpx.Response(status_code, text=str(body))
    return httpx.MockTransport(transport)


def _patch_httpx_get(transport: httpx.MockTransport):
    """Patch module-level httpx.get to use a MockTransport-backed Client."""
    client = httpx.Client(transport=transport)
    return patch("apps.integrations.google.reviews_client.httpx.get", side_effect=client.get)


def _patch_httpx_put(transport: httpx.MockTransport):
    client = httpx.Client(transport=transport)
    return patch("apps.integrations.google.reviews_client.httpx.put", side_effect=client.put)


class TestListReviews:
    def test_success_returns_payload(self) -> None:
        payload = {"reviews": [{"reviewId": "abc", "starRating": "FIVE"}], "totalReviewCount": 1}
        with _patch_httpx_get(_mock_get(200, payload)):
            data = list_reviews(
                access_token="t",
                account_name="accounts/123",
                location_name="accounts/123/locations/456",
            )
        assert data["reviews"][0]["reviewId"] == "abc"
        assert data["totalReviewCount"] == 1

    def test_401_raises_invalid_grant(self) -> None:
        with _patch_httpx_get(_mock_get(401, {})):
            with pytest.raises(GoogleAuthError) as exc:
                list_reviews(
                    access_token="t",
                    account_name="accounts/123",
                    location_name="accounts/123/locations/456",
                )
        assert exc.value.reason == "invalid_grant"

    def test_403_raises_quota_error(self) -> None:
        with _patch_httpx_get(_mock_get(403, {})):
            with pytest.raises(GoogleQuotaError):
                list_reviews(
                    access_token="t",
                    account_name="accounts/123",
                    location_name="accounts/123/locations/456",
                )

    def test_500_raises_unreachable(self) -> None:
        with _patch_httpx_get(_mock_get(500, {})):
            with pytest.raises(GoogleUnreachableError):
                list_reviews(
                    access_token="t",
                    account_name="accounts/123",
                    location_name="accounts/123/locations/456",
                )

    def test_pagetoken_passed_through(self) -> None:
        captured = {}

        def transport(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json={"reviews": []})

        client = httpx.Client(transport=httpx.MockTransport(transport))
        with patch("apps.integrations.google.reviews_client.httpx.get", side_effect=client.get):
            list_reviews(
                access_token="t",
                account_name="accounts/123",
                location_name="accounts/123/locations/456",
                page_token="next-tok",
            )
        assert "pageToken=next-tok" in captured["url"]


class TestPostReply:
    def test_success_returns_payload(self) -> None:
        payload = {"comment": "Thanks!", "updateTime": "2026-05-01T12:00:00Z"}
        with _patch_httpx_put(_mock_get(200, payload)):
            data = post_reply(
                access_token="t",
                account_name="accounts/123",
                location_name="accounts/123/locations/456",
                review_id="rev-1",
                comment="Thanks!",
            )
        assert data["comment"] == "Thanks!"

    def test_401_raises_invalid_grant(self) -> None:
        with _patch_httpx_put(_mock_get(401, {})):
            with pytest.raises(GoogleAuthError):
                post_reply(
                    access_token="t",
                    account_name="accounts/123",
                    location_name="accounts/123/locations/456",
                    review_id="rev-1",
                    comment="Thanks!",
                )

    def test_400_raises_reply_error(self) -> None:
        with _patch_httpx_put(_mock_get(400, "invalid comment")), pytest.raises(
            GoogleReplyError
        ) as exc:
            post_reply(
                access_token="t",
                account_name="accounts/123",
                location_name="accounts/123/locations/456",
                review_id="rev-1",
                comment="bad",
            )
        assert exc.value.status == 400
