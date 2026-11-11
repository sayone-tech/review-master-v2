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

The organisation-edit path (CRED-06) uses the set-based helpers ``materialise_org_balances``
and ``raise_zero_balances`` below instead of looping ``ensure_balance`` (D-20; this supersedes
"``ensure_balance`` is the only materialisation path" for that case only: bonus and
consumption still call ``ensure_balance``). The caller must hold the organisation row lock
inside its own ``transaction.atomic``; the global lock order is organisation row -> balance
rows.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

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


def _write_initial_ledger_and_audit(
    *,
    organisation_id: int,
    allocation: int,
    period: Period,
    balance_shop_ids: list[tuple[int, int]],
) -> None:
    """Insert INITIAL_ALLOCATION + ``shop.credits.allocated`` rows, as ``ensure_balance`` does.

    ``balance_shop_ids`` is ``[(balance_pk, shop_id), ...]`` in shop pk order. Balances that
    already hold an INITIAL row are skipped, so a retry never double-writes.
    """
    if not balance_shop_ids:
        return
    already = set(
        CreditTransaction.objects.filter(
            shop_credit_balance_id__in=[b for b, _ in balance_shop_ids],
            transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION,
        ).values_list("shop_credit_balance_id", flat=True)
    )
    pending = [(b, s) for b, s in balance_shop_ids if b not in already]
    if not pending:
        return
    CreditTransaction.objects.bulk_create(
        [
            CreditTransaction(
                shop_credit_balance_id=balance_pk,
                shop_id=shop_id,
                organisation_id=organisation_id,
                transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION,
                status=CreditTransaction.Status.COMMITTED,
                credits_delta=allocation,
                actor=None,
            )
            for balance_pk, shop_id in pending
        ],
        ignore_conflicts=True,
    )
    AuditLog.objects.bulk_create(
        [
            AuditLog(
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
            for _, shop_id in pending
        ]
    )


def materialise_org_balances(*, organisation_id: int, allocation: int, period: Period) -> int:
    """Create ``period`` rows at ``allocation`` for every shop of the organisation lacking one.

    Active and inactive shops alike (Phase 29 D-13). Writes the same rows as looping
    ``ensure_balance`` would (balance; plus INITIAL_ALLOCATION and ``shop.credits.allocated``
    when ``allocation > 0``) in a fixed number of queries. Existing rows are never touched,
    and a concurrent ``ensure_balance`` winner keeps its row. Returns the number of shops
    that lacked a row. Caller holds the organisation row lock inside its own atomic block.
    """
    have = set(
        ShopCreditBalance.objects.filter(
            organisation_id=organisation_id, period_year=period.year, period_month=period.month
        ).values_list("shop_id", flat=True)
    )
    missing = [
        shop_id
        for shop_id in Shop.objects.filter(organisation_id=organisation_id)
        .order_by("pk")
        .values_list("pk", flat=True)
        if shop_id not in have
    ]
    if not missing:
        return 0
    ShopCreditBalance.objects.bulk_create(
        [
            ShopCreditBalance(
                shop_id=shop_id,
                organisation_id=organisation_id,
                period_year=period.year,
                period_month=period.month,
                allocated_credits=allocation,
            )
            for shop_id in missing
        ],
        ignore_conflicts=True,
    )
    if allocation > 0:
        rows = list(
            ShopCreditBalance.objects.filter(
                shop_id__in=missing, period_year=period.year, period_month=period.month
            )
            .order_by("shop_id")
            .values_list("pk", "shop_id")
        )
        _write_initial_ledger_and_audit(
            organisation_id=organisation_id,
            allocation=allocation,
            period=period,
            balance_shop_ids=rows,
        )
    logger.info(
        "credits.balances.materialised organisation_id=%s period=%d-%02d allocation=%d created=%d",
        organisation_id,
        period.year,
        period.month,
        allocation,
        len(missing),
    )
    return len(missing)


def raise_zero_balances(*, organisation_id: int, allocation: int, period: Period) -> int:
    """Raise the organisation's zero-allocation ``period`` rows to ``allocation`` (0 -> N).

    A bonus on a 0-allocation organisation creates a zero row that must pick up the new
    allocation immediately. Bonus and consumed columns are untouched. Writes the same
    INITIAL_ALLOCATION and ``shop.credits.allocated`` rows ``ensure_balance`` would at
    ``allocation``. Returns the number of rows raised. Caller holds the organisation lock.
    """
    if allocation <= 0:
        raise ValueError("allocation must be positive")
    rows = list(
        ShopCreditBalance.objects.filter(
            organisation_id=organisation_id,
            period_year=period.year,
            period_month=period.month,
            allocated_credits=0,
        )
        .order_by("shop_id")
        .values_list("pk", "shop_id")
    )
    if not rows:
        return 0
    # QuerySet.update() does not fire auto_now, so updated_at is set explicitly.
    ShopCreditBalance.objects.filter(pk__in=[pk for pk, _ in rows], allocated_credits=0).update(
        allocated_credits=allocation, updated_at=timezone.now()
    )
    _write_initial_ledger_and_audit(
        organisation_id=organisation_id,
        allocation=allocation,
        period=period,
        balance_shop_ids=rows,
    )
    logger.info(
        "credits.balances.raised organisation_id=%s period=%d-%02d allocation=%d raised=%d",
        organisation_id,
        period.year,
        period.month,
        allocation,
        len(rows),
    )
    return len(rows)
