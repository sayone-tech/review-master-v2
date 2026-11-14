"""Tests for the /kpis/ previous-period, trend and oldest-wait additions."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboard.filters import DashboardFilterParams
from apps.dashboard.selectors.aggregations import dashboard_kpis
from apps.dashboard.tests.conftest import make_review
from apps.regions.tests.factories import RegionFactory
from apps.reviews.models import Review
from apps.shops.tests.factories import ShopFactory

SUCCESS = Review.EnrichmentStatus.SUCCESS


def _p(shop_ids, date_from, date_to, **kw):
    return DashboardFilterParams(
        region_id=kw.get("region_id"),
        shop_id=kw.get("shop_id"),
        date_from=date_from,
        date_to=date_to,
        accessible_shop_ids=tuple(shop_ids),
    )


def _today() -> date:
    return timezone.now().date()


@pytest.mark.django_db
@pytest.mark.parametrize("days", [7, 30, 90, 12])
def test_previous_window_is_same_length_immediately_before(org, accessible_shops, days):
    shop = accessible_shops[0]
    today = _today()
    d_from = today - timedelta(days=days)
    n = days + 1  # inclusive window length
    # current window: 2 reviews; previous window: 3 reviews (first and last day)
    make_review(shop=shop, star_rating=5, days_ago=0)
    make_review(shop=shop, star_rating=5, days_ago=days)
    make_review(shop=shop, star_rating=2, days_ago=days + 1)  # last day of previous
    make_review(shop=shop, star_rating=4, days_ago=days + n)  # first day of previous
    make_review(shop=shop, star_rating=1, days_ago=days + n + 1)  # outside both
    result = dashboard_kpis(
        org_id=org.id, params=_p([s.id for s in accessible_shops], d_from, today)
    )
    assert result["total_reviews"] == 2
    assert result["previous"]["total_reviews"] == 2
    assert result["previous"]["avg_rating"] == 3.0


@pytest.mark.django_db
def test_previous_is_null_for_all_time(org, accessible_shops):
    make_review(shop=accessible_shops[0])
    result = dashboard_kpis(org_id=org.id, params=_p([s.id for s in accessible_shops], None, None))
    assert result["previous"] is None


@pytest.mark.django_db
def test_previous_fields_use_same_formulas(org, accessible_shops):
    shop = accessible_shops[0]
    today = _today()
    # window = 10 days inclusive; previous = today-20 .. today-11
    make_review(shop=shop, sentiment="negative", enrichment_status=SUCCESS, days_ago=15)
    make_review(shop=shop, sentiment="positive", enrichment_status=SUCCESS, days_ago=15)
    make_review(shop=shop, enrichment_status=Review.EnrichmentStatus.PENDING, days_ago=15)
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=9), today),
    )
    assert result["previous"] == {
        "total_reviews": 3,
        "avg_rating": 5.0,
        "negative_pct": 50.0,
        "awaiting_reply": 3,
    }


@pytest.mark.django_db
def test_trend_buckets_cover_30_day_range_exactly(org, accessible_shops):
    shop = accessible_shops[0]
    today = _today()
    d_from = today - timedelta(days=29)  # N = 30 -> buckets of 5 days
    # one review at first and last day of each bucket (offsets 0,4 / 5,9 / ...)
    for i in range(6):
        for off in (i * 5, i * 5 + 4):
            make_review(shop=shop, star_rating=i + 1 if i < 5 else 5, days_ago=29 - off)
    # bucket 2 gets an extra review; bucket 3 gets none of its own
    make_review(shop=shop, star_rating=1, days_ago=29 - 10)
    result = dashboard_kpis(
        org_id=org.id, params=_p([s.id for s in accessible_shops], d_from, today)
    )
    assert result["trend"]["total_reviews"] == [2, 2, 3, 2, 2, 2]
    assert result["trend"]["avg_rating"][0] == 1.0
    assert result["trend"]["avg_rating"][2] == round((3 + 3 + 1) / 3, 1)
    assert sum(result["trend"]["total_reviews"]) == result["total_reviews"]


@pytest.mark.django_db
def test_trend_empty_bucket_has_zero_and_nulls(org, accessible_shops):
    today = _today()
    make_review(
        shop=accessible_shops[0], days_ago=0, sentiment="negative", enrichment_status=SUCCESS
    )
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=29), today),
    )
    t = result["trend"]
    assert t["total_reviews"] == [0, 0, 0, 0, 0, 1]
    assert t["avg_rating"][:5] == [None] * 5
    assert t["negative_pct"][:5] == [None] * 5
    assert t["negative_pct"][5] == 100.0


@pytest.mark.django_db
def test_trend_negative_pct_null_without_enriched(org, accessible_shops):
    today = _today()
    make_review(shop=accessible_shops[0], days_ago=0)  # pending, not enriched
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=29), today),
    )
    assert result["trend"]["total_reviews"][5] == 1
    assert result["trend"]["negative_pct"][5] is None


@pytest.mark.django_db
def test_trend_short_range_has_empty_buckets(org, accessible_shops):
    today = _today()
    make_review(shop=accessible_shops[0], days_ago=0)
    make_review(shop=accessible_shops[0], days_ago=2)
    # N = 3 days -> floor(i*3/6): offsets [0,0),[0,1),[1,1),[1,2),[2,2),[2,3)
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=2), today),
    )
    assert result["trend"]["total_reviews"] == [0, 1, 0, 0, 0, 1]


@pytest.mark.django_db
def test_trend_all_time_is_last_six_calendar_months(org, accessible_shops):
    shop = accessible_shops[0]
    today = _today()
    first_this = today.replace(day=1)
    make_review(shop=shop, days_ago=0)
    make_review(shop=shop, days_ago=(today - (first_this - timedelta(days=1))).days)  # prev month
    # 5 months back, still in window; and 7 months back, excluded
    in_window = (today - (first_this - timedelta(days=130))).days
    make_review(shop=shop, days_ago=in_window)
    make_review(shop=shop, days_ago=(today - (first_this - timedelta(days=220))).days)
    result = dashboard_kpis(org_id=org.id, params=_p([s.id for s in accessible_shops], None, None))
    t = result["trend"]["total_reviews"]
    assert len(t) == 6
    assert t[5] == 1
    assert t[4] == 1
    assert sum(t) == 3  # the 7-month-old review is outside the 6 months
    assert result["total_reviews"] == 4  # but still counted all-time


@pytest.mark.django_db
def test_oldest_awaiting_days(org, accessible_shops):
    shop = accessible_shops[0]
    today = _today()
    old = make_review(shop=shop, days_ago=20)
    make_review(shop=shop, days_ago=3)
    replied = make_review(shop=shop, days_ago=25)
    Review.objects.filter(pk=replied.pk).update(reply_comment="thanks")
    assert old.reply_comment == ""
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=30), today),
    )
    assert result["oldest_awaiting_days"] == 20


@pytest.mark.django_db
def test_oldest_awaiting_days_null_when_none_awaiting(org, accessible_shops):
    today = _today()
    r = make_review(shop=accessible_shops[0], days_ago=2)
    Review.objects.filter(pk=r.pk).update(reply_comment="done")
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=30), today),
    )
    assert result["oldest_awaiting_days"] is None


@pytest.mark.django_db
def test_oldest_awaiting_respects_store_region_and_staff_scope(org, region):
    today = _today()
    in_region = ShopFactory(organisation=org, region=region)
    other_region = RegionFactory(organisation=org)
    elsewhere = ShopFactory(organisation=org, region=other_region)
    make_review(shop=in_region, days_ago=5)
    make_review(shop=elsewhere, days_ago=25)
    ids = [in_region.id, elsewhere.id]
    d_from = today - timedelta(days=30)
    assert (
        dashboard_kpis(org_id=org.id, params=_p(ids, d_from, today))["oldest_awaiting_days"] == 25
    )
    by_region = _p(ids, d_from, today, region_id=region.id)
    assert dashboard_kpis(org_id=org.id, params=by_region)["oldest_awaiting_days"] == 5
    by_store = _p(ids, d_from, today, shop_id=in_region.id)
    assert dashboard_kpis(org_id=org.id, params=by_store)["oldest_awaiting_days"] == 5
    staff = _p([in_region.id], d_from, today)  # Staff scope limited to one shop
    assert dashboard_kpis(org_id=org.id, params=staff)["oldest_awaiting_days"] == 5


@pytest.mark.django_db
def test_previous_and_trend_respect_region_scope(org, region):
    today = _today()
    in_region = ShopFactory(organisation=org, region=region)
    elsewhere = ShopFactory(organisation=org, region=RegionFactory(organisation=org))
    make_review(shop=in_region, days_ago=40)
    make_review(shop=elsewhere, days_ago=40)
    result = dashboard_kpis(
        org_id=org.id,
        params=_p(
            [in_region.id, elsewhere.id], today - timedelta(days=29), today, region_id=region.id
        ),
    )
    assert result["previous"]["total_reviews"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize("all_time", [False, True])
def test_kpis_query_count_is_fixed(org, accessible_shops, all_time):
    shop = accessible_shops[0]
    for d in range(0, 30, 3):
        make_review(shop=shop, days_ago=d, sentiment="negative", enrichment_status=SUCCESS)
    today = _today()
    params = _p(
        [s.id for s in accessible_shops],
        None if all_time else today - timedelta(days=29),
        None if all_time else today,
    )
    with CaptureQueriesContext(connection) as ctx:
        dashboard_kpis(org_id=org.id, params=params)
    # current+previous aggregate, 6-bucket trend, oldest awaiting
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_previous_avg_and_negative_pct_null_when_previous_window_empty(org, accessible_shops):
    today = _today()
    make_review(
        shop=accessible_shops[0], days_ago=0, sentiment="negative", enrichment_status=SUCCESS
    )
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=9), today),
    )
    assert result["previous"] == {
        "total_reviews": 0,
        "avg_rating": None,
        "negative_pct": None,
        "awaiting_reply": 0,
    }


@pytest.mark.django_db
def test_previous_negative_pct_null_when_previous_has_no_enriched(org, accessible_shops):
    today = _today()
    make_review(shop=accessible_shops[0], star_rating=4, days_ago=15)  # pending
    result = dashboard_kpis(
        org_id=org.id,
        params=_p([s.id for s in accessible_shops], today - timedelta(days=9), today),
    )
    assert result["previous"]["total_reviews"] == 1
    assert result["previous"]["avg_rating"] == 4.0
    assert result["previous"]["negative_pct"] is None


def test_trend_windows_all_time_across_year_boundary(monkeypatch):
    import datetime as dt

    from apps.dashboard.selectors import aggregations as agg

    monkeypatch.setattr(agg.timezone, "now", lambda: dt.datetime(2027, 2, 10, 12, 0, tzinfo=dt.UTC))
    params = _p([1], None, None)
    windows = agg._trend_windows(params)
    assert [w[0] for w in windows] == [
        date(2026, 9, 1),
        date(2026, 10, 1),
        date(2026, 11, 1),
        date(2026, 12, 1),
        date(2027, 1, 1),
        date(2027, 2, 1),
    ]
    assert windows[3][1] == date(2026, 12, 31)
    assert windows[4][1] == date(2027, 1, 31)
    assert windows[5][1] == date(2027, 2, 28)
