"""Phase 12 / 23 — _emit_enrichment_progress tests.

Phase 12: sync.enrichment.progress emitted, enriched counter incremented.
Phase 23 (D-02): sync.complete ownership moved to run_finalise_canonical_tags.
  _emit_enrichment_progress NO LONGER emits sync.complete or sets status=success.
  These tests reflect the updated contract.

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
def test_emit_enrichment_progress_does_not_emit_sync_complete_when_enriched_gte_fetched() -> None:
    """Phase 23 (D-02): _emit_enrichment_progress NEVER emits sync.complete.

    Even when enriched (post-increment) >= fetched, the function only emits
    sync.enrichment.progress and leaves status as "enriching".  sync.complete
    ownership moved to run_finalise_canonical_tags in finalise.py.
    """
    review = ReviewFactory()
    snapshot = {
        "shop_id": review.shop_id,
        "status": "enriching",
        "fetched": 3,
        "enriched": 2,  # incrementing to 3 -> == fetched, but must NOT fire sync.complete
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
        # enriched was 2; after atomic INCR -> 3 (== fetched)
        patch(
            "apps.reviews.services.progress.increment_enriched_counter",
            return_value=3,
        ),
    ):
        _emit_enrichment_progress(review=review)

    assert len(written_snapshots) == 1
    written = written_snapshots[0]
    assert written["enriched"] == 3
    # status must stay "enriching" — Phase 23 D-02: no sync.complete from enrichment
    assert written["status"] == "enriching"
    # Only sync.enrichment.progress; sync.complete must NOT be emitted
    types = [p["type"] for p in emitted_payloads]
    assert "sync.complete" not in types
    assert "sync.enrichment.progress" in types


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
def test_sync_complete_never_dispatched_from_emit_enrichment_progress() -> None:
    """Phase 23 (D-02) regression: _dispatch_sync_complete_notifications must NEVER
    be called from _emit_enrichment_progress, even when enriched >= fetched.

    Phase 12 had a notification-spam bug where _emit_enrichment_progress fired
    sync.complete on every enrichment after enriched surpassed a stale fetched value.
    The Phase 12 fix used claim_sync_complete (SETNX).
    Phase 23 D-02 moves sync.complete ownership entirely to run_finalise_canonical_tags
    (finalise.py), so the guard is no longer needed here and all sync.complete
    dispatch must be absent from this function regardless of enriched/fetched ratio.
    """
    from apps.reviews.services.enrichment import _emit_enrichment_progress

    review = ReviewFactory()
    shop_id = review.shop_id

    # Snapshot where enriched is clearly past fetched (the old trigger condition).
    snapshot = {
        "shop_id": shop_id,
        "status": "enriching",
        "fetched": 50,
        "enriched": 49,
        "started_at": "2026-04-01T10:00:00Z",
        "last_update_at": "2026-04-01T10:01:00Z",
        "page_count": 1,
    }

    dispatch_calls: list[dict] = []

    def _capture_dispatch(*, shop_id: int, organisation_id: int, total_fetched: int) -> None:
        dispatch_calls.append({"total_fetched": total_fetched})

    # Simulate 10 concurrent enrichment completions where enriched > fetched.
    # Under Phase 23 D-02 none of them should fire _dispatch_sync_complete_notifications.
    with (
        patch(
            "apps.reviews.services.progress.read_progress_snapshot",
            return_value=snapshot,
        ),
        patch("apps.reviews.services.progress.write_progress_snapshot"),
        patch("apps.reviews.services.sync.emit_progress_event"),
        patch.object(
            enrichment_mod, "_dispatch_sync_complete_notifications", side_effect=_capture_dispatch
        ),
    ):
        for counter_value in range(51, 61):
            with patch(
                "apps.reviews.services.progress.increment_enriched_counter",
                return_value=counter_value,
            ):
                _emit_enrichment_progress(review=review)

    assert len(dispatch_calls) == 0, (
        f"_dispatch_sync_complete_notifications must never be called from "
        f"_emit_enrichment_progress (Phase 23 D-02); "
        f"called {len(dispatch_calls)} time(s) (notification spam regression)"
    )
