"""Phase 20 — AI safety guardrails for OpenAI calls.

Two public entry points:
  - moderate_input(text, *, review=None, request_type="enrichment") -> str
      Truncates input to OPENAI_REVIEW_TEXT_MAX_CHARS (D-03/D-21), then runs the
      OpenAI Moderation API on the (truncated) text. Raises
      ContentModeratedException on a high-severity category hit (D-04/D-23/D-30).
      When a Review is provided, writes a MODERATED AiUsageLog row BEFORE raising
      (D-33; written outside any caller atomic block so a downstream rollback
      cannot erase the safety-event audit row).

  - moderate_output(text, *, review=None, request_type="reply_generation",
                    usage_data=None) -> str
      Runs the Moderation API on a generated reply. Raises
      ContentModeratedException on a high-severity category hit (D-07). The
      AiUsageLog row written on a block carries REAL tokens/cost from
      `usage_data` per D-29 (the OpenAI call did execute and consumed tokens
      before output moderation fired), with error_code="output_moderated".

Plus one length helper that is part of the public surface so Plan 20-06's reply
service can apply it post-success:

  - truncate_reply_at_sentence(text) -> str
      Trims a generated reply to at most 300 words at the last sentence boundary
      that fits, appending the canonical suffix. D-08/D-22.

Design notes:
  - Fail-open with ONE retry per D-24. If the Moderation API itself fails twice,
    `_moderate_with_retry` logs at ERROR and returns (False, []) so the caller
    proceeds with the OpenAI call. Trade-off: brief unsafe window; OpenAI's own
    policy enforcement is the backstop.
  - NEVER decorated with LangSmith tracing. Moderation is an operational
    safety check, not a billable generation; visibility comes from the
    `ai.moderation.flagged` / `ai.moderation.errored` log events.
  - NEVER wrapped in a Django atomic block. Audit-row survival on rollback is
    a hard requirement (D-33). See `_persist_moderated_log` docstring.
  - Review text is NEVER logged at any level. Only category names and entity
    IDs appear in WARNING / ERROR records (CLAUDE.md §21).
"""

from __future__ import annotations

import logging
import re
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import openai
from django.conf import settings

from apps.integrations.openai.client import _get_client
from apps.integrations.openai.exceptions import ContentModeratedException
from apps.integrations.openai.models import AiUsageLog

if TYPE_CHECKING:  # pragma: no cover — type-only import to avoid cycle
    from apps.reviews.models import Review

logger = logging.getLogger(__name__)

# Underscore form matches Pydantic field names (default model_dump); slash form
# is the SDK JSON alias and only appears with model_dump(by_alias=True). Do NOT
# "fix" to slash form — see RESEARCH.md Pitfall 1 + D-30. Verified against the
# installed openai SDK by introspecting Categories.model_fields.
BLOCKING_MODERATION_CATEGORIES: frozenset[str] = frozenset(
    {
        "sexual_minors",
        "hate_threatening",
        "violence_graphic",
        "self_harm_intent",
        "self_harm_instructions",
    }
)

_MODERATION_MODEL = "omni-moderation-latest"
_TRUNCATION_SUFFIX = "…[truncated]"
_REPLY_WORD_CAP = 300
_REPLY_SUFFIX = " (Please review and complete before sending.)"

# SDK exceptions considered transient for the one-retry fail-open path (D-24).
# Retained for documentation/back-compat; the actual retry loop below catches
# the broader `Exception` to satisfy the D-24 contract verbatim ("if the call
# raises ... retry once. If the retry also fails, proceed with the OpenAI
# call"). Narrow tuples here would let a non-SDK exception (e.g.
# httpx.RequestError, AttributeError from a future SDK shape change, or any
# openai.OpenAIError subclass outside this tuple) bypass the fail-open
# contract and surface as a hard failure to enrichment / reply generation.
_MODERATION_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    openai.RateLimitError,
    openai.APIStatusError,
    openai.APIConnectionError,
)


# --- Internal helpers ---------------------------------------------------------


def _truncate_input(text: str) -> str:
    """Cap text at settings.OPENAI_REVIEW_TEXT_MAX_CHARS with `…[truncated]` suffix."""
    cap = settings.OPENAI_REVIEW_TEXT_MAX_CHARS
    if len(text) <= cap:
        return text
    head_len = cap - len(_TRUNCATION_SUFFIX)
    if head_len < 0:
        head_len = 0
    return text[:head_len] + _TRUNCATION_SUFFIX


def truncate_reply_at_sentence(text: str) -> str:
    """Trim a reply to ≤300 words at the last sentence boundary that fits.

    D-08/D-22 — public so the reply service (Plan 20-06) can apply it
    post-success. If even the first sentence exceeds the cap, falls back to a
    hard word-count cut with the same canonical suffix. Returns the input
    unchanged when the original is already within the cap.
    """
    words = text.split()
    if len(words) <= _REPLY_WORD_CAP:
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    accumulated: list[str] = []
    running = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if running + sentence_words > _REPLY_WORD_CAP:
            break
        accumulated.append(sentence)
        running += sentence_words

    if accumulated:
        joined = " ".join(accumulated).rstrip()
        return joined + _REPLY_SUFFIX

    # First sentence already exceeds the cap — fall back to word-count truncation.
    return " ".join(words[:_REPLY_WORD_CAP]) + _REPLY_SUFFIX


def _call_moderation_api(text: str) -> Any:
    """One Moderation API call. Caller (`_moderate_with_retry`) handles retry."""
    return _get_client().moderations.create(input=text, model=_MODERATION_MODEL)


def _evaluate(response: Any) -> tuple[bool, list[str]]:
    """Return (blocked, flagged_categories).

    `flagged` is the sorted list of underscore-form category names that the
    Moderation API marked True. `blocked` is True iff any of those falls in
    BLOCKING_MODERATION_CATEGORIES (D-23/D-30).
    """
    cats = response.results[0].categories.model_dump()  # underscore keys per D-30
    flagged = sorted(k for k, v in cats.items() if v)
    blocked = any(k in BLOCKING_MODERATION_CATEGORIES for k in flagged)
    return blocked, flagged


def _moderate_with_retry(
    text: str, *, stage: str, entity_id: int | str | None
) -> tuple[bool, list[str]]:
    """Run the Moderation API with one 1s-delayed retry (D-24).

    On second failure: log ERROR `ai.moderation.errored` and return (False, [])
    so the caller fails open. Never raises.

    The except clause is intentionally `Exception` (not the narrow
    `_MODERATION_TRANSIENT_EXCEPTIONS` tuple) to honour D-24 verbatim — "if
    the call raises (network, 5xx, rate limit), retry once... If the retry
    also fails, proceed with the OpenAI call". Any non-transient raise
    (httpx error, AttributeError from a future SDK shape change, generic
    OpenAIError subclass) must still fail open rather than crashing the
    enrichment task or returning HTTP 502 from the reply view. Per
    CLAUDE.md §21, we log only the error class name + sanitized message —
    never the moderation input text.
    """
    last_exc: BaseException | None = None
    for attempt in (1, 2):
        try:
            resp = _call_moderation_api(text)
            return _evaluate(resp)
        except Exception as exc:
            last_exc = exc
            if attempt == 1:
                time.sleep(1.0)
                continue
            break
    logger.error(
        "ai.moderation.errored stage=%s entity_id=%s error_class=%s error=%s",
        stage,
        entity_id,
        type(last_exc).__name__ if last_exc is not None else "",
        last_exc,
    )
    return False, []


def _persist_moderated_log(
    *,
    review: Review,
    stage: str,
    flagged: list[str],
    request_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
    total_tokens: int = 0,
    estimated_cost_usd: Decimal = Decimal("0"),
) -> None:
    """Write a MODERATED AiUsageLog row.

    NOT wrapped in a Django atomic block per D-33: if the caller is inside an
    atomic block that later rolls back, this audit row must still survive so
    the safety event is preserved. Callers are responsible for invoking
    `moderate_*` OUTSIDE their atomic blocks.
    """
    error_code = "content_moderated" if stage == "input" else "output_moderated"
    AiUsageLog.objects.create(
        organisation_id=review.organisation_id,
        review_id=review.pk,
        request_type=request_type,
        model=settings.OPENAI_MODEL,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        status=AiUsageLog.Status.MODERATED,
        error_code=error_code,
        error_message=f"flagged_categories={flagged}",
    )


# --- Public surface -----------------------------------------------------------


def moderate_input(
    text: str,
    *,
    review: Review | None = None,
    request_type: str = "enrichment",
) -> str:
    """Truncate input text and screen it through the Moderation API.

    Returns the (possibly-truncated) text when not blocked. Raises
    `ContentModeratedException` when a high-severity category fires. When a
    Review is provided and the call is blocked, writes a MODERATED AiUsageLog
    row BEFORE raising (D-04/D-33).
    """
    truncated = _truncate_input(text)
    entity_id = getattr(review, "pk", None)
    blocked, flagged = _moderate_with_retry(truncated, stage="input", entity_id=entity_id)
    if flagged:
        logger.warning(
            "ai.moderation.flagged stage=input entity_type=review entity_id=%s "
            "categories=%s blocked=%s",
            entity_id,
            flagged,
            blocked,
        )
    if blocked:
        if review is not None:
            _persist_moderated_log(
                review=review,
                stage="input",
                flagged=flagged,
                request_type=request_type,
            )
        raise ContentModeratedException("input flagged")
    return truncated


def moderate_output(
    text: str,
    *,
    review: Review | None = None,
    request_type: str = "reply_generation",
    usage_data: dict[str, Any] | None = None,
) -> str:
    """Screen a generated reply through the Moderation API.

    Returns the input unchanged when not blocked (length truncation is the
    caller's responsibility — apply `truncate_reply_at_sentence` post-success).
    Raises `ContentModeratedException` when a high-severity category fires.
    When a Review is provided and the call is blocked, writes a MODERATED
    AiUsageLog row carrying REAL tokens/cost from `usage_data` per D-29
    (the OpenAI call already executed and consumed tokens).
    """
    entity_id = getattr(review, "pk", None)
    blocked, flagged = _moderate_with_retry(text, stage="output", entity_id=entity_id)
    if flagged:
        logger.warning(
            "ai.moderation.flagged stage=output entity_type=review entity_id=%s "
            "categories=%s blocked=%s",
            entity_id,
            flagged,
            blocked,
        )
    if blocked:
        if review is not None:
            usage = usage_data or {}
            _persist_moderated_log(
                review=review,
                stage="output",
                flagged=flagged,
                request_type=request_type,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                cached_tokens=int(usage.get("cached_tokens", 0) or 0),
                total_tokens=int(usage.get("total_tokens", 0) or 0),
                estimated_cost_usd=Decimal(
                    str(usage.get("estimated_cost_usd", Decimal("0")) or Decimal("0"))
                ),
            )
        raise ContentModeratedException("output flagged")
    return text
