"""Celery tasks for apps.common.

Tasks remain thin wrappers around services/ modules (see CLAUDE.md §5).
"""

from typing import Any

from celery import shared_task

from apps.common.services.cloudwatch_metrics import publish_celery_queue_depths


@shared_task(bind=True)  # type: ignore[misc]
def smoke_test_task(self: Any, message: str = "ok") -> str:
    """No-op task. Returns its input. Used by CI smoke test only."""
    return message


@shared_task(bind=True)  # type: ignore[misc]
def publish_celery_queue_depths_task(self: Any) -> dict[str, int]:
    """Periodic Beat task: publishes each Celery queue's depth to CloudWatch.

    Runs every 60s (see migration 0003_periodic_tasks_seed_celery_metrics).
    Returns the observed depths so the result backend (and tests) can assert.
    """
    return publish_celery_queue_depths()
