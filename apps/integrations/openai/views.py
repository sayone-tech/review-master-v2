"""Superadmin AI Cost Explorer endpoints (Phase 34): platform summary and organisation list.

Non-tenant: ``IsAuthenticated`` + ``IsSuperadmin`` and a scoped throttle. Views validate, call
selectors and shape the response; payloads are cached for ``CACHE_TTL`` seconds.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsSuperadmin
from apps.common.pagination import DefaultPageNumberPagination
from apps.integrations.openai.cost_window import resolve_cost_window
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.selectors.ai_cost import (
    get_cost_summary,
    get_request_type_costs,
    get_shop_request_type_costs,
    get_unattributed_costs,
    list_model_costs,
    list_org_costs,
    list_shop_costs,
    quantize_cost,
)
from apps.integrations.openai.serializers import (
    CostSummaryResponseSerializer,
    ModelCostListResponseSerializer,
    OrgCostListResponseSerializer,
    OrgCostRowSerializer,
    OrgSummaryResponseSerializer,
    ShopCostListResponseSerializer,
    ShopCostRowSerializer,
    UnattributedCostSerializer,
)
from apps.organisations.models import Organisation

CACHE_TTL = 600
TAG = "superadmin-ai-cost"

RANGE_PARAMS = [
    OpenApiParameter(
        "range",
        str,
        enum=["this_month", "last_month", "7d", "30d", "90d", "custom"],
        description="Date range (UTC); default this_month",
    ),
    OpenApiParameter("from", str, description="YYYY-MM-DD, required when range=custom"),
    OpenApiParameter("to", str, description="YYYY-MM-DD, required when range=custom"),
]


def _cached(endpoint: str, request: Request, build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Return the cached payload for this URL + window, building and storing it on a miss.

    ``build`` runs only on a miss, so validation errors it raises are never cached. The
    window's ``cache_hash`` is folded into the key so rolling ranges change keys each minute.
    """
    window = resolve_cost_window(params=request.query_params)
    raw = f"{request.get_full_path()}|{window.cache_hash()}"
    digest = hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()
    key = f"admin:ai_cost:{endpoint}:{digest}"
    payload: dict[str, Any] | None = cache.get(key)
    if payload is None:
        payload = build()
        cache.set(key, payload, CACHE_TTL)
    return payload


class _AiCostBaseView(APIView):
    permission_classes = [IsAuthenticated, IsSuperadmin]  # noqa: RUF012
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    throttle_scope = "superadmin_ai_cost_read"


class AiCostSummaryView(_AiCostBaseView):
    """GET /api/v1/superadmin/ai-cost/summary/ (Superadmin only)."""

    @extend_schema(
        parameters=RANGE_PARAMS,
        responses={
            200: CostSummaryResponseSerializer,
            400: OpenApiResponse(description="Invalid date range"),
            403: OpenApiResponse(description="Superadmin role required"),
            429: OpenApiResponse(description="Throttled"),
        },
        tags=[TAG],
    )
    def get(self, request: Request) -> Response:
        def build() -> dict[str, Any]:
            window = resolve_cost_window(params=request.query_params)
            return dict(
                CostSummaryResponseSerializer(
                    {
                        "range": {
                            "key": window.range_key,
                            "start": window.start,
                            "end": window.end,
                        },
                        "generated_at": timezone.now(),
                        "has_any_usage": AiUsageLog.objects.exists(),
                        "totals": get_cost_summary(window=window),
                    }
                ).data
            )

        return Response(_cached("summary", request, build))


class AiCostOrganisationListView(_AiCostBaseView):
    """GET /api/v1/superadmin/ai-cost/organisations/ (Superadmin only)."""

    @extend_schema(
        parameters=[
            *RANGE_PARAMS,
            OpenApiParameter(
                "sort",
                str,
                description="name|active_shops|calls|input_tokens|output_tokens|cost, "
                "prefix '-' for descending (default -cost)",
            ),
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Rows per page (default 25, max 100)"),
        ],
        responses={
            200: OrgCostListResponseSerializer,
            400: OpenApiResponse(description="Invalid date range or sort"),
            403: OpenApiResponse(description="Superadmin role required"),
            429: OpenApiResponse(description="Throttled"),
        },
        tags=[TAG],
    )
    def get(self, request: Request) -> Response:
        def build() -> dict[str, Any]:
            window = resolve_cost_window(params=request.query_params)
            # Validates ``sort`` eagerly, before any pagination query runs.
            rows = list_org_costs(window=window, sort=request.query_params.get("sort") or "-cost")
            paginator = DefaultPageNumberPagination()
            page = paginator.paginate_queryset(rows, request, view=self) or []
            by_type = get_request_type_costs(
                window=window, organisation_ids=[r["organisation_id"] for r in page]
            )
            results = [
                {
                    **r,
                    "cost": quantize_cost(r["cost"]),
                    "by_request_type": by_type.get(r["organisation_id"], {}),
                }
                for r in page
            ]
            body = paginator.get_paginated_response(
                OrgCostRowSerializer(results, many=True).data
            ).data
            return {**body, "generated_at": timezone.now().isoformat()}

        return Response(_cached("organisations", request, build))


def _generated_at() -> str:
    return str(serializers.DateTimeField().to_representation(timezone.now()))


def _get_org(org_id: int) -> Organisation:
    """The org with its total shop count; 404 (never cached, as it raises) when unknown."""
    org: Organisation | None = (
        Organisation.objects.annotate(shop_count=Count("shops")).filter(pk=org_id).first()
    )
    if org is None:
        raise NotFound({"code": "organisation_not_found", "detail": "Organisation not found."})
    return org


ORG_ERRORS = {
    403: OpenApiResponse(description="Superadmin role required"),
    404: OpenApiResponse(description="Organisation not found"),
    429: OpenApiResponse(description="Throttled"),
}


class AiCostOrgSummaryView(_AiCostBaseView):
    """GET /api/v1/superadmin/ai-cost/organisations/<org_id>/summary/ (Superadmin only)."""

    @extend_schema(
        parameters=RANGE_PARAMS,
        responses={
            200: OrgSummaryResponseSerializer,
            400: OpenApiResponse(description="Invalid date range"),
            **ORG_ERRORS,
        },
        tags=[TAG],
    )
    def get(self, request: Request, org_id: int) -> Response:
        def build() -> dict[str, Any]:
            window = resolve_cost_window(params=request.query_params)
            org = _get_org(org_id)
            return dict(
                OrgSummaryResponseSerializer(
                    {
                        "organisation": {
                            "id": org.id,
                            "name": org.name,
                            "org_type": org.org_type,
                            "shop_count": org.shop_count,  # type: ignore[attr-defined]
                        },
                        "range": {
                            "key": window.range_key,
                            "start": window.start,
                            "end": window.end,
                        },
                        "generated_at": timezone.now(),
                        "totals": get_cost_summary(window=window, organisation_id=org.id),
                    }
                ).data
            )

        return Response(_cached("org-summary", request, build))


class AiCostOrgShopsView(_AiCostBaseView):
    """GET /api/v1/superadmin/ai-cost/organisations/<org_id>/shops/ (Superadmin only)."""

    @extend_schema(
        parameters=[
            *RANGE_PARAMS,
            OpenApiParameter(
                "sort",
                str,
                description="name|region_name|calls|input_tokens|output_tokens|cost, "
                "prefix '-' for descending (default -cost)",
            ),
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Rows per page (default 25, max 100)"),
        ],
        responses={
            200: ShopCostListResponseSerializer,
            400: OpenApiResponse(description="Invalid date range or sort"),
            **ORG_ERRORS,
        },
        tags=[TAG],
    )
    def get(self, request: Request, org_id: int) -> Response:
        def build() -> dict[str, Any]:
            window = resolve_cost_window(params=request.query_params)
            org = _get_org(org_id)
            # Validates ``sort`` eagerly, before any pagination query runs.
            rows = list_shop_costs(
                window=window,
                organisation_id=org.id,
                sort=request.query_params.get("sort") or "-cost",
            )
            paginator = DefaultPageNumberPagination()
            page = paginator.paginate_queryset(rows, request, view=self) or []
            by_type = get_shop_request_type_costs(
                window=window, organisation_id=org.id, shop_ids=[r["shop_id"] for r in page]
            )
            results = [
                {
                    **r,
                    "cost": quantize_cost(r["cost"]),
                    "by_request_type": by_type.get(r["shop_id"], {}),
                }
                for r in page
            ]
            body = paginator.get_paginated_response(
                ShopCostRowSerializer(results, many=True).data
            ).data
            unattributed = get_unattributed_costs(window=window, organisation_id=org.id)
            return {
                **body,
                "unattributed": (
                    dict(UnattributedCostSerializer(unattributed).data) if unattributed else None
                ),
                "generated_at": _generated_at(),
            }

        return Response(_cached("org-shops", request, build))


class AiCostOrgModelsView(_AiCostBaseView):
    """GET /api/v1/superadmin/ai-cost/organisations/<org_id>/models/ (Superadmin only)."""

    @extend_schema(
        parameters=RANGE_PARAMS,
        responses={
            200: ModelCostListResponseSerializer,
            400: OpenApiResponse(description="Invalid date range"),
            **ORG_ERRORS,
        },
        tags=[TAG],
    )
    def get(self, request: Request, org_id: int) -> Response:
        def build() -> dict[str, Any]:
            window = resolve_cost_window(params=request.query_params)
            org = _get_org(org_id)
            return dict(
                ModelCostListResponseSerializer(
                    {
                        "results": list_model_costs(window=window, organisation_id=org.id),
                        "generated_at": timezone.now(),
                    }
                ).data
            )

        return Response(_cached("org-models", request, build))
