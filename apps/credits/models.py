"""AI reply credits: per-shop monthly balance + append-only ledger (v0.9, Phase 29).

Other apps are referenced only through string FKs so ``credits`` stays a leaf
bounded context (no model imports from shops / reviews / organisations / openai).
"""

from __future__ import annotations

from typing import Any, ClassVar, NoReturn

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.credits.exceptions import AppendOnlyViolation, InvalidStatusTransition
from apps.credits.managers import CreditTransactionQuerySet


class ShopCreditBalance(models.Model):
    """One row per shop per UTC month, created lazily by ``ensure_balance``.

    Invariants are DB-enforced (CheckConstraints) so SQLite and PostgreSQL agree.
    NOTE: ``updated_at`` uses ``auto_now``, which fires only on ``save()``. Any future
    ``QuerySet.update()`` on balances MUST set ``updated_at`` explicitly.

    ``lapsed_at`` is the only non-counter field written after creation, and only by the
    lapse service (``apps/credits/services/lapse.py``), once (NULL -> timestamp).
    """

    # db_index=False on shop/organisation: the unique (shop, year, month) and the
    # (organisation, year, month) composite indexes already lead with them.
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.PROTECT,
        related_name="credit_balances",
        db_index=False,
    )
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=False,
    )
    period_year = models.SmallIntegerField()
    period_month = models.SmallIntegerField()
    allocated_credits = models.IntegerField()
    bonus_credits = models.IntegerField(default=0)
    consumed_credits = models.IntegerField(default=0)
    # Lapse done-marker: written only by services/lapse.py, NULL -> timestamp once. No column
    # index (see the partial index in Meta).
    lapsed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["shop", "period_year", "period_month"],
                name="credit_balance_shop_period_uniq",
            ),
            models.CheckConstraint(
                condition=Q(period_month__gte=1, period_month__lte=12),
                name="credit_balance_month_range",
            ),
            models.CheckConstraint(
                condition=Q(
                    allocated_credits__gte=0, bonus_credits__gte=0, consumed_credits__gte=0
                ),
                name="credit_balance_nonneg",
            ),
            models.CheckConstraint(
                condition=Q(consumed_credits__lte=F("allocated_credits") + F("bonus_credits")),
                name="credit_balance_no_overspend",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "period_year", "period_month"],
                name="credit_bal_org_period_idx",
            ),
            # The unlapsed set is ~one row per active shop plus stragglers, while the table
            # grows by shops x months; the daily lapse sweep predicate is exactly that partial
            # set (mirrors credit_tx_reserved_idx).
            models.Index(
                fields=["period_year", "period_month"],
                condition=Q(lapsed_at__isnull=True),
                name="credit_bal_unlapsed_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"ShopCreditBalance(shop={self.shop_id} {self.period_year}-{self.period_month:02d})"


class CreditTransaction(models.Model):
    """Append-only credit ledger row (full schema shipped now, D-01)."""

    class Type(models.TextChoices):
        INITIAL_ALLOCATION = "INITIAL_ALLOCATION", "Initial allocation"
        BONUS_ALLOCATION = "BONUS_ALLOCATION", "Bonus allocation"
        CONSUMPTION = "CONSUMPTION", "Consumption"
        LAPSED = "LAPSED", "Lapsed"

    class Status(models.TextChoices):
        RESERVED = "RESERVED", "Reserved"
        COMMITTED = "COMMITTED", "Committed"
        REFUNDED = "REFUNDED", "Refunded"

    # D-06: the only legal status moves; anything else (incl. COMMITTED -> REFUNDED) is rejected.
    ALLOWED_STATUS_TRANSITIONS: ClassVar[frozenset[tuple[str, str]]] = frozenset(
        {
            (Status.RESERVED, Status.COMMITTED),
            (Status.RESERVED, Status.REFUNDED),
        }
    )

    shop_credit_balance = models.ForeignKey(
        ShopCreditBalance,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    # Denormalised for ledger reads; covered by the (shop, created_at) and
    # (organisation, created_at) indexes below, so no per-FK index.
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="+", db_index=False
    )
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=False,
    )
    transaction_type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMMITTED)
    credits_delta = models.IntegerField()
    review = models.ForeignKey(
        "reviews.Review",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    ai_usage_log = models.ForeignKey(
        "openai.AiUsageLog",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credit_transactions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # D-04: NULL means "no note" on an append-only row.
    note = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    created_at = models.DateTimeField(auto_now_add=True)

    objects: CreditTransactionQuerySet = CreditTransactionQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["shop_credit_balance"],
                condition=Q(transaction_type="INITIAL_ALLOCATION"),
                name="credit_tx_one_initial_per_balance",
            ),
            models.UniqueConstraint(
                fields=["shop_credit_balance"],
                condition=Q(transaction_type="LAPSED"),
                name="credit_tx_one_lapse_per_balance",
            ),
            models.CheckConstraint(
                condition=Q(transaction_type="CONSUMPTION") | Q(status="COMMITTED"),
                name="credit_tx_only_consumption_reserved",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        transaction_type__in=["INITIAL_ALLOCATION", "BONUS_ALLOCATION"],
                        credits_delta__gt=0,
                    )
                    | Q(transaction_type__in=["CONSUMPTION", "LAPSED"], credits_delta__lt=0)
                ),
                name="credit_tx_delta_sign",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["shop", "created_at"], name="credit_tx_shop_created_idx"),
            models.Index(fields=["organisation", "created_at"], name="credit_tx_org_created_idx"),
            models.Index(
                fields=["status", "created_at"],
                condition=Q(status="RESERVED"),
                name="credit_tx_reserved_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"CreditTransaction({self.transaction_type} {self.credits_delta:+d} {self.status})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Insert freely; for an existing row only a status-only save is allowed (D-05).

        A status-only save is the same CAS as ``ledger.transition_status`` (RESERVED ->
        COMMITTED/REFUNDED), so a stale or already-settled instance fails closed.
        """
        if self._state.adding:
            # WR-01: force a plain INSERT so a new instance carrying an existing pk
            # collides (IntegrityError) instead of Django's UPDATE-then-INSERT rewriting it.
            kwargs["force_insert"] = True
            super().save(*args, **kwargs)
            return
        update_fields = kwargs.get("update_fields")
        if update_fields is None and len(args) > 3:  # positional save(..., update_fields)
            update_fields = args[3]
        if update_fields is None or set(update_fields) != {"status"}:
            raise AppendOnlyViolation(
                "CreditTransaction rows are append-only; only save(update_fields=['status'])."
            )
        if (self.Status.RESERVED, self.status) not in self.ALLOWED_STATUS_TRANSITIONS:
            raise InvalidStatusTransition(f"RESERVED -> {self.status} is not an allowed transition")
        changed = type(self).objects.cas_status(
            pk=self.pk, from_status=self.Status.RESERVED, to_status=self.status
        )
        if changed != 1:
            raise InvalidStatusTransition(
                f"CreditTransaction {self.pk} is not RESERVED; status unchanged"
            )

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise AppendOnlyViolation("CreditTransaction rows are append-only and cannot be deleted.")
