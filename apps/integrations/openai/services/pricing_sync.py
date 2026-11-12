"""LiteLLM pricing auto-sync (Phase 36): the on/off toggle and the sync run.

The run only prices models this platform used recently (plus ``settings.OPENAI_MODEL``), by
exact LiteLLM key. Every price write goes through ``pricing_management.add_price`` (append-only,
actor ``None``); a manually entered price is never overridden and ``AiUsageLog`` is never
touched. One run at a time, guarded by a non-blocking Redis lock.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import httpx
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.common.locks import distributed_lock
from apps.common.models import AuditLog
from apps.integrations.openai.litellm import (
    LiteLLMCatalog,
    LiteLLMFetchError,
    LiteLLMPrice,
    fetch_litellm_catalog,
)
from apps.integrations.openai.models import AiPricing, AiPricingSyncConfig
from apps.integrations.openai.selectors.pricing import list_recent_usage_models
from apps.integrations.openai.services.pricing_management import (
    MAX_PRICE_PER_1M,
    ConcurrentPriceChangeError,
    ManualPriceProtectedError,
    ScheduledPriceExistsError,
    add_price,
)

logger = logging.getLogger(__name__)

SYNC_LOCK_KEY = "lock:ai_pricing:sync"
_QUANT = Decimal("0.00000001")


@transaction.atomic
def set_sync_enabled(*, enabled: bool, actor: User) -> AiPricingSyncConfig:
    """Flip the auto-sync switch; a no-op (no audit row) when the value is unchanged."""
    AiPricingSyncConfig.load()
    config = AiPricingSyncConfig.objects.select_for_update().get(pk=1)
    if config.enabled == enabled:
        return config
    before = config.enabled
    config.enabled = enabled
    config.save(update_fields=["enabled", "updated_at"])
    AuditLog.objects.create(
        organisation=None,
        actor=actor,
        entity_type="ai_pricing",
        entity_id="sync",
        action="ai_pricing.sync_enabled" if enabled else "ai_pricing.sync_disabled",
        before_data={"enabled": before},
        after_data={"enabled": enabled},
    )
    logger.info("ai_pricing.sync_toggled enabled=%s", enabled)
    return config


class SyncOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED_DISABLED = "skipped_disabled"
    SKIPPED_LOCKED = "skipped_locked"


def _fmt(value: Decimal) -> str:
    return str(Decimal(value).quantize(_QUANT))


@dataclass
class SyncSummary:
    outcome: SyncOutcome
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped_manual: list[dict[str, Any]] = field(default_factory=list)
    skipped_scheduled: list[str] = field(default_factory=list)
    skipped_concurrent: list[str] = field(default_factory=list)
    unpriced: list[str] = field(default_factory=list)
    errored: list[str] = field(default_factory=list)
    error: str = ""

    def counts(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "updated": len(self.updated),
            "unchanged": len(self.unchanged),
            "skipped_manual": len(self.skipped_manual),
            "skipped_scheduled": len(self.skipped_scheduled),
            "skipped_concurrent": len(self.skipped_concurrent),
            "unpriced": len(self.unpriced),
            "errored": len(self.errored),
        }

    def as_json(self) -> dict[str, Any]:
        """JSON-safe, deterministic form: sorted lists, Decimals as 8-dp strings."""
        manual = [
            {
                "model": item["model"],
                "ours": {k: _fmt(v) for k, v in item["ours"].items()},
                "litellm": {k: _fmt(v) for k, v in item["litellm"].items()},
            }
            for item in sorted(self.skipped_manual, key=lambda i: str(i["model"]))
        ]
        return {
            "outcome": str(self.outcome),
            "added": sorted(self.added),
            "updated": sorted(self.updated),
            "unchanged": sorted(self.unchanged),
            "skipped_manual": manual,
            "skipped_scheduled": sorted(self.skipped_scheduled),
            "skipped_concurrent": sorted(self.skipped_concurrent),
            "unpriced": sorted(self.unpriced),
            "errored": sorted(self.errored),
            "error": self.error,
        }


def _triple(row: AiPricing) -> dict[str, Decimal]:
    return {
        "input": Decimal(row.input_token_price_per_1m),
        "output": Decimal(row.output_token_price_per_1m),
        "cached": Decimal(row.cached_token_price_per_1m),
    }


def _litellm_triple(price: LiteLLMPrice) -> dict[str, Decimal]:
    return {
        "input": price.input_per_1m,
        "output": price.output_per_1m,
        "cached": price.cached_per_1m,
    }


def _within_tolerance(ours: dict[str, Decimal], theirs: dict[str, Decimal]) -> bool:
    tolerance = settings.AI_PRICING_SYNC_TOLERANCE_USD_PER_1M
    return all(abs(ours[k] - theirs[k]) <= tolerance for k in ("input", "output", "cached"))


def _sync_model(
    *, model: str, catalog: LiteLLMCatalog, now: datetime | None, summary: SyncSummary
) -> None:
    # Each model's new price starts when it is written, not when the run started (a slow run
    # would otherwise date prices minutes in the past). Tests inject a fixed ``now``.
    now = now or timezone.now()
    price = catalog.prices.get(model)
    if price is None:
        reason = "unusable entry" if model in catalog.unusable else "not in catalog"
        logger.warning("ai_pricing.sync_unpriced model=%s reason=%s", model, reason)
        summary.unpriced.append(model)
        return
    theirs = _litellm_triple(price)
    if any(v > MAX_PRICE_PER_1M for v in theirs.values()):
        logger.warning("ai_pricing.sync_unpriced model=%s reason=out of range", model)
        summary.unpriced.append(model)
        return

    try:
        active: AiPricing | None = AiPricing.objects.get_active(model=model, at=now)
    except AiPricing.DoesNotExist:
        active = None
    if active is not None:
        ours = _triple(active)
        if _within_tolerance(ours, theirs):
            summary.unchanged.append(model)
            return
        if active.source == AiPricing.Source.MANUAL:
            summary.skipped_manual.append({"model": model, "ours": ours, "litellm": theirs})
            return
    if AiPricing.objects.filter(model=model, effective_from__gt=now).exists():
        summary.skipped_scheduled.append(model)
        return

    try:
        add_price(
            model=model,
            input_token_price_per_1m=price.input_per_1m,
            output_token_price_per_1m=price.output_per_1m,
            cached_token_price_per_1m=price.cached_per_1m,
            effective_from=now,
            actor=None,
            source=AiPricing.Source.SYNC,
            now=now,
            audit_action=(
                "ai_pricing.added_from_sync" if active is None else "ai_pricing.updated_from_sync"
            ),
            protect_manual=True,
        )
    except ManualPriceProtectedError as exc:
        # A hand-set price landed after the unlocked check above; add_price re-checked it under
        # the row lock and refused, so nothing was written.
        summary.skipped_manual.append(
            {"model": model, "ours": _triple(exc.current), "litellm": theirs}
        )
        return
    except ScheduledPriceExistsError:
        summary.skipped_scheduled.append(model)
        return
    except ConcurrentPriceChangeError:
        summary.skipped_concurrent.append(model)
        return
    (summary.added if active is None else summary.updated).append(model)


def _sync_audit(action: str, after_data: dict[str, Any]) -> None:
    AuditLog.objects.create(
        organisation=None,
        actor=None,
        entity_type="ai_pricing",
        entity_id="sync",
        action=action,
        before_data=None,
        after_data=after_data,
    )


def _record_failure(*, now: datetime, error: str) -> SyncSummary:
    # update() on pk=1 so a concurrent toggle's ``enabled`` is never overwritten.
    AiPricingSyncConfig.objects.filter(pk=1).update(
        last_status=AiPricingSyncConfig.Status.FAILED, last_error=error, updated_at=now
    )
    _sync_audit("ai_pricing.sync_failed", {"error": error})
    return SyncSummary(outcome=SyncOutcome.FAILED, error=error)


def _run_locked(
    *, now: datetime, fixed_now: bool, transport: httpx.BaseTransport | None
) -> SyncSummary:
    AiPricingSyncConfig.load()
    config = AiPricingSyncConfig.objects.filter(pk=1)
    # "running" lets the status selector spot a run whose worker was hard-killed (it never
    # reaches the success/failed write below).
    config.update(last_status=AiPricingSyncConfig.Status.RUNNING, last_run_at=now, updated_at=now)

    try:
        catalog = fetch_litellm_catalog(transport=transport)
    except LiteLLMFetchError as exc:
        logger.warning("ai_pricing.sync_failed error=%s", exc)
        return _record_failure(now=now, error=str(exc))

    summary = SyncSummary(outcome=SyncOutcome.COMPLETED)
    models = set(list_recent_usage_models(now=now, use_cache=False))
    models.add(settings.OPENAI_MODEL)
    for model in sorted(models):
        try:
            # One transaction per model (a savepoint when an outer transaction is open, e.g. in
            # tests): a DB error rolls back only this model's writes and never poisons the
            # next model's queries.
            with transaction.atomic():
                _sync_model(
                    model=model, catalog=catalog, now=now if fixed_now else None, summary=summary
                )
        except SoftTimeLimitExceeded:
            raise  # the run is out of time: stop, and let run_pricing_sync record the failure
        except Exception:
            logger.exception("ai_pricing.sync_model_failed model=%s", model)
            summary.errored.append(model)

    data = summary.as_json()
    _sync_audit(
        "ai_pricing.sync_completed",
        {
            "counts": summary.counts(),
            "skipped_manual": data["skipped_manual"],
            "unpriced": data["unpriced"],
        },
    )
    # Success is the run's last write, so a crash anywhere before it is recorded as failed.
    config.update(
        last_status=AiPricingSyncConfig.Status.SUCCESS,
        last_success_at=now,
        last_error="",
        last_summary=data,
        updated_at=now,
    )
    # No cache invalidation here: every add_price call already drops the missing-pricing cache
    # on commit, and added/updated only ever hold models add_price wrote.
    logger.info("ai_pricing.sync_completed %s", summary.counts())
    return summary


def run_pricing_sync(
    *,
    force: bool = False,
    now: datetime | None = None,
    transport: httpx.BaseTransport | None = None,
) -> SyncSummary:
    """Apply LiteLLM prices to ``AiPricing`` for recently used models.

    ``force`` runs even when the switch is off ("Sync Now"); the scheduled run passes False.
    Never raises past the enabled check: a lock (Redis) error, an unexpected error, or the
    Celery soft time limit (``SoftTimeLimitExceeded``, re-raised out of the per-model loop) is
    recorded as a failed run and returned (the status banner is the owner's signal; the task
    does not retry). Returning on the soft limit lets the task end cleanly before the hard limit.
    """
    fixed_now = now is not None
    now = now or timezone.now()
    if not force:
        enabled = AiPricingSyncConfig.objects.filter(pk=1).values_list("enabled", flat=True)
        if not enabled.first():
            return SyncSummary(outcome=SyncOutcome.SKIPPED_DISABLED)

    with contextlib.ExitStack() as stack:
        try:
            acquired = stack.enter_context(distributed_lock(SYNC_LOCK_KEY, timeout=300))
        except Exception as exc:
            logger.exception("ai_pricing.sync_lock_failed")
            return _record_failure(
                now=now, error=f"Could not acquire sync lock ({type(exc).__name__})."
            )
        if not acquired:
            logger.info("ai_pricing.sync_skipped reason=locked")
            return SyncSummary(outcome=SyncOutcome.SKIPPED_LOCKED)
        try:
            return _run_locked(now=now, fixed_now=fixed_now, transport=transport)
        except Exception as exc:
            # The stored/audited error carries the class name only (exception text may hold
            # response or DB content); the full traceback goes to the server log only.
            logger.exception("ai_pricing.sync_crashed")
            return _record_failure(
                now=now, error=f"Sync failed unexpectedly ({type(exc).__name__})"
            )
