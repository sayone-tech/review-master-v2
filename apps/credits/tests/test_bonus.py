"""Bonus allocation service (CSUP-01)."""

from __future__ import annotations

import json

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.services.bonus import allocate_bonus
from apps.credits.services.periods import current_period
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.organisations.services.organisations import update_organisation
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

Type = CreditTransaction.Type


def test_allocate_bonus_increments_bonus_and_returns_snapshot_when_period_is_current():
    actor = UserFactory()
    org = OrganisationFactory(monthly_credit_allocation=100)
    shop = ShopFactory(organisation=org)

    result = allocate_bonus(
        shop_id=shop.pk, amount=50, reason=None, period=current_period(), actor_id=actor.pk
    )

    assert (result.allocated, result.bonus, result.consumed, result.remaining) == (100, 50, 0, 150)
    assert (result.period_year, result.period_month) == tuple(current_period())
    tx = CreditTransaction.objects.get(pk=result.transaction_id)
    assert tx.transaction_type == Type.BONUS_ALLOCATION
    assert tx.note is None


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_allocate_bonus_stores_null_note_when_reason_blank(reason):
    actor = UserFactory()
    shop = ShopFactory(organisation=OrganisationFactory(monthly_credit_allocation=5))

    result = allocate_bonus(
        shop_id=shop.pk, amount=3, reason=reason, period=current_period(), actor_id=actor.pk
    )

    assert CreditTransaction.objects.get(pk=result.transaction_id).note is None
    assert (
        AuditLog.objects.get(action="shop.credits.bonus_allocated").after_data["has_reason"]
        is False
    )


def test_allocate_bonus_stores_trimmed_reason_and_never_audits_reason_text():
    actor = UserFactory()
    shop = ShopFactory(organisation=OrganisationFactory(monthly_credit_allocation=5))

    result = allocate_bonus(
        shop_id=shop.pk,
        amount=3,
        reason="  Goodwill credit  ",
        period=current_period(),
        actor_id=actor.pk,
    )

    assert CreditTransaction.objects.get(pk=result.transaction_id).note == "Goodwill credit"
    audit = AuditLog.objects.get(action="shop.credits.bonus_allocated")
    assert audit.after_data["has_reason"] is True
    assert "Goodwill" not in json.dumps(audit.before_data)
    assert "Goodwill" not in json.dumps(audit.after_data)


def test_allocate_bonus_creates_zero_row_without_initial_when_organisation_at_zero():
    actor = UserFactory()
    shop = ShopFactory(organisation=OrganisationFactory(monthly_credit_allocation=0))

    result = allocate_bonus(
        shop_id=shop.pk, amount=9, reason=None, period=current_period(), actor_id=actor.pk
    )

    balance = ShopCreditBalance.objects.get(shop=shop)
    assert (balance.allocated_credits, balance.bonus_credits) == (0, 9)
    assert result.remaining == 9
    assert not CreditTransaction.objects.filter(
        shop=shop, transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
    ).exists()


def test_zero_to_n_edit_raises_bonus_created_row_when_bonus_came_first():
    actor = UserFactory()
    org = OrganisationFactory(monthly_credit_allocation=0)
    shop = ShopFactory(organisation=org)
    allocate_bonus(
        shop_id=shop.pk, amount=9, reason=None, period=current_period(), actor_id=actor.pk
    )

    update_organisation(organisation=org, actor=actor, monthly_credit_allocation=50)

    balance = ShopCreditBalance.objects.get(shop=shop)
    assert (balance.allocated_credits, balance.bonus_credits) == (50, 9)
    initial = CreditTransaction.objects.filter(
        shop=shop, transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
    )
    assert [t.credits_delta for t in initial] == [50]
    assert balance.allocated_credits + balance.bonus_credits - balance.consumed_credits == 59


def test_allocate_bonus_on_existing_balance_keeps_consumed():
    actor = UserFactory()
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org)
    balance = ShopCreditBalanceFactory(shop=shop, allocated_credits=10, consumed_credits=0)
    # Seed consumption through the ledger so the reconciliation invariant holds.
    CreditTransaction.objects.create(
        shop_credit_balance=balance,
        shop=shop,
        organisation=org,
        transaction_type=CreditTransaction.Type.CONSUMPTION,
        status=CreditTransaction.Status.COMMITTED,
        credits_delta=-7,
    )
    ShopCreditBalance.objects.filter(pk=balance.pk).update(consumed_credits=7)

    result = allocate_bonus(
        shop_id=shop.pk, amount=4, reason=None, period=current_period(), actor_id=actor.pk
    )

    balance.refresh_from_db()
    assert (balance.bonus_credits, balance.consumed_credits) == (4, 7)
    assert result.consumed == 7
    assert result.remaining == 7
    assert not CreditTransaction.objects.filter(
        shop=shop, transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
    ).exists()
    assert_ledger_reconciles(balance)


@pytest.mark.parametrize("amount", [0, 10001])
def test_allocate_bonus_rejects_out_of_range_amount_in_service(amount):
    actor = UserFactory()
    shop = ShopFactory()

    with pytest.raises(ValueError, match="amount"):
        allocate_bonus(
            shop_id=shop.pk,
            amount=amount,
            reason=None,
            period=current_period(),
            actor_id=actor.pk,
        )
