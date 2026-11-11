"""CRED-06 proof matrix for the org-edit path."""

from __future__ import annotations

import pytest

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.balances import get_shop_credit_balance
from apps.credits.services.allocation import ensure_balance
from apps.credits.services.periods import current_period
from apps.organisations.services.organisations import update_organisation
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def test_update_organisation_materialises_rows_at_old_value_when_allocation_changes_n_to_m():
    org = OrganisationFactory(monthly_credit_allocation=100)
    existing = ShopFactory(organisation=org)
    fresh_a = ShopFactory(organisation=org)
    fresh_b = ShopFactory(organisation=org, is_active=False)
    balance, _ = ensure_balance(shop_id=existing.pk)
    ShopCreditBalance.objects.filter(pk=balance.pk).update(consumed_credits=7)

    update_organisation(organisation=org, monthly_credit_allocation=50)

    org.refresh_from_db()
    assert org.monthly_credit_allocation == 50
    period = current_period()
    rows = ShopCreditBalance.objects.filter(
        organisation=org, period_year=period.year, period_month=period.month
    )
    assert rows.count() == 3
    assert {r.allocated_credits for r in rows} == {100}
    untouched = rows.get(shop=existing)
    assert untouched.consumed_credits == 7
    for shop in (existing, fresh_a, fresh_b):
        assert get_shop_credit_balance(shop_id=shop.pk).allocated == 100
    initials = CreditTransaction.objects.filter(
        transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
    )
    assert initials.count() == 3
    assert all(
        t.credits_delta == 100 and t.actor_id is None and t.status == "COMMITTED" for t in initials
    )
    assert get_shop_credit_balance(shop_id=fresh_a.pk).remaining == 100
    assert AuditLog.objects.filter(action="shop.credits.allocated").count() == 3
    audit = AuditLog.objects.get(action="organisation.credits.set")
    assert audit.entity_type == "organisation"
    assert audit.entity_id == str(org.pk)
    assert audit.actor is None
    assert audit.before_data == {"monthly_credit_allocation": 100}
    assert set(audit.after_data) == {
        "monthly_credit_allocation",
        "effective",
        "shops_touched",
        "period_year",
        "period_month",
    }
    assert audit.after_data["effective"] == "next_month"
    assert audit.after_data["shops_touched"] == 2
