"""Monthly credit lapse: unused credits of a past month expire (v0.9, Phase 31, CREN-01).

``lapse_past_balances`` is the daily, idempotent catch-up sweep (Celery Beat, 00:05 UTC).
For every past-month balance that has not lapsed yet, ``lapse_balance`` writes one LAPSED
ledger row for the remaining credits plus one ``shop.credits.lapsed`` AuditLog row, and sets the
``lapsed_at`` marker. The marker (not the ledger row) is the done-flag: a balance with nothing
remaining is marked without any ledger or audit row (D-02). ``allocated`` / ``bonus`` /
``consumed`` are never changed by a lapse.

A balance that still holds a RESERVED reservation is skipped and retried by a later sweep, so a
credit can never be forfeited while a generation is in flight (D-07).

This module is a leaf of the credits bounded context: ids and ints only, no review text
anywhere (CLAUDE.md section 22).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.lapse import list_unlapsed_past_balance_ids
from apps.credits.services.periods import current_period, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LapseOutcome:
    status: Literal["lapsed", "lapsed_zero", "skipped_held", "skipped_noop"]
    balance_id: int
    lapsed_credits: int = 0
    transaction_id: int | None = None


@dataclass(frozen=True, slots=True)
class LapseSummary:
    lapsed: int = 0
    lapsed_zero: int = 0
    skipped_held: int = 0
    skipped_noop: int = 0
    errored: int = 0
    credits_lapsed: int = 0


def lapse_balance(*, balance_id: int, now: datetime | None = None) -> LapseOutcome:
    """Lapse one balance if it is a past month, unlapsed and holds no RESERVED row.

    Runs in its own atomic block under a skip-locked row lock, re-checking every condition
    under the lock, so overlapping sweeps (or a direct call) can neither double-write nor
    lapse the current or a future month.
    """
    now = now or utc_now()
    p = current_period(now)
    with transaction.atomic():
        locked = (
            ShopCreditBalance.objects.select_for_update(skip_locked=True, of=("self",))
            .filter(
                Q(period_year__lt=p.year) | Q(period_year=p.year, period_month__lt=p.month),
                pk=balance_id,
                lapsed_at__isnull=True,
            )
            .values(
                "pk",
                "shop_id",
                "organisation_id",
                "period_year",
                "period_month",
                "allocated_credits",
                "bonus_credits",
                "consumed_credits",
            )
            .first()
        )
        if locked is None:
            # Already lapsed, locked by another sweep, or not a past period.
            return LapseOutcome(status="skipped_noop", balance_id=balance_id)

        if CreditTransaction.objects.filter(
            shop_credit_balance_id=balance_id,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status=CreditTransaction.Status.RESERVED,
        ).exists():
            return LapseOutcome(status="skipped_held", balance_id=balance_id)

        remaining = (
            locked["allocated_credits"] + locked["bonus_credits"] - locked["consumed_credits"]
        )
        transaction_id: int | None = None
        if remaining > 0:
            tx = CreditTransaction.objects.create(
                shop_credit_balance_id=balance_id,
                shop_id=locked["shop_id"],
                organisation_id=locked["organisation_id"],
                transaction_type=CreditTransaction.Type.LAPSED,
                status=CreditTransaction.Status.COMMITTED,
                credits_delta=-remaining,
                actor=None,
            )
            transaction_id = tx.pk
            AuditLog.objects.create(
                organisation_id=locked["organisation_id"],
                actor=None,
                entity_type="shop",
                entity_id=str(locked["shop_id"]),
                action="shop.credits.lapsed",
                before_data=None,
                after_data={
                    "allocated": locked["allocated_credits"],
                    "bonus": locked["bonus_credits"],
                    "consumed": locked["consumed_credits"],
                    "lapsed": remaining,
                    "period_year": locked["period_year"],
                    "period_month": locked["period_month"],
                    "transaction_id": transaction_id,
                },
            )

        # updated_at is explicit: QuerySet.update() bypasses auto_now.
        marked = ShopCreditBalance.objects.filter(pk=balance_id, lapsed_at__isnull=True).update(
            lapsed_at=now, updated_at=now
        )
        if marked != 1:
            raise RuntimeError(f"lapse marker for balance {balance_id} did not apply")

    logger.info(
        "credits.lapsed balance_id=%s shop_id=%s credits=%d",
        balance_id,
        locked["shop_id"],
        max(remaining, 0),
    )
    if remaining > 0:
        return LapseOutcome(
            status="lapsed",
            balance_id=balance_id,
            lapsed_credits=remaining,
            transaction_id=transaction_id,
        )
    return LapseOutcome(status="lapsed_zero", balance_id=balance_id)


def lapse_past_balances(*, now: datetime | None = None) -> LapseSummary:
    """Lapse every outstanding past-month balance; safe to re-run at any time.

    Pages by primary key (``pk > last``), never "select unlapsed until none": a held balance
    stays unlapsed and would otherwise loop forever. A failure on one balance is logged (ids
    only), counted, and never aborts the sweep.
    """
    now = now or utc_now()
    chunk = settings.REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE
    counters = {
        "lapsed": 0,
        "lapsed_zero": 0,
        "skipped_held": 0,
        "skipped_noop": 0,
        "errored": 0,
    }
    credits_lapsed = 0
    after_pk = 0
    while True:
        ids = list_unlapsed_past_balance_ids(now=now, after_pk=after_pk, limit=chunk)
        if not ids:
            break
        for balance_id in ids:
            try:
                outcome = lapse_balance(balance_id=balance_id, now=now)
            except SoftTimeLimitExceeded:
                raise
            except Exception:
                logger.exception("credits.lapse.failed balance_id=%s", balance_id)
                counters["errored"] += 1
                continue
            counters[outcome.status] += 1
            credits_lapsed += outcome.lapsed_credits
        after_pk = ids[-1]
        if len(ids) < chunk:
            break
    return LapseSummary(credits_lapsed=credits_lapsed, **counters)


__all__ = ["LapseOutcome", "LapseSummary", "lapse_balance", "lapse_past_balances"]
