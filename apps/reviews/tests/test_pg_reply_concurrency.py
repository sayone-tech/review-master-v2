"""Real-PostgreSQL concurrency tests for metered reply generation (CCON-02, D-03, D-12).

SQLite serialises writers, so only PostgreSQL can show that N concurrent generate requests
against K remaining credits never spend more than K, that two requests for one review yield
a single reservation, and that a request aborted mid-draft still settles. These run in the
``backend-pg`` CI job (and locally with ``--ds=config.settings.test_pg``) and auto-skip on
SQLite.

The OpenAI layer is never reached: the draft seam
``apps.reviews.services.reply_generation._generate_reply_draft_with_log`` is patched once,
outside the threads (a patch is process-global, so every worker sees it).
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from asgiref.sync import ThreadSensitiveContext, sync_to_async
from django.db import connections

from apps.accounts.tests.factories import OrgAdminFactory
from apps.common.models import AuditLog
from apps.credits.exceptions import GenerationInProgressError, InsufficientCreditsError
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.balances import get_shop_credit_balance
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.integrations.openai.exceptions import OpenAITransientError
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import Review
from apps.reviews.services.reply_generation import (
    ReplyUnavailableError,
    generate_reply_with_credits,
)
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

SEAM = "apps.reviews.services.reply_generation._generate_reply_draft_with_log"
COST_2_COMMENT = "x" * 150
COST_3_COMMENT = "x" * 600

Status = CreditTransaction.Status


def _slow_draft(*, review: Review, tone: str, log_holder: Any = None) -> tuple[str, None]:
    time.sleep(0.05)  # widen the race window
    return "draft", None


def _setup(*, allocation: int, comment: str, n_reviews: int):
    org = OrganisationFactory(monthly_credit_allocation=allocation)
    shop = ShopFactory(organisation=org)
    user = OrgAdminFactory(organisation=org)
    reviews = [
        ReviewFactory(organisation=org, shop=shop, comment=comment) for _ in range(n_reviews)
    ]
    return shop, user, reviews


def _run_generate_threads(
    *, reviews: list[Review], user_pk: int, seam: Callable[..., tuple[str, None]]
) -> tuple[list[tuple[int, str, str]], list[str]]:
    """Run one generate call per entry of ``reviews`` behind a barrier.

    Returns ``([(review_pk, outcome, exception_class_name), ...], errors)``. ``outcome`` is
    ``"success"`` or ``"error"``; unexpected exception classes are surfaced by the caller's
    assertions on the recorded class name.
    """
    barrier = threading.Barrier(len(reviews))
    results: list[tuple[int, str, str]] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker(review_pk: int) -> None:
        try:
            barrier.wait(timeout=10)
            review = Review.objects.select_related("shop__organisation").get(pk=review_pk)
            try:
                generate_reply_with_credits(review=review, tone="professional", actor_id=user_pk)
            except Exception as exc:
                with lock:
                    results.append((review_pk, "error", type(exc).__name__))
            else:
                with lock:
                    results.append((review_pk, "success", ""))
        except Exception as exc:
            with lock:
                errors.append(repr(exc))
        finally:
            connections.close_all()

    with patch(SEAM, side_effect=seam):
        threads = [threading.Thread(target=worker, args=(r.pk,)) for r in reviews]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "a worker thread did not finish (deadlock?)"
    return results, errors


def _committed(shop) -> int:
    return CreditTransaction.objects.filter(
        shop=shop,
        transaction_type=CreditTransaction.Type.CONSUMPTION,
        status=Status.COMMITTED,
    ).count()


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_generate_never_overspends_when_n_threads_race_for_k_credits():
    shop, user, reviews = _setup(allocation=10, comment=COST_2_COMMENT, n_reviews=12)

    results, errors = _run_generate_threads(reviews=reviews, user_pk=user.pk, seam=_slow_draft)

    assert not errors, errors
    assert len(results) == 12
    assert [r for r in results if r[1] == "success"].__len__() == 5
    assert (
        sorted(r[2] for r in results if r[1] == "error") == [InsufficientCreditsError.__name__] * 7
    )
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 10
    assert balance.consumed_credits <= balance.allocated_credits + balance.bonus_credits
    assert _committed(shop) == 5
    assert (
        AuditLog.objects.filter(action="shop.credits.consumed", entity_id=str(shop.pk)).count() == 5
    )
    assert_ledger_reconciles(balance)


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_generate_leaves_one_credit_when_n_threads_race_with_cost_three():
    shop, user, reviews = _setup(allocation=10, comment=COST_3_COMMENT, n_reviews=6)

    results, errors = _run_generate_threads(reviews=reviews, user_pk=user.pk, seam=_slow_draft)

    assert not errors, errors
    assert len([r for r in results if r[1] == "success"]) == 3
    assert {r[2] for r in results if r[1] == "error"} == {InsufficientCreditsError.__name__}
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 9
    assert get_shop_credit_balance(shop_id=shop.pk).remaining == 1
    assert_ledger_reconciles(balance)


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_refunded_failures_free_credits_when_mixed_threads_race():
    shop, user, reviews = _setup(allocation=10, comment=COST_2_COMMENT, n_reviews=12)

    def flaky(*, review: Review, tone: str, log_holder: Any = None) -> tuple[str, None]:
        time.sleep(0.05)
        if review.pk % 2 == 1:
            raise OpenAITransientError("simulated outage")
        return "draft", None

    results, errors = _run_generate_threads(reviews=reviews, user_pk=user.pk, seam=flaky)

    assert not errors, errors
    assert len(results) == 12
    by_review = {pk: (outcome, exc) for pk, outcome, exc in results}
    for review in reviews:
        if review.pk % 2 == 1 and by_review[review.pk][0] == "error":
            # An odd review either failed its draft (refunded, 502) or never reserved (402).
            assert by_review[review.pk][1] in {
                ReplyUnavailableError.__name__,
                InsufficientCreditsError.__name__,
            }
    refunded_reviews = set(
        CreditTransaction.objects.filter(shop=shop, status=Status.REFUNDED).values_list(
            "review_id", flat=True
        )
    )
    unavailable = {pk for pk, outcome, exc in results if exc == ReplyUnavailableError.__name__}
    assert unavailable == refunded_reviews
    assert all(pk % 2 == 1 for pk in unavailable)
    assert {exc for _, outcome, exc in results if outcome == "error"} <= {
        ReplyUnavailableError.__name__,
        InsufficientCreditsError.__name__,
    }
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 2 * _committed(shop)
    assert balance.consumed_credits <= balance.allocated_credits + balance.bonus_credits
    assert not CreditTransaction.objects.filter(shop=shop, status=Status.RESERVED).exists()
    assert_ledger_reconciles(balance)


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_generate_yields_one_success_when_n_threads_race_on_same_review():
    shop, user, reviews = _setup(allocation=10, comment=COST_2_COMMENT, n_reviews=1)
    same_review = [reviews[0]] * 8

    results, errors = _run_generate_threads(reviews=same_review, user_pk=user.pk, seam=_slow_draft)

    assert not errors, errors
    assert len([r for r in results if r[1] == "success"]) == 1
    assert [r[2] for r in results if r[1] == "error"] == [GenerationInProgressError.__name__] * 7
    assert (
        CreditTransaction.objects.filter(
            review=reviews[0], transaction_type=CreditTransaction.Type.CONSUMPTION
        ).count()
        == 1
    )
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 2
    assert_ledger_reconciles(balance)


@pytest.mark.pg_concurrency
@pytest.mark.django_db(transaction=True)
def test_settles_when_client_aborts_mid_generation():
    """D-03: a cancelled awaiting task (Daphne client disconnect) must not strand the credits.

    ``sync_to_async`` inside a ``ThreadSensitiveContext`` runs the orchestrator on a worker
    thread; cancelling the awaiting task does not stop that thread, so settlement still runs.
    """
    shop, user, reviews = _setup(allocation=10, comment=COST_2_COMMENT, n_reviews=1)
    review_pk = reviews[0].pk
    started = threading.Event()
    finished = threading.Event()

    def slow_seam(*, review: Review, tone: str, log_holder: Any = None) -> tuple[str, None]:
        started.set()
        time.sleep(0.5)
        return "draft", None

    def run() -> None:
        try:
            review = Review.objects.select_related("shop__organisation").get(pk=review_pk)
            generate_reply_with_credits(review=review, tone="professional", actor_id=user.pk)
        finally:
            connections.close_all()
            finished.set()

    async def drive() -> None:
        async with ThreadSensitiveContext():
            task = asyncio.ensure_future(sync_to_async(run)())
            deadline = time.monotonic() + 5
            while not started.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            assert started.is_set(), "the draft seam was never reached"
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    with patch(SEAM, side_effect=slow_seam):
        asyncio.run(drive())
        assert finished.wait(timeout=10), "the worker thread did not finish after the abort"

    tx = CreditTransaction.objects.get(
        review_id=review_pk, transaction_type=CreditTransaction.Type.CONSUMPTION
    )
    assert tx.status == Status.COMMITTED
    assert (
        AuditLog.objects.filter(action="shop.credits.consumed", entity_id=str(shop.pk)).count() == 1
    )
    balance = ShopCreditBalance.objects.get(shop=shop)
    assert balance.consumed_credits == 2
    assert_ledger_reconciles(balance)
