from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlencode

import httpx
from django.conf import settings
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.integrations.google.exceptions import (
    GoogleAuthError,
    GoogleUnreachableError,
)

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105  # nosec B105
ACCOUNTS_ENDPOINT = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
LOCATIONS_ENDPOINT_TMPL = (
    "https://mybusinessbusinessinformation.googleapis.com/v1/{account}/locations"
    "?readMask=name,title,storefrontAddress,metadata"
)
SCOPE = "https://www.googleapis.com/auth/business.manage"
REQUEST_TIMEOUT = 10.0

_RETRY = retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)


def _setting(name: str) -> str:
    """Retrieve a string setting from Django settings, defaulting to empty string."""
    return cast(str, getattr(settings, name, ""))


def build_auth_url(*, state: str) -> str:
    """Build the Google OAuth 2.0 authorization URL with the required scopes and state."""
    params = {
        "client_id": _setting("GOOGLE_OAUTH_CLIENT_ID"),
        "redirect_uri": _setting("GOOGLE_OAUTH_REDIRECT_URI"),
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


@_RETRY
def _post_token(data: dict[str, str]) -> httpx.Response:
    return httpx.post(TOKEN_ENDPOINT, data=data, timeout=REQUEST_TIMEOUT)


def exchange_code_for_token(*, code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for a token response dict.

    Returns the full token dict (contains refresh_token and access_token).
    Raises:
        GoogleUnreachableError: transport error or 5xx.
        GoogleAuthError: 4xx or response missing refresh_token.
    """
    data = {
        "code": code,
        "client_id": _setting("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": _setting("GOOGLE_OAUTH_CLIENT_SECRET"),
        "redirect_uri": _setting("GOOGLE_OAUTH_REDIRECT_URI"),
        "grant_type": "authorization_code",
    }
    try:
        resp = _post_token(data)
    except (httpx.TransportError, RetryError) as exc:
        raise GoogleUnreachableError() from exc
    if resp.status_code >= 500:
        raise GoogleUnreachableError()
    body = resp.json()
    if resp.status_code != 200:
        raise GoogleAuthError(reason=str(body.get("error_description") or body.get("error", "")))
    if "refresh_token" not in body:
        raise GoogleAuthError(reason="missing_refresh_token")
    return body  # type: ignore[no-any-return]


def _refresh_access_token(refresh_token: str) -> str:
    """Exchange a refresh token for a short-lived access token."""
    data = {
        "refresh_token": refresh_token,
        "client_id": _setting("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": _setting("GOOGLE_OAUTH_CLIENT_SECRET"),
        "grant_type": "refresh_token",
    }
    try:
        resp = _post_token(data)
    except (httpx.TransportError, RetryError) as exc:
        raise GoogleUnreachableError() from exc
    if resp.status_code == 401:
        raise GoogleAuthError(reason="invalid_grant")
    if resp.status_code != 200:
        raise GoogleUnreachableError()
    token = resp.json().get("access_token", "")
    if not token:
        raise GoogleAuthError(reason="missing_access_token")
    return str(token)


@_RETRY
def _bearer_get(url: str, access_token: str) -> httpx.Response:
    return httpx.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=REQUEST_TIMEOUT,
    )


def list_business_locations(*, refresh_token: str) -> list[dict[str, str]]:
    """List all Google Business Profile locations for an authenticated account.

    Refreshes the access token first, then lists accounts and their locations.
    Returns a flat list of dicts shaped: [{name, address, place_id}].
    Raises:
        GoogleUnreachableError: network failure or non-auth server error.
        GoogleAuthError: 401 (token expired/revoked) — reason="invalid_grant".
    """
    access_token = _refresh_access_token(refresh_token)
    # 1. List accounts
    try:
        accounts_resp = _bearer_get(ACCOUNTS_ENDPOINT, access_token)
    except (httpx.TransportError, RetryError) as exc:
        raise GoogleUnreachableError() from exc
    if accounts_resp.status_code == 401:
        raise GoogleAuthError(reason="invalid_grant")
    if accounts_resp.status_code != 200:
        raise GoogleUnreachableError()
    accounts = accounts_resp.json().get("accounts", [])
    # 2. For each account, list locations and flatten
    listings: list[dict[str, str]] = []
    for acc in accounts:
        account_name = acc.get("name", "")
        if not account_name:
            continue
        url = LOCATIONS_ENDPOINT_TMPL.format(account=account_name)
        try:
            loc_resp = _bearer_get(url, access_token)
        except (httpx.TransportError, RetryError) as exc:
            raise GoogleUnreachableError() from exc
        if loc_resp.status_code == 401:
            raise GoogleAuthError(reason="invalid_grant")
        if loc_resp.status_code != 200:
            raise GoogleUnreachableError()
        for loc in loc_resp.json().get("locations", []):
            addr_obj = loc.get("storefrontAddress") or {}
            address_lines = addr_obj.get("addressLines", [])
            locality = addr_obj.get("locality", "")
            region = addr_obj.get("administrativeArea", "")
            postal = addr_obj.get("postalCode", "")
            address = ", ".join(p for p in [*address_lines, locality, region, postal] if p)
            location_name = str(loc.get("name", ""))  # e.g. "locations/456" or full path
            # Build the full resource name for the GBP Reviews API (required by Phase 11).
            full_location_name = (
                location_name
                if location_name.startswith("accounts/")
                else f"{account_name}/{location_name}"
            )
            listings.append(
                {
                    "name": str(loc.get("title", "")),
                    "address": address,
                    "place_id": str((loc.get("metadata") or {}).get("placeId", "")),
                    "account_name": account_name,
                    "location_name": full_location_name,
                }
            )
    return listings
