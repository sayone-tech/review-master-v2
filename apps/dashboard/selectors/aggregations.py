"""Dashboard aggregation selectors.

Each function performs all aggregation inside the database via a single
``aggregate()`` or ``values().annotate()`` call.  No Python-side looping
over QuerySets.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from django.db.models import Avg, Count, Min, Q, QuerySet
from django.utils import timezone

from apps.dashboard.filters import DashboardFilterParams
from apps.reviews.models import Review, ReviewTag

MIN_REVIEWS_FOR_RANKING = 3
TREND_BUCKETS = 6
ALL_STORES_CAP = 200

SUCCESS = Review.EnrichmentStatus.SUCCESS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scope_qs(*, org_id: int, params: DashboardFilterParams) -> QuerySet[Review]:
    """Org + shop scope + region/store filters, with NO date restriction."""
    qs: QuerySet[Review] = (
        Review.objects.active()
        .filter(organisation_id=org_id)
        .filter(shop_id__in=params.accessible_shop_ids)
    )
    if params.region_id is not None:
        qs = qs.filter(shop__region_id=params.region_id)
    if params.shop_id is not None:
        qs = qs.filter(shop_id=params.shop_id)
    return qs


def _base_qs(*, org_id: int, params: DashboardFilterParams) -> QuerySet[Review]:
    """Applies org + shop scope + full filters (region + shop + date)."""
    qs = _scope_qs(org_id=org_id, params=params)
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


def _day_q(start: date, end: date) -> Q:
    """Inclusive UTC-date window on review_create_time."""
    return Q(review_create_time__date__gte=start, review_create_time__date__lte=end)


def _window_aggs(prefix: str, window: Q) -> dict[str, Any]:
    """Conditional aggregates for one window (empty Q = unrestricted)."""
    enriched = window & Q(enrichment_status=SUCCESS)
    return {
        f"{prefix}total": Count("pk", filter=window),
        f"{prefix}avg": Avg("star_rating", filter=window),
        f"{prefix}enriched": Count("pk", filter=enriched),
        f"{prefix}negative": Count("pk", filter=enriched & Q(sentiment="negative")),
        f"{prefix}awaiting": Count("pk", filter=window & Q(reply_comment="")),
    }


def _pct(negative: int, enriched: int) -> float:
    return round(negative / enriched * 100, 1) if enriched > 0 else 0.0


def _trend_windows(params: DashboardFilterParams) -> list[tuple[date, date]]:
    """Six contiguous inclusive (start, end) windows, oldest first.

    Date range: bucket i covers day offsets [floor(i*N/6), floor((i+1)*N/6)).
    All time: the last six calendar months including the current one (UTC).
    A window with start > end is empty (range shorter than six days).
    """
    if params.date_from is not None and params.date_to is not None:
        n = (params.date_to - params.date_from).days + 1
        return [
            (
                params.date_from + timedelta(days=i * n // TREND_BUCKETS),
                params.date_from + timedelta(days=(i + 1) * n // TREND_BUCKETS - 1),
            )
            for i in range(TREND_BUCKETS)
        ]
    today = timezone.now().date()
    months = [(today.year * 12 + today.month - 1) - k for k in range(TREND_BUCKETS - 1, -1, -1)]
    out: list[tuple[date, date]] = []
    for m in months:
        first = date(m // 12, m % 12 + 1, 1)
        nxt = date((m + 1) // 12, (m + 1) % 12 + 1, 1)
        out.append((first, nxt - timedelta(days=1)))
    return out


def _kpi_trend(*, org_id: int, params: DashboardFilterParams) -> dict[str, list[Any]]:
    windows = _trend_windows(params)
    live = [(i, w) for i, w in enumerate(windows) if w[0] <= w[1]]
    aggs: dict[str, Any] = {}
    for i, (start, end) in live:
        aggs.update(_window_aggs(f"b{i}_", _day_q(start, end)))
    total = [0] * TREND_BUCKETS
    avg: list[float | None] = [None] * TREND_BUCKETS
    neg: list[float | None] = [None] * TREND_BUCKETS
    if live:
        qs = _scope_qs(org_id=org_id, params=params).filter(_day_q(live[0][1][0], live[-1][1][1]))
        row = qs.aggregate(**aggs)
        for i, _ in live:
            total[i] = row[f"b{i}_total"] or 0
            if row[f"b{i}_avg"] is not None:
                avg[i] = round(float(row[f"b{i}_avg"]), 1)
            enriched = row[f"b{i}_enriched"] or 0
            if enriched > 0:
                neg[i] = _pct(row[f"b{i}_negative"] or 0, enriched)
    return {"total_reviews": total, "avg_rating": avg, "negative_pct": neg}


def dashboard_kpis(*, org_id: int, params: DashboardFilterParams) -> dict[str, Any]:
    """Return top-level KPI metrics, previous-period comparison, trend and oldest wait.

    Queries (3 max): current+previous conditional aggregates, the six trend
    buckets, and the oldest awaiting review.

    KPI-03: negative_reviews counts only AI-sentiment='negative' with
    enrichment_status=SUCCESS — NOT by star rating.
    KPI-04: negative_pct denominator is enriched_count.
    KPI-05: awaiting_reply counts reviews with no reply posted yet.
    previous: same-length window immediately before date_from (None for all time).
    """
    scope = _scope_qs(org_id=org_id, params=params)
    d_from, d_to = params.date_from, params.date_to
    has_range = d_from is not None and d_to is not None
    aggs: dict[str, Any] = {}
    if d_from is not None and d_to is not None:
        n = (d_to - d_from).days + 1
        prev_from = d_from - timedelta(days=n)
        prev_to = d_from - timedelta(days=1)
        scope = scope.filter(_day_q(prev_from, d_to))
        cur_q = _day_q(d_from, d_to)
        aggs.update(_window_aggs("p_", _day_q(prev_from, prev_to)))
    else:
        cur_q = Q()
    aggs.update(_window_aggs("c_", cur_q))
    agg = scope.aggregate(**aggs)

    total = agg["c_total"] or 0
    enriched = agg["c_enriched"] or 0
    negative = agg["c_negative"] or 0

    previous: dict[str, Any] | None = None
    if has_range:
        p_enriched = agg["p_enriched"] or 0
        previous = {
            "total_reviews": agg["p_total"] or 0,
            "avg_rating": round(float(agg["p_avg"] or 0.0), 1),
            "negative_pct": _pct(agg["p_negative"] or 0, p_enriched),
            "awaiting_reply": agg["p_awaiting"] or 0,
        }

    oldest = (
        _base_qs(org_id=org_id, params=params)
        .filter(reply_comment="")
        .aggregate(oldest=Min("review_create_time"))["oldest"]
    )
    oldest_days: int | None = None
    if oldest is not None:
        oldest_days = max((timezone.now().date() - oldest.date()).days, 0)

    return {
        "total_reviews": total,
        "avg_rating": round(float(agg["c_avg"] or 0.0), 1),
        "negative_reviews": negative,
        "negative_pct": _pct(negative, enriched),
        "enriched_count": enriched,
        "store_count": len(params.accessible_shop_ids),
        "awaiting_reply": agg["c_awaiting"] or 0,
        "previous": previous,
        "trend": _kpi_trend(org_id=org_id, params=params),
        "oldest_awaiting_days": oldest_days,
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
    all_stores = [
        {
            "shop_id": r["shop_id"],
            "shop_name": r["shop_name"],
            "avg_rating": r["avg_rating"],
            "review_count": r["review_count"],
        }
        for r in shops[:ALL_STORES_CAP]
    ]
    if len(shops) > 10:
        return {"shops": shops[:5] + shops[-5:], "split": True, "all_stores": all_stores}
    return {"shops": shops, "split": False, "all_stores": all_stores}


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


def dashboard_tag_polarity(*, organisation_id: int, limit: int = 10) -> dict[str, Any]:
    """Return top-N canonical tags with positive/negative split (TDASH-01, TDASH-02).

    TDASH-02: canonical_tag__organisation_id=organisation_id already implies
    canonical_tag IS NOT NULL — no redundant Python-side null filter needed.
    No N+1: single ReviewTag grouped aggregate query.
    Query ceiling: 1 query (the aggregate) — well within the ≤2 limit.
    """
    rows: list[dict[str, Any]] = cast(
        list[dict[str, Any]],
        list(
            ReviewTag.objects.filter(canonical_tag__organisation_id=organisation_id)
            .values(
                "canonical_tag_id",
                "canonical_tag__label",
                "canonical_tag__polarity_type",
            )
            .annotate(
                positive_count=Count("id", filter=Q(polarity="positive")),
                negative_count=Count("id", filter=Q(polarity="negative")),
                total_count=Count("id"),
            )
            .order_by("-total_count")[: limit + 1]
        ),
    )
    has_more = len(rows) > limit
    return {
        "tags": [
            {
                "label": r["canonical_tag__label"],
                "polarity_type": r["canonical_tag__polarity_type"],
                "positive_count": r["positive_count"],
                "negative_count": r["negative_count"],
                "total_count": r["total_count"],
            }
            for r in rows[:limit]
        ],
        "has_more": has_more,
    }
