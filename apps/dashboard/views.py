from __future__ import annotations

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.permissions import IsOrgScoped
from apps.dashboard.filters import DashboardFilterParams, validate_filter_params
from apps.dashboard.selectors.aggregations import (
    dashboard_highlights,
    dashboard_kpis,
    dashboard_sentiment_distribution,
    dashboard_top_performing,
    dashboard_your_store,
)
from apps.dashboard.services.cache import (
    DASHBOARD_TTL_SECONDS,
    cache_get,
    cache_set,
    dashboard_cache_key,
)


class DashboardApiView(APIView):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    endpoint_name: str = ""

    def get(self, request: Request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        org_id: int = user.organisation_id  # type: ignore[assignment]
        params: DashboardFilterParams = validate_filter_params(
            request=request,
            user=user,
            org_id=org_id,
        )
        key = dashboard_cache_key(
            endpoint=self.endpoint_name,
            org_id=org_id,
            user_id=int(user.pk),
            params=params,
        )
        cached = cache_get(key)
        if cached is not None:
            return Response(cached)
        data = self._fetch(org_id=org_id, params=params, user=user)
        if data is None:
            data = {}
        cache_set(key, data, ttl=DASHBOARD_TTL_SECONDS)
        return Response(data)

    def _fetch(
        self, *, org_id: int, params: DashboardFilterParams, user: User
    ) -> dict[str, Any] | None:
        raise NotImplementedError


class KpisView(DashboardApiView):
    endpoint_name = "kpis"

    def _fetch(
        self, *, org_id: int, params: DashboardFilterParams, user: User
    ) -> dict[str, Any] | None:
        return dashboard_kpis(org_id=org_id, params=params)


class SentimentView(DashboardApiView):
    endpoint_name = "sentiment-distribution"

    def _fetch(
        self, *, org_id: int, params: DashboardFilterParams, user: User
    ) -> dict[str, Any] | None:
        return dashboard_sentiment_distribution(org_id=org_id, params=params)


class TopPerformingView(DashboardApiView):
    endpoint_name = "top-performing"

    def _fetch(
        self, *, org_id: int, params: DashboardFilterParams, user: User
    ) -> dict[str, Any] | None:
        return dashboard_top_performing(org_id=org_id, params=params)


class HighlightsView(DashboardApiView):
    endpoint_name = "highlights"

    def _fetch(
        self, *, org_id: int, params: DashboardFilterParams, user: User
    ) -> dict[str, Any] | None:
        return dashboard_highlights(org_id=org_id, params=params)


class YourStoreView(DashboardApiView):
    endpoint_name = "your-store"

    def _fetch(
        self, *, org_id: int, params: DashboardFilterParams, user: User
    ) -> dict[str, Any] | None:
        return dashboard_your_store(org_id=org_id, params=params)
