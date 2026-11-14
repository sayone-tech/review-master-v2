from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.insights.selectors import get_latest_insights


class InsightsBookApiView(APIView):
    permission_classes = [IsOrgAdmin]  # noqa: RUF012
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    throttle_scope = "insights"

    @extend_schema(responses={200: dict}, summary="Latest insights book for the organisation")
    def get(self, request: Request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        book = get_latest_insights(organisation_id=user.organisation_id)  # type: ignore[arg-type]
        if book is None:
            return Response({"cover": None, "window": None, "items": []})
        return Response(
            {
                "cover": book.cover,
                "window": {
                    "from": book.window_from.isoformat(),
                    "to": book.window_to.isoformat(),
                },
                "items": book.items,
            }
        )


@org_admin_required
def insights_page_view(request: HttpRequest) -> HttpResponse:
    return render(request, "insights/book.html", {"page_title": "Insights"})
