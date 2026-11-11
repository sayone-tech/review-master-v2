"""Celery tasks for the credits bounded context (v0.9, Phase 31).

Tasks are thin wrappers: all business logic lives in ``apps/credits/services/`` (CLAUDE.md
section 12.3).
"""

from __future__ import annotations

import dataclasses
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task  # type: ignore[misc]
def lapse_expired_credit_balances_task() -> dict[str, int]:
    """Phase 31 CREN-01: daily 00:05 UTC idempotent lapse of past-month credit balances.

    Thin wrapper around ``lapse_past_balances()``. No autoretry on purpose, deviating from the
    section 12.3 blanket autoretry: this is an idempotent fleet sweep that isolates per-balance
    errors, re-runs daily and resumes by primary-key keyset, so a blanket retry would re-run
    the whole sweep and hide real failures. The 300 s soft limit may interrupt a very large
    catch-up; the next run continues. Routed to the default queue (section 12.5).
    """
    from apps.credits.services.lapse import lapse_past_balances

    summary = lapse_past_balances()
    logger.info(
        "lapse_expired_credit_balances_task.complete lapsed=%s lapsed_zero=%s "
        "skipped_held=%s skipped_noop=%s errored=%s",
        summary.lapsed,
        summary.lapsed_zero,
        summary.skipped_held,
        summary.skipped_noop,
        summary.errored,
    )
    return dataclasses.asdict(summary)
