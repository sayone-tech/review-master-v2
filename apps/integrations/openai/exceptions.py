"""Phase 12 — OpenAI exception hierarchy.

OpenAITransientError    -> Celery autoretry_for (429, 5xx)
OpenAIPermanentError    -> do not retry (4xx other than 429)
EnrichmentParseError    -> retry once (Pydantic validation failed)
"""

from __future__ import annotations


class OpenAIError(Exception):
    """Base exception for OpenAI integration."""


class OpenAITransientError(OpenAIError):
    """OpenAI 429 or 5xx — retried by Celery autoretry_for."""


class OpenAIPermanentError(OpenAIError):
    """OpenAI 4xx other than 429 — do not retry."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class EnrichmentParseError(OpenAIError):
    """Pydantic validation failed on response.output_parsed — retry once."""


class ContentModeratedException(OpenAIError):  # noqa: N818 — name fixed by plan 20-02 (D-16/D-32)
    """Raised when input or output content is blocked by moderation (Phase 20, D-16/D-32)."""
