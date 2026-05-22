"""Phase 12 — OpenAI client wrapper for review enrichment.

Exposes one public entry point: call_openai_enrichment(review, model).
  - Builds the prompt via build_enrichment_messages
  - Calls client.responses.parse(text_format=EnrichmentResult)
  - Wraps with @traceable for LangSmith (best-effort per ENRCH-11)
  - Maps openai SDK exceptions to OpenAITransientError / OpenAIPermanentError /
    EnrichmentParseError (Plan 04's Celery autoretry_for understands these)
  - Returns (EnrichmentResult, usage_data) with usage_data using Chat-Completions
    key names so the rest of the codebase stays stable across SDK API changes
    (RESEARCH.md Pitfall 2)

NEVER call this directly without mocking in tests — set
CELERY_TASK_ALWAYS_EAGER=True in test settings (already done) AND patch
_call_openai_with_tracing in pytest.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import openai
from django.conf import settings
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from openai import OpenAI

from apps.integrations.openai.exceptions import (
    EnrichmentParseError,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.parser import EnrichmentResult
from apps.integrations.openai.prompts import (
    build_enrichment_messages,
    build_reply_generation_messages,
)

logger = logging.getLogger(__name__)

# Lazy singleton — module-level initialisation is deferred to first call so
# import-time access to settings.OPENAI_API_KEY does not fail when the key is
# empty in test settings (mock patches _do_responses_parse before any real
# call is made, so the SDK client is never exercised in tests).
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = settings.OPENAI_API_KEY
        _client = OpenAI(api_key=api_key) if api_key else OpenAI()
    return _client


def _map_openai_error(exc: Exception) -> Exception:
    """Translate openai SDK exceptions to our custom hierarchy."""
    if isinstance(exc, openai.RateLimitError):
        return OpenAITransientError(str(exc))
    if isinstance(exc, openai.APIStatusError):
        status_code = getattr(exc, "status_code", None)
        if status_code is not None and status_code >= 500:
            return OpenAITransientError(str(exc))
        return OpenAIPermanentError(str(exc), status_code=status_code)
    return exc


def _extract_usage(response: Any, *, latency_ms: int, trace_id: str | None) -> dict[str, Any]:
    """Extract token usage from a Responses API response.

    Field name mapping (RESEARCH.md Pitfall 2):
      input_tokens                              -> prompt_tokens
      output_tokens                             -> completion_tokens
      input_tokens_details.cached_tokens or 0   -> cached_tokens
      total_tokens                              -> total_tokens
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
            "latency_ms": latency_ms,
            "langsmith_trace_id": trace_id,
        }
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    details = getattr(usage, "input_tokens_details", None)
    cached_tokens = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "langsmith_trace_id": trace_id,
    }


def _do_responses_parse(*, messages: list[dict[str, str]], model: str) -> Any:
    """Single SDK call. Maps SDK errors to our exception hierarchy."""
    try:
        # Cast messages to Any to satisfy the openai SDK's complex input union
        # type — list[dict[str, str]] is accepted at runtime but not statically.
        return _get_client().responses.parse(
            model=model,
            input=messages,  # type: ignore[arg-type]
            text_format=EnrichmentResult,
        )
    except (openai.RateLimitError, openai.APIStatusError) as exc:
        raise _map_openai_error(exc) from exc


@traceable(run_type="llm", name="enrich_review")
def _call_openai_with_tracing(
    *,
    messages: list[dict[str, str]],
    model: str,
    review_id: int | None = None,
    organisation_id: int | None = None,
    shop_id: int | None = None,
) -> tuple[Any, str | None]:
    """LangSmith-traced path. Captures trace_id and attaches entity metadata.

    Entity IDs (review_id, organisation_id, shop_id, model, request_type) are
    attached to run_tree.metadata per CLAUDE.md §14.5 so LangSmith traces can
    be cross-referenced from AiUsageLog rows. Best-effort: metadata update
    failure does not block the OpenAI call.

    Also attaches `usage_metadata` and `ls_model_name` to the run so LangSmith's
    pricing engine can compute the Cost column. The Responses API exposes usage
    as `response.usage.input_tokens / output_tokens / total_tokens`, which
    matches LangSmith's UsageMetadata schema 1:1 (no remapping needed). Without
    these, LangSmith renders Cost as $0.00 even though tokens are present in
    the underlying response — see debug session
    .planning/debug/resolved/langsmith-cost-not-shown.md.
    """
    response = _do_responses_parse(messages=messages, model=model)
    trace_id: str | None = None
    try:
        run_tree = get_current_run_tree()
        if run_tree is not None:
            trace_id = str(run_tree.trace_id)
            metadata_update: dict[str, Any] = {
                "request_type": "enrichment",
                "review_id": review_id,
                "organisation_id": organisation_id,
                "shop_id": shop_id,
                "model": model,
                # ls_model_name is the key LangSmith's pricing lookup uses
                # (see langsmith.wrappers._openai). Setting it explicitly
                # ensures cost rendering for snapshot model IDs like
                # gpt-4o-mini-2024-07-18.
                "ls_model_name": model,
            }
            usage = getattr(response, "usage", None)
            if usage is not None:
                input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
                total_tokens = int(
                    getattr(usage, "total_tokens", input_tokens + output_tokens) or 0
                )
                usage_metadata: dict[str, Any] = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                }
                details = getattr(usage, "input_tokens_details", None)
                cached_tokens = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
                if cached_tokens:
                    # LangSmith's InputTokenDetails uses `cache_read` for
                    # cached/cache-hit tokens (matches Anthropic/OpenAI cache
                    # conventions). Optional — only include when non-zero.
                    usage_metadata["input_token_details"] = {
                        "cache_read": cached_tokens,
                    }
                metadata_update["usage_metadata"] = usage_metadata
            run_tree.metadata.update(metadata_update)
    except Exception:  # pragma: no cover — defensive
        trace_id = None
    return response, trace_id


def call_openai_enrichment(
    *,
    review: Any,
    model: str | None = None,
) -> tuple[EnrichmentResult, dict[str, Any]]:
    """Run a single enrichment call. Returns (EnrichmentResult, usage_data).

    Best-effort LangSmith per ENRCH-11: if the traced path raises a non-OpenAI
    exception (LangSmith init / shipping failure), fall back to an untraced
    direct call so the OpenAI request still proceeds. trace_id becomes None.
    """
    use_model = model or settings.OPENAI_MODEL
    messages = build_enrichment_messages(review=review)
    started = time.monotonic()
    response: Any
    trace_id: str | None = None
    try:
        response, trace_id = _call_openai_with_tracing(
            messages=messages,
            model=use_model,
            review_id=getattr(review, "pk", None),
            organisation_id=getattr(review, "organisation_id", None),
            shop_id=getattr(review, "shop_id", None),
        )
    except (OpenAITransientError, OpenAIPermanentError):
        raise
    except (openai.RateLimitError, openai.APIStatusError) as exc:
        # Raw SDK errors propagated from the traced path (e.g., when patching
        # _do_responses_parse in tests) must be mapped to our hierarchy.
        raise _map_openai_error(exc) from exc
    except Exception as exc:  # LangSmith init / shipping failure
        logger.warning(
            "langsmith_best_effort_fallback exc_type=%s exc=%s",
            type(exc).__name__,
            exc,
        )
        response = _do_responses_parse(messages=messages, model=use_model)
        trace_id = None
    latency_ms = int((time.monotonic() - started) * 1000)

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise EnrichmentParseError(
            "openai responses.parse returned output_parsed=None "
            "(model refused or schema validation failed)"
        )
    if not isinstance(
        parsed, EnrichmentResult
    ):  # defensive — SDK normally returns the typed instance
        parsed = EnrichmentResult.model_validate(parsed)

    usage_data = _extract_usage(response, latency_ms=latency_ms, trace_id=trace_id)
    return parsed, usage_data


# ---------------------------------------------------------------------------
# Phase 19 — AI reply generation client
#
# Mirrors call_openai_enrichment but exercises the Chat Completions API
# (D-07: response_format={"type": "text"} — plain text, not structured JSON).
# Token field names use Chat Completions conventions (prompt_tokens /
# completion_tokens), so usage extraction does NOT reuse _extract_usage().
# ---------------------------------------------------------------------------


def _extract_reply_usage(response: Any, *, latency_ms: int, trace_id: str | None) -> dict[str, Any]:
    """Extract token usage from a Chat Completions API response.

    Field name mapping (Chat Completions, NOT Responses API):
      prompt_tokens                                   -> prompt_tokens
      completion_tokens                               -> completion_tokens
      prompt_tokens_details.cached_tokens or 0        -> cached_tokens
      total_tokens                                    -> total_tokens
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
            "latency_ms": latency_ms,
            "langsmith_trace_id": trace_id,
        }
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "langsmith_trace_id": trace_id,
    }


def _do_chat_completions_create(*, messages: list[dict[str, str]], model: str) -> Any:
    """Single SDK call to chat.completions.create. Maps SDK errors."""
    try:
        # The SDK's chat.completions.create overloads are heavily-typed
        # (TypedDict unions per message role + ResponseFormatText for the
        # response_format param); our plain dicts are accepted at runtime.
        # Cast through Any to satisfy mypy without re-typing every message.
        from typing import cast

        return _get_client().chat.completions.create(
            model=model,
            messages=cast(Any, messages),
            response_format=cast(Any, {"type": "text"}),
        )
    except (openai.RateLimitError, openai.APIStatusError) as exc:
        raise _map_openai_error(exc) from exc


@traceable(run_type="llm", name="generate_reply")
def _call_openai_reply_with_tracing(
    *,
    messages: list[dict[str, str]],
    model: str,
    review_id: int | None = None,
    organisation_id: int | None = None,
    shop_id: int | None = None,
) -> tuple[Any, str | None]:
    """LangSmith-traced reply generation path. Best-effort metadata attach."""
    response = _do_chat_completions_create(messages=messages, model=model)
    trace_id: str | None = None
    try:
        run_tree = get_current_run_tree()
        if run_tree is not None:
            trace_id = str(run_tree.trace_id)
            metadata_update: dict[str, Any] = {
                "request_type": "reply_generation",
                "review_id": review_id,
                "organisation_id": organisation_id,
                "shop_id": shop_id,
                "model": model,
                "ls_model_name": model,
            }
            usage = getattr(response, "usage", None)
            if usage is not None:
                input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                total_tokens = int(
                    getattr(usage, "total_tokens", input_tokens + output_tokens) or 0
                )
                usage_metadata: dict[str, Any] = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                }
                details = getattr(usage, "prompt_tokens_details", None)
                cached_tokens = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
                if cached_tokens:
                    usage_metadata["input_token_details"] = {
                        "cache_read": cached_tokens,
                    }
                metadata_update["usage_metadata"] = usage_metadata
            run_tree.metadata.update(metadata_update)
    except Exception:  # pragma: no cover — defensive
        trace_id = None
    return response, trace_id


def call_openai_reply_generation(
    *,
    review: Any,
    tone: str,
    model: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run a single reply-generation call. Returns (draft_text, usage_data).

    Best-effort LangSmith per D-15 / §14.5: if the traced path raises a
    non-OpenAI exception (LangSmith init / shipping failure), fall back to
    an untraced direct call so the OpenAI request still proceeds.
    """
    use_model = model or settings.OPENAI_MODEL
    brand_name = review.shop.organisation.name
    messages = build_reply_generation_messages(review=review, tone=tone, brand_name=brand_name)
    started = time.monotonic()
    response: Any
    trace_id: str | None = None
    try:
        response, trace_id = _call_openai_reply_with_tracing(
            messages=messages,
            model=use_model,
            review_id=getattr(review, "pk", None),
            organisation_id=getattr(review, "organisation_id", None),
            shop_id=getattr(review, "shop_id", None),
        )
    except (OpenAITransientError, OpenAIPermanentError):
        raise
    except (openai.RateLimitError, openai.APIStatusError) as exc:
        raise _map_openai_error(exc) from exc
    except Exception as exc:  # LangSmith init / shipping failure
        logger.warning(
            "langsmith_best_effort_fallback_reply exc_type=%s exc=%s",
            type(exc).__name__,
            exc,
        )
        response = _do_chat_completions_create(messages=messages, model=use_model)
        trace_id = None
    latency_ms = int((time.monotonic() - started) * 1000)

    choices = getattr(response, "choices", None) or []
    if not choices:
        raise OpenAIPermanentError(
            "openai chat.completions returned no choices for reply generation"
        )
    draft = getattr(choices[0].message, "content", None) or ""

    usage_data = _extract_reply_usage(response, latency_ms=latency_ms, trace_id=trace_id)
    return draft, usage_data
