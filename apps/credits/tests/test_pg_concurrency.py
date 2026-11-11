"""Real-PostgreSQL concurrency tests for credits (CQA-01, D-14).

SQLite serialises writers, so it can never expose a first-use race. These tests run
in the ``backend-pg`` CI job (and ``make test-pg``) and auto-skip elsewhere.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pytest
from django.db import connection, connections

from apps.common.models import AuditLog
from apps.credits.exceptions import GenerationInProgressError, InsufficientCreditsError
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.allocation import ensure_balance
from apps.credits.services.consumption import (
    SettleResult,
    commit_reservation,
    refund_reservation,
    reserve_credits,
)
from apps.credits.services.ledger import transition_status
from apps.credits.services.reaper import ReapSummary, reap_stale_reservations
from apps.credits.tests.factories import CreditTransactionFactory
from apps.credits.tests.helpers import age_reservation, assert_ledger_reconciles
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

N_THREADS = 8


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_connection_is_postgres_when_pg_concurrency_runs():
    assert connection.vendor == "postgresql"


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_first_use_creates_one_balance_and_one_initial_when_n_threads_race():
    org = OrganisationFactory(monthly_credit_allocation=7)
    shop = ShopFactory(organisation=org)
    barrier = threading.Barrier(N_THREADS)
    results: list[tuple[bool, int]] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            balance, created = ensure_balance(shop_id=shop.pk)
            with lock:
                results.append((created, balance.pk))
        except Exception as exc:
            with lock:
                errors.append(repr(exc))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, errors
    assert len(results) == N_THREADS
    assert [created for created, _ in results].count(True) == 1
    assert len({pk for _, pk in results}) == 1
    assert ShopCreditBalance.objects.filter(shop=shop).count() == 1
    initial = CreditTransaction.objects.filter(
        shop=shop, transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
    )
    assert initial.count() == 1
    assert initial.get().credits_delta == 7
    assert (
        AuditLog.objects.filter(action="shop.credits.allocated", entity_id=str(shop.pk)).count()
        == 1
    )


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_cas_transition_succeeds_once_when_n_threads_settle_same_reservation():
    tx = CreditTransactionFactory(credits_delta=-2)
    barrier = threading.Barrier(N_THREADS)
    results: list[tuple[bool, str]] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        target = (
            CreditTransaction.Status.COMMITTED
            if index % 2 == 0
            else CreditTransaction.Status.REFUNDED
        )
        try:
            barrier.wait(timeout=10)
            won = transition_status(
                transaction_id=tx.pk,
                from_status=CreditTransaction.Status.RESERVED,
                to_status=target,
            )
            with lock:
                results.append((won, target))
        except Exception as exc:
            with lock:
                errors.append(repr(exc))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, errors
    assert len(results) == N_THREADS
    winners = [target for won, target in results if won]
    assert len(winners) == 1
    tx.refresh_from_db()
    assert tx.status == winners[0]


def _run_threads(count: int, target: Callable[[int], None]) -> list[str]:
    """Start ``count`` threads running ``target(index)``; return collected error reprs.

    Every thread closes its own connections in ``finally`` and the join is bounded, so a
    deadlock between the reserve lock order and the settle CAS fails the test instead of
    hanging the suite.
    """
    errors: list[str] = []
    lock = threading.Lock()

    def wrapped(index: int) -> None:
        try:
            target(index)
        except Exception as exc:
            with lock:
                errors.append(repr(exc))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "a worker thread did not finish (deadlock?)"
    return errors


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_reserve_never_overspends_when_n_threads_race_for_k_credits():
    n_threads = 12
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    reviews = [ReviewFactory(organisation=org, shop=shop) for _ in range(n_threads)]
    barrier = threading.Barrier(n_threads)
    reserved: list[int] = []
    denied: list[str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        barrier.wait(timeout=10)
        try:
            res = reserve_credits(
                shop_id=shop.pk, review_id=reviews[index].pk, credits=2, actor_id=None
            )
        except InsufficientCreditsError as exc:
            with lock:
                denied.append(exc.reason)
            return
        with lock:
            reserved.append(res.transaction_id)

    errors = _run_threads(n_threads, worker)

    assert not errors, errors
    assert len(reserved) == 5
    assert denied == ["exhausted"] * 7
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 10
    live = CreditTransaction.objects.filter(
        shop=shop,
        transaction_type=CreditTransaction.Type.CONSUMPTION,
        status=CreditTransaction.Status.RESERVED,
    )
    assert live.count() == 5
    assert_ledger_reconciles(balance)


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_reserve_yields_one_reservation_when_n_threads_race_on_same_review():
    n_threads = 8
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    review = ReviewFactory(organisation=org, shop=shop)
    barrier = threading.Barrier(n_threads)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(_index: int) -> None:
        barrier.wait(timeout=10)
        try:
            reserve_credits(shop_id=shop.pk, review_id=review.pk, credits=1, actor_id=None)
        except GenerationInProgressError:
            with lock:
                outcomes.append("in_progress")
            return
        with lock:
            outcomes.append("reserved")

    errors = _run_threads(n_threads, worker)

    assert not errors, errors
    assert outcomes.count("reserved") == 1
    assert outcomes.count("in_progress") == n_threads - 1
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 1
    assert_ledger_reconciles(balance)


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_first_use_reserve_creates_one_balance_when_n_threads_race():
    n_threads = 8
    org = OrganisationFactory(monthly_credit_allocation=7)
    shop = ShopFactory(organisation=org)
    reviews = [ReviewFactory(organisation=org, shop=shop) for _ in range(n_threads)]
    assert not ShopCreditBalance.objects.filter(shop=shop).exists()
    barrier = threading.Barrier(n_threads)
    reserved: list[int] = []
    denied: list[str] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        barrier.wait(timeout=10)
        try:
            res = reserve_credits(
                shop_id=shop.pk, review_id=reviews[index].pk, credits=1, actor_id=None
            )
        except InsufficientCreditsError as exc:
            with lock:
                denied.append(exc.reason)
            return
        with lock:
            reserved.append(res.transaction_id)

    errors = _run_threads(n_threads, worker)

    assert not errors, errors
    assert len(reserved) == 7
    assert denied == ["exhausted"]
    assert ShopCreditBalance.objects.filter(shop=shop).count() == 1
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 7
    assert (
        CreditTransaction.objects.filter(
            shop=shop, transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
        ).count()
        == 1
    )
    assert_ledger_reconciles(balance)


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_charges_once_when_commit_and_refund_race():
    """Exactly one CAS wins per reservation, and the shop is charged exactly once either way.

    Not the reaper test: the orchestrator only ever commits a reservation once, so each
    reservation here has one committer racing one bare refunder. The real reaper racing a late
    commit is ``test_reaper_and_late_commit_settle_each_reservation_once_when_racing`` below
    (Phase 31, CREN-03).
    """
    n_reservations = 10
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    reviews = [ReviewFactory(organisation=org, shop=shop) for _ in range(n_reservations)]
    reservations = [
        reserve_credits(shop_id=shop.pk, review_id=r.pk, credits=1, actor_id=None) for r in reviews
    ]
    barriers = [threading.Barrier(2) for _ in reservations]
    refund_wins: list[int] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        reservation = reservations[index // 2]
        barriers[index // 2].wait(timeout=10)
        if index % 2 == 0:
            commit_reservation(
                transaction_id=reservation.transaction_id,
                ai_usage_log_id=None,
                outcome="success",
                actor_id=None,
            )
        elif refund_reservation(
            transaction_id=reservation.transaction_id, reason="unexpected_error"
        ):
            with lock:
                refund_wins.append(reservation.transaction_id)

    errors = _run_threads(n_reservations * 2, worker)

    assert not errors, errors
    for review in reviews:
        committed = CreditTransaction.objects.filter(
            review=review,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status=CreditTransaction.Status.COMMITTED,
        )
        assert committed.count() == 1
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == n_reservations
    assert balance.consumed_credits <= balance.allocated_credits + balance.bonus_credits
    late_rows = CreditTransaction.objects.filter(shop=shop, note="late_commit")
    assert late_rows.count() == len(refund_wins)
    rededucted = [
        a
        for a in AuditLog.objects.filter(action="shop.credits.late_commit", entity_id=str(shop.pk))
        if a.after_data["outcome"] == "rededucted"
    ]
    assert len(rededucted) == len(refund_wins)
    assert_ledger_reconciles(balance)


def _refunded_audit_rows(shop_id: int, transaction_id: int) -> list[AuditLog]:
    return [
        a
        for a in AuditLog.objects.filter(action="shop.credits.refunded", entity_id=str(shop_id))
        if a.after_data["transaction_id"] == transaction_id
    ]


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_reaper_and_late_commit_settle_each_reservation_once_when_racing():
    """Phase 31 reaper-vs-late-commit test (CREN-03, CQA-01).

    Uses the real ``reap_stale_reservations`` (not a bare refund) against ``commit_reservation``
    on one stale reservation per round. Either the commit wins (reaper reaps nothing) or the
    reaper wins and the late commit re-deducts once; the shop is charged exactly once per review.
    """
    n_rounds = 10
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    reviews = [ReviewFactory(organisation=org, shop=shop) for _ in range(n_rounds)]
    split = {"committed": 0, "refunded": 0}

    for round_index, review in enumerate(reviews):
        res = reserve_credits(shop_id=shop.pk, review_id=review.pk, credits=1, actor_id=None)
        age_reservation(res.transaction_id, minutes=6)
        barrier = threading.Barrier(2)
        reaped: list[ReapSummary] = []
        settled: list[SettleResult] = []
        lock = threading.Lock()

        def worker(
            index: int,
            barrier: threading.Barrier = barrier,
            tx_id: int = res.transaction_id,
            reaped: list[ReapSummary] = reaped,
            settled: list[SettleResult] = settled,
            lock: threading.Lock = lock,
            delay: float = 0.003 * (round_index % 2),
        ) -> None:
            barrier.wait(timeout=10)
            if index == 0:
                summary = reap_stale_reservations()
                with lock:
                    reaped.append(summary)
            else:
                # Odd rounds delay the committer 3ms, even rounds do not, so both orderings
                # (commit first, reaper first) are likely every run; either winner is accepted.
                if delay:
                    time.sleep(delay)
                result = commit_reservation(
                    transaction_id=tx_id, ai_usage_log_id=None, outcome="success", actor_id=None
                )
                with lock:
                    settled.append(result)

        errors = _run_threads(2, worker)

        assert not errors, errors
        assert len(reaped) == 1
        assert len(settled) == 1
        summary = reaped[0]
        result = settled[0]
        assert summary.errored == 0
        tx = CreditTransaction.objects.get(pk=res.transaction_id)
        refunds = _refunded_audit_rows(shop.pk, res.transaction_id)
        late = CreditTransaction.objects.filter(review=review, note="late_commit")
        if tx.status == CreditTransaction.Status.COMMITTED:
            split["committed"] += 1
            assert result.outcome == "committed"
            assert refunds == []
            assert summary.reaped == 0
            assert late.count() == 0
        else:
            split["refunded"] += 1
            assert tx.status == CreditTransaction.Status.REFUNDED
            assert len(refunds) == 1
            assert refunds[0].after_data["reason"] == "reaped_stale"
            assert summary.reaped == 1
            assert result.outcome == "rededucted"
            assert late.count() == 1
            assert late.get().status == CreditTransaction.Status.COMMITTED

    for review in reviews:
        committed = CreditTransaction.objects.filter(
            review=review,
            transaction_type=CreditTransaction.Type.CONSUMPTION,
            status=CreditTransaction.Status.COMMITTED,
        )
        assert committed.count() == 1
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == n_rounds
    assert balance.consumed_credits <= balance.allocated_credits + balance.bonus_credits
    assert_ledger_reconciles(balance)
    assert split["committed"] + split["refunded"] == n_rounds
    print(f"reaper-vs-late-commit split: {split}")  # noqa: T201 - recorded in the SUMMARY
