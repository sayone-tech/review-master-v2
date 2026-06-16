"""Tests for apps.dashboard.selectors.aggregations."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dashboard.filters import DashboardFilterParams
from apps.dashboard.selectors.aggregations import (
    dashboard_highlights,
    dashboard_kpis,
    dashboard_sentiment_distribution,
    dashboard_tag_polarity,
    dashboard_top_performing,
    dashboard_your_store,
)
from apps.dashboard.tests.conftest import make_review
from apps.reviews.models import OrgCanonicalTag, Review
from apps.reviews.tests.factories import OrgCanonicalTagFactory, ReviewTagFactory
from apps.shops.tests.factories import ShopFactory

SUCCESS = Review.EnrichmentStatus.SUCCESS
PENDING = Review.EnrichmentStatus.PENDING

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _params(org, shop_ids, *, date_from=None, date_to=None, region_id=None, shop_id=None):
    today = timezone.now().date()
    return DashboardFilterParams(
        region_id=region_id,
        shop_id=shop_id,
        date_from=date_from or today - timedelta(days=30),
        date_to=date_to or today,
        accessible_shop_ids=tuple(shop_ids),
    )


# ===========================================================================
# dashboard_kpis
# ===========================================================================


@pytest.mark.django_db
def test_dashboard_kpis_query_count(accessible_shops, org):
    shop = accessible_shops[0]
    make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=3, sentiment="neutral", enrichment_status=SUCCESS)
    params = _params(org, [s.id for s in accessible_shops])

    with CaptureQueriesContext(connection) as ctx:
        result = dashboard_kpis(org_id=org.id, params=params)

    assert len(ctx.captured_queries) == 1, f"Expected 1 query, got {len(ctx.captured_queries)}"
    assert result["total_reviews"] == 2


@pytest.mark.django_db
def test_dashboard_kpis_basic(accessible_shops, org):
    shop = accessible_shops[0]
    make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=2, sentiment="negative", enrichment_status=SUCCESS)
    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_kpis(org_id=org.id, params=params)
    assert result["total_reviews"] == 2
    assert result["avg_rating"] == 3.0
    assert result["negative_reviews"] == 1
    assert result["negative_pct"] == 50.0
    assert result["store_count"] == len(accessible_shops)


@pytest.mark.django_db
def test_negative_count_ai_sentiment(accessible_shops, org):
    """KPI-03: negative count uses AI sentiment=negative, not star rating."""
    shop = accessible_shops[0]
    # 5 reviews with star=1 but sentiment != negative (or not enriched)
    for _ in range(3):
        make_review(shop=shop, star_rating=1, sentiment="positive", enrichment_status=SUCCESS)
    for _ in range(2):
        make_review(shop=shop, star_rating=1, sentiment="negative", enrichment_status=PENDING)
    # 2 reviews: star=5 but AI says negative + enriched
    make_review(shop=shop, star_rating=5, sentiment="negative", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=5, sentiment="negative", enrichment_status=SUCCESS)

    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_kpis(org_id=org.id, params=params)
    assert result["negative_reviews"] == 2


@pytest.mark.django_db
def test_negative_pct_uses_enriched_denominator(accessible_shops, org):
    """KPI-04: negative_pct denominator is enriched_count, not total_count."""
    shop = accessible_shops[0]
    # 10 reviews total, only 4 enriched, 1 of those is negative
    for _ in range(6):
        make_review(shop=shop, star_rating=3, sentiment="", enrichment_status=PENDING)
    for _ in range(3):
        make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=2, sentiment="negative", enrichment_status=SUCCESS)

    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_kpis(org_id=org.id, params=params)
    assert result["total_reviews"] == 10
    assert result["negative_reviews"] == 1
    assert result["negative_pct"] == 25.0  # 1/4 enriched


@pytest.mark.django_db
def test_dashboard_kpis_empty(accessible_shops, org):
    """Empty org returns zeros."""
    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_kpis(org_id=org.id, params=params)
    assert result["total_reviews"] == 0
    assert result["avg_rating"] == 0.0
    assert result["negative_reviews"] == 0
    assert result["negative_pct"] == 0.0


# ===========================================================================
# dashboard_sentiment_distribution
# ===========================================================================


@pytest.mark.django_db
def test_dashboard_sentiment_query_count(accessible_shops, org):
    shop = accessible_shops[0]
    make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    params = _params(org, [s.id for s in accessible_shops])

    with CaptureQueriesContext(connection) as ctx:
        dashboard_sentiment_distribution(org_id=org.id, params=params)

    assert len(ctx.captured_queries) == 1


@pytest.mark.django_db
def test_sentiment_empty_states(accessible_shops, org):
    """SENT-06: when total=0, coverage_pct=0; when enriched=0, all counts=0."""
    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_sentiment_distribution(org_id=org.id, params=params)
    assert result["total_count"] == 0
    assert result["coverage_pct"] == 0
    assert result["positive"] == 0
    assert result["neutral"] == 0
    assert result["negative"] == 0

    # Now add un-enriched reviews — enriched=0 but total > 0
    shop = accessible_shops[0]
    for _ in range(5):
        make_review(shop=shop, star_rating=3, sentiment="", enrichment_status=PENDING)

    result2 = dashboard_sentiment_distribution(org_id=org.id, params=params)
    assert result2["total_count"] == 5
    assert result2["enriched_count"] == 0
    assert result2["coverage_pct"] == 0
    assert result2["positive"] == 0
    assert result2["neutral"] == 0
    assert result2["negative"] == 0


@pytest.mark.django_db
def test_dashboard_sentiment_distribution_basic(accessible_shops, org):
    """SENT-01: only enriched reviews contribute to sentiment counts."""
    shop = accessible_shops[0]
    make_review(shop=shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=3, sentiment="neutral", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=1, sentiment="negative", enrichment_status=SUCCESS)
    make_review(shop=shop, star_rating=1, sentiment="negative", enrichment_status=PENDING)

    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_sentiment_distribution(org_id=org.id, params=params)
    assert result["positive"] == 1
    assert result["neutral"] == 1
    assert result["negative"] == 1
    assert result["enriched_count"] == 3
    assert result["total_count"] == 4
    assert result["coverage_pct"] == 75


# ===========================================================================
# dashboard_your_store
# ===========================================================================


@pytest.mark.django_db
def test_dashboard_your_store_returns_none_for_multi_shop(accessible_shops, org):
    """Returns None when accessible_shop_ids has > 1 entry."""
    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_your_store(org_id=org.id, params=params)
    assert result is None


@pytest.mark.django_db
def test_dashboard_your_store_basic(single_shop, org):
    """Basic structure is returned for single-shop params."""
    today = timezone.now().date()
    params = DashboardFilterParams(
        region_id=None,
        shop_id=None,
        date_from=today - timedelta(days=30),
        date_to=today,
        accessible_shop_ids=(single_shop.id,),
    )
    make_review(shop=single_shop, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    make_review(shop=single_shop, star_rating=1, sentiment="negative", enrichment_status=SUCCESS)

    result = dashboard_your_store(org_id=org.id, params=params)
    assert result is not None
    assert result["shop_id"] == single_shop.id
    assert result["shop_name"] == single_shop.name
    assert result["total_reviews"] == 2
    assert result["positive_count"] == 1
    assert result["negative_count"] == 1
    assert set(result["distribution"].keys()) == {1, 2, 3, 4, 5}


@pytest.mark.django_db
def test_dashboard_your_store_trend_no_previous_data(single_shop, org):
    """STORE-03: trend_direction = 'none' when previous window has < 3 reviews."""
    today = timezone.now().date()
    params = DashboardFilterParams(
        region_id=None,
        shop_id=None,
        date_from=today - timedelta(days=30),
        date_to=today,
        accessible_shop_ids=(single_shop.id,),
    )
    # Only current-window reviews; no previous window data
    make_review(
        shop=single_shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS, days_ago=5
    )

    result = dashboard_your_store(org_id=org.id, params=params)
    assert result is not None
    assert result["trend_direction"] == "none"
    assert result["trend_delta"] is None


@pytest.mark.django_db
def test_dashboard_your_store_trend_up(single_shop, org):
    """STORE-03: trend_direction = 'up' when current avg > previous avg."""
    today = timezone.now().date()
    params = DashboardFilterParams(
        region_id=None,
        shop_id=None,
        date_from=today - timedelta(days=30),
        date_to=today,
        accessible_shop_ids=(single_shop.id,),
    )
    # Previous window (31-60 days ago): 3 reviews with avg 3.0
    for _ in range(3):
        make_review(
            shop=single_shop,
            star_rating=3,
            sentiment="neutral",
            enrichment_status=SUCCESS,
            days_ago=45,
        )
    # Current window: 3 reviews with avg 5.0
    for _ in range(3):
        make_review(
            shop=single_shop,
            star_rating=5,
            sentiment="positive",
            enrichment_status=SUCCESS,
            days_ago=5,
        )

    result = dashboard_your_store(org_id=org.id, params=params)
    assert result is not None
    assert result["trend_direction"] == "up"
    assert result["trend_delta"] == 2.0


# ===========================================================================
# dashboard_top_performing
# ===========================================================================


@pytest.mark.django_db
def test_top_performing_date_only(org, region):
    """TOP-01: region_id and shop_id filters are ignored — all accessible shops appear."""
    shop1 = ShopFactory(organisation=org, region=region)
    shop2 = ShopFactory(organisation=org, region=region)
    shop3 = ShopFactory(organisation=org, region=region)

    for shop in [shop1, shop2, shop3]:
        for _ in range(3):
            make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)

    today = timezone.now().date()
    params = DashboardFilterParams(
        region_id=region.id,  # should be ignored by dashboard_top_performing
        shop_id=shop1.id,  # should be ignored by dashboard_top_performing
        date_from=today - timedelta(days=30),
        date_to=today,
        accessible_shop_ids=(shop1.id, shop2.id, shop3.id),
    )
    result = dashboard_top_performing(org_id=org.id, params=params)
    shop_ids = [s["shop_id"] for s in result["shops"]]
    assert shop1.id in shop_ids
    assert shop2.id in shop_ids
    assert shop3.id in shop_ids


@pytest.mark.django_db
def test_top_performing_min_reviews(org, region):
    """TOP-02: shops with < 3 reviews are excluded."""
    shop_a = ShopFactory(organisation=org, region=region)
    shop_b = ShopFactory(organisation=org, region=region)

    # shop_a: only 2 reviews — below threshold
    for _ in range(2):
        make_review(shop=shop_a, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    # shop_b: 5 reviews — above threshold
    for _ in range(5):
        make_review(shop=shop_b, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)

    params = _params(org, [shop_a.id, shop_b.id])
    result = dashboard_top_performing(org_id=org.id, params=params)
    shop_ids = [s["shop_id"] for s in result["shops"]]
    assert shop_a.id not in shop_ids
    assert shop_b.id in shop_ids


@pytest.mark.django_db
def test_top_performing_split_at_11_shops(org, region):
    """TOP-02: split=True and len(shops)==10 when > 10 qualifying shops."""
    shops = [ShopFactory(organisation=org, region=region) for _ in range(11)]
    for i, shop in enumerate(shops):
        for _ in range(3):
            make_review(
                shop=shop,
                star_rating=(i % 5) + 1,
                sentiment="positive",
                enrichment_status=SUCCESS,
            )

    params = _params(org, [s.id for s in shops])
    result = dashboard_top_performing(org_id=org.id, params=params)
    assert result["split"] is True
    assert len(result["shops"]) == 10  # top 5 + worst 5


@pytest.mark.django_db
def test_top_performing_query_count(accessible_shops, org):
    """TECH-04: dashboard_top_performing uses exactly 1 DB query."""
    shop = accessible_shops[0]
    for _ in range(3):
        make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)

    params = _params(org, [s.id for s in accessible_shops])

    with CaptureQueriesContext(connection) as ctx:
        dashboard_top_performing(org_id=org.id, params=params)

    assert len(ctx.captured_queries) == 1, f"Expected 1 query, got {len(ctx.captured_queries)}"


@pytest.mark.django_db
def test_top_performing_empty(accessible_shops, org):
    """TOP-07: no shops with >= 3 reviews -> returns empty list with split=False."""
    shop = accessible_shops[0]
    # Only 2 reviews — below threshold
    for _ in range(2):
        make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)

    params = _params(org, [s.id for s in accessible_shops])
    result = dashboard_top_performing(org_id=org.id, params=params)
    assert result == {"shops": [], "split": False}


# ===========================================================================
# dashboard_highlights
# ===========================================================================


@pytest.mark.django_db
def test_highlights_returns_top_and_bottom(org, region):
    """TOP-06: top shop has highest avg_rating, bottom has lowest."""
    shop_high = ShopFactory(organisation=org, region=region)
    shop_mid = ShopFactory(organisation=org, region=region)
    shop_low = ShopFactory(organisation=org, region=region)

    for _ in range(3):
        make_review(shop=shop_high, star_rating=5, sentiment="positive", enrichment_status=SUCCESS)
    for _ in range(3):
        make_review(shop=shop_mid, star_rating=3, sentiment="neutral", enrichment_status=SUCCESS)
    for _ in range(3):
        make_review(shop=shop_low, star_rating=1, sentiment="negative", enrichment_status=SUCCESS)

    params = _params(org, [shop_high.id, shop_mid.id, shop_low.id])
    result = dashboard_highlights(org_id=org.id, params=params)
    assert result["top"] is not None
    assert result["bottom"] is not None
    assert result["top"]["shop_id"] == shop_high.id
    assert result["bottom"]["shop_id"] == shop_low.id


@pytest.mark.django_db
def test_highlights_uses_ai_sentiment_counts(org, region):
    """TOP-06: negative_count reflects AI sentiment, not star rating."""
    shop = ShopFactory(organisation=org, region=region)
    # 3 reviews: star=5 but AI says negative + enriched
    for _ in range(3):
        make_review(shop=shop, star_rating=5, sentiment="negative", enrichment_status=SUCCESS)

    params = _params(org, [shop.id])
    result = dashboard_highlights(org_id=org.id, params=params)
    assert result["top"] is not None
    # avg_rating is 5 (from star_rating) but negative_count is 3 (from AI sentiment)
    assert result["top"]["avg_rating"] == 5.0
    assert result["top"]["negative_count"] == 3
    assert result["top"]["positive_count"] == 0


@pytest.mark.django_db
def test_highlights_query_count(accessible_shops, org):
    """TECH-04: dashboard_highlights uses exactly 1 DB query."""
    shop = accessible_shops[0]
    for _ in range(3):
        make_review(shop=shop, star_rating=4, sentiment="positive", enrichment_status=SUCCESS)

    params = _params(org, [s.id for s in accessible_shops])

    with CaptureQueriesContext(connection) as ctx:
        dashboard_highlights(org_id=org.id, params=params)

    assert len(ctx.captured_queries) == 1, f"Expected 1 query, got {len(ctx.captured_queries)}"


# ===========================================================================
# dashboard_tag_polarity (TDASH-01, TDASH-02)
# ===========================================================================


@pytest.mark.django_db
def test_tag_polarity_basic(org):
    """TDASH-01: mixed tag returns pos/neg split; always_positive tag returns negative_count==0."""
    # Create a mixed tag with both positive and negative ReviewTags
    mixed_tag = OrgCanonicalTagFactory(
        organisation=org, polarity_type=OrgCanonicalTag.PolarityType.MIXED
    )
    review = make_review(shop=ShopFactory(organisation=org), star_rating=3)
    ReviewTagFactory(review=review, polarity="positive", canonical_tag=mixed_tag)
    ReviewTagFactory(review=review, polarity="negative", canonical_tag=mixed_tag)
    ReviewTagFactory(review=review, polarity="positive", canonical_tag=mixed_tag)

    # Create an always_positive tag with only positive ReviewTags
    pos_tag = OrgCanonicalTagFactory(
        organisation=org, polarity_type=OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE
    )
    ReviewTagFactory(review=review, polarity="positive", canonical_tag=pos_tag)

    result = dashboard_tag_polarity(organisation_id=org.id)

    # Find the mixed tag in results
    mixed_result = next((t for t in result["tags"] if t["label"] == mixed_tag.label), None)
    assert mixed_result is not None
    assert mixed_result["positive_count"] > 0
    assert mixed_result["negative_count"] > 0

    # Find the always_positive tag in results
    pos_result = next((t for t in result["tags"] if t["label"] == pos_tag.label), None)
    assert pos_result is not None
    assert pos_result["negative_count"] == 0


@pytest.mark.django_db
def test_tag_polarity_excludes_null_canonical(org):
    """TDASH-02: ReviewTag rows with canonical_tag=None are NOT counted."""
    review = make_review(shop=ShopFactory(organisation=org), star_rating=4)
    # ReviewTag with no canonical tag — must not appear in results
    ReviewTagFactory(review=review, polarity="positive", canonical_tag=None)

    result = dashboard_tag_polarity(organisation_id=org.id)
    assert result["tags"] == []
    assert result["has_more"] is False


@pytest.mark.django_db
def test_tag_polarity_query_count(org):
    """TDASH-02: dashboard_tag_polarity runs in ≤2 DB queries (no N+1)."""
    shop = ShopFactory(organisation=org)
    review = make_review(shop=shop, star_rating=4)
    for _ in range(5):
        tag = OrgCanonicalTagFactory(
            organisation=org, polarity_type=OrgCanonicalTag.PolarityType.MIXED
        )
        ReviewTagFactory(review=review, polarity="positive", canonical_tag=tag)
        ReviewTagFactory(review=review, polarity="negative", canonical_tag=tag)

    with CaptureQueriesContext(connection) as ctx:
        result = dashboard_tag_polarity(organisation_id=org.id)

    assert len(ctx.captured_queries) <= 2, (
        f"Expected ≤2 queries, got {len(ctx.captured_queries)}: "
        f"{[q['sql'][:80] for q in ctx.captured_queries]}"
    )
    assert len(result["tags"]) == 5
