"""Reservation reaper (Phase 31: CREN-03, D-07..D-12)."""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.consumption import reserve_credits
from apps.credits.services.reaper import reap_stale_reservations
from apps.credits.tests.helpers import age_reservation, assert_ledger_reconciles
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

SENTRY = "apps.credits.services.reaper.sentry_sdk.capture_message"
SECRET = "SECRET-REVIEW-TEXT"


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
