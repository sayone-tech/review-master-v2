"""Phase 11 — Google review sync service.

run_initial_backfill(shop_id) — paginate ALL historical reviews, persist each
                                 page, soft-delete absent on final page.
run_incremental_sync(shop_id) — same engine; called every 6 hours by Beat.

Both wrap fetch_and_persist_reviews which:
  1. Acquires per-shop Redis lock (lock:google_sync:shop:{shop_id}, 5min TTL)
  2. Refreshes access token from shop.google_refresh_token
  3. Pages through GBP list_reviews; bulk_creates with update_conflicts=True
  4. Resets enrichment_status to PENDING when comment/star_rating differs
  5. Soft-deletes reviews absent from the full fetched ID set
  6. Writes progress snapshots to Redis between pages
  7. Emits WebSocket events to sync-progress-{shop_id} group
  8. Writes AuditLog rows for sync.started, sync.completed/failed
  9. On 401 invalid_grant -> sets shop.connection_status = EXPIRED, halts
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.postgres.search import SearchVector
from django.db import connection, transaction
from django.utils import timezone as dj_timezone
from django.utils.dateparse import parse_datetime

from apps.common.locks import distributed_lock
from apps.common.models import AuditLog
from apps.integrations.google.exceptions import (
    GoogleAuthError,
    GoogleQuotaError,
    GoogleUnreachableError,
)
from apps.integrations.google.oauth import _refresh_access_token
from apps.integrations.google.reviews_client import list_reviews
from apps.reviews.models import Review
from apps.reviews.services.progress import (
    bulk_increment_enriched_counter,
    clear_progress_snapshot,
    increment_google_token_bucket,
    token_bucket_depleted,
    write_progress_snapshot,
)
from apps.shops.models import Shop

logger = logging.getLogger(__name__)

STAR_RATING_MAP = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
LOCK_KEY_TMPL = "lock:google_sync:shop:{shop_id}"
LOCK_TIMEOUT_SECONDS = 300


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _normalise_review(api_review: dict[str, Any], *, shop: Shop) -> dict[str, Any]:
    reviewer = api_review.get("reviewer") or {}
    reply = api_review.get("reviewReply") or {}
    rating_str = api_review.get("starRating", "")
    star_rating = STAR_RATING_MAP.get(str(rating_str).upper(), 0)
    return {
        "organisation_id": shop.organisation_id,
        "shop_id": shop.pk,
        "google_review_id": api_review.get("reviewId", ""),
        "google_account_id": shop.google_account_name,
        "google_location_id": shop.google_location_name,
        "star_rating": star_rating,
        "reviewer_display_name": str(reviewer.get("displayName", "") or ""),
        "reviewer_photo_url": str(reviewer.get("profilePhotoUrl", "") or ""),
        "reviewer_is_anonymous": bool(reviewer.get("isAnonymous", False)),
        "comment": str(api_review.get("comment", "") or ""),
        "review_create_time": _parse_dt(api_review.get("createTime")) or dj_timezone.now(),
        "review_update_time": _parse_dt(api_review.get("updateTime")) or dj_timezone.now(),
        "reply_comment": str(reply.get("comment", "") or ""),
        "reply_update_time": _parse_dt(reply.get("updateTime")),
        "is_replied": bool(reply.get("comment")),
    }


def emit_progress_event(*, shop_id: int, payload: dict[str, Any]) -> None:
    """Send a progress event to the SyncProgressConsumer group.

    Safe to call from Celery prefork workers — async_to_sync creates a new
    event loop per call. Must NOT be called inside transaction.atomic() — emit
    AFTER commit to avoid sending events for rolled-back state.
    """
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"sync-progress-{shop_id}",
        {"type": "progress.event", "payload": payload},
    )


def _persist_page(
    *,
    shop: Shop,
    api_reviews: list[dict[str, Any]],
    start_date: datetime | None = None,
) -> tuple[int, set[str], set[str]]:
    """Upsert a page of reviews. Reset enrichment_status when text/rating changed.

    Returns (count_persisted, set_of_google_review_ids, set_of_new_google_review_ids).
    The third element identifies google_review_ids that did NOT already exist for
    this shop — used by Phase 13-05 to dispatch one new_review Notification per
    genuinely new row (NOTF-02 / R4).
    """
    if not api_reviews:
        return 0, set(), set()
    rows: list[Review] = []
    rev_ids: set[str] = set()
    for api_rev in api_reviews:
        norm = _normalise_review(api_rev, shop=shop)
        if not norm["google_review_id"]:
            continue
        # Phase 15 — initial-backfill date filter (BKFL-01/02). Skipped rows are NOT
        # added to rev_ids, so _soft_delete_absent will purge previously-synced rows
        # that fall outside the new sync_depth window (intentional — see RESEARCH §Open Q1).
        if start_date is not None and norm["review_create_time"] < start_date:
            continue
        rev_ids.add(norm["google_review_id"])
        rows.append(Review(**norm))

    # Detect changes vs existing rows BEFORE upsert so enrichment can be reset
    existing = {
        r.google_review_id: r
        for r in Review.objects.filter(shop=shop, google_review_id__in=list(rev_ids)).only(
            "id", "google_review_id", "comment", "star_rating", "enrichment_status"
        )
    }
    # Phase 13-05 (R4): IDs in this page that don't exist in the DB are NEW
    # reviews. They drive one new_review Notification per eligible recipient
    # at the end of fetch_and_persist_reviews. Captured BEFORE the upsert.
    new_google_review_ids: set[str] = rev_ids - set(existing.keys())
    changed_ids: list[int] = []
    for row in rows:
        prev = existing.get(row.google_review_id)
        if prev and (prev.comment != row.comment or prev.star_rating != row.star_rating):
            changed_ids.append(prev.pk)

    update_fields = [
        "star_rating",
        "comment",
        "review_update_time",
        "reviewer_display_name",
        "reviewer_photo_url",
        "reviewer_is_anonymous",
        "reply_comment",
        "reply_update_time",
        "is_replied",
        "google_account_id",
        "google_location_id",
        "updated_at",
    ]
    Review.objects.bulk_create(
        rows,
        update_conflicts=True,
        update_fields=update_fields,
        unique_fields=["shop", "google_review_id"],
    )

    # RESEARCH.md Pitfall 3 — bulk_create skips DB triggers, so search_vector
    # remains NULL for newly inserted/updated rows. Without this update,
    # REVW-02 (keyword search) silently returns 0 results for all newly
    # fetched reviews. Run AFTER bulk_create so the new rows are visible.
    # Guard: SearchVector is PostgreSQL-only; SQLite test DB skips this step.
    if connection.vendor == "postgresql":
        Review.objects.filter(shop=shop, search_vector__isnull=True).update(
            search_vector=SearchVector("comment", "reviewer_display_name", config="english")
        )

    # Reset enrichment_status for changed rows (do NOT touch unchanged rows).
    if changed_ids:
        Review.objects.filter(pk__in=changed_ids).update(
            enrichment_status=Review.EnrichmentStatus.PENDING,
            sentiment="",
        )

    return len(new_google_review_ids), rev_ids, new_google_review_ids


_NEW_REVIEW_RECENCY_DAYS = 5


def _schedule_new_review_dispatch(*, shop: Shop, new_google_review_ids: set[str]) -> None:
    """Dispatch ONE summary new_review Notification per incremental sync run.

    Sends a single "X new reviews at <Shop>" notification rather than one per
    review. Initial backfill callers skip this entirely — the sync progress
    indicator already communicates that work.

    Only reviews whose review_create_time is within _NEW_REVIEW_RECENCY_DAYS
    are counted. Google occasionally re-surfaces old reviews (e.g. after a
    location merge) that are new-to-DB but were written years ago. Notifying
    on those creates a mismatch: the bell shows "1 new review at X" but
    Reports (filtered by review_create_time) shows nothing new.
    """
    from apps.notifications.services.dispatch import dispatch_notification

    if not new_google_review_ids:
        return

    # Filter: only notify for reviews whose create time is recent.
    recency_cutoff = dj_timezone.now() - timedelta(days=_NEW_REVIEW_RECENCY_DAYS)
    recent_count = Review.objects.filter(
        shop=shop,
        google_review_id__in=new_google_review_ids,
        review_create_time__gte=recency_cutoff,
    ).count()

    count = recent_count
    if count == 0:
        return

    # Fetch organisation_id from the shop itself — avoids a per-review query.
    org_id = shop.organisation_id
    shop_name = shop.name
    shop_pk = shop.pk
    title = f"1 new review at {shop_name}" if count == 1 else f"{count} new reviews at {shop_name}"
    target_url = f"/admin/org/reviews/?shop={shop_pk}"

    def _dispatch_summary() -> None:
        dispatch_notification(
            organisation_id=org_id,
            notification_type="new_review",
            title=title,
            target_url=target_url,
            shop=shop,
            review=None,
        )
        logger.info(
            "new_review_summary_notification_dispatched shop_id=%s count=%s",
            shop_pk,
            count,
        )

    transaction.on_commit(_dispatch_summary)


def _soft_delete_absent(*, shop: Shop, fetched_ids: set[str]) -> int:
    """Mark reviews absent from fetched_ids as deleted_at=now."""
    if not fetched_ids:
        return 0
    return int(
        Review.objects.filter(shop=shop, deleted_at__isnull=True)
        .exclude(google_review_id__in=fetched_ids)
        .update(deleted_at=dj_timezone.now())
    )


def _audit(*, shop: Shop, action: str, after: dict[str, Any] | None = None) -> None:
    AuditLog.objects.create(
        organisation_id=shop.organisation_id,
        actor=None,
        entity_type="shop_sync",
        entity_id=str(shop.pk),
        action=action,
        after_data=after,
    )


def fetch_and_persist_reviews(
    *,
    shop_id: int,
    trigger: str = "incremental",
    start_date: datetime | None = None,
) -> dict[str, Any]:
    """Lock + paginate + upsert + soft-delete + audit.

    trigger: "initial" | "incremental" | "manual" — recorded in AuditLog payload.
    Returns a summary dict {"fetched": int, "soft_deleted": int, "duration_seconds": float}.
    """
    shop = Shop.objects.select_related("organisation").get(pk=shop_id)
    # Phase 15 — derive date floor for initial backfill from shop.sync_depth.
    # Computed HERE (at execution time, not enqueue time) using the shop instance
    # already fetched above — no second DB query (RESEARCH §Pitfall 1, §Pitfall 2).
    if start_date is None:
        if shop.sync_depth == Shop.SyncDepth.ONE_YEAR:
            start_date = dj_timezone.now() - timedelta(days=365)
        elif shop.sync_depth == Shop.SyncDepth.TWO_YEARS:
            start_date = dj_timezone.now() - timedelta(days=730)
        # ALL_TIME → start_date stays None (no filter)
    if shop.connection_status == Shop.ConnectionStatus.EXPIRED:
        return {"fetched": 0, "soft_deleted": 0, "duration_seconds": 0, "skipped": "expired"}

    started_at = dj_timezone.now()
    lock_key = LOCK_KEY_TMPL.format(shop_id=shop_id)

    with distributed_lock(lock_key, timeout=LOCK_TIMEOUT_SECONDS) as acquired:
        if not acquired:
            return {"fetched": 0, "soft_deleted": 0, "duration_seconds": 0, "skipped": "locked"}

        clear_progress_snapshot(shop_id=shop_id)
        write_progress_snapshot(
            shop_id=shop_id,
            data={
                "shop_id": shop_id,
                "status": "fetching",
                "fetched": 0,
                "total_estimate": None,
                "enriched": 0,
                "started_at": started_at.isoformat(),
                "last_update_at": started_at.isoformat(),
                "page_count": 0,
            },
        )
        _audit(shop=shop, action="sync.started", after={"trigger": trigger})

        try:
            access_token = _refresh_access_token(shop.google_refresh_token or "")
        except GoogleAuthError as exc:
            if exc.reason == "invalid_grant":
                Shop.objects.filter(pk=shop_id).update(
                    connection_status=Shop.ConnectionStatus.EXPIRED
                )
                write_progress_snapshot(
                    shop_id=shop_id,
                    data={
                        "shop_id": shop_id,
                        "status": "failed",
                        "error_code": "invalid_grant",
                        "error_message": "Google connection expired.",
                    },
                )
                emit_progress_event(
                    shop_id=shop_id,
                    payload={
                        "type": "sync.error",
                        "shop_id": shop_id,
                        "stage": "auth",
                        "error_code": "invalid_grant",
                        "error_message": "Google connection expired.",
                    },
                )
                _audit(
                    shop=shop,
                    action="sync.failed",
                    after={"trigger": trigger, "error": "invalid_grant"},
                )
                return {
                    "fetched": 0,
                    "soft_deleted": 0,
                    "duration_seconds": 0,
                    "skipped": "invalid_grant",
                }
            raise

        all_fetched_ids: set[str] = set()
        # Phase 13-05 (R4 / NOTF-02): accumulate genuinely-new google_review_ids
        # across pages so we can dispatch one new_review Notification per new
        # row at the end (batched per shop sync, post-commit).
        all_new_google_ids: set[str] = set()
        total_persisted = 0
        page_count = 0
        next_token = ""  # nosec B105 — not a password, it's a page cursor
        total_estimate: int | None = None

        try:
            while True:
                if token_bucket_depleted():
                    logger.warning(
                        "google_token_bucket_depleted shop_id=%s page_count=%s — "
                        "halting pagination; next Beat tick will retry",
                        shop_id,
                        page_count,
                    )
                    break
                increment_google_token_bucket()
                page = list_reviews(
                    access_token=access_token,
                    account_name=shop.google_account_name,
                    location_name=shop.google_location_name,
                    page_token=next_token,
                )
                page_reviews = list(page.get("reviews") or [])
                total_estimate = int(page.get("totalReviewCount", total_estimate or 0))
                # When syncing a date-bounded window (start_date is set), Google's
                # totalReviewCount is the all-time count — it will never match the
                # number of reviews actually fetched. Suppress it from the progress
                # display so the UI shows "N fetched" without a misleading denominator.
                # ALL_TIME syncs (start_date is None) keep the full estimate.
                progress_total: int | None = None if start_date is not None else total_estimate
                with transaction.atomic():
                    persisted, ids, new_ids = _persist_page(
                        shop=shop, api_reviews=page_reviews, start_date=start_date
                    )
                total_persisted += persisted
                all_fetched_ids.update(ids)
                all_new_google_ids.update(new_ids)
                page_count += 1

                AuditLog.objects.create(
                    organisation_id=shop.organisation_id,
                    actor=None,
                    entity_type="review",
                    entity_id=str(shop.pk),
                    action="review.fetched",
                    after_data={
                        "page": page_count,
                        "count": persisted,
                        "trigger": trigger,
                    },
                )

                # ENRCH-02: enqueue enrichment for PENDING reviews; bulk-advance
                # the enriched counter for already-SUCCESS reviews without
                # dispatching tasks (avoids flooding ai-enrichment queue with
                # no-op idempotent tasks when a shop is re-synced after a
                # previous full enrichment run).
                if ids:
                    from apps.reviews.tasks import enrich_review_task

                    page_statuses = list(
                        Review.objects.filter(
                            shop=shop,
                            google_review_id__in=ids,
                            deleted_at__isnull=True,
                        ).values_list("id", "enrichment_status")
                    )
                    pending_ids = [
                        r_id
                        for r_id, status in page_statuses
                        if status == Review.EnrichmentStatus.PENDING
                    ]
                    already_enriched = sum(
                        1
                        for _, status in page_statuses
                        if status == Review.EnrichmentStatus.SUCCESS
                    )
                    for review_id in pending_ids:
                        enrich_review_task.delay(review_id)
                    if already_enriched:
                        bulk_increment_enriched_counter(shop_id=shop_id, count=already_enriched)

                snapshot = {
                    "shop_id": shop_id,
                    "status": "fetching",
                    "fetched": total_persisted,
                    "total_estimate": progress_total,
                    "enriched": 0,
                    "started_at": started_at.isoformat(),
                    "last_update_at": dj_timezone.now().isoformat(),
                    "page_count": page_count,
                }
                write_progress_snapshot(shop_id=shop_id, data=snapshot)
                emit_progress_event(
                    shop_id=shop_id,
                    payload={
                        "type": "sync.fetch.progress",
                        "shop_id": shop_id,
                        "fetched": total_persisted,
                        "total_estimate": progress_total,
                    },
                )

                next_token = page.get("nextPageToken", "") or ""
                if not next_token:
                    break

            soft_deleted = _soft_delete_absent(shop=shop, fetched_ids=all_fetched_ids)

            # Dispatch a single summary new_review notification for incremental
            # syncs only. Initial backfill is already communicated via the
            # TopbarBell sync progress indicator — spamming 100+ per-review
            # notifications on first connect is unwanted.
            if all_new_google_ids and trigger != "initial":
                _schedule_new_review_dispatch(shop=shop, new_google_review_ids=all_new_google_ids)

            duration = (dj_timezone.now() - started_at).total_seconds()
            success_payload = {
                "shop_id": shop_id,
                "status": "success",
                "fetched": total_persisted,
                "total_estimate": total_estimate or total_persisted,
                "enriched": 0,
                "started_at": started_at.isoformat(),
                "last_update_at": dj_timezone.now().isoformat(),
                "duration_seconds": duration,
                "page_count": page_count,
            }
            write_progress_snapshot(shop_id=shop_id, data=success_payload)
            emit_progress_event(
                shop_id=shop_id,
                payload={
                    "type": "sync.complete",
                    "shop_id": shop_id,
                    "total_fetched": total_persisted,
                    "total_estimate": total_estimate or total_persisted,
                    "duration_seconds": duration,
                },
            )
            _audit(
                shop=shop,
                action="sync.completed",
                after={
                    "trigger": trigger,
                    "total_fetched": total_persisted,
                    "soft_deleted": soft_deleted,
                    "duration_seconds": duration,
                },
            )
            return {
                "fetched": total_persisted,
                "soft_deleted": soft_deleted,
                "duration_seconds": duration,
            }
        except (GoogleQuotaError, GoogleUnreachableError) as exc:
            error_code = "quota_exceeded" if isinstance(exc, GoogleQuotaError) else "unreachable"
            logger.error(
                "google_sync_failed shop_id=%s organisation_id=%s trigger=%s "
                "error_code=%s pages_completed=%s reviews_fetched_so_far=%s error=%s",
                shop_id,
                shop.organisation_id,
                trigger,
                error_code,
                page_count,
                total_persisted,
                exc,
                exc_info=True,
            )
            write_progress_snapshot(
                shop_id=shop_id,
                data={
                    "shop_id": shop_id,
                    "status": "failed",
                    "error_code": error_code,
                    "error_message": str(exc),
                },
            )
            emit_progress_event(
                shop_id=shop_id,
                payload={
                    "type": "sync.error",
                    "shop_id": shop_id,
                    "stage": "fetch",
                    "error_code": error_code,
                    "error_message": str(exc),
                },
            )
            _audit(
                shop=shop,
                action="sync.failed",
                after={"trigger": trigger, "error": error_code},
            )
            raise


def run_initial_backfill(*, shop_id: int) -> dict[str, Any]:
    """Initial backfill — same engine, trigger="initial"."""
    return fetch_and_persist_reviews(shop_id=shop_id, trigger="initial")


def run_incremental_sync(*, shop_id: int) -> dict[str, Any]:
    """6-hour incremental sync — same engine, trigger="incremental"."""
    return fetch_and_persist_reviews(shop_id=shop_id, trigger="incremental")
