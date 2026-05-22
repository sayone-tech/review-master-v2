"""Phase 19 — AI reply generation service. Calls OpenAI and writes AiUsageLog per D-14/D-15/D-16.

Architecture (CLAUDE.md §5):
  - The view (Plan 19-02) calls generate_reply_draft and returns the result.
  - Business logic (OpenAI call orchestration + cost tracking) lives here.
  - The client wrapper (apps/integrations/openai/client.py) hides the SDK.

Idempotency: Reply generation is a synchronous, user-initiated action — there
is NO Redis lock or three-layer pattern here (unlike enrichment in Phase 12).
Each click costs one OpenAI call. If the user clicks twice, that is two calls
intentionally; the view layer throttle (10/min/user, D-12) is the only guard.

Exception handling (D-17): every exception writes one FAILED AiUsageLog row
before propagating. The view layer maps these to HTTP 502.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings

from apps.integrations.openai.client import call_openai_reply_generation
from apps.integrations.openai.exceptions import (
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.pricing import calculate_cost
from apps.reviews.models import Review

logger = logging.getLogger(__name__)

_ALLOWED_TONES: frozenset[str] = frozenset({"professional", "friendly"})


def _write_failure_log(*, review: Review, exc: Exception) -> None:
    """Write a single FAILED AiUsageLog row. Never raises (best-effort)."""
    try:
        AiUsageLog.objects.create(
            organisation_id=review.organisation_id,
            review_id=review.pk,
            request_type="reply_generation",
            model=settings.OPENAI_MODEL,
            prompt_tokens=None,
            completion_tokens=None,
            cached_tokens=0,
            total_tokens=None,
            estimated_cost_usd=Decimal("0"),
            latency_ms=None,
            langsmith_trace_id="",
            status=AiUsageLog.Status.FAILED,
            error_code=type(exc).__name__,
            error_message=str(exc)[:500],
        )
    except Exception:  # pragma: no cover — defensive
        logger.exception("reply_generation_failed_log_write_failed review_id=%s", review.pk)


def generate_reply_draft(*, review: Review, tone: str) -> str:
    """Generate a reply draft for `review` using the requested tone.

    Returns the draft text. Writes exactly one AiUsageLog row per call:
      - status=SUCCESS on the happy path
      - status=FAILED for OpenAITransientError, OpenAIPermanentError, or any
        other exception (D-17); the original exception is then re-raised so
        the view layer can map it to HTTP 502.
    """
    if tone not in _ALLOWED_TONES:
        raise ValueError(f"Unknown tone: {tone!r}")

    try:
        draft, usage_data = call_openai_reply_generation(
            review=review,
            tone=tone,
            model=settings.OPENAI_MODEL,
        )
    except (OpenAITransientError, OpenAIPermanentError) as exc:
        _write_failure_log(review=review, exc=exc)
        raise
    except Exception as exc:
        _write_failure_log(review=review, exc=exc)
        raise

    cost = calculate_cost(
        model=settings.OPENAI_MODEL,
        prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
        completion_tokens=int(usage_data.get("completion_tokens") or 0),
        cached_tokens=int(usage_data.get("cached_tokens") or 0),
    )
    AiUsageLog.objects.create(
        organisation_id=review.organisation_id,
        review_id=review.pk,
        request_type="reply_generation",
        model=settings.OPENAI_MODEL,
        prompt_tokens=usage_data.get("prompt_tokens"),
        completion_tokens=usage_data.get("completion_tokens"),
        cached_tokens=usage_data.get("cached_tokens", 0) or 0,
        total_tokens=usage_data.get("total_tokens"),
        estimated_cost_usd=cost,
        latency_ms=usage_data.get("latency_ms"),
        langsmith_trace_id=usage_data.get("langsmith_trace_id") or "",
        status=AiUsageLog.Status.SUCCESS,
    )
    return draft
