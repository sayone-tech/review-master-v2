"""Celery wiring + end-to-end tests for the credits tasks (Phase 31)."""

from __future__ import annotations

import dataclasses

import pytest
from celery import current_app
from django_celery_beat.models import PeriodicTask

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction
from apps.credits.services.lapse import LapseSummary
from apps.credits.services.periods import Period, current_period
from apps.credits.tasks import lapse_expired_credit_balances_task
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

LAPSE_TASK = "apps.credits.tasks.lapse_expired_credit_balances_task"


def _previous_period() -> Period:
    p = current_period()
    return Period(p.year - 1, 12) if p.month == 1 else Period(p.year, p.month - 1)


def test_lapse_periodic_task_is_seeded_daily_at_0005_utc_on_default_queue():
    pt = PeriodicTask.objects.get(name="credits_lapse_expired_balances")

    assert pt.task == LAPSE_TASK
    assert pt.queue == "default"
    assert pt.enabled is True
    assert pt.interval is None
    assert pt.crontab.minute == "5"
    assert pt.crontab.hour == "0"
    assert pt.crontab.day_of_month == "*"
    assert pt.crontab.day_of_week == "*"
    assert str(pt.crontab.timezone) == "UTC"


def test_lapse_task_is_registered_and_routed_to_default_queue():
    path = PeriodicTask.objects.get(name="credits_lapse_expired_balances").task

    assert path in current_app.tasks
    assert current_app.conf.task_routes[path]["queue"] == "default"


def test_lapse_task_lapses_previous_month_balance_end_to_end():
    shop = ShopFactory()
    prev = _previous_period()
    old = ShopCreditBalanceFactory(
        shop=shop,
        period_year=prev.year,
        period_month=prev.month,
        allocated_credits=10,
        bonus_credits=3,
        consumed_credits=4,
    )
    current = ShopCreditBalanceFactory(shop=shop, allocated_credits=10)

    result = lapse_expired_credit_balances_task.delay().get()

    assert result == dataclasses.asdict(LapseSummary(lapsed=1, credits_lapsed=9))
    rows = list(
        CreditTransaction.objects.filter(shop_credit_balance=old, transaction_type="LAPSED")
    )
    assert len(rows) == 1
    assert rows[0].credits_delta == -9
    assert rows[0].status == CreditTransaction.Status.COMMITTED
    assert rows[0].actor_id is None
    audit = list(AuditLog.objects.filter(action="shop.credits.lapsed"))
    assert len(audit) == 1
    assert audit[0].organisation_id == old.organisation_id
    assert audit[0].entity_type == "shop"
    assert audit[0].entity_id == str(shop.pk)
    assert audit[0].actor_id is None
    assert audit[0].after_data == {
        "allocated": 10,
        "bonus": 3,
        "consumed": 4,
        "lapsed": 9,
        "period_year": prev.year,
        "period_month": prev.month,
        "transaction_id": rows[0].pk,
    }
    old.refresh_from_db()
    assert old.lapsed_at is not None
    assert (old.allocated_credits, old.bonus_credits, old.consumed_credits) == (10, 3, 4)
    current.refresh_from_db()
    assert current.lapsed_at is None
    assert not CreditTransaction.objects.filter(shop_credit_balance=current).exists()
