"""Read side of the Insights book: latest snapshot with names resolved (never writes)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from apps.insights.models import InsightSnapshot
from apps.shops.models import Shop

ALL_STORES = "All stores"


@dataclass(frozen=True)
class InsightsBook:
    cover: dict[str, Any]
    window_from: dt.date
    window_to: dt.date
    items: list[dict[str, Any]]


def _fill(text: str, *, store: str, tag: str) -> str:
    return text.replace("{store}", store).replace("{tag_lower}", tag.lower()).replace("{tag}", tag)


def get_latest_insights(*, organisation_id: int) -> InsightsBook | None:
    snapshot = (
        InsightSnapshot.objects.select_related("organisation")
        .filter(organisation_id=organisation_id)
        .order_by("-computed_for")
        .first()
    )
    if snapshot is None:
        return None
    payload = snapshot.payload or {}
    shops = dict(
        Shop.objects.filter(organisation_id=organisation_id, is_active=True).values_list(
            "id", "name"
        )
    )
    items: list[dict[str, Any]] = []
    for raw in payload.get("items", []):
        store_id = raw.get("store_id")
        if store_id is not None and store_id not in shops:
            continue
        store = shops[store_id] if store_id is not None else ALL_STORES
        tag = raw.get("tag_text") or ""
        item = {key: raw[key] for key in ("type", "chapter", "headline", "visual", "link", "cta")}
        for key in ("title", "body", "caption"):
            item[key] = _fill(raw[key], store=store, tag=tag)
        item["store"] = store
        items.append(item)
    if not items:
        return None
    cover = {
        "organisation": snapshot.organisation.name,
        "reviews": payload.get("cover", {}).get("reviews", 0),
        "stores": payload.get("cover", {}).get("stores", 0),
        "attention": sum(1 for i in items if i["chapter"] == "attention"),
        "good": sum(1 for i in items if i["chapter"] == "good"),
    }
    return InsightsBook(
        cover=cover, window_from=snapshot.window_from, window_to=snapshot.window_to, items=items
    )
