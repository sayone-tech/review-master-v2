"""Reserve / commit / refund / late-commit primitives (Phase 30: CCON-01, 03, 05, 06)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.common.models import AuditLog
from apps.credits.exceptions import GenerationInProgressError, InsufficientCreditsError
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.consumption import (
    SettleResult,
    commit_reservation,
    refund_reservation,
    reserve_credits,
)
from apps.credits.services.periods import current_period
from apps.credits.tests.factories import CreditTransactionFactory, ShopCreditBalanceFactory
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.integrations.openai.tests.factories import AiUsageLogFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

Status = CreditTransaction.Status
Type = CreditTransaction.Type
SENTRY = "apps.credits.services.consumption.sentry_sdk.capture_message"
SECRET = "SECRET-REVIEW-TEXT"


def _shop_review(*, allocation: int = 10, comment: str = SECRET):
    org = OrganisationFactory(monthly_credit_allocation=allocation)
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(organisation=org, shop=shop, comment=comment)
    return org, shop, review


def _reserve(review, *, credits: int = 3, actor_id: int | None = None):
    return reserve_credits(
        shop_id=review.shop_id, review_id=review.pk, credits=credits, actor_id=actor_id
    )


def _balance(shop) -> ShopCreditBalance:
    return ShopCreditBalance.objects.get(shop=shop)


def _status(transaction_id: int) -> str:
    return CreditTransaction.objects.values_list("status", flat=True).get(pk=transaction_id)


def _audit(action: str):
    return list(AuditLog.objects.filter(action=action))


def _previous_period():
    p = current_period()
    return (p.year - 1, 12) if p.month == 1 else (p.year, p.month - 1)


# --- reserve -------------------------------------------------------------------


def test_reserve_raises_consumed_and_inserts_reserved_row_when_capacity_available():
    _org, shop, review = _shop_review(allocation=10)

    res = _reserve(review, credits=3, actor_id=None)

    balance = _balance(shop)
    assert balance.consumed_credits == 3
    tx = CreditTransaction.objects.get(pk=res.transaction_id)
    assert (tx.status, tx.transaction_type, tx.credits_delta) == (
        Status.RESERVED,
        Type.CONSUMPTION,
        -3,
    )
    assert (res.shop_id, res.review_id, res.credits) == (shop.pk, review.pk, 3)
    assert res.shop_credit_balance_id == balance.pk
    assert res.organisation_id == shop.organisation_id
    assert_ledger_reconciles(balance)


def test_reserve_succeeds_and_fills_balance_when_remaining_equals_cost():
    _org, shop, review = _shop_review(allocation=3)

    _reserve(review, credits=3)

    balance = _balance(shop)
    assert balance.consumed_credits == balance.allocated_credits + balance.bonus_credits
    assert_ledger_reconciles(balance)


def test_reserve_raises_exhausted_and_writes_nothing_when_remaining_is_one_below_cost():
    _org, shop, review = _shop_review(allocation=5)
    ShopCreditBalanceFactory(shop=shop, allocated_credits=5, consumed_credits=3)
    before = CreditTransaction.objects.count()

    with pytest.raises(InsufficientCreditsError) as exc:
        _reserve(review, credits=3)

    assert (exc.value.reason, exc.value.required, exc.value.remaining) == ("exhausted", 3, 2)
    assert CreditTransaction.objects.count() == before
    assert _balance(shop).consumed_credits == 3


def test_reserve_raises_not_enabled_without_any_write_when_allocation_is_zero():
    _org, shop, review = _shop_review(allocation=0)

    with CaptureQueriesContext(connection) as ctx, pytest.raises(InsufficientCreditsError) as exc:
        _reserve(review, credits=2)

    assert (exc.value.reason, exc.value.required, exc.value.remaining) == ("not_enabled", 2, 0)
    assert ShopCreditBalance.objects.filter(shop=shop).count() == 0
    writes = [
        q["sql"]
        for q in ctx.captured_queries
        if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
    ]
    assert writes == []


def test_reserve_raises_not_enabled_when_materialised_balance_has_zero_allocation_and_bonus():
    _org, shop, review = _shop_review(allocation=0)
    ShopCreditBalanceFactory(shop=shop, allocated_credits=0, bonus_credits=0)

    with pytest.raises(InsufficientCreditsError) as exc:
        _reserve(review, credits=1)

    assert exc.value.reason == "not_enabled"


def test_reserve_succeeds_when_only_bonus_credits_exist():
    _org, shop, review = _shop_review(allocation=0)
    ShopCreditBalanceFactory(shop=shop, allocated_credits=0, bonus_credits=3)

    _reserve(review, credits=1)

    assert _balance(shop).consumed_credits == 1


@pytest.mark.parametrize("credits", [0, -1])
def test_reserve_raises_value_error_before_any_query_when_credits_not_positive(credits):
    _org, _shop, review = _shop_review()

    with CaptureQueriesContext(connection) as ctx, pytest.raises(ValueError, match="positive"):
        _reserve(review, credits=credits)

    assert len(ctx.captured_queries) == 0


def test_reserve_raises_in_progress_and_changes_nothing_when_review_has_reserved_row():
    _org, shop, review = _shop_review(allocation=10)
    _reserve(review, credits=2)
    before = (CreditTransaction.objects.count(), _balance(shop).consumed_credits)

    with pytest.raises(GenerationInProgressError) as exc:
        _reserve(review, credits=2)

    assert exc.value.review_id == review.pk
    assert (CreditTransaction.objects.count(), _balance(shop).consumed_credits) == before


@pytest.mark.parametrize("settle", ["commit", "refund"])
def test_reserve_succeeds_when_prior_reservation_for_review_is_settled(settle):
    _org, shop, review = _shop_review(allocation=10)
    first = _reserve(review, credits=2)
    if settle == "commit":
        commit_reservation(
            transaction_id=first.transaction_id,
            ai_usage_log_id=None,
            outcome="success",
            actor_id=None,
        )
    else:
        assert refund_reservation(transaction_id=first.transaction_id, reason="t") is True

    second = _reserve(review, credits=2)

    assert second.transaction_id != first.transaction_id
    assert_ledger_reconciles(_balance(shop))


# --- commit --------------------------------------------------------------------


def test_commit_links_usage_log_and_writes_one_consumed_audit_row_when_cas_wins():
    org, shop, review = _shop_review(allocation=10)
    res = _reserve(review, credits=2)
    log = AiUsageLogFactory(organisation=org, review=review, request_type="reply_generation")

    result = commit_reservation(
        transaction_id=res.transaction_id,
        ai_usage_log_id=log.pk,
        outcome="success",
        actor_id=None,
    )

    assert result == SettleResult(credits_charged=2, outcome="committed")
    tx = CreditTransaction.objects.get(pk=res.transaction_id)
    assert tx.status == Status.COMMITTED
    assert tx.ai_usage_log_id == log.pk
    assert _balance(shop).consumed_credits == 2  # commit never touches the balance
    rows = _audit("shop.credits.consumed")
    assert len(rows) == 1
    assert set(rows[0].after_data) == {
        "transaction_id",
        "review_id",
        "credits",
        "outcome",
        "ai_usage_log_id",
        "period_year",
        "period_month",
    }
    assert SECRET not in json.dumps(rows[0].after_data)
    assert_ledger_reconciles(_balance(shop))


def test_commit_settles_with_null_link_when_no_usage_log_id_given():
    _org, shop, review = _shop_review()
    res = _reserve(review, credits=1)

    result = commit_reservation(
        transaction_id=res.transaction_id, ai_usage_log_id=None, outcome="success", actor_id=None
    )

    assert result.outcome == "committed"
    tx = CreditTransaction.objects.get(pk=res.transaction_id)
    assert tx.status == Status.COMMITTED
    assert tx.ai_usage_log_id is None
    assert_ledger_reconciles(_balance(shop))


# --- refund --------------------------------------------------------------------


@pytest.mark.parametrize("with_link", [True, False])
def test_refund_restores_balance_and_audits_once_when_cas_wins(with_link):
    org, shop, review = _shop_review(allocation=10)
    res = _reserve(review, credits=3)
    log = AiUsageLogFactory(organisation=org, review=review) if with_link else None

    won = refund_reservation(
        transaction_id=res.transaction_id,
        reason="unexpected_error",
        ai_usage_log_id=log.pk if log else None,
    )

    assert won is True
    tx = CreditTransaction.objects.get(pk=res.transaction_id)
    assert tx.status == Status.REFUNDED
    assert tx.ai_usage_log_id == (log.pk if log else None)
    assert _balance(shop).consumed_credits == 0
    rows = _audit("shop.credits.refunded")
    assert len(rows) == 1
    assert rows[0].after_data["reason"] == "unexpected_error"
    assert_ledger_reconciles(_balance(shop))


def test_refund_returns_false_without_second_change_when_called_twice():
    _org, shop, review = _shop_review()
    res = _reserve(review, credits=2)
    assert refund_reservation(transaction_id=res.transaction_id, reason="a") is True

    assert refund_reservation(transaction_id=res.transaction_id, reason="b") is False

    assert _balance(shop).consumed_credits == 0
    assert len(_audit("shop.credits.refunded")) == 1
    assert_ledger_reconciles(_balance(shop))


def test_refund_returns_false_and_keeps_committed_when_row_already_committed():
    _org, shop, review = _shop_review()
    res = _reserve(review, credits=2)
    commit_reservation(
        transaction_id=res.transaction_id, ai_usage_log_id=None, outcome="success", actor_id=None
    )

    assert refund_reservation(transaction_id=res.transaction_id, reason="late") is False

    assert _status(res.transaction_id) == Status.COMMITTED
    assert _balance(shop).consumed_credits == 2
    assert _audit("shop.credits.refunded") == []


def test_refund_raises_and_rolls_back_cas_when_decrement_would_go_negative():
    _org, shop, review = _shop_review()
    res = _reserve(review, credits=3)
    # Corrupt the balance so the guarded decrement cannot apply (test-only direct update).
    ShopCreditBalance.objects.filter(pk=res.shop_credit_balance_id).update(consumed_credits=1)

    with pytest.raises(RuntimeError, match="negative"):
        refund_reservation(transaction_id=res.transaction_id, reason="x")

    assert _status(res.transaction_id) == Status.RESERVED
    assert _audit("shop.credits.refunded") == []
    assert _balance(shop).consumed_credits == 1


def test_refund_returns_false_when_transaction_does_not_exist():
    assert refund_reservation(transaction_id=987654321, reason="x") is False


# --- late commit (D-01, D-02, D-16) ---------------------------------------------


def _late_commit(res, *, log_id: int | None = None, actor_id: int | None = None) -> SettleResult:
    return commit_reservation(
        transaction_id=res.transaction_id,
        ai_usage_log_id=log_id,
        outcome="success",
        actor_id=actor_id,
    )


def test_late_commit_rededucts_once_when_refunded_reservation_has_capacity():
    org, shop, review = _shop_review(allocation=10)
    res = _reserve(review, credits=3)
    refund_reservation(transaction_id=res.transaction_id, reason="reaped")
    log = AiUsageLogFactory(organisation=org, review=review)

    with patch(SENTRY) as sentry:
        result = _late_commit(res, log_id=log.pk)

    assert result == SettleResult(credits_charged=3, outcome="rededucted")
    new_rows = CreditTransaction.objects.filter(
        review=review, transaction_type=Type.CONSUMPTION, status=Status.COMMITTED
    )
    assert new_rows.count() == 1
    new_tx = new_rows.get()
    assert (new_tx.note, new_tx.ai_usage_log_id, new_tx.credits_delta) == (
        "late_commit",
        log.pk,
        -3,
    )
    assert _status(res.transaction_id) == Status.REFUNDED
    assert _balance(shop).consumed_credits == 3
    rows = _audit("shop.credits.late_commit")
    assert len(rows) == 1
    assert rows[0].after_data["outcome"] == "rededucted"
    sentry.assert_called_once()
    assert sentry.call_args.kwargs["level"] == "warning"
    assert SECRET not in json.dumps(rows[0].after_data)
    assert SECRET not in str(sentry.call_args)
    assert_ledger_reconciles(_balance(shop))


def test_late_commit_is_free_draft_when_refunded_reservation_has_no_capacity():
    _org, shop, review = _shop_review(allocation=3)
    other = ReviewFactory(organisation=shop.organisation, shop=shop, comment=SECRET)
    res = _reserve(review, credits=3)
    refund_reservation(transaction_id=res.transaction_id, reason="reaped")
    _reserve(other, credits=3)  # a newer request now owns all the capacity
    before = CreditTransaction.objects.count()

    with patch(SENTRY) as sentry:
        result = _late_commit(res)

    assert result == SettleResult(credits_charged=0, outcome="free_draft")
    assert CreditTransaction.objects.count() == before
    assert _balance(shop).consumed_credits == 3
    rows = _audit("shop.credits.late_commit")
    assert len(rows) == 1
    assert rows[0].after_data["outcome"] == "free_draft"
    sentry.assert_called_once()
    assert_ledger_reconciles(_balance(shop))


def test_late_commit_never_charges_twice_when_reservation_already_committed():
    _org, shop, review = _shop_review()
    res = _reserve(review, credits=3)
    assert _late_commit(res).outcome == "committed"
    before = CreditTransaction.objects.count()

    with patch(SENTRY) as sentry:
        result = _late_commit(res)

    assert result == SettleResult(credits_charged=3, outcome="already_settled")
    assert CreditTransaction.objects.count() == before
    assert _balance(shop).consumed_credits == 3
    rows = _audit("shop.credits.late_commit")
    assert len(rows) == 1
    assert rows[0].after_data["outcome"] == "already_settled"
    sentry.assert_called_once()
    assert_ledger_reconciles(_balance(shop))


def test_late_commit_is_free_draft_without_balance_write_when_reservation_is_prior_month():
    _org, shop, review = _shop_review()
    year, month = _previous_period()
    old = ShopCreditBalanceFactory(
        shop=shop, period_year=year, period_month=month, allocated_credits=10, consumed_credits=3
    )
    tx = CreditTransactionFactory(
        shop_credit_balance=old,
        credits_delta=-3,
        review=review,
        status=Status.RESERVED,
    )
    assert refund_reservation(transaction_id=tx.pk, reason="reaped") is True
    before = CreditTransaction.objects.count()

    with patch(SENTRY):
        result = commit_reservation(
            transaction_id=tx.pk, ai_usage_log_id=None, outcome="success", actor_id=None
        )

    assert result == SettleResult(credits_charged=0, outcome="free_draft")
    assert CreditTransaction.objects.count() == before
    old.refresh_from_db()
    assert old.consumed_credits == 0
    assert ShopCreditBalance.objects.filter(shop=shop).count() == 1
    assert _audit("shop.credits.late_commit")[0].after_data["outcome"] == "free_draft"
    assert_ledger_reconciles(old)


def test_late_commit_is_free_draft_when_current_balance_is_marked_lapsed():
    _org, shop, review = _shop_review(allocation=10)
    res = _reserve(review, credits=3)
    refund_reservation(transaction_id=res.transaction_id, reason="reaped")
    balance = _balance(shop)
    CreditTransactionFactory(
        shop_credit_balance=balance,
        transaction_type=Type.LAPSED,
        status=Status.COMMITTED,
        credits_delta=-7,
    )
    ShopCreditBalance.objects.filter(pk=balance.pk).update(lapsed_at=timezone.now())
    before = CreditTransaction.objects.count()

    with patch(SENTRY):
        result = _late_commit(res)

    assert result == SettleResult(credits_charged=0, outcome="free_draft")
    assert CreditTransaction.objects.count() == before
    assert _balance(shop).consumed_credits == 0
    assert _audit("shop.credits.late_commit")[0].after_data["outcome"] == "free_draft"


def test_late_commit_is_free_draft_when_balance_lapsed_with_zero_remaining():
    _org, shop, review = _shop_review(allocation=10)
    res = _reserve(review, credits=3)
    refund_reservation(transaction_id=res.transaction_id, reason="reaped")
    balance = _balance(shop)
    # Marker only: a zero-remaining lapse writes no LAPSED ledger row.
    ShopCreditBalance.objects.filter(pk=balance.pk).update(lapsed_at=timezone.now())
    before = CreditTransaction.objects.count()

    with patch(SENTRY):
        result = _late_commit(res)

    assert result == SettleResult(credits_charged=0, outcome="free_draft")
    assert CreditTransaction.objects.count() == before
    assert _balance(shop).consumed_credits == 0
    assert _audit("shop.credits.late_commit")[0].after_data["outcome"] == "free_draft"
