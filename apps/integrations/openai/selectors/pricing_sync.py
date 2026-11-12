"""Read-only LiteLLM pricing sync status (Phase 36)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from django.utils import timezone

from apps.integrations.openai.models import AiPricingSyncConfig

OVERDUE_AFTER = timedelta(days=14)
# A "running" status older than this means the worker died mid-run (the task's hard time limit
# is 180 s), so it is reported as failed.
STALE_RUNNING_AFTER = timedelta(minutes=15)
STALE_RUNNING_ERROR = "Sync did not finish (worker stopped)."
# Fixed copy of the Beat schedule seeded by migration 0007 (Monday 09:00 UTC). Editing the
# PeriodicTask in Django admin does NOT move ``next_run_at``; change both together.
RUN_WEEKDAY = 0  # Monday
RUN_HOUR_UTC = 9


class SyncStatus(TypedDict):
    enabled: bool
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_status: str
    last_error: str
    overdue: bool
    summary: dict[str, Any]
    next_run_at: datetime | None


def _next_run_at(now: datetime) -> datetime:
    """Next Monday 09:00 UTC strictly after ``now``."""
    now = now.astimezone(UTC)
    candidate = now.replace(hour=RUN_HOUR_UTC, minute=0, second=0, microsecond=0)
    candidate += timedelta(days=(RUN_WEEKDAY - now.weekday()) % 7)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def get_sync_status(*, now: datetime | None = None) -> SyncStatus:
    """Read-only: never creates the singleton (an unsaved default stands in when missing)."""
    now = now or timezone.now()
    config = AiPricingSyncConfig.objects.filter(pk=1).first() or AiPricingSyncConfig()
    # Never succeeded yet: measure from the last run, else the toggle time (``updated_at``), so
    # a fresh enable is "not synced yet" rather than overdue until the first scheduled run.
    baseline = config.last_success_at or config.last_run_at or config.updated_at
    overdue = bool(config.enabled and baseline is not None and now - baseline > OVERDUE_AFTER)
    last_status, last_error = config.last_status, config.last_error
    if last_status == AiPricingSyncConfig.Status.RUNNING and (
        config.last_run_at is None or now - config.last_run_at > STALE_RUNNING_AFTER
    ):
        last_status, last_error = AiPricingSyncConfig.Status.FAILED, STALE_RUNNING_ERROR
    return SyncStatus(
        enabled=config.enabled,
        last_run_at=config.last_run_at,
        last_success_at=config.last_success_at,
        last_status=last_status,
        last_error=last_error,
        overdue=overdue,
        summary=config.last_summary,
        next_run_at=_next_run_at(now) if config.enabled else None,
    )
