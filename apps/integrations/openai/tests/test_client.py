"""Phase 12 — OpenAI client wrapper tests.

NEVER hits real OpenAI. _do_responses_parse is patched in every test that
exercises a SDK call. LangSmith is forced off by config/settings/test.py
(LANGSMITH_TRACING=false) so @traceable is a no-op unless explicitly tested.

Covers:
  ENRCH-01 — structured parse + token mapping (test_success)
  ENRCH-04 — error mapping (test_rate_limit_raises_transient,
              test_5xx_raises_transient, test_4xx_other_than_429_raises_permanent,
              test_output_parsed_none_raises_parse_error)
  ENRCH-11 — LangSmith best-effort (test_langsmith_best_effort)
  ENRCH-12 — trace id capture (test_trace_id_captured)
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import openai
import pytest

from apps.integrations.openai.client import (
    call_openai_enrichment,
    call_openai_reply_generation,
)
from apps.integrations.openai.exceptions import (
    EnrichmentParseError,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.parser import EnrichmentResult
from apps.reviews.tests.factories import ReviewFactory

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _build_response(*, parsed: EnrichmentResult, cached_tokens: int = 0) -> SimpleNamespace:
    """Build a Mock response matching the Responses API shape."""
    details = SimpleNamespace(cached_tokens=cached_tokens)
    usage = SimpleNamespace(
        input_tokens=500,
        output_tokens=200,
        total_tokens=700,
        input_tokens_details=details,
    )
    return SimpleNamespace(output_parsed=parsed, usage=usage)


def _load_fixture() -> EnrichmentResult:
    payload = json.loads((FIXTURE_DIR / "enrichment_success.json").read_text())
    return EnrichmentResult.model_validate(payload)


@pytest.mark.django_db
def test_success_returns_parsed_and_usage_data() -> None:
    """ENRCH-01: structured parse returns EnrichmentResult + correctly mapped usage."""
    review = ReviewFactory()
    parsed = _load_fixture()
    response = _build_response(parsed=parsed, cached_tokens=100)

    with patch(
        "apps.integrations.openai.client._do_responses_parse",
        return_value=response,
    ):
        result, usage_data = call_openai_enrichment(review=review)

    assert isinstance(result, EnrichmentResult)
    assert result.sentiment == "positive"
    assert usage_data["prompt_tokens"] == 500
    assert usage_data["completion_tokens"] == 200
    assert usage_data["cached_tokens"] == 100
    assert usage_data["total_tokens"] == 700
    assert usage_data["latency_ms"] >= 0
    # LangSmith forced off in test settings -> trace id is None.
    assert usage_data["langsmith_trace_id"] is None


@pytest.mark.django_db
def test_cached_tokens_default_zero_when_details_missing() -> None:
    """RESEARCH.md Pitfall 2 / community issue: input_tokens_details may be None."""
    review = ReviewFactory()
    parsed = _load_fixture()
    response = SimpleNamespace(
        output_parsed=parsed,
        usage=SimpleNamespace(
            input_tokens=500,
            output_tokens=200,
            total_tokens=700,
            input_tokens_details=None,
        ),
    )
    with patch(
        "apps.integrations.openai.client._do_responses_parse",
        return_value=response,
    ):
        _, usage_data = call_openai_enrichment(review=review)
    assert usage_data["cached_tokens"] == 0


@pytest.mark.django_db
def test_rate_limit_raises_transient() -> None:
    """ENRCH-04: 429 -> OpenAITransientError so Celery autoretry_for triggers."""
    review = ReviewFactory()
    err = openai.RateLimitError(
        message="rate limited",
        response=MagicMock(),
        body=None,
    )
    with (
        patch(
            "apps.integrations.openai.client._do_responses_parse",
            side_effect=err,
        ),
        pytest.raises(OpenAITransientError),
    ):
        call_openai_enrichment(review=review)


@pytest.mark.django_db
def test_5xx_raises_transient() -> None:
    """ENRCH-04: 5xx -> OpenAITransientError."""
    review = ReviewFactory()
    err = openai.APIStatusError(
        message="server error",
        response=MagicMock(status_code=503),
        body=None,
    )
    err.status_code = 503  # ensure attribute is set
    with (
        patch(
            "apps.integrations.openai.client._do_responses_parse",
            side_effect=err,
        ),
        pytest.raises(OpenAITransientError),
    ):
        call_openai_enrichment(review=review)


@pytest.mark.django_db
def test_4xx_other_than_429_raises_permanent() -> None:
    """ENRCH-04: 4xx (other than 429) -> OpenAIPermanentError, no retry."""
    review = ReviewFactory()
    err = openai.APIStatusError(
        message="bad request",
        response=MagicMock(status_code=400),
        body=None,
    )
    err.status_code = 400
    with (
        patch(
            "apps.integrations.openai.client._do_responses_parse",
            side_effect=err,
        ),
        pytest.raises(OpenAIPermanentError),
    ):
        call_openai_enrichment(review=review)


@pytest.mark.django_db
def test_output_parsed_none_raises_parse_error() -> None:
    """ENRCH-04: model refusal / schema failure -> EnrichmentParseError (retried once)."""
    review = ReviewFactory()
    response = SimpleNamespace(
        output_parsed=None,
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=0,
            total_tokens=10,
            input_tokens_details=None,
        ),
    )
    with (
        patch(
            "apps.integrations.openai.client._do_responses_parse",
            return_value=response,
        ),
        pytest.raises(EnrichmentParseError),
    ):
        call_openai_enrichment(review=review)


@pytest.mark.django_db
def test_langsmith_best_effort() -> None:
    """ENRCH-11: LangSmith init / shipping failure must NOT block the OpenAI call.

    Patch _call_openai_with_tracing to raise RuntimeError (simulating a
    LangSmith library failure during the traced call). The wrapper must
    fall back to _do_responses_parse and return a valid result with
    langsmith_trace_id=None.
    """
    review = ReviewFactory()
    parsed = _load_fixture()
    response = _build_response(parsed=parsed)

    with (
        patch(
            "apps.integrations.openai.client._call_openai_with_tracing",
            side_effect=RuntimeError("langsmith api down"),
        ),
        patch(
            "apps.integrations.openai.client._do_responses_parse",
            return_value=response,
        ),
    ):
        result, usage_data = call_openai_enrichment(review=review)

    assert isinstance(result, EnrichmentResult)
    assert usage_data["langsmith_trace_id"] is None


@pytest.mark.django_db
def test_trace_id_captured_from_run_tree() -> None:
    """ENRCH-12: trace_id is captured from get_current_run_tree() and surfaced.

    Patches the langsmith.run_helpers.get_current_run_tree call inside the
    @traceable function so it returns a Mock with .trace_id set.
    """
    review = ReviewFactory()
    parsed = _load_fixture()
    response = _build_response(parsed=parsed)
    fake_trace = uuid4()

    fake_run_tree = MagicMock()
    fake_run_tree.trace_id = fake_trace

    with (
        patch(
            "apps.integrations.openai.client._do_responses_parse",
            return_value=response,
        ),
        patch(
            "apps.integrations.openai.client.get_current_run_tree",
            return_value=fake_run_tree,
        ),
    ):
        _, usage_data = call_openai_enrichment(review=review)

    assert usage_data["langsmith_trace_id"] == str(fake_trace)


# ---------------------------------------------------------------------------
# Phase 19 — call_openai_reply_generation tests
#
# Mirrors the enrichment test structure but exercises the Chat Completions
# code path (not Responses API). Token fields use Chat Completions naming:
# prompt_tokens / completion_tokens (NOT input_tokens / output_tokens).
# ---------------------------------------------------------------------------


def _build_chat_response(
    *,
    content: str = "Thanks so much for the kind review!",
    prompt_tokens: int = 120,
    completion_tokens: int = 60,
    cached_tokens: int = 0,
) -> SimpleNamespace:
    """Build a Mock chat.completions.create response."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    details = SimpleNamespace(cached_tokens=cached_tokens)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        prompt_tokens_details=details,
    )
    return SimpleNamespace(choices=[choice], usage=usage)


class TestCallOpenAiReplyGeneration:
    @pytest.mark.django_db
    def test_returns_draft_and_usage_data(self) -> None:
        """Success path returns (draft_text, usage_dict) with Chat Completions token mapping."""
        review = ReviewFactory()
        response = _build_chat_response(
            content="Hi there! Thanks for visiting.",
            prompt_tokens=100,
            completion_tokens=50,
            cached_tokens=20,
        )
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = response
        with patch(
            "apps.integrations.openai.client._get_client",
            return_value=fake_client,
        ):
            draft, usage = call_openai_reply_generation(review=review, tone="professional")

        assert draft == "Hi there! Thanks for visiting."
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["cached_tokens"] == 20
        assert usage["total_tokens"] == 150
        assert usage["latency_ms"] >= 0
        assert "langsmith_trace_id" in usage
        # Verify chat.completions.create was called with response_format text
        call_kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "text"}
        # messages list shape sanity check
        assert isinstance(call_kwargs["messages"], list)
        assert call_kwargs["messages"][0]["role"] == "system"

    @pytest.mark.django_db
    def test_rate_limit_raises_transient(self) -> None:
        """429 -> OpenAITransientError."""
        review = ReviewFactory()
        err = openai.RateLimitError(
            message="rate limited",
            response=MagicMock(),
            body=None,
        )
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = err
        with (
            patch(
                "apps.integrations.openai.client._get_client",
                return_value=fake_client,
            ),
            pytest.raises(OpenAITransientError),
        ):
            call_openai_reply_generation(review=review, tone="professional")

    @pytest.mark.django_db
    def test_5xx_raises_transient(self) -> None:
        """5xx -> OpenAITransientError."""
        review = ReviewFactory()
        err = openai.APIStatusError(
            message="server error",
            response=MagicMock(status_code=503),
            body=None,
        )
        err.status_code = 503
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = err
        with (
            patch(
                "apps.integrations.openai.client._get_client",
                return_value=fake_client,
            ),
            pytest.raises(OpenAITransientError),
        ):
            call_openai_reply_generation(review=review, tone="friendly")

    @pytest.mark.django_db
    def test_4xx_raises_permanent(self) -> None:
        """4xx other than 429 -> OpenAIPermanentError."""
        review = ReviewFactory()
        err = openai.APIStatusError(
            message="bad request",
            response=MagicMock(status_code=400),
            body=None,
        )
        err.status_code = 400
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = err
        with (
            patch(
                "apps.integrations.openai.client._get_client",
                return_value=fake_client,
            ),
            pytest.raises(OpenAIPermanentError),
        ):
            call_openai_reply_generation(review=review, tone="professional")
