"""Phase 11 — Celery task wrapper tests."""

from __future__ import annotations

import contextlib
from unittest.mock import patch

import pytest

from apps.reviews import tasks
from apps.shops.models import Shop
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def test_initial_backfill_task_delegates_to_service() -> None:
    with patch.object(tasks, "run_initial_backfill", return_value={"fetched": 0}) as svc:
        result = tasks.initial_backfill_task(shop_id=42)
    svc.assert_called_once_with(shop_id=42)
    assert result == {"fetched": 0}


def test_sync_shop_reviews_task_delegates_to_service() -> None:
    with patch.object(tasks, "run_incremental_sync", return_value={"fetched": 5}) as svc:
        result = tasks.sync_shop_reviews_task(shop_id=42)
    svc.assert_called_once_with(shop_id=42)
    assert result == {"fetched": 5}


def test_enqueue_incremental_syncs_dispatches_per_connected_shop() -> None:
    s1 = ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=True)
    s2 = ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=True)
    ShopFactory(connection_status=Shop.ConnectionStatus.NOT_CONNECTED, is_active=True)
    ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=False)
    ShopFactory(connection_status=Shop.ConnectionStatus.EXPIRED, is_active=True)

    with patch.object(tasks.sync_shop_reviews_task, "apply_async") as apply_async:
        count = tasks.enqueue_incremental_syncs_task()

    assert count == 2
    dispatched_args = sorted(c.kwargs["args"][0] for c in apply_async.call_args_list)
    assert dispatched_args == sorted([s1.pk, s2.pk])


def test_enqueue_incremental_syncs_countdown_within_jitter_window() -> None:
    ShopFactory(connection_status=Shop.ConnectionStatus.CONNECTED, is_active=True)
    with patch.object(tasks.sync_shop_reviews_task, "apply_async") as apply_async:
        tasks.enqueue_incremental_syncs_task()
    countdown = apply_async.call_args.kwargs["countdown"]
    assert 0.0 <= countdown <= tasks.INCREMENTAL_JITTER_SECONDS_MAX


def test_periodic_task_seeded() -> None:
    from django_celery_beat.models import PeriodicTask

    pt = PeriodicTask.objects.filter(name="enqueue_incremental_syncs").first()
    assert pt is not None
    assert pt.task == "apps.reviews.tasks.enqueue_incremental_syncs_task"
    assert pt.queue == "google-sync"
    assert pt.enabled is True


def test_initial_backfill_dispatched_to_google_sync_queue() -> None:
    """Verify Celery routing matches the requirement (SYNC-01: dispatched after OAuth)."""
    from celery import current_app

    routes = current_app.conf.task_routes
    assert routes["apps.reviews.tasks.initial_backfill_task"]["queue"] == "google-sync"
    assert routes["apps.reviews.tasks.sync_shop_reviews_task"]["queue"] == "google-sync"


# ---------------------------------------------------------------------------
# Phase 12 — enrich_review_task + retry_failed_enrichments_task tests
# ---------------------------------------------------------------------------


def test_enrich_review_task_has_rate_limit() -> None:
    """QUEUE-02: enrich_review_task must carry rate_limit from settings.ENRICHMENT_RATE_LIMIT.

    The rate_limit is PER WORKER INSTANCE (D-06), not global. This test only
    asserts the configured per-worker value is wired from the setting.
    """
    from django.conf import settings

    assert tasks.enrich_review_task.rate_limit == settings.ENRICHMENT_RATE_LIMIT


def test_enrich_review_task_calls_service() -> None:
    """Task body is a thin wrapper — verify it calls enrich_review."""
    from apps.reviews.tests.factories import ReviewFactory

    review = ReviewFactory()
    with patch("apps.reviews.services.enrichment.enrich_review") as mock_service:
        tasks.enrich_review_task(review.pk)
    mock_service.assert_called_once_with(review_id=review.pk)


def test_retry_failed_enrichments_task_enqueues_failed_reviews() -> None:
    """ENRCH-06: only FAILED + version<3 + not soft-deleted are re-enqueued."""
    from django.utils import timezone

    from apps.reviews.models import Review
    from apps.reviews.tasks import MAX_TOTAL_ENRICH_ATTEMPTS
    from apps.reviews.tests.factories import ReviewFactory

    # FAILED with version 0 — should be enqueued
    candidate = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version=0,
    )
    # FAILED with version=3 — at cap, NOT enqueued
    at_cap = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version=MAX_TOTAL_ENRICH_ATTEMPTS,
    )
    # SUCCESS — not enqueued
    success = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.SUCCESS,
        enrichment_version=1,
    )
    # PENDING — not enqueued
    pending = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    # FAILED but soft-deleted — not enqueued
    deleted = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version=0,
        deleted_at=timezone.now(),
    )

    with patch("apps.reviews.tasks.enrich_review_task.apply_async") as mock_apply:
        count = tasks.retry_failed_enrichments_task()

    assert count == 1
    mock_apply.assert_called_once_with(args=[candidate.pk], queue="ai-enrichment-low")
    # Verify none of the others were enqueued
    enqueued_ids = {call.kwargs["args"][0] for call in mock_apply.call_args_list}
    assert at_cap.pk not in enqueued_ids
    assert success.pk not in enqueued_ids
    assert pending.pk not in enqueued_ids
    assert deleted.pk not in enqueued_ids


def test_retry_failed_enrichments_task_returns_zero_when_no_candidates() -> None:
    from apps.reviews.models import Review
    from apps.reviews.tests.factories import ReviewFactory

    ReviewFactory(enrichment_status=Review.EnrichmentStatus.SUCCESS)
    with patch("apps.reviews.tasks.enrich_review_task.apply_async"):
        assert tasks.retry_failed_enrichments_task() == 0


def test_retry_failed_enrichments_task_caps_at_500_per_run() -> None:
    """Defensive: large FAILED backlog still fits in one run."""
    from apps.reviews.models import Review
    from apps.reviews.tests.factories import ReviewFactory

    # Build 510 FAILED reviews — cap should fire at 500.
    ReviewFactory.create_batch(
        510,
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version=0,
    )
    with patch("apps.reviews.tasks.enrich_review_task.apply_async") as mock_apply:
        count = tasks.retry_failed_enrichments_task()
    assert count == 500
    assert mock_apply.call_count == 500


def test_retry_failed_enrichments_excludes_moderated() -> None:
    """D-25: content_moderated rows must NEVER be retried (reviewer text is immutable).

    D-31: uses the denormalized Review.enrichment_error_code field.
    """
    from apps.reviews.models import Review
    from apps.reviews.tests.factories import ReviewFactory

    moderated = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version=1,
        enrichment_error_code="content_moderated",
    )
    transient = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version=1,
        enrichment_error_code="openai_5xx",
    )
    legacy = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.FAILED,
        enrichment_version=1,
        enrichment_error_code="",
    )

    with patch("apps.reviews.tasks.enrich_review_task.apply_async") as mock_apply:
        count = tasks.retry_failed_enrichments_task()

    enqueued_ids = {call.kwargs["args"][0] for call in mock_apply.call_args_list}
    assert moderated.pk not in enqueued_ids, "content_moderated must not be retried (D-25)"
    assert transient.pk in enqueued_ids
    assert legacy.pk in enqueued_ids
    assert count == 2


def test_retry_failed_enrichments_includes_other_failure_codes() -> None:
    """D-25 negative: all non-moderated failure codes remain retry-eligible."""
    from apps.reviews.models import Review
    from apps.reviews.tests.factories import ReviewFactory

    codes = ["openai_5xx", "parse_error", "openai_timeout", ""]
    reviews = [
        ReviewFactory(
            enrichment_status=Review.EnrichmentStatus.FAILED,
            enrichment_version=1,
            enrichment_error_code=code,
        )
        for code in codes
    ]

    with patch("apps.reviews.tasks.enrich_review_task.apply_async") as mock_apply:
        count = tasks.retry_failed_enrichments_task()

    enqueued_ids = {call.kwargs["args"][0] for call in mock_apply.call_args_list}
    for review in reviews:
        assert review.pk in enqueued_ids, f"code={review.enrichment_error_code!r} should retry"
    assert count == len(codes)


# ---------------------------------------------------------------------------
# Phase 23 Task 2 — token-bucket guard in enrich_review + sync.complete decoupling
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _acquired_lock(_key: str, timeout: int = 300):  # type: ignore[type-arg]
    """Context manager that always yields True (lock acquired) without Redis."""
    yield True


def test_enrich_review_bulk_path_raises_on_depleted_bucket() -> None:
    """Bulk path (skip_rate_limit_guard=False): depleted bucket → raises OpenAITransientError."""
    from apps.integrations.openai.exceptions import OpenAITransientError
    from apps.reviews.models import Review
    from apps.reviews.services import enrichment as enrichment_mod
    from apps.reviews.services.enrichment import enrich_review
    from apps.reviews.tests.factories import ReviewFactory

    review = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.PENDING,
        comment="test comment",
    )
    with (
        patch.object(enrichment_mod, "distributed_lock", _acquired_lock),
        patch.object(enrichment_mod, "openai_token_bucket_depleted", return_value=True),
        pytest.raises(OpenAITransientError),
    ):
        enrich_review(review_id=review.pk)


def test_enrich_review_seed_path_does_not_raise_on_depleted_bucket() -> None:
    """Seed path (skip_rate_limit_guard=True): depleted bucket → NO raise, NO increment."""
    from apps.reviews.models import Review
    from apps.reviews.services import enrichment as enrichment_mod
    from apps.reviews.services.enrichment import enrich_review
    from apps.reviews.tests.factories import ReviewFactory

    review = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.PENDING,
        comment="",  # no-comment path: avoids OpenAI call, lock is still needed
    )
    mock_depleted = patch.object(enrichment_mod, "openai_token_bucket_depleted", return_value=True)
    mock_incr = patch.object(enrichment_mod, "increment_openai_token_bucket")
    # Patch progress functions used by _persist_success_no_comment → _emit_enrichment_progress
    mock_read = patch("apps.reviews.services.progress.read_progress_snapshot", return_value=None)
    with (
        patch.object(enrichment_mod, "distributed_lock", _acquired_lock),
        mock_depleted as depleted_mock,
        mock_incr as incr_mock,
        mock_read,
    ):
        enrich_review(review_id=review.pk, skip_rate_limit_guard=True)

    # Token bucket must NOT have been checked or incremented on the seed path
    depleted_mock.assert_not_called()
    incr_mock.assert_not_called()


def test_enrich_review_bulk_path_increments_bucket_when_not_depleted() -> None:
    """Bulk path: bucket has headroom → increments once then proceeds to call_openai_enrichment.

    Uses a review with a comment so it reaches the token-bucket guard (the no-comment
    path early-returns before the guard runs). Mocks moderate_input + call_openai_enrichment
    so no real OpenAI call is made, and _persist_success so no DB writes are needed.
    """
    from unittest.mock import MagicMock

    from apps.reviews.models import Review
    from apps.reviews.services import enrichment as enrichment_mod
    from apps.reviews.services.enrichment import enrich_review
    from apps.reviews.tests.factories import ReviewFactory

    review = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.PENDING,
        comment="A real comment so the no-comment path is NOT taken.",
    )
    fake_result = MagicMock()
    fake_usage: dict[str, int] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    with (
        patch.object(enrichment_mod, "distributed_lock", _acquired_lock),
        patch.object(
            enrichment_mod, "openai_token_bucket_depleted", return_value=False
        ) as mock_depleted,
        patch.object(enrichment_mod, "increment_openai_token_bucket") as mock_incr,
        patch.object(enrichment_mod, "moderate_input", return_value="truncated text"),
        patch.object(
            enrichment_mod, "call_openai_enrichment", return_value=(fake_result, fake_usage)
        ),
        patch.object(enrichment_mod, "_persist_success"),
    ):
        enrich_review(review_id=review.pk)  # skip_rate_limit_guard=False (default)

    mock_depleted.assert_called_once()
    mock_incr.assert_called_once()


def test_emit_enrichment_progress_does_not_emit_sync_complete_when_enriched_gte_fetched() -> None:
    """_emit_enrichment_progress must NOT emit sync.complete even when enriched >= fetched.

    sync.complete ownership has moved to the finalising pass (run_finalise_canonical_tags).
    """
    from apps.reviews.models import Review
    from apps.reviews.services.enrichment import _emit_enrichment_progress
    from apps.reviews.tests.factories import ReviewFactory

    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.SUCCESS)
    shop_id = review.shop_id

    # Mock Redis helpers so the test runs without a real Redis backend.
    # The snapshot has fetched=1; enriched will reach 1 after 1 increment.
    fake_snapshot = {"shop_id": shop_id, "status": "enriching", "fetched": 1, "enriched": 0}

    emitted_types: list[str] = []

    def _capture_event(*, shop_id: int, payload: dict) -> None:  # type: ignore[type-arg]
        emitted_types.append(payload.get("type", ""))

    with (
        patch(
            "apps.reviews.services.progress.read_progress_snapshot",
            return_value=fake_snapshot,
        ),
        patch(
            "apps.reviews.services.progress.increment_enriched_counter",
            return_value=1,
        ),
        patch("apps.reviews.services.progress.write_progress_snapshot"),
        patch(
            "apps.reviews.services.sync.emit_progress_event",
            side_effect=_capture_event,
        ),
    ):
        _emit_enrichment_progress(review=review)

    assert "sync.complete" not in emitted_types, (
        "sync.complete must not be emitted by _emit_enrichment_progress (moved to finalise.py)"
    )
