"""Virtual-balance read contract (CRED-05).

A shop with no balance row for the period reports the organisation's LIVE
``monthly_credit_allocation`` as both ``allocated`` and ``remaining``. Reads never
create, update or delete a row: materialisation is a write-side concern
(``services.allocation.ensure_balance``), and locking the allocation in on read would
break the next-month rule (CRED-06).

These selectors are unscoped primitives. Tenant / Staff scoping is the caller's job
(Phase 32/33 endpoints). They never filter on ``is_active`` (D-13): inactive shops are
computed exactly like active ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import (
    BooleanField,
    ExpressionWrapper,
    F,
    FilteredRelation,
    IntegerField,
    Q,
    QuerySet,
    Value,
)
from django.db.models.functions import Coalesce

from apps.credits.models import ShopCreditBalance
from apps.credits.services.periods import Period, current_period, next_period_start


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
    """Return the shop's balance for ``period`` (default: current UTC month).

    Uses 1 query when the row exists, 2 when it does not (the second reads the live org
    allocation). Raises ``Shop.DoesNotExist`` for an unknown ``shop_id`` when there is no
    row; callers resolve the shop under tenant scope first.
    """
    p = period or current_period()
    row = (
        ShopCreditBalance.objects.filter(shop_id=shop_id, period_year=p.year, period_month=p.month)
        .values("allocated_credits", "bonus_credits", "consumed_credits")
        .first()
    )
    if row is not None:
        allocated = row["allocated_credits"]
        bonus = row["bonus_credits"]
        consumed = row["consumed_credits"]
        materialized = True
    else:
        # Function-level import keeps the credits -> shops edge out of module scope.
        from apps.shops.models import Shop

        allocated = (
            Shop.objects.filter(pk=shop_id)
            .values_list("organisation__monthly_credit_allocation", flat=True)
            .get()
        )
        bonus = 0
        consumed = 0
        materialized = False
    return CreditBalanceView(
        shop_id=shop_id,
        year=p.year,
        month=p.month,
        allocated=allocated,
        bonus=bonus,
        consumed=consumed,
        remaining=allocated + bonus - consumed,
        is_enabled=(allocated + bonus) > 0,
        is_materialized=materialized,
        renews_on=next_period_start(p).date(),
    )


def annotate_credit_state(
    *, queryset: QuerySet[Any], period: Period | None = None
) -> QuerySet[Any]:
    """Annotate a Shop queryset with the virtual balance in one query, never writing.

    Adds ``credit_allocated``, ``credit_bonus``, ``credit_consumed``, ``credit_remaining``
    (ints) and ``credit_materialized`` (bool). ``queryset`` must be a ``Shop`` queryset.
    One LEFT JOIN restricted to the period (at most one match, by the unique constraint)
    plus Coalesce over the organisation's live allocation: no fan-out, no N+1. Wiring this
    into ``apps/shops/selectors/shops.py::list_shops`` is Phase 32/33 work.
    """
    p = period or current_period()
    annotated: QuerySet[Any] = (
        queryset.annotate(
            _cb=FilteredRelation(
                "credit_balances",
                condition=Q(
                    credit_balances__period_year=p.year,
                    credit_balances__period_month=p.month,
                ),
            )
        )
        .annotate(
            credit_allocated=Coalesce(
                F("_cb__allocated_credits"),
                F("organisation__monthly_credit_allocation"),
                output_field=IntegerField(),
            ),
            credit_bonus=Coalesce(F("_cb__bonus_credits"), Value(0), output_field=IntegerField()),
            credit_consumed=Coalesce(
                F("_cb__consumed_credits"), Value(0), output_field=IntegerField()
            ),
            credit_materialized=ExpressionWrapper(
                Q(_cb__isnull=False), output_field=BooleanField()
            ),
        )
        .annotate(
            credit_remaining=ExpressionWrapper(
                F("credit_allocated") + F("credit_bonus") - F("credit_consumed"),
                output_field=IntegerField(),
            )
        )
    )
    return annotated
