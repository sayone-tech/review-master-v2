from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models
from encrypted_fields.fields import EncryptedTextField

from apps.common.models import TimeStampedModel


class Shop(TimeStampedModel):
    class ConnectionMethod(models.TextChoices):
        GOOGLE_OAUTH = "GOOGLE_OAUTH", "Google OAuth"
        MANUAL = "MANUAL", "Manual API Key"
        NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"

    class ConnectionStatus(models.TextChoices):
        CONNECTED = "CONNECTED", "Connected"
        EXPIRED = "EXPIRED", "Connection Expired"
        ERROR = "ERROR", "Connection Error"
        QUOTA_EXCEEDED = "QUOTA_EXCEEDED", "Quota Exceeded"
        NOT_CONNECTED = "NOT_CONNECTED", "Not Connected"

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
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    place_id = models.CharField(max_length=300, blank=True, db_index=True)
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
    # Encrypted at rest — never add db_index to encrypted fields (ciphertext is per-row unique)
    # null=True is required: EncryptedTextField returns None for empty string (no ciphertext stored)
    google_refresh_token = EncryptedTextField(null=True, blank=True, default="")
    api_key = EncryptedTextField(null=True, blank=True, default="")
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
