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

# Phase 12-09 (gap closure): mapping for comment-less reviews that skip OpenAI.
# Rating-only Google Business Profile reviews have no text for the LLM to
# analyse, so sentiment is derived locally from the star rating instead.
RATING_TO_SENTIMENT: dict[int, str] = {
    1: "negative",
    2: "negative",
    3: "neutral",
    4: "positive",
    5: "positive",
}


def rating_to_sentiment(star_rating: int) -> str:
    """Map a 1-5 star rating to sentiment for comment-less reviews.

    Used when the review has no comment text and we cannot call OpenAI.
    Returns 'negative' (1-2), 'neutral' (3), or 'positive' (4-5).
    Falls back to 'neutral' for unexpected values (defensive).
    """
    return RATING_TO_SENTIMENT.get(int(star_rating), "neutral")


def _persist_success(
    *,
    review: Review,
    result: Any,
    usage_data: dict[str, Any],
) -> None:
    """Write SUCCESS state + AiUsageLog row. ENRCH-07 + ENRCH-08 + ENRCH-12.

    Phase 12-06: also emits sync.enrichment.progress (and gated sync.complete)
    AFTER the transaction commits (RESEARCH.md anti-pattern: events inside txns).
    """
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

    # AFTER commit: emit progress event for the live ProgressModal.
    _emit_enrichment_progress(review=review)


def _persist_success_no_comment(*, review: Review) -> None:
    """Skip-OpenAI success path for comment-less reviews (Phase 12-09).

    Writes sentiment derived from star_rating, empty tags, empty
    extracted_action_items, status=SUCCESS, bumps enrichment_version. NO
    AiUsageLog row is written — this path incurs ZERO OpenAI cost.

    Emits the same post-commit progress event as a normal success so the live
    ProgressModal counter advances correctly.
    """
    sentiment_value = rating_to_sentiment(review.star_rating)
    with transaction.atomic():
        Review.objects.filter(pk=review.pk).update(
            enrichment_status=Review.EnrichmentStatus.SUCCESS,
            sentiment=sentiment_value,
            tags=[],
            extracted_action_items=[],
            enrichment_version=models.F("enrichment_version") + 1,
        )

    # AFTER commit: emit progress so the modal counter increments
    # identically to a normal enrichment.
    _emit_enrichment_progress(review=review)


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


def _emit_enrichment_progress(*, review: Review) -> None:
    """Phase 12 progress emission after a successful enrichment.

    Reads sync:progress:{shop_id} from Redis. If absent (incremental sync with
    no live ProgressModal client), returns silently — no WebSocket event.

    On success, increments the snapshot's `enriched` counter, writes it back,
    and emits sync.enrichment.progress. When enriched >= fetched (and
    fetched > 0), also emits sync.complete — the SOLE source of sync.complete
    in Phase 12 (CONTEXT.md decision; the fetch loop in sync.py no longer
    emits it).

    MUST be called AFTER transaction.atomic() commits in _persist_success
    (RESEARCH.md anti-pattern: do not emit events from within a transaction).
    """
    from apps.reviews.services.progress import (
        read_progress_snapshot,
        write_progress_snapshot,
    )
    from apps.reviews.services.sync import emit_progress_event

    shop_id = review.shop_id
    snapshot = read_progress_snapshot(shop_id=shop_id)
    if snapshot is None:
        # No live progress modal — no WebSocket event needed (e.g. incremental sync).
        return

    enriched = int(snapshot.get("enriched", 0)) + 1
    fetched = int(snapshot.get("fetched", 0))

    new_snapshot = {**snapshot, "enriched": enriched}
    if fetched > 0 and enriched >= fetched:
        new_snapshot["status"] = "success"
    else:
        new_snapshot["status"] = "enriching"
    write_progress_snapshot(shop_id=shop_id, data=new_snapshot)

    emit_progress_event(
        shop_id=shop_id,
        payload={
            "type": "sync.enrichment.progress",
            "shop_id": shop_id,
            "enriched": enriched,
            "fetched": fetched,
        },
    )

    if fetched > 0 and enriched >= fetched:
        emit_progress_event(
            shop_id=shop_id,
            payload={
                "type": "sync.complete",
                "shop_id": shop_id,
                "total_fetched": fetched,
                "total_enriched": enriched,
                "duration_seconds": snapshot.get("duration_seconds"),
            },
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

        # Phase 12-09 (gap closure): skip OpenAI for comment-less reviews.
        # Rating-only Google reviews have no text for the LLM to analyse, so
        # we derive sentiment locally and persist SUCCESS without billing.
        if not (review.comment or "").strip():
            logger.info(
                "enrich_review_skip_no_comment review_id=%s star_rating=%s",
                review_id,
                review.star_rating,
            )
            _persist_success_no_comment(review=review)
            return

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
