"""Celery smoke-test task — used by INFRA-07 CI gate.

All real business logic lives in services/ modules; tasks remain thin wrappers
(see CLAUDE.md §5).
"""

from typing import Any

from celery import shared_task


@shared_task(bind=True)  # type: ignore[misc]
def smoke_test_task(self: Any, message: str = "ok") -> str:
    """No-op task. Returns its input. Used by CI smoke test only."""
    return message
