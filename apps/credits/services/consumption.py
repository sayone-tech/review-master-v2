"""Credit consumption: reserve -> (caller's OpenAI call) -> commit / refund (v0.9, Phase 30).

Two-phase accounting for one AI reply generation:

* ``reserve_credits`` runs a short, row-locked transaction: it takes the shop balance row lock,
  raises ``consumed_credits`` through a guarded ``F()`` UPDATE and inserts a RESERVED
  CONSUMPTION row. It commits *before* the OpenAI call so no database lock is held across the
  network.
* ``commit_reservation`` settles a successful call with a status CAS only (the credits were
  already added at reserve time) and links the single ``AiUsageLog`` row in the same UPDATE.
* ``refund_reservation`` settles a failed call: a won CAS plus a guarded decrement, in one
  atomic block, so a refund can only ever happen once per reservation.

When the commit CAS loses (for example Phase 31's reaper already refunded a slow call) one
policy applies for every case (``_settle_lost_race``, D-01/D-02/D-16) and the caller never gets
an exception.

This module is a leaf of the credits bounded context: it takes plain ids and ints, never imports
the reviews app, and writes no review text, draft or moderation category anywhere (CLAUDE.md
section 22).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.common.models import AuditLog
from apps.credits.exceptions import GenerationInProgressError, InsufficientCreditsError
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.balances import get_shop_credit_balance
from apps.credits.services.allocation import ensure_balance
from apps.credits.services.ledger import transition_status

logger = logging.getLogger(__name__)

Status = CreditTransaction.Status


@dataclass(frozen=True, slots=True)
class Reservation:
    transaction_id: int
    shop_credit_balance_id: int
    shop_id: int
    organisation_id: int
    review_id: int
    credits: int
    actor_id: int | None


@dataclass(frozen=True, slots=True)
class SettleResult:
    """``outcome`` is one of committed | rededucted | free_draft | already_settled."""

    credits_charged: int
    outcome: str


@dataclass(frozen=True, slots=True)
class _TxRow:
    shop_id: int
    organisation_id: int
    review_id: int | None
    credits: int
    shop_credit_balance_id: int
    period_year: int
    period_month: int


def _read_tx(transaction_id: int) -> _TxRow | None:
    row = (
        CreditTransaction.objects.filter(pk=transaction_id)
        .values(
            "shop_id",
            "organisation_id",
            "review_id",
            "credits_delta",
            "shop_credit_balance_id",
            "shop_credit_balance__period_year",
            "shop_credit_balance__period_month",
        )
        .first()
    )
    if row is None:
        return None
    return _TxRow(
        shop_id=row["shop_id"],
        organisation_id=row["organisation_id"],
        review_id=row["review_id"],
        credits=-row["credits_delta"],
        shop_credit_balance_id=row["shop_credit_balance_id"],
        period_year=row["shop_credit_balance__period_year"],
        period_month=row["shop_credit_balance__period_month"],
    )


def reserve_credits(
    *, shop_id: int, review_id: int, credits: int, actor_id: int | None
) -> Reservation:
    """Reserve ``credits`` for one generation, or raise before writing anything.

    Raises ``ValueError`` for ``credits <= 0`` (cost 0 is rejected upstream, CCON-04),
    ``InsufficientCreditsError`` (402: ``not_enabled`` / ``exhausted``) and
    ``GenerationInProgressError`` (409: a RESERVED row already exists for the review).
    """
    if credits <= 0:
        raise ValueError("credits must be positive")

    # D-19: read-only pre-check so a 402 never materialises a balance row or writes anything.
    view = get_shop_credit_balance(shop_id=shop_id)
    if not view.is_enabled:
        raise InsufficientCreditsError(
            reason="not_enabled", required=credits, remaining=view.remaining
        )
    if view.remaining < credits:
        raise InsufficientCreditsError(
            reason="exhausted", required=credits, remaining=view.remaining
        )

    # Own atomic block inside ensure_balance; kept outside the reserve transaction below.
    balance, _ = ensure_balance(shop_id=shop_id)

    with transaction.atomic():
        locked = (
            ShopCreditBalance.objects.select_for_update(of=("self",))
            .values("allocated_credits", "bonus_credits", "consumed_credits", "organisation_id")
            .get(pk=balance.pk)
        )
        # D-12: serialised by the balance-row lock above, so this check is race-free. Filter by
        # review only so a month straddle still matches.
        if CreditTransaction.objects.filter(
            review_id=review_id,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status=Status.RESERVED,
        ).exists():
            raise GenerationInProgressError(review_id=review_id)

        total = locked["allocated_credits"] + locked["bonus_credits"]
        remaining = total - locked["consumed_credits"]
        if total == 0:
            raise InsufficientCreditsError(reason="not_enabled", required=credits, remaining=0)
        if remaining < credits:
            raise InsufficientCreditsError(
                reason="exhausted", required=credits, remaining=remaining
            )

        updated = ShopCreditBalance.objects.filter(
            pk=balance.pk,
            consumed_credits__lte=F("allocated_credits") + F("bonus_credits") - credits,
        ).update(consumed_credits=F("consumed_credits") + credits, updated_at=timezone.now())
        if updated != 1:
            raise InsufficientCreditsError(
                reason="exhausted", required=credits, remaining=remaining
            )

        tx = CreditTransaction.objects.create(
            shop_credit_balance_id=balance.pk,
            shop_id=shop_id,
            organisation_id=locked["organisation_id"],
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status=Status.RESERVED,
            credits_delta=-credits,
            review_id=review_id,
            actor_id=actor_id,
        )

    logger.info(
        "credits.reserved tx_id=%s shop_id=%s review_id=%s credits=%d",
        tx.pk,
        shop_id,
        review_id,
        credits,
    )
    return Reservation(
        transaction_id=tx.pk,
        shop_credit_balance_id=balance.pk,
        shop_id=shop_id,
        organisation_id=locked["organisation_id"],
        review_id=review_id,
        credits=credits,
        actor_id=actor_id,
    )


def commit_reservation(
    *,
    transaction_id: int,
    ai_usage_log_id: int | None,
    outcome: str,
    actor_id: int | None,
) -> SettleResult:
    """Settle a reservation as consumed (RESERVED -> COMMITTED, linking the usage log).

    Never touches the balance: the credits were added at reserve time. When the CAS loses,
    ``_settle_lost_race`` applies the late-commit policy and this function still returns.
    """
    row = _read_tx(transaction_id)
    if row is None:
        raise CreditTransaction.DoesNotExist(f"CreditTransaction {transaction_id} not found")
    with transaction.atomic():
        won = transition_status(
            transaction_id=transaction_id,
            from_status=Status.RESERVED,
            to_status=Status.COMMITTED,
            ai_usage_log_id=ai_usage_log_id,
        )
        if won:
            AuditLog.objects.create(
                organisation_id=row.organisation_id,
                actor_id=actor_id,
                entity_type="shop",
                entity_id=str(row.shop_id),
                action="shop.credits.consumed",
                before_data=None,
                after_data={
                    "transaction_id": transaction_id,
                    "review_id": row.review_id,
                    "credits": row.credits,
                    "outcome": outcome,
                    "ai_usage_log_id": ai_usage_log_id,
                    "period_year": row.period_year,
                    "period_month": row.period_month,
                },
            )
    if won:
        return SettleResult(credits_charged=row.credits, outcome="committed")
    return _settle_lost_race(
        row=row,
        transaction_id=transaction_id,
        ai_usage_log_id=ai_usage_log_id,
        actor_id=actor_id,
    )


def refund_reservation(
    *,
    transaction_id: int,
    reason: str,
    ai_usage_log_id: int | None = None,
    actor_id: int | None = None,
) -> bool:
    """Settle a reservation as refunded; True only for the call that won the CAS.

    The CAS and the balance decrement share one atomic block: a decrement that cannot apply
    (it would drive ``consumed_credits`` negative) raises ``RuntimeError`` and rolls the CAS
    back, so the row stays RESERVED for the reaper. Phase 31's reaper reuses this function.
    """
    row = _read_tx(transaction_id)
    if row is None:
        return False
    with transaction.atomic():
        if not transition_status(
            transaction_id=transaction_id,
            from_status=Status.RESERVED,
            to_status=Status.REFUNDED,
            ai_usage_log_id=ai_usage_log_id,
        ):
            return False
        updated = ShopCreditBalance.objects.filter(
            pk=row.shop_credit_balance_id, consumed_credits__gte=row.credits
        ).update(consumed_credits=F("consumed_credits") - row.credits, updated_at=timezone.now())
        if updated != 1:
            raise RuntimeError(
                f"refund of transaction {transaction_id} would drive consumed_credits negative"
            )
        AuditLog.objects.create(
            organisation_id=row.organisation_id,
            actor_id=actor_id,
            entity_type="shop",
            entity_id=str(row.shop_id),
            action="shop.credits.refunded",
            before_data=None,
            after_data={
                "transaction_id": transaction_id,
                "review_id": row.review_id,
                "credits": row.credits,
                "reason": reason,
                "ai_usage_log_id": ai_usage_log_id,
                "period_year": row.period_year,
                "period_month": row.period_month,
            },
        )
    logger.info(
        "credits.refunded tx_id=%s reason=%s credits=%d", transaction_id, reason, row.credits
    )
    return True


def _settle_lost_race(
    *,
    row: _TxRow,
    transaction_id: int,
    ai_usage_log_id: int | None,
    actor_id: int | None,
) -> SettleResult:
    """The commit CAS lost: one policy for every cause (D-01, D-02). Never raises to the caller.

    Task 1 placeholder: log and treat the draft as free. Replaced by the D-16 policy.
    """
    logger.warning(
        "credits.late_commit tx_id=%s review_id=%s outcome=free_draft",
        transaction_id,
        row.review_id,
    )
    return SettleResult(credits_charged=0, outcome="free_draft")


__all__ = [
    "Reservation",
    "SettleResult",
    "commit_reservation",
    "refund_reservation",
    "reserve_credits",
]
