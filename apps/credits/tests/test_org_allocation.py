"""CRED-06 proof matrix for the org-edit path."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.common.models import AuditLog
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.selectors.balances import get_shop_credit_balance
from apps.credits.services.allocation import (
    ensure_balance,
    materialise_org_balances,
    raise_zero_balances,
)
from apps.credits.services.periods import current_period
from apps.credits.tests.factories import ShopCreditBalanceFactory
from apps.organisations.models import Organisation
from apps.organisations.services.organisations import update_organisation
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
NEXT_MONTH = datetime(2026, 12, 1, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fixed_now():
    with mock.patch("apps.credits.services.periods.utc_now", return_value=NOW) as patched:
        yield patched


def _credit_audits(org: Organisation):
    return AuditLog.objects.filter(organisation=org, action="organisation.credits.set")


def _balances(org: Organisation):
    period = current_period()
    return ShopCreditBalance.objects.filter(
        organisation=org, period_year=period.year, period_month=period.month
    )


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
    assert rows.count() == 2
    assert not rows.filter(shop=fresh_b).exists()
    assert {r.allocated_credits for r in rows} == {100}
    untouched = rows.get(shop=existing)
    assert untouched.consumed_credits == 7
    for shop in (existing, fresh_a):
        assert get_shop_credit_balance(shop_id=shop.pk).allocated == 100
    initials = CreditTransaction.objects.filter(
        transaction_type=CreditTransaction.Type.INITIAL_ALLOCATION
    )
    assert initials.count() == 2
    assert not CreditTransaction.objects.filter(shop=fresh_b).exists()
    assert all(
        t.credits_delta == 100 and t.actor_id is None and t.status == "COMMITTED" for t in initials
    )
    assert get_shop_credit_balance(shop_id=fresh_a.pk).remaining == 100
    assert AuditLog.objects.filter(action="shop.credits.allocated").count() == 2
    assert not AuditLog.objects.filter(
        action="shop.credits.allocated", entity_id=str(fresh_b.pk)
    ).exists()
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
    assert audit.after_data["shops_touched"] == 1


def test_update_organisation_is_immediate_and_creates_no_rows_when_raising_zero_to_n():
    org = OrganisationFactory(monthly_credit_allocation=0)
    shops = ShopFactory.create_batch(3, organisation=org)

    update_organisation(organisation=org, monthly_credit_allocation=50)

    audit = _credit_audits(org).get()
    assert audit.after_data["effective"] == "immediate"
    assert audit.after_data["shops_touched"] == 0
    assert ShopCreditBalance.objects.count() == 0
    for shop in shops:
        assert get_shop_credit_balance(shop_id=shop.pk).remaining == 50


def test_update_organisation_raises_zero_rows_to_n_with_one_initial_when_bonus_created_them():
    org = OrganisationFactory(monthly_credit_allocation=0)
    bonus_shop = ShopFactory(organisation=org)
    plain_shop = ShopFactory(organisation=org)
    row = ShopCreditBalanceFactory(shop=bonus_shop, allocated_credits=0, bonus_credits=20)

    update_organisation(organisation=org, monthly_credit_allocation=50)

    row.refresh_from_db()
    assert (row.allocated_credits, row.bonus_credits, row.consumed_credits) == (50, 20, 0)
    initial = CreditTransaction.objects.get(transaction_type="INITIAL_ALLOCATION")
    assert (initial.credits_delta, initial.status, initial.actor_id) == (50, "COMMITTED", None)
    assert initial.shop_credit_balance_id == row.pk
    allocated = AuditLog.objects.get(action="shop.credits.allocated")
    assert allocated.after_data["allocated_credits"] == 50
    assert get_shop_credit_balance(shop_id=bonus_shop.pk).remaining == 70
    assert get_shop_credit_balance(shop_id=plain_shop.pk).remaining == 50
    assert not ShopCreditBalance.objects.filter(shop=plain_shop).exists()
    assert _credit_audits(org).get().after_data["shops_touched"] == 1


def test_update_organisation_defers_second_change_when_shops_held_allocation_earlier_this_month(
    fixed_now,
):
    org = OrganisationFactory(monthly_credit_allocation=100)
    first, second = ShopFactory.create_batch(2, organisation=org)

    update_organisation(organisation=org, monthly_credit_allocation=0)
    third = ShopFactory(organisation=org)
    update_organisation(organisation=org, monthly_credit_allocation=50)

    org.refresh_from_db()
    assert org.monthly_credit_allocation == 50
    last = _credit_audits(org).order_by("-pk").first()
    assert last is not None
    assert last.after_data["effective"] == "next_month"
    assert _balances(org).get(shop=first).allocated_credits == 100
    assert _balances(org).get(shop=second).allocated_credits == 100
    third_row = _balances(org).get(shop=third)
    assert third_row.allocated_credits == 0
    assert not CreditTransaction.objects.filter(shop_credit_balance=third_row).exists()
    assert not AuditLog.objects.filter(
        action="shop.credits.allocated", entity_id=str(third.pk)
    ).exists()

    fixed_now.return_value = NEXT_MONTH
    for shop in (first, second, third):
        assert get_shop_credit_balance(shop_id=shop.pk).allocated == 50


def test_update_organisation_keeps_shops_at_n_this_month_when_set_to_zero():
    org = OrganisationFactory(monthly_credit_allocation=80)
    shops = ShopFactory.create_batch(2, organisation=org)

    update_organisation(organisation=org, monthly_credit_allocation=0)

    org.refresh_from_db()
    assert org.monthly_credit_allocation == 0
    assert {r.allocated_credits for r in _balances(org)} == {80}
    assert _credit_audits(org).get().after_data["effective"] == "next_month"
    with mock.patch("apps.credits.services.periods.utc_now", return_value=NEXT_MONTH):
        for shop in shops:
            view = get_shop_credit_balance(shop_id=shop.pk)
            assert view.allocated == 0
            assert view.is_enabled is False


def test_shops_get_new_allocation_next_month_after_n_to_m():
    org = OrganisationFactory(monthly_credit_allocation=100)
    shop = ShopFactory(organisation=org)

    update_organisation(organisation=org, monthly_credit_allocation=40)

    assert get_shop_credit_balance(shop_id=shop.pk).allocated == 100
    with mock.patch("apps.credits.services.periods.utc_now", return_value=NEXT_MONTH):
        assert get_shop_credit_balance(shop_id=shop.pk).allocated == 40
        balance, created = ensure_balance(shop_id=shop.pk)
    assert created is True
    assert (balance.period_year, balance.period_month, balance.allocated_credits) == (2026, 12, 40)
    december = CreditTransaction.objects.get(shop_credit_balance=balance)
    assert (december.transaction_type, december.credits_delta) == ("INITIAL_ALLOCATION", 40)


def test_update_organisation_writes_nothing_when_value_unchanged_or_absent():
    org = OrganisationFactory(monthly_credit_allocation=100)
    ShopFactory.create_batch(2, organisation=org)

    update_organisation(organisation=org, monthly_credit_allocation=100)
    update_organisation(organisation=org, number_of_stores=11)
    update_organisation(organisation=org, name="Renamed Org")

    assert _credit_audits(org).count() == 0
    assert ShopCreditBalance.objects.count() == 0

    update_organisation(organisation=org, monthly_credit_allocation=50)
    counts = (
        ShopCreditBalance.objects.count(),
        CreditTransaction.objects.count(),
        AuditLog.objects.count(),
    )
    update_organisation(organisation=org, monthly_credit_allocation=50)
    assert (
        ShopCreditBalance.objects.count(),
        CreditTransaction.objects.count(),
        AuditLog.objects.count(),
    ) == counts


def test_materialise_org_balances_is_idempotent_when_called_twice():
    org = OrganisationFactory(monthly_credit_allocation=30)
    ShopFactory.create_batch(3, organisation=org)
    period = current_period()

    first = materialise_org_balances(organisation_id=org.pk, allocation=30, period=period)
    counts = (
        ShopCreditBalance.objects.count(),
        CreditTransaction.objects.count(),
        AuditLog.objects.count(),
    )
    second = materialise_org_balances(organisation_id=org.pk, allocation=30, period=period)

    assert (first, second) == (3, 0)
    assert (
        ShopCreditBalance.objects.count(),
        CreditTransaction.objects.count(),
        AuditLog.objects.count(),
    ) == counts


def test_update_organisation_reads_old_value_from_locked_row_when_instance_is_stale():
    org = OrganisationFactory(monthly_credit_allocation=0)
    ShopFactory(organisation=org)
    stale = Organisation.objects.get(pk=org.pk)
    Organisation.objects.filter(pk=org.pk).update(monthly_credit_allocation=100)

    update_organisation(organisation=stale, monthly_credit_allocation=50)

    audit = _credit_audits(org).get()
    assert audit.before_data == {"monthly_credit_allocation": 100}
    assert audit.after_data["effective"] == "next_month"
    assert {r.allocated_credits for r in _balances(org)} == {100}
    org.refresh_from_db()
    assert org.monthly_credit_allocation == 50


def test_update_organisation_rolls_back_everything_when_audit_write_fails():
    org = OrganisationFactory(monthly_credit_allocation=100)
    ShopFactory.create_batch(2, organisation=org)
    audits_before = AuditLog.objects.count()

    failing_audit = mock.MagicMock()
    failing_audit.objects.create.side_effect = RuntimeError("audit down")
    with (
        mock.patch("apps.organisations.services.organisations.AuditLog", failing_audit),
        pytest.raises(RuntimeError),
    ):
        update_organisation(organisation=org, monthly_credit_allocation=50)

    org.refresh_from_db()
    assert org.monthly_credit_allocation == 100
    assert ShopCreditBalance.objects.count() == 0
    assert CreditTransaction.objects.count() == 0
    assert AuditLog.objects.count() == audits_before


def _normalised(org: Organisation, shop_names: dict[int, str]):
    balances = sorted(
        (shop_names[r.shop_id], r.allocated_credits, r.bonus_credits, r.consumed_credits)
        for r in ShopCreditBalance.objects.filter(organisation=org)
    )
    ledger = sorted(
        (
            shop_names[t.shop_id],
            t.transaction_type,
            t.status,
            t.credits_delta,
            t.actor_id,
            t.note,
        )
        for t in CreditTransaction.objects.filter(organisation=org)
    )
    audit = sorted(
        (
            shop_names[int(a.entity_id)],
            a.action,
            a.entity_type,
            a.actor_id,
            repr(a.before_data),
            repr(a.after_data),
        )
        for a in AuditLog.objects.filter(organisation=org)
    )
    return balances, ledger, audit


@pytest.mark.parametrize("allocation", [30, 0])
def test_materialise_matches_looping_ensure_balance(allocation):
    org_a = OrganisationFactory(monthly_credit_allocation=allocation)
    org_b = OrganisationFactory(monthly_credit_allocation=allocation)
    names: dict[int, str] = {}
    shops_b = []
    for idx in range(3):
        shop_a = ShopFactory(organisation=org_a, name=f"S{idx}", is_active=idx != 2)
        shop_b = ShopFactory(organisation=org_b, name=f"S{idx}", is_active=idx != 2)
        names[shop_a.pk] = names[shop_b.pk] = f"S{idx}"
        shops_b.append(shop_b)

    materialise_org_balances(
        organisation_id=org_a.pk, allocation=allocation, period=current_period()
    )
    for shop in shops_b:
        if shop.is_active:
            ensure_balance(shop_id=shop.pk)

    a, b = _normalised(org_a, names), _normalised(org_b, names)
    assert a == b
    assert len(a[0]) == 2
    if allocation == 0:
        assert a[1] == []
        assert a[2] == []
    else:
        assert len(a[1]) == 2
        assert len(a[2]) == 2


def test_raise_zero_balances_writes_same_ledger_and_audit_as_ensure_balance():
    raised_org = OrganisationFactory(monthly_credit_allocation=0)
    fresh_org = OrganisationFactory(monthly_credit_allocation=50)
    raised_shop = ShopFactory(organisation=raised_org, name="X")
    fresh_shop = ShopFactory(organisation=fresh_org, name="X")
    ShopCreditBalanceFactory(shop=raised_shop, allocated_credits=0)

    count = raise_zero_balances(
        organisation_id=raised_org.pk, allocation=50, period=current_period()
    )
    ensure_balance(shop_id=fresh_shop.pk)

    assert count == 1
    names_a = {raised_shop.pk: "X"}
    names_b = {fresh_shop.pk: "X"}
    assert _normalised(raised_org, names_a) == _normalised(fresh_org, names_b)


def _count_queries(fn) -> int:
    with CaptureQueriesContext(connection) as ctx:
        fn()
    return len(ctx.captured_queries)


def test_materialise_query_count_is_constant_when_shop_count_grows():
    region = RegionFactory()
    small = OrganisationFactory(monthly_credit_allocation=30)
    large = OrganisationFactory(monthly_credit_allocation=30)
    ShopFactory.create_batch(5, organisation=small, region=region)
    ShopFactory.create_batch(50, organisation=large, region=region)
    period = current_period()

    small_q = _count_queries(
        lambda: materialise_org_balances(organisation_id=small.pk, allocation=30, period=period)
    )
    large_q = _count_queries(
        lambda: materialise_org_balances(organisation_id=large.pk, allocation=30, period=period)
    )

    assert small_q == large_q
    assert _balances(large).count() == 50


def test_raise_zero_balances_query_count_is_constant_when_zero_rows_grow():
    region = RegionFactory()
    small = OrganisationFactory(monthly_credit_allocation=0)
    large = OrganisationFactory(monthly_credit_allocation=0)
    for org, n in ((small, 2), (large, 10)):
        for shop in ShopFactory.create_batch(n, organisation=org, region=region):
            ShopCreditBalanceFactory(shop=shop, allocated_credits=0)
    period = current_period()

    small_q = _count_queries(
        lambda: raise_zero_balances(organisation_id=small.pk, allocation=5, period=period)
    )
    large_q = _count_queries(
        lambda: raise_zero_balances(organisation_id=large.pk, allocation=5, period=period)
    )

    assert small_q == large_q


def test_raise_zero_balances_rejects_non_positive_allocation():
    org = OrganisationFactory()
    with pytest.raises(ValueError, match="positive"):
        raise_zero_balances(organisation_id=org.pk, allocation=0, period=current_period())


def test_materialise_skips_inactive_shops_when_org_has_active_and_inactive():
    org = OrganisationFactory(monthly_credit_allocation=30)
    active = ShopFactory.create_batch(2, organisation=org)
    inactive = ShopFactory(organisation=org, is_active=False)

    created = materialise_org_balances(
        organisation_id=org.pk, allocation=30, period=current_period()
    )

    assert created == 2
    assert set(_balances(org).values_list("shop_id", flat=True)) == {s.pk for s in active}
    assert CreditTransaction.objects.filter(shop=inactive).count() == 0
    assert CreditTransaction.objects.count() == 2
    assert not AuditLog.objects.filter(
        action="shop.credits.allocated", entity_id=str(inactive.pk)
    ).exists()
    assert AuditLog.objects.filter(action="shop.credits.allocated").count() == 2


def test_raise_zero_balances_skips_inactive_shop_rows():
    org = OrganisationFactory(monthly_credit_allocation=0)
    active = ShopFactory(organisation=org)
    inactive = ShopFactory(organisation=org, is_active=False)
    active_row = ShopCreditBalanceFactory(shop=active, allocated_credits=0)
    inactive_row = ShopCreditBalanceFactory(shop=inactive, allocated_credits=0)

    raised = raise_zero_balances(organisation_id=org.pk, allocation=50, period=current_period())

    assert raised == 1
    active_row.refresh_from_db()
    inactive_row.refresh_from_db()
    assert active_row.allocated_credits == 50
    assert inactive_row.allocated_credits == 0
    assert CreditTransaction.objects.filter(shop_credit_balance=inactive_row).count() == 0
    assert not AuditLog.objects.filter(
        action="shop.credits.allocated", entity_id=str(inactive.pk)
    ).exists()
    assert CreditTransaction.objects.filter(shop_credit_balance=active_row).count() == 1


def test_update_organisation_zero_to_n_does_not_raise_inactive_shop_row():
    org = OrganisationFactory(monthly_credit_allocation=0)
    active = ShopFactory(organisation=org)
    inactive = ShopFactory(organisation=org, is_active=False)
    active_row = ShopCreditBalanceFactory(shop=active, allocated_credits=0, bonus_credits=5)
    inactive_row = ShopCreditBalanceFactory(shop=inactive, allocated_credits=0)

    update_organisation(organisation=org, monthly_credit_allocation=10)

    active_row.refresh_from_db()
    inactive_row.refresh_from_db()
    assert active_row.allocated_credits == 10
    assert inactive_row.allocated_credits == 0
    assert _credit_audits(org).get().after_data["shops_touched"] == 1


def test_update_organisation_n_to_m_creates_no_row_for_inactive_shop():
    org = OrganisationFactory(monthly_credit_allocation=10)
    active = ShopFactory(organisation=org)
    inactive = ShopFactory(organisation=org, is_active=False)

    update_organisation(organisation=org, monthly_credit_allocation=20)

    assert _balances(org).get(shop=active).allocated_credits == 10
    assert not _balances(org).filter(shop=inactive).exists()
    assert not CreditTransaction.objects.filter(shop=inactive).exists()


def test_reactivated_shop_gets_full_allocation_on_first_use_via_ensure_balance():
    org = OrganisationFactory(monthly_credit_allocation=10)
    shop = ShopFactory(organisation=org, is_active=False)
    update_organisation(organisation=org, monthly_credit_allocation=20)
    assert not _balances(org).filter(shop=shop).exists()

    shop.is_active = True
    shop.save(update_fields=["is_active"])
    balance, created = ensure_balance(shop_id=shop.pk)

    assert created is True
    assert balance.allocated_credits == 20
    ledger = CreditTransaction.objects.get(shop_credit_balance=balance)
    assert (ledger.transaction_type, ledger.credits_delta) == ("INITIAL_ALLOCATION", 20)
