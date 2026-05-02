"""Phase 11 — Sync service tests.

Mocks: list_reviews + _refresh_access_token + distributed_lock + Redis writes
       + channel_layer.group_send. No real Google calls; no real Redis required.
"""

from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import patch

import pytest

from apps.common.models import AuditLog
from apps.reviews.models import Review
from apps.reviews.services import sync as sync_mod
from apps.shops.models import Shop
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def patched_dependencies():
    """Patch list_reviews, _refresh_access_token, distributed_lock (acquired),
    Redis writes (write_progress_snapshot, increment_google_token_bucket),
    and emit_progress_event."""

    @contextlib.contextmanager
    def _lock(_key: str, timeout: int = 300):
        yield True

    with (
        patch.object(sync_mod, "_refresh_access_token", return_value="fake-token"),
        patch.object(sync_mod, "distributed_lock", _lock),
        patch.object(sync_mod, "write_progress_snapshot") as wps,
        patch.object(sync_mod, "clear_progress_snapshot"),
        patch.object(sync_mod, "increment_google_token_bucket") as bump,
        patch.object(sync_mod, "emit_progress_event"),
    ):
        yield {"write_progress_snapshot": wps, "increment_google_token_bucket": bump}


def _api_review(rid: str, comment: str = "Great!", rating: str = "FIVE") -> dict[str, Any]:
    return {
        "reviewId": rid,
        "starRating": rating,
        "comment": comment,
        "createTime": "2026-05-01T12:00:00Z",
        "updateTime": "2026-05-01T12:00:00Z",
        "reviewer": {"displayName": "Jane", "isAnonymous": False},
    }


def _make_shop() -> Shop:
    shop = ShopFactory(
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    return shop


def test_upsert_no_duplicates_on_repeat(patched_dependencies) -> None:
    shop = _make_shop()
    page = {"reviews": [_api_review("g-1"), _api_review("g-2")], "totalReviewCount": 2}
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.run_initial_backfill(shop_id=shop.pk)
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.run_incremental_sync(shop_id=shop.pk)
    assert Review.objects.filter(shop=shop).count() == 2


def test_changed_review_resets_enrichment(patched_dependencies) -> None:
    shop = _make_shop()
    page1 = {"reviews": [_api_review("g-1", comment="Old")], "totalReviewCount": 1}
    page2 = {"reviews": [_api_review("g-1", comment="New")], "totalReviewCount": 1}
    with patch.object(sync_mod, "list_reviews", return_value=page1):
        sync_mod.run_initial_backfill(shop_id=shop.pk)
    Review.objects.filter(shop=shop, google_review_id="g-1").update(
        enrichment_status=Review.EnrichmentStatus.SUCCESS, sentiment="positive"
    )
    with patch.object(sync_mod, "list_reviews", return_value=page2):
        sync_mod.run_incremental_sync(shop_id=shop.pk)
    r = Review.objects.get(shop=shop, google_review_id="g-1")
    assert r.comment == "New"
    assert r.enrichment_status == Review.EnrichmentStatus.PENDING


def test_soft_delete_missing_reviews(patched_dependencies) -> None:
    shop = _make_shop()
    page1 = {
        "reviews": [_api_review("g-1"), _api_review("g-2"), _api_review("g-3")],
        "totalReviewCount": 3,
    }
    with patch.object(sync_mod, "list_reviews", return_value=page1):
        sync_mod.run_initial_backfill(shop_id=shop.pk)
    page2 = {"reviews": [_api_review("g-1"), _api_review("g-2")], "totalReviewCount": 2}
    with patch.object(sync_mod, "list_reviews", return_value=page2):
        sync_mod.run_incremental_sync(shop_id=shop.pk)
    g3 = Review.objects.get(shop=shop, google_review_id="g-3")
    assert g3.deleted_at is not None


def test_401_invalid_grant_sets_shop_expired(patched_dependencies) -> None:
    from apps.integrations.google.exceptions import GoogleAuthError

    shop = _make_shop()
    with patch.object(
        sync_mod,
        "_refresh_access_token",
        side_effect=GoogleAuthError(reason="invalid_grant"),
    ):
        result = sync_mod.run_initial_backfill(shop_id=shop.pk)
    shop.refresh_from_db()
    assert shop.connection_status == Shop.ConnectionStatus.EXPIRED
    assert result.get("skipped") == "invalid_grant"


def test_lock_not_acquired_returns_skipped(patched_dependencies) -> None:
    @contextlib.contextmanager
    def _lock(_key: str, timeout: int = 300):
        yield False

    shop = _make_shop()
    with patch.object(sync_mod, "distributed_lock", _lock):
        result = sync_mod.run_incremental_sync(shop_id=shop.pk)
    assert result.get("skipped") == "locked"
    assert Review.objects.filter(shop=shop).count() == 0


def test_audit_log_started_and_completed(patched_dependencies) -> None:
    shop = _make_shop()
    page = {"reviews": [_api_review("g-1")], "totalReviewCount": 1}
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.run_initial_backfill(shop_id=shop.pk)
    actions = list(
        AuditLog.objects.filter(entity_type="shop_sync", entity_id=str(shop.pk)).values_list(
            "action", flat=True
        )
    )
    assert "sync.started" in actions
    assert "sync.completed" in actions


def test_token_bucket_incremented_per_page(patched_dependencies) -> None:
    shop = _make_shop()
    page1 = {"reviews": [_api_review("g-1")], "totalReviewCount": 2, "nextPageToken": "x"}
    page2 = {"reviews": [_api_review("g-2")], "totalReviewCount": 2}
    with patch.object(sync_mod, "list_reviews", side_effect=[page1, page2]):
        sync_mod.run_initial_backfill(shop_id=shop.pk)
    assert patched_dependencies["increment_google_token_bucket"].call_count == 2


def test_progress_snapshot_written_fetching_then_success(patched_dependencies) -> None:
    shop = _make_shop()
    page = {"reviews": [_api_review("g-1")], "totalReviewCount": 1}
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.run_initial_backfill(shop_id=shop.pk)
    write_calls = patched_dependencies["write_progress_snapshot"].call_args_list
    statuses = [c.kwargs["data"]["status"] for c in write_calls]
    assert "fetching" in statuses
    assert "success" in statuses


def test_search_vector_populated_after_persist_page(patched_dependencies) -> None:
    """RESEARCH.md Pitfall 3 — bulk_create skips DB triggers, so the sync
    service must explicitly populate search_vector after each page or REVW-02
    keyword search returns 0 results for all newly fetched reviews.

    Strategy: patch connection.vendor to "postgresql" so the guard lets the
    update through, then intercept the QuerySet.update call to avoid actual
    SearchVector SQL (which fails on SQLite). Verify the update was attempted
    with a search_vector argument.
    """
    from django.db.models.query import QuerySet

    from apps.reviews.services import sync as _sync

    shop = _make_shop()
    page = {
        "reviews": [
            _api_review("g-1", comment="Great food and service"),
            _api_review("g-2", comment="Loved the dessert"),
        ],
        "totalReviewCount": 2,
    }

    search_vector_update_calls: list[dict] = []
    original_qs_update = QuerySet.update

    def _intercepting_update(self, **kwargs):  # type: ignore[no-untyped-def]
        if "search_vector" in kwargs:
            search_vector_update_calls.append(kwargs)
            return 0  # skip real SearchVector SQL on SQLite
        return original_qs_update(self, **kwargs)

    with (
        patch.object(_sync, "list_reviews", return_value=page),
        patch.object(_sync.connection, "vendor", new="postgresql"),
        patch.object(QuerySet, "update", _intercepting_update),
    ):
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    assert search_vector_update_calls, (
        "search_vector update must be called when vendor=postgresql so REVW-02 "
        "keyword search works for newly fetched reviews (RESEARCH.md Pitfall 3)"
    )
    assert "search_vector" in search_vector_update_calls[0]
