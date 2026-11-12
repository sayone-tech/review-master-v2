"""Read-only LiteLLM pricing sync status (Phase 36)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from django.utils import timezone

from apps.integrations.openai.models import AiPricingSyncConfig

OVERDUE_AFTER = timedelta(days=14)
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
    now = now or timezone.now()
    config = AiPricingSyncConfig.load()
    overdue = config.enabled and (
        config.last_success_at is None or now - config.last_success_at > OVERDUE_AFTER
    )
    return SyncStatus(
        enabled=config.enabled,
        last_run_at=config.last_run_at,
        last_success_at=config.last_success_at,
        last_status=config.last_status,
        last_error=config.last_error,
        overdue=overdue,
        summary=config.last_summary,
        next_run_at=_next_run_at(now) if config.enabled else None,
    )
