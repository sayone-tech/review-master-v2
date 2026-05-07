"""Dashboard aggregation selectors.

Each function performs all aggregation inside the database via a single
``aggregate()`` or ``values().annotate()`` call.  No Python-side looping
over QuerySets.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import Avg, Count, Q, QuerySet

from apps.dashboard.filters import DashboardFilterParams
from apps.reviews.models import Review

MIN_REVIEWS_FOR_RANKING = 3

SUCCESS = Review.EnrichmentStatus.SUCCESS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _base_qs(*, org_id: int, params: DashboardFilterParams) -> QuerySet[Review]:
    """Applies org + shop scope + full filters (region + shop + date)."""
    qs: QuerySet[Review] = (
        Review.objects.active()
        .filter(organisation_id=org_id)
        .filter(shop_id__in=params.accessible_shop_ids)
    )
    if params.region_id is not None:
        qs = qs.filter(shop__region_id=params.region_id)
    if params.shop_id is not None:
        qs = qs.filter(shop_id=params.shop_id)
    if params.date_from is not None:
        qs = qs.filter(review_create_time__date__gte=params.date_from)
    if params.date_to is not None:
        qs = qs.filter(review_create_time__date__lte=params.date_to)
    return qs


def _date_only_qs(*, org_id: int, params: DashboardFilterParams) -> QuerySet[Review]:
    """Date-range only — does NOT apply region_id or shop_id (TOP-01)."""
    qs: QuerySet[Review] = (
        Review.objects.active()
        .filter(organisation_id=org_id)
        .filter(shop_id__in=params.accessible_shop_ids)
    )
    if params.date_from is not None:
        qs = qs.filter(review_create_time__date__gte=params.date_from)
    if params.date_to is not None:
        qs = qs.filter(review_create_time__date__lte=params.date_to)
    return qs


# ---------------------------------------------------------------------------
# Public selectors
# ---------------------------------------------------------------------------


def dashboard_kpis(*, org_id: int, params: DashboardFilterParams) -> dict[str, Any]:
    """Return top-level KPI metrics in a single DB query.

    Keys: total_reviews, avg_rating, negative_reviews, negative_pct,
    enriched_count, store_count.

    KPI-03: negative_reviews counts only AI-sentiment='negative' with
    enrichment_status=SUCCESS — NOT by star rating.
    KPI-04: negative_pct denominator is enriched_count.
    """
    agg = _base_qs(org_id=org_id, params=params).aggregate(
        total_reviews=Count("pk"),
        avg_rating=Avg("star_rating"),
        enriched_count=Count("pk", filter=Q(enrichment_status=SUCCESS)),
        negative_count=Count(
            "pk",
            filter=Q(sentiment="negative", enrichment_status=SUCCESS),
        ),
    )
    total = agg["total_reviews"] or 0
    enriched = agg["enriched_count"] or 0
    negative = agg["negative_count"] or 0
    avg_rating = round(float(agg["avg_rating"] or 0.0), 1)
    neg_pct = round(negative / enriched * 100, 1) if enriched > 0 else 0.0
    return {
        "total_reviews": total,
        "avg_rating": avg_rating,
        "negative_reviews": negative,
        "negative_pct": neg_pct,
        "enriched_count": enriched,
        "store_count": len(params.accessible_shop_ids),
    }


def dashboard_sentiment_distribution(
    *, org_id: int, params: DashboardFilterParams
) -> dict[str, Any]:
    """Return positive/neutral/negative counts and coverage in a single DB query.

    SENT-01: only enriched (enrichment_status=SUCCESS) reviews contribute.
    SENT-04: coverage_pct = enriched / total * 100.
    SENT-06: coverage_pct = 0 when total = 0.
    """
    agg = _base_qs(org_id=org_id, params=params).aggregate(
        total=Count("pk"),
        enriched=Count("pk", filter=Q(enrichment_status=SUCCESS)),
        positive=Count("pk", filter=Q(sentiment="positive", enrichment_status=SUCCESS)),
        neutral=Count("pk", filter=Q(sentiment="neutral", enrichment_status=SUCCESS)),
        negative=Count("pk", filter=Q(sentiment="negative", enrichment_status=SUCCESS)),
    )
    total = agg["total"] or 0
    enriched = agg["enriched"] or 0
    coverage_pct = round(enriched / total * 100) if total > 0 else 0
    return {
        "positive": agg["positive"] or 0,
        "neutral": agg["neutral"] or 0,
        "negative": agg["negative"] or 0,
        "enriched_count": enriched,
        "total_count": total,
        "coverage_pct": coverage_pct,
    }


def dashboard_your_store(*, org_id: int, params: DashboardFilterParams) -> dict[str, Any] | None:
    """Return single-shop KPIs, star distribution, and rating trend.

    Returns None when accessible_shop_ids contains more than one shop.
    STORE-02: shop_name, region_name, avg_rating, total_reviews, positive/negative
              counts and pcts, star distribution.
    STORE-03: trend vs previous window (same day-length window immediately before
              date_from). trend_direction = 'none' when previous window has < 3
              reviews.
    """
    if len(params.accessible_shop_ids) != 1:
        return None
    shop_id = params.accessible_shop_ids[0]

    from apps.shops.models import Shop

    shop = Shop.objects.select_related("region").filter(pk=shop_id).first()
    if shop is None:
        return None

    current_qs = _base_qs(org_id=org_id, params=params)
    agg = current_qs.aggregate(
        total=Count("pk"),
        avg_rating=Avg("star_rating"),
        positive=Count("pk", filter=Q(sentiment="positive", enrichment_status=SUCCESS)),
        negative=Count("pk", filter=Q(sentiment="negative", enrichment_status=SUCCESS)),
        r1=Count("pk", filter=Q(star_rating=1)),
        r2=Count("pk", filter=Q(star_rating=2)),
        r3=Count("pk", filter=Q(star_rating=3)),
        r4=Count("pk", filter=Q(star_rating=4)),
        r5=Count("pk", filter=Q(star_rating=5)),
    )

    # Previous-window comparison (STORE-03)
    trend_direction = "none"
    trend_delta: float | None = None
    if params.date_from and params.date_to:
        window_days = (params.date_to - params.date_from).days
        prev_to: date = params.date_from - timedelta(days=1)
        prev_from: date = prev_to - timedelta(days=window_days)
        prev = (
            Review.objects.active()
            .filter(organisation_id=org_id, shop_id=shop_id)
            .filter(review_create_time__date__gte=prev_from)
            .filter(review_create_time__date__lte=prev_to)
            .aggregate(prev_total=Count("pk"), prev_avg=Avg("star_rating"))
        )
        prev_total = prev["prev_total"] or 0
        curr_avg = float(agg["avg_rating"] or 0.0)
        prev_avg = float(prev["prev_avg"] or 0.0)
        if prev_total >= MIN_REVIEWS_FOR_RANKING and (agg["total"] or 0) > 0:
            delta = round(curr_avg - prev_avg, 1)
            if delta > 0:
                trend_direction, trend_delta = "up", delta
            elif delta < 0:
                trend_direction, trend_delta = "down", delta
            else:
                trend_direction, trend_delta = "flat", 0.0

    total = agg["total"] or 0
    positive = agg["positive"] or 0
    negative = agg["negative"] or 0
    region_name: str | None = None
    if shop.region_id is not None and shop.region is not None:
        region_name = shop.region.name
    return {
        "shop_id": shop.id,
        "shop_name": shop.name,
        "region_name": region_name,
        "avg_rating": round(float(agg["avg_rating"] or 0.0), 1),
        "total_reviews": total,
        "positive_count": positive,
        "positive_pct": round(positive / total * 100, 1) if total else 0.0,
        "negative_count": negative,
        "negative_pct": round(negative / total * 100, 1) if total else 0.0,
        "distribution": {
            1: agg["r1"] or 0,
            2: agg["r2"] or 0,
            3: agg["r3"] or 0,
            4: agg["r4"] or 0,
            5: agg["r5"] or 0,
        },
        "trend_direction": trend_direction,
        "trend_delta": trend_delta,
    }


def dashboard_top_performing(*, org_id: int, params: DashboardFilterParams) -> dict[str, Any]:
    """Return top-performing shops list in a single DB query.

    TOP-01: ignores region_id and shop_id — only org, accessible_shop_ids and
            date range apply.
    TOP-02: excludes shops with review_count < MIN_REVIEWS_FOR_RANKING.
    Returns {"shops": [...], "split": False} when <= 10 qualifying shops.
    Returns {"shops": top5 + worst5, "split": True} when > 10 qualifying shops.
    """
    rows = (
        _date_only_qs(org_id=org_id, params=params)
        .values("shop_id", "shop__name")
        .annotate(review_count=Count("pk"), avg_rating=Avg("star_rating"))
        .filter(review_count__gte=MIN_REVIEWS_FOR_RANKING)
        .order_by("-avg_rating", "-review_count")
    )
    shops: list[dict[str, Any]] = [
        {
            "shop_id": r["shop_id"],
            "shop_name": r["shop__name"],
            "review_count": r["review_count"],
            "avg_rating": round(float(r["avg_rating"]), 2),
        }
        for r in rows
    ]
    if len(shops) > 10:
        return {"shops": shops[:5] + shops[-5:], "split": True}
    return {"shops": shops, "split": False}


def dashboard_highlights(*, org_id: int, params: DashboardFilterParams) -> dict[str, Any]:
    """Return top and bottom performing shop highlights in a single DB query.

    TOP-06: uses AI-derived positive/negative counts (not star rating).
    Returns {"top": None, "bottom": None} when no qualifying shops.
    """
    rows = (
        _date_only_qs(org_id=org_id, params=params)
        .values("shop_id", "shop__name")
        .annotate(
            review_count=Count("pk"),
            avg_rating=Avg("star_rating"),
            positive=Count("pk", filter=Q(sentiment="positive", enrichment_status=SUCCESS)),
            negative=Count("pk", filter=Q(sentiment="negative", enrichment_status=SUCCESS)),
        )
        .filter(review_count__gte=MIN_REVIEWS_FOR_RANKING)
        .order_by("-avg_rating", "-review_count")
    )
    shops = list(rows)
    if not shops:
        return {"top": None, "bottom": None}
    top = shops[0]
    bottom = shops[-1] if len(shops) > 1 else None

    def _shape(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "shop_id": r["shop_id"],
            "shop_name": r["shop__name"],
            "avg_rating": round(float(r["avg_rating"]), 2),
            "positive_count": r["positive"],
            "negative_count": r["negative"],
            "review_count": r["review_count"],
        }

    return {"top": _shape(top), "bottom": _shape(bottom) if bottom else None}
