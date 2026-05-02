"""Phase 12 — Review enrichment service.

Implements three-layer idempotency (CLAUDE.md §12.4):
  Layer 1: Redis lock per review (lock:enrich:review:{review_id}, 5-min TTL)
  Layer 2: transaction.atomic() + select_for_update on the Review row
  Layer 3: status flag — exit if SUCCESS or IN_PROGRESS

The OpenAI HTTP call happens OUTSIDE transaction.atomic() — holding a row lock
during a slow HTTP call is an anti-pattern (RESEARCH.md anti-patterns).

Errors are mapped per ENRCH-04:
  OpenAITransientError    -> persist FAILED + raise (Celery autoretry_for)
  EnrichmentParseError    -> persist FAILED + raise (retry once via autoretry)
  OpenAIPermanentError    -> persist FAILED + return (no retry per ENRCH-04)

enrichment_version is incremented on every terminal transition (SUCCESS or
FAILED). retry_failed_enrichments_task uses enrichment_version < 3 as its
attempt cap (RESEARCH.md Open Question 3).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone as dj_timezone

from apps.common.locks import distributed_lock
from apps.integrations.openai.client import call_openai_enrichment
from apps.integrations.openai.exceptions import (
    EnrichmentParseError,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.pricing import calculate_cost
from apps.reviews.models import Review

logger = logging.getLogger(__name__)

LOCK_KEY_TMPL = "lock:enrich:review:{review_id}"
LOCK_TIMEOUT_SECONDS = 300


def _persist_success(
    *,
    review: Review,
    result: Any,
    usage_data: dict[str, Any],
) -> None:
    """Write SUCCESS state + AiUsageLog row. ENRCH-07 + ENRCH-08 + ENRCH-12."""
    cost = calculate_cost(
        model=settings.OPENAI_MODEL,
        prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
        completion_tokens=int(usage_data.get("completion_tokens") or 0),
        cached_tokens=int(usage_data.get("cached_tokens") or 0),
    )
    with transaction.atomic():
        Review.objects.filter(pk=review.pk).update(
            enrichment_status=Review.EnrichmentStatus.SUCCESS,
            sentiment=result.sentiment,
            tags=[{"label": t.label, "polarity": t.polarity} for t in result.tags],
            extracted_action_items=[
                {"title": a.title, "scope": a.scope, "priority": a.priority}
                for a in result.action_items
            ],
            enrichment_version=models.F("enrichment_version") + 1,
        )
        AiUsageLog.objects.create(
            organisation_id=review.organisation_id,
            review_id=review.pk,
            request_type="enrichment",
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


def _persist_failure(
    *,
    review: Review,
    usage_data: dict[str, Any] | None,
    exc: Exception,
) -> None:
    """Write FAILED state + AiUsageLog row. ENRCH-04 + ENRCH-05."""
    usage = usage_data or {}
    with transaction.atomic():
        Review.objects.filter(pk=review.pk).update(
            enrichment_status=Review.EnrichmentStatus.FAILED,
            sentiment="",
            enrichment_version=models.F("enrichment_version") + 1,
        )
        AiUsageLog.objects.create(
            organisation_id=review.organisation_id,
            review_id=review.pk,
            request_type="enrichment",
            model=settings.OPENAI_MODEL,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            cached_tokens=usage.get("cached_tokens", 0) or 0,
            total_tokens=usage.get("total_tokens"),
            estimated_cost_usd=Decimal("0"),
            latency_ms=usage.get("latency_ms"),
            langsmith_trace_id=usage.get("langsmith_trace_id") or "",
            status=AiUsageLog.Status.FAILED,
            error_code=type(exc).__name__,
            error_message=str(exc)[:1000],
        )


def enrich_review(*, review_id: int) -> None:
    """Enrich a review with three-layer idempotency. See module docstring.

    Returns None. Raises OpenAITransientError or EnrichmentParseError so
    Celery autoretry_for can apply exponential backoff. OpenAIPermanentError
    is caught silently (ENRCH-04: no retry on 4xx other than 429).
    """
    lock_key = LOCK_KEY_TMPL.format(review_id=review_id)
    with distributed_lock(lock_key, timeout=LOCK_TIMEOUT_SECONDS) as acquired:
        if not acquired:
            logger.info("enrich_review_lock_held review_id=%s", review_id)
            return

        # Layer 2 + 3: short transaction transitioning PENDING -> IN_PROGRESS.
        with transaction.atomic():
            try:
                review = (
                    Review.objects.select_related("shop__organisation")
                    .select_for_update()
                    .get(pk=review_id)
                )
            except Review.DoesNotExist:
                logger.warning("enrich_review_missing review_id=%s", review_id)
                return
            if review.enrichment_status in (
                Review.EnrichmentStatus.SUCCESS,
                Review.EnrichmentStatus.IN_PROGRESS,
            ):
                logger.info(
                    "enrich_review_idempotent_skip review_id=%s status=%s",
                    review_id,
                    review.enrichment_status,
                )
                return
            review.enrichment_status = Review.EnrichmentStatus.IN_PROGRESS
            review.enrichment_attempted_at = dj_timezone.now()
            review.save(update_fields=["enrichment_status", "enrichment_attempted_at"])

        # OpenAI call OUTSIDE the transaction (RESEARCH.md anti-pattern).
        try:
            result, usage_data = call_openai_enrichment(review=review)
        except (OpenAITransientError, EnrichmentParseError) as exc:
            _persist_failure(review=review, usage_data=None, exc=exc)
            raise  # Celery autoretry_for picks this up
        except OpenAIPermanentError as exc:
            _persist_failure(review=review, usage_data=None, exc=exc)
            return  # ENRCH-04: do not retry on 4xx other than 429

        _persist_success(review=review, result=result, usage_data=usage_data)
