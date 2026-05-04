from __future__ import annotations


class GoogleUnreachableError(Exception):
    """Raised when the Google API is unreachable due to network failure or timeout."""


class GoogleAuthError(Exception):
    """Raised when OAuth code exchange or token refresh fails (non-network error)."""

    def __init__(self, reason: str = "") -> None:
        self.reason = reason
        super().__init__(reason or "Google OAuth error.")


class PlaceIDNotFoundError(Exception):
    """Raised when the Places API rejects the place_id (NOT_FOUND / INVALID_REQUEST)."""


class APIKeyInvalidError(Exception):
    """Raised when the Places API returns REQUEST_DENIED (api_key invalid/unauthorised)."""


class GoogleQuotaError(Exception):
    """Raised when GBP returns 403 quota_exceeded — caller should retry with backoff."""


class GoogleReplyError(Exception):
    """Raised when posting a reply fails with a non-auth 4xx (e.g. 400 invalid comment)."""

    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self.body = body
        super().__init__(f"Reply rejected with status {status}: {body[:200]}")
