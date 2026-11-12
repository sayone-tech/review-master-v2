"""Celery tasks for the OpenAI integration (Phase 36 AI pricing auto-sync).

Tasks are thin wrappers: all business logic lives in ``services/`` (CLAUDE.md section 12.3).
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task  # type: ignore[misc]
def sync_ai_pricing_from_litellm_task(force: bool = False) -> dict[str, Any]:
    """Weekly (Monday 09:00 UTC) LiteLLM price sync; ``force=True`` runs even when disabled.

    Thin wrapper around ``run_pricing_sync()``. No autoretry on purpose, deviating from the
    section 12.3 blanket autoretry: the service never raises for fetch failures or unexpected
    errors, it records them (config ``last_status="failed"`` plus an audit row) and returns a
    FAILED summary, and the next weekly run retries. Routed to the default queue (section 12.5).
    """
    from apps.integrations.openai.services.pricing_sync import run_pricing_sync

    summary = run_pricing_sync(force=force)
    logger.info(
        "sync_ai_pricing_from_litellm_task.complete outcome=%s counts=%s",
        summary.outcome,
        summary.counts(),
    )
    return summary.as_json()
