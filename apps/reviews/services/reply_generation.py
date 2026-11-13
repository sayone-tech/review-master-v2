"""Phase 19 — AI reply generation service. Calls OpenAI and writes AiUsageLog per D-14/D-15/D-16.

Architecture (CLAUDE.md §5):
  - The view (Plan 19-02) calls generate_reply_draft and returns the result.
  - Business logic (OpenAI call orchestration + cost tracking) lives here.
  - The client wrapper (apps/integrations/openai/client.py) hides the SDK.

Phase 20 (Plan 20-06): input + output moderation and 300-word sentence
truncation are wired around the OpenAI call per D-07 / D-08 / D-14 / D-22 /
D-29 / D-33. Both moderate_* calls run OUTSIDE any transaction.atomic block
so the MODERATED audit row written by guardrails survives caller rollbacks.

Metering (Phase 30): every click is metered. ``generate_reply_with_credits``
reserves the review's credit cost (short row-locked transaction), calls OpenAI
outside any transaction, then settles in a ``finally`` (commit on success,
refund on failure). A regenerate charges again (D-11), and a second request
for a review with an unsettled reservation is rejected (D-12). There is still
no Redis lock: the shop balance row lock is the serialiser.

Exception handling (D-17): every exception writes one FAILED AiUsageLog row
before propagating. The view layer maps these to HTTP 502.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import connection

from apps.common.models import AuditLog
from apps.credits.selectors.balances import get_shop_credit_balance
from apps.credits.services.consumption import (
    SettleResult,
    commit_reservation,
    refund_reservation,
    reserve_credits,
)
from apps.credits.services.credit_cost import credit_cost
from apps.integrations.openai.client import (
    REPLY_MODERATION_MAX_RETRIES,
    call_openai_reply_generation,
)
from apps.integrations.openai.exceptions import (
    ContentModeratedException,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.guardrails import (
    ReviewWithModeratedComment,
    moderate_input,
    moderate_output,
    truncate_reply_at_sentence,
)
from apps.integrations.openai.models import AiUsageLog
from apps.integrations.openai.pricing import calculate_cost
from apps.integrations.openai.prompts import ALLOWED_REPLY_TONES
from apps.reviews.models import Review

logger = logging.getLogger(__name__)

# WR-03: single source of truth lives in apps.integrations.openai.prompts.
_ALLOWED_TONES: frozenset[str] = frozenset(ALLOWED_REPLY_TONES)


# NOTE: `_ReviewWithModeratedComment` was hoisted to
# `apps.integrations.openai.guardrails.ReviewWithModeratedComment` so both
# this service and `enrich_review` share a single definition (WR-02).


def _write_failure_log(*, review: Review, exc: Exception) -> int | None:
    """Write a single FAILED AiUsageLog row and return its pk (None if the write failed).

    Never raises (best-effort).

    WR-04: AiUsageLog.error_message is a TextField (no max_length), so the
    full exception string is stored without truncation. Diagnostic context
    is preserved for support / Sentry cross-reference.
    """
    try:
        row = AiUsageLog.objects.create(
            organisation_id=review.organisation_id,
            review_id=review.pk,
            request_type="reply_generation",
            model=settings.OPENAI_MODEL,
            prompt_tokens=None,
            completion_tokens=None,
            cached_tokens=0,
            total_tokens=None,
            estimated_cost_usd=Decimal("0"),
            latency_ms=None,
            langsmith_trace_id="",
            status=AiUsageLog.Status.FAILED,
            error_code=type(exc).__name__,
            error_message=str(exc),
        )
    except Exception:  # pragma: no cover — defensive
        logger.exception("reply_generation_failed_log_write_failed review_id=%s", review.pk)
        return None
    return row.pk


@dataclass(slots=True)
class _LogHolder:
    """Receives the pk of the FAILED AiUsageLog row so the orchestrator can link it (D-17)."""

    id: int | None = None


class ReplyModeratedError(Exception):
    """Moderation blocked the request. Carries the settled credit state for the 422 body."""

    def __init__(self, *, stage: str | None) -> None:
        super().__init__(f"reply moderated stage={stage}")
        self.stage = stage
        self.credits_charged: int = 0
        self.credits_remaining: int | None = None


class ReplyUnavailableError(Exception):
    """OpenAI failed or something unexpected broke. Carries the settled state for the 502 body."""

    def __init__(self) -> None:
        super().__init__("reply generation unavailable")
        self.credits_charged: int = 0
        self.credits_remaining: int | None = None


class ShopInactiveError(Exception):
    """The review's shop is inactive: it never gets or spends AI reply credits (CRED-INACTIVE-01)."""


class EmptyCommentError(Exception):
    """The review has no chargeable text (empty or whitespace-only comment, CCON-04)."""


@dataclass(frozen=True, slots=True)
class ReplyResult:
    draft: str
    credits_charged: int
    credits_remaining: int | None


def read_credits_remaining(*, shop_id: int) -> int | None:
    """Current remaining credits for the shop, or None when the read itself fails."""
    try:
        return get_shop_credit_balance(shop_id=shop_id).remaining
    except Exception:
        logger.exception("reply_generation_remaining_read_failed shop_id=%s", shop_id)
        return None


def _assert_no_open_transaction() -> None:
    """D-07 / D-18: the OpenAI call must never run inside a database transaction.

    A real raise (``python -O`` strips ``assert``). Atomic blocks opened by pytest-django's
    test wrapper (``_from_testcase``) are ignored so default ``django_db`` tests are not flagged.
    """
    if any(not getattr(b, "_from_testcase", False) for b in connection.atomic_blocks):
        raise RuntimeError("OpenAI call must not run inside a database transaction")


def _generate_reply_draft_with_log(
    *, review: Review, tone: str, log_holder: _LogHolder | None = None
) -> tuple[str, int]:
    """Generate a reply draft for `review` using the requested tone.

    Returns ``(draft, usage_log_id)`` where ``usage_log_id`` is the pk of the SUCCESS
    AiUsageLog row. Writes exactly one AiUsageLog row per call:
      - status=SUCCESS on the happy path
      - status=FAILED for OpenAITransientError, OpenAIPermanentError, or any
        other exception (D-17); the original exception is then re-raised so
        the view layer can map it to HTTP 502.
      - status=MODERATED (written by apps.integrations.openai.guardrails) on
        input or output moderation block; ContentModeratedException then
        propagates to the caller, which maps it to HTTP 422.

    ``log_holder`` (optional) receives the pk of the FAILED row when one is written.
    """
    if tone not in _ALLOWED_TONES:
        raise ValueError(f"Unknown tone: {tone!r}")

    # D-14 / D-33: input moderation BEFORE the OpenAI call, OUTSIDE any
    # transaction.atomic() block so the MODERATED audit row survives a
    # caller-side rollback. ContentModeratedException propagates uncaught.
    truncated_comment = moderate_input(
        review.comment or "",
        review=review,
        request_type="reply_generation",
        timeout=settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS,
        max_retries=REPLY_MODERATION_MAX_RETRIES,
    )
    review_for_prompt = ReviewWithModeratedComment(review, truncated_comment)

    try:
        draft, usage_data = call_openai_reply_generation(
            review=review_for_prompt,
            tone=tone,
            model=settings.OPENAI_MODEL,
        )
    except (OpenAITransientError, OpenAIPermanentError) as exc:
        failed_id = _write_failure_log(review=review, exc=exc)
        if log_holder is not None:
            log_holder.id = failed_id
        raise
    except Exception as exc:
        failed_id = _write_failure_log(review=review, exc=exc)
        if log_holder is not None:
            log_holder.id = failed_id
        raise

    # WR-05: never let a missing AiPricing row swallow the SUCCESS log. The
    # OpenAI call has already been billed; we MUST record it. If pricing
    # lookup fails (e.g., seed migration missed for a new model), log the
    # call with estimated_cost_usd=0 + error_code="ai_pricing_lookup_failed"
    # so cost auditing surfaces the gap rather than silently undercounting.
    #
    # D-29: cost is computed BEFORE moderate_output and injected into
    # usage_data so the MODERATED row (if guardrails writes one) carries the
    # REAL estimated_cost_usd — the OpenAI call already consumed tokens.
    pricing_error_code = ""
    pricing_error_message = ""
    try:
        cost: Decimal = calculate_cost(
            model=settings.OPENAI_MODEL,
            prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
            completion_tokens=int(usage_data.get("completion_tokens") or 0),
            cached_tokens=int(usage_data.get("cached_tokens") or 0),
        )
    except Exception as exc:
        logger.exception("ai_pricing_lookup_failed model=%s", settings.OPENAI_MODEL)
        cost = Decimal("0")
        pricing_error_code = "ai_pricing_lookup_failed"
        pricing_error_message = str(exc)
    usage_data["estimated_cost_usd"] = cost

    # D-07 / D-29 / D-33: output moderation AFTER the OpenAI call and BEFORE
    # the SUCCESS AiUsageLog write. usage_data carries REAL prompt/completion
    # tokens AND real cost so guardrails writes an accurate MODERATED row on
    # a block. Outside any atomic block per D-33.
    moderate_output(
        draft,
        review=review,
        request_type="reply_generation",
        usage_data=usage_data,
        timeout=settings.REVIEWBEE_REPLY_OPENAI_TIMEOUT_SECONDS,
        max_retries=REPLY_MODERATION_MAX_RETRIES,
    )

    # D-08 / D-22: 300-word sentence-boundary truncation applied AFTER output
    # moderation passes (length cap is a presentation transform of an
    # already-safe draft, not a safety gate).
    draft = truncate_reply_at_sentence(draft)

    usage_log = AiUsageLog.objects.create(
        organisation_id=review.organisation_id,
        review_id=review.pk,
        request_type="reply_generation",
        model=settings.OPENAI_MODEL,
        prompt_tokens=usage_data.get("prompt_tokens"),
        completion_tokens=usage_data.get("completion_tokens"),
        cached_tokens=usage_data.get("cached_tokens", 0) or 0,
        total_tokens=usage_data.get("total_tokens"),
        estimated_cost_usd=cost,
        latency_ms=usage_data.get("latency_ms"),
        langsmith_trace_id=usage_data.get("langsmith_trace_id") or "",
        status=AiUsageLog.Status.SUCCESS,
        error_code=pricing_error_code,
        error_message=pricing_error_message,
    )
    return draft, usage_log.pk


def generate_reply_draft(*, review: Review, tone: str) -> str:
    """Thin wrapper over ``_generate_reply_draft_with_log`` returning only the draft."""
    return _generate_reply_draft_with_log(review=review, tone=tone)[0]


def _settle(
    *,
    transaction_id: int,
    review_id: int,
    commit: bool,
    reason: str,
    usage_log_id: int | None,
    actor_id: int | None,
) -> SettleResult | None:
    """Commit or refund the reservation. Never raises: a settle failure must not mask the
    original outcome (the Phase 31 reaper refunds anything left RESERVED)."""
    try:
        if commit:
            return commit_reservation(
                transaction_id=transaction_id,
                ai_usage_log_id=usage_log_id,
                outcome=reason,
                actor_id=actor_id,
            )
        refund_reservation(
            transaction_id=transaction_id,
            reason=reason,
            ai_usage_log_id=usage_log_id,
            actor_id=actor_id,
        )
    except Exception:
        logger.exception(
            "reply_generation_settle_failed tx_id=%s review_id=%s", transaction_id, review_id
        )
    return None


def _record_ai_reply_generated(*, review: Review, tone: str, actor_id: int | None) -> None:
    """CVIS-06: one review-level Activity Log row per successful generation.

    Visible to Staff for their shops, so ``after_data`` is the tone only: no credit numbers
    (CVIS-05) and no AI usage log id (a platform-wide sequence). Both live on the
    Org-Admin-only ``shop.credits.consumed`` row. Never
    raises: the credits are already charged, so the user must still get the draft.
    """
    try:
        AuditLog.objects.create(
            organisation_id=review.organisation_id,
            actor_id=actor_id,
            entity_type="review",
            entity_id=str(review.pk),
            action="ai_reply_generated",
            after_data={"tone": tone},
        )
    except Exception:
        logger.exception("ai_reply_generated_audit_failed review_id=%s", review.pk)


def generate_reply_with_credits(*, review: Review, tone: str, actor_id: int | None) -> ReplyResult:
    """Metered generation: reserve -> OpenAI call -> settle (commit or refund in ``finally``).

    Outcome matrix (D-03, D-04, D-17): a success or a certain output-stage moderation block
    commits (OpenAI billed); everything else refunds (input block, OpenAI error, unexpected
    error, stage-less moderation exception, interruption). Settlement completes before any
    result or wrapper exception is built, so ``credits_remaining`` is the settled balance.

    Raises ``ShopInactiveError`` and ``EmptyCommentError`` before any reservation, ``InsufficientCreditsError`` /
    ``GenerationInProgressError`` from the reserve, ``ReplyModeratedError`` and
    ``ReplyUnavailableError`` after settlement.
    """
    if tone not in _ALLOWED_TONES:
        raise ValueError(f"Unknown tone: {tone!r}")
    # CRED-INACTIVE-01: refuse before any balance, reservation, or OpenAI call.
    if not review.shop.is_active:
        raise ShopInactiveError(f"shop {review.shop_id} is inactive")
    cost = credit_cost(review.comment)
    if cost == 0:
        raise EmptyCommentError(f"review {review.pk} has no chargeable comment")

    reservation = reserve_credits(
        shop_id=review.shop_id, review_id=review.pk, credits=cost, actor_id=actor_id
    )
    # D-04: the default is refund. Only a success or a certain output block switches to commit.
    commit = False
    reason = "unexpected_error"
    usage_log_id: int | None = None
    draft = ""
    pending: ReplyModeratedError | ReplyUnavailableError | None = None
    holder = _LogHolder()
    try:
        try:
            _assert_no_open_transaction()
            draft, usage_log_id = _generate_reply_draft_with_log(
                review=review, tone=tone, log_holder=holder
            )
            commit = True
            reason = "success"
        except ContentModeratedException as exc:
            usage_log_id = exc.usage_log_id
            if exc.stage == "output":
                commit = True
                reason = "output_moderated"
            else:
                reason = "input_moderated"
            pending = ReplyModeratedError(stage=exc.stage)
            logger.info(
                "reply_generation_moderated review_id=%s tx_id=%s stage=%s",
                review.pk,
                reservation.transaction_id,
                exc.stage,
            )
        except (OpenAITransientError, OpenAIPermanentError) as exc:
            reason = "openai_failure"
            usage_log_id = holder.id
            pending = ReplyUnavailableError()
            pending.__cause__ = exc
            logger.warning(
                "reply_generation_openai_failed review_id=%s tx_id=%s exc_type=%s",
                review.pk,
                reservation.transaction_id,
                type(exc).__name__,
            )
        except Exception as exc:
            reason = "unexpected_error"
            usage_log_id = holder.id
            pending = ReplyUnavailableError()
            pending.__cause__ = exc
            logger.exception(
                "reply_generation_unexpected review_id=%s tx_id=%s exc_type=%s",
                review.pk,
                reservation.transaction_id,
                type(exc).__name__,
            )
    finally:
        # D-03: settle here so it completes on any exit, including a BaseException.
        settle = _settle(
            transaction_id=reservation.transaction_id,
            review_id=review.pk,
            commit=commit,
            reason=reason,
            usage_log_id=usage_log_id,
            actor_id=actor_id,
        )
    charged = settle.credits_charged if settle is not None else 0
    remaining = read_credits_remaining(shop_id=review.shop_id)
    if pending is None and reason == "success":
        _record_ai_reply_generated(review=review, tone=tone, actor_id=actor_id)
    if pending is not None:
        pending.credits_charged = charged
        pending.credits_remaining = remaining
        raise pending
    return ReplyResult(draft=draft, credits_charged=charged, credits_remaining=remaining)
