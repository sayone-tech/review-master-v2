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
)
def initial_backfill_task(self: Any, shop_id: int) -> dict[str, Any]:
    """Initial historical review backfill for a shop, dispatched after OAuth."""
    return run_initial_backfill(shop_id=shop_id)


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
    return run_incremental_sync(shop_id=shop_id)


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
    return len(shop_ids)


@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(OpenAITransientError, EnrichmentParseError),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def enrich_review_task(self: Any, review_id: int) -> None:
    """Phase 12 — Single-review enrichment task. Routes to ai-enrichment queue.

    autoretry_for handles transient errors with exponential backoff
    (30s, 60s, ..., capped at 600s). max_retries=3 caps total attempts.

    OpenAIPermanentError is NOT in autoretry_for — the service handles it
    silently (marks FAILED + returns). retry_failed_enrichments_task picks
    them up later (ENRCH-06).
    """
    from apps.reviews.services.enrichment import enrich_review

    enrich_review(review_id=review_id)


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

    ids = list(
        Review.objects.filter(
            enrichment_status=Review.EnrichmentStatus.FAILED,
            enrichment_version__lt=MAX_TOTAL_ENRICH_ATTEMPTS,
            deleted_at__isnull=True,
        ).values_list("id", flat=True)[:500]
    )
    for review_id in ids:
        enrich_review_task.delay(review_id)
    logger.info("retry_failed_enrichments dispatched count=%s", len(ids))
    return len(ids)
