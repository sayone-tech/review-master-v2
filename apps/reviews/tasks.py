"""Phase 11/12 — Celery tasks for Google review sync + AI enrichment.

Phase 11 tasks: initial_backfill_task, sync_shop_reviews_task,
enqueue_incremental_syncs_task — Google review sync. Routes to google-sync.

Phase 12 tasks: enrich_review_task, retry_failed_enrichments_task — OpenAI
review enrichment. Routes to ai-enrichment.

Tasks are thin wrappers — all business logic lives in service modules.
Routes are pre-configured in config/settings/base.py CELERY_TASK_ROUTES.

Per CLAUDE.md §12.3:
  - bind=True for retries
  - max_retries=3
  - retry_backoff with jitter
  - tasks receive IDs (not model instances)
"""

from __future__ import annotations

import logging
import random
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.integrations.openai.exceptions import (
    EnrichmentParseError,
    OpenAITransientError,
)
from apps.reviews.services.sync import run_incremental_sync, run_initial_backfill

logger = logging.getLogger(__name__)

INCREMENTAL_JITTER_SECONDS_MAX = (
    1800  # 30 minutes per CLAUDE.md §14.8 INCREMENTAL_SYNC_JITTER_MINUTES
)

MAX_TOTAL_ENRICH_ATTEMPTS = 3


@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    # Phase 23 (Pitfall 1 / Open Question 2): the sequential seed loop + token-wait can
    # exceed the global 300s soft limit. Raise to 540s soft / 600s hard so the seed loop
    # completes without SoftTimeLimitExceeded.
    soft_time_limit=540,
    time_limit=600,
)
def initial_backfill_task(self: Any, shop_id: int) -> dict[str, Any]:
    """Initial historical review backfill for a shop, dispatched after OAuth."""
    task_id = self.request.id
    attempt = self.request.retries + 1
    logger.info(
        "initial_backfill_task.start task_id=%s shop_id=%s attempt=%s",
        task_id,
        shop_id,
        attempt,
    )
    try:
        result = run_initial_backfill(shop_id=shop_id)
    except Exception as exc:
        logger.error(
            "initial_backfill_task.error task_id=%s shop_id=%s attempt=%s max_retries=%s error=%r",
            task_id,
            shop_id,
            attempt,
            self.max_retries,
            exc,
            exc_info=True,
        )
        raise
    if result.get("skipped"):
        logger.info(
            "initial_backfill_task.skipped task_id=%s shop_id=%s reason=%s",
            task_id,
            shop_id,
            result["skipped"],
        )
    else:
        logger.info(
            "initial_backfill_task.success task_id=%s shop_id=%s "
            "fetched=%s soft_deleted=%s duration_seconds=%.1f",
            task_id,
            shop_id,
            result.get("fetched", 0),
            result.get("soft_deleted", 0),
            result.get("duration_seconds", 0.0),
        )
    return result


@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def sync_shop_reviews_task(self: Any, shop_id: int) -> dict[str, Any]:
    """6-hour incremental sync for a shop, dispatched by Beat fan-out."""
    task_id = self.request.id
    attempt = self.request.retries + 1
    logger.info(
        "sync_shop_reviews_task.start task_id=%s shop_id=%s attempt=%s",
        task_id,
        shop_id,
        attempt,
    )
    try:
        result = run_incremental_sync(shop_id=shop_id)
    except Exception as exc:
        logger.error(
            "sync_shop_reviews_task.error task_id=%s shop_id=%s attempt=%s max_retries=%s error=%r",
            task_id,
            shop_id,
            attempt,
            self.max_retries,
            exc,
            exc_info=True,
        )
        raise
    if result.get("skipped"):
        logger.info(
            "sync_shop_reviews_task.skipped task_id=%s shop_id=%s reason=%s",
            task_id,
            shop_id,
            result["skipped"],
        )
    else:
        logger.info(
            "sync_shop_reviews_task.success task_id=%s shop_id=%s "
            "fetched=%s soft_deleted=%s duration_seconds=%.1f",
            task_id,
            shop_id,
            result.get("fetched", 0),
            result.get("soft_deleted", 0),
            result.get("duration_seconds", 0.0),
        )
    return result


@shared_task  # type: ignore[misc]
def enqueue_incremental_syncs_task() -> int:
    """Beat-scheduled fan-out: dispatch sync_shop_reviews_task per CONNECTED shop with jitter.

    Returns the number of shops dispatched.
    """
    from apps.shops.models import Shop

    shop_ids = list(
        Shop.objects.filter(
            is_active=True,
            connection_status=Shop.ConnectionStatus.CONNECTED,
        ).values_list("id", flat=True)
    )
    for shop_id in shop_ids:
        countdown = random.uniform(0, INCREMENTAL_JITTER_SECONDS_MAX)  # nosec B311  # noqa: S311
        sync_shop_reviews_task.apply_async(args=[shop_id], countdown=countdown)
    logger.info(
        "enqueue_incremental_syncs_task.dispatched shops_count=%s",
        len(shop_ids),
    )
    return len(shop_ids)


@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(OpenAITransientError, EnrichmentParseError),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    rate_limit=settings.ENRICHMENT_RATE_LIMIT,
)
def enrich_review_task(self: Any, review_id: int) -> None:
    """Phase 12 — Single-review enrichment task. Routes to ai-enrichment queue.

    autoretry_for handles transient errors with exponential backoff
    (30s, 60s, ..., capped at 600s). max_retries=3 caps total attempts.

    OpenAIPermanentError is NOT in autoretry_for — the service handles it
    silently (marks FAILED + returns). retry_failed_enrichments_task picks
    them up later (ENRCH-06).

    Rate limiting (QUEUE-02 / D-06):
    Celery ``rate_limit`` is enforced PER WORKER INSTANCE, not globally across
    all workers. The configured value (``settings.ENRICHMENT_RATE_LIMIT``,
    default "125/m") represents the platform target divided by the expected
    worker count (e.g. 500 total ÷ 4 workers = 125/m per worker). A true
    cross-worker global throttle (Redis token bucket) is deferred to Phase 23
    (QUEUE-01). Do not interpret this setting as a global rate guarantee.
    """
    from apps.reviews.services.enrichment import enrich_review

    task_id = self.request.id
    attempt = self.request.retries + 1
    logger.info(
        "enrich_review_task.start task_id=%s review_id=%s attempt=%s",
        task_id,
        review_id,
        attempt,
    )
    try:
        enrich_review(review_id=review_id)
    except Exception as exc:
        logger.error(
            "enrich_review_task.error task_id=%s review_id=%s attempt=%s max_retries=%s error=%r",
            task_id,
            review_id,
            attempt,
            self.max_retries,
            exc,
            exc_info=True,
        )
        raise
    logger.info(
        "enrich_review_task.success task_id=%s review_id=%s attempt=%s",
        task_id,
        review_id,
        attempt,
    )


@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def finalize_canonical_tags_task(
    self: Any, *, organisation_id: int, shop_id: int
) -> dict[str, Any]:
    """Phase 23 — Canonical tag finalising pass (SEED-04, Step 4).

    Deduplicates case-insensitive OrgCanonicalTag pairs, re-points ReviewTag FKs
    to the winner, backfills null canonical_tag stragglers, and refreshes
    review_count from the aggregate. Routes to tag-merge queue (Plan 01 settings).

    Uses retry_backoff=60 (longer than the 30s hot-path default) since this is
    a non-time-critical finalising step. Business logic lives in
    run_finalise_canonical_tags (CLAUDE.md §12.3 — no logic in task body).
    """
    from apps.reviews.services.finalise import run_finalise_canonical_tags

    task_id = self.request.id
    attempt = self.request.retries + 1
    logger.info(
        "finalize_canonical_tags_task.start task_id=%s organisation_id=%s shop_id=%s attempt=%s",
        task_id,
        organisation_id,
        shop_id,
        attempt,
    )
    try:
        result = run_finalise_canonical_tags(organisation_id=organisation_id, shop_id=shop_id)
    except Exception as exc:
        logger.error(
            "finalize_canonical_tags_task.error task_id=%s organisation_id=%s "
            "shop_id=%s attempt=%s max_retries=%s error=%r",
            task_id,
            organisation_id,
            shop_id,
            attempt,
            self.max_retries,
            exc,
            exc_info=True,
        )
        raise
    if result.get("skipped"):
        logger.info(
            "finalize_canonical_tags_task.skipped task_id=%s organisation_id=%s "
            "shop_id=%s reason=lock_held",
            task_id,
            organisation_id,
            shop_id,
        )
    else:
        logger.info(
            "finalize_canonical_tags_task.success task_id=%s organisation_id=%s "
            "shop_id=%s merged_groups=%s stragglers_backfilled=%s",
            task_id,
            organisation_id,
            shop_id,
            result.get("merged_groups", 0),
            result.get("stragglers_backfilled", 0),
        )
    return result


@shared_task  # type: ignore[misc]
def retry_failed_enrichments_task() -> int:
    """Phase 12 ENRCH-06 — Beat-scheduled, every 6h.

    Re-enqueues FAILED reviews where enrichment_version < MAX_TOTAL_ENRICH_ATTEMPTS
    and deleted_at IS NULL. Returns the count of reviews dispatched.

    enrichment_version doubles as an attempt counter — each FAILED + each SUCCESS
    increments it. The cap of 3 means: max 3 distinct enrich_review attempts
    across initial + retry cycles.

    Cap of 500 reviews per run prevents the task from holding a worker for
    unbounded time when many reviews failed.
    """
    from apps.reviews.models import Review

    # D-25: skip content_moderated rows — reviewer text is immutable, retry is pure waste.
    ids = list(
        Review.objects.filter(
            enrichment_status=Review.EnrichmentStatus.FAILED,
            enrichment_version__lt=MAX_TOTAL_ENRICH_ATTEMPTS,
            deleted_at__isnull=True,
        )
        .exclude(enrichment_error_code="content_moderated")
        .values_list("id", flat=True)[:500]
    )
    for review_id in ids:
        # Phase 23 (Pitfall 6): route to ai-enrichment-low (retry traffic is lower priority
        # than new initial-sync bulk traffic which routes to ai-enrichment-high).
        # Using apply_async with an explicit queue avoids routing to the removed
        # monolithic ai-enrichment queue.
        enrich_review_task.apply_async(args=[review_id], queue="ai-enrichment-low")
    logger.info(
        "retry_failed_enrichments_task.dispatched reviews_count=%s",
        len(ids),
    )
    return len(ids)
