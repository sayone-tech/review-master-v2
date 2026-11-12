"""Stale-reservation selection for the reaper (v0.9, Phase 31, CREN-03).

Unscoped system primitive: the reaper covers every tenant, so nothing here filters by
organisation. Read-only; the write side lives in ``services/reaper.py``. Returns ids and ints
only, never review text (CLAUDE.md section 22).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple

from django.conf import settings

from apps.credits.models import CreditTransaction


class StaleReservation(NamedTuple):
    transaction_id: int
    shop_credit_balance_id: int
    shop_id: int
    period_year: int
    period_month: int
    credits: int


def list_stale_reservations(*, now: datetime, limit: int) -> list[StaleReservation]:
    """RESERVED consumption rows strictly older than the TTL, oldest first, at most ``limit``.

    One query: the join to the balance carries the period, so the reaper's re-lapse decision
    needs no further read. The predicate and order match the partial index
    ``credit_tx_reserved_idx`` ``(status, created_at) WHERE status = 'RESERVED'``.
    """
    cutoff = now - timedelta(minutes=settings.REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES)
    rows = (
        CreditTransaction.objects.filter(
            status=CreditTransaction.Status.RESERVED,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            created_at__lt=cutoff,
        )
        .order_by("created_at", "pk")
        .values_list(
            "pk",
            "shop_credit_balance_id",
            "shop_id",
            "shop_credit_balance__period_year",
            "shop_credit_balance__period_month",
            "credits_delta",
        )[:limit]
    )
    return [
        StaleReservation(
            transaction_id=pk,
            shop_credit_balance_id=balance_id,
            shop_id=shop_id,
            period_year=year,
            period_month=month,
            credits=-delta,
        )
        for pk, balance_id, shop_id, year, month, delta in rows
    ]
