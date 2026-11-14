"""Celery tasks for the insights bounded context (thin wrappers, CLAUDE.md section 12.3)."""

from __future__ import annotations

from celery import shared_task

from apps.insights.services.build import compute_all_insights


@shared_task(  # type: ignore[misc]
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
)
def compute_daily_insights_task(self) -> int:  # type: ignore[no-untyped-def]
    return compute_all_insights()
