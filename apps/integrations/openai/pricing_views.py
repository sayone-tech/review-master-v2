"""AI pricing API views (Superadmin). Routed from ``api_urls.py`` under ``api/v1/``."""

from __future__ import annotations

from typing import Any

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsSuperadmin
from apps.common.pagination import DefaultPageNumberPagination
from apps.integrations.openai.selectors.pricing import (
    invalidate_missing_pricing_cache,
    list_missing_pricing_models,
    list_model_suggestions,
    list_price_history,
    list_price_summary,
)
from apps.integrations.openai.serializers import (
    MissingModelsResponseSerializer,
    ModelSuggestionsResponseSerializer,
    PriceHistoryListResponseSerializer,
    PriceRowSerializer,
    PriceSummaryListResponseSerializer,
    PriceSummaryRowSerializer,
)
from apps.integrations.openai.views import _generated_at

PRICING_TAG = "superadmin-ai-pricing"
PRICING_ERRORS = {
    403: OpenApiResponse(description="Superadmin role required"),
    429: OpenApiResponse(description="Throttled"),
}


class _AiPricingBaseView(APIView):
    permission_classes = [IsAuthenticated, IsSuperadmin]  # noqa: RUF012
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    throttle_scope = "superadmin_ai_pricing_read"


def _missing_payload() -> dict[str, Any]:
    return dict(
        MissingModelsResponseSerializer(
            {"models": list_missing_pricing_models(), "generated_at": _generated_at()}
        ).data
    )


class AiPricingListView(_AiPricingBaseView):
    """GET /api/v1/superadmin/ai-pricing/ (Superadmin only)."""

    @extend_schema(
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Rows per page (default 25, max 100)"),
        ],
        responses={200: PriceSummaryListResponseSerializer, **PRICING_ERRORS},
        tags=[PRICING_TAG],
    )
    def get(self, request: Request) -> Response:
        now = timezone.now()
        paginator = DefaultPageNumberPagination()
        # DRF paginates any sliceable sequence; the stubs only type QuerySet.
        page: list[Any] = (
            paginator.paginate_queryset(
                list_price_summary(now=now),  # type: ignore[arg-type]
                request,
                view=self,
            )
            or []
        )
        data = PriceSummaryRowSerializer(page, many=True, context={"now": now}).data
        return paginator.get_paginated_response(data)


class AiPricingHistoryView(_AiPricingBaseView):
    """GET /api/v1/superadmin/ai-pricing/history/?model=<model> (Superadmin only)."""

    @extend_schema(
        parameters=[
            OpenApiParameter("model", str, required=True, description="Model id"),
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Rows per page (default 25, max 100)"),
        ],
        responses={
            200: PriceHistoryListResponseSerializer,
            400: OpenApiResponse(description="model is required"),
            **PRICING_ERRORS,
        },
        tags=[PRICING_TAG],
    )
    def get(self, request: Request) -> Response:
        model = (request.query_params.get("model") or "").strip()
        if not model:
            raise ValidationError({"model": "This query parameter is required."})
        paginator = DefaultPageNumberPagination()
        page = paginator.paginate_queryset(list_price_history(model=model), request, view=self)
        data = PriceRowSerializer(page, many=True, context={"now": timezone.now()}).data
        return paginator.get_paginated_response(data)


class AiPricingSuggestionsView(_AiPricingBaseView):
    """GET /api/v1/superadmin/ai-pricing/model-suggestions/?q= (Superadmin only)."""

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Case-insensitive substring filter")],
        responses={200: ModelSuggestionsResponseSerializer, **PRICING_ERRORS},
        tags=[PRICING_TAG],
    )
    def get(self, request: Request) -> Response:
        suggestions = list_model_suggestions(query=request.query_params.get("q", ""), limit=20)
        return Response(ModelSuggestionsResponseSerializer({"results": suggestions}).data)


class AiPricingMissingView(_AiPricingBaseView):
    """GET /api/v1/superadmin/ai-pricing/missing/ (Superadmin only)."""

    @extend_schema(
        responses={200: MissingModelsResponseSerializer, **PRICING_ERRORS},
        tags=[PRICING_TAG],
    )
    def get(self, request: Request) -> Response:
        return Response(_missing_payload())


class AiPricingMissingRefreshView(_AiPricingBaseView):
    """POST /api/v1/superadmin/ai-pricing/missing/refresh/ (Superadmin only)."""

    throttle_scope = "superadmin_ai_pricing_refresh"

    @extend_schema(
        request=None,
        responses={200: MissingModelsResponseSerializer, **PRICING_ERRORS},
        tags=[PRICING_TAG],
    )
    def post(self, request: Request) -> Response:
        invalidate_missing_pricing_cache()
        return Response(_missing_payload())
