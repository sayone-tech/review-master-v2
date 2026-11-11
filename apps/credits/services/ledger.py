"""Ledger status transitions (CRED-03, D-05, D-06).

This is the thin primitive only. Phase 30 composes commit/refund with the balance
``F()`` update inside one atomic block, and Phase 31's reaper uses REFUNDED; neither
reserve/commit/refund belongs here.
"""

from __future__ import annotations

import logging

from apps.credits.exceptions import InvalidStatusTransition
from apps.credits.models import CreditTransaction

logger = logging.getLogger(__name__)


def transition_status(*, transaction_id: int, from_status: str, to_status: str) -> bool:
    """Move one ledger row ``from_status`` -> ``to_status`` with a single conditional UPDATE.

    Returns True when this call changed the row, False when the row is absent or was
    already settled (so a repeated or racing call is a safe no-op). Raises
    ``InvalidStatusTransition`` for any pair other than RESERVED -> COMMITTED/REFUNDED.
    """
    if (from_status, to_status) not in CreditTransaction.ALLOWED_STATUS_TRANSITIONS:
        raise InvalidStatusTransition(f"{from_status} -> {to_status} is not an allowed transition")
    won = (
        CreditTransaction.objects.cas_status(
            pk=transaction_id, from_status=from_status, to_status=to_status
        )
        == 1
    )
    logger.debug(
        "credits.ledger.transition id=%s %s->%s won=%s", transaction_id, from_status, to_status, won
    )
    return won
