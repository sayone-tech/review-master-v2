"""Append-only QuerySet for the credit ledger (D-05, CRED-03)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from django.db import models

from apps.credits.exceptions import AppendOnlyViolation

if TYPE_CHECKING:
    from apps.credits.models import CreditTransaction  # noqa: F401 - string forward ref below


class CreditTransactionQuerySet(models.QuerySet["CreditTransaction"]):
    """Ledger rows are insert-only. Plain ``create`` / ``bulk_create`` insert freely, but
    ``bulk_create(update_conflicts=True)`` is rejected (it is an upsert that rewrites rows);
    the only mutation is the status CAS below (``update`` also backs ``bulk_update``)."""

    def bulk_create(
        self,
        objs: Any,
        batch_size: int | None = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Any = None,
        unique_fields: Any = None,
    ) -> Any:
        # Explicit signature so update_conflicts is caught whether passed by keyword or position.
        if update_conflicts:
            raise AppendOnlyViolation(
                "CreditTransaction rows are append-only; "
                "bulk_create(update_conflicts=True) would rewrite rows."
            )
        return super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )

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
