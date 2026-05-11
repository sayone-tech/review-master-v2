from __future__ import annotations

import datetime
from math import floor
from typing import TypedDict

from apps.reviews.models import Review
from apps.shops.models import ReviewTarget


class TargetProgress(TypedDict):
    id: int
    period_type: str
    target_count: int
    received_count: int
    pct: int
    period_label: str
    days_remaining: int


def _current_period_bounds(
    period_type: str, today: datetime.date
) -> tuple[datetime.date, datetime.date]:
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


def list_targets_for_shop(*, shop_id: int, org_id: int) -> list[TargetProgress]:
    targets = list(ReviewTarget.objects.filter(shop_id=shop_id, organisation_id=org_id))
    if not targets:
        return []

    today = datetime.date.today()

    # Compute period bounds once per period_type (max 2)
    bounds: dict[str, tuple[datetime.date, datetime.date]] = {
        t.period_type: _current_period_bounds(t.period_type, today) for t in targets
    }

    # Single review query covering the union of all period ranges
    min_start = min(b[0] for b in bounds.values())
    max_end = max(b[1] for b in bounds.values())

    raw_datetimes: list[datetime.datetime] = list(
        Review.objects.filter(
            shop_id=shop_id,
            review_create_time__gte=datetime.datetime.combine(min_start, datetime.time.min).replace(
                tzinfo=datetime.UTC
            ),
            review_create_time__lt=datetime.datetime.combine(
                max_end + datetime.timedelta(days=1), datetime.time.min
            ).replace(tzinfo=datetime.UTC),
            deleted_at__isnull=True,
        ).values_list("review_create_time", flat=True)
    )

    # Bucket each review date into the right period_type
    counts: dict[str, int] = dict.fromkeys(bounds, 0)
    for dt in raw_datetimes:
        d = dt.date()
        for pt, (start, end) in bounds.items():
            if start <= d <= end:
                counts[pt] += 1

    results: list[TargetProgress] = []
    for t in targets:
        start, end = bounds[t.period_type]
        received = counts[t.period_type]
        pct = min(100, floor(received / t.target_count * 100)) if t.target_count > 0 else 0
        results.append(
            TargetProgress(
                id=t.pk,
                period_type=t.period_type,
                target_count=t.target_count,
                received_count=received,
                pct=pct,
                period_label=_period_label(t.period_type, start, end),
                days_remaining=max(0, (end - today).days),
            )
        )

    return results
