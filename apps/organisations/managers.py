from __future__ import annotations

from django.db import models
from django.db.models import IntegerField, Value


class OrganisationQuerySet(models.QuerySet):  # type: ignore[type-arg]
    def active(self) -> OrganisationQuerySet:
        return self.filter(status="ACTIVE")

    def disabled(self) -> OrganisationQuerySet:
        return self.filter(status="DISABLED")

    def deleted(self) -> OrganisationQuerySet:
        return self.filter(status="DELETED")

    def not_deleted(self) -> OrganisationQuerySet:
        return self.exclude(status="DELETED")

    # TODO(phase-2): Replace with real Count("stores") annotations once
    # apps.stores.Store is added with FK to Organisation (related_name='stores').
    def annotate_store_counts(self) -> OrganisationQuerySet:
        """Phase 1 stub: returns zero counts. Phase 2 replaces this with
        reverse-FK counts after apps.stores.Store is added with related_name='stores'."""
        return self.annotate(  # type: ignore[no-any-return]
            total_stores=Value(0, output_field=IntegerField()),
            active_stores=Value(0, output_field=IntegerField()),
        )
