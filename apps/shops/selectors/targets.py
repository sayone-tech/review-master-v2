from __future__ import annotations

import datetime
from math import floor
from typing import cast

from apps.reviews.models import Review
from apps.shops.models import ReviewTarget


def _period_end(period_type: str, period_start: datetime.date) -> datetime.date:
    if period_type == ReviewTarget.PeriodType.WEEK:
        return period_start + datetime.timedelta(days=6)  # Sunday
    if period_type == ReviewTarget.PeriodType.MONTH:
        if period_start.month == 12:
            return datetime.date(period_start.year + 1, 1, 1) - datetime.timedelta(days=1)
        return datetime.date(period_start.year, period_start.month + 1, 1) - datetime.timedelta(
            days=1
        )
    raise ValueError(f"Unknown period_type: {period_type!r}")


def list_targets_for_shop(*, shop_id: int, org_id: int) -> list[dict[str, object]]:
    """Return targets with live progress. Ordered: current first, future next, past last."""
    targets = list(ReviewTarget.objects.filter(shop_id=shop_id, organisation_id=org_id))
    if not targets:
        return []

    today = datetime.date.today()

    # Build period boundaries once per target
    boundaries: dict[int, datetime.date] = {
        t.pk: _period_end(t.period_type, t.period_start) for t in targets
    }

    # Single aggregation: query all reviews for this shop that fall within ANY of the
    # target periods — one DB round trip for reviews (2 total: targets + reviews).
    min_start = min(t.period_start for t in targets)
    max_end = max(boundaries[t.pk] for t in targets)

    reviews_qs = Review.objects.filter(
        shop_id=shop_id,
        review_create_time__date__gte=min_start,
        review_create_time__date__lte=max_end,
        deleted_at__isnull=True,
    ).values_list("review_create_time", flat=True)

    # Partition review dates into each period in Python (O(reviews * targets), negligible scale)
    review_dates = [dt.date() for dt in reviews_qs]

    received_map: dict[int, int] = {}
    for t in targets:
        period_end = boundaries[t.pk]
        received_map[t.pk] = sum(1 for d in review_dates if t.period_start <= d <= period_end)

    results = []
    for t in targets:
        period_end = boundaries[t.pk]
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

    def _sort_key(row: dict[str, object]) -> tuple[bool, bool, datetime.date]:
        period_end = cast(datetime.date, row["period_end"])
        period_start = cast(datetime.date, row["period_start"])
        is_past = period_end < today
        is_future = period_start > today
        return (is_past, is_future, period_start)

    results.sort(key=_sort_key)
    return results
