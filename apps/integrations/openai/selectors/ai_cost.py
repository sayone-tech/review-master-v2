"""Read-only AI cost aggregates for the Superadmin AI Cost Explorer (Phase 34).

Cost and token totals sum ``SUCCESS`` rows only; call counts include every status.
Windows are start-inclusive / end-exclusive (``CostWindow``).

Cost sums are quantized to six decimal places in Python (SQLite, used in tests,
stores decimals as REAL). ``get_cost_summary`` and ``get_request_type_costs``
quantize before returning; ``list_org_costs`` returns a lazy ``values()``
QuerySet (so views can sort/paginate it) whose ``cost`` is the raw database
Decimal -- callers must pass it through ``quantize_cost`` when serializing.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any, TypedDict

from django.db.models import Count, F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError

from apps.integrations.openai.cost_window import CostWindow
from apps.integrations.openai.models import AiUsageLog

COST_QUANT = Decimal("0.000001")
SUCCESS = Q(status=AiUsageLog.Status.SUCCESS)

# API sort key -> annotation name on the org-list rows.
ORG_SORT_FIELDS: dict[str, str] = {
    "name": "name",
    "active_shops": "active_shops",
    "calls": "calls",
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cost": "cost",
}

# API sort key -> annotation name on the shop-list rows.
SHOP_SORT_FIELDS: dict[str, str] = {
    "name": "name",
    "calls": "calls",
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cost": "cost",
}


class CostTotals(TypedDict):
    calls: int
    success_calls: int
    failed_calls: int
    moderated_calls: int
    input_tokens: int
    output_tokens: int
    cost: Decimal


class CostSummary(CostTotals):
    org_count: int
    active_shops: int


def quantize_cost(value: Decimal | float | int) -> Decimal:
    return Decimal(value).quantize(COST_QUANT)


def _in_window(window: CostWindow) -> Q:
    return Q(created_at__gte=window.start, created_at__lt=window.end)


def get_cost_summary(*, window: CostWindow, organisation_id: int | None = None) -> CostSummary:
    qs = AiUsageLog.objects.filter(_in_window(window))
    if organisation_id is not None:
        qs = qs.filter(organisation_id=organisation_id)
    row = qs.order_by().aggregate(
        calls=Count("id"),
        success_calls=Count("id", filter=SUCCESS),
        failed_calls=Count("id", filter=Q(status=AiUsageLog.Status.FAILED)),
        moderated_calls=Count("id", filter=Q(status=AiUsageLog.Status.MODERATED)),
        input_tokens=Coalesce(Sum("prompt_tokens", filter=SUCCESS), 0),
        output_tokens=Coalesce(Sum("completion_tokens", filter=SUCCESS), 0),
        cost=Coalesce(Sum("estimated_cost_usd", filter=SUCCESS), Decimal("0")),
        org_count=Count("organisation_id", distinct=True),
        active_shops=Count("review__shop_id", filter=SUCCESS, distinct=True),
    )
    return CostSummary(
        calls=row["calls"],
        success_calls=row["success_calls"],
        failed_calls=row["failed_calls"],
        moderated_calls=row["moderated_calls"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        cost=quantize_cost(row["cost"]),
        org_count=row["org_count"],
        active_shops=row["active_shops"],
    )


def list_org_costs(*, window: CostWindow, sort: str = "-cost") -> QuerySet[Any]:
    """One row per organisation with at least one call in the window (any status)."""
    field = ORG_SORT_FIELDS.get(sort.lstrip("-"))
    if field is None:
        raise ValidationError({"detail": f"Unsupported sort '{sort}'."})
    ordering = f"-{field}" if sort.startswith("-") else field
    return (
        AiUsageLog.objects.filter(_in_window(window))
        .order_by()
        .values("organisation_id")
        .annotate(
            name=F("organisation__name"),
            org_type=F("organisation__org_type"),
            active_shops=Count("review__shop_id", filter=SUCCESS, distinct=True),
            calls=Count("id"),
            input_tokens=Coalesce(Sum("prompt_tokens", filter=SUCCESS), 0),
            output_tokens=Coalesce(Sum("completion_tokens", filter=SUCCESS), 0),
            cost=Coalesce(Sum("estimated_cost_usd", filter=SUCCESS), Decimal("0")),
        )
        .order_by(ordering, "organisation_id")
    )


def get_request_type_costs(
    *, window: CostWindow, organisation_ids: Sequence[int]
) -> dict[int, dict[str, Decimal]]:
    rows = (
        AiUsageLog.objects.filter(
            _in_window(window), SUCCESS, organisation_id__in=list(organisation_ids)
        )
        .order_by()
        .values("organisation_id", "request_type")
        .annotate(cost=Sum("estimated_cost_usd"))
    )
    result: dict[int, dict[str, Decimal]] = {}
    for r in rows:
        result.setdefault(r["organisation_id"], {})[r["request_type"]] = quantize_cost(r["cost"])
    return result


class UnattributedCosts(CostTotals):
    by_request_type: dict[str, Decimal]


def list_shop_costs(
    *, window: CostWindow, organisation_id: int, sort: str = "-cost"
) -> QuerySet[Any]:
    """One row per shop of the org with a review-linked call in the window.

    ``cost`` is the raw database Decimal; callers must ``quantize_cost`` it.
    """
    field = SHOP_SORT_FIELDS.get(sort.removeprefix("-"))
    if field is None:
        raise ValidationError({"detail": f"Unsupported sort '{sort}'."})
    ordering = f"-{field}" if sort.startswith("-") else field
    return (
        AiUsageLog.objects.filter(
            _in_window(window), organisation_id=organisation_id, review__isnull=False
        )
        .order_by()
        .values(shop_id=F("review__shop_id"))
        .annotate(
            name=F("review__shop__name"),
            region_name=F("review__shop__region__name"),
            calls=Count("id"),
            input_tokens=Coalesce(Sum("prompt_tokens", filter=SUCCESS), 0),
            output_tokens=Coalesce(Sum("completion_tokens", filter=SUCCESS), 0),
            cost=Coalesce(Sum("estimated_cost_usd", filter=SUCCESS), Decimal("0")),
        )
        .order_by(ordering, "shop_id")
    )


def get_shop_request_type_costs(
    *, window: CostWindow, organisation_id: int, shop_ids: Sequence[int]
) -> dict[int, dict[str, Decimal]]:
    rows = (
        AiUsageLog.objects.filter(
            _in_window(window),
            SUCCESS,
            organisation_id=organisation_id,
            review__shop_id__in=list(shop_ids),
        )
        .order_by()
        .values(shop_id=F("review__shop_id"), req_type=F("request_type"))
        .annotate(cost=Sum("estimated_cost_usd"))
    )
    result: dict[int, dict[str, Decimal]] = {}
    for r in rows:
        result.setdefault(r["shop_id"], {})[r["req_type"]] = quantize_cost(r["cost"])
    return result


def get_unattributed_costs(*, window: CostWindow, organisation_id: int) -> UnattributedCosts | None:
    """Totals for calls with no review (so no shop); None when there are none."""
    base = AiUsageLog.objects.filter(
        _in_window(window), organisation_id=organisation_id, review__isnull=True
    ).order_by()
    row = base.aggregate(
        calls=Count("id"),
        success_calls=Count("id", filter=SUCCESS),
        failed_calls=Count("id", filter=Q(status=AiUsageLog.Status.FAILED)),
        moderated_calls=Count("id", filter=Q(status=AiUsageLog.Status.MODERATED)),
        input_tokens=Coalesce(Sum("prompt_tokens", filter=SUCCESS), 0),
        output_tokens=Coalesce(Sum("completion_tokens", filter=SUCCESS), 0),
        cost=Coalesce(Sum("estimated_cost_usd", filter=SUCCESS), Decimal("0")),
    )
    if row["calls"] == 0:
        return None
    by_type = {
        r["request_type"]: quantize_cost(r["cost"])
        for r in base.filter(SUCCESS)
        .values("request_type")
        .annotate(cost=Sum("estimated_cost_usd"))
    }
    return UnattributedCosts(
        calls=row["calls"],
        success_calls=row["success_calls"],
        failed_calls=row["failed_calls"],
        moderated_calls=row["moderated_calls"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        cost=quantize_cost(row["cost"]),
        by_request_type=by_type,
    )


def list_model_costs(*, window: CostWindow, organisation_id: int) -> list[dict[str, Any]]:
    rows = (
        AiUsageLog.objects.filter(_in_window(window), organisation_id=organisation_id)
        .order_by()
        .values("model")
        .annotate(
            calls=Count("id"),
            input_tokens=Coalesce(Sum("prompt_tokens", filter=SUCCESS), 0),
            output_tokens=Coalesce(Sum("completion_tokens", filter=SUCCESS), 0),
            cost=Coalesce(Sum("estimated_cost_usd", filter=SUCCESS), Decimal("0")),
        )
    )
    result = [{**r, "cost": quantize_cost(r["cost"])} for r in rows]
    result.sort(key=lambda r: (-r["cost"], r["model"]))
    return result
