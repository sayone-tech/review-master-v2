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
            period_start=datetime.date(2026, 5, 1),
            target_count=200,
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert len(result) == 1
        row = result[0]
        assert row["id"] == t.pk
        assert row["period_type"] == "MONTH"
        assert row["period_start"] == datetime.date(2026, 5, 1)
        assert row["period_end"] == datetime.date(2026, 5, 31)
        assert row["target_count"] == 200
        assert row["received_count"] == 0
        assert row["pct"] == 0
        assert isinstance(row["days_remaining"], int)
        assert row["days_remaining"] >= 0

    def test_received_count_matches_reviews_in_period(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=10,
        )
        # 3 reviews inside the period
        for _ in range(3):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(2026, 5, 15, 12, 0, tzinfo=datetime.UTC),
            )
        # 1 review outside the period (April)
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(2026, 4, 30, 12, 0, tzinfo=datetime.UTC),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 3
        assert result[0]["pct"] == 30

    def test_soft_deleted_reviews_excluded_from_count(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=10,
        )
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(2026, 5, 10, 12, 0, tzinfo=datetime.UTC),
        )
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(2026, 5, 10, 12, 0, tzinfo=datetime.UTC),
            deleted_at=datetime.datetime(2026, 5, 11, tzinfo=datetime.UTC),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 1

    def test_pct_capped_at_100(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=2,
        )
        for _ in range(5):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(2026, 5, 5, 12, 0, tzinfo=datetime.UTC),
            )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["pct"] == 100

    def test_org_isolation(self):
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        shop_a = ShopFactory(organisation=org_a)
        shop_b = ShopFactory(organisation=org_b)
        ReviewTargetFactory(shop=shop_b)  # organisation is derived via LazyAttribute
        result = list_targets_for_shop(shop_id=shop_a.pk, org_id=org_a.pk)
        assert result == []

    def test_org_isolation_cross_tenant_cannot_see_other_org_targets(self):
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        shop_b = ShopFactory(organisation=org_b)
        ReviewTargetFactory(shop=shop_b)  # org_b target
        # Attacker knows shop_b.pk but provides their own org_id
        result = list_targets_for_shop(shop_id=shop_b.pk, org_id=org_a.pk)
        assert result == []

    def test_query_count_is_fixed_regardless_of_target_count(self):
        shop = ShopFactory()
        # Create 5 targets with distinct period_start dates to satisfy the unique constraint
        for i in range(5):
            ReviewTargetFactory(
                shop=shop,
                period_type=ReviewTarget.PeriodType.MONTH,
                period_start=datetime.date(2025, i + 1, 1),
            )
        with CaptureQueriesContext(connection) as ctx:
            list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        # 2 queries: one for ReviewTarget rows, one for Review dates
        assert len(ctx.captured_queries) <= 3

    def test_ordering_current_future_past(self):
        shop = ShopFactory()
        today = datetime.date.today()
        # Past: last month
        past_start = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        # Current: this month
        current_start = today.replace(day=1)
        # Future: next month
        if today.month == 12:
            future_start = datetime.date(today.year + 1, 1, 1)
        else:
            future_start = datetime.date(today.year, today.month + 1, 1)

        ReviewTargetFactory(
            shop=shop, period_type=ReviewTarget.PeriodType.MONTH, period_start=past_start
        )
        ReviewTargetFactory(
            shop=shop, period_type=ReviewTarget.PeriodType.MONTH, period_start=future_start
        )
        ReviewTargetFactory(
            shop=shop, period_type=ReviewTarget.PeriodType.MONTH, period_start=current_start
        )

        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert len(result) == 3
        assert result[0]["period_start"] == current_start  # current first
        assert result[1]["period_start"] == future_start  # future second
        assert result[2]["period_start"] == past_start  # past last

    def test_week_period_end_is_sunday(self):
        shop = ShopFactory()
        # Monday 2026-05-11 -> Sunday 2026-05-17
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.WEEK,
            period_start=datetime.date(2026, 5, 11),
            target_count=50,
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["period_end"] == datetime.date(2026, 5, 17)
