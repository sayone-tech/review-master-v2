"""Superadmin credit endpoints (CSUP-01, CSUP-02).

Non-tenant, Superadmin-only views: ``IsAuthenticated`` + ``IsSuperadmin`` and a scoped throttle
on each. Views validate, call a service and shape the response; no business logic here.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsSuperadmin
from apps.credits.exceptions import PeriodMismatchError, ShopNotAvailableError
from apps.credits.serializers import (
    BonusAllocationSerializer,
    BonusResultSerializer,
    CreditBalanceSnapshotSerializer,
    CreditErrorSerializer,
    PeriodMismatchResponseSerializer,
)
from apps.credits.services.bonus import allocate_bonus
from apps.credits.services.periods import Period


class BonusAllocationView(APIView):
    """POST /api/v1/superadmin/shops/{shop_id}/credits/bonus/ (Superadmin only)."""

    permission_classes = [IsAuthenticated, IsSuperadmin]  # noqa: RUF012
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    throttle_scope = "superadmin_credits_write"

    @extend_schema(
        request=BonusAllocationSerializer,
        responses={
            201: BonusResultSerializer,
            400: OpenApiResponse(description="Field validation errors"),
            403: OpenApiResponse(description="Superadmin role required"),
            404: CreditErrorSerializer,
            409: PeriodMismatchResponseSerializer,
            429: OpenApiResponse(description="Throttled"),
        },
        tags=["superadmin-credits"],
    )
    def post(self, request: Request, shop_id: int) -> Response:
        serializer = BonusAllocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = allocate_bonus(
                shop_id=shop_id,
                amount=data["amount"],
                reason=data["reason"] or None,
                period=Period(data["period_year"], data["period_month"]),
                actor_id=request.user.pk,
            )
        except PeriodMismatchError as exc:
            return Response(
                {
                    "code": "period_mismatch",
                    "detail": "A new month started. Reload the balance and try again.",
                    "period": {"year": exc.current.year, "month": exc.current.month},
                    "balance": CreditBalanceSnapshotSerializer(exc.balance).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except ShopNotAvailableError:
            return Response(
                {"code": "shop_unavailable", "detail": "This shop is no longer active."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(BonusResultSerializer(result).data, status=status.HTTP_201_CREATED)
