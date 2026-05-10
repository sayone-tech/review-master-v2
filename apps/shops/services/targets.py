from __future__ import annotations

import datetime

from django.db import IntegrityError

from apps.accounts.models import User
from apps.shops.models import ReviewTarget


def _anchor_month(d: datetime.date) -> datetime.date:
    return d.replace(day=1)


def _anchor_week(d: datetime.date) -> datetime.date:
    return d - datetime.timedelta(days=d.weekday())  # Monday (weekday() == 0 for Monday)


def _current_period_start(period_type: str) -> datetime.date:
    today = datetime.date.today()
    if period_type == ReviewTarget.PeriodType.WEEK:
        return _anchor_week(today)
    return _anchor_month(today)


def create_target(
    *,
    shop_id: int,
    org_id: int,
    period_type: str,
    period_start: datetime.date,
    target_count: int,
    created_by: User,
) -> ReviewTarget:
    if target_count < 1:
        raise ValueError("Target must be at least 1 review.")

    # Verify the shop belongs to this org (raises DoesNotExist if not)
    from apps.shops.models import Shop

    if not Shop.objects.filter(pk=shop_id, organisation_id=org_id).exists():
        raise ReviewTarget.DoesNotExist

    # Normalise period_start to canonical anchor
    if period_type == ReviewTarget.PeriodType.WEEK:
        period_start = _anchor_week(period_start)
    else:
        period_start = _anchor_month(period_start)

    # Reject past periods
    current_start = _current_period_start(period_type)
    if period_start < current_start:
        raise ValueError("Cannot set targets for past periods.")

    try:
        return ReviewTarget.objects.create(
            shop_id=shop_id,
            organisation_id=org_id,
            period_type=period_type,
            period_start=period_start,
            target_count=target_count,
            created_by=created_by,
        )
    except IntegrityError:
        raise ValueError("A target for this period already exists.") from None


def update_target(*, target_id: int, org_id: int, target_count: int) -> ReviewTarget:
    if target_count < 1:
        raise ValueError("Target must be at least 1 review.")
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.target_count = target_count
    target.save(update_fields=["target_count", "updated_at"])
    return target


def delete_target(*, target_id: int, org_id: int) -> None:
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.delete()
