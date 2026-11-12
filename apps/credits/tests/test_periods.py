from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from apps.credits.services import periods
from apps.credits.services.periods import Period, current_period


def test_resolves_november_when_last_second_of_month_utc():
    assert current_period(datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC)) == Period(2026, 11)


def test_resolves_december_when_first_instant_of_month_utc():
    assert current_period(datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)) == Period(2026, 12)


def test_resolves_in_utc_when_aware_non_utc_datetime():
    ist = timezone(timedelta(hours=5, minutes=30))
    assert current_period(datetime(2026, 12, 1, 3, 0, 0, tzinfo=ist)) == Period(2026, 11)


def test_raises_when_datetime_is_naive():
    with pytest.raises(ValueError, match="timezone-aware"):
        current_period(datetime(2026, 11, 30, 12, 0, 0))


def test_uses_patched_clock_when_no_argument_given():
    with patch(
        "apps.credits.services.periods.utc_now",
        return_value=datetime(2031, 2, 3, tzinfo=UTC),
    ):
        assert current_period() == Period(2031, 2)


def test_next_period_start_is_first_of_following_month_when_mid_year():
    result = periods.next_period_start(Period(2026, 11))

    assert result == datetime(2026, 12, 1, tzinfo=UTC)
    assert result.utcoffset() == timedelta(0)


def test_next_period_start_rolls_to_january_when_december():
    assert periods.next_period_start(Period(2026, 12)) == datetime(2027, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("period", "label"),
    [
        (Period(2026, 11), "November 2026"),
        (Period(2026, 9), "September 2026"),
        (Period(2027, 1), "January 2027"),
        (Period(2026, 12), "December 2026"),
    ],
)
def test_period_label_is_english_month_name_and_year(period, label):
    assert periods.period_label(period) == label
