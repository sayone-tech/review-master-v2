"""Read-only AI pricing selectors + missing-price (gap) detection (Phase 35).

"Current" price = row active now; "scheduled" = row with ``effective_from > now``
(by the one-open-row invariant it is the model's open row).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max, Q, QuerySet
from django.utils import timezone

from apps.integrations.openai.models import AiPricing, AiUsageLog

MISSING_CACHE_KEY = "ai_pricing:missing_models"
RECENT_USAGE_CACHE_KEY = "ai_pricing:recent_usage"


class MissingModel(TypedDict):
    model: str
    last_used_at: datetime | None
    configured: bool


class PriceSummaryRow(TypedDict):
    model: str
    current: AiPricing | None
    scheduled: AiPricing | None


class ModelSuggestion(TypedDict):
    model: str
    last_used_at: datetime | None
    has_price: bool


def _recent_usage(now: datetime, *, use_cache: bool = True) -> dict[str, datetime | None]:
    """model -> last usage time over the lookback window (one grouped query).

    Cached under ``RECENT_USAGE_CACHE_KEY`` (shared by gap detection and suggestions) and
    dropped together with the missing-models cache by ``services.pricing_cache``.
    """
    if use_cache:
        cached = cache.get(RECENT_USAGE_CACHE_KEY)
        if cached is not None:
            return dict(cached)
    since = now - timedelta(days=settings.AI_PRICING_LOOKBACK_DAYS)
    rows = (
        AiUsageLog.objects.filter(created_at__gte=since)
        .values("model")
        .annotate(last_used_at=Max("created_at"))
    )
    usage: dict[str, datetime | None] = {r["model"]: r["last_used_at"] for r in rows}
    if use_cache:
        cache.set(RECENT_USAGE_CACHE_KEY, usage, settings.AI_PRICING_MISSING_CACHE_TTL_SECONDS)
    return dict(usage)


def _priced_now(now: datetime, models: set[str]) -> set[str]:
    return set(
        AiPricing.objects.active_at(now).filter(model__in=models).values_list("model", flat=True)
    )


def _last_used_desc(item: tuple[str, datetime | None]) -> tuple[bool, float, str]:
    model, last = item
    return (last is None, -(last.timestamp() if last else 0.0), model)


def list_missing_pricing_models(
    *, now: datetime | None = None, use_cache: bool = True
) -> list[MissingModel]:
    """Models used recently (plus the configured one) with no price active now."""
    if use_cache:
        cached = cache.get(MISSING_CACHE_KEY)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
    now = now or timezone.now()
    usage = _recent_usage(now, use_cache=use_cache)
    configured = settings.OPENAI_MODEL
    usage.setdefault(configured, None)
    for free in settings.AI_PRICING_KNOWN_FREE_MODELS:
        usage.pop(free, None)
    priced = _priced_now(now, set(usage))
    missing: list[MissingModel] = [
        {"model": m, "last_used_at": last, "configured": m == configured}
        for m, last in sorted(
            ((m, last) for m, last in usage.items() if m not in priced), key=_last_used_desc
        )
    ]
    if use_cache:
        cache.set(MISSING_CACHE_KEY, missing, settings.AI_PRICING_MISSING_CACHE_TTL_SECONDS)
    return missing


def list_price_summary(*, now: datetime | None = None) -> list[PriceSummaryRow]:
    """One row per model with a current or scheduled price, sorted by model."""
    now = now or timezone.now()
    rows = AiPricing.objects.filter(
        Q(effective_from__gt=now) | Q(effective_to__isnull=True) | Q(effective_to__gt=now)
    ).select_related("created_by")
    by_model: dict[str, PriceSummaryRow] = {}
    for row in rows:
        entry = by_model.setdefault(
            row.model, {"model": row.model, "current": None, "scheduled": None}
        )
        if row.effective_from > now:
            entry["scheduled"] = row
        else:
            entry["current"] = row
    return [by_model[m] for m in sorted(by_model)]


def list_price_history(*, model: str) -> QuerySet[AiPricing]:
    return (
        AiPricing.objects.filter(model=model)
        .select_related("created_by")
        .order_by("effective_from", "pk")
    )


def list_model_suggestions(
    *, query: str = "", limit: int = 20, now: datetime | None = None
) -> list[ModelSuggestion]:
    """Distinct known model names for the add-price picker, unpriced first."""
    now = now or timezone.now()
    usage = _recent_usage(now)
    names = set(usage) | set(AiPricing.objects.values_list("model", flat=True).distinct())
    names.add(settings.OPENAI_MODEL)
    needle = query.strip().lower()
    if needle:
        names = {n for n in names if needle in n.lower()}
    priced = _priced_now(now, names)
    out: list[ModelSuggestion] = [
        {"model": n, "last_used_at": usage.get(n), "has_price": n in priced} for n in names
    ]
    unpriced = sorted(
        (s for s in out if not s["has_price"]),
        key=lambda s: _last_used_desc((s["model"], s["last_used_at"])),
    )
    rest = sorted((s for s in out if s["has_price"]), key=lambda s: s["model"])
    return (unpriced + rest)[:limit]
