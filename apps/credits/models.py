"""AI reply credits: per-shop monthly balance + append-only ledger (v0.9, Phase 29).

Other apps are referenced only through string FKs so ``credits`` stays a leaf
bounded context (no model imports from shops / reviews / organisations / openai).
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class ShopCreditBalance(models.Model):
    """One row per shop per UTC month, created lazily by ``ensure_balance``.

    Invariants are DB-enforced (CheckConstraints) so SQLite and PostgreSQL agree.
    NOTE: ``updated_at`` uses ``auto_now``, which fires only on ``save()``. Any future
    ``QuerySet.update()`` on balances MUST set ``updated_at`` explicitly.
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
