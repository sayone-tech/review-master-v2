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
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext

from apps.integrations.openai.exceptions import (
    EnrichmentParseError,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.parser import EnrichmentResult
from apps.reviews.models import OrgCanonicalTag, Review, ReviewTag
from apps.reviews.services.enrichment import (
    RATING_TO_SENTIMENT,
    enrich_review,
    rating_to_sentiment,
)
from apps.reviews.tests.factories import (
    OrgCanonicalTagFactory,
    ReviewFactory,
    ReviewTagFactory,
)


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
                {
                    "label": "fast service",
                    "polarity": "positive",
                    "canonical": "Fast Service",
                    "polarity_type": "always_positive",
                },
                {
                    "label": "limited menu",
                    "polarity": "neutral",
                    "canonical": "Limited Menu",
                    "polarity_type": "mixed",
                },
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
    # Phase 17 (TAG-02): tags now live in ReviewTag rows, not Review.tags JSONField.
    tag_qs = ReviewTag.objects.filter(review=review).order_by("label")
    assert tag_qs.count() == 2
    tag_labels = sorted(t.label for t in tag_qs)
    assert tag_labels == sorted(["Fast Service", "Limited Menu"])  # title-cased
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
    assert ReviewTag.objects.filter(review=review).count() == 0
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
    assert ReviewTag.objects.filter(review=review).count() == 0
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


# ---------------------------------------------------------------------------
# Phase 17 (TAG-02): ReviewTag relational write path tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_enrich_creates_review_tag_rows() -> None:
    """TAG-02: successful enrichment writes one ReviewTag row per result.tag."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
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
    assert ReviewTag.objects.filter(review=review).count() == len(result.tags)


@pytest.mark.django_db
def test_enrich_stores_labels_title_cased() -> None:
    """TAG-02: ReviewTag.label is stored title-cased (not the raw GPT label)."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _build_result()  # raw labels: "fast service", "limited menu"
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
    labels = set(ReviewTag.objects.filter(review=review).values_list("label", flat=True))
    assert labels == {"Fast Service", "Limited Menu"}


@pytest.mark.django_db
def test_re_enrichment_is_idempotent_deletes_old_tag_rows() -> None:
    """TAG-02 (D-09): re-enriching a review deletes old ReviewTag rows before insert.

    Simulates two enrichment passes producing different tags. Final state must
    contain only the second pass's tags — no duplicates, no stale rows.
    """
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)

    first_result = EnrichmentResult.model_validate(
        {
            "sentiment": "positive",
            "tags": [
                {
                    "label": "old tag",
                    "polarity": "positive",
                    "canonical": "Old Tag",
                    "polarity_type": "always_positive",
                },
                {
                    "label": "another old",
                    "polarity": "neutral",
                    "canonical": "Another Old",
                    "polarity_type": "mixed",
                },
            ],
            "action_items": [],
        }
    )
    second_result = EnrichmentResult.model_validate(
        {
            "sentiment": "negative",
            "tags": [
                {
                    "label": "fresh tag",
                    "polarity": "negative",
                    "canonical": "Fresh Tag",
                    "polarity_type": "always_negative",
                },
            ],
            "action_items": [],
        }
    )

    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(first_result, _usage()),
        ),
    ):
        enrich_review(review_id=review.pk)

    # Sanity: first pass landed.
    assert ReviewTag.objects.filter(review=review).count() == 2

    # Reset status so the second enrichment is allowed to run through (not
    # short-circuited by the Layer-3 SUCCESS guard).
    Review.objects.filter(pk=review.pk).update(enrichment_status=Review.EnrichmentStatus.PENDING)

    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(second_result, _usage()),
        ),
    ):
        enrich_review(review_id=review.pk)

    final_labels = set(ReviewTag.objects.filter(review=review).values_list("label", flat=True))
    assert final_labels == {"Fresh Tag"}  # stale rows deleted, only new tag remains


@pytest.mark.django_db
def test_no_comment_enrichment_clears_stale_review_tag_rows() -> None:
    """TAG-02: comment-less enrichment deletes any pre-existing ReviewTag rows.

    A review enriched once (with tags), then re-fetched as comment-less (e.g.
    reviewer edited their review to remove the text), must end with zero
    ReviewTag rows — not the stale ones.
    """
    review = ReviewFactory(
        comment="",
        star_rating=4,
        enrichment_status=Review.EnrichmentStatus.PENDING,
    )
    # Pre-seed stale tags as if a previous enrichment had run.
    ReviewTagFactory(review=review, label="Stale One")
    ReviewTagFactory(review=review, label="Stale Two")
    assert ReviewTag.objects.filter(review=review).count() == 2

    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_call,
    ):
        enrich_review(review_id=review.pk)
    mock_call.assert_not_called()
    assert ReviewTag.objects.filter(review=review).count() == 0


# ---------------------------------------------------------------------------
# Phase 20 — TestEnrichReviewModeration (D-15, D-31, D-33 regression)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEnrichReviewModeration:
    """Phase 20 plan 20-05 — input moderation wiring in enrich_review."""

    def test_moderate_input_called_before_openai(self) -> None:
        """D-15: moderate_input runs first; truncated text flows to OpenAI."""
        from apps.integrations.openai.exceptions import ContentModeratedException  # noqa: F401

        review = ReviewFactory(
            comment="Original review text",
            enrichment_status=Review.EnrichmentStatus.PENDING,
        )
        result = _build_result()
        call_order: list[str] = []

        def _moderate_side_effect(text, *, review=None, request_type="enrichment"):
            call_order.append("moderate")
            return "clean truncated text"

        def _openai_side_effect(*, review, canonical_vocab=None):
            call_order.append("openai")
            # The truncated text from moderate_input must be on the review.comment
            # in-memory before reaching the prompt assembly (D-21).
            assert review.comment == "clean truncated text"
            return (result, _usage())

        with (
            patch(
                "apps.reviews.services.enrichment.distributed_lock",
                side_effect=lambda *_a, **_kw: _lock_acquired(True),
            ),
            patch(
                "apps.reviews.services.enrichment.moderate_input",
                side_effect=_moderate_side_effect,
            ) as mock_moderate,
            patch(
                "apps.reviews.services.enrichment.call_openai_enrichment",
                side_effect=_openai_side_effect,
            ) as mock_openai,
        ):
            enrich_review(review_id=review.pk)

        assert call_order == ["moderate", "openai"]
        assert mock_moderate.call_count == 1
        # moderate_input was called with the ORIGINAL review.comment.
        called_text = mock_moderate.call_args.args[0]
        assert called_text == "Original review text"
        assert mock_openai.call_count == 1

    def test_moderate_input_blocks_sets_failed_with_error_code(self) -> None:
        """D-15/D-31: ContentModeratedException → FAILED + content_moderated."""
        from apps.integrations.openai.exceptions import ContentModeratedException

        review = ReviewFactory(
            comment="Some flagged content",
            enrichment_status=Review.EnrichmentStatus.PENDING,
            enrichment_error_code="",
        )
        with (
            patch(
                "apps.reviews.services.enrichment.distributed_lock",
                side_effect=lambda *_a, **_kw: _lock_acquired(True),
            ),
            patch(
                "apps.reviews.services.enrichment.moderate_input",
                side_effect=ContentModeratedException("input flagged"),
            ),
            patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_openai,
        ):
            enrich_review(review_id=review.pk)

        mock_openai.assert_not_called()
        review.refresh_from_db()
        assert review.enrichment_status == Review.EnrichmentStatus.FAILED
        assert review.enrichment_error_code == "content_moderated"
        assert review.enrichment_attempted_at is not None

    def test_moderate_input_does_not_use_atomic_block(self) -> None:
        """D-33 / Pitfall 3: moderate_input must run OUTSIDE any atomic block
        opened by enrich_review.

        @pytest.mark.django_db wraps every test in an outer atomic block, so
        `in_atomic_block` is always True inside a test. Instead, snapshot the
        savepoint depth BEFORE calling enrich_review, then at the moderation
        call site assert the depth has not grown — proving no inner
        transaction.atomic() block from enrich_review is open when
        moderate_input runs.
        """
        from django.db import connection as dj_connection

        review = ReviewFactory(
            comment="Some text",
            enrichment_status=Review.EnrichmentStatus.PENDING,
        )
        result = _build_result()
        baseline_depth = len(dj_connection.savepoint_ids)
        depth_at_call: list[int] = []

        def _moderate_side_effect(text, *, review=None, request_type="enrichment"):
            depth_at_call.append(len(dj_connection.savepoint_ids))
            return text

        with (
            patch(
                "apps.reviews.services.enrichment.distributed_lock",
                side_effect=lambda *_a, **_kw: _lock_acquired(True),
            ),
            patch(
                "apps.reviews.services.enrichment.moderate_input",
                side_effect=_moderate_side_effect,
            ),
            patch(
                "apps.reviews.services.enrichment.call_openai_enrichment",
                return_value=(result, _usage()),
            ),
        ):
            enrich_review(review_id=review.pk)

        # No nested atomic block from enrich_review is open at the moderation
        # call site: savepoint depth matches the pre-call baseline (which is
        # the depth of the outer test-wrapping atomic only).
        assert depth_at_call == [baseline_depth]

    def test_already_success_review_skips_moderation(self) -> None:
        """D-15 idempotency: SUCCESS-status review is a no-op.

        Pins CLAUDE.md §12.4 layer-3 short-circuit — prevents a future refactor
        from moving moderate_input above the SUCCESS guard and silently
        re-billing moderated traffic.
        """
        review = ReviewFactory(
            comment="Already enriched",
            enrichment_status=Review.EnrichmentStatus.SUCCESS,
        )
        baseline = AiUsageLog.objects.filter(review=review).count()

        with (
            patch(
                "apps.reviews.services.enrichment.distributed_lock",
                side_effect=lambda *_a, **_kw: _lock_acquired(True),
            ),
            patch("apps.reviews.services.enrichment.moderate_input") as mock_moderate,
            patch("apps.reviews.services.enrichment.call_openai_enrichment") as mock_openai,
        ):
            enrich_review(review_id=review.pk)

        mock_moderate.assert_not_called()
        mock_openai.assert_not_called()
        assert AiUsageLog.objects.filter(review=review).count() == baseline


# ---------------------------------------------------------------------------
# Phase 22 — canonical FK resolution folded into _persist_success (22-05).
# CTAG-06 (FK populate / new-label insert), CTAG-07 (one AiUsageLog), D-03
# (review_count untouched), no-N+1 query ceiling, atomic rollback, idempotency.
# ---------------------------------------------------------------------------


def _build_result_with_canonical() -> EnrichmentResult:
    """Two tags: one proposing a NEW canonical (concrete polarity_type), one
    whose canonical matches an EXISTING OrgCanonicalTag (polarity_type=None)."""
    return EnrichmentResult.model_validate(
        {
            "sentiment": "positive",
            "tags": [
                {
                    "label": "great coffee",
                    "polarity": "positive",
                    "canonical": "Coffee Quality",
                    "polarity_type": "always_positive",
                },
                {
                    "label": "slow staff",
                    "polarity": "negative",
                    "canonical": "Staff Speed",
                    "polarity_type": None,
                },
            ],
            "action_items": [],
        }
    )


@pytest.mark.django_db
def test_canonical_fk_populated_new_and_existing() -> None:
    """CTAG-06/CTAG-01: matched label reused; new label created with polarity_type."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    existing = OrgCanonicalTagFactory(
        organisation=review.organisation,
        label="Staff Speed",
        polarity_type=OrgCanonicalTag.PolarityType.MIXED,
    )
    result = _build_result_with_canonical()
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

    tags = {
        t.label: t for t in ReviewTag.objects.filter(review=review).select_related("canonical_tag")
    }
    # New canonical created exactly once, org-scoped, with GPT's polarity_type.
    new_canon = OrgCanonicalTag.objects.get(
        organisation=review.organisation, label="Coffee Quality"
    )
    assert new_canon.polarity_type == OrgCanonicalTag.PolarityType.ALWAYS_POSITIVE
    assert tags["Great Coffee"].canonical_tag_id == new_canon.pk
    # Existing canonical reused (same pk) — no duplicate row.
    assert tags["Slow Staff"].canonical_tag_id == existing.pk
    assert (
        OrgCanonicalTag.objects.filter(
            organisation=review.organisation, label="Staff Speed"
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_canonical_usage_log_is_exactly_one() -> None:
    """CTAG-07: exactly one AiUsageLog row even with canonical fold-in."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _build_result_with_canonical()
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
    assert AiUsageLog.objects.filter(review=review).count() == 1


@pytest.mark.django_db
def test_canonical_atomic_rollback_on_reviewtag_failure() -> None:
    """CTAG-06: a ReviewTag.bulk_create failure rolls back the canonical inserts too."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _build_result_with_canonical()
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(result, _usage()),
        ),
        patch(
            "apps.reviews.services.enrichment.ReviewTag.objects.bulk_create",
            side_effect=IntegrityError("boom"),
        ),
        pytest.raises(IntegrityError),
    ):
        enrich_review(review_id=review.pk)

    # Fresh querysets — the rollback must have unwound everything in the block.
    assert Review.objects.get(pk=review.pk).enrichment_status != Review.EnrichmentStatus.SUCCESS
    assert (
        OrgCanonicalTag.objects.filter(
            organisation=review.organisation, label="Coffee Quality"
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_canonical_idempotent_no_duplicate_rows_or_miscount() -> None:
    """D-03: re-enrichment creates no duplicate canonical rows; review_count stays 0."""
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _build_result_with_canonical()
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
        first_count = OrgCanonicalTag.objects.filter(organisation=review.organisation).count()
        # Force a real re-enrichment (the SUCCESS short-circuit would otherwise skip).
        Review.objects.filter(pk=review.pk).update(
            enrichment_status=Review.EnrichmentStatus.PENDING
        )
        enrich_review(review_id=review.pk)

    assert (
        OrgCanonicalTag.objects.filter(organisation=review.organisation).count() == first_count == 2
    )
    # D-03: review_count is never written in the hot path.
    assert list(
        OrgCanonicalTag.objects.filter(organisation=review.organisation).values_list(
            "review_count", flat=True
        )
    ) == [0, 0]


def _result_with_n_tags(n: int) -> EnrichmentResult:
    return EnrichmentResult.model_validate(
        {
            "sentiment": "positive",
            "tags": [
                {
                    "label": f"tag {i}",
                    "polarity": "positive",
                    "canonical": f"Canon {i}",
                    "polarity_type": "always_positive",
                }
                for i in range(min(n, 5))  # schema caps at 5 tags
            ],
            "action_items": [],
        }
    )


def _enrich_query_count(*, tag_count: int) -> int:
    review = ReviewFactory(enrichment_status=Review.EnrichmentStatus.PENDING)
    result = _result_with_n_tags(tag_count)
    with (
        patch(
            "apps.reviews.services.enrichment.distributed_lock",
            side_effect=lambda *_a, **_kw: _lock_acquired(True),
        ),
        patch(
            "apps.reviews.services.enrichment.call_openai_enrichment",
            return_value=(result, _usage()),
        ),
        patch("apps.reviews.services.enrichment._emit_enrichment_progress"),
        CaptureQueriesContext(connection) as ctx,
    ):
        enrich_review(review_id=review.pk)
    return len(ctx.captured_queries)


@pytest.mark.django_db
def test_canonical_query_count_is_fixed_regardless_of_tag_count() -> None:
    """No-N+1 (§6.9): the canonical fold-in is batch — query count is identical
    for 2 tags and 5 tags, and stays under a fixed ceiling.

    The ceiling (15) is the GREEN-observed count, NOT proportional to tags:
    select_for_update + IN_PROGRESS update, get_org_vocabulary, AiPricing
    get_active (calculate_cost), Review.update, ReviewTag.delete, the three
    canonical batch queries (SELECT + bulk_create + re-SELECT), ReviewTag
    bulk_create, AiUsageLog.create, plus the SAVEPOINT/RELEASE pairs that
    pytest-django's outer transaction turns the two atomic() blocks into.
    """
    two = _enrich_query_count(tag_count=2)
    five = _enrich_query_count(tag_count=5)
    assert two == five  # identical → no per-tag query growth
    assert five <= 15
