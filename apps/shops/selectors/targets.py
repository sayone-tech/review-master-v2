from __future__ import annotations

import datetime
from math import floor

from apps.reviews.models import Review
from apps.shops.models import ReviewTarget


def _current_period_bounds(period_type: str) -> tuple[datetime.date, datetime.date]:
    today = datetime.date.today()
    if period_type == ReviewTarget.PeriodType.WEEK:
        start = today - datetime.timedelta(days=today.weekday())  # Monday
        end = start + datetime.timedelta(days=6)  # Sunday
        return start, end
    # MONTH
    start = today.replace(day=1)
    if today.month == 12:
        end = datetime.date(today.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        end = datetime.date(today.year, today.month + 1, 1) - datetime.timedelta(days=1)
    return start, end


def _period_label(period_type: str, start: datetime.date, end: datetime.date) -> str:
    if period_type == ReviewTarget.PeriodType.WEEK:
        if start.month == end.month:
            return f"Week of {start.strftime('%b')} {start.day}-{end.day}"
        return f"Week of {start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}"
    return start.strftime("%B %Y")


def list_targets_for_shop(*, shop_id: int, org_id: int) -> list[dict[str, object]]:
    targets = list(ReviewTarget.objects.filter(shop_id=shop_id, organisation_id=org_id))
    if not targets:
        return []

    today = datetime.date.today()

    # Compute period bounds once per period_type (max 2)
    bounds: dict[str, tuple[datetime.date, datetime.date]] = {
        t.period_type: _current_period_bounds(t.period_type) for t in targets
    }

    # Single review query covering the union of all period ranges
    min_start = min(b[0] for b in bounds.values())
    max_end = max(b[1] for b in bounds.values())

    raw_datetimes = list(
        Review.objects.filter(
            shop_id=shop_id,
            review_create_time__date__gte=min_start,
            review_create_time__date__lte=max_end,
            deleted_at__isnull=True,
        ).values_list("review_create_time", flat=True)
    )

    # Bucket each review date into the right period_type
    counts: dict[str, int] = dict.fromkeys(bounds, 0)
    for dt in raw_datetimes:
        d = dt.date() if hasattr(dt, "date") else dt
        for pt, (start, end) in bounds.items():
            if start <= d <= end:
                counts[pt] += 1

    results = []
    for t in targets:
        start, end = bounds[t.period_type]
        received = counts[t.period_type]
        pct = min(100, floor(received / t.target_count * 100)) if t.target_count > 0 else 0
        results.append(
            {
                "id": t.pk,
                "period_type": t.period_type,
                "target_count": t.target_count,
                "received_count": received,
                "pct": pct,
                "period_label": _period_label(t.period_type, start, end),
                "days_remaining": max(0, (end - today).days),
            }
        )

    return results
