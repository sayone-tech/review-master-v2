"""Lazy creation of a shop's monthly credit balance (CRED-02).

The first credit operation for a shop in a UTC month creates exactly one
``ShopCreditBalance`` seeded from the organisation's live
``monthly_credit_allocation``. When the allocation is > 0 the same atomic block
also writes one INITIAL_ALLOCATION ledger row and one ``shop.credits.allocated``
AuditLog row, both system events (``actor=None``, D-03). With allocation 0 only the
balance row is written: no zero-amount ledger row and no audit row.

Race safety: ``get_or_create`` inserts inside its own savepoint and the unique
``(shop, period_year, period_month)`` index picks one winner. A losing caller blocks
until the winner's outer atomic commits, then re-reads the committed row with
``created=False``, so a loser never sees a balance without its INITIAL row.
"""

from __future__ import annotations

import logging

from django.db import transaction

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.periods import Period, current_period
from apps.shops.models import Shop

logger = logging.getLogger(__name__)


def ensure_balance(*, shop_id: int, period: Period | None = None) -> tuple[ShopCreditBalance, bool]:
    """Return ``(balance, created)`` for the shop in ``period`` (default: current UTC month).

    The organisation is derived from the shop row, never supplied by the caller
    (CLAUDE.md section 9). Raises ``Shop.DoesNotExist`` for an unknown shop.
    """
    period = period or current_period()
    organisation_id, allocation = (
        Shop.objects.filter(pk=shop_id)
        .values_list("organisation_id", "organisation__monthly_credit_allocation")
        .get()
    )
    with transaction.atomic():
        balance, created = ShopCreditBalance.objects.get_or_create(
            shop_id=shop_id,
            period_year=period.year,
            period_month=period.month,
            defaults={"organisation_id": organisation_id, "allocated_credits": allocation},
        )
        if created and allocation > 0:
            CreditTransaction.objects.create(
                shop_credit_balance=balance,
                shop_id=shop_id,
                organisation_id=organisation_id,
                transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION,
                status=CreditTransaction.Status.COMMITTED,
                credits_delta=allocation,
                actor=None,
            )
            AuditLog.objects.create(
                organisation_id=organisation_id,
                actor=None,
                entity_type="shop",
                entity_id=str(shop_id),
                action="shop.credits.allocated",
                before_data=None,
                after_data={
                    "period_year": period.year,
                    "period_month": period.month,
                    "allocated_credits": allocation,
                },
            )
    if created:
        logger.info(
            "credits.balance.created shop_id=%s period=%d-%02d allocated=%d",
            shop_id,
            period.year,
            period.month,
            allocation,
        )
    return balance, created
