"""Reservation reaper: refunds abandoned credit reservations (v0.9, Phase 31, CREN-03).

``reap_stale_reservations`` runs every 10 minutes (Celery Beat). It selects RESERVED consumption
rows older than ``REVIEWBEE_CREDIT_RESERVATION_TTL_MINUTES`` (oldest first, at most
``REVIEWBEE_CREDIT_REAPER_BATCH_SIZE``) and releases each through Phase 30's
``refund_reservation`` with reason ``reaped_stale``. Afterwards it re-lapses the past-month
balances it touched (D-08), so a reservation that straddled a month end no longer blocks the
lapse.

Concurrency choice (CAS-only, no ``skip_locked`` pre-select): ``refund_reservation`` already owns
a per-row atomic block and its RESERVED -> REFUNDED compare-and-set. A concurrent late commit or
a second reaper blocks on the winner's row lock and then matches 0 rows, so the loser simply gets
``False``. A pre-lock would need an outer transaction holding up to a whole batch of row locks
for no safety gain. This supersedes the ROADMAP note that mentions skip_locked (CONTEXT D-10 left
it to the planner).

There is deliberately no outer transaction around the loop: one failure must not roll back the
refunds already made, and an outer block would turn the CAS into a savepoint.

Ids and ints only in logs and Sentry messages (CLAUDE.md section 22); this module never reads
review text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import sentry_sdk
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings

from apps.credits.selectors.reservations import list_stale_reservations
from apps.credits.services.consumption import refund_reservation
from apps.credits.services.lapse import lapse_balance
from apps.credits.services.periods import current_period, utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReapSummary:
    reaped: int
    skipped: int
    errored: int
    lapsed_after: int


def reap_stale_reservations(*, now: datetime | None = None) -> ReapSummary:
    """Refund every stale reservation in this batch; safe to re-run and to overlap.

    * refund won -> ``reaped`` (one WARNING log per row, ids and credits only).
    * refund lost the CAS or the row vanished (a late commit or another reaper got there first)
      -> ``skipped``; nothing is written.
    * ``RuntimeError`` (the refund cannot apply: ``consumed_credits`` is below the reservation)
      -> ``errored`` plus one Sentry error carrying only the ids (D-09); the row stays RESERVED
      and, because ``lapse_balance`` re-checks RESERVED rows, its balance stays unlapsed.
    * any other exception is isolated the same way; ``SoftTimeLimitExceeded`` is re-raised.
    """
    now = now or utc_now()
    current = current_period(now)
    batch = settings.REVIEWBEE_CREDIT_REAPER_BATCH_SIZE
    rows = list_stale_reservations(now=now, limit=batch)

    reaped = skipped = errored = lapsed_after = 0
    touched: set[int] = set()

    for row in rows:
        try:
            won = refund_reservation(
                transaction_id=row.transaction_id, reason="reaped_stale", actor_id=None
            )
        except SoftTimeLimitExceeded:
            raise
        except RuntimeError:
            errored += 1
            message = (
                f"credits.reaper.refund_failed tx_id={row.transaction_id} "
                f"balance_id={row.shop_credit_balance_id}"
            )
            logger.warning(message)
            sentry_sdk.capture_message(message, level="error")
            continue
        except Exception:
            errored += 1
            logger.exception(
                "credits.reaper.failed tx_id=%s balance_id=%s",
                row.transaction_id,
                row.shop_credit_balance_id,
            )
            continue

        if not won:
            skipped += 1
            continue

        reaped += 1
        logger.warning(
            "credits.reaped tx_id=%s balance_id=%s shop_id=%s credits=%d",
            row.transaction_id,
            row.shop_credit_balance_id,
            row.shop_id,
            row.credits,
        )
        if (row.period_year, row.period_month) < (current.year, current.month):
            touched.add(row.shop_credit_balance_id)

    # D-08: a refund may have freed a past-month balance to lapse. lapse_balance re-checks for
    # remaining RESERVED rows under its lock, so a balance that still holds one stays unlapsed.
    for balance_id in sorted(touched):
        try:
            outcome = lapse_balance(balance_id=balance_id, now=now)
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            errored += 1
            logger.exception("credits.reaper.lapse_failed balance_id=%s", balance_id)
            continue
        if outcome.status in ("lapsed", "lapsed_zero"):
            lapsed_after += 1

    if reaped:
        sentry_sdk.capture_message(f"credits.reaper.reaped count={reaped}", level="warning")

    return ReapSummary(reaped=reaped, skipped=skipped, errored=errored, lapsed_after=lapsed_after)


__all__ = ["ReapSummary", "reap_stale_reservations"]
