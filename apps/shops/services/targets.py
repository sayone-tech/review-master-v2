from __future__ import annotations

import datetime

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
        raise ReviewTarget.DoesNotExist

    target, _ = ReviewTarget.objects.update_or_create(
        shop_id=shop_id,
        organisation_id=org_id,
        period_type=period_type,
        defaults={"target_count": target_count, "created_by": created_by},
    )
    return target


def delete_target(*, target_id: int, org_id: int) -> None:
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.delete()


# ---------------------------------------------------------------------------
# Backward-compat shims — kept so views.py continues to import without error
# until Task 5 migrates the viewset to use set_target directly.
# ---------------------------------------------------------------------------


def create_target(
    *,
    shop_id: int,
    org_id: int,
    period_type: str,
    period_start: datetime.date,  # accepted but ignored — model no longer has this field
    target_count: int,
    created_by: User,
) -> ReviewTarget:
    return set_target(
        shop_id=shop_id,
        org_id=org_id,
        period_type=period_type,
        target_count=target_count,
        created_by=created_by,
    )


def update_target(*, target_id: int, org_id: int, target_count: int) -> ReviewTarget:
    if target_count < 1:
        raise ValueError("Target must be at least 1 review.")
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.target_count = target_count
    target.save(update_fields=["target_count", "updated_at"])
    return target
