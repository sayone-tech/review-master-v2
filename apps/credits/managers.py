"""Append-only QuerySet for the credit ledger (D-05, CRED-03)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from django.db import models

from apps.credits.exceptions import AppendOnlyViolation

if TYPE_CHECKING:
    from apps.credits.models import CreditTransaction  # noqa: F401 - string forward ref below


class CreditTransactionQuerySet(models.QuerySet["CreditTransaction"]):
    """Ledger rows are insert-only. ``create`` / ``bulk_create`` are untouched; the only
    mutation is the status CAS below (``update`` also backs ``bulk_update``)."""

    def update(self, **kwargs: Any) -> NoReturn:
        raise AppendOnlyViolation(
            "CreditTransaction rows are append-only; use ledger.transition_status for status."
        )

    def delete(self) -> NoReturn:
        raise AppendOnlyViolation("CreditTransaction rows are append-only and cannot be deleted.")

    def cas_status(self, *, pk: int, from_status: str, to_status: str) -> int:
        """Single conditional UPDATE; returns rows affected (1 = won, 0 = lost/absent).

        Escape hatch: the only callers are ``services/ledger.py`` and
        ``CreditTransaction.save``. Calls the base ``QuerySet.update`` to bypass the guard.
        """
        return models.QuerySet.update(self.filter(pk=pk, status=from_status), status=to_status)
