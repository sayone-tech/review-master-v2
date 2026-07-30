from __future__ import annotations

from django.db import models
from django.db.models import Count, Q


class OrganisationQuerySet(models.QuerySet):  # type: ignore[type-arg]
    def active(self) -> OrganisationQuerySet:
        return self.filter(status="ACTIVE")

    def disabled(self) -> OrganisationQuerySet:
        return self.filter(status="DISABLED")

    def deleted(self) -> OrganisationQuerySet:
        return self.filter(status="DELETED")

    def not_deleted(self) -> OrganisationQuerySet:
        return self.exclude(status="DELETED")

    def annotate_store_counts(self) -> OrganisationQuerySet:
        """Annotate total and active shop counts from the reverse FK (shops).

        active_stores is the "in-use" count the UI shows as "N used of M
        allocated" and the value the store-allocation guard is measured against.
        distinct=True guards against row multiplication if the queryset joins
        other reverse relations."""
        return self.annotate(  # type: ignore[no-any-return]
            total_stores=Count("shops", distinct=True),
            active_stores=Count("shops", filter=Q(shops__is_active=True), distinct=True),
        )
