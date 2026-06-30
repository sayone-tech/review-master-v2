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
    ContentModeratedException,
    EnrichmentParseError,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.guardrails import (
    ReviewWithModeratedComment,
    moderate_input,
)
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.pricing import calculate_cost
from apps.reviews.models import OrgCanonicalTag, Review, ReviewTag
from apps.reviews.selectors.canonical_tags import get_org_vocabulary
from apps.reviews.services.progress import (
    increment_openai_token_bucket,
    openai_token_bucket_depleted,
)

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
            extracted_action_items=[
                {"title": a.title, "scope": a.scope, "priority": a.priority, "category": a.category}
                for a in result.action_items
            ],
            enrichment_version=models.F("enrichment_version") + 1,
        )
        # Phase 17 (TAG-02): write tags as relational ReviewTag rows. Delete-before-
        # bulk_create makes re-enrichment idempotent (D-09); both calls inside the
        # transaction so a bulk_create failure rolls back the Review update.
        ReviewTag.objects.filter(review_id=review.pk).delete()

        # Phase 22 (CTAG-06/CTAG-07/D-01/D-03): resolve each tag's canonical FK
        # inside this same atomic block. Strategy (RESEARCH.md Pitfalls 3+4):
        # one batch SELECT + bulk_create(ignore_conflicts=True) + a re-SELECT of
        # only the missing labels. This keeps the query count FIXED regardless of
        # tag count (no N+1) and is race-safe — ignore_conflicts does NOT abort
        # the outer transaction the way per-tag get_or_create would. review_count
        # is NEVER written here (D-03 — derived on read; touching it would
        # double-count on re-enrichment).
        org_id = review.organisation_id
        # Distinct normalized canonical labels (already Title-Cased by the 22-03
        # validator). Remember the polarity_type proposed for any NEW label
        # (first proposal wins), defaulting to MIXED when GPT left it null.
        proposed_polarity: dict[str, str] = {}
        for tag in result.tags:
            proposed_polarity.setdefault(
                tag.canonical,
                tag.polarity_type or OrgCanonicalTag.PolarityType.MIXED,
            )
        labels = list(proposed_polarity)
        canonical_map = {
            ct.label: ct
            for ct in OrgCanonicalTag.objects.filter(organisation_id=org_id, label__in=labels)
        }
        missing = [label for label in labels if label not in canonical_map]
        if missing:
            OrgCanonicalTag.objects.bulk_create(
                [
                    OrgCanonicalTag(
                        organisation_id=org_id,
                        label=label,
                        polarity_type=proposed_polarity[label],
                    )
                    for label in missing
                ],
                ignore_conflicts=True,
            )
            # Re-SELECT only the missing labels to fetch their FKs — also picks up
            # rows another worker inserted concurrently (the (org,label) unique
            # constraint is authoritative).
            for ct in OrgCanonicalTag.objects.filter(organisation_id=org_id, label__in=missing):
                canonical_map[ct.label] = ct

        ReviewTag.objects.bulk_create(
            [
                ReviewTag(
                    review_id=review.pk,
                    label=tag.label.title(),
                    polarity=tag.polarity,
                    canonical_tag=canonical_map[tag.canonical],
                )
                for tag in result.tags
            ]
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
            extracted_action_items=[],
            enrichment_version=models.F("enrichment_version") + 1,
        )
        # Phase 17 (TAG-02): clear any stale ReviewTag rows from a prior
        # enrichment. No bulk_create — comment-less reviews have no tags.
        ReviewTag.objects.filter(review_id=review.pk).delete()

    # AFTER commit: emit progress so the modal counter increments
    # identically to a normal enrichment.
    _emit_enrichment_progress(review=review)


def _persist_moderated(review: Review) -> None:
    """Phase 20 (D-15/D-31/D-33): persist FAILED + content_moderated error_code.

    Called by enrich_review when moderate_input raises ContentModeratedException.
    Does NOT write an AiUsageLog row — guardrails.moderate_input has already
    written the MODERATED row before raising (D-33). Single-row save; no
    transaction.atomic() wrapper needed.
    """
    review.enrichment_status = Review.EnrichmentStatus.FAILED
    review.enrichment_error_code = "content_moderated"
    review.enrichment_attempted_at = dj_timezone.now()
    review.save(
        update_fields=[
            "enrichment_status",
            "enrichment_error_code",
            "enrichment_attempted_at",
        ]
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


def _dispatch_sync_complete_notifications(
    *, shop_id: int, organisation_id: int, total_fetched: int
) -> None:
    """Dispatch the two consolidated notifications that fire once at sync.complete.

    Called by run_finalise_canonical_tags (finalise.py) after sync.complete is emitted.
    Dispatches:
      1. new_action_item — "N action items found" (all items from this sync batch)
      2. new_review — "N reviews synced at <shop>" (summary of the full initial sync)

    Signature uses (shop_id, organisation_id, total_fetched) directly to remove the
    coupling to a Review proxy object (IN-01 / CLAUDE.md §5 — services operate at
    org/shop level, not review level for this concern).

    Both use function-local imports to avoid circular dependencies.
    """
    from apps.notifications.services.dispatch import dispatch_notification
    from apps.reviews.services.progress import pop_action_item_summary
    from apps.shops.models import Shop

    org_id = organisation_id
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
    """Phase 12/23 progress emission after a successful enrichment.

    Reads sync:progress:{shop_id} from Redis. If absent (incremental sync with
    no live ProgressModal client), returns silently — no WebSocket event.

    On success, increments the snapshot's `enriched` counter, writes it back,
    and emits sync.enrichment.progress. The snapshot status is set to "enriching"
    (NOT "success") — sync.complete ownership has moved to the finalising pass
    (run_finalise_canonical_tags in finalise.py, Phase 23 D-02).

    MUST be called AFTER transaction.atomic() commits in _persist_success
    (RESEARCH.md anti-pattern: do not emit events from within a transaction).
    """
    from apps.reviews.services.progress import (
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

    # Phase 23 (D-02): status stays "enriching" until the finalising pass emits
    # sync.complete. This function NO LONGER sets status="success" or emits
    # sync.complete — that responsibility belongs to run_finalise_canonical_tags.
    # Bump last_update_at so the progress modal's "Last updated Ns ago" reflects live
    # bulk activity — without it the timestamp stays frozen at the last transition for
    # the whole (~20 min) bulk phase, making an actively-draining sync look stuck.
    new_snapshot = {
        **snapshot,
        "enriched": enriched,
        "status": "enriching",
        "step": "enriching",
        "last_update_at": dj_timezone.now().isoformat(),
    }
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


def enrich_review(*, review_id: int, skip_rate_limit_guard: bool = False) -> None:
    """Enrich a review with three-layer idempotency. See module docstring.

    Args:
        review_id: PK of the Review to enrich.
        skip_rate_limit_guard: When True (seed-loop path), the global OpenAI token
            bucket check AND increment are both skipped. The seed loop pre-acquires
            a token via _wait_for_openai_token before calling this function, so
            re-checking here would double-count and could crash the seed loop on a
            depleted bucket (Blocker 2 / Phase 23 D-08). When False (bulk/task path,
            the default), the guard runs: if the bucket is depleted,
            raises OpenAITransientError so Celery autoretry re-queues with
            exponential backoff (RESEARCH Pattern 1).

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

        # Phase 20 (D-15/D-33): input moderation BEFORE the OpenAI call and
        # OUTSIDE any transaction.atomic() block, so the MODERATED AiUsageLog
        # row written inside guardrails survives a downstream rollback.
        try:
            truncated_text = moderate_input(
                review.comment, review=review, request_type="enrichment"
            )
        except ContentModeratedException:
            _persist_moderated(review)
            return

        # Flow the truncated text into the prompt (D-21) via a read-only
        # proxy instead of mutating `review.comment` in place. A future
        # contributor switching from `Review.objects.filter(pk=...).update(...)`
        # to `review.save()` would otherwise silently persist the
        # `…[truncated]` suffix into the database, corrupting the
        # reviewer's actual text. Mirrors the pattern in reply_generation
        # (WR-02).
        review_for_prompt = ReviewWithModeratedComment(review, truncated_text)

        # Phase 22 (CTAG-03/D-02): inject the org's capped canonical vocabulary
        # into the single prompt. organisation_id is already loaded via
        # select_related("shop__organisation"), so this adds no extra org query
        # beyond the bounded selector lookup.
        canonical_vocab = get_org_vocabulary(
            organisation_id=review.organisation_id,
            limit=settings.CANONICAL_VOCAB_INJECT_LIMIT,
        )

        # Phase 23 (D-08) — global cross-worker OpenAI token-bucket guard.
        # Bulk / task path (skip_rate_limit_guard=False): if the per-org rolling-minute
        # counter is at/above OPENAI_GLOBAL_RATE_LIMIT, raise OpenAITransientError so
        # Celery autoretry re-queues with exponential backoff (RESEARCH Pattern 1).
        # Seed-loop path (skip_rate_limit_guard=True): the caller already pre-acquired a
        # token via _wait_for_openai_token, so we skip BOTH the check AND the increment
        # to avoid double-counting and to prevent crashing the seed loop (Blocker 2).
        if not skip_rate_limit_guard:
            org_id = review.organisation_id
            if openai_token_bucket_depleted(
                organisation_id=org_id,
                max_calls=settings.OPENAI_GLOBAL_RATE_LIMIT,
            ):
                raise OpenAITransientError(
                    f"openai_global_rate_limit: bucket depleted for org {org_id}; Celery will retry"
                )
            increment_openai_token_bucket(organisation_id=org_id)

        # OpenAI call OUTSIDE the transaction (RESEARCH.md anti-pattern).
        try:
            result, usage_data = call_openai_enrichment(
                review=review_for_prompt, canonical_vocab=canonical_vocab
            )
        except (OpenAITransientError, EnrichmentParseError) as exc:
            _persist_failure(review=review, usage_data=None, exc=exc)
            raise  # Celery autoretry_for picks this up
        except OpenAIPermanentError as exc:
            _persist_failure(review=review, usage_data=None, exc=exc)
            return  # ENRCH-04: do not retry on 4xx other than 429

        _persist_success(review=review, result=result, usage_data=usage_data)
