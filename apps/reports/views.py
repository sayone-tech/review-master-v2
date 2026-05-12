from __future__ import annotations

from datetime import date, timedelta
from typing import cast

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.reports.selectors.store_report import ReportFilterParams, list_store_report

VALID_REPLY_STATUSES = {"replied", "not_replied"}
VALID_SENTIMENTS = {"positive", "neutral", "negative"}
PRESET_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}
MAX_RANGE_DAYS = 365


def _parse_date(raw: str | None, *, field: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({field: "Invalid ISO date (YYYY-MM-DD)."}) from exc


def _resolve_dates(
    range_key: str | None,
    raw_from: str | None,
    raw_to: str | None,
) -> tuple[date | None, date | None]:
    today = timezone.now().date()
    if range_key in PRESET_DAYS:
        days = PRESET_DAYS[range_key]
        return today - timedelta(days=days), today
    if range_key == "custom":
        d_from = _parse_date(raw_from, field="from")
        d_to = _parse_date(raw_to, field="to")
        if d_from is None or d_to is None:
            raise ValidationError({"detail": "Custom range requires both from and to."})
        if d_from > d_to:
            raise ValidationError({"detail": "End date must be after start date."})
        if (d_to - d_from).days > MAX_RANGE_DAYS:
            raise ValidationError({"detail": "Date range cannot exceed 365 days."})
        return d_from, d_to
    if range_key is not None:
        raise ValidationError(
            {"range": f"Invalid range '{range_key}'. Use 7d, 30d, 90d, or custom."}
        )
    return None, None


def _validate_params(request: Request) -> ReportFilterParams:
    qp = request.query_params
    range_key = qp.get("range") or None
    reply_status = qp.get("reply_status") or None
    sentiment = qp.get("sentiment") or None

    if reply_status is not None and reply_status not in VALID_REPLY_STATUSES:
        raise ValidationError({"reply_status": "Must be 'replied' or 'not_replied'."})
    if sentiment is not None and sentiment not in VALID_SENTIMENTS:
        raise ValidationError({"sentiment": "Must be 'positive', 'neutral', or 'negative'."})

    date_from, date_to = _resolve_dates(range_key, qp.get("from"), qp.get("to"))
    return ReportFilterParams(
        date_from=date_from,
        date_to=date_to,
        reply_status=reply_status,
        sentiment=sentiment,
    )


class StoreReportApiView(APIView):
    permission_classes = [IsOrgAdmin]  # noqa: RUF012

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        params = _validate_params(request)
        rows = list_store_report(org_id=user.organisation_id, params=params)  # type: ignore[arg-type]
        return Response(rows)


@org_admin_required
def reports_page_view(request: HttpRequest) -> HttpResponse:
    return render(request, "reports/store_report.html", {})
