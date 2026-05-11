"""Phase 13 — Notification admin registration."""

from __future__ import annotations

from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = (
        "id",
        "recipient",
        "notification_type",
        "is_read",
        "created_at",
    )
    list_filter = ("notification_type", "is_read")
    search_fields = ("title", "recipient__email")
    raw_id_fields = (
        "organisation",
        "recipient",
        "shop",
        "action_item",
        "review",
    )
    readonly_fields = ("created_at", "updated_at")
