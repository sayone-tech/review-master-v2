"""Virtual-balance read contract (stub for TDD RED)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import QuerySet

from apps.credits.services.periods import Period


@dataclass(frozen=True, slots=True)
class CreditBalanceView:
    shop_id: int
    year: int
    month: int
    allocated: int
    bonus: int
    consumed: int
    remaining: int
    is_enabled: bool
    is_materialized: bool
    renews_on: date


def get_shop_credit_balance(*, shop_id: int, period: Period | None = None) -> CreditBalanceView:
    return CreditBalanceView(shop_id, 0, 0, 0, 0, 0, 0, False, False, date(1970, 1, 1))


def annotate_credit_state(
    *, queryset: QuerySet[Any], period: Period | None = None
) -> QuerySet[Any]:
    return queryset
