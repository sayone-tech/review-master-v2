"""UTC date windows for the Superadmin AI cost explorer (Phase 34).

Windows are start-inclusive and end-exclusive. ``resolve_cost_window`` is the
only place query-string range parameters are interpreted.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

ROLLING_RANGES: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}
MAX_CUSTOM_SPAN_DAYS = 365
DEFAULT_RANGE = "this_month"
# Open-ended ranges end at "now" rounded down to this bucket, so the query and the
# cache key share one end and a cached payload stays valid for the whole bucket.
END_BUCKET_MINUTES = 10


@dataclass(frozen=True)
class CostWindow:
    range_key: str
    start: datetime
    end: datetime

    def cache_hash(self) -> str:
        raw = f"{self.range_key}|{self.start.isoformat()}|{self.end.isoformat()}"
        return hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()


def _invalid(message: str) -> ValidationError:
    return ValidationError({"detail": message})


def _parse_day(value: str | None, name: str) -> date:
    if not value:
        raise _invalid(f"'{name}' is required for a custom range.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _invalid(f"'{name}' must be a date in YYYY-MM-DD format.") from None


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _bucket_end(moment: datetime) -> datetime:
    """``moment`` rounded down to the start of its ``END_BUCKET_MINUTES`` bucket."""
    minute = moment.minute - moment.minute % END_BUCKET_MINUTES
    return moment.replace(minute=minute, second=0, microsecond=0)


def resolve_cost_window(*, params: Mapping[str, str], now: datetime | None = None) -> CostWindow:
    current = (now or timezone.now()).astimezone(UTC)
    range_key = params.get("range") or DEFAULT_RANGE
    today = _midnight(current.date())

    if range_key == "this_month":
        return CostWindow(range_key, _midnight(current.date().replace(day=1)), _bucket_end(current))

    if range_key == "last_month":
        first_this = current.date().replace(day=1)
        last_month_end = first_this
        last_month_start = (first_this - timedelta(days=1)).replace(day=1)
        return CostWindow(range_key, _midnight(last_month_start), _midnight(last_month_end))

    if range_key in ROLLING_RANGES:
        start = today - timedelta(days=ROLLING_RANGES[range_key] - 1)
        return CostWindow(range_key, start, _bucket_end(current))

    if range_key == "custom":
        from_day = _parse_day(params.get("from"), "from")
        to_day = _parse_day(params.get("to"), "to")
        if from_day > to_day:
            raise _invalid("'from' must be on or before 'to'.")
        span_days = (to_day - from_day).days + 1
        if span_days > MAX_CUSTOM_SPAN_DAYS:
            raise _invalid(f"Custom range may span at most {MAX_CUSTOM_SPAN_DAYS} days.")
        start = _midnight(from_day)
        # A range that includes today ends at the current bucket (like the open-ended
        # ranges) so the cache key stays stable; a past range keeps its exclusive end.
        end = min(_midnight(to_day + timedelta(days=1)), _bucket_end(current))
        if start >= end:  # entirely in the future: empty window, not an error
            end = start
        return CostWindow(range_key, start, end)

    raise _invalid(f"Unknown range '{range_key}'.")
