"""Superadmin bonus top-up (CSUP-01).

One atomic block per allocation: lock the organisation row, materialise the shop's current-month
balance with ``ensure_balance``, lock the balance row, raise ``bonus_credits`` with ``F()``, then
write one BONUS_ALLOCATION ledger row and one ``shop.credits.bonus_allocated`` AuditLog row. The
lock order is organisation row -> balance row, the same as ``update_organisation``, so a
bonus-created zero row can never slip past a concurrent 0 -> N allocation edit.

The period echo is checked before any write (a stale dialog must never materialise a row or
credit the wrong month). Only ids and integers go to logs and the audit row; the free-text reason
is stored only in ``CreditTransaction.note`` (CLAUDE.md section 22).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.common.models import AuditLog
from apps.credits.exceptions import PeriodMismatchError, ShopNotAvailableError
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.balances import get_shop_credit_balance
from apps.credits.services.allocation import ensure_balance
from apps.credits.services.periods import Period, current_period
from apps.organisations.models import Organisation
from apps.shops.models import Shop

logger = logging.getLogger(__name__)

MIN_BONUS = 1
MAX_BONUS = 10_000


@dataclass(frozen=True, slots=True)
class BonusResult:
    shop_id: int
    period_year: int
    period_month: int
    allocated: int
    bonus: int
    consumed: int
    remaining: int
    transaction_id: int


def allocate_bonus(
    *, shop_id: int, amount: int, reason: str | None, period: Period, actor_id: int
) -> BonusResult:
    """Add ``amount`` bonus credits to the shop's current-month balance.

    Raises ``ValueError`` for an out-of-range amount, ``PeriodMismatchError`` when ``period`` is
    not the current UTC month (read-only, D-12) and ``ShopNotAvailableError`` for an unknown or
    inactive shop or a DELETED organisation (D-19; DISABLED organisations are allowed, D-03).
    """
    if not MIN_BONUS <= amount <= MAX_BONUS:
        raise ValueError(f"amount must be between {MIN_BONUS} and {MAX_BONUS}")

    current = current_period()  # read once so the check and the write use the same month
    if period != current:
        try:
            balance_view = get_shop_credit_balance(shop_id=shop_id, period=current)
        except Shop.DoesNotExist as exc:
            raise ShopNotAvailableError(shop_id=shop_id) from exc
        raise PeriodMismatchError(current=current, balance=balance_view)

    org_id = (
        Shop.objects.filter(pk=shop_id, is_active=True)
        .exclude(organisation__status=Organisation.Status.DELETED)
        .values_list("organisation_id", flat=True)
        .first()
    )
    if org_id is None:
        raise ShopNotAvailableError(shop_id=shop_id)

    note = (reason or "").strip() or None

    with transaction.atomic():
        Organisation.objects.select_for_update(of=("self",)).filter(pk=org_id).values_list(
            "pk", flat=True
        ).get()
        balance, _ = ensure_balance(shop_id=shop_id, period=period)
        locked = (
            ShopCreditBalance.objects.select_for_update(of=("self",))
            .values("allocated_credits", "bonus_credits", "consumed_credits")
            .get(pk=balance.pk)
        )
        before = locked["bonus_credits"]
        ShopCreditBalance.objects.filter(pk=balance.pk).update(
            bonus_credits=F("bonus_credits") + amount, updated_at=timezone.now()
        )
        tx = CreditTransaction.objects.create(
            shop_credit_balance_id=balance.pk,
            shop_id=shop_id,
            organisation_id=org_id,
            transaction_type=CreditTransaction.Type.BONUS_ALLOCATION,
            status=CreditTransaction.Status.COMMITTED,
            credits_delta=amount,
            actor_id=actor_id,
            note=note,
        )
        AuditLog.objects.create(
            organisation_id=org_id,
            actor_id=actor_id,
            entity_type="shop",
            entity_id=str(shop_id),
            action="shop.credits.bonus_allocated",
            before_data={"bonus_credits": before},
            after_data={
                "amount": amount,
                "bonus_credits": before + amount,
                "has_reason": note is not None,
                "transaction_id": tx.pk,
                "period_year": period.year,
                "period_month": period.month,
            },
        )

    logger.info(
        "credits.bonus.allocated shop_id=%s organisation_id=%s amount=%d transaction_id=%s",
        shop_id,
        org_id,
        amount,
        tx.pk,
    )
    allocated = locked["allocated_credits"]
    bonus = before + amount
    consumed = locked["consumed_credits"]
    return BonusResult(
        shop_id=shop_id,
        period_year=period.year,
        period_month=period.month,
        allocated=allocated,
        bonus=bonus,
        consumed=consumed,
        remaining=allocated + bonus - consumed,
        transaction_id=tx.pk,
    )
