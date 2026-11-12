"""Lapse sweep selection (v0.9, Phase 31, CREN-01).

Unscoped system primitive: the daily sweep covers every tenant, so nothing here filters by
organisation, and it never filters ``is_active`` (Phase 29 D-13): inactive shops lapse exactly
like active ones. Read-only; the write side lives in ``services/lapse.py``.
"""

from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from apps.credits.models import ShopCreditBalance
from apps.credits.services.periods import current_period


def list_unlapsed_past_balance_ids(*, now: datetime, after_pk: int, limit: int) -> list[int]:
    """Primary keys of unlapsed balances for a month before ``now``'s UTC month.

    Keyset-paged by ``pk`` (``pk > after_pk``, ascending) so a balance that stays unlapsed
    (a held reservation) can never make the sweep loop forever. One query, no joins; served by
    the partial index ``credit_bal_unlapsed_idx``.
    """
    p = current_period(now)
    return list(
        ShopCreditBalance.objects.filter(
            Q(period_year__lt=p.year) | Q(period_year=p.year, period_month__lt=p.month),
            lapsed_at__isnull=True,
            pk__gt=after_pk,
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:limit]
    )
