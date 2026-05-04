"""Phase 13 — Notification model.

The Notification model records in-app bell notifications. Each row is
recipient-specific (one Notification per recipient per event); fan-out to
multiple recipients is performed by apps.notifications.services.dispatch.

The composite index (recipient, is_read, created_at) covers both the
unread-count poll query (NOTF-04, 60-second interval) and the popover list
query (NOTF-01, last 10 unread newest-first) with a single index scan.
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    class NotificationType(models.TextChoices):
        NEW_REVIEW = "new_review", "New Review"
        NEW_ACTION_ITEM = "new_action_item", "New Action Item"
        ACTION_ITEM_ASSIGNED = "action_item_assigned", "Action Item Assigned"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=30, choices=NotificationType.choices, db_index=True
    )
    title = models.CharField(max_length=200)
    shop = models.ForeignKey(
        "shops.Shop",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    action_item = models.ForeignKey(
        "action_items.ActionItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    review = models.ForeignKey(
        "reviews.Review",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    target_url = models.CharField(max_length=500)

    class Meta:
        db_table = "notifications_notification"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["recipient", "is_read", "created_at"],
                name="notif_recipient_unread_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Notification({self.pk}, {self.notification_type}, recipient={self.recipient_id})"
