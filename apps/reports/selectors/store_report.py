from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Avg, Count, Q

from apps.reviews.models import Review

SUCCESS = Review.EnrichmentStatus.SUCCESS


@dataclass(frozen=True)
class ReportFilterParams:
    date_from: date | None
    date_to: date | None
    reply_status: str | None  # 'replied' | 'not_replied' | None
    sentiment: str | None  # 'positive' | 'neutral' | 'negative' | None


def list_store_report(*, org_id: int, params: ReportFilterParams) -> list[dict]:  # type: ignore[type-arg]
    """Return per-store review summary in a single DB query.

    Stores with zero matching reviews are excluded from results.
    Results ordered by total_reviews descending.
    """
    qs = Review.objects.active().filter(organisation_id=org_id)

    if params.date_from is not None:
        qs = qs.filter(review_create_time__date__gte=params.date_from)
    if params.date_to is not None:
        qs = qs.filter(review_create_time__date__lte=params.date_to)
    if params.reply_status == "replied":
        qs = qs.filter(is_replied=True)
    elif params.reply_status == "not_replied":
        qs = qs.filter(is_replied=False)
    if params.sentiment is not None:
        qs = qs.filter(enrichment_status=SUCCESS, sentiment=params.sentiment)

    rows = (
        qs.values("shop_id", "shop__name")
        .annotate(
            total_reviews=Count("pk"),
            avg_rating=Avg("star_rating"),
            replied_count=Count("pk", filter=Q(is_replied=True)),
            not_replied_count=Count("pk", filter=Q(is_replied=False)),
            positive_count=Count("pk", filter=Q(enrichment_status=SUCCESS, sentiment="positive")),
            neutral_count=Count("pk", filter=Q(enrichment_status=SUCCESS, sentiment="neutral")),
            negative_count=Count("pk", filter=Q(enrichment_status=SUCCESS, sentiment="negative")),
        )
        .order_by("-total_reviews")
    )

    return [
        {
            "shop_id": r["shop_id"],
            "shop_name": r["shop__name"],
            "total_reviews": r["total_reviews"],
            "avg_rating": round(float(r["avg_rating"]), 2) if r["avg_rating"] else 0.0,
            "replied_count": r["replied_count"],
            "not_replied_count": r["not_replied_count"],
            "positive_count": r["positive_count"],
            "neutral_count": r["neutral_count"],
            "negative_count": r["negative_count"],
        }
        for r in rows
    ]
