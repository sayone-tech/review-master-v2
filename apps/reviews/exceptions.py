"""Phase 11 — Review-app domain exceptions."""

from __future__ import annotations


class ReplyConflictError(Exception):
    """Raised when a concurrent reply submission for the same review is in flight."""


class ReplyFailedError(Exception):
    """Raised when posting a reply to Google fails permanently for this attempt.

    The local Review row is NOT mutated. Caller (view) maps to HTTP 502.
    """

    def __init__(self, *, code: str, message: str = "") -> None:
        self.code = code
        self.message = message
        super().__init__(message or code)
