"""Phase 19 — Tests for apps.reviews.services.reply_generation.

Covers D-14 / D-15 / D-16 / D-17:
  - generate_reply_draft returns draft string on success
  - exactly one AiUsageLog row per call (SUCCESS or FAILED)
  - request_type="reply_generation"
  - OpenAITransientError / OpenAIPermanentError write FAILED log + re-raise
  - Generic Exception (e.g. ConnectionError) also writes FAILED log + re-raises
    (D-17 — view layer maps to 502)

Phase 20 — TestGenerateReplyDraftModeration covers D-07 / D-08 / D-14 / D-22 /
D-29 / D-33 (input + output moderation wiring, output truncation, atomic-block
discipline for the audit row).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.db import transaction

from apps.integrations.openai.exceptions import (
    ContentModeratedException,
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
        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                side_effect=lambda text, **kw: text,
            ),
            patch(
                "apps.reviews.services.reply_generation.moderate_output",
                side_effect=lambda text, **kw: text,
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                return_value=("Nice reply!", _usage_data()),
            ),
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
                "apps.reviews.services.reply_generation.moderate_input",
                side_effect=lambda text, **kw: text,
            ),
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
                "apps.reviews.services.reply_generation.moderate_input",
                side_effect=lambda text, **kw: text,
            ),
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
                "apps.reviews.services.reply_generation.moderate_input",
                side_effect=lambda text, **kw: text,
            ),
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


class TestGenerateReplyDraftModeration:
    """Phase 20 — input + output moderation + 300-word truncation wiring.

    D-14: moderate_input runs BEFORE call_openai_reply_generation; the truncated
    text flows into the prompt. moderate_output runs AFTER the OpenAI call and
    BEFORE the SUCCESS AiUsageLog write. truncate_reply_at_sentence runs AFTER
    moderate_output passes.

    D-29: when moderate_output blocks, the MODERATED AiUsageLog row carries the
    REAL prompt/completion tokens and REAL cost from `usage_data` — the OpenAI
    call already consumed those tokens.

    D-33: both moderation call sites are outside any transaction.atomic() block
    so a caller-side rollback cannot erase the safety-event audit row.
    """

    @pytest.mark.django_db
    def test_moderate_input_called_before_openai_call(self) -> None:
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        call_order: list[str] = []

        def _input_se(text: str, *, review: object, request_type: str) -> str:
            call_order.append("input")
            return "clean text"

        def _openai_se(*, review: object, tone: str, model: str) -> tuple:
            call_order.append("openai")
            return ("Nice reply.", _usage_data())

        def _output_se(
            text: str,
            *,
            review: object,
            request_type: str,
            usage_data: dict | None = None,
        ) -> str:
            call_order.append("output")
            return text

        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                side_effect=_input_se,
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                side_effect=_openai_se,
            ),
            patch(
                "apps.reviews.services.reply_generation.moderate_output",
                side_effect=_output_se,
            ),
        ):
            draft = generate_reply_draft(review=review, tone="professional")

        assert draft == "Nice reply."
        assert call_order == ["input", "openai", "output"]

    @pytest.mark.django_db
    def test_input_moderation_block_raises_and_skips_openai(self) -> None:
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                side_effect=ContentModeratedException("input flagged"),
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
            ) as mock_openai,
            patch(
                "apps.reviews.services.reply_generation.moderate_output",
            ) as mock_output,
            pytest.raises(ContentModeratedException),
        ):
            generate_reply_draft(review=review, tone="professional")

        mock_openai.assert_not_called()
        mock_output.assert_not_called()

    @pytest.mark.django_db
    def test_output_moderation_block_writes_aiusagelog_with_real_tokens(self) -> None:
        """D-29: output-moderation MODERATED row carries REAL tokens + cost +
        error_code='output_moderated'. Exercise the real `moderate_output`
        end-to-end (only the Moderation HTTP call is mocked) so the
        `_persist_moderated_log` path is observed for fidelity.
        """
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()

        # A flagged Moderation API response: sexual_minors is in the blocking set.
        flagged_categories = {
            "sexual_minors": True,
            "hate_threatening": False,
            "violence_graphic": False,
            "self_harm_intent": False,
            "self_harm_instructions": False,
            "harassment": False,
            "hate": False,
            "self_harm": False,
            "sexual": False,
            "violence": False,
        }

        class _FakeCategories:
            def model_dump(self) -> dict:
                return flagged_categories

        fake_response = MagicMock()
        fake_response.results = [MagicMock(categories=_FakeCategories())]

        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                return_value="clean input",
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                return_value=("naughty draft", _usage_data()),
            ),
            # Let the real moderate_output run — only intercept the API call.
            patch(
                "apps.integrations.openai.guardrails._call_moderation_api",
                return_value=fake_response,
            ),
            pytest.raises(ContentModeratedException),
        ):
            generate_reply_draft(review=review, tone="professional")

        moderated = AiUsageLog.objects.filter(
            request_type="reply_generation",
            status=AiUsageLog.Status.MODERATED,
        )
        assert moderated.count() == 1
        log = moderated.first()
        assert log.error_code == "output_moderated"
        # D-29: real tokens from usage_data flowed through to the audit row.
        assert log.prompt_tokens == 100
        assert log.completion_tokens == 50
        assert log.total_tokens == 150
        assert log.estimated_cost_usd > Decimal("0")
        # No SUCCESS row — moderation blocked before the SUCCESS log.
        assert (
            AiUsageLog.objects.filter(
                request_type="reply_generation",
                status=AiUsageLog.Status.SUCCESS,
            ).count()
            == 0
        )

    @pytest.mark.django_db
    def test_output_truncation_applied_after_moderation_pass(self) -> None:
        """D-08/D-22: truncate_reply_at_sentence runs AFTER moderate_output."""
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        # 4 sentences, 80 words each = 320 words total — over the 300-word cap.
        sentence = " ".join(["word"] * 80) + "."
        long_draft = " ".join([sentence] * 4)
        assert len(long_draft.split()) == 320

        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                return_value="clean input",
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                return_value=(long_draft, _usage_data()),
            ),
            patch(
                "apps.reviews.services.reply_generation.moderate_output",
                side_effect=lambda text, **kw: text,
            ),
        ):
            draft = generate_reply_draft(review=review, tone="professional")

        assert draft.endswith(" (Please review and complete before sending.)")
        body = draft.removesuffix(" (Please review and complete before sending.)")
        assert len(body.split()) <= 300

    @pytest.mark.django_db
    def test_short_reply_not_truncated(self) -> None:
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        short_draft = " ".join(["word"] * 150) + "."

        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                return_value="clean input",
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                return_value=(short_draft, _usage_data()),
            ),
            patch(
                "apps.reviews.services.reply_generation.moderate_output",
                side_effect=lambda text, **kw: text,
            ),
        ):
            draft = generate_reply_draft(review=review, tone="professional")

        assert draft == short_draft

    @pytest.mark.django_db
    def test_truncated_input_flows_into_openai(self) -> None:
        """D-14: the moderated/truncated text — not raw review.comment — is
        what gets used for prompt assembly inside call_openai_reply_generation.
        """
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory(comment="raw untrimmed comment")

        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                return_value="TRUNCATED_MARKER",
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                return_value=("Ok.", _usage_data()),
            ) as mock_openai,
            patch(
                "apps.reviews.services.reply_generation.moderate_output",
                side_effect=lambda text, **kw: text,
            ),
        ):
            generate_reply_draft(review=review, tone="professional")

        assert mock_openai.call_count == 1
        kwargs = mock_openai.call_args.kwargs
        forwarded_review = kwargs["review"]
        assert forwarded_review.comment == "TRUNCATED_MARKER"
        # Original Review.comment must NOT have been mutated in place.
        assert review.comment == "raw untrimmed comment"

    @pytest.mark.django_db(transaction=True)
    def test_moderate_calls_outside_atomic_block(self) -> None:
        """D-33: both moderate_input and moderate_output run OUTSIDE any
        transaction.atomic() block — runtime regression for Pitfall 3.

        Records `transaction.get_connection().in_atomic_block` at each call
        site and asserts [False, False]. Uses `transaction=True` to disable
        pytest-django's default test-wrapping atomic block, otherwise EVERY
        callsite would falsely report True and the regression check would
        be useless.
        """
        from apps.reviews.services.reply_generation import generate_reply_draft

        review = ReviewFactory()
        recorded: list[bool] = []

        def _input_se(text: str, *, review: object, request_type: str) -> str:
            recorded.append(transaction.get_connection().in_atomic_block)
            return "clean input"

        def _output_se(
            text: str,
            *,
            review: object,
            request_type: str,
            usage_data: dict | None = None,
        ) -> str:
            recorded.append(transaction.get_connection().in_atomic_block)
            return text

        with (
            patch(
                "apps.reviews.services.reply_generation.moderate_input",
                side_effect=_input_se,
            ),
            patch(
                "apps.reviews.services.reply_generation.call_openai_reply_generation",
                return_value=("Nice.", _usage_data()),
            ),
            patch(
                "apps.reviews.services.reply_generation.moderate_output",
                side_effect=_output_se,
            ),
        ):
            generate_reply_draft(review=review, tone="professional")

        assert recorded == [False, False]
