from __future__ import annotations

from typing import ClassVar

from django.db import models

from apps.common.models import TimeStampedModel
from apps.organisations.managers import OrganisationQuerySet


class Organisation(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISABLED = "DISABLED", "Disabled"
        DELETED = "DELETED", "Deleted"

    class OrgType(models.TextChoices):
        RETAIL = "RETAIL", "Retail"
        RESTAURANT = "RESTAURANT", "Restaurant"
        PHARMACY = "PHARMACY", "Pharmacy"
        SUPERMARKET = "SUPERMARKET", "Supermarket"

    name = models.CharField(max_length=100, db_index=True)
    org_type = models.CharField(max_length=20, choices=OrgType.choices, db_index=True)
    email = models.EmailField(unique=True)
    address = models.TextField(max_length=500, blank=True)
    number_of_stores = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_organisations",
    )

    objects: OrganisationQuerySet = OrganisationQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        db_table = "organisations_organisation"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["status", "created_at"], name="org_status_created_idx"),
            models.Index(fields=["org_type", "status"], name="org_type_status_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def soft_delete(self) -> None:
        """Mark organisation as deleted without removing the row."""
        self.status = self.Status.DELETED
        self.save(update_fields=["status", "updated_at"])
