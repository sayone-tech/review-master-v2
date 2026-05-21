"""Phase 11 — ReviewViewSet + review_list template view."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Exists, OuterRef, Q, QuerySet
from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore[import-untyped]
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet
from apps.reviews.exceptions import ReplyConflictError, ReplyFailedError
from apps.reviews.filters import ReviewFilterSet
from apps.reviews.models import Review
from apps.reviews.selectors.reviews import (
    base_reviews_queryset,
    get_accessible_shop_ids,
)
from apps.reviews.serializers import ReviewReadSerializer, ReviewReplySerializer
from apps.reviews.services.replies import remove_reply, submit_reply


class ReviewPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"


class ReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    serializer_class = ReviewReadSerializer
    pagination_class = ReviewPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]  # noqa: RUF012
    filterset_class = ReviewFilterSet
    ordering_fields = ["review_create_time", "star_rating"]  # noqa: RUF012
    ordering = ["-review_create_time"]  # noqa: RUF012
    throttle_scope = "review_reply"  # used only when ScopedRateThrottle is selected
    queryset = Review.objects.none()

    def get_queryset(self) -> QuerySet[Review]:
        user = self.request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return Review.objects.none()
        qs = base_reviews_queryset(organisation_id=org_id)
        if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
            raw_pk = user.pk
            if raw_pk is None:
                return Review.objects.none()
            user_id: int = raw_pk
            qs = qs.filter(shop_id__in=get_accessible_shop_ids(user_id=user_id))
        # Phase 13 Plan 07 (B3): annotate has_action_items via Exists() so the
        # ReviewReadSerializer's BooleanField is folded into the existing list
        # JOIN — no extra queries (REVW-14 <=5 query budget preserved).
        # Local import to avoid app-load cycles between reviews and action_items.
        from apps.action_items.models import ActionItem

        return qs.annotate(
            has_action_items=Exists(ActionItem.objects.filter(source_review=OuterRef("pk")))
        )

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        total_count = qs.values("pk").count()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
        else:
            response = Response({"results": serializer.data})
        response.data["total_count"] = total_count
        return response

    @action(detail=False, methods=["get"], url_path="tags")
    def tags(self, request: Request) -> Response:
        """Return distinct tag labels + counts scoped to the caller's org.

        ?shop=<id> — optional, narrows to a single shop.
        Staff users see only tags from their accessible shops.
        """
        user = request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return Response([])

        # Local import — avoids any circular import risk at module load time.
        from apps.reviews.models import ReviewTag

        qs = ReviewTag.objects.filter(review__shop__organisation_id=org_id)

        shop_id = request.query_params.get("shop")
        if shop_id:
            qs = qs.filter(review__shop_id=shop_id)

        if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
            raw_pk = user.pk
            if raw_pk is None:
                return Response([])
            user_id: int = raw_pk
            qs = qs.filter(review__shop_id__in=get_accessible_shop_ids(user_id=user_id))

        result = qs.values("label").annotate(count=Count("id")).order_by("-count")
        return Response([{"label": row["label"], "count": row["count"]} for row in result])

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request: Request) -> Response:
        """Aggregate stats for the reviews list header cards."""
        qs = self.filter_queryset(self.get_queryset())
        agg = qs.aggregate(
            total=Count("pk"),
            avg_rating=Avg("star_rating"),
            awaiting_reply=Count("pk", filter=Q(is_replied=False)),
            positive_count=Count(
                "pk",
                filter=Q(sentiment="positive", enrichment_status=Review.EnrichmentStatus.SUCCESS),
            ),
            enriched_count=Count("pk", filter=Q(enrichment_status=Review.EnrichmentStatus.SUCCESS)),
        )
        total: int = agg["total"] or 0
        avg_rating: float = round(float(agg["avg_rating"] or 0.0), 1)
        awaiting_reply: int = agg["awaiting_reply"] or 0
        enriched: int = agg["enriched_count"] or 0
        positive_pct: int = (
            round((agg["positive_count"] or 0) / enriched * 100) if enriched > 0 else 0
        )
        return Response(
            {
                "total_count": total,
                "avg_rating": avg_rating,
                "awaiting_reply_count": awaiting_reply,
                "positive_sentiment_pct": positive_pct,
            }
        )

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="reply",
        throttle_classes=[ScopedRateThrottle],
    )
    def reply(self, request: Request, pk: int | None = None) -> Response:
        """POST: submit reply to Google. DELETE: remove reply from Google."""
        self.throttle_scope = "review_reply"
        review = self.get_object()

        if request.method == "DELETE":
            if not review.is_replied:
                return Response(
                    {"detail": "This review has no reply to delete.", "code": "no_reply"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                updated = remove_reply(review=review, actor=request.user)
            except ReplyConflictError as exc:
                return Response(
                    {"detail": str(exc), "code": "conflict"},
                    status=status.HTTP_409_CONFLICT,
                )
            except ReplyFailedError as exc:
                return Response(
                    {"detail": exc.message, "code": exc.code},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return Response(ReviewReadSerializer(updated).data, status=status.HTTP_200_OK)

        serializer = ReviewReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = submit_reply(
                review=review,
                comment=serializer.validated_data["comment"],
                actor=request.user,
            )
        except ReplyConflictError as exc:
            return Response(
                {"detail": str(exc), "code": "conflict"},
                status=status.HTTP_409_CONFLICT,
            )
        except ReplyFailedError as exc:
            return Response(
                {"detail": exc.message, "code": exc.code},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(ReviewReadSerializer(updated).data, status=status.HTTP_200_OK)


@login_required(login_url="/login/")
def review_list(request):  # type: ignore[no-untyped-def]
    user = request.user
    open_progress = request.GET.get("open_progress") or ""
    org_id = getattr(user, "organisation_id", None)

    shops_data: list[Any] = []
    has_connected = False
    if org_id is not None:
        from apps.shops.models import Shop

        qs = Shop.objects.filter(organisation_id=org_id, is_active=True)
        if getattr(user, "role", "") == "STAFF_ADMIN":
            qs = qs.filter(id__in=get_accessible_shop_ids(user_id=user.pk))
        shops_data = list(qs.values("id", "name").order_by("name"))
        has_connected = qs.filter(connection_status=Shop.ConnectionStatus.CONNECTED).exists()

    return render(
        request,
        "reviews/review_list.html",
        {
            "page_title": "Reviews",
            "open_progress_shop_id": open_progress,
            "current_user_role": getattr(user, "role", ""),
            "shops_json": shops_data,
            "has_connected_shops": has_connected,
        },
    )
