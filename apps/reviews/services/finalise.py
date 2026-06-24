"""Phase 23 — Canonical tag finalising pass service (SEED-04, Step 4).

run_finalise_canonical_tags(organisation_id, shop_id) — dedup + backfill + count-refresh.

Implements decisions:
  D-05: duplicate = case-insensitive Title-Case label match, no fuzzy/semantic
  D-06: merge winner = higher review_count, tie -> earliest created_at; keep winner's polarity_type
  D-07: backfill null canonical_tag stragglers + refresh review_count cache on tag-merge queue

Three-layer idempotency (CLAUDE.md §12.4):
  Layer 1: per-org Redis lock (lock:tag_merge:org:{org_id}, 5-min TTL)
  Layer 2: transaction.atomic() + select_for_update on OrgCanonicalTag candidates
  Layer 3: early-return when lock not acquired (another worker holds it)

FK re-point uses a single bulk UPDATE per loser — no N+1 (CLAUDE.md §6.10).
review_count refreshed from a single aggregate query + bulk_update — never inline (D-03).
Progress events emitted AFTER the atomic block commits (RESEARCH.md anti-pattern guard).
"""

from __future__ import annotations

import logging
import time as _time
from typing import Any

from django.db import transaction
from django.db.models import Count

from apps.common.locks import distributed_lock
from apps.reviews.models import OrgCanonicalTag, ReviewTag
from apps.reviews.selectors.canonical_tags import (
    get_duplicate_canonical_tag_groups,
    get_null_straggler_review_tags,
)
from apps.reviews.services.progress import read_progress_snapshot, write_progress_snapshot
from apps.reviews.services.sync import emit_progress_event

logger = logging.getLogger(__name__)

LOCK_KEY_TMPL = "lock:tag_merge:org:{organisation_id}"
LOCK_TIMEOUT_SECONDS = 300

# Bounded backfill batch size (T-23-05: unbounded straggler scans are DoS risk)
STRAGGLER_BATCH_SIZE = 500


def run_finalise_canonical_tags(*, organisation_id: int, shop_id: int) -> dict[str, Any]:
    """Dedup canonical tags, backfill stragglers, refresh review_count cache.

    Returns a dict with summary counters. Returns ``{"skipped": True}`` when
    the per-org Redis lock is already held by another worker.

    Thread-safety: per-org distributed lock prevents two concurrent finalising
    or Phase-25 merge tasks from colliding on the same org (T-23-04).
    """
    lock_key = LOCK_KEY_TMPL.format(organisation_id=organisation_id)
    with distributed_lock(lock_key, timeout=LOCK_TIMEOUT_SECONDS) as acquired:
        if not acquired:
            logger.info(
                "run_finalise_canonical_tags.lock_held organisation_id=%s shop_id=%s",
                organisation_id,
                shop_id,
            )
            return {"skipped": True}

        return _run_finalise(organisation_id=organisation_id, shop_id=shop_id)


def _run_finalise(*, organisation_id: int, shop_id: int) -> dict[str, Any]:
    """Inner finalising logic — called only when the distributed lock is held."""
    _finalise_start = _time.monotonic()
    merged_groups = 0
    stragglers_backfilled = 0

    # -------------------------------------------------------------------
    # Emit finalising.progress snapshot (step = finalising)
    # -------------------------------------------------------------------
    # Preserve the accumulated fetched/enriched counts from the prior snapshot.
    # Writing a bare dict here wipes them, which then zeroes the fetched/enriched
    # values read back for the sync.complete totals below — surfacing as "N of 0"
    # in the progress UI and a "0 reviews" completion screen.
    prior = read_progress_snapshot(shop_id=shop_id) or {}
    write_progress_snapshot(
        shop_id=shop_id,
        data={
            **prior,
            "shop_id": shop_id,
            "status": "finalising",
            "step": "finalising",
            "last_update_at": _now_iso(),
        },
    )
    emit_progress_event(
        shop_id=shop_id,
        payload={
            "type": "sync.finalising.progress",
            "shop_id": shop_id,
            "processed": 0,
            "total": None,
        },
    )

    # -------------------------------------------------------------------
    # Step 1 — Resolve duplicate groups (D-05, D-06)
    # -------------------------------------------------------------------
    duplicate_groups = get_duplicate_canonical_tag_groups(organisation_id=organisation_id)

    for lower_label in duplicate_groups:
        _merge_group(
            organisation_id=organisation_id,
            lower_label=lower_label,
        )
        merged_groups += 1

    # -------------------------------------------------------------------
    # Step 2 — Backfill null straggler ReviewTags (D-07)
    # -------------------------------------------------------------------
    stragglers_backfilled = _backfill_stragglers(
        organisation_id=organisation_id,
    )

    # -------------------------------------------------------------------
    # Step 3 — Refresh review_count from aggregate (D-03/D-07)
    # Must run AFTER merges so counts reflect the post-merge state.
    # -------------------------------------------------------------------
    _refresh_review_counts(organisation_id=organisation_id)

    # -------------------------------------------------------------------
    # Emit sync.complete AFTER all mutations are committed (CR-01)
    # -------------------------------------------------------------------
    # Read accumulated counters from the Redis snapshot — these carry fetched
    # and enriched counts that were written by sync.py / enrichment.py.
    snap = read_progress_snapshot(shop_id=shop_id) or {}
    total_fetched = int(snap.get("fetched", 0))
    total_enriched = int(snap.get("enriched", 0))
    duration_seconds = round(_time.monotonic() - _finalise_start, 1)

    write_progress_snapshot(
        shop_id=shop_id,
        data={
            "shop_id": shop_id,
            "status": "success",
            "fetched": total_fetched,
            "enriched": total_enriched,
            "duration_seconds": duration_seconds,
            "last_update_at": _now_iso(),
        },
    )
    emit_progress_event(
        shop_id=shop_id,
        payload={
            "type": "sync.finalising.progress",
            "shop_id": shop_id,
            "processed": merged_groups,
            "total": merged_groups,
        },
    )
    emit_progress_event(
        shop_id=shop_id,
        payload={
            "type": "sync.complete",
            "shop_id": shop_id,
            "total_fetched": total_fetched,
            "total_enriched": total_enriched,
            "duration_seconds": duration_seconds,
            "merged_groups": merged_groups,
            "stragglers_backfilled": stragglers_backfilled,
        },
    )

    # Dispatch consolidated notifications (CR-02): "N action items found" + "N reviews synced".
    # Must be called AFTER sync.complete is emitted so the UI transitions before notifications
    # fire (belt-and-suspenders ordering).
    if total_fetched > 0:
        from apps.reviews.services.enrichment import (
            _dispatch_sync_complete_notifications,
        )

        _dispatch_sync_complete_notifications(
            shop_id=shop_id,
            organisation_id=organisation_id,
            total_fetched=total_fetched,
        )

    logger.info(
        "run_finalise_canonical_tags.done organisation_id=%s shop_id=%s "
        "merged_groups=%s stragglers_backfilled=%s",
        organisation_id,
        shop_id,
        merged_groups,
        stragglers_backfilled,
    )
    return {
        "organisation_id": organisation_id,
        "shop_id": shop_id,
        "merged_groups": merged_groups,
        "stragglers_backfilled": stragglers_backfilled,
    }


def _merge_group(*, organisation_id: int, lower_label: str) -> None:
    """Collapse all OrgCanonicalTag rows with label iexact=lower_label to one winner.

    Runs inside transaction.atomic() with select_for_update() on the candidates.
    Winner = row with highest review_count; tie broken by earliest created_at (D-06).
    Loser's ReviewTag FKs are re-pointed in a single UPDATE (no N+1 — CLAUDE.md §6.10).
    Loser rows are hard-deleted after the FK re-point.
    """
    with transaction.atomic():
        # select_for_update prevents concurrent modifications (T-23-04)
        candidates = list(
            OrgCanonicalTag.objects.select_for_update()
            .filter(
                organisation_id=organisation_id,
                label__iexact=lower_label,
            )
            .order_by("-review_count", "created_at")
        )
        if len(candidates) < 2:
            # Another worker may have already merged this group — idempotent skip
            return

        winner = candidates[0]
        losers = candidates[1:]

        for loser in losers:
            # Re-point all ReviewTag FKs in ONE UPDATE (no N+1 — CLAUDE.md §6.10)
            ReviewTag.objects.filter(canonical_tag=loser).update(canonical_tag=winner)
            loser.delete()

        # WR-04: log inside the atomic block where winner/losers are guaranteed in-scope.
        logger.debug(
            "_merge_group organisation_id=%s lower_label=%r winner_id=%s losers=%s",
            organisation_id,
            lower_label,
            winner.pk,
            [loser_row.pk for loser_row in losers],
        )


def _backfill_stragglers(*, organisation_id: int) -> int:
    """Assign canonical_tag FK to ReviewTag rows that have null canonical_tag.

    Matches by case-insensitive label against the post-merge org vocabulary.
    Operates in a bounded batch (STRAGGLER_BATCH_SIZE) to prevent DoS risk (T-23-05).
    Returns the number of ReviewTag rows updated.
    """
    # Build a lower-case lookup map from the current (post-merge) vocabulary
    vocab_map: dict[str, int] = {
        label.lower(): pk
        for pk, label in OrgCanonicalTag.objects.filter(
            organisation_id=organisation_id
        ).values_list("id", "label")
    }
    if not vocab_map:
        return 0

    stragglers = list(
        get_null_straggler_review_tags(
            organisation_id=organisation_id,
            limit=STRAGGLER_BATCH_SIZE,
        )
    )
    if not stragglers:
        return 0

    # CR-03: group by canonical_tag_id and issue one UPDATE per group, not per row
    # (CLAUDE.md §6 N+1 is a blocker-level bug; §6.10 use bulk UPDATE).
    from collections import defaultdict

    groups: dict[int, list[int]] = defaultdict(list)
    for rt in stragglers:
        canonical_id = vocab_map.get(rt.label.lower())
        if canonical_id is not None:
            groups[canonical_id].append(rt.pk)

    updated = 0
    with transaction.atomic():
        for canonical_id, pk_list in groups.items():
            cnt = ReviewTag.objects.filter(pk__in=pk_list).update(canonical_tag_id=canonical_id)
            updated += cnt

    logger.debug(
        "_backfill_stragglers organisation_id=%s total_stragglers=%s updated=%s",
        organisation_id,
        len(stragglers),
        updated,
    )
    return updated


def _refresh_review_counts(*, organisation_id: int) -> None:
    """Refresh OrgCanonicalTag.review_count from a single aggregate query.

    D-03/D-07: review_count is a DENORMALIZED CACHE — NEVER incremented inline.
    It is derived here from the ReviewTag aggregate, then written back via
    bulk_update() in a single round-trip (CLAUDE.md §6.10).
    """
    # One aggregate query: ReviewTag -> canonical_tag_id -> count
    counts = (
        ReviewTag.objects.filter(canonical_tag__organisation_id=organisation_id)
        .values("canonical_tag_id")
        .annotate(cnt=Count("id"))
    )
    count_map: dict[int, int] = {row["canonical_tag_id"]: row["cnt"] for row in counts}

    tags_to_update = []
    for tag in OrgCanonicalTag.objects.filter(organisation_id=organisation_id):
        tag.review_count = count_map.get(tag.pk, 0)
        tags_to_update.append(tag)

    if tags_to_update:
        OrgCanonicalTag.objects.bulk_update(tags_to_update, ["review_count"])

    logger.debug(
        "_refresh_review_counts organisation_id=%s tags_updated=%s",
        organisation_id,
        len(tags_to_update),
    )


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    from django.utils import timezone as dj_timezone

    return dj_timezone.now().isoformat()
