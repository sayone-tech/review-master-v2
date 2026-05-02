"""Phase 11 — ReviewViewSet + review_list template view."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import QuerySet
from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore[import-untyped]
from rest_framework import mixins
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet
from apps.reviews.filters import ReviewFilterSet
from apps.reviews.models import Review
from apps.reviews.selectors.reviews import (
    base_reviews_queryset,
    get_accessible_shop_ids,
)
from apps.reviews.serializers import ReviewReadSerializer


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


@login_required(login_url="/login/")
def review_list(request):  # type: ignore[no-untyped-def]
    user = request.user
    open_progress = request.GET.get("open_progress") or ""
    return render(
        request,
        "reviews/review_list.html",
        {
            "page_title": "Reviews",
            "open_progress_shop_id": open_progress,
            "current_user_role": getattr(user, "role", ""),
        },
    )
