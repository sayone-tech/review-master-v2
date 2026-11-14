"""UTC date windows for insights, and the one place their day boundaries are turned into SQL.

*now* = the 30 full UTC days ending yesterday; *before* = the 30 days before that.
``review_window_q`` builds the date predicate from the Reviews page's own ``from_date`` /
``to_date`` filters, so an insight counts exactly the reviews its ``from``/``to`` link shows.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db.models import Q

from apps.reviews.filters import ReviewFilterSet

WINDOW_DAYS = 30
HISTORY_WINDOWS = 6  # "the last 6 months" = six consecutive 30-day windows ending with *now*


@dataclass(frozen=True)
class Window:
    now_from: dt.date
    now_to: dt.date
    before_from: dt.date
    before_to: dt.date


def windows_for(today: dt.date) -> Window:
    return Window(
        now_from=today - dt.timedelta(days=WINDOW_DAYS),
        now_to=today - dt.timedelta(days=1),
        before_from=today - dt.timedelta(days=2 * WINDOW_DAYS),
        before_to=today - dt.timedelta(days=WINDOW_DAYS + 1),
    )


def six_windows(window: Window) -> list[tuple[dt.date, dt.date]]:
    """Six consecutive 30-day (from, to) windows, oldest first; the last one is *now*."""
    out = []
    for i in range(HISTORY_WINDOWS - 1, -1, -1):
        shift = dt.timedelta(days=WINDOW_DAYS * i)
        out.append((window.now_from - shift, window.now_to - shift))
    return out


def review_window_q(date_from: dt.date, date_to: dt.date, *, prefix: str = "") -> Q:
    """Reviews created in [date_from, date_to], bounded exactly like the Reviews page filter.

    ``prefix`` is the relation path to the review (e.g. ``"review__"`` from ReviewTag).
    """
    lo = ReviewFilterSet.base_filters["from_date"]
    hi = ReviewFilterSet.base_filters["to_date"]
    return Q(
        **{
            f"{prefix}{lo.field_name}__{lo.lookup_expr}": date_from,
            f"{prefix}{hi.field_name}__{hi.lookup_expr}": date_to,
        }
    )
