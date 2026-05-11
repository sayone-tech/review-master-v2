from __future__ import annotations

from apps.accounts.models import User
from apps.shops.models import ReviewTarget


def set_target(
    *,
    shop_id: int,
    org_id: int,
    period_type: str,
    target_count: int,
    created_by: User,
) -> ReviewTarget:
    if target_count < 1:
        raise ValueError("Target must be at least 1 review.")

    from apps.shops.models import Shop

    if not Shop.objects.filter(pk=shop_id, organisation_id=org_id).exists():
        raise ReviewTarget.DoesNotExist(
            f"Shop {shop_id} does not exist or does not belong to org {org_id}."
        )

    target, _ = ReviewTarget.objects.update_or_create(
        shop_id=shop_id,
        period_type=period_type,
        defaults={
            "organisation_id": org_id,
            "target_count": target_count,
            "created_by": created_by,
        },
    )
    return target


def delete_target(*, target_id: int, org_id: int) -> None:
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.delete()
