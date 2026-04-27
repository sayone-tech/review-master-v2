from __future__ import annotations

from typing import ClassVar

from django.db import models

from apps.common.models import TimeStampedModel


class Region(TimeStampedModel):
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="regions",
    )
    name = models.CharField(max_length=100)
    region_id = models.CharField(max_length=20, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "regions_region"
        ordering: ClassVar[list[str]] = ["created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "region_id"],
                name="region_org_id_unique",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "is_active"],
                name="region_org_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.region_id})"
