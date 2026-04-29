from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from apps.integrations.google.exceptions import (
    APIKeyInvalidError,
    GoogleUnreachableError,
    PlaceIDNotFoundError,
)

PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/details/json"
REQUEST_TIMEOUT = 10.0


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _places_get(params: dict[str, str]) -> httpx.Response:
    return httpx.get(PLACES_API_URL, params=params, timeout=REQUEST_TIMEOUT)


def validate_place_id(*, place_id: str, api_key: str) -> dict[str, Any]:
    """Validate a Google Place ID + API key.

    Returns the Places API "result" dict on success.
    Raises:
        GoogleUnreachableError: network failure, 5xx, or unknown status.
        PlaceIDNotFoundError: Places API status == NOT_FOUND or INVALID_REQUEST.
        APIKeyInvalidError: Places API status == REQUEST_DENIED.
    """
    params = {"place_id": place_id, "key": api_key, "fields": "name,formatted_address"}
    try:
        resp = _places_get(params)
    except httpx.TransportError as exc:
        raise GoogleUnreachableError() from exc
    except RetryError as exc:
        raise GoogleUnreachableError() from exc

    if resp.status_code >= 500:
        raise GoogleUnreachableError()
    if resp.status_code != 200:
        raise GoogleUnreachableError()

    body = resp.json()
    status = body.get("status", "")
    if status == "OK":
        return body.get("result", {})  # type: ignore[no-any-return]
    if status in ("NOT_FOUND", "INVALID_REQUEST"):
        raise PlaceIDNotFoundError()
    if status == "REQUEST_DENIED":
        raise APIKeyInvalidError()
    raise GoogleUnreachableError()
