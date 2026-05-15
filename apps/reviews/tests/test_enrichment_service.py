"""Phase 12 — Tests for apps.reviews.services.enrichment.

Covers ENRCH-02 (Redis lock + status idempotency), ENRCH-03 (status transitions
under select_for_update), ENRCH-04 (error mapping), ENRCH-07 (AiUsageLog row
written on success), ENRCH-12 (langsmith_trace_id persisted).

Mocking strategy:
  - Patch apps.reviews.services.enrichment.call_openai_enrichment for happy path
  - Patch the same path with side_effect=OpenAITransientError / Permanent / Parse
    to test error handling
  - Patch apps.reviews.services.enrichment.distributed_lock to yield False to
    test lock-not-acquired exit

Phase 12-06: _persist_success now calls _emit_enrichment_progress which reads
Redis via read_progress_snapshot. The no_progress_snapshot fixture suppresses
Redis access in these tests by returning None (no live modal = no WebSocket event).
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.integrations.openai.exceptions import (
    EnrichmentParseError,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.parser import EnrichmentResult
from apps.reviews.models import Review
from apps.reviews.services.enrichment import (
    RATING_TO_SENTIMENT,
    enrich_review,
    rating_to_sentiment,
)
from apps.reviews.tests.factories import ReviewFactory


@pytest.fixture(autouse=True)
def no_progress_snapshot():
    """Phase 12-06: suppress Redis reads in _emit_enrichment_progress.

    _persist_success now calls _emit_enrichment_progress which reads from Redis.
    Returning None makes the helper exit silently so these tests focus on DB
    state and AiUsageLog — not WebSocket progress events.
    """
    with patch(
        "apps.reviews.services.progress.read_progress_snapshot",
        return_value=None,
    ):
        yield


def _build_result() -> EnrichmentResult:
    return EnrichmentResult.model_validate(
        {
            "sentiment": "positive",
            "tags": [
                {"label": "fast service", "polarity": "positive"},
                {"label": "limited menu", "polarity": "neutral"},
            ],
            "action_items": [
                {
                    "title": "Expand menu",
                    "scope": "shop",
                    "priority": "medium",
                    "category": "other",
                },
            ],
        }
    )


def _usage(*, trace_id: str | None = "trace-test-001") -> dict:
    return {
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "cached_tokens": 0,
        "total_tokens": 1200,
        "latency_ms": 1234,
        "langsmith_trace_id": trace_id,
    }


@contextmanager
def _lock_acquired(value: bool):
    """Context-manager helper that simulates distributed_lock yielding `value`."""
    yield value


def _patch_lock(acquired: bool) -> MagicMock:
    """Build a MagicMock for distributed_lock that yields the given acquired flag."""
    mock = MagicMock()
    mock.return_value.__enter__.return_value = acquired
    mock.return_value.__exit__.return_value = False
    return mock


@pytest.mark.django_db
def test_lock_not_acquired_exits_without_calling_openai() -> None:
    """ENRCH-02: another worker holds the lock — exit cleanly, no OpenAI call."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(False),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=review.pk)
    mock_call.assert_not_called()
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.PENDING


@pytest.mark.django_db
def test_idempotency_skips_when_status_success() -> None:
    """ENRCH-02: status=SUCCESS exits early without OpenAI call."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.SUCCESS)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=review.pk)
    mock_call.assert_not_called()
    assert AiUsageLog.objects.count() == 0


@pytest.mark.django_db
def test_idempotency_skips_when_status_in_progress() -> None:
    """ENRCH-02: status=IN_PROGRESS exits early without OpenAI call."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.IN_PROGRESS)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=review.pk)
    mock_call.assert_not_called()
    assert AiUsageLog.objects.count() == 0


@pytest.mark.django_db
def test_status_transitions_pending_to_success() -> None:
    """ENRCH-03: PENDING -> IN_PROGRESS -> SUCCESS transition path."""
    review = ReviewFactory(
        enrichment_status=Review.EnrichmentStatus.PENDING,
        sentiment="",
        tags=[],
        extracted_action_items=[],
        enrichment_version=0,
    )
    result = _build_result()
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(result, _usage()),
        ),
    ):
        enrich_review(review_id=review.pk)
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.SUCCESS
    assert review.sentiment == "positive"
    assert len(review.tags) == 2
    assert review.tags[0]["label"] == "fast service"
    assert len(review.extracted_action_items) == 1
    assert review.extracted_action_items[0]["scope"] == "shop"
    assert review.enrichment_version == 1


@pytest.mark.django_db
def test_usage_log_written_on_success() -> None:
    """ENRCH-07: AiUsageLog row written with token counts + cost + trace_id."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _build_result()
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(result, _usage(trace_id="trace-xyz-789")),
        ),
    ):
        enrich_review(review_id=review.pk)
    log = AiUsageLog.objects.get(review_id=review.pk)
    assert log.organisation_id == review.organisation_id
    assert log.request_type == "enrichment"
    assert log.prompt_tokens == 1000
    assert log.completion_tokens == 200
    assert log.cached_tokens == 0
    assert log.total_tokens == 1200
    assert log.latency_ms == 1234
    assert log.langsmith_trace_id == "trace-xyz-789"
    assert log.status == AiUsageLog.Status.SUCCESS
    # Cost = (1000-0)/1M * 0.15 + 0 + 200/1M * 0.6 = 0.00015 + 0.00012 = 0.00027
    assert log.estimated_cost_usd == Decimal("0.000270")


@pytest.mark.django_db
def test_trace_id_persisted_when_present() -> None:
    """ENRCH-12: trace_id surfaces onto AiUsageLog.langsmith_trace_id."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _build_result()
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(result, _usage(trace_id="trace-persist-test")),
        ),
    ):
        enrich_review(review_id=review.pk)
    log = AiUsageLog.objects.get(review_id=review.pk)
    assert log.langsmith_trace_id == "trace-persist-test"


@pytest.mark.django_db
def test_trace_id_blank_when_langsmith_disabled() -> None:
    """LangSmith disabled -> trace_id None -> AiUsageLog.langsmith_trace_id = '' (not None)."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _build_result()
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(result, _usage(trace_id=None)),
        ),
    ):
        enrich_review(review_id=review.pk)
    log = AiUsageLog.objects.get(review_id=review.pk)
    assert log.langsmith_trace_id == ""


@pytest.mark.django_db
def test_transient_error_marks_failed_and_raises() -> None:
    """ENRCH-04: 429/5xx -> mark FAILED + AiUsageLog FAILED + re-raise (autoretry)."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            side_effect=OpenAITransientError("rate limited"),
        ),
        pytest.raises(OpenAITransientError),
    ):
        enrich_review(review_id=review.pk)
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.FAILED
    assert review.sentiment == ""
    assert review.enrichment_version == 1
    log = AiUsageLog.objects.get(review_id=review.pk)
    assert log.status == AiUsageLog.Status.FAILED
    assert log.error_code == "OpenAITransientError"


@pytest.mark.django_db
def test_parse_error_marks_failed_and_raises() -> None:
    """ENRCH-04: parse failure -> mark FAILED + raise so autoretry_for fires once."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            side_effect=EnrichmentParseError("schema mismatch"),
        ),
        pytest.raises(EnrichmentParseError),
    ):
        enrich_review(review_id=review.pk)
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.FAILED


@pytest.mark.django_db
def test_permanent_error_marks_failed_and_returns() -> None:
    """ENRCH-04: 4xx (not 429) -> mark FAILED + DO NOT raise (no retry)."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            side_effect=OpenAIPermanentError("bad request", status_code=400),
        ),
    ):
        # Must NOT raise — test fails if it does.
        enrich_review(review_id=review.pk)
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.FAILED
    log = AiUsageLog.objects.get(review_id=review.pk)
    assert log.status == AiUsageLog.Status.FAILED
    assert log.error_code == "OpenAIPermanentError"


@pytest.mark.django_db
def test_missing_review_exits_silently() -> None:
    """Defensive: deleted review -> service returns without crashing."""
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=999_999_999)
    mock_call.assert_not_called()
    assert AiUsageLog.objects.count() == 0


@pytest.mark.django_db
def test_failed_review_appears_in_serializer() -> None:
    """ENRCH-05: a FAILED review still serializes — not hidden from /api/v1/reviews/."""
    from apps.reviews.serializers import ReviewReadSerializer

    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            side_effect=OpenAIPermanentError("bad", status_code=400),
        ),
    ):
        enrich_review(review_id=review.pk)
    review.refresh_from_db()
    data = ReviewReadSerializer(review).data
    assert data["enrichment_status"] == "FAILED"
    assert data["sentiment"] == ""
    assert data["tags"] == []
    assert data["extracted_action_items"] == []


# ---------------------------------------------------------------------------
# Phase 12-09 (gap closure): empty-comment skip path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rating", "expected"),
    [
        (1, "negative"),
        (2, "negative"),
        (3, "neutral"),
        (4, "positive"),
        (5, "positive"),
    ],
)
def test_rating_to_sentiment_mapping(rating: int, expected: str) -> None:
    """All five star ratings map to the expected sentiment bucket."""
    assert rating_to_sentiment(rating) == expected
    assert RATING_TO_SENTIMENT[rating] == expected


@pytest.mark.django_db
def test_skip_openai_when_no_comment() -> None:
    """Review with empty comment must NOT call OpenAI; sentiment from rating."""
    review = ReviewFactory(
        comment="",
        star_rating=1,
        enrichment_status=Review.EnrichmentStatus.PENDING,
    )
    usage_before = AiUsageLog.objects.count()
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=review.pk)
    mock_call.assert_not_called()
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.SUCCESS
    assert review.sentiment == "negative"
    assert review.tags == []
    assert review.extracted_action_items == []
    assert review.enrichment_version == 1
    assert AiUsageLog.objects.count() == usage_before


@pytest.mark.django_db
def test_skip_openai_when_whitespace_comment() -> None:
    """Whitespace-only comment is treated identically to empty."""
    review = ReviewFactory(
        comment="   \n\t  ",
        star_rating=3,
        enrichment_status=Review.EnrichmentStatus.PENDING,
    )
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=review.pk)
    mock_call.assert_not_called()
    review.refresh_from_db()
    assert review.sentiment == "neutral"
    assert review.enrichment_status == Review.EnrichmentStatus.SUCCESS
    assert review.tags == []
    assert review.extracted_action_items == []


@pytest.mark.django_db
def test_skip_path_does_not_write_ai_usage_log() -> None:
    """Skip path must incur ZERO AiUsageLog rows for the review."""
    review = ReviewFactory(
        comment="",
        star_rating=5,
        enrichment_status=Review.EnrichmentStatus.PENDING,
    )
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment"),
    ):
        enrich_review(review_id=review.pk)
    assert AiUsageLog.objects.filter(review_id=review.pk).count() == 0


@pytest.mark.django_db
def test_skip_path_idempotent() -> None:
    """Second call on a comment-less SUCCESS review is a no-op (Layer 3 guard)."""
    review = ReviewFactory(
        comment="",
        star_rating=5,
        enrichment_status=Review.EnrichmentStatus.PENDING,
    )
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=review.pk)
        enrich_review(review_id=review.pk)  # second call -> idempotent skip
    mock_call.assert_not_called()
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.SUCCESS
    assert review.enrichment_version == 1  # bumped exactly once
    assert AiUsageLog.objects.filter(review_id=review.pk).count() == 0


@pytest.mark.django_db
def test_normal_path_still_calls_openai_for_reviews_with_comments() -> None:
    """Regression guard: reviews WITH comments still hit OpenAI."""
    review = ReviewFactory(
        comment="Great service!",
        star_rating=5,
        enrichment_status=Review.EnrichmentStatus.PENDING,
    )
    result = _build_result()
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(result, _usage()),
        ) as mock_call,
    ):
        enrich_review(review_id=review.pk)
    mock_call.assert_called_once()
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.SUCCESS


# ---------------------------------------------------------------------------
# Regression: idempotent SUCCESS skip must still emit progress (bug fix)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_idempotent_success_skip_still_emits_progress() -> None:
    """Regression: pre-enriched SUCCESS review must emit _emit_enrichment_progress.

    Before the fix, enrich_review() returned early for SUCCESS reviews without
    calling _emit_enrichment_progress. This meant the Redis enriched counter
    never advanced for reviews that were already SUCCESS at sync time, causing
    a permanent fetched > enriched mismatch and sync.complete never firing
    (e.g. 101 of 109 enriched stuck forever with 8 pre-existing SUCCESS reviews).

    After the fix: the SUCCESS early-return path calls _emit_enrichment_progress
    AFTER the transaction exits, so the counter advances correctly.
    """
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.SUCCESS)
    emitted_calls: list[dict] = []

    def _capture_emit(*, review: Review) -> None:
        emitted_calls.append({"review_id": review.pk})

    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_openai,
        patch(
            "apps.reviews.services.enrichment._emit_enrichment_progress",
            side_effect=_capture_emit,
        ),
    ):
        enrich_review(review_id=review.pk)

    # OpenAI must NOT be called — the review was already SUCCESS.
    mock_openai.assert_not_called()
    # Progress MUST be emitted so the Redis counter advances.
    assert len(emitted_calls) == 1
    assert emitted_calls[0]["review_id"] == review.pk
    # DB state must remain SUCCESS and unchanged (no extra enrichment_version bump).
    review.refresh_from_db()
    assert review.enrichment_status == Review.EnrichmentStatus.SUCCESS


@pytest.mark.django_db
def test_in_progress_skip_does_not_emit_progress() -> None:
    """IN_PROGRESS skip must NOT emit progress — another worker owns that review.

    If IN_PROGRESS also emitted, two workers would double-count the same review
    in the Redis enriched counter (once for the skip, once on actual completion).
    """
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.IN_PROGRESS)
    emitted_calls: list[dict] = []

    def _capture_emit(*, review: Review) -> None:
        emitted_calls.append({"review_id": review.pk})

    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_openai,
        patch(
            "apps.reviews.services.enrichment._emit_enrichment_progress",
            side_effect=_capture_emit,
        ),
    ):
        enrich_review(review_id=review.pk)

    mock_openai.assert_not_called()
    # No progress emission for IN_PROGRESS — the active worker will emit on completion.
    assert len(emitted_calls) == 0
