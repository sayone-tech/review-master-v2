"""Phase 11 — Celery tasks for Google review sync.

Tasks are thin wrappers — all business logic lives in apps.reviews.services.sync.
Routes are pre-configured in config/settings/base.py CELERY_TASK_ROUTES:
  - initial_backfill_task   -> google-sync
  - sync_shop_reviews_task  -> google-sync
  - enqueue_incremental_syncs_task -> default (fan-out only; light)

Per CLAUDE.md §12.3:
  - bind=True for retries
  - autoretry_for=(Exception,) with retry_backoff=30, retry_backoff_max=600, retry_jitter=True
  - max_retries=3
  - tasks receive IDs (not model instances)
"""

from __future__ import annotations

import logging
import random
from typing import Any

from celery import shared_task

from apps.reviews.services.sync import run_incremental_sync, run_initial_backfill

logger = logging.getLogger(__name__)

INCREMENTAL_JITTER_SECONDS_MAX = (
    1800  # 30 minutes per CLAUDE.md §14.8 INCREMENTAL_SYNC_JITTER_MINUTES
)


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
