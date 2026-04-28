from __future__ import annotations

from django.db import transaction

from apps.organisations.models import Organisation
from apps.regions.exceptions import RegionHasShopsError
from apps.regions.models import Region


@transaction.atomic
def create_region(*, organisation: Organisation, name: str, region_id: str) -> Region:
    return Region.objects.create(
        organisation=organisation,
        name=name,
        region_id=region_id,
    )


@transaction.atomic
def update_region(
    *,
    region: Region,
    name: str | None = None,
    region_id: str | None = None,
) -> Region:
    changed: list[str] = []
    if name is not None and region.name != name:
        region.name = name
        changed.append("name")
    if region_id is not None and region.region_id != region_id:
        region.region_id = region_id
        changed.append("region_id")
    if changed:
        changed.append("updated_at")
        region.save(update_fields=changed)
    return region


def delete_region(*, region: Region) -> None:
    if region.shops.exists():
        count = region.shops.count()
        raise RegionHasShopsError(shop_count=count)
    region.delete()
