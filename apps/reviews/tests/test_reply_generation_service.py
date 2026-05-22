"""Phase 19 — Tests for apps.reviews.services.reply_generation.

Covers D-14 / D-15 / D-16 / D-17:
  - generate_reply_draft returns draft string on success
  - exactly one AiUsageLog row per call (SUCCESS or FAILED)
  - request_type="reply_generation"
  - OpenAITransientError / OpenAIPermanentError write FAILED log + re-raise
  - Generic Exception (e.g. ConnectionError) also writes FAILED log + re-raises
    (D-17 — view layer maps to 502)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.integrations.openai.exceptions import (
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.models import AiUsageLog
from apps.reviews.tests.factories import ReviewFactory


def _usage_data() -> dict:
    return {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "cached_tokens": 0,
        "total_tokens": 150,
        "latency_ms": 500,
        "langsmith_trace_id": "trace-reply-001",
    }


class TestGenerateReplyDraft:
    @pytest.mark.django_db
    def test_success_returns_draft_and_writes_log(self) -> None:
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        with patch(
            "apps.reviews.services.reply_generation.call_openai_reply_generation",
            return_value=("Nice reply!", _usage_data()),
        ):
            draft = generate_reply_draft(review=review, tone="professional")

        assert draft == "Nice reply!"
        logs = AiUsageLog.objects.filter(
            request_type="reply_generation",
            status=AiUsageLog.Status.SUCCESS,
        )
        assert logs.count() == 1
        log = logs.first()
        assert log.review_id == review.pk
        assert log.organisation_id == review.organisation_id
        assert log.prompt_tokens == 100
        assert log.completion_tokens == 50
        assert log.total_tokens == 150
        assert log.langsmith_trace_id == "trace-reply-001"

    @pytest.mark.django_db
    def test_transient_error_writes_failed_log_and_raises(self) -> None:
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        with (
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                side_effect=OpenAITransientError("boom"),
            ),
            pytest.raises(OpenAITransientError),
        ):
            generate_reply_draft(review=review, tone="professional")

        logs = AiUsageLog.objects.filter(
            request_type="reply_generation",
            status=AiUsageLog.Status.FAILED,
        )
        assert logs.count() == 1
        log = logs.first()
        assert log.error_code == "OpenAITransientError"
        assert "boom" in log.error_message

    @pytest.mark.django_db
    def test_permanent_error_writes_failed_log_and_raises(self) -> None:
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        with (
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                side_effect=OpenAIPermanentError("down", status_code=400),
            ),
            pytest.raises(OpenAIPermanentError),
        ):
            generate_reply_draft(review=review, tone="friendly")

        logs = AiUsageLog.objects.filter(
            request_type="reply_generation",
            status=AiUsageLog.Status.FAILED,
        )
        assert logs.count() == 1
        assert logs.first().error_code == "OpenAIPermanentError"

    @pytest.mark.django_db
    def test_generic_exception_writes_failed_log_and_raises(self) -> None:
        """D-17: any exception (not just OpenAI-typed) must write a FAILED log."""
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        with (
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                side_effect=ConnectionError("timeout"),
            ),
            pytest.raises(ConnectionError),
        ):
            generate_reply_draft(review=review, tone="professional")

        logs = AiUsageLog.objects.filter(
            request_type="reply_generation",
            status=AiUsageLog.Status.FAILED,
        )
        assert logs.count() == 1
        log = logs.first()
        assert log.error_code == "ConnectionError"
        assert "timeout" in log.error_message

    @pytest.mark.django_db
    def test_unknown_tone_raises_value_error_before_openai_call(self) -> None:
        """Belt-and-braces tone validation in the service (serializer also validates)."""
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        with (
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
            ) as mock_call,
            pytest.raises(ValueError, match="tone"),
        ):
            generate_reply_draft(review=review, tone="formal")
        mock_call.assert_not_called()
        assert AiUsageLog.objects.filter(request_type="reply_generation").count() == 0
