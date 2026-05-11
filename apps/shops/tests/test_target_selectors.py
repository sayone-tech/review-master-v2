from __future__ import annotations

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.models import ReviewTarget
from apps.shops.selectors.targets import list_targets_for_shop
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _today() -> datetime.date:
    return datetime.date.today()


@pytest.mark.django_db
class TestListTargetsForShop:
    def test_returns_empty_list_when_no_targets(self):
        shop = ShopFactory()
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result == []

    def test_returns_target_with_computed_fields(self):
        shop = ShopFactory()
        t = ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            target_count=200,
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert len(result) == 1
        row = result[0]
        assert row["id"] == t.pk
        assert row["period_type"] == "MONTH"
        assert row["target_count"] == 200
        assert row["received_count"] == 0
        assert row["pct"] == 0
        assert isinstance(row["days_remaining"], int)
        assert row["days_remaining"] >= 0
        assert isinstance(row["period_label"], str)
        assert len(row["period_label"]) > 0

    def test_received_count_counts_reviews_in_current_month(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            target_count=10,
        )
        today = _today()
        # 3 reviews inside the current month
        for _ in range(3):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(
                    today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
                ),
            )
        # 1 review in the previous month — should be excluded
        prev_month = today.replace(day=1) - datetime.timedelta(days=1)
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                prev_month.year, prev_month.month, prev_month.day, 12, 0, tzinfo=datetime.UTC
            ),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 3
        assert result[0]["pct"] == 30

    def test_received_count_counts_reviews_in_current_week(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.WEEK,
            target_count=10,
        )
        today = _today()
        week_start = today - datetime.timedelta(days=today.weekday())
        # 2 reviews inside the current week
        for _ in range(2):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(
                    week_start.year,
                    week_start.month,
                    week_start.day,
                    12,
                    0,
                    tzinfo=datetime.UTC,
                ),
            )
        # 1 review 7 days before Monday — previous week, excluded
        prev_week_day = week_start - datetime.timedelta(days=1)
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                prev_week_day.year,
                prev_week_day.month,
                prev_week_day.day,
                12,
                0,
                tzinfo=datetime.UTC,
            ),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 2

    def test_soft_deleted_reviews_excluded(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=10)
        today = _today()
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
            ),
        )
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
            ),
            deleted_at=_now_utc(),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 1

    def test_pct_capped_at_100(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=2)
        today = _today()
        for _ in range(5):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(
                    today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
                ),
            )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["pct"] == 100

    def test_month_period_label_format(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=10)
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        # e.g. "May 2026"
        import re

        assert re.match(r"^[A-Z][a-z]+ \d{4}$", result[0]["period_label"])

    def test_week_period_label_contains_week_of(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.WEEK, target_count=5)
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert "Week of" in result[0]["period_label"]

    def test_org_isolation(self):
        org_a = OrganisationFactory()
        shop_a = ShopFactory(organisation=org_a)
        org_b = OrganisationFactory()
        shop_b = ShopFactory(organisation=org_b)
        ReviewTargetFactory(shop=shop_b)
        result = list_targets_for_shop(shop_id=shop_a.pk, org_id=org_a.pk)
        assert result == []

    def test_cross_tenant_cannot_see_other_org_targets(self):
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        shop_b = ShopFactory(organisation=org_b)
        ReviewTargetFactory(shop=shop_b)
        result = list_targets_for_shop(shop_id=shop_b.pk, org_id=org_a.pk)
        assert result == []

    def test_query_count_fixed_for_two_targets(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.WEEK, target_count=10)
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=40)
        with CaptureQueriesContext(connection) as ctx:
            list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        # 1 query for targets + 1 for reviews = 2
        assert len(ctx.captured_queries) <= 3
