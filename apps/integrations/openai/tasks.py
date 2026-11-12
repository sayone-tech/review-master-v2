"""Celery tasks for the OpenAI integration (Phase 36 AI pricing auto-sync).

Tasks are thin wrappers: all business logic lives in ``services/`` (CLAUDE.md section 12.3).
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=120, time_limit=180)  # type: ignore[misc]
def sync_ai_pricing_from_litellm_task(self: Any, force: bool = False) -> dict[str, Any]:
    """Weekly (Monday 09:00 UTC) LiteLLM price sync; ``force=True`` runs even when disabled.

    Thin wrapper around ``run_pricing_sync()``. No autoretry on purpose, deviating from the
    section 12.3 blanket autoretry: the service never raises for fetch failures or unexpected
    errors, it records them (config ``last_status="failed"`` plus an audit row) and returns a
    FAILED summary, and the next weekly run retries. Routed to the default queue (section 12.5).

    Own time limits (soft 120 s, hard 180 s) instead of the global 300/600 s: both stay below
    the 300 s sync lock TTL, so the lock never expires under a still-running sync. The soft
    limit is recorded as a failed run by the service, which then returns normally.
    """
    from apps.integrations.openai.services.pricing_sync import run_pricing_sync

    summary = run_pricing_sync(force=force)
    logger.info(
        "sync_ai_pricing_from_litellm_task.complete outcome=%s counts=%s",
        summary.outcome,
        summary.counts(),
    )
    return summary.as_json()
