"""Phase 19 — AI reply generation service. Calls OpenAI and writes AiUsageLog per D-14/D-15/D-16.

Architecture (CLAUDE.md §5):
  - The view (Plan 19-02) calls generate_reply_draft and returns the result.
  - Business logic (OpenAI call orchestration + cost tracking) lives here.
  - The client wrapper (apps/integrations/openai/client.py) hides the SDK.

Phase 20 (Plan 20-06): input + output moderation and 300-word sentence
truncation are wired around the OpenAI call per D-07 / D-08 / D-14 / D-22 /
D-29 / D-33. Both moderate_* calls run OUTSIDE any transaction.atomic block
so the MODERATED audit row written by guardrails survives caller rollbacks.

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
from apps.integrations.openai.guardrails import (
    ReviewWithModeratedComment,
    moderate_input,
    moderate_output,
    truncate_reply_at_sentence,
)
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.pricing import calculate_cost
from apps.integrations.openai.prompts import ALLOWED_REPLY_TONES
from apps.reviews.models import Review

logger = logging.getLogger(__name__)

# WR-03: single source of truth lives in apps.integrations.openai.prompts.
_ALLOWED_TONES: frozenset[str] = frozenset(ALLOWED_REPLY_TONES)


# NOTE: `_ReviewWithModeratedComment` was hoisted to
# `apps.integrations.openai.guardrails.ReviewWithModeratedComment` so both
# this service and `enrich_review` share a single definition (WR-02).


def _write_failure_log(*, review: Review, exc: Exception) -> None:
    """Write a single FAILED AiUsageLog row. Never raises (best-effort).

    WR-04: AiUsageLog.error_message is a TextField (no max_length), so the
    full exception string is stored without truncation. Diagnostic context
    is preserved for support / Sentry cross-reference.
    """
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
            error_message=str(exc),
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
      - status=MODERATED (written by apps.integrations.openai.guardrails) on
        input or output moderation block; ContentModeratedException then
        propagates to the view (Plan 20-07) which maps to HTTP 422.
    """
    if tone not in _ALLOWED_TONES:
        raise ValueError(f"Unknown tone: {tone!r}")

    # D-14 / D-33: input moderation BEFORE the OpenAI call, OUTSIDE any
    # transaction.atomic() block so the MODERATED audit row survives a
    # caller-side rollback. ContentModeratedException propagates uncaught.
    truncated_comment = moderate_input(
        review.comment or "",
        review=review,
        request_type="reply_generation",
    )
    review_for_prompt = ReviewWithModeratedComment(review, truncated_comment)

    try:
        draft, usage_data = call_openai_reply_generation(
            review=review_for_prompt,
            tone=tone,
            model=settings.OPENAI_MODEL,
        )
    except (OpenAITransientError, OpenAIPermanentError) as exc:
        _write_failure_log(review=review, exc=exc)
        raise
    except Exception as exc:
        _write_failure_log(review=review, exc=exc)
        raise

    # WR-05: never let a missing AiPricing row swallow the SUCCESS log. The
    # OpenAI call has already been billed; we MUST record it. If pricing
    # lookup fails (e.g., seed migration missed for a new model), log the
    # call with estimated_cost_usd=0 + error_code="ai_pricing_lookup_failed"
    # so cost auditing surfaces the gap rather than silently undercounting.
    #
    # D-29: cost is computed BEFORE moderate_output and injected into
    # usage_data so the MODERATED row (if guardrails writes one) carries the
    # REAL estimated_cost_usd — the OpenAI call already consumed tokens.
    pricing_error_code = ""
    pricing_error_message = ""
    try:
        cost: Decimal = calculate_cost(
            model=settings.OPENAI_MODEL,
            prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
            completion_tokens=int(usage_data.get("completion_tokens") or 0),
            cached_tokens=int(usage_data.get("cached_tokens") or 0),
        )
    except Exception as exc:
        logger.exception("ai_pricing_lookup_failed model=%s", settings.OPENAI_MODEL)
        cost = Decimal("0")
        pricing_error_code = "ai_pricing_lookup_failed"
        pricing_error_message = str(exc)
    usage_data["estimated_cost_usd"] = cost

    # D-07 / D-29 / D-33: output moderation AFTER the OpenAI call and BEFORE
    # the SUCCESS AiUsageLog write. usage_data carries REAL prompt/completion
    # tokens AND real cost so guardrails writes an accurate MODERATED row on
    # a block. Outside any atomic block per D-33.
    moderate_output(
        draft,
        review=review,
        request_type="reply_generation",
        usage_data=usage_data,
    )

    # D-08 / D-22: 300-word sentence-boundary truncation applied AFTER output
    # moderation passes (length cap is a presentation transform of an
    # already-safe draft, not a safety gate).
    draft = truncate_reply_at_sentence(draft)

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
        error_code=pricing_error_code,
        error_message=pricing_error_message,
    )
    return draft
