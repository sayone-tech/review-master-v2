from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.regions.models import Region


def list_regions(*, organisation_id: int, search: str = "") -> QuerySet[Region]:
    """Return regions for the organisation, optionally filtered by name or region_id."""
    qs = Region.objects.filter(organisation_id=organisation_id)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(region_id__icontains=search))
    return qs
