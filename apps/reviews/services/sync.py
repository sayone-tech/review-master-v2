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
from datetime import UTC, datetime
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
    clear_progress_snapshot,
    increment_google_token_bucket,
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
) -> tuple[int, set[str]]:
    """Upsert a page of reviews. Reset enrichment_status when text/rating changed.

    Returns (count_persisted, set_of_google_review_ids).
    """
    if not api_reviews:
        return 0, set()
    rows: list[Review] = []
    rev_ids: set[str] = set()
    for api_rev in api_reviews:
        norm = _normalise_review(api_rev, shop=shop)
        if not norm["google_review_id"]:
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

    return len(rows), rev_ids


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


def fetch_and_persist_reviews(*, shop_id: int, trigger: str = "incremental") -> dict[str, Any]:
    """Lock + paginate + upsert + soft-delete + audit.

    trigger: "initial" | "incremental" | "manual" — recorded in AuditLog payload.
    Returns a summary dict {"fetched": int, "soft_deleted": int, "duration_seconds": float}.
    """
    shop = Shop.objects.select_related("organisation").get(pk=shop_id)
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
        total_persisted = 0
        page_count = 0
        next_token = ""  # nosec B105 — not a password, it's a page cursor
        total_estimate: int | None = None

        try:
            while True:
                increment_google_token_bucket()
                page = list_reviews(
                    access_token=access_token,
                    account_name=shop.google_account_name,
                    location_name=shop.google_location_name,
                    page_token=next_token,
                )
                page_reviews = list(page.get("reviews") or [])
                total_estimate = int(page.get("totalReviewCount", total_estimate or 0))
                with transaction.atomic():
                    persisted, ids = _persist_page(shop=shop, api_reviews=page_reviews)
                total_persisted += persisted
                all_fetched_ids.update(ids)
                page_count += 1

                snapshot = {
                    "shop_id": shop_id,
                    "status": "fetching",
                    "fetched": total_persisted,
                    "total_estimate": total_estimate,
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
                        "total_estimate": total_estimate,
                    },
                )

                next_token = page.get("nextPageToken", "") or ""
                if not next_token:
                    break

            soft_deleted = _soft_delete_absent(shop=shop, fetched_ids=all_fetched_ids)
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
                    "total_enriched": 0,
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
