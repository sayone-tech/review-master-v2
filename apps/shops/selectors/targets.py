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


class TargetHistoryEntry(TypedDict):
    period_label: str
    period_start: str  # ISO date
    period_end: str  # ISO date
    target_count: int
    received_count: int
    pct: int


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


def _past_period_bounds(
    period_type: str, today: datetime.date, n: int
) -> list[tuple[datetime.date, datetime.date]]:
    """Return the last n completed periods, most-recent first."""
    periods = []
    if period_type == ReviewTarget.PeriodType.WEEK:
        current_start = today - datetime.timedelta(days=today.weekday())
        for i in range(1, n + 1):
            start = current_start - datetime.timedelta(weeks=i)
            end = start + datetime.timedelta(days=6)
            periods.append((start, end))
    else:  # MONTH
        ref = today.replace(day=1)
        for _ in range(n):
            if ref.month == 1:
                ref = datetime.date(ref.year - 1, 12, 1)
            else:
                ref = ref.replace(month=ref.month - 1)
            last_day = (
                datetime.date(ref.year, ref.month + 1, 1) - datetime.timedelta(days=1)
                if ref.month < 12
                else datetime.date(ref.year + 1, 1, 1) - datetime.timedelta(days=1)
            )
            periods.append((ref, last_day))
    return periods


def list_target_history(
    *, shop_id: int, org_id: int, period_type: str, n: int = 6
) -> list[TargetHistoryEntry]:
    try:
        target = ReviewTarget.objects.get(
            shop_id=shop_id, organisation_id=org_id, period_type=period_type
        )
    except ReviewTarget.DoesNotExist:
        return []

    today = datetime.date.today()
    past_periods = _past_period_bounds(period_type, today, n)
    if not past_periods:
        return []

    min_start = past_periods[-1][0]
    max_end = past_periods[0][1]

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

    results: list[TargetHistoryEntry] = []
    for start, end in past_periods:
        count = sum(1 for dt in raw_datetimes if start <= dt.date() <= end)
        pct = min(100, floor(count / target.target_count * 100)) if target.target_count > 0 else 0
        results.append(
            TargetHistoryEntry(
                period_label=_period_label(period_type, start, end),
                period_start=start.isoformat(),
                period_end=end.isoformat(),
                target_count=target.target_count,
                received_count=count,
                pct=pct,
            )
        )
    return results
