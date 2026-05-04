"""Phase 13 plan 05 — Notification serializers.

Read-only serialiser for the bell popover and mark-read endpoints. The bell
list query is hot (polled every 60s by NotifBell — Plan 13-08), so the
serialiser stays lean: scalar fields + a single SerializerMethodField for
shop_name that reads from the prefetched select_related shop.
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationReadSerializer(serializers.ModelSerializer[Notification]):
    shop_name = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields: ClassVar[list[str]] = [
            "id",
            "notification_type",
            "title",
            "target_url",
            "is_read",
            "shop_id",
            "shop_name",
            "action_item_id",
            "review_id",
            "created_at",
        ]
        read_only_fields = fields

    def get_shop_name(self, obj: Notification) -> str | None:
        if obj.shop_id is None:
            return None
        # shop is select_related on the queryset — no extra query.
        return obj.shop.name if obj.shop else None
