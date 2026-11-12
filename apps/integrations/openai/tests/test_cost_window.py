"""Phase 34 Task 1 — UTC date-window parsing for the Superadmin AI cost explorer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.exceptions import ValidationError

from apps.integrations.openai.cost_window import CostWindow, resolve_cost_window

NOW = datetime(2026, 11, 12, 15, 30, tzinfo=UTC)


def test_default_is_this_month():
    w = resolve_cost_window(params={}, now=NOW)
    assert (w.range_key, w.start, w.end) == ("this_month", datetime(2026, 11, 1, tzinfo=UTC), NOW)


def test_last_month_is_full_previous_calendar_month():
    w = resolve_cost_window(params={"range": "last_month"}, now=NOW)
    assert (w.start, w.end) == (
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2026, 11, 1, tzinfo=UTC),
    )


def test_last_month_in_january_wraps_year():
    w = resolve_cost_window(params={"range": "last_month"}, now=datetime(2027, 1, 5, tzinfo=UTC))
    assert w.start == datetime(2026, 12, 1, tzinfo=UTC)


@pytest.mark.parametrize(("key", "days"), [("7d", 7), ("30d", 30), ("90d", 90)])
def test_rolling_ranges_anchor_to_utc_midnight(key, days):
    w = resolve_cost_window(params={"range": key}, now=NOW)
    assert w.start == datetime(2026, 11, 12, tzinfo=UTC) - timedelta(days=days - 1)
    assert w.end == NOW


def test_custom_range_is_inclusive_of_to_date():
    w = resolve_cost_window(
        params={"range": "custom", "from": "2026-10-01", "to": "2026-10-31"}, now=NOW
    )
    assert (w.start, w.end) == (
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2026, 11, 1, tzinfo=UTC),
    )


def test_midnight_on_first_belongs_to_this_month():  # Review Focus 2
    this_m = resolve_cost_window(params={}, now=NOW)
    last_m = resolve_cost_window(params={"range": "last_month"}, now=NOW)
    t = datetime(2026, 11, 1, tzinfo=UTC)
    assert this_m.start <= t < this_m.end
    assert not (last_m.start <= t < last_m.end)


@pytest.mark.parametrize(
    "params",
    [
        {"range": "custom", "from": "2026-10-31", "to": "2026-10-01"},  # from > to
        {"range": "custom", "from": "2025-01-01", "to": "2026-01-01"},  # 366 days
        {"range": "custom", "from": "2026-10-01"},  # missing to
        {"range": "custom", "from": "bad", "to": "2026-10-01"},
        {"range": "yesterday"},
    ],
)
def test_invalid_params_raise(params):
    with pytest.raises(ValidationError):
        resolve_cost_window(params=params, now=NOW)


def test_365_day_custom_range_is_allowed():
    resolve_cost_window(
        params={"range": "custom", "from": "2025-01-01", "to": "2025-12-31"}, now=NOW
    )


def test_cache_hash_is_stable_within_the_same_minute_for_rolling_ranges():
    a = resolve_cost_window(params={"range": "7d"}, now=NOW)
    b = resolve_cost_window(params={"range": "7d"}, now=NOW + timedelta(seconds=40))
    assert a.cache_hash() == b.cache_hash()
    assert isinstance(a, CostWindow)
