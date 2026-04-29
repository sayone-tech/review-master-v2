from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.organisations.models import Organisation
from apps.regions.models import Region
from apps.shops.models import Shop


def list_shops(
    *,
    organisation_id: int,
    search: str = "",
    status: str = "",
    region_id: int | None = None,
    active_only: bool = False,
) -> QuerySet[Shop]:
    qs = Shop.objects.filter(organisation_id=organisation_id).select_related("region")
    if active_only:
        qs = qs.filter(is_active=True)
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(street_address__icontains=search)
            | Q(city__icontains=search)
        )
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    if region_id is not None:
        qs = qs.filter(region_id=region_id)
    return qs


def get_has_regions(*, organisation_id: int) -> bool:
    return Region.objects.filter(organisation_id=organisation_id).exists()


def get_allocation_status(*, organisation: Organisation) -> dict[str, int | bool]:
    current = Shop.objects.filter(organisation=organisation).count()
    return {
        "current": current,
        "max": organisation.number_of_stores,
        "at_limit": current >= organisation.number_of_stores,
    }
