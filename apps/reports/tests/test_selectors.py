"""Tests for apps.reports.selectors.store_report."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboard.tests.conftest import make_review
from apps.organisations.tests.factories import OrganisationFactory
from apps.reports.selectors.store_report import ReportFilterParams, list_store_report
from apps.reviews.models import Review
from apps.shops.tests.factories import ShopFactory

SUCCESS = Review.EnrichmentStatus.SUCCESS


def _params(*, date_from=None, date_to=None, reply_status=None, sentiment=None):
    today = timezone.now().date()
    return ReportFilterParams(
        date_from=date_from or today - timedelta(days=30),
        date_to=date_to or today,
        reply_status=reply_status,
        sentiment=sentiment,
    )


@pytest.mark.django_db
def test_query_count():
    """list_store_report must execute at most 1 DB query."""
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)

    with CaptureQueriesContext(connection) as ctx:
        list_store_report(org_id=org.id, params=_params())

    assert len(ctx.captured_queries) <= 1, f"Expected ≤1 query, got {len(ctx.captured_queries)}"


@pytest.mark.django_db
def test_basic_counts():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    make_review(
        shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS, days_ago=5
    )
    make_review(
        shop=shop, star_rating=3, sentiment="neutral", enrichment_status=SUCCESS, days_ago=5
    )
    make_review(
        shop=shop, star_rating=1, sentiment="negative", enrichment_status=SUCCESS, days_ago=5
    )

    rows = list_store_report(org_id=org.id, params=_params())

    assert len(rows) == 1
    r = rows[0]
    assert r["shop_id"] == shop.id
    assert r["shop_name"] == shop.name
    assert r["total_reviews"] == 3
    assert round(r["avg_rating"], 1) == 3.0
    assert r["positive_count"] == 1
    assert r["neutral_count"] == 1
    assert r["negative_count"] == 1


@pytest.mark.django_db
def test_replied_counts():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    r2 = make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)
    r2.is_replied = True
    r2.save(update_fields=["is_replied"])

    rows = list_store_report(org_id=org.id, params=_params())

    assert rows[0]["replied_count"] == 1
    assert rows[0]["not_replied_count"] == 1


@pytest.mark.django_db
def test_reply_status_filter_replied():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    r1 = make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    r1.is_replied = True
    r1.save(update_fields=["is_replied"])
    make_review(shop=shop, star_rating=2, sentiment="negative", enrichment_status=SUCCESS)

    rows = list_store_report(org_id=org.id, params=_params(reply_status="replied"))

    assert len(rows) == 1
    assert rows[0]["total_reviews"] == 1
    assert rows[0]["replied_count"] == 1


@pytest.mark.django_db
def test_reply_status_filter_not_replied():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    r1 = make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    r1.is_replied = True
    r1.save(update_fields=["is_replied"])
    make_review(shop=shop, star_rating=2, sentiment="negative", enrichment_status=SUCCESS)

    rows = list_store_report(org_id=org.id, params=_params(reply_status="not_replied"))

    assert rows[0]["total_reviews"] == 1
    assert rows[0]["not_replied_count"] == 1


@pytest.mark.django_db
def test_sentiment_filter():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=1, sentiment="negative", enrichment_status=SUCCESS)

    rows = list_store_report(org_id=org.id, params=_params(sentiment="negative"))

    assert rows[0]["total_reviews"] == 1
    assert rows[0]["negative_count"] == 1
    assert rows[0]["positive_count"] == 0


@pytest.mark.django_db
def test_combined_filters():
    """reply_status and sentiment are AND-combined."""
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    r1 = make_review(shop=shop, star_rating=1, sentiment="negative", enrichment_status=SUCCESS)
    r1.is_replied = True
    r1.save(update_fields=["is_replied"])
    make_review(shop=shop, star_rating=1, sentiment="negative", enrichment_status=SUCCESS)
    r3 = make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    r3.is_replied = True
    r3.save(update_fields=["is_replied"])

    rows = list_store_report(
        org_id=org.id,
        params=_params(sentiment="negative", reply_status="replied"),
    )

    assert rows[0]["total_reviews"] == 1


@pytest.mark.django_db
def test_zero_match_store_excluded():
    """Stores with zero matching reviews must not appear in results."""
    org = OrganisationFactory()
    ShopFactory(organisation=org)

    rows = list_store_report(org_id=org.id, params=_params())

    assert rows == []


@pytest.mark.django_db
def test_other_org_excluded():
    org1 = OrganisationFactory()
    org2 = OrganisationFactory()
    shop1 = ShopFactory(organisation=org1)
    shop2 = ShopFactory(organisation=org2)
    make_review(shop=shop1, star_rating=5, enrichment_status=SUCCESS)
    make_review(shop=shop2, star_rating=5, enrichment_status=SUCCESS)

    rows = list_store_report(org_id=org1.id, params=_params())

    assert len(rows) == 1
    assert rows[0]["shop_id"] == shop1.id


@pytest.mark.django_db
def test_ordered_by_total_reviews_desc():
    org = OrganisationFactory()
    shop_a = ShopFactory(organisation=org)
    shop_b = ShopFactory(organisation=org)
    make_review(shop=shop_a, star_rating=5, enrichment_status=SUCCESS)
    for _ in range(3):
        make_review(shop=shop_b, star_rating=4, enrichment_status=SUCCESS)

    rows = list_store_report(org_id=org.id, params=_params())

    assert rows[0]["shop_id"] == shop_b.id
