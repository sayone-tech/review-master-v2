"""Append-only AI pricing management (Phase 35).

Existing ``AiPricing`` rows are never edited except to (a) set ``effective_to`` on the row being
closed by a new price and (b) reset it to ``NULL`` when its scheduled successor is deleted.
``AiUsageLog`` is never touched. Every change writes one platform-level ``AuditLog`` row
(organisation ``NULL``) and drops the missing-pricing cache once the transaction commits.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.common.models import AuditLog
from apps.integrations.openai.models import AiPricing
from apps.integrations.openai.services.pricing_cache import invalidate_missing_pricing_cache

logger = logging.getLogger(__name__)

GRACE = timedelta(seconds=5)


class PricingError(Exception):
    code: str = "pricing_error"
    detail: str = "Pricing change failed."

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class BackdatedPriceError(PricingError):
    code = "backdated"
    detail = "Prices cannot start in the past."


STARTS_BEFORE_CURRENT_DETAIL = "A new price must start after the current price's start time."


class ScheduledPriceExistsError(PricingError):
    code = "scheduled_price_exists"
    detail = "A scheduled price already exists for this model. Delete it first."


class PriceNotScheduledError(PricingError):
    code = "price_not_scheduled"
    detail = "Only a scheduled price that hasn't started yet can be deleted."


class ConcurrentPriceChangeError(PricingError):
    code = "concurrent_change"
    detail = (
        "Another change to this model's pricing happened at the same time. Reload and try again."
    )


def _price(value: Decimal) -> str:
    return str(Decimal(value).quantize(Decimal("0.00000001")))


def _snapshot(row: AiPricing) -> dict[str, Any]:
    return {
        "model": row.model,
        "input_token_price_per_1m": _price(row.input_token_price_per_1m),
        "output_token_price_per_1m": _price(row.output_token_price_per_1m),
        "cached_token_price_per_1m": _price(row.cached_token_price_per_1m),
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "source": row.source,
    }


@transaction.atomic
def add_price(
    *,
    model: str,
    input_token_price_per_1m: Decimal,
    output_token_price_per_1m: Decimal,
    cached_token_price_per_1m: Decimal,
    effective_from: datetime,
    actor: User | None,
    source: str = AiPricing.Source.MANUAL,
    now: datetime | None = None,
) -> AiPricing:
    """Add a price starting at ``effective_from``, closing the model's open row at that instant.

    Raises ``BackdatedPriceError``, ``ScheduledPriceExistsError`` (a not-yet-started price is
    already queued) or ``ConcurrentPriceChangeError`` (the one-open-row constraint tripped).
    """
    model = model.strip()
    if not model:
        raise ValueError("model must not be empty")
    now = now or timezone.now()

    open_row = (
        AiPricing.objects.select_for_update().filter(model=model, effective_to__isnull=True).first()
    )
    if effective_from < now - GRACE:
        raise BackdatedPriceError
    if open_row is not None and open_row.effective_from > now:
        raise ScheduledPriceExistsError
    if open_row is not None and effective_from <= open_row.effective_from:
        # Inside the 5 s grace a new price could otherwise close the open row at or before
        # its own start, leaving a zero/negative-length window.
        raise BackdatedPriceError(STARTS_BEFORE_CURRENT_DETAIL)

    before = _snapshot(open_row) if open_row is not None else None
    if open_row is not None:
        open_row.effective_to = effective_from
        open_row.save(update_fields=["effective_to"])
    try:
        with transaction.atomic():
            new = AiPricing.objects.create(
                model=model,
                input_token_price_per_1m=input_token_price_per_1m,
                output_token_price_per_1m=output_token_price_per_1m,
                cached_token_price_per_1m=cached_token_price_per_1m,
                effective_from=effective_from,
                effective_to=None,
                source=source,
                created_by=actor,
            )
    except IntegrityError as exc:
        raise ConcurrentPriceChangeError from exc

    AuditLog.objects.create(
        organisation=None,
        actor=actor,
        entity_type="ai_pricing",
        entity_id=str(new.pk),
        action="ai_pricing.added",
        before_data=before,
        after_data=_snapshot(new),
    )
    transaction.on_commit(invalidate_missing_pricing_cache)
    logger.info("ai_pricing.added model=%s pricing_id=%s source=%s", model, new.pk, source)
    return new


@transaction.atomic
def delete_scheduled_price(*, pricing_id: int, actor: User, now: datetime | None = None) -> None:
    """Delete a not-yet-started price and re-open its predecessor (``effective_to`` -> NULL).

    Raises ``AiPricing.DoesNotExist`` for an unknown id and ``PriceNotScheduledError`` when the
    price has already started.
    """
    now = now or timezone.now()
    row = AiPricing.objects.select_for_update().get(pk=pricing_id)
    if row.effective_from <= now:
        raise PriceNotScheduledError

    predecessor = (
        AiPricing.objects.select_for_update()
        .filter(model=row.model, effective_to=row.effective_from)
        .first()
    )
    before = _snapshot(row)
    row.delete()
    if predecessor is not None:
        predecessor.effective_to = None
        predecessor.save(update_fields=["effective_to"])

    AuditLog.objects.create(
        organisation=None,
        actor=actor,
        entity_type="ai_pricing",
        entity_id=str(pricing_id),
        action="ai_pricing.deleted",
        before_data=before,
        after_data=None,
    )
    transaction.on_commit(invalidate_missing_pricing_cache)
    logger.info("ai_pricing.deleted model=%s pricing_id=%s", before["model"], pricing_id)
