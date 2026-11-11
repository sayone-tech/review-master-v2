"""Reservation reaper (Phase 31: CREN-03, D-07..D-12)."""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.reservations import list_stale_reservations
from apps.credits.services import consumption
from apps.credits.services.consumption import (
    SettleResult,
    commit_reservation,
    refund_reservation,
    reserve_credits,
)
from apps.credits.services.lapse import lapse_past_balances
from apps.credits.services.periods import current_period
from apps.credits.services.reaper import reap_stale_reservations
from apps.credits.tests.factories import CreditTransactionFactory, ShopCreditBalanceFactory
from apps.credits.tests.helpers import age_reservation, assert_ledger_reconciles
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

SENTRY = "apps.credits.services.reaper.sentry_sdk.capture_message"
SECRET = "SECRET-REVIEW-TEXT"
REFUND = "apps.credits.services.reaper.refund_reservation"
Status = CreditTransaction.Status


def _shop_review(*, allocation: int = 10):
    org = OrganisationFactory(monthly_credit_allocation=allocation)
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(organisation=org, shop=shop, comment=SECRET)
    return org, shop, review


def test_reaper_logs_one_warning_and_one_sentry_count_when_one_reservation_is_reaped(caplog):
    _org, shop, review = _shop_review()
    res = reserve_credits(shop_id=shop.pk, review_id=review.pk, credits=3, actor_id=None)
    age_reservation(res.transaction_id, minutes=6)

    with (
        patch(SENTRY) as sentry,
        caplog.at_level(logging.WARNING, logger="apps.credits.services.reaper"),
    ):
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.skipped, summary.errored) == (1, 0, 0)
    records = [r for r in caplog.records if r.name == "apps.credits.services.reaper"]
    assert len(records) == 1
    assert records[0].getMessage().startswith("credits.reaped tx_id=")
    sentry.assert_called_once()
    assert sentry.call_args.kwargs["level"] == "warning"
    assert "count=1" in sentry.call_args.args[0]
    assert SECRET not in caplog.text
    assert SECRET not in str(sentry.call_args_list)
    for log in AuditLog.objects.all():
        assert SECRET not in json.dumps(log.after_data)
    assert_ledger_reconciles(ShopCreditBalance.objects.get(pk=res.shop_credit_balance_id))
    assert CreditTransaction.objects.get(pk=res.transaction_id).status == "REFUNDED"


def _status(tx_id: int) -> str:
    return CreditTransaction.objects.values_list("status", flat=True).get(pk=tx_id)


def _balance(pk: int) -> ShopCreditBalance:
    return ShopCreditBalance.objects.get(pk=pk)


def _reserve(shop, org, credits: int, *, age: int | None = None):
    review = ReviewFactory(organisation=org, shop=shop, comment=SECRET)
    res = reserve_credits(shop_id=shop.pk, review_id=review.pk, credits=credits, actor_id=None)
    if age is not None:
        age_reservation(res.transaction_id, minutes=age)
    return res


def _previous_period() -> tuple[int, int]:
    p = current_period()
    return (p.year - 1, 12) if p.month == 1 else (p.year, p.month - 1)


def _past_balance(shop, *, allocated=10, bonus=0, consumed=0):
    year, month = _previous_period()
    return ShopCreditBalanceFactory(
        shop=shop,
        period_year=year,
        period_month=month,
        allocated_credits=allocated,
        bonus_credits=bonus,
        consumed_credits=consumed,
    )


def _past_reservation(balance, shop, *, credits: int, age: int):
    review = ReviewFactory(organisation=shop.organisation, shop=shop, comment=SECRET)
    tx = CreditTransactionFactory(
        shop_credit_balance=balance,
        credits_delta=-credits,
        review=review,
        status=Status.RESERVED,
    )
    age_reservation(tx.pk, minutes=age)
    return tx


def test_reaper_respects_ttl_boundary_when_one_row_is_younger_than_ttl():
    org, shop, _review = _shop_review()
    young = _reserve(shop, org, 1, age=4)
    old = _reserve(shop, org, 2, age=6)

    with patch(SENTRY):
        summary = reap_stale_reservations()

    assert summary.reaped == 1
    assert _status(old.transaction_id) == Status.REFUNDED
    assert _status(young.transaction_id) == Status.RESERVED
    assert _balance(young.shop_credit_balance_id).consumed_credits == 1


def test_reaper_writes_nothing_when_run_twice():
    org, shop, _review = _shop_review()
    _reserve(shop, org, 3, age=9)
    with patch(SENTRY):
        reap_stale_reservations()
    audit_before = AuditLog.objects.count()

    with patch(SENTRY) as sentry:
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.skipped, summary.errored, summary.lapsed_after) == (0, 0, 0, 0)
    assert AuditLog.objects.count() == audit_before
    sentry.assert_not_called()


def test_reaper_ignores_committed_and_refunded_rows_when_aged():
    org, shop, _review = _shop_review()
    committed = _reserve(shop, org, 2)
    commit_reservation(
        transaction_id=committed.transaction_id,
        ai_usage_log_id=None,
        outcome="success",
        actor_id=None,
    )
    refunded = _reserve(shop, org, 1)
    refund_reservation(transaction_id=refunded.transaction_id, reason="x")
    age_reservation(committed.transaction_id, minutes=10)
    age_reservation(refunded.transaction_id, minutes=10)
    audit_before = AuditLog.objects.count()

    with patch(SENTRY) as sentry:
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.skipped, summary.errored) == (0, 0, 0)
    assert _status(committed.transaction_id) == Status.COMMITTED
    assert _status(refunded.transaction_id) == Status.REFUNDED
    assert _balance(committed.shop_credit_balance_id).consumed_credits == 2
    assert AuditLog.objects.count() == audit_before
    sentry.assert_not_called()


def test_reaper_skips_row_when_commit_wins_after_selection():
    org, shop, _review = _shop_review()
    res = _reserve(shop, org, 3, age=9)

    def select_then_commit(**kwargs):
        rows = list_stale_reservations(**kwargs)
        commit_reservation(
            transaction_id=res.transaction_id,
            ai_usage_log_id=None,
            outcome="success",
            actor_id=None,
        )
        return rows

    with (
        patch("apps.credits.services.reaper.list_stale_reservations", select_then_commit),
        patch(SENTRY) as sentry,
    ):
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.skipped, summary.errored) == (0, 1, 0)
    assert _status(res.transaction_id) == Status.COMMITTED
    assert not AuditLog.objects.filter(action="shop.credits.refunded").exists()
    sentry.assert_not_called()
    assert_ledger_reconciles(_balance(res.shop_credit_balance_id))


def test_reaper_caps_batch_oldest_first_when_batch_size_is_two(settings):
    settings.REVIEWBEE_CREDIT_REAPER_BATCH_SIZE = 2
    org, shop, _review = _shop_review()
    oldest = _reserve(shop, org, 1, age=9)
    middle = _reserve(shop, org, 1, age=8)
    newest = _reserve(shop, org, 1, age=7)

    with patch(SENTRY):
        first = reap_stale_reservations()

    assert first.reaped == 2
    assert _status(oldest.transaction_id) == Status.REFUNDED
    assert _status(middle.transaction_id) == Status.REFUNDED
    assert _status(newest.transaction_id) == Status.RESERVED

    with patch(SENTRY):
        second = reap_stale_reservations()

    assert second.reaped == 1
    assert _status(newest.transaction_id) == Status.REFUNDED


def test_reaper_relapses_past_balance_when_refund_frees_it():
    org, shop, _review = _shop_review()
    old = _past_balance(shop, allocated=10, bonus=2, consumed=3)
    tx = _past_reservation(old, shop, credits=3, age=9)
    current_res = _reserve(shop, org, 2, age=9)

    with patch(SENTRY):
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.lapsed_after) == (2, 1)
    assert _status(tx.pk) == Status.REFUNDED
    lapsed = list(
        CreditTransaction.objects.filter(shop_credit_balance=old, transaction_type="LAPSED")
    )
    assert len(lapsed) == 1
    assert lapsed[0].credits_delta == -12
    audit = AuditLog.objects.get(action="shop.credits.lapsed")
    assert audit.after_data["consumed"] == 0
    assert audit.after_data["lapsed"] == 12
    assert _balance(old.pk).lapsed_at is not None
    assert _balance(current_res.shop_credit_balance_id).lapsed_at is None


def test_reaper_does_not_lapse_past_balance_when_fresh_reservation_remains():
    _org, shop, _review = _shop_review()
    old = _past_balance(shop, allocated=10, consumed=4)
    _past_reservation(old, shop, credits=3, age=9)
    _past_reservation(old, shop, credits=1, age=1)

    with patch(SENTRY):
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.lapsed_after) == (1, 0)
    assert _balance(old.pk).lapsed_at is None
    assert not CreditTransaction.objects.filter(
        shop_credit_balance=old, transaction_type="LAPSED"
    ).exists()


def test_reaper_counts_error_and_keeps_row_when_refund_cannot_apply():
    _org, shop, _review = _shop_review()
    old = _past_balance(shop, allocated=10, consumed=4)
    ok = _past_reservation(old, shop, credits=1, age=9)
    bad = _past_reservation(old, shop, credits=3, age=8)
    # Corrupt the balance so the 3-credit refund cannot apply (test-only direct update).
    ShopCreditBalance.objects.filter(pk=old.pk).update(consumed_credits=2)

    with patch(SENTRY) as sentry:
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.errored, summary.lapsed_after) == (1, 1, 0)
    assert _status(ok.pk) == Status.REFUNDED
    assert _status(bad.pk) == Status.RESERVED
    assert _balance(old.pk).lapsed_at is None
    assert not CreditTransaction.objects.filter(
        shop_credit_balance=old, transaction_type="LAPSED"
    ).exists()
    calls = {c.kwargs["level"]: c.args[0] for c in sentry.call_args_list}
    assert sentry.call_count == 2
    assert calls["error"] == (f"credits.reaper.refund_failed tx_id={bad.pk} balance_id={old.pk}")
    assert "count=1" in calls["warning"]
    assert SECRET not in str(sentry.call_args_list)


def test_reaper_isolates_unexpected_error_and_reaps_other_rows():
    org, shop, _review = _shop_review()
    first = _reserve(shop, org, 1, age=9)
    second = _reserve(shop, org, 1, age=8)
    real = consumption.refund_reservation

    def flaky(**kwargs):
        if kwargs["transaction_id"] == first.transaction_id:
            raise ValueError("boom")
        return real(**kwargs)

    with patch(REFUND, side_effect=flaky), patch(SENTRY):
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.errored) == (1, 1)
    assert _status(first.transaction_id) == Status.RESERVED
    assert _status(second.transaction_id) == Status.REFUNDED


def test_reaper_reraises_soft_time_limit():
    org, shop, _review = _shop_review()
    _reserve(shop, org, 1, age=9)

    with patch(REFUND, side_effect=SoftTimeLimitExceeded), pytest.raises(SoftTimeLimitExceeded):
        reap_stale_reservations()


def test_reaper_sends_no_sentry_message_when_nothing_is_stale():
    with patch(SENTRY) as sentry:
        summary = reap_stale_reservations()

    assert (summary.reaped, summary.skipped, summary.errored, summary.lapsed_after) == (0, 0, 0, 0)
    sentry.assert_not_called()


def test_reaper_settles_straddling_reservation_before_lapse_and_late_commit_is_free():
    _org, shop, _review = _shop_review()
    old = _past_balance(shop, allocated=10, consumed=3)
    tx = _past_reservation(old, shop, credits=3, age=9)

    swept = lapse_past_balances()
    assert swept.skipped_held == 1
    assert not CreditTransaction.objects.filter(
        shop_credit_balance=old, transaction_type="LAPSED"
    ).exists()

    with patch(SENTRY):
        summary = reap_stale_reservations()
    assert (summary.reaped, summary.lapsed_after) == (1, 1)

    with patch("apps.credits.services.consumption.sentry_sdk.capture_message"):
        result = commit_reservation(
            transaction_id=tx.pk, ai_usage_log_id=None, outcome="success", actor_id=None
        )

    assert result == SettleResult(credits_charged=0, outcome="free_draft")
    refreshed = _balance(old.pk)
    assert refreshed.consumed_credits == 0
    assert (
        CreditTransaction.objects.filter(shop_credit_balance=old, transaction_type="LAPSED").count()
        == 1
    )
    assert_ledger_reconciles(refreshed)


@pytest.mark.parametrize("count", [2, 5])
def test_list_stale_reservations_issues_one_query_regardless_of_row_count(count):
    org, shop, _review = _shop_review(allocation=50)
    for _ in range(count):
        _reserve(shop, org, 1, age=9)

    with CaptureQueriesContext(connection) as ctx:
        rows = list_stale_reservations(now=timezone.now(), limit=500)

    assert len(rows) == count
    assert len(ctx.captured_queries) == 1
