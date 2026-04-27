import uuid

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
