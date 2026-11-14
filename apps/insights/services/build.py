"""Rank rule candidates and store one InsightSnapshot per organisation per day."""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.insights.models import InsightSnapshot
from apps.insights.services import rules
from apps.insights.services.rules import Candidate
from apps.insights.services.windows import Window, review_window_q, windows_for
from apps.reviews.models import Review
from apps.shops.models import Shop

MAX_INSIGHTS = 8
MAX_PER_TYPE = 2
RETENTION_DAYS = 14
# "Waiting for a reply" (2) and "complaint rising" (1) lead; then "store below brand" (3).
TYPE_WEIGHTS = {2: 1.3, 1: 1.2, 3: 1.1}

RULE_FUNCTIONS = (
    rules.complaint_rising,
    rules.waiting_negative,
    rules.store_below_brand,
    rules.five_star_share_change,
    rules.reply_rate_change,
    rules.best_month,
    rules.new_tag,
    rules.volume_drop,
)


def collect_candidates(*, organisation_id: int, window: Window) -> list[Candidate]:
    out: list[Candidate] = []
    for rule in RULE_FUNCTIONS:
        out.extend(rule(organisation_id=organisation_id, window=window))
    return out


def _sort_key(c: Candidate) -> tuple[int, float, int]:
    weighted = c.score * TYPE_WEIGHTS.get(c.type, 1.0)
    return (0 if c.chapter == "attention" else 1, -weighted, -c.review_count)


def rank(candidates: list[Candidate]) -> list[Candidate]:
    """Attention first, then weighted score desc, ties by more reviews; max 2 per type, 8 total."""
    per_type: dict[int, int] = {}
    out: list[Candidate] = []
    for c in sorted(candidates, key=_sort_key):
        if per_type.get(c.type, 0) >= MAX_PER_TYPE:
            continue
        per_type[c.type] = per_type.get(c.type, 0) + 1
        out.append(c)
        if len(out) == MAX_INSIGHTS:
            break
    return out


@transaction.atomic
def build_snapshot(*, organisation_id: int, today: dt.date) -> InsightSnapshot:
    window = windows_for(today)
    items = rank(collect_candidates(organisation_id=organisation_id, window=window))
    payload: dict[str, Any] = {
        "cover": {
            "reviews": Review.objects.filter(
                review_window_q(window.now_from, window.now_to),
                organisation_id=organisation_id,
                deleted_at__isnull=True,
                shop__is_active=True,
            ).count(),
            "stores": Shop.objects.filter(organisation_id=organisation_id, is_active=True).count(),
            "attention": sum(1 for c in items if c.chapter == "attention"),
            "good": sum(1 for c in items if c.chapter == "good"),
        },
        "items": [dataclasses.asdict(c) for c in items],
    }
    snapshot, _ = InsightSnapshot.objects.update_or_create(
        organisation_id=organisation_id,
        computed_for=today,
        defaults={
            "window_from": window.before_from,
            "window_to": window.now_to,
            "payload": payload,
        },
    )
    InsightSnapshot.objects.filter(
        organisation_id=organisation_id,
        computed_for__lt=today - dt.timedelta(days=RETENTION_DAYS),
    ).delete()
    return snapshot


def compute_all_insights() -> int:
    """Build today's (UTC) snapshot for every organisation with an active shop; returns the count."""
    today = timezone.now().date()
    org_ids = (
        Shop.objects.filter(is_active=True)
        .order_by("organisation_id")
        .values_list("organisation_id", flat=True)
        .distinct()
    )
    count = 0
    for org_id in org_ids:
        build_snapshot(organisation_id=org_id, today=today)
        count += 1
    return count
