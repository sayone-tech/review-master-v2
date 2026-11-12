"""AI pricing API views (Superadmin). Routed from ``api_urls.py`` under ``api/v1/``."""

from __future__ import annotations

from typing import Any, cast

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsSuperadmin
from apps.common.pagination import DefaultPageNumberPagination
from apps.common.throttling import SyncTriggerThrottle
from apps.integrations.openai.models import AiPricing
from apps.integrations.openai.selectors.pricing import (
    list_missing_pricing_models,
    list_model_suggestions,
    list_price_history,
    list_price_summary,
)
from apps.integrations.openai.selectors.pricing_sync import get_sync_status
from apps.integrations.openai.serializers import (
    AiPriceCreateSerializer,
    MissingModelsResponseSerializer,
    ModelSuggestionsResponseSerializer,
    PriceHistoryListResponseSerializer,
    PriceRowSerializer,
    PriceSummaryListResponseSerializer,
    PriceSummaryRowSerializer,
    SyncStatusSerializer,
    SyncToggleSerializer,
    SyncTriggerResponseSerializer,
)
from apps.integrations.openai.services.pricing_cache import invalidate_missing_pricing_cache
from apps.integrations.openai.services.pricing_management import (
    BackdatedPriceError,
    PricingError,
    add_price,
    delete_scheduled_price,
)
from apps.integrations.openai.services.pricing_sync import set_sync_enabled
from apps.integrations.openai.tasks import sync_ai_pricing_from_litellm_task
from apps.integrations.openai.views import generated_at_now

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
            {"models": list_missing_pricing_models(), "generated_at": generated_at_now()}
        ).data
    )


def _pricing_error_response(exc: PricingError) -> Response:
    """400 for a bad request (backdating), 409 for a state conflict."""
    code = (
        status.HTTP_400_BAD_REQUEST
        if isinstance(exc, BackdatedPriceError)
        else status.HTTP_409_CONFLICT
    )
    return Response({"code": exc.code, "detail": exc.detail}, status=code)


class AiPricingListView(_AiPricingBaseView):
    """GET (read scope) and POST (write scope) /api/v1/superadmin/ai-pricing/ (Superadmin only)."""

    def get_throttles(self) -> list[Any]:
        self.throttle_scope = (
            "superadmin_ai_pricing_write"
            if self.request.method == "POST"
            else "superadmin_ai_pricing_read"
        )
        return super().get_throttles()

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

    @extend_schema(
        request=AiPriceCreateSerializer,
        responses={
            201: PriceRowSerializer,
            400: OpenApiResponse(description="Validation error or code=backdated"),
            409: OpenApiResponse(description="code=scheduled_price_exists or concurrent_change"),
            **PRICING_ERRORS,
        },
        tags=[PRICING_TAG],
    )
    def post(self, request: Request) -> Response:
        serializer = AiPriceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = add_price(**serializer.validated_data, actor=cast(User, request.user))
        except PricingError as exc:
            return _pricing_error_response(exc)
        except ValueError as exc:  # service rejects a blank model; the serializer normally does
            raise ValidationError({"model": ["This field may not be blank."]}) from exc
        data = PriceRowSerializer(row, context={"now": timezone.now()}).data
        return Response(data, status=status.HTTP_201_CREATED)


class AiPricingDetailView(_AiPricingBaseView):
    """DELETE /api/v1/superadmin/ai-pricing/<id>/ — remove a scheduled price (Superadmin only)."""

    throttle_scope = "superadmin_ai_pricing_write"

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Deleted"),
            404: OpenApiResponse(description="Unknown price"),
            409: OpenApiResponse(description="code=price_not_scheduled"),
            **PRICING_ERRORS,
        },
        tags=[PRICING_TAG],
    )
    def delete(self, request: Request, pk: int) -> Response:
        try:
            delete_scheduled_price(pricing_id=pk, actor=cast(User, request.user))
        except AiPricing.DoesNotExist as exc:
            raise NotFound from exc
        except PricingError as exc:
            return _pricing_error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    """GET /api/v1/superadmin/ai-pricing/missing/ (Superadmin only).

    Unpaginated by design: returns one bounded object (models used in the lookback window that
    lack a current price), not a growing collection.
    """

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


class AiPricingSyncStatusView(_AiPricingBaseView):
    """GET /api/v1/superadmin/ai-pricing/sync/status/ (Superadmin only)."""

    @extend_schema(
        responses={200: SyncStatusSerializer, **PRICING_ERRORS},
        tags=[PRICING_TAG],
    )
    def get(self, request: Request) -> Response:
        return Response(SyncStatusSerializer(get_sync_status()).data)


class AiPricingSyncToggleView(_AiPricingBaseView):
    """POST /api/v1/superadmin/ai-pricing/sync/toggle/ {enabled} (Superadmin only)."""

    throttle_scope = "superadmin_ai_pricing_write"

    @extend_schema(
        request=SyncToggleSerializer,
        responses={
            200: SyncStatusSerializer,
            400: OpenApiResponse(description="enabled must be a boolean"),
            **PRICING_ERRORS,
        },
        tags=[PRICING_TAG],
    )
    def post(self, request: Request) -> Response:
        serializer = SyncToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            set_sync_enabled(
                enabled=serializer.validated_data["enabled"], actor=cast(User, request.user)
            )
        return Response(SyncStatusSerializer(get_sync_status()).data)


class AiPricingSyncTriggerView(_AiPricingBaseView):
    """POST /api/v1/superadmin/ai-pricing/sync/trigger/ — "Sync Now" (1 per 15 min per user)."""

    throttle_classes = [SyncTriggerThrottle]  # noqa: RUF012

    @extend_schema(
        request=None,
        responses={202: SyncTriggerResponseSerializer, **PRICING_ERRORS},
        tags=[PRICING_TAG],
    )
    def post(self, request: Request) -> Response:
        transaction.on_commit(lambda: sync_ai_pricing_from_litellm_task.delay(force=True))
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)
