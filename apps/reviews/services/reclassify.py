"""Phase 24 — Weekly polarity auto-reclassification service (POL-02, POL-03).

run_polarity_reclassification() — global no-N+1 aggregate that flips
always_positive / always_negative OrgCanonicalTag rows to mixed when the
opposite polarity exceeds the configured threshold over the trailing window.

Decisions implemented:
  D-01: one-way, sticky — only always_positive / always_negative are candidates;
        mixed tags NEVER re-enter evaluation.
  D-02: numerator = opposite polarity only; denominator = ALL polarities incl.
        neutral; flip condition is ratio > threshold (strict >) AND
        denominator >= POLARITY_RECLASSIFY_MIN_REVIEWS.
  D-03: window by Review.review_create_time; soft-deleted excluded.
  D-05: idempotent — mixed tags are excluded so a second run writes nothing.
  D-06: one AuditLog row per flip (entity_type canonical_tag,
        action polarity_reclassified, actor None, before/after_data).

No-N+1 (CLAUDE.md §6): the aggregate is ONE grouped query over ReviewTag
grouped by (canonical_tag_id, polarity) — never a per-tag loop.

Org scoping (§9/§22): organisation_id derives structurally from the tag FK.
No GPT, Redis, or WebSocket usage.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.common.models import AuditLog
from apps.reviews.models import OrgCanonicalTag, ReviewTag

logger = logging.getLogger(__name__)


def run_polarity_reclassification() -> dict[str, Any]:
    """Aggregate ReviewTag polarity per canonical tag and flip qualifying tags.

    Returns a dict with keys:
        flipped           — number of tags flipped to mixed this run
        skipped_low_sample — tags with denominator < MIN_REVIEWS
        evaluated         — total candidate tags examined (always_* only)
    """
    threshold: float = settings.POLARITY_RECLASSIFY_THRESHOLD
    window_days: int = settings.POLARITY_RECLASSIFY_WINDOW_DAYS
    min_reviews: int = settings.POLARITY_RECLASSIFY_MIN_REVIEWS

    cutoff = timezone.now() - timedelta(days=window_days)

    # Fetch ALL candidate tags (always_positive + always_negative only — D-01).
    # mixed tags are pre-filtered; they never appear in this queryset (sticky).
    candidates = list(
        OrgCanonicalTag.objects.filter(
            polarity_type__in=[
                OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE,
                OrgCanonicalTag.PolarityType.ALWAYS_NEGATIVE,
            ]
        ).only("id", "organisation_id", "polarity_type")
    )

    if not candidates:
        logger.info("run_polarity_reclassification.done flipped=0 skipped_low_sample=0 evaluated=0")
        return {"flipped": 0, "skipped_low_sample": 0, "evaluated": 0}

    candidate_map: dict[int, OrgCanonicalTag] = {tag.pk: tag for tag in candidates}

    # ONE grouped aggregate query — no per-tag loop (CLAUDE.md §6, §6.9).
    # Joins ReviewTag -> Review filtered by window + not soft-deleted.
    # Groups by (canonical_tag_id, polarity) and counts rows.
    rows = (
        ReviewTag.objects.filter(
            canonical_tag_id__in=candidate_map.keys(),
            review__review_create_time__gte=cutoff,
            review__deleted_at__isnull=True,
        )
        .values("canonical_tag_id", "polarity")
        .annotate(cnt=Count("id"))
    )

    # Group aggregate rows in Python into by_tag[tag_id][polarity] = cnt
    by_tag: dict[int, dict[str, int]] = defaultdict(dict)
    for row in rows:
        by_tag[row["canonical_tag_id"]][row["polarity"]] = row["cnt"]

    # Evaluate each candidate against threshold + min-sample guard (D-02)
    to_flip: list[tuple[OrgCanonicalTag, float, int]] = []  # (tag, ratio, reviews_in_window)
    skipped_low_sample = 0

    for tag_id, tag in candidate_map.items():
        counts = by_tag.get(tag_id, {})
        total = sum(counts.values())  # denominator = ALL polarities incl. neutral

        if total < min_reviews:
            skipped_low_sample += 1
            continue

        # Numerator = opposite polarity only (D-02)
        if tag.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE:
            opposite = "negative"
        else:
            opposite = "positive"

        opposite_count = counts.get(opposite, 0)
        ratio = opposite_count / total

        # Strict > (not >=): exactly 0.15 does NOT flip (D-02)
        if ratio > threshold:
            to_flip.append((tag, ratio, total))

    evaluated = len(candidate_map)
    flipped = len(to_flip)

    if to_flip:
        _flip_and_audit(to_flip=to_flip, window_days=window_days)

    logger.info(
        "run_polarity_reclassification.done flipped=%s skipped_low_sample=%s evaluated=%s",
        flipped,
        skipped_low_sample,
        evaluated,
    )
    return {
        "flipped": flipped,
        "skipped_low_sample": skipped_low_sample,
        "evaluated": evaluated,
    }


@transaction.atomic
def _flip_and_audit(
    *,
    to_flip: list[tuple[OrgCanonicalTag, float, int]],
    window_days: int,
) -> None:
    """Atomically flip qualifying tags to mixed and write one AuditLog per flip.

    Runs inside transaction.atomic() so tag state and audit row are always
    consistent — partial-write rollback is impossible (T-24-06).

    bulk_update field list is exactly ["polarity_type", "polarity_reclassified_at"]
    — review_count is intentionally excluded (D-03, T-24-08).
    """
    now = timezone.now()
    tags_to_update: list[OrgCanonicalTag] = []
    audit_rows: list[AuditLog] = []

    for tag, opposite_ratio, reviews_in_window in to_flip:
        old_polarity = tag.polarity_type

        tag.polarity_type = OrgCanonicalTag.PolarityType.MIXED
        tag.polarity_reclassified_at = now
        tags_to_update.append(tag)

        audit_rows.append(
            AuditLog(
                organisation_id=tag.organisation_id,  # structural FK — never a parameter (§9)
                actor=None,  # system event (D-06)
                entity_type="canonical_tag",
                entity_id=str(tag.pk),
                action="polarity_reclassified",
                before_data={"polarity_type": old_polarity},
                after_data={
                    "polarity_type": "mixed",
                    "opposite_ratio": round(opposite_ratio, 6),
                    "window_days": window_days,
                    "reviews_in_window": reviews_in_window,
                },
            )
        )

    # Single bulk_update — field list MUST exclude review_count (D-03, Pitfall 2)
    OrgCanonicalTag.objects.bulk_update(
        tags_to_update, ["polarity_type", "polarity_reclassified_at"]
    )
    AuditLog.objects.bulk_create(audit_rows)
