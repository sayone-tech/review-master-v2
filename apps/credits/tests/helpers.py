"""Test-only helpers for credits (used by Phase 30 reserve/commit/refund tests)."""

from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import F, Sum
from django.utils import timezone

from apps.credits.models import CreditTransaction, ShopCreditBalance


def assert_ledger_reconciles(balance: ShopCreditBalance) -> None:
    """Assert ``consumed_credits`` equals SUM(-delta) of live CONSUMPTION rows.

    Live means RESERVED or COMMITTED; REFUNDED rows no longer count. The headline
    "used" figure always reads the balance column, never SUM(history).
    """
    total = (
        CreditTransaction.objects.filter(
            shop_credit_balance=balance,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status__in=[CreditTransaction.Status.RESERVED, CreditTransaction.Status.COMMITTED],
        ).aggregate(total=Sum(-F("credits_delta")))["total"]
        or 0
    )
    stored = ShopCreditBalance.objects.values_list("consumed_credits", flat=True).get(pk=balance.pk)
    assert stored == total, (
        f"ledger does not reconcile: balance.consumed_credits={stored} "
        f"but SUM(-credits_delta) over live CONSUMPTION rows={total}"
    )


def age_reservation(transaction_id: int, *, minutes: int) -> None:
    """Backdate a ledger row's ``created_at`` by ``minutes`` (test-only).

    ``CreditTransaction.created_at`` is ``auto_now_add`` and the ledger queryset's own
    ``update`` raises ``AppendOnlyViolation``, so this uses the base ``models.QuerySet.update``,
    the same escape hatch the ``cas_status`` primitive relies on.
    """
    models.QuerySet.update(
        CreditTransaction.objects.filter(pk=transaction_id),
        created_at=timezone.now() - timedelta(minutes=minutes),
    )
