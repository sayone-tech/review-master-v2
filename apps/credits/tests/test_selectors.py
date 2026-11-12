from __future__ import annotations

import dataclasses
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.balances import (
    CreditBalanceView,
    annotate_credit_state,
    get_shop_credit_balance,
)
from apps.credits.services.periods import Period, current_period
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.models import Shop
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

PERIOD = Period(2026, 11)


def _shop(allocation: int = 7, **kwargs):
    org = OrganisationFactory(monthly_credit_allocation=allocation)
    return ShopFactory(organisation=org, **kwargs)


def _row(shop, period: Period = PERIOD, **kwargs):
    return ShopCreditBalanceFactory(
        shop=shop,
        organisation=shop.organisation,
        period_year=period.year,
        period_month=period.month,
        **kwargs,
    )


def test_reports_live_org_allocation_when_no_current_row():
    shop = _shop(7)
    view = get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    assert isinstance(view, CreditBalanceView)
    assert (view.allocated, view.remaining) == (7, 7)
    assert (view.bonus, view.consumed) == (0, 0)
    assert view.is_materialized is False
    assert view.is_enabled is True
    assert (view.shop_id, view.year, view.month) == (shop.pk, 2026, 11)


def test_reports_disabled_when_org_allocation_zero_and_no_row():
    shop = _shop(0)
    view = get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    assert (view.allocated, view.remaining) == (0, 0)
    assert view.is_enabled is False


def test_ignores_previous_month_row_when_reading_current_period():
    shop = _shop(7)
    _row(shop, Period(2026, 10), allocated_credits=7, consumed_credits=4)
    view = get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    assert (view.allocated, view.remaining, view.consumed) == (7, 7, 0)
    assert view.is_materialized is False


def test_reports_row_values_when_current_row_exists():
    shop = _shop(7)
    _row(shop, allocated_credits=5, bonus_credits=2, consumed_credits=4)
    view = get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    assert (view.allocated, view.bonus, view.consumed) == (5, 2, 4)
    assert view.remaining == 3
    assert view.is_enabled is True
    assert view.is_materialized is True


def test_materialised_row_keeps_own_allocation_when_org_allocation_changes():
    shop = _shop(7)
    _row(shop, allocated_credits=5)
    shop.organisation.monthly_credit_allocation = 9
    shop.organisation.save()
    assert get_shop_credit_balance(shop_id=shop.pk, period=PERIOD).allocated == 5


def test_unmaterialised_shop_reflects_org_allocation_change_immediately():
    shop = _shop(7)
    assert get_shop_credit_balance(shop_id=shop.pk, period=PERIOD).allocated == 7
    shop.organisation.monthly_credit_allocation = 9
    shop.organisation.save()
    assert get_shop_credit_balance(shop_id=shop.pk, period=PERIOD).allocated == 9


def test_computes_inactive_shop_like_active_shop():
    active = _shop(7, is_active=True)
    inactive = _shop(7, is_active=False)
    a = get_shop_credit_balance(shop_id=active.pk, period=PERIOD)
    i = get_shop_credit_balance(shop_id=inactive.pk, period=PERIOD)
    assert (a.allocated, a.remaining, a.is_enabled) == (i.allocated, i.remaining, i.is_enabled)
    _row(inactive, allocated_credits=3, consumed_credits=1)
    assert get_shop_credit_balance(shop_id=inactive.pk, period=PERIOD).remaining == 2


def test_renews_on_is_first_day_of_next_utc_month_and_december_rolls_over():
    shop = _shop(7)
    assert get_shop_credit_balance(shop_id=shop.pk, period=PERIOD).renews_on == date(2026, 12, 1)
    assert get_shop_credit_balance(shop_id=shop.pk, period=Period(2026, 12)).renews_on == date(
        2027, 1, 1
    )


def test_view_is_frozen():
    shop = _shop(7)
    view = get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.allocated = 99  # type: ignore[misc]


def test_defaults_to_current_period_when_period_omitted():
    shop = _shop(7)
    cur = current_period()
    view = get_shop_credit_balance(shop_id=shop.pk)
    assert (view.year, view.month) == (cur.year, cur.month)


def test_uses_at_most_two_queries_when_no_row(assert_query_ceiling):
    shop = _shop(7)
    with CaptureQueriesContext(connection) as ctx:
        get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    assert_query_ceiling(ctx, 2)


def test_uses_exactly_one_query_when_row_exists():
    shop = _shop(7)
    _row(shop, allocated_credits=5)
    with CaptureQueriesContext(connection) as ctx:
        get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    assert len(ctx.captured_queries) == 1


def test_raises_shop_does_not_exist_when_shop_id_unknown():
    with pytest.raises(Shop.DoesNotExist):
        get_shop_credit_balance(shop_id=999_999, period=PERIOD)


def _is_write(sql: str) -> bool:
    return sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))


def test_get_shop_credit_balance_never_writes():
    shop = _shop(7)
    with CaptureQueriesContext(connection) as ctx:
        get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
        get_shop_credit_balance(shop_id=shop.pk, period=PERIOD)
    assert ShopCreditBalance.objects.count() == 0
    assert CreditTransaction.objects.count() == 0
    assert not [q["sql"] for q in ctx.captured_queries if _is_write(q["sql"])]


def test_annotate_credit_state_never_writes():
    _shop(7)
    with CaptureQueriesContext(connection) as ctx:
        list(annotate_credit_state(queryset=Shop.objects.all(), period=PERIOD))
    assert ShopCreditBalance.objects.count() == 0
    assert CreditTransaction.objects.count() == 0
    assert not [q["sql"] for q in ctx.captured_queries if _is_write(q["sql"])]


def _three_shops():
    org = OrganisationFactory(monthly_credit_allocation=7)
    materialised = ShopFactory(organisation=org, name="A materialised")
    other_month = ShopFactory(organisation=org, name="B other month")
    ShopFactory(organisation=org, name="C no row")
    _row(materialised, allocated_credits=5, bonus_credits=2, consumed_credits=4)
    _row(other_month, Period(2026, 10), allocated_credits=7, consumed_credits=6)
    return org


def test_annotates_remaining_and_materialized_when_mixed_shops():
    org = _three_shops()
    qs = annotate_credit_state(
        queryset=Shop.objects.filter(organisation=org).order_by("name"), period=PERIOD
    )
    assert [(s.credit_remaining, s.credit_materialized) for s in qs] == [
        (3, True),
        (7, False),
        (7, False),
    ]
    first = qs[0]
    assert (first.credit_allocated, first.credit_bonus, first.credit_consumed) == (5, 2, 4)


def test_annotation_is_filterable_when_remaining_threshold_applied():
    org = _three_shops()
    qs = annotate_credit_state(queryset=Shop.objects.filter(organisation=org), period=PERIOD)
    assert qs.filter(credit_remaining__lte=3).count() == 1


@pytest.mark.parametrize("n_shops", [2, 20])
def test_annotate_uses_one_query_when_listing_shops(n_shops, assert_query_ceiling):
    org = OrganisationFactory(monthly_credit_allocation=7)
    for i in range(n_shops):
        shop = ShopFactory(organisation=org)
        if i % 2:
            _row(shop, allocated_credits=5)
    with CaptureQueriesContext(connection) as ctx:
        rows = list(
            annotate_credit_state(queryset=Shop.objects.filter(organisation=org), period=PERIOD)
        )
    assert len(rows) == n_shops
    assert_query_ceiling(ctx, 1)
    assert len(ctx.captured_queries) == 1


def test_annotate_returns_one_row_per_shop_and_preserves_order_when_multi_month_balances():
    org = OrganisationFactory(monthly_credit_allocation=7)
    s1 = ShopFactory(organisation=org, name="A")
    s2 = ShopFactory(organisation=org, name="B")
    for period in (Period(2026, 9), Period(2026, 10), PERIOD):
        _row(s1, period, allocated_credits=5)
    rows = list(
        annotate_credit_state(
            queryset=Shop.objects.filter(organisation=org).order_by("-name"), period=PERIOD
        )
    )
    assert [s.pk for s in rows] == [s2.pk, s1.pk]
    assert [s.credit_materialized for s in rows] == [False, True]


def test_annotate_falls_back_to_each_shops_own_org_allocation_when_two_orgs():
    s_a = _shop(7)
    s_b = _shop(11)
    rows = {
        s.pk: s.credit_remaining
        for s in annotate_credit_state(
            queryset=Shop.objects.filter(pk__in=[s_a.pk, s_b.pk]), period=PERIOD
        )
    }
    assert rows == {s_a.pk: 7, s_b.pk: 11}


def test_annotate_computes_inactive_shop_like_active_shop():
    org = OrganisationFactory(monthly_credit_allocation=7)
    ShopFactory(organisation=org, is_active=False)
    ShopFactory(organisation=org, is_active=True)
    rows = list(
        annotate_credit_state(queryset=Shop.objects.filter(organisation=org), period=PERIOD)
    )
    assert [s.credit_remaining for s in rows] == [7, 7]


def test_annotate_defaults_to_current_period_when_period_omitted():
    shop = _shop(7)
    ShopCreditBalanceFactory(shop=shop, organisation=shop.organisation, allocated_credits=4)
    (row,) = annotate_credit_state(queryset=Shop.objects.filter(pk=shop.pk))
    assert (row.credit_remaining, row.credit_materialized) == (4, True)
