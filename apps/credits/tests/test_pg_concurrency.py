"""Real-PostgreSQL concurrency tests for credits (CQA-01, D-14).

SQLite serialises writers, so it can never expose a first-use race. These tests run
in the ``backend-pg`` CI job (and ``make test-pg``) and auto-skip elsewhere.
"""

from __future__ import annotations

import threading

import pytest
from django.db import connection, connections

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.allocation import ensure_balance
from apps.credits.services.ledger import transition_status
from apps.credits.tests.factories import CreditTransactionFactory
from apps.organisations.tests.factories import OrganisationFactory
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
