from typing import ClassVar

from django.db import models

from apps.common.models import TimeStampedModel


class InsightSnapshot(TimeStampedModel):
    """One computed insights payload per organisation per day (read-only to tenants)."""

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="insight_snapshots",
    )
    computed_for = models.DateField()
    window_from = models.DateField()
    window_to = models.DateField()
    payload = models.JSONField(default=dict)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "computed_for"], name="insight_snapshot_org_day"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "-computed_for"], name="insight_snap_org_latest_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"InsightSnapshot({self.organisation_id}, {self.computed_for})"
