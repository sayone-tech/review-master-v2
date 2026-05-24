from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models
from encrypted_fields.fields import EncryptedTextField

from apps.common.models import TimeStampedModel


class Shop(TimeStampedModel):
    class ConnectionMethod(models.TextChoices):
        GOOGLE_OAUTH = "GOOGLE_OAUTH", "Google OAuth"
        NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"

    class ConnectionStatus(models.TextChoices):
        CONNECTED = "CONNECTED", "Connected"
        EXPIRED = "EXPIRED", "Connection Expired"
        ERROR = "ERROR", "Connection Error"
        QUOTA_EXCEEDED = "QUOTA_EXCEEDED", "Quota Exceeded"
        NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"

    class SyncDepth(models.TextChoices):
        ONE_YEAR = "ONE_YEAR", "Last 1 year"
        TWO_YEARS = "TWO_YEARS", "Last 2 years"
        ALL_TIME = "ALL_TIME", "All time"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="shops",
    )
    region = models.ForeignKey(
        "regions.Region",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shops",
    )
    name = models.CharField(max_length=200, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    street_address = models.CharField(max_length=300, blank=True)
    place_id = models.CharField(max_length=300, blank=True, db_index=True)
    google_account_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="GBP API resource path, e.g. accounts/123",
    )
    google_location_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="GBP API resource path, e.g. accounts/123/locations/456",
    )
    connection_method = models.CharField(
        max_length=15,
        choices=ConnectionMethod.choices,
        default=ConnectionMethod.NOT_CONNECTED,
        db_index=True,
    )
    connection_status = models.CharField(
        max_length=15,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.NOT_CONNECTED,
        db_index=True,
    )
    sync_depth = models.CharField(
        max_length=10,
        choices=SyncDepth.choices,
        default=SyncDepth.TWO_YEARS,
    )
    # Encrypted at rest — never add db_index to encrypted fields (ciphertext is per-row unique)
    # null=True is required: EncryptedTextField returns None for empty string (no ciphertext stored)
    google_refresh_token = EncryptedTextField(null=True, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "shops_shop"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "is_active", "connection_status"],
                name="shop_org_active_conn_idx",
            ),
        ]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            # Prevent the same Google Place being added twice within one org.
            # Condition excludes blank place_id (NOT_CONNECTED shops have place_id="").
            models.UniqueConstraint(
                fields=["organisation", "place_id"],
                condition=models.Q(place_id__gt=""),
                name="shop_unique_place_id_per_org",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ShopAuditLog(models.Model):
    class Action(models.TextChoices):
        API_KEY_REVEALED = "shop.api_key.revealed", "API Key Revealed"
        API_KEY_ROTATED = "shop.api_key.rotated", "API Key Rotated"

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="shop_audit_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "shops_shopauditlog"
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.shop_id}:{self.action}"


class ReviewTarget(TimeStampedModel):
    class PeriodType(models.TextChoices):
        WEEK = "WEEK", "Weekly"
        MONTH = "MONTH", "Monthly"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="review_targets",
    )
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="review_targets",
    )
    period_type = models.CharField(
        max_length=5,
        choices=PeriodType.choices,
        db_index=True,
    )
    target_count = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_targets",
    )

    class Meta:
        db_table = "shops_reviewtarget"
        ordering: ClassVar[list[str]] = ["period_type"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["shop", "period_type"],
                name="target_unique_per_shop_period_type",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "shop", "period_type"],
                name="tgt_org_shop_period_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"ReviewTarget({self.shop_id} {self.period_type})"
