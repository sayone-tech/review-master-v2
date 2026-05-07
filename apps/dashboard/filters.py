from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.reviews.selectors.reviews import get_accessible_shop_ids

MAX_RANGE_DAYS = 365
DEFAULT_RANGE_DAYS = 30
PRESET_DAYS = {"7d": 7, "30d": 30, "90d": 90}


@dataclass(frozen=True)
class DashboardFilterParams:
    region_id: int | None
    shop_id: int | None
    date_from: date | None
    date_to: date | None
    accessible_shop_ids: tuple[int, ...]

    def filter_hash(self) -> str:
        payload = {
            "region_id": self.region_id,
            "shop_id": self.shop_id,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "shop_ids": list(self.accessible_shop_ids),
        }
        blob = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


def _parse_int(raw: str | None) -> int | None:
    if raw in (None, "", "null"):
        return None
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValidationError({"detail": "Invalid integer parameter."}) from exc


def _parse_date(raw: str | None, *, field: str) -> date | None:
    if raw in (None, "", "null"):
        return None
    try:
        return date.fromisoformat(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValidationError({field: "Invalid ISO date (expected YYYY-MM-DD)."}) from exc


def _resolve_date_window(
    *,
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
    # Default: last 30 days
    return today - timedelta(days=DEFAULT_RANGE_DAYS), today


def _get_all_org_shop_ids(org_id: int) -> list[int]:
    from apps.shops.models import Shop

    return sorted(
        Shop.objects.filter(organisation_id=org_id, is_active=True).values_list("id", flat=True)
    )


def validate_filter_params(*, request: Any, user: Any, org_id: int) -> DashboardFilterParams:
    from apps.accounts.models import User

    # ORG_ADMIN can access all shops in the org; STAFF_ADMIN is scoped via StaffAccessScope.
    if user.role == User.Role.STAFF_ADMIN:
        accessible_shop_ids = tuple(get_accessible_shop_ids(user_id=user.id))
    else:
        accessible_shop_ids = tuple(_get_all_org_shop_ids(org_id))
    params = request.query_params if hasattr(request, "query_params") else request.GET

    region_id = _parse_int(params.get("region"))
    shop_id = _parse_int(params.get("store"))
    range_key = params.get("range") or "30d"
    date_from, date_to = _resolve_date_window(
        range_key=range_key,
        raw_from=params.get("from"),
        raw_to=params.get("to"),
    )

    if shop_id is not None and shop_id not in accessible_shop_ids:
        raise PermissionDenied("Selected store is not accessible.")

    if region_id is not None:
        from apps.shops.models import Shop

        region_shop_ids = set(
            Shop.objects.filter(
                organisation_id=org_id,
                region_id=region_id,
                id__in=accessible_shop_ids,
            ).values_list("id", flat=True)
        )
        if not region_shop_ids:
            raise PermissionDenied("Selected region is not accessible.")

    return DashboardFilterParams(
        region_id=region_id,
        shop_id=shop_id,
        date_from=date_from,
        date_to=date_to,
        accessible_shop_ids=accessible_shop_ids,
    )
