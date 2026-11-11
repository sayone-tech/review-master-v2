"""CREN-01: the monthly lapse service and sweep (Phase 31).

Every test injects ``now=`` (no clock freezing); past/current boundaries are fixed around
``NOW``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.lapse import list_unlapsed_past_balance_ids
from apps.credits.services import lapse as lapse_module
from apps.credits.services.consumption import commit_reservation
from apps.credits.services.lapse import lapse_balance, lapse_past_balances
from apps.credits.tests.factories import CreditTransactionFactory, ShopCreditBalanceFactory
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

Status = CreditTransaction.Status
Type = CreditTransaction.Type

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
# Measured: SAVEPOINT, SELECT FOR UPDATE, RESERVED check, LAPSED insert, AuditLog insert,
# marker UPDATE, RELEASE SAVEPOINT (SQLite counts savepoints; fixed per balance).
LAPSE_BALANCE_QUERY_CEILING = 7


def _balance(shop, year, month, **credits):
    return ShopCreditBalanceFactory(shop=shop, period_year=year, period_month=month, **credits)


def test_lapse_past_balances_lapses_one_past_balance_and_skips_current_when_now_is_injected():
    shop = ShopFactory()
    past = _balance(shop, 2026, 2, allocated_credits=10, consumed_credits=4)
    current = _balance(shop, 2026, 3, allocated_credits=10, consumed_credits=2)

    summary = lapse_past_balances(now=NOW)

    assert summary.lapsed == 1
    assert summary.credits_lapsed == 6
    lapsed_row = CreditTransaction.objects.get(shop_credit_balance=past, transaction_type="LAPSED")
    assert lapsed_row.credits_delta == -6
    assert AuditLog.objects.filter(action="shop.credits.lapsed").count() == 1
    past.refresh_from_db()
    current.refresh_from_db()
    assert past.lapsed_at == NOW
    assert current.lapsed_at is None
    assert not CreditTransaction.objects.filter(shop_credit_balance=current).exists()
    assert ShopCreditBalance.objects.count() == 2


def _lapsed_rows(balance):
    return CreditTransaction.objects.filter(shop_credit_balance=balance, transaction_type="LAPSED")


def _audit_count():
    return AuditLog.objects.filter(action="shop.credits.lapsed").count()


# --- zero remaining (D-02) -------------------------------------------------------


@pytest.mark.parametrize(
    ("allocated", "bonus", "consumed"),
    [(10, 0, 10), (8, 2, 10), (0, 0, 0)],
    ids=["fully_used", "fully_used_with_bonus", "nothing_allocated"],
)
def test_zero_remaining_balance_is_marked_without_ledger_or_audit_row_when_lapsing(
    allocated, bonus, consumed
):
    past = _balance(
        ShopFactory(),
        2026,
        2,
        allocated_credits=allocated,
        bonus_credits=bonus,
        consumed_credits=consumed,
    )

    outcome = lapse_balance(balance_id=past.pk, now=NOW)

    assert outcome.status == "lapsed_zero"
    assert outcome.lapsed_credits == 0
    past.refresh_from_db()
    assert past.lapsed_at == NOW
    assert not _lapsed_rows(past).exists()
    assert _audit_count() == 0


def test_bonus_only_balance_lapses_remaining_bonus_when_allocation_is_zero():
    past = _balance(
        ShopFactory(), 2026, 2, allocated_credits=0, bonus_credits=5, consumed_credits=2
    )

    outcome = lapse_balance(balance_id=past.pk, now=NOW)

    assert outcome.status == "lapsed"
    assert outcome.lapsed_credits == 3
    assert _lapsed_rows(past).get().credits_delta == -3


# --- idempotency and catch-up (D-05) -------------------------------------------


def test_second_sweep_writes_nothing_when_all_balances_already_lapsed():
    shop = ShopFactory()
    _balance(shop, 2026, 2, allocated_credits=10, consumed_credits=4)
    _balance(ShopFactory(), 2026, 1, allocated_credits=5, consumed_credits=5)
    lapse_past_balances(now=NOW)
    tx_count, audit_count = CreditTransaction.objects.count(), AuditLog.objects.count()

    again = lapse_past_balances(now=NOW)

    assert (again.lapsed, again.lapsed_zero) == (0, 0)
    assert CreditTransaction.objects.count() == tx_count
    assert AuditLog.objects.count() == audit_count


def test_lapse_balance_returns_skipped_noop_when_balance_already_lapsed():
    past = _balance(ShopFactory(), 2026, 2, allocated_credits=10)
    assert lapse_balance(balance_id=past.pk, now=NOW).status == "lapsed"

    outcome = lapse_balance(balance_id=past.pk, now=NOW)

    assert outcome.status == "skipped_noop"
    assert _lapsed_rows(past).count() == 1


def test_all_outstanding_past_months_lapse_in_one_run_when_sweeps_were_missed():
    shop = ShopFactory()
    old = [
        _balance(shop, 2026, 2, allocated_credits=10),
        _balance(shop, 2026, 1, allocated_credits=10),
        _balance(shop, 2025, 2, allocated_credits=10),
    ]

    summary = lapse_past_balances(now=NOW)

    assert summary.lapsed == 3
    assert summary.credits_lapsed == 30
    assert all(ShopCreditBalance.objects.get(pk=b.pk).lapsed_at is not None for b in old)


def test_december_balance_lapses_when_now_is_january_of_next_year():
    shop = ShopFactory()
    december = _balance(shop, 2025, 12, allocated_credits=10)
    january = _balance(shop, 2026, 1, allocated_credits=10)

    summary = lapse_past_balances(now=datetime(2026, 1, 10, tzinfo=UTC))

    assert summary.lapsed == 1
    december.refresh_from_db()
    january.refresh_from_db()
    assert december.lapsed_at is not None
    assert january.lapsed_at is None


@pytest.mark.parametrize(("year", "month"), [(2026, 3), (2026, 4), (2027, 1)])
def test_lapse_balance_is_a_noop_when_period_is_current_or_future(year, month):
    balance = _balance(ShopFactory(), year, month, allocated_credits=10)

    outcome = lapse_balance(balance_id=balance.pk, now=NOW)

    assert outcome.status == "skipped_noop"
    balance.refresh_from_db()
    assert balance.lapsed_at is None
    assert CreditTransaction.objects.count() == 0
    assert AuditLog.objects.count() == 0


def test_inactive_shop_balance_lapses_like_an_active_one():
    past = _balance(ShopFactory(is_active=False), 2026, 2, allocated_credits=10)

    summary = lapse_past_balances(now=NOW)

    assert summary.lapsed == 1
    assert _lapsed_rows(past).count() == 1


def test_lapse_rows_carry_their_own_tenant_when_two_organisations_lapse():
    orgs = [OrganisationFactory(), OrganisationFactory()]
    shops = [ShopFactory(organisation=o) for o in orgs]
    balances = [_balance(s, 2026, 2, allocated_credits=10) for s in shops]

    lapse_past_balances(now=NOW)

    for org, shop, balance in zip(orgs, shops, balances, strict=True):
        row = _lapsed_rows(balance).get()
        assert (row.organisation_id, row.shop_id) == (org.pk, shop.pk)
        audit = AuditLog.objects.get(action="shop.credits.lapsed", entity_id=str(shop.pk))
        assert audit.organisation_id == org.pk
        assert audit.after_data["transaction_id"] == row.pk


# --- held reservations (D-07, ROADMAP SC4) ---------------------------------------


def test_held_balance_is_skipped_then_lapses_after_its_reservation_commits():
    shop = ShopFactory()
    past = _balance(shop, 2026, 2, allocated_credits=10, bonus_credits=2, consumed_credits=3)
    tx = CreditTransactionFactory(
        shop_credit_balance=past, credits_delta=-3, status=Status.RESERVED
    )

    held = lapse_past_balances(now=NOW)

    assert (held.skipped_held, held.lapsed) == (1, 0)
    past.refresh_from_db()
    assert past.lapsed_at is None
    assert not _lapsed_rows(past).exists()
    assert _audit_count() == 0

    commit_reservation(transaction_id=tx.pk, ai_usage_log_id=None, outcome="success", actor_id=None)
    settled = lapse_past_balances(now=NOW)

    assert settled.lapsed == 1
    assert _lapsed_rows(past).get().credits_delta == -(10 + 2 - 3)
    assert AuditLog.objects.get(action="shop.credits.lapsed").after_data["lapsed"] == 9
    past.refresh_from_db()
    assert past.lapsed_at == NOW
    assert_ledger_reconciles(past)


# --- sweep safety (D-06, D-12) ---------------------------------------------------


def test_sweep_terminates_when_a_held_balance_exists_and_chunk_size_is_one(settings):
    settings.REVIEWBEE_CREDIT_LAPSE_CHUNK_SIZE = 1
    held = _balance(ShopFactory(), 2026, 2, allocated_credits=10, consumed_credits=1)
    CreditTransactionFactory(shop_credit_balance=held, credits_delta=-1, status=Status.RESERVED)
    _balance(ShopFactory(), 2026, 2, allocated_credits=10)
    _balance(ShopFactory(), 2026, 1, allocated_credits=10)

    with patch.object(
        lapse_module, "list_unlapsed_past_balance_ids", wraps=list_unlapsed_past_balance_ids
    ) as selector:
        summary = lapse_past_balances(now=NOW)

    assert (summary.lapsed, summary.skipped_held) == (2, 1)
    assert selector.call_count <= 4


def test_sweep_continues_and_counts_error_when_one_balance_raises():
    bad = _balance(ShopFactory(), 2026, 2, allocated_credits=10)
    good = _balance(ShopFactory(), 2026, 2, allocated_credits=10)
    real = lapse_balance

    def flaky(*, balance_id, now=None):
        if balance_id == bad.pk:
            raise ValueError("boom")
        return real(balance_id=balance_id, now=now)

    with patch.object(lapse_module, "lapse_balance", side_effect=flaky):
        summary = lapse_past_balances(now=NOW)

    assert (summary.errored, summary.lapsed) == (1, 1)
    assert ShopCreditBalance.objects.get(pk=good.pk).lapsed_at is not None
    assert ShopCreditBalance.objects.get(pk=bad.pk).lapsed_at is None


def test_sweep_counts_error_and_rolls_back_when_a_stray_lapsed_row_exists():
    stray = _balance(ShopFactory(), 2026, 2, allocated_credits=10, consumed_credits=4)
    CreditTransactionFactory(
        shop_credit_balance=stray,
        transaction_type=Type.LAPSED,
        status=Status.COMMITTED,
        credits_delta=-5,
    )
    ok = _balance(ShopFactory(), 2026, 2, allocated_credits=10)

    summary = lapse_past_balances(now=NOW)

    assert (summary.errored, summary.lapsed) == (1, 1)
    stray.refresh_from_db()
    assert stray.lapsed_at is None
    assert _lapsed_rows(stray).count() == 1
    assert _audit_count() == 1
    assert ShopCreditBalance.objects.get(pk=ok.pk).lapsed_at is not None


def test_sweep_reraises_soft_time_limit_when_lapse_balance_hits_it():
    _balance(ShopFactory(), 2026, 2, allocated_credits=10)

    with (
        patch.object(lapse_module, "lapse_balance", side_effect=SoftTimeLimitExceeded()),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        lapse_past_balances(now=NOW)


# --- query ceiling (CLAUDE.md section 6) -------------------------------------------


@pytest.mark.parametrize("count", [2, 5])
def test_selection_issues_one_query_regardless_of_eligible_balance_count(count):
    for _ in range(count):
        _balance(ShopFactory(), 2026, 2, allocated_credits=10)

    with CaptureQueriesContext(connection) as ctx:
        ids = list_unlapsed_past_balance_ids(now=NOW, after_pk=0, limit=100)

    assert len(ids) == count
    assert len(ctx.captured_queries) == 1


def _lapse_queries(ledger_rows: int) -> CaptureQueriesContext:
    balance = _balance(ShopFactory(), 2026, 2, allocated_credits=20, consumed_credits=ledger_rows)
    for _ in range(ledger_rows):
        CreditTransactionFactory(
            shop_credit_balance=balance, credits_delta=-1, status=Status.COMMITTED
        )
    with CaptureQueriesContext(connection) as ctx:
        assert lapse_balance(balance_id=balance.pk, now=NOW).status == "lapsed"
    return ctx


def test_lapse_balance_query_count_is_fixed_when_ledger_grows(assert_query_ceiling):
    small = _lapse_queries(1)
    large = _lapse_queries(6)

    assert len(small.captured_queries) == len(large.captured_queries)
    assert_query_ceiling(large, LAPSE_BALANCE_QUERY_CEILING)
