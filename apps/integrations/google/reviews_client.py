"""Google Business Profile Reviews API client.

GET  /v4/{accountName}/locations/{locationName}/reviews
PUT  /v4/{accountName}/locations/{locationName}/reviews/{reviewId}/reply

See 11-RESEARCH.md Pattern 3 for endpoint details and CLAUDE.md §11 for
retry/backoff rules. accountName and locationName are full resource paths
(e.g. "accounts/123" and "accounts/123/locations/456") stored on
shop.google_account_name and shop.google_location_name.
"""
from __future__ import annotations

from typing import Any

import httpx

from apps.integrations.google.exceptions import (
    GoogleAuthError,
    GoogleQuotaError,
    GoogleReplyError,
    GoogleUnreachableError,
)

REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"
REQUEST_TIMEOUT = 10.0
DEFAULT_PAGE_SIZE = 50


def _build_url(account_name: str, location_name: str, suffix: str = "") -> str:
    """Build a GBP reviews URL.

    account_name: e.g. "accounts/123" (full resource path)
    location_name: e.g. "accounts/123/locations/456" (full resource path) OR
                   bare "locations/456" — both supported; only the location
                   segment is appended.
    """
    # Normalise location_name to "locations/{id}" form
    loc = location_name
    if "/" in loc:
        loc = "locations/" + loc.rsplit("locations/", 1)[-1]
    base = f"{REVIEWS_BASE}/{account_name}/{loc}/reviews"
    return f"{base}{suffix}"


def list_reviews(
    *,
    access_token: str,
    account_name: str,
    location_name: str,
    page_token: str = "",
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """GET reviews page from GBP.

    Returns: {"reviews": [...], "totalReviewCount": int, "nextPageToken": str?}
    Raises:
        GoogleAuthError(reason="invalid_grant"): 401
        GoogleQuotaError: 403
        GoogleUnreachableError: 5xx or transport error
    """
    url = _build_url(account_name, location_name)
    params: dict[str, Any] = {"pageSize": min(page_size, DEFAULT_PAGE_SIZE)}
    if page_token:
        params["pageToken"] = page_token
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.TransportError as exc:
        raise GoogleUnreachableError() from exc

    if resp.status_code == 401:
        raise GoogleAuthError(reason="invalid_grant")
    if resp.status_code == 403:
        raise GoogleQuotaError()
    if resp.status_code >= 500:
        raise GoogleUnreachableError()
    if resp.status_code >= 400:
        # 4xx not 401/403 — treat as transient; raise unreachable so caller retries.
        raise GoogleUnreachableError()
    return resp.json()  # type: ignore[no-any-return]


def post_reply(
    *,
    access_token: str,
    account_name: str,
    location_name: str,
    review_id: str,
    comment: str,
) -> dict[str, Any]:
    """PUT reply to GBP review.

    Returns: {"comment": str, "updateTime": str (RFC 3339)}
    Raises:
        GoogleAuthError(reason="invalid_grant"): 401
        GoogleReplyError(status=...): 400, 404, etc. (non-auth 4xx)
        GoogleUnreachableError: 5xx or transport error
    """
    url = _build_url(account_name, location_name, suffix=f"/{review_id}/reply")
    try:
        resp = httpx.put(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"comment": comment},
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.TransportError as exc:
        raise GoogleUnreachableError() from exc

    if resp.status_code == 401:
        raise GoogleAuthError(reason="invalid_grant")
    if resp.status_code >= 500:
        raise GoogleUnreachableError()
    if resp.status_code >= 400:
        raise GoogleReplyError(status=resp.status_code, body=resp.text)
    return resp.json()  # type: ignore[no-any-return]
