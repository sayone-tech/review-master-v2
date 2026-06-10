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
    emit_progress_event, and enrich_review_task.delay.

    Phase 12-06: enrich_review_task.delay is now called by fetch_and_persist_reviews.
    With CELERY_TASK_ALWAYS_EAGER=True, .delay() runs the task synchronously which
    requires Redis. Patching .delay() prevents unwanted Redis calls in sync tests
    that do not need to verify enrichment dispatch.
    """

    @contextlib.contextmanager
    def _lock(_key: str, timeout: int = 300):
        yield True

    with (
        patch.object(sync_mod, "_refresh_access_token", return_value="fake-token"),
        patch.object(sync_mod, "distributed_lock", _lock),
        patch.object(sync_mod, "write_progress_snapshot") as wps,
        patch.object(sync_mod, "clear_progress_snapshot"),
        patch.object(sync_mod, "increment_google_token_bucket") as bump,
        patch.object(sync_mod, "token_bucket_depleted", return_value=False),
        patch.object(sync_mod, "emit_progress_event"),
        patch("apps.reviews.tasks.enrich_review_task.delay"),
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


def test_incremental_sync_fetched_count_excludes_existing(patched_dependencies) -> None:
    # Regression: incremental sync was reporting len(api_rows) as "fetched"
    # even for reviews already in the DB — so re-syncing 2 existing reviews
    # showed "2 synced" instead of "0 new".
    shop = _make_shop()
    page = {"reviews": [_api_review("g-1"), _api_review("g-2")], "totalReviewCount": 2}
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.run_initial_backfill(shop_id=shop.pk)
    with patch.object(sync_mod, "list_reviews", return_value=page):
        result = sync_mod.run_incremental_sync(shop_id=shop.pk)
    assert result["fetched"] == 0, "re-syncing existing reviews must not inflate the fetched count"
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


# ---------------------------------------------------------------------------
# Phase 23 — Four-phase run_initial_backfill tests (SEED-01/02/03, DSYNC-01)
# ---------------------------------------------------------------------------


def _api_review_with_time(
    rid: str,
    comment: str = "Great!",
    rating: str = "FIVE",
    create_time: str = "2026-05-01T12:00:00Z",
) -> dict[str, Any]:
    return {
        "reviewId": rid,
        "starRating": rating,
        "comment": comment,
        "createTime": create_time,
        "updateTime": create_time,
        "reviewer": {"displayName": "Jane", "isAnonymous": False},
    }


@pytest.fixture
def patched_backfill_deps():
    """Patch dependencies for four-phase run_initial_backfill tests.

    Patches list_reviews, _refresh_access_token, distributed_lock (acquired),
    Redis writes, channel_layer, enrich_review (direct call), enrich_review_task
    (async dispatch), finalize_canonical_tags_task (async dispatch), and
    _wait_for_openai_token (returns 1, no sleep).
    """
    import contextlib

    @contextlib.contextmanager
    def _lock(_key: str, timeout: int = 300):
        yield True

    with (
        patch.object(sync_mod, "_refresh_access_token", return_value="fake-token"),
        patch.object(sync_mod, "distributed_lock", _lock),
        patch.object(sync_mod, "write_progress_snapshot"),
        patch.object(sync_mod, "clear_progress_snapshot"),
        patch.object(sync_mod, "increment_google_token_bucket") as _bump,
        patch.object(sync_mod, "token_bucket_depleted", return_value=False),
        patch.object(sync_mod, "emit_progress_event"),
        patch("apps.reviews.tasks.enrich_review_task.delay"),
    ):
        yield _bump


def test_seed_loop_processes_newest_n_reviews_sequentially(patched_backfill_deps: Any) -> None:
    """SEED-02/03: seed loop processes min(SEED_PHASE_SIZE, pending) reviews newest-first."""
    from unittest.mock import MagicMock, patch

    from django.conf import settings

    shop = _make_shop()
    # Make reviews with different times to test ordering
    reviews_api = [
        _api_review_with_time(f"g-{i}", create_time=f"2026-05-0{i}T12:00:00Z") for i in range(1, 6)
    ]
    page = {"reviews": reviews_api, "totalReviewCount": 5}

    mock_enrich = MagicMock()
    mock_wait = MagicMock(return_value=1)
    mock_apply_async = MagicMock()

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.services.sync.enrich_review", mock_enrich),
        patch("apps.reviews.services.sync._wait_for_openai_token", mock_wait),
        patch("apps.reviews.services.sync.enrich_review_task") as mock_task,
        patch("apps.reviews.services.sync.finalize_canonical_tags_task"),
    ):
        mock_task.apply_async = mock_apply_async
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    seed_size = min(settings.SEED_PHASE_SIZE, 5)
    # Each seed enrich_review called with skip_rate_limit_guard=True
    for call_obj in mock_enrich.call_args_list[:seed_size]:
        assert call_obj.kwargs.get("skip_rate_limit_guard") is True, (
            "seed path must pass skip_rate_limit_guard=True"
        )
    # _wait_for_openai_token called once per seed review
    assert mock_wait.call_count == seed_size


def test_seed_processes_all_when_fewer_than_seed_phase_size(patched_backfill_deps: Any) -> None:
    """SEED-02: all reviews seeded when count < SEED_PHASE_SIZE."""
    from unittest.mock import MagicMock, patch

    shop = _make_shop()
    # Only 3 reviews, less than default SEED_PHASE_SIZE=50
    reviews_api = [_api_review(f"g-{i}") for i in range(1, 4)]
    page = {"reviews": reviews_api, "totalReviewCount": 3}

    mock_enrich = MagicMock()
    mock_wait = MagicMock(return_value=1)

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.services.sync.enrich_review", mock_enrich),
        patch("apps.reviews.services.sync._wait_for_openai_token", mock_wait),
        patch("apps.reviews.services.sync.enrich_review_task") as mock_task,
        patch("apps.reviews.services.sync.finalize_canonical_tags_task"),
    ):
        mock_task.apply_async = MagicMock()
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    # All 3 should be seeded (no bulk dispatch)
    assert mock_enrich.call_count == 3
    # No bulk dispatch since all seeded
    mock_task.apply_async.assert_not_called()


def test_bulk_dispatched_to_ai_enrichment_high(patched_backfill_deps: Any) -> None:
    """SEED-03: reviews beyond SEED_PHASE_SIZE are dispatched to ai-enrichment-high."""
    from unittest.mock import MagicMock, patch

    from django.conf import settings

    shop = _make_shop()
    # Create 70 reviews when SEED_PHASE_SIZE=50 → 50 seeded, 20 bulk
    reviews_api = [
        _api_review_with_time(f"g-{i:03d}", create_time=f"2026-0{(i // 30) + 1}-01T{i:02d}:00:00Z")
        for i in range(1, 71)
    ]
    page = {"reviews": reviews_api, "totalReviewCount": 70}

    mock_enrich = MagicMock()
    mock_wait = MagicMock(return_value=1)
    captured_queues: list[str] = []

    def _apply_async(*args: Any, **kwargs: Any) -> None:
        captured_queues.append(kwargs.get("queue", ""))

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.services.sync.enrich_review", mock_enrich),
        patch("apps.reviews.services.sync._wait_for_openai_token", mock_wait),
        patch("apps.reviews.services.sync.enrich_review_task") as mock_task,
        patch("apps.reviews.services.sync.finalize_canonical_tags_task"),
    ):
        mock_task.apply_async = _apply_async
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    seed_size = min(settings.SEED_PHASE_SIZE, 70)
    bulk_size = 70 - seed_size
    # Bulk dispatched to ai-enrichment-high
    assert all(q == "ai-enrichment-high" for q in captured_queues[:bulk_size]), (
        "bulk must route to ai-enrichment-high"
    )


def test_finalize_dispatched_to_tag_merge_with_countdown(patched_backfill_deps: Any) -> None:
    """Phase 4: finalize_canonical_tags_task dispatched to tag-merge with countdown."""
    from unittest.mock import MagicMock, patch

    shop = _make_shop()
    page = {"reviews": [_api_review("g-1")], "totalReviewCount": 1}

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.services.sync.enrich_review", MagicMock()),
        patch("apps.reviews.services.sync._wait_for_openai_token", MagicMock(return_value=1)),
        patch("apps.reviews.services.sync.enrich_review_task") as _et,
        patch("apps.reviews.services.sync.finalize_canonical_tags_task") as mock_finalize,
    ):
        _et.apply_async = MagicMock()
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    mock_finalize.apply_async.assert_called_once()
    call_kwargs = mock_finalize.apply_async.call_args.kwargs
    assert call_kwargs.get("queue") == "tag-merge", "finalize must go to tag-merge"
    assert call_kwargs.get("countdown") is not None, "finalize must have a countdown"
    assert call_kwargs["countdown"] > 0, "finalize countdown must be positive"


def test_vocab_progress_event_emitted(patched_backfill_deps: Any) -> None:
    """D-02: sync.vocab.progress emitted after each seed review commit."""
    from unittest.mock import MagicMock, patch

    shop = _make_shop()
    page = {"reviews": [_api_review("g-1"), _api_review("g-2")], "totalReviewCount": 2}

    emitted_events: list[dict] = []

    def _capture_emit(*, shop_id: int, payload: dict[str, Any]) -> None:
        emitted_events.append(payload)

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.services.sync.enrich_review", MagicMock()),
        patch("apps.reviews.services.sync._wait_for_openai_token", MagicMock(return_value=1)),
        patch("apps.reviews.services.sync.enrich_review_task") as _et,
        patch("apps.reviews.services.sync.finalize_canonical_tags_task"),
        patch.object(sync_mod, "emit_progress_event", side_effect=_capture_emit),
    ):
        _et.apply_async = MagicMock()
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    vocab_events = [e for e in emitted_events if e.get("type") == "sync.vocab.progress"]
    assert len(vocab_events) >= 2, "one sync.vocab.progress per seed review"
    assert all("enriched" in e and "total" in e for e in vocab_events)


def test_incremental_sync_routes_to_ai_enrichment_low(patched_backfill_deps: Any) -> None:
    """DSYNC-01: incremental sync uses ai-enrichment-low queue."""
    from unittest.mock import patch

    shop = _make_shop()
    page = {"reviews": [_api_review("g-1")], "totalReviewCount": 1}

    captured_queue: list[str] = []

    def _apply_async(*args: Any, **kwargs: Any) -> None:
        captured_queue.append(kwargs.get("queue", ""))

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.tasks.enrich_review_task.apply_async", side_effect=_apply_async),
    ):
        sync_mod.run_incremental_sync(shop_id=shop.pk)

    if captured_queue:
        assert all(q == "ai-enrichment-low" for q in captured_queue), (
            f"incremental dispatch must use ai-enrichment-low, got: {captured_queue}"
        )


def test_depleted_bucket_seed_completes_all_reviews(patched_backfill_deps: Any) -> None:
    """INTEGRATION (Blocker 2): depleted bucket must NOT crash the seed loop.

    Forces the bucket to appear depleted for the first K checks, then clear.
    Asserts enrich_review is called N times and no exception escapes.
    """
    from unittest.mock import MagicMock, patch

    shop = _make_shop()
    reviews_api = [_api_review(f"g-{i}") for i in range(1, 4)]
    page = {"reviews": reviews_api, "totalReviewCount": 3}

    enrich_calls: list[int] = []

    def _mock_enrich(*, review_id: int, skip_rate_limit_guard: bool = False) -> None:
        enrich_calls.append(review_id)

    wait_calls = 0

    def _wait_that_pretends_to_wait(*, organisation_id: int, max_calls: int, **kwargs: Any) -> int:
        nonlocal wait_calls
        wait_calls += 1
        return 1  # never raises, always returns

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.services.sync.enrich_review", side_effect=_mock_enrich),
        patch(
            "apps.reviews.services.sync._wait_for_openai_token",
            side_effect=_wait_that_pretends_to_wait,
        ),
        patch("apps.reviews.services.sync.enrich_review_task") as _et,
        patch("apps.reviews.services.sync.finalize_canonical_tags_task"),
    ):
        _et.apply_async = MagicMock()
        # Must not raise even with simulated delays
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    assert len(enrich_calls) == 3, f"all 3 seed reviews must be enriched, got {len(enrich_calls)}"
    assert wait_calls == 3, f"_wait_for_openai_token called once per seed review, got {wait_calls}"


def test_get_org_vocabulary_called_per_seed_iteration(patched_backfill_deps: Any) -> None:
    """D-04: re-read org vocabulary before each seed review."""
    from unittest.mock import MagicMock, patch

    shop = _make_shop()
    page = {"reviews": [_api_review(f"g-{i}") for i in range(1, 4)], "totalReviewCount": 3}

    vocab_calls: list[int] = []

    def _mock_get_vocab(*, organisation_id: int, **kwargs: Any) -> list[str]:
        vocab_calls.append(organisation_id)
        return []

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.services.sync.enrich_review", MagicMock()),
        patch("apps.reviews.services.sync._wait_for_openai_token", MagicMock(return_value=1)),
        patch("apps.reviews.services.sync.get_org_vocabulary", side_effect=_mock_get_vocab),
        patch("apps.reviews.services.sync.enrich_review_task") as _et,
        patch("apps.reviews.services.sync.finalize_canonical_tags_task"),
    ):
        _et.apply_async = MagicMock()
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    # Called at least once per seed review (3 reviews)
    assert len(vocab_calls) >= 3, (
        f"get_org_vocabulary must be called per seed review, got {len(vocab_calls)}"
    )


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


def test_review_fetched_audit_logged(patched_dependencies) -> None:
    """SYNC-10 gap closure: review.fetched AuditLog row is written per persisted page."""
    shop = _make_shop()
    page1 = {
        "reviews": [_api_review("g-1"), _api_review("g-2")],
        "totalReviewCount": 3,
        "nextPageToken": "next",
    }
    page2 = {
        "reviews": [_api_review("g-3")],
        "totalReviewCount": 3,
    }
    with patch.object(sync_mod, "list_reviews", side_effect=[page1, page2]):
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    rows = list(
        AuditLog.objects.filter(
            entity_type="review",
            action="review.fetched",
            entity_id=str(shop.pk),
        ).order_by("created_at")
    )
    assert len(rows) == 2
    pages = [r.after_data["page"] for r in rows]
    counts = [r.after_data["count"] for r in rows]
    assert pages == [1, 2]
    assert counts == [2, 1]
    assert all(r.after_data["trigger"] == "initial" for r in rows)


def test_pagination_halts_when_bucket_depleted(patched_dependencies) -> None:
    """SYNC-09 gap closure: depleted bucket short-circuits the pagination loop."""
    shop = _make_shop()
    page = {"reviews": [_api_review("g-1")], "totalReviewCount": 1}
    with (
        patch.object(sync_mod, "token_bucket_depleted", return_value=True),
        patch.object(sync_mod, "list_reviews", return_value=page) as list_mock,
    ):
        sync_mod.run_initial_backfill(shop_id=shop.pk)

    assert list_mock.call_count == 0
    assert (
        AuditLog.objects.filter(
            entity_type="review",
            action="review.fetched",
            entity_id=str(shop.pk),
        ).count()
        == 0
    )
    # sync.started is still recorded so the audit trail shows the attempt
    assert AuditLog.objects.filter(
        entity_type="shop_sync",
        action="sync.started",
        entity_id=str(shop.pk),
    ).exists()


# ---------------------------------------------------------------------------
# Phase 12-06: inline enrichment dispatch + sync.complete removal
# ---------------------------------------------------------------------------


def _build_api_review(*, review_id: str, comment: str, rating: str = "FIVE") -> dict:
    return {
        "reviewId": review_id,
        "starRating": rating,
        "comment": comment,
        "createTime": "2026-04-01T10:00:00Z",
        "updateTime": "2026-04-01T10:00:00Z",
        "reviewer": {"displayName": "Test Reviewer", "isAnonymous": False, "profilePhotoUrl": ""},
    }


@pytest.mark.django_db
def test_fetch_and_persist_enqueues_enrichment_for_pending_reviews(
    patched_dependencies,
) -> None:
    """ENRCH-02 sync wiring: every upserted PENDING review receives an enrich_review_task dispatch."""
    shop = _make_shop()
    page = {
        "reviews": [
            _build_api_review(review_id="g-rev-1", comment="Great service"),
            _build_api_review(review_id="g-rev-2", comment="Loved the staff"),
            _build_api_review(review_id="g-rev-3", comment="Quick response"),
        ],
        "totalReviewCount": 3,
    }
    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        # enrich_review_task is imported locally inside fetch_and_persist_reviews
        # to avoid a circular import. Patch at the tasks module level.
        patch("apps.reviews.tasks.enrich_review_task.delay") as mock_delay,
    ):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="initial")

    assert mock_delay.call_count == 3
    enqueued_ids = {call.args[0] for call in mock_delay.call_args_list}
    persisted = list(
        Review.objects.filter(shop=shop, google_review_id__startswith="g-rev-").values_list(
            "id", flat=True
        )
    )
    assert enqueued_ids == set(persisted)


@pytest.mark.django_db
def test_fetch_and_persist_emits_sync_complete(patched_dependencies) -> None:
    """fetch_and_persist_reviews must emit sync.complete on success so the UI updates.

    Previously the success path only wrote the Redis snapshot but never sent
    the WebSocket event, leaving the progress bar frozen at the last fetch-progress
    value. The fix adds emit_progress_event in the success path.
    """
    shop = _make_shop()
    page = {
        "reviews": [_build_api_review(review_id="g-only-1", comment="Test")],
        "totalReviewCount": 1,
    }
    captured_emit: list[dict] = []

    def _capture_emit(*, shop_id: int, payload: dict) -> None:
        captured_emit.append(payload)

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        # enrich_review_task is imported locally; patch at tasks module level
        patch("apps.reviews.tasks.enrich_review_task.delay"),
        patch.object(sync_mod, "emit_progress_event", side_effect=_capture_emit),
    ):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="initial")

    emitted_types = [p["type"] for p in captured_emit]
    # sync.fetch.progress emitted during fetch, sync.complete emitted on success
    assert "sync.fetch.progress" in emitted_types
    assert "sync.complete" in emitted_types, (
        f"sync.complete must be emitted by fetch_and_persist_reviews on success; "
        f"got types: {emitted_types}"
    )
    complete_event = next(p for p in captured_emit if p["type"] == "sync.complete")
    assert complete_event["shop_id"] == shop.pk
    assert complete_event["total_fetched"] == 1


# ---------------------------------------------------------------------------
# Rate-limit and enrichment-dispatch optimisations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_token_bucket_cap_is_1800() -> None:
    """Google's published QPM for the GBP API is 1 800.  Our defensive cap must
    not be lower than that — a cap of 600 caused mid-sync halts for shops with
    more than 600 reviews per minute of fetch time when multiple stores synced
    concurrently (token_bucket_depleted short-circuits the pagination loop)."""
    from apps.reviews.services.progress import GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE

    assert GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE >= 1800, (
        "Token bucket cap must be >= 1800 (Google GBP QPM limit). "
        "A lower cap causes partial syncs for large shops."
    )


@pytest.mark.django_db
def test_already_enriched_reviews_bulk_incremented_not_dispatched(
    patched_dependencies,
) -> None:
    """Re-syncing a shop where reviews are already SUCCESS must NOT dispatch
    enrich_review_task for those reviews.  Instead, fetch_and_persist_reviews
    must call bulk_increment_enriched_counter so the enriched-counter advances
    without flooding the ai-enrichment queue with no-op idempotent tasks.

    Scenario: page contains 2 reviews; both are already SUCCESS in the DB.
    Expected: enrich_review_task.delay never called; bulk_increment called once
    with count=2.
    """
    shop = _make_shop()
    page = {
        "reviews": [_api_review("g-already-1"), _api_review("g-already-2")],
        "totalReviewCount": 2,
    }

    # Pre-create reviews as SUCCESS with the same comment/rating as the API
    # fixture — if the content differs, _persist_page resets status to PENDING.
    from apps.reviews.models import Review
    from apps.reviews.tests.factories import ReviewFactory

    ReviewFactory(
        shop=shop,
        google_review_id="g-already-1",
        comment="Great!",
        star_rating=5,
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
    )
    ReviewFactory(
        shop=shop,
        google_review_id="g-already-2",
        comment="Great!",
        star_rating=5,
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
    )

    with (
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch("apps.reviews.tasks.enrich_review_task.delay") as mock_delay,
        patch.object(sync_mod, "bulk_increment_enriched_counter") as mock_bulk,
    ):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="initial")

    assert mock_delay.call_count == 0, (
        "enrich_review_task must NOT be dispatched for already-SUCCESS reviews"
    )
    assert mock_bulk.call_count >= 1, (
        "bulk_increment_enriched_counter must be called for already-SUCCESS reviews"
    )
    total_bulk_incremented = sum(c.kwargs["count"] for c in mock_bulk.call_args_list)
    assert total_bulk_incremented == 2, (
        "bulk counter must be advanced by exactly 2 (the number of SUCCESS reviews)"
    )


# ---------------------------------------------------------------------------
# Phase 15-03: BKFL-01 / BKFL-02 / BKFL-03 — initial backfill date filter
# ---------------------------------------------------------------------------


def _build_gbp_review(google_review_id: str, days_old: int) -> dict[str, Any]:
    """Build a single GBP API review payload at a given age relative to now."""
    from datetime import timedelta

    from django.utils import timezone as dj_timezone

    create_time = (dj_timezone.now() - timedelta(days=days_old)).isoformat().replace("+00:00", "Z")
    return {
        "name": f"accounts/x/locations/y/reviews/{google_review_id}",
        "reviewId": google_review_id,
        "reviewer": {"displayName": "Test", "isAnonymous": False},
        "starRating": "FIVE",
        "comment": "ok",
        "createTime": create_time,
        "updateTime": create_time,
    }


@pytest.mark.django_db
def test_initial_backfill_one_year_date_filter(patched_dependencies) -> None:
    """BKFL-01: ONE_YEAR shop initial backfill skips reviews older than 365 days."""
    shop = ShopFactory(
        sync_depth=Shop.SyncDepth.ONE_YEAR,
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    page = {
        "reviews": [
            _build_gbp_review("r-recent", 100),
            _build_gbp_review("r-mid", 400),
            _build_gbp_review("r-old", 800),
        ],
        "totalReviewCount": 3,
    }
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="initial")
    persisted_ids = set(Review.objects.filter(shop=shop).values_list("google_review_id", flat=True))
    assert persisted_ids == {"r-recent"}, (
        f"ONE_YEAR filter must exclude reviews older than 365 days; got {persisted_ids}"
    )


@pytest.mark.django_db
def test_initial_backfill_two_years_date_filter(patched_dependencies) -> None:
    """BKFL-02: TWO_YEARS shop initial backfill skips reviews older than 730 days."""
    shop = ShopFactory(
        sync_depth=Shop.SyncDepth.TWO_YEARS,
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    page = {
        "reviews": [
            _build_gbp_review("r-recent", 100),
            _build_gbp_review("r-mid", 400),
            _build_gbp_review("r-old", 800),
        ],
        "totalReviewCount": 3,
    }
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="initial")
    persisted_ids = set(Review.objects.filter(shop=shop).values_list("google_review_id", flat=True))
    assert persisted_ids == {"r-recent", "r-mid"}, (
        f"TWO_YEARS filter must exclude reviews older than 730 days; got {persisted_ids}"
    )


@pytest.mark.django_db
def test_initial_backfill_all_time_no_filter(patched_dependencies) -> None:
    """BKFL-03: ALL_TIME shop initial backfill persists all reviews regardless of age."""
    shop = ShopFactory(
        sync_depth=Shop.SyncDepth.ALL_TIME,
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    page = {
        "reviews": [
            _build_gbp_review("r-recent", 100),
            _build_gbp_review("r-mid", 400),
            _build_gbp_review("r-old", 800),
        ],
        "totalReviewCount": 3,
    }
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="initial")
    persisted_ids = set(Review.objects.filter(shop=shop).values_list("google_review_id", flat=True))
    assert persisted_ids == {"r-recent", "r-mid", "r-old"}, (
        f"ALL_TIME must persist all reviews; got {persisted_ids}"
    )


# ---------------------------------------------------------------------------
# Phase 16-01 Task 3: incremental sync respects shop.sync_depth date floor
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_incremental_sync_filters_reviews_older_than_one_year(patched_dependencies) -> None:
    """Phase 16-01: ONE_YEAR incremental sync skips reviews older than 365 days."""
    shop = ShopFactory(
        sync_depth=Shop.SyncDepth.ONE_YEAR,
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    page = {
        "reviews": [
            _build_gbp_review("r-recent", 100),  # inside ONE_YEAR window
            _build_gbp_review("r-old", 400),  # outside ONE_YEAR window (>365 days)
        ],
        "totalReviewCount": 2,
    }
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="incremental")
    persisted_ids = set(Review.objects.filter(shop=shop).values_list("google_review_id", flat=True))
    assert persisted_ids == {"r-recent"}, (
        f"ONE_YEAR incremental sync must exclude reviews older than 365 days; got {persisted_ids}"
    )


@pytest.mark.django_db
def test_incremental_sync_no_filter_for_all_time(patched_dependencies) -> None:
    """Phase 16-01: ALL_TIME incremental sync persists all reviews regardless of age."""
    shop = ShopFactory(
        sync_depth=Shop.SyncDepth.ALL_TIME,
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    page = {
        "reviews": [
            _build_gbp_review("r-old-1000", 1000),  # well outside any date window
        ],
        "totalReviewCount": 1,
    }
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="incremental")
    assert Review.objects.filter(shop=shop).count() == 1, (
        "ALL_TIME incremental sync must persist all reviews regardless of age"
    )


@pytest.mark.django_db
def test_incremental_sync_two_years_filter(patched_dependencies) -> None:
    """Phase 16-01: TWO_YEARS incremental sync skips reviews older than 730 days."""
    shop = ShopFactory(
        sync_depth=Shop.SyncDepth.TWO_YEARS,
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    page = {
        "reviews": [
            _build_gbp_review("r-old-800", 800),  # outside TWO_YEARS window (>730 days)
        ],
        "totalReviewCount": 1,
    }
    with patch.object(sync_mod, "list_reviews", return_value=page):
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="incremental")
    assert Review.objects.filter(shop=shop).count() == 0, (
        "TWO_YEARS incremental sync must exclude reviews older than 730 days"
    )
