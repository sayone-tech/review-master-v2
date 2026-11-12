"""Phase 30 Plan 03 — outcome matrix of ``generate_reply_with_credits`` (CCON-05, CCON-06).

Consume when OpenAI billed (success, output-stage moderation block); refund when it did
not (input block, OpenAI failure, unexpected error, interruption, stage-less exception).
Exactly one AiUsageLog row per request that reaches OpenAI/moderation, linked to the settled
ledger row (D-17), exactly one consumed/refunded AuditLog row, and the ledger reconciles.

External seams only are mocked: the OpenAI chat call and the Moderation API transport.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from django.db import transaction

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.integrations.openai.exceptions import (
    ContentModeratedException,
    OpenAIPermanentError,
    OpenAITransientError,
)
from apps.integrations.openai.models import AiUsageLog
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.services.reply_generation import (
    ReplyModeratedError,
    ReplyResult,
    ReplyUnavailableError,
    generate_reply_with_credits,
)
from apps.reviews.tests.factories import ReviewFactory

pytestmark = pytest.mark.django_db

CALL = "apps.reviews.services.reply_generation.call_openai_reply_generation"
MODERATION_API = "apps.integrations.openai.guardrails._call_moderation_api"
COST = 2  # a 150-character comment
ALLOCATION = 10
REVIEW_TEXT = "x" * 150


def _usage_data() -> dict:
    return {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "cached_tokens": 0,
        "total_tokens": 150,
        "latency_ms": 500,
        "langsmith_trace_id": "trace-reply-001",
    }


def _mod_response(categories: dict[str, bool]) -> MagicMock:
    response = MagicMock()
    response.results[0].categories.model_dump.return_value = categories
    return response


CLEAN = _mod_response({"harassment": False})
BLOCKED = _mod_response({"self_harm_intent": True})


@pytest.fixture
def review():
    org = OrganisationFactory(monthly_credit_allocation=ALLOCATION)
    return ReviewFactory(organisation=org, comment=REVIEW_TEXT)


def _tx(review) -> CreditTransaction:
    return CreditTransaction.objects.get(
        review=review, transaction_type=CreditTransaction.Type.CONSUMPTION
    )


def _generate(review):
    return generate_reply_with_credits(review=review, tone="professional", actor_id=None)


def _balance(review) -> ShopCreditBalance:
    return ShopCreditBalance.objects.get(shop=review.shop)


def _single_log(review, status: str) -> AiUsageLog:
    assert AiUsageLog.objects.filter(review=review).count() == 1
    return AiUsageLog.objects.get(review=review, status=status)


class TestCommitBranches:
    def test_success_commits_and_links_success_row_when_draft_is_returned(self, review) -> None:
        with (
            patch(MODERATION_API, return_value=CLEAN),
            patch(CALL, return_value=("A fine draft.", _usage_data())),
        ):
            result = _generate(review)

        assert isinstance(result, ReplyResult)
        assert result.draft == "A fine draft."
        assert result.credits_charged == COST
        assert result.credits_remaining == ALLOCATION - COST
        tx = _tx(review)
        assert tx.status == CreditTransaction.Status.COMMITTED
        log = _single_log(review, AiUsageLog.Status.SUCCESS)
        assert tx.ai_usage_log_id == log.pk
        consumed = AuditLog.objects.get(action="shop.credits.consumed")
        assert consumed.after_data["outcome"] == "success"
        assert AuditLog.objects.filter(action="shop.credits.refunded").count() == 0
        assert_ledger_reconciles(_balance(review))

    def test_output_block_commits_and_links_moderated_row_when_output_is_flagged(
        self, review
    ) -> None:
        with (
            patch(MODERATION_API, side_effect=[CLEAN, BLOCKED]),
            patch(CALL, return_value=("A flagged draft.", _usage_data())),
            pytest.raises(ReplyModeratedError) as info,
        ):
            _generate(review)

        assert info.value.stage == "output"
        assert info.value.credits_charged == COST
        assert info.value.credits_remaining == ALLOCATION - COST
        tx = _tx(review)
        assert tx.status == CreditTransaction.Status.COMMITTED
        log = _single_log(review, AiUsageLog.Status.MODERATED)
        assert tx.ai_usage_log_id == log.pk
        consumed = AuditLog.objects.get(action="shop.credits.consumed")
        assert consumed.after_data["outcome"] == "output_moderated"
        assert_ledger_reconciles(_balance(review))


class TestRefundBranches:
    def test_input_block_refunds_and_links_moderated_row_without_calling_openai(
        self, review
    ) -> None:
        with (
            patch(MODERATION_API, return_value=BLOCKED),
            patch(CALL) as call_mock,
            pytest.raises(ReplyModeratedError) as info,
        ):
            _generate(review)

        call_mock.assert_not_called()
        assert info.value.stage == "input"
        assert info.value.credits_charged == 0
        assert info.value.credits_remaining == ALLOCATION
        tx = _tx(review)
        assert tx.status == CreditTransaction.Status.REFUNDED
        log = _single_log(review, AiUsageLog.Status.MODERATED)
        assert tx.ai_usage_log_id == log.pk
        refunded = AuditLog.objects.get(action="shop.credits.refunded")
        assert refunded.after_data["reason"] == "input_moderated"
        assert AuditLog.objects.filter(action="shop.credits.consumed").count() == 0
        assert_ledger_reconciles(_balance(review))

    @pytest.mark.parametrize("stage", [None, "sideways"])
    def test_moderation_exception_refunds_when_stage_is_not_output(self, review, stage) -> None:
        exc = ContentModeratedException("blocked", stage=stage)
        with (
            patch(
                "apps.reviews.services.reply_generation._generate_reply_draft_with_log",
                side_effect=exc,
            ),
            pytest.raises(ReplyModeratedError) as info,
        ):
            _generate(review)

        assert info.value.credits_charged == 0
        assert info.value.credits_remaining == ALLOCATION
        assert _tx(review).status == CreditTransaction.Status.REFUNDED
        assert AuditLog.objects.filter(action="shop.credits.consumed").count() == 0
        assert_ledger_reconciles(_balance(review))

    @pytest.mark.parametrize(
        "error", [OpenAITransientError("boom"), OpenAIPermanentError("nope", status_code=400)]
    )
    def test_openai_error_refunds_and_links_failed_row_when_call_fails(self, review, error) -> None:
        with (
            patch(MODERATION_API, return_value=CLEAN),
            patch(CALL, side_effect=error),
            pytest.raises(ReplyUnavailableError) as info,
        ):
            _generate(review)

        assert info.value.__cause__ is error
        assert info.value.credits_charged == 0
        assert info.value.credits_remaining == ALLOCATION
        tx = _tx(review)
        assert tx.status == CreditTransaction.Status.REFUNDED
        log = _single_log(review, AiUsageLog.Status.FAILED)
        assert tx.ai_usage_log_id == log.pk
        refunded = AuditLog.objects.get(action="shop.credits.refunded")
        assert refunded.after_data["reason"] == "openai_failure"
        assert_ledger_reconciles(_balance(review))

    def test_unexpected_error_refunds_when_call_raises_runtime_error(self, review) -> None:
        with (
            patch(MODERATION_API, return_value=CLEAN),
            patch(CALL, side_effect=RuntimeError("kaboom")),
            pytest.raises(ReplyUnavailableError) as info,
        ):
            _generate(review)

        assert isinstance(info.value.__cause__, RuntimeError)
        tx = _tx(review)
        assert tx.status == CreditTransaction.Status.REFUNDED
        log = _single_log(review, AiUsageLog.Status.FAILED)
        assert tx.ai_usage_log_id == log.pk
        refunded = AuditLog.objects.get(action="shop.credits.refunded")
        assert refunded.after_data["reason"] == "unexpected_error"
        assert_ledger_reconciles(_balance(review))

    def test_interruption_refunds_in_finally_and_is_reraised_when_keyboard_interrupt(
        self, review
    ) -> None:
        with (
            patch(
                "apps.reviews.services.reply_generation._generate_reply_draft_with_log",
                side_effect=KeyboardInterrupt,
            ),
            pytest.raises(KeyboardInterrupt),
        ):
            _generate(review)

        assert _tx(review).status == CreditTransaction.Status.REFUNDED
        assert _balance(review).consumed_credits == 0
        assert_ledger_reconciles(_balance(review))


class TestSettleFailure:
    def test_caller_still_gets_result_and_row_stays_reserved_when_commit_fails(
        self, review, caplog
    ) -> None:
        with (
            patch(MODERATION_API, return_value=CLEAN),
            patch(CALL, return_value=("A fine draft.", _usage_data())),
            patch(
                "apps.reviews.services.reply_generation.commit_reservation",
                side_effect=RuntimeError(f"db down {REVIEW_TEXT}"),
            ),
            caplog.at_level(logging.INFO),
        ):
            result = _generate(review)

        assert result.draft == "A fine draft."
        assert result.credits_charged == 0
        tx = _tx(review)
        assert tx.status == CreditTransaction.Status.RESERVED
        assert f"tx_id={tx.pk}" in caplog.text
        settle_records = [r for r in caplog.records if "settle_failed" in r.getMessage()]
        assert settle_records
        assert all(REVIEW_TEXT not in r.getMessage() for r in settle_records)
        assert_ledger_reconciles(_balance(review))


class TestTransactionGuard:
    def test_guard_does_not_raise_in_default_django_db_test(self, review) -> None:
        from django.db import connection

        from apps.reviews.services.reply_generation import _assert_no_open_transaction

        assert connection.in_atomic_block is True  # pytest-django's wrapper
        _assert_no_open_transaction()

    def test_orchestrator_refunds_and_never_calls_draft_when_inside_atomic_block(
        self, review
    ) -> None:
        with (
            patch("apps.reviews.services.reply_generation._generate_reply_draft_with_log") as seam,
            transaction.atomic(),
            pytest.raises(ReplyUnavailableError) as info,
        ):
            _generate(review)

        seam.assert_not_called()
        assert isinstance(info.value.__cause__, RuntimeError)
        assert _tx(review).status == CreditTransaction.Status.REFUNDED
        assert_ledger_reconciles(_balance(review))

    @pytest.mark.django_db(transaction=True)
    def test_guard_raises_only_inside_explicit_atomic_when_not_wrapped(self) -> None:
        from django.db import connection

        from apps.reviews.services.reply_generation import _assert_no_open_transaction

        assert connection.in_atomic_block is False
        _assert_no_open_transaction()
        with transaction.atomic(), pytest.raises(RuntimeError, match="database transaction"):
            _assert_no_open_transaction()


class TestAiReplyGeneratedAudit:
    """CVIS-06: one review-level ``ai_reply_generated`` row per successful generation."""

    def test_writes_review_event_with_tone_and_no_credit_numbers_when_draft_is_returned(
        self, review
    ) -> None:
        with (
            patch(MODERATION_API, return_value=CLEAN),
            patch(CALL, return_value=("A fine draft.", _usage_data())),
        ):
            generate_reply_with_credits(review=review, tone="friendly", actor_id=None)

        event = AuditLog.objects.get(action="ai_reply_generated")
        assert event.entity_type == "review"
        assert event.entity_id == str(review.pk)
        assert event.organisation_id == review.organisation_id
        # Staff can read this row: tone only, no credit numbers (CVIS-05), no usage log id.
        assert event.after_data == {"tone": "friendly"}

    def test_writes_no_review_event_when_openai_call_fails(self, review) -> None:
        with (
            patch(MODERATION_API, return_value=CLEAN),
            patch(CALL, side_effect=OpenAITransientError("boom")),
            pytest.raises(ReplyUnavailableError),
        ):
            _generate(review)

        assert not AuditLog.objects.filter(action="ai_reply_generated").exists()

    def test_writes_no_review_event_when_output_is_moderated(self, review) -> None:
        with (
            patch(MODERATION_API, side_effect=[CLEAN, BLOCKED]),
            patch(CALL, return_value=("A blocked draft.", _usage_data())),
            pytest.raises(ReplyModeratedError),
        ):
            _generate(review)

        assert not AuditLog.objects.filter(action="ai_reply_generated").exists()

    def test_still_returns_draft_when_audit_write_fails(self, review) -> None:
        real_create = AuditLog.objects.create

        def failing_create(**kwargs):
            if kwargs.get("action") == "ai_reply_generated":
                raise RuntimeError("audit down")
            return real_create(**kwargs)

        with (
            patch(MODERATION_API, return_value=CLEAN),
            patch(CALL, return_value=("A fine draft.", _usage_data())),
            patch.object(AuditLog.objects, "create", side_effect=failing_create),
        ):
            result = _generate(review)

        assert result.draft == "A fine draft."
        assert result.credits_charged == COST
