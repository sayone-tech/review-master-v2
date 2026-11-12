"""Ledger status transitions (CRED-03, D-05, D-06).

This is the thin primitive only. Phase 30 composes reserve/commit/refund with the balance
``F()`` update inside one atomic block in ``services/consumption.py``, and Phase 31's reaper
reuses its refund; none of that belongs here.
"""

from __future__ import annotations

import logging

from apps.credits.exceptions import InvalidStatusTransition
from apps.credits.models import CreditTransaction

logger = logging.getLogger(__name__)


def transition_status(
    *,
    transaction_id: int,
    from_status: str,
    to_status: str,
    ai_usage_log_id: int | None = None,
) -> bool:
    """Move one ledger row ``from_status`` -> ``to_status`` with a single conditional UPDATE.

    Returns True when this call changed the row, False when the row is absent or was
    already settled (so a repeated or racing call is a safe no-op). Raises
    ``InvalidStatusTransition`` for any pair other than RESERVED -> COMMITTED/REFUNDED.

    When ``ai_usage_log_id`` is given it is written in the same conditional UPDATE as the
    status (D-14), so a lost CAS leaves the link NULL.
    """
    if (from_status, to_status) not in CreditTransaction.ALLOWED_STATUS_TRANSITIONS:
        raise InvalidStatusTransition(f"{from_status} -> {to_status} is not an allowed transition")
    won = (
        CreditTransaction.objects.cas_status(
            pk=transaction_id,
            from_status=from_status,
            to_status=to_status,
            ai_usage_log_id=ai_usage_log_id,
        )
        == 1
    )
    logger.debug(
        "credits.ledger.transition id=%s %s->%s won=%s", transaction_id, from_status, to_status, won
    )
    return won
