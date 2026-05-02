"""Phase 11 — ReviewViewSet + review_list template view."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore[import-untyped]
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import CursorPagination
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
from apps.reviews.services.replies import submit_reply


class ReviewCursorPagination(CursorPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-review_create_time"
    cursor_query_param = "cursor"


class ReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    serializer_class = ReviewReadSerializer
    pagination_class = ReviewCursorPagination
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
            user_id: int = user.pk  # type: ignore[assignment]
            qs = qs.filter(shop_id__in=get_accessible_shop_ids(user_id=user_id))
        return qs

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

    @action(
        detail=True,
        methods=["post"],
        url_path="reply",
        throttle_classes=[ScopedRateThrottle],
    )
    def reply(self, request: Request, pk: int | None = None) -> Response:
        """Submit a reply that is posted to Google synchronously."""
        self.throttle_scope = "review_reply"
        review = self.get_object()
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

    shops_data: list[dict[str, Any]] = []
    has_connected = False
    if org_id is not None:
        from apps.shops.models import Shop

        qs = Shop.objects.filter(organisation_id=org_id, is_active=True)
        if getattr(user, "role", "") == "STAFF_ADMIN":
            qs = qs.filter(id__in=get_accessible_shop_ids(user_id=user.pk))
        shops_data = list(qs.values("id", "name").order_by("name"))  # type: ignore[arg-type]
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
