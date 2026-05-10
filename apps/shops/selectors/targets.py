from __future__ import annotations

import datetime
from math import floor
from typing import cast

from apps.reviews.models import Review
from apps.shops.models import ReviewTarget


def _period_end(period_type: str, period_start: datetime.date) -> datetime.date:
    if period_type == ReviewTarget.PeriodType.WEEK:
        return period_start + datetime.timedelta(days=6)  # Sunday
    # MONTH: last day of month
    if period_start.month == 12:
        return datetime.date(period_start.year + 1, 1, 1) - datetime.timedelta(days=1)
    return datetime.date(period_start.year, period_start.month + 1, 1) - datetime.timedelta(days=1)


def list_targets_for_shop(*, shop_id: int, org_id: int) -> list[dict[str, object]]:
    """Return targets with live progress. Ordered: current first, future next, past last."""
    targets = list(ReviewTarget.objects.filter(shop_id=shop_id, organisation_id=org_id))
    if not targets:
        return []

    today = datetime.date.today()

    received_map: dict[int, int] = {}
    for t in targets:
        period_start = t.period_start
        period_end = _period_end(t.period_type, period_start)
        count = Review.objects.filter(
            shop_id=shop_id,
            review_create_time__date__gte=period_start,
            review_create_time__date__lte=period_end,
            deleted_at__isnull=True,
        ).count()
        received_map[t.pk] = count

    results = []
    for t in targets:
        period_end = _period_end(t.period_type, t.period_start)
        received = received_map[t.pk]
        pct = min(100, floor(received / t.target_count * 100)) if t.target_count > 0 else 0
        days_remaining = max(0, (period_end - today).days)
        results.append(
            {
                "id": t.pk,
                "period_type": t.period_type,
                "period_start": t.period_start,
                "period_end": period_end,
                "target_count": t.target_count,
                "received_count": received,
                "pct": pct,
                "days_remaining": days_remaining,
            }
        )

    # Sort: current periods first, future next, past last
    def _sort_key(row: dict[str, object]) -> tuple[bool, bool, datetime.date]:
        period_end = cast(datetime.date, row["period_end"])
        period_start = cast(datetime.date, row["period_start"])
        is_past = period_end < today
        is_future = period_start > today
        return (is_past, is_future, period_start)

    results.sort(key=_sort_key)
    return results
