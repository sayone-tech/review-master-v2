"""Phase 12 — _emit_enrichment_progress tests (sync.enrichment.progress + gated sync.complete).

Note: _emit_enrichment_progress uses lazy imports (inside function body) to avoid circular
imports (enrichment.py -> sync.py -> tasks.py -> enrichment.py). Therefore, patching must
target the source modules (progress.py and sync.py), not the enrichment module namespace.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.reviews.services import enrichment as enrichment_mod
from apps.reviews.services.enrichment import _emit_enrichment_progress
from apps.reviews.tests.factories import ReviewFactory


@pytest.mark.django_db
def test_emit_enrichment_progress_returns_silently_when_snapshot_missing() -> None:
    """No live ProgressModal -> no WebSocket event, no error."""
    review = ReviewFactory()
    with (
        patch(
            "apps.reviews.services.progress.read_progress_snapshot",
            return_value=None,
        ),
        patch(
            "apps.reviews.services.progress.write_progress_snapshot",
        ) as mock_write,
        patch(
            "apps.reviews.services.sync.emit_progress_event",
        ) as mock_emit,
    ):
        _emit_enrichment_progress(review=review)
    mock_write.assert_not_called()
    mock_emit.assert_not_called()


@pytest.mark.django_db
def test_emit_enrichment_progress_increments_and_emits() -> None:
    """When enriched < fetched, emit sync.enrichment.progress only."""
    review = ReviewFactory()
    snapshot = {
        "shop_id": review.shop_id,
        "status": "fetching",
        "fetched": 5,
        "enriched": 2,
        "started_at": "2026-04-01T10:00:00Z",
        "last_update_at": "2026-04-01T10:01:00Z",
        "page_count": 1,
    }
    written_snapshots: list[dict] = []
    emitted_payloads: list[dict] = []

    def _capture_write(*, shop_id: int, data: dict) -> None:
        written_snapshots.append(data)

    def _capture_emit(*, shop_id: int, payload: dict) -> None:
        emitted_payloads.append(payload)

    with (
        patch(
            "apps.reviews.services.progress.read_progress_snapshot",
            return_value=snapshot,
        ),
        patch(
            "apps.reviews.services.progress.write_progress_snapshot",
            side_effect=_capture_write,
        ),
        patch(
            "apps.reviews.services.sync.emit_progress_event",
            side_effect=_capture_emit,
        ),
        # increment_enriched_counter uses Redis INCR; mock it to return
        # the next counter value (previous enriched + 1 = 3).
        patch(
            "apps.reviews.services.progress.increment_enriched_counter",
            return_value=3,
        ),
    ):
        _emit_enrichment_progress(review=review)

    # Snapshot rewritten with enriched=3, status="enriching"
    assert len(written_snapshots) == 1
    written = written_snapshots[0]
    assert written["enriched"] == 3
    assert written["status"] == "enriching"
    # One sync.enrichment.progress event, no sync.complete
    assert len(emitted_payloads) == 1
    payload = emitted_payloads[0]
    assert payload["type"] == "sync.enrichment.progress"
    assert payload["shop_id"] == review.shop_id
    assert payload["enriched"] == 3
    assert payload["fetched"] == 5


@pytest.mark.django_db
def test_emit_enrichment_progress_fires_sync_complete_when_caught_up() -> None:
    """When enriched (post-increment) >= fetched, also emit sync.complete."""
    review = ReviewFactory()
    snapshot = {
        "shop_id": review.shop_id,
        "status": "enriching",
        "fetched": 3,
        "enriched": 2,  # incrementing to 3 -> >= fetched
        "started_at": "2026-04-01T10:00:00Z",
        "last_update_at": "2026-04-01T10:01:00Z",
        "duration_seconds": 12.5,
        "page_count": 1,
    }
    written_snapshots: list[dict] = []
    emitted_payloads: list[dict] = []

    def _capture_write(*, shop_id: int, data: dict) -> None:
        written_snapshots.append(data)

    def _capture_emit(*, shop_id: int, payload: dict) -> None:
        emitted_payloads.append(payload)

    with (
        patch(
            "apps.reviews.services.progress.read_progress_snapshot",
            return_value=snapshot,
        ),
        patch(
            "apps.reviews.services.progress.write_progress_snapshot",
            side_effect=_capture_write,
        ),
        patch(
            "apps.reviews.services.sync.emit_progress_event",
            side_effect=_capture_emit,
        ),
        # enriched was 2; after atomic INCR -> 3 (== fetched -> sync.complete)
        patch(
            "apps.reviews.services.progress.increment_enriched_counter",
            return_value=3,
        ),
        # Notification dispatch at sync.complete is tested separately
        patch.object(enrichment_mod, "_dispatch_sync_complete_notifications"),
        # claim_sync_complete uses Redis SETNX; mock to return True (first caller wins)
        patch(
            "apps.reviews.services.progress.claim_sync_complete",
            return_value=True,
        ),
    ):
        _emit_enrichment_progress(review=review)

    assert len(written_snapshots) == 1
    written = written_snapshots[0]
    assert written["enriched"] == 3
    assert written["status"] == "success"
    # Two events: sync.enrichment.progress + sync.complete
    assert len(emitted_payloads) == 2
    types = [p["type"] for p in emitted_payloads]
    assert "sync.enrichment.progress" in types
    assert "sync.complete" in types
    complete_payload = next(p for p in emitted_payloads if p["type"] == "sync.complete")
    assert complete_payload["total_fetched"] == 3
    assert complete_payload["total_enriched"] == 3
    assert complete_payload["duration_seconds"] == 12.5


@pytest.mark.django_db
def test_emit_enrichment_progress_no_sync_complete_when_fetched_zero() -> None:
    """fetched=0 (edge case) -> no sync.complete even if enriched matches."""
    review = ReviewFactory()
    snapshot = {
        "shop_id": review.shop_id,
        "status": "fetching",
        "fetched": 0,
        "enriched": 0,
        "started_at": "2026-04-01T10:00:00Z",
        "last_update_at": "2026-04-01T10:01:00Z",
        "page_count": 0,
    }
    emitted_payloads: list[dict] = []

    def _capture_emit(*, shop_id: int, payload: dict) -> None:
        emitted_payloads.append(payload)

    with (
        patch(
            "apps.reviews.services.progress.read_progress_snapshot",
            return_value=snapshot,
        ),
        patch(
            "apps.reviews.services.progress.write_progress_snapshot",
        ),
        patch(
            "apps.reviews.services.sync.emit_progress_event",
            side_effect=_capture_emit,
        ),
        # fetched=0 so even after increment sync.complete must NOT fire
        patch(
            "apps.reviews.services.progress.increment_enriched_counter",
            return_value=1,
        ),
    ):
        _emit_enrichment_progress(review=review)

    types = [p["type"] for p in emitted_payloads]
    assert "sync.complete" not in types


@pytest.mark.django_db
def test_sync_complete_dispatched_exactly_once_under_concurrent_enrichments() -> None:
    """Regression test for the notification spam bug (6 418 notifications for
    FRUITBAE Kakkanad).

    Root cause: _emit_enrichment_progress does a non-atomic read-modify-write on
    the Redis snapshot, which can overwrite sync.py's updated 'fetched' value with
    a stale one.  Once enriched > stale_fetched, the condition 'enriched >= fetched'
    evaluates True on every subsequent enrichment call, firing
    _dispatch_sync_complete_notifications once per review instead of once per sync.

    The fix: claim_sync_complete() uses Redis SETNX so only the first caller that
    satisfies the condition wins the right to dispatch.  All later callers — including
    those running with a stale fetched value — receive False and are silenced.
    """
    from apps.reviews.services.enrichment import _emit_enrichment_progress

    review = ReviewFactory()
    shop_id = review.shop_id

    # Simulate the stale-snapshot race: fetched appears to be 50 (page 1 total) in
    # every worker's snapshot read, but the enriched counter has already surpassed 50
    # because enrichments for page 1 completed before sync.py wrote the page-2
    # snapshot (fetched=100).
    stale_snapshot = {
        "shop_id": shop_id,
        "status": "enriching",
        "fetched": 50,
        "enriched": 49,
        "started_at": "2026-04-01T10:00:00Z",
        "last_update_at": "2026-04-01T10:01:00Z",
        "page_count": 1,
    }

    dispatch_calls: list[dict] = []

    def _capture_dispatch(*, review: object, total_fetched: int) -> None:
        dispatch_calls.append({"total_fetched": total_fetched})

    # Simulate 10 concurrent enrichment completions where enriched (51-60) > fetched (50)
    # — every single one satisfies the condition without the SETNX guard.
    claim_results = [True] + [False] * 9  # only the first call wins the lock

    with (
        patch(
            "apps.reviews.services.progress.read_progress_snapshot",
            return_value=stale_snapshot,
        ),
        patch("apps.reviews.services.progress.write_progress_snapshot"),
        patch("apps.reviews.services.sync.emit_progress_event"),
        patch.object(
            enrichment_mod, "_dispatch_sync_complete_notifications", side_effect=_capture_dispatch
        ),
        patch(
            "apps.reviews.services.progress.claim_sync_complete",
            side_effect=claim_results,
        ),
    ):
        for counter_value in range(51, 61):
            with patch(
                "apps.reviews.services.progress.increment_enriched_counter",
                return_value=counter_value,
            ):
                _emit_enrichment_progress(review=review)

    assert len(dispatch_calls) == 1, (
        f"_dispatch_sync_complete_notifications must fire exactly once; "
        f"fired {len(dispatch_calls)} times (notification spam regression)"
    )
