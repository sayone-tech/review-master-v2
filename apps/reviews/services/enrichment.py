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

    # Phase 13-05: promote extracted_action_items JSON -> ActionItem rows AND
    # dispatch one new_action_item Notification per genuinely-new row. Wrapped
    # in transaction.on_commit so promotion only runs after enrichment commits
    # (RESEARCH.md Pitfall 3 — never wrap promote_action_items_from_review in
    # an outer atomic block from inside _persist_success). When called outside
    # an active transaction, on_commit runs synchronously — same semantics.
    _schedule_action_item_promotion(review=review)


def _schedule_action_item_promotion(*, review: Review) -> None:
    """Queue post-commit promotion and notification routing.

    For initial sync (progress snapshot present): accumulates action item
    counts in Redis; a single consolidated notification fires at sync.complete.
    For incremental sync (no snapshot): dispatches one notification per review
    immediately (small batches, no natural batch-complete event).
    """
    from apps.action_items.models import ActionItem
    from apps.action_items.services.lifecycle import (
        promote_action_items_from_review,
    )
    from apps.notifications.services.dispatch import dispatch_notification

    review_pk = review.pk
    review_org_id = review.organisation_id

    def _on_enrichment_committed() -> None:
        from apps.reviews.services.progress import (
            accumulate_action_items,
            read_progress_snapshot,
        )

        fresh_review = Review.objects.get(pk=review_pk)
        shop_id = fresh_review.shop_id
        pre_pks = set(
            ActionItem.objects.filter(source_review_id=review_pk).values_list("pk", flat=True)
        )
        created_count = promote_action_items_from_review(review=fresh_review)
        if not created_count:
            return
        new_items = list(
            ActionItem.objects.filter(source_review_id=review_pk)
            .exclude(pk__in=pre_pks)
            .select_related("shop")
        )
        if not new_items:
            return

        has_brand = any(getattr(ai, "scope", None) == "BRAND" for ai in new_items)
        count = len(new_items)

        # Initial sync: progress snapshot exists → accumulate; sync.complete dispatches ONE
        # consolidated notification after all enrichments finish.
        if read_progress_snapshot(shop_id=shop_id) is not None:
            accumulate_action_items(shop_id=shop_id, count=count, has_brand=has_brand)
            return

        # Incremental sync: no snapshot, no sync.complete event — dispatch per review.
        shop = next((ai.shop for ai in new_items if ai.shop is not None), None)
        if count == 1:
            title = f"New action item: {new_items[0].title}"
        else:
            title = f"{count} new action items found"
        dispatch_notification(
            organisation_id=review_org_id,
            notification_type="new_action_item",
            title=title,
            target_url="/admin/org/action-items/",
            shop=shop,
            action_item=None,
            review=fresh_review,
            org_admins_only=has_brand,
        )

    transaction.on_commit(_on_enrichment_committed)


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


def _dispatch_sync_complete_notifications(*, review: Review, total_fetched: int) -> None:
    """Dispatch the two consolidated notifications that fire once at sync.complete.

    Called by _emit_enrichment_progress when enriched >= fetched. Dispatches:
      1. new_action_item — "N action items found" (all items from this sync batch)
      2. new_review — "N reviews synced at <shop>" (summary of the full initial sync)

    Both use function-local imports to avoid circular dependencies.
    """
    from apps.notifications.services.dispatch import dispatch_notification
    from apps.reviews.services.progress import pop_action_item_summary
    from apps.shops.models import Shop

    shop_id = review.shop_id
    org_id = review.organisation_id
    shop = Shop.objects.filter(pk=shop_id).first()

    # 1. Consolidated action items notification.
    ai_count, has_brand = pop_action_item_summary(shop_id=shop_id)
    if ai_count > 0:
        ai_title = (
            "1 new action item found" if ai_count == 1 else f"{ai_count} new action items found"
        )
        dispatch_notification(
            organisation_id=org_id,
            notification_type="new_action_item",
            title=ai_title,
            target_url="/admin/org/action-items/",
            shop=shop,
            action_item=None,
            review=None,
            org_admins_only=has_brand,
        )

    # 2. Sync summary — "X reviews synced" (initial sync only; incremental syncs
    # dispatch their own new_review notification in sync._schedule_new_review_dispatch).
    shop_name = shop.name if shop else "your shop"
    review_title = (
        f"1 review synced at {shop_name}"
        if total_fetched == 1
        else f"{total_fetched} reviews synced at {shop_name}"
    )
    dispatch_notification(
        organisation_id=org_id,
        notification_type="new_review",
        title=review_title,
        target_url=f"/admin/org/reviews/?shop={shop_id}",
        shop=shop,
        review=None,
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
        claim_sync_complete,
        increment_enriched_counter,
        read_progress_snapshot,
        write_progress_snapshot,
    )
    from apps.reviews.services.sync import emit_progress_event

    shop_id = review.shop_id
    snapshot = read_progress_snapshot(shop_id=shop_id)
    if snapshot is None:
        # No live progress modal — no WebSocket event needed (e.g. incremental sync).
        return

    # Atomic INCR prevents lost updates when two workers enrich concurrently.
    # The increment happens outside the snapshot read-modify-write cycle so no
    # two workers can increment to the same value.
    enriched = increment_enriched_counter(shop_id=shop_id)
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

    if fetched > 0 and enriched >= fetched and claim_sync_complete(shop_id=shop_id):
        _dispatch_sync_complete_notifications(review=review, total_fetched=fetched)
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
        # _already_success is set when the review is already SUCCESS so we can
        # emit the progress counter increment AFTER the transaction exits
        # (RESEARCH.md anti-pattern: never emit WebSocket events inside a txn).
        _already_success = False
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
            if review.enrichment_status == Review.EnrichmentStatus.IN_PROGRESS:
                logger.info(
                    "enrich_review_idempotent_skip review_id=%s status=%s",
                    review_id,
                    review.enrichment_status,
                )
                return
            if review.enrichment_status == Review.EnrichmentStatus.SUCCESS:
                logger.info(
                    "enrich_review_idempotent_skip review_id=%s status=%s",
                    review_id,
                    review.enrichment_status,
                )
                _already_success = True
            else:
                review.enrichment_status = Review.EnrichmentStatus.IN_PROGRESS
                review.enrichment_attempted_at = dj_timezone.now()
                review.save(update_fields=["enrichment_status", "enrichment_attempted_at"])

        if _already_success:
            # Emit progress AFTER the transaction closes so the WebSocket event
            # is never sent for rolled-back state (RESEARCH.md anti-pattern).
            # This advances the Redis enriched counter for reviews that were
            # already SUCCESS before the sync started — without this, fetched >
            # enriched permanently and sync.complete never fires.
            _emit_enrichment_progress(review=review)
            return

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
