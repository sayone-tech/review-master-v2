"""Phase 21 plan 01 — Common app serializers (AuditLog read).

D-10: AuditLogReadSerializer omits before_data (sensitive / not displayed).
D-11: Includes actor_name (User.full_name) so the UI doesn't need a second
       lookup per row.
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework import serializers

from apps.common.models import AuditLog


class AuditLogReadSerializer(serializers.ModelSerializer[AuditLog]):
    actor_id = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields: ClassVar[list[str]] = [
            "id",
            "created_at",
            "entity_type",
            "entity_id",
            "action",
            "actor_id",
            "actor_name",
            "after_data",
        ]

    def get_actor_id(self, obj: AuditLog) -> int | None:
        return obj.actor_id

    def get_actor_name(self, obj: AuditLog) -> str | None:
        actor = obj.actor
        if actor is None:
            return None
        full_name = getattr(actor, "full_name", "") or ""
        return str(full_name) if full_name else None
