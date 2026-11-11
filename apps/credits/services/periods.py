"""UTC period seam for credit balances.

All period maths is UTC. Never use ``date.today()`` or ``timezone.localtime()``
(server-local). ``utc_now`` is the single patch point for tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple


class Period(NamedTuple):
    year: int
    month: int


_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def current_period(now: datetime | None = None) -> Period:
    """Return the UTC (year, month) for ``now`` (default: ``utc_now()``).

    Naive datetimes are rejected; aware datetimes are converted to UTC first.
    """
    moment = utc_now() if now is None else now
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("current_period() requires a timezone-aware datetime")
    utc = moment.astimezone(UTC)
    return Period(utc.year, utc.month)


def next_period_start(period: Period) -> datetime:
    """First instant (aware, UTC) of the month after ``period``; December rolls to January."""
    return datetime(period.year + period.month // 12, period.month % 12 + 1, 1, tzinfo=UTC)


def period_label(period: Period) -> str:
    """Server-owned month label, e.g. ``"November 2026"``.

    Hard-coded English names, never locale formatting: the server locale must not change
    the label the credits card shows.
    """
    return f"{_MONTH_NAMES[period.month - 1]} {period.year}"
