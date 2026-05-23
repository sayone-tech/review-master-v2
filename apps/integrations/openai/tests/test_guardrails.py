"""Phase 20 — apps/integrations/openai/guardrails.py unit-test suite.

Mocking convention: per CLAUDE.md §16 + RESEARCH.md "Mock convention", every
test patches the imported symbol inside the consuming module (here,
`apps.integrations.openai.guardrails._call_moderation_api`) — NOT the
underlying SDK. We never hit the real OpenAI Moderation API.

Coverage:
  TestTruncateInput              — D-03 / D-21 length truncation
  TestTruncateReplyAtSentence    — D-08 / D-22 reply length cap at sentence boundary
  TestEvaluateAndBlockingCategories
                                  — D-23 / D-30 category-aware blocking
                                    (Pitfall 1 regression: underscore form only)
  TestModerateInput              — D-01 / D-04 / D-21 / D-33 input gate +
                                    Pitfall 2 regression (status uppercase)
  TestModerateOutput             — D-07 / D-08 / D-29 output gate +
                                    real tokens written on output-moderated block
  TestFailOpenRetry              — D-24 one retry then fail-open
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import openai
import pytest
from django.test import override_settings

from apps.integrations.openai.exceptions import ContentModeratedException
from apps.integrations.openai.guardrails import (
    BLOCKING_MODERATION_CATEGORIES,
    _evaluate,
    _truncate_input,
    moderate_input,
    moderate_output,
    truncate_reply_at_sentence,
)
from apps.integrations.openai.models import AiUsageLog
from apps.reviews.tests.factories import ReviewFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATCH_TARGET = "apps.integrations.openai.guardrails._call_moderation_api"
_SLEEP_TARGET = "apps.integrations.openai.guardrails.time.sleep"


def _mod_response(categories: dict[str, bool]) -> MagicMock:
    """Build a MagicMock Moderation API response with the given category map."""
    response = MagicMock()
    response.results[0].categories.model_dump.return_value = categories
    return response


def _rate_limit_error() -> openai.RateLimitError:
    return openai.RateLimitError(message="rate limited", response=MagicMock(), body=None)


def _connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=MagicMock())


# ---------------------------------------------------------------------------
# TestTruncateInput — D-03 / D-21
# ---------------------------------------------------------------------------


class TestTruncateInput:
    def test_short_text_unchanged(self) -> None:
        with override_settings(OPENAI_REVIEW_TEXT_MAX_CHARS=4000):
            text = "Short review text."
            assert _truncate_input(text) == text

    def test_long_text_truncated_with_suffix(self) -> None:
        with override_settings(OPENAI_REVIEW_TEXT_MAX_CHARS=50):
            text = "x" * 200
            result = _truncate_input(text)
            assert result.endswith("…[truncated]")
            assert len(result) <= 50


# ---------------------------------------------------------------------------
# TestTruncateReplyAtSentence — D-08 / D-22
# ---------------------------------------------------------------------------


class TestTruncateReplyAtSentence:
    def test_short_reply_unchanged(self) -> None:
        text = "Thank you for your kind review. We appreciate your feedback."
        assert truncate_reply_at_sentence(text) == text

    def test_long_reply_truncated_at_sentence_boundary(self) -> None:
        # Build three sentences: 150 + 145 + 50 = 345 words. Sentence 1+2 = 295
        # words (fits under 300); adding sentence 3 would overshoot. Result
        # should contain sentences 1+2 and the canonical suffix; sentence 3
        # must not appear.
        sentence_1 = " ".join(["alpha"] * 150) + "."
        sentence_2 = " ".join(["beta"] * 145) + "."
        sentence_3 = " ".join(["gamma"] * 50) + "."
        text = f"{sentence_1} {sentence_2} {sentence_3}"

        result = truncate_reply_at_sentence(text)

        assert result.endswith(" (Please review and complete before sending.)")
        assert "gamma" not in result
        assert "alpha" in result
        assert "beta" in result


# ---------------------------------------------------------------------------
# TestEvaluateAndBlockingCategories — D-23 / D-30 (Pitfall 1 regression)
# ---------------------------------------------------------------------------


class TestEvaluateAndBlockingCategories:
    def test_underscore_self_harm_intent_blocks(self) -> None:
        response = _mod_response({"self_harm_intent": True, "harassment": False})
        blocked, flagged = _evaluate(response)
        assert blocked is True
        assert flagged == ["self_harm_intent"]

    def test_low_severity_categories_do_not_block(self) -> None:
        response = _mod_response({"harassment": True, "sexual": True, "violence": True})
        blocked, flagged = _evaluate(response)
        assert blocked is False
        # All three keys should appear in flagged, sorted alphabetically.
        assert flagged == sorted(["harassment", "sexual", "violence"])

    def test_no_categories_flagged_returns_false(self) -> None:
        response = _mod_response({"harassment": False, "violence": False})
        blocked, flagged = _evaluate(response)
        assert blocked is False
        assert flagged == []

    def test_blocking_categories_constant_underscore_form(self) -> None:
        # Pitfall 1 regression — guard against a future "fix" back to slash.
        assert "self_harm_intent" in BLOCKING_MODERATION_CATEGORIES
        assert "self-harm/intent" not in BLOCKING_MODERATION_CATEGORIES
        # Spot-check the other four members.
        for cat in (
            "sexual_minors",
            "hate_threatening",
            "violence_graphic",
            "self_harm_instructions",
        ):
            assert cat in BLOCKING_MODERATION_CATEGORIES


# ---------------------------------------------------------------------------
# TestModerateInput — D-01 / D-04 / D-21 / D-33 (+ Pitfall 2 regression)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestModerateInput:
    def test_moderate_input_calls_api_once_with_correct_model(self) -> None:
        with patch(_PATCH_TARGET, return_value=_mod_response({})) as mock_call:
            result = moderate_input("clean review")
        assert mock_call.call_count == 1
        assert result == "clean review"

    def test_moderate_input_returns_truncated_text_when_clean(self) -> None:
        with (
            override_settings(OPENAI_REVIEW_TEXT_MAX_CHARS=50),
            patch(_PATCH_TARGET, return_value=_mod_response({})),
        ):
            result = moderate_input("x" * 200)
        assert result.endswith("…[truncated]")
        assert len(result) <= 50

    def test_moderate_input_blocks_high_severity_raises_content_moderated_exception(
        self,
    ) -> None:
        with (
            patch(_PATCH_TARGET, return_value=_mod_response({"self_harm_intent": True})),
            pytest.raises(ContentModeratedException),
        ):
            moderate_input("bad review")

    def test_moderate_input_writes_moderated_aiusagelog_when_review_provided(self) -> None:
        review = ReviewFactory()
        with (
            patch(_PATCH_TARGET, return_value=_mod_response({"self_harm_intent": True})),
            pytest.raises(ContentModeratedException),
        ):
            moderate_input("bad review", review=review)

        row = AiUsageLog.objects.get(review=review)
        assert row.status == "MODERATED"
        assert row.error_code == "content_moderated"
        assert row.prompt_tokens == 0
        assert row.completion_tokens == 0
        assert row.estimated_cost_usd == Decimal("0")

    def test_moderate_input_skips_aiusagelog_when_review_none(self) -> None:
        before = AiUsageLog.objects.count()
        with (
            patch(_PATCH_TARGET, return_value=_mod_response({"self_harm_intent": True})),
            pytest.raises(ContentModeratedException),
        ):
            moderate_input("bad review", review=None)
        assert AiUsageLog.objects.count() == before

    def test_moderate_input_aiusagelog_status_uppercase(self) -> None:
        # Pitfall 2 regression — the persisted status MUST be the literal
        # uppercase string "MODERATED" so admin/dashboard filters keyed on
        # AiUsageLog.Status.MODERATED match the row.
        review = ReviewFactory()
        with (
            patch(_PATCH_TARGET, return_value=_mod_response({"self_harm_intent": True})),
            pytest.raises(ContentModeratedException),
        ):
            moderate_input("bad review", review=review)

        row = AiUsageLog.objects.get(review=review)
        assert row.status == "MODERATED"


# ---------------------------------------------------------------------------
# TestModerateOutput — D-07 / D-08 / D-29
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestModerateOutput:
    def test_moderate_output_returns_text_when_clean(self) -> None:
        with patch(_PATCH_TARGET, return_value=_mod_response({})):
            result = moderate_output("Thanks for your review!")
        assert result == "Thanks for your review!"

    def test_moderate_output_blocks_and_raises(self) -> None:
        with (
            patch(_PATCH_TARGET, return_value=_mod_response({"violence_graphic": True})),
            pytest.raises(ContentModeratedException),
        ):
            moderate_output("Some flagged generated content")

    def test_moderate_output_writes_aiusagelog_with_real_tokens(self) -> None:
        review = ReviewFactory()
        usage = {
            "prompt_tokens": 150,
            "completion_tokens": 80,
            "cached_tokens": 0,
            "total_tokens": 230,
            "estimated_cost_usd": Decimal("0.000234"),
        }
        with (
            patch(_PATCH_TARGET, return_value=_mod_response({"violence_graphic": True})),
            pytest.raises(ContentModeratedException),
        ):
            moderate_output("bad output", review=review, usage_data=usage)

        row = AiUsageLog.objects.get(review=review)
        assert row.status == "MODERATED"
        assert row.error_code == "output_moderated"
        assert row.prompt_tokens == 150
        assert row.completion_tokens == 80
        assert row.total_tokens == 230
        assert row.estimated_cost_usd == Decimal("0.000234")


# ---------------------------------------------------------------------------
# TestFailOpenRetry — D-24
# ---------------------------------------------------------------------------


class TestFailOpenRetry:
    def test_fail_open_first_call_succeeds_no_retry(self) -> None:
        with (
            patch(_PATCH_TARGET, return_value=_mod_response({})) as mock_call,
            patch(_SLEEP_TARGET) as mock_sleep,
        ):
            result = moderate_input("clean review")
        assert result == "clean review"
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()

    def test_fail_open_first_call_fails_retry_succeeds(self) -> None:
        # First call raises APIConnectionError; second call returns clean.
        with (
            patch(
                _PATCH_TARGET,
                side_effect=[_connection_error(), _mod_response({})],
            ) as mock_call,
            patch(_SLEEP_TARGET) as mock_sleep,
        ):
            result = moderate_input("clean review")
        assert result == "clean review"
        assert mock_call.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    def test_fail_open_both_calls_fail_returns_unblocked_and_logs_error(self, caplog) -> None:
        # Both attempts raise RateLimitError — must fail-open (return text,
        # no raise) and emit an ERROR log. We don't write AiUsageLog on a
        # fail-open path because nothing was actually blocked.
        with (
            patch(
                _PATCH_TARGET,
                side_effect=[_rate_limit_error(), _rate_limit_error()],
            ),
            patch(_SLEEP_TARGET),
            caplog.at_level("ERROR", logger="apps.integrations.openai.guardrails"),
        ):
            result = moderate_input("clean review")

        assert result == "clean review"
        assert any("ai.moderation.errored" in rec.message for rec in caplog.records)
