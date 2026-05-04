import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SequenceCounter(TimeStampedModel):
    """Fallback sequence counter using select_for_update().

    Insurance only — django-sequences 3.0 is the primary mechanism. This model
    is created so the fallback in apps/regions/services/sequences.py (Phase 7)
    can be activated without a migration if the smoke test fails.
    """

    name = models.CharField(max_length=100, unique=True)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "common_sequence_counter"

    def __str__(self) -> str:
        return f"SequenceCounter(name={self.name}, next={self.next_value})"


class AuditLog(TimeStampedModel):
    """Generic, cross-phase audit log.

    Phase 11 events: reply_posted, sync_triggered, sync_completed, sync_failed,
    review.fetched. Phase 12-13 reuse this model for action_item.* and
    enrichment.* events without new migrations.
    """

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="audit_logs",
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_log_entries",
    )
    entity_type = models.CharField(max_length=50, db_index=True)
    entity_id = models.CharField(max_length=200, db_index=True)
    action = models.CharField(max_length=100, db_index=True)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "common_audit_log"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "entity_type", "created_at"],
                name="audit_org_entity_date_idx",
            ),
            models.Index(
                fields=["entity_type", "entity_id"],
                name="audit_entity_lookup_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"AuditLog({self.entity_type}:{self.entity_id} {self.action})"
