from __future__ import annotations

from django.db.models import QuerySet

from apps.regions.models import Region


def list_regions(*, organisation_id: int) -> QuerySet[Region]:
    """Return all regions for the organisation, ordered by created_at (model default)."""
    return Region.objects.filter(organisation_id=organisation_id)
