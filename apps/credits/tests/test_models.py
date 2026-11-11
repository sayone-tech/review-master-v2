"""DB-level invariants for ShopCreditBalance and CreditTransaction (CRED-02, CRED-03, D-02, D-04, D-07).

CHECK violations also assert the constraint name (both engines name CHECKs); unique
violations assert only IntegrityError because SQLite omits the constraint name.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.tests.factories import CreditTransactionFactory, ShopCreditBalanceFactory
from apps.credits.tests.helpers import assert_ledger_reconciles
from apps.integrations.openai.tests.factories import AiUsageLogFactory
from apps.reviews.tests.factories import ReviewFactory

pytestmark = pytest.mark.django_db

Type = CreditTransaction.Type
Status = CreditTransaction.Status


# --- ShopCreditBalance (CRED-02) -----------------------------------------------


def test_duplicate_shop_period_is_rejected_when_balance_exists():
    existing = ShopCreditBalanceFactory(period_year=2026, period_month=11)
    with pytest.raises(IntegrityError), transaction.atomic():
        ShopCreditBalanceFactory(shop=existing.shop, period_year=2026, period_month=11)


def test_adjacent_month_is_allowed_when_same_shop_has_a_balance():
    existing = ShopCreditBalanceFactory(period_year=2026, period_month=11)
    other = ShopCreditBalanceFactory(shop=existing.shop, period_year=2026, period_month=12)
    assert other.pk != existing.pk


def test_consumed_equal_to_total_is_accepted_when_allocated_plus_bonus():
    balance = ShopCreditBalanceFactory(allocated_credits=7, bonus_credits=3, consumed_credits=10)
    assert balance.pk is not None


def test_overspend_is_rejected_when_consumed_exceeds_allocated_plus_bonus():
    with pytest.raises(IntegrityError, match="credit_balance_no_overspend"), transaction.atomic():
        ShopCreditBalanceFactory(allocated_credits=7, bonus_credits=3, consumed_credits=11)


@pytest.mark.parametrize(
    ("values", "constraint_pattern"),
    [
        ({"consumed_credits": -1}, "credit_balance_nonneg"),
        # allocated=-1 also violates no_overspend (0 <= -1 is false); PostgreSQL does not
        # guarantee which CHECK it reports first, so either name proves the row is rejected.
        (
            {"allocated_credits": -1, "consumed_credits": 0},
            "credit_balance_(nonneg|no_overspend)",
        ),
        ({"bonus_credits": -1}, "credit_balance_nonneg"),
    ],
)
def test_negative_values_are_rejected_when_credits_go_below_zero(values, constraint_pattern):
    with pytest.raises(IntegrityError, match=constraint_pattern), transaction.atomic():
        ShopCreditBalanceFactory(**values)


@pytest.mark.parametrize("month", [0, 13])
def test_month_is_rejected_when_outside_1_to_12(month):
    with pytest.raises(IntegrityError, match="credit_balance_month_range"), transaction.atomic():
        ShopCreditBalanceFactory(period_month=month)


@pytest.mark.parametrize("month", [1, 12])
def test_month_is_accepted_when_on_the_boundary(month):
    assert ShopCreditBalanceFactory(period_month=month).pk is not None


# --- CreditTransaction constraints (D-07, A3b) ---------------------------------


def _tx(balance, **kwargs):
    return CreditTransactionFactory(shop_credit_balance=balance, **kwargs)


def test_second_initial_is_rejected_when_balance_already_has_one():
    balance = ShopCreditBalanceFactory()
    _tx(balance, transaction_type=Type.INITIAL_ALLOCATION, status=Status.COMMITTED, credits_delta=5)
    with pytest.raises(IntegrityError), transaction.atomic():
        _tx(
            balance,
            transaction_type=Type.INITIAL_ALLOCATION,
            status=Status.COMMITTED,
            credits_delta=5,
        )


def test_initial_rows_coexist_when_balances_are_adjacent_months_of_one_shop():
    first = ShopCreditBalanceFactory(period_year=2026, period_month=11)
    second = ShopCreditBalanceFactory(shop=first.shop, period_year=2026, period_month=12)
    for balance in (first, second):
        _tx(
            balance,
            transaction_type=Type.INITIAL_ALLOCATION,
            status=Status.COMMITTED,
            credits_delta=5,
        )
    assert CreditTransaction.objects.filter(shop=first.shop).count() == 2


def test_second_lapsed_is_rejected_when_balance_already_has_one():
    balance = ShopCreditBalanceFactory()
    _tx(balance, transaction_type=Type.LAPSED, status=Status.COMMITTED, credits_delta=-3)
    with pytest.raises(IntegrityError), transaction.atomic():
        _tx(balance, transaction_type=Type.LAPSED, status=Status.COMMITTED, credits_delta=-3)


def test_many_consumption_rows_are_accepted_when_on_one_balance():
    balance = ShopCreditBalanceFactory()
    for _ in range(3):
        _tx(balance)
    assert CreditTransaction.objects.filter(shop_credit_balance=balance).count() == 3


@pytest.mark.parametrize(
    ("transaction_type", "delta"),
    [
        (Type.INITIAL_ALLOCATION, 0),
        (Type.INITIAL_ALLOCATION, -1),
        (Type.CONSUMPTION, 1),
        (Type.LAPSED, 1),
    ],
)
def test_delta_sign_is_rejected_when_wrong_for_type(transaction_type, delta):
    with pytest.raises(IntegrityError, match="credit_tx_delta_sign"), transaction.atomic():
        CreditTransactionFactory(
            transaction_type=transaction_type, status=Status.COMMITTED, credits_delta=delta
        )


def test_non_consumption_is_rejected_when_status_is_reserved():
    with (
        pytest.raises(IntegrityError, match="credit_tx_only_consumption_reserved"),
        transaction.atomic(),
    ):
        CreditTransactionFactory(
            transaction_type=Type.BONUS_ALLOCATION, status=Status.RESERVED, credits_delta=5
        )


def test_consumption_is_accepted_when_status_is_reserved():
    assert CreditTransactionFactory(status=Status.RESERVED).pk is not None


def test_reserved_partial_index_covers_status_and_created_at_when_declared():
    index = next(i for i in CreditTransaction._meta.indexes if i.name == "credit_tx_reserved_idx")
    assert list(index.fields) == ["status", "created_at"]
    assert index.condition == Q(status="RESERVED")


def test_lapsed_at_is_nullable_and_unlapsed_partial_index_is_declared():
    assert ShopCreditBalance._meta.get_field("lapsed_at").null is True
    assert ShopCreditBalanceFactory().lapsed_at is None
    index = next(i for i in ShopCreditBalance._meta.indexes if i.name == "credit_bal_unlapsed_idx")
    assert list(index.fields) == ["period_year", "period_month"]
    assert index.condition == Q(lapsed_at__isnull=True)


# --- FK delete rules (D-02) ----------------------------------------------------


def test_ledger_row_survives_with_null_fk_when_review_is_deleted():
    review = ReviewFactory()
    tx = CreditTransactionFactory(review=review)
    review.delete()
    tx.refresh_from_db()
    assert tx.review is None


def test_ledger_row_survives_with_null_actor_when_user_is_deleted():
    user = UserFactory()
    tx = CreditTransactionFactory(actor=user)
    user.delete()
    tx.refresh_from_db()
    assert tx.actor is None


def test_ledger_row_survives_with_null_usage_log_when_ai_usage_log_is_deleted():
    usage = AiUsageLogFactory()
    tx = CreditTransactionFactory(ai_usage_log=usage)
    usage.delete()
    tx.refresh_from_db()
    assert tx.ai_usage_log is None


def test_shop_delete_is_protected_when_a_balance_exists():
    balance = ShopCreditBalanceFactory()
    with pytest.raises(ProtectedError) as excinfo, transaction.atomic():
        balance.shop.delete()
    assert balance in excinfo.value.protected_objects


def test_organisation_delete_is_protected_when_a_balance_exists():
    balance = ShopCreditBalanceFactory()
    with pytest.raises(ProtectedError), transaction.atomic():
        balance.organisation.delete()
    assert ShopCreditBalance.objects.filter(pk=balance.pk).exists()


# --- Meta (ordering edge, D-04) ------------------------------------------------


def test_pk_is_big_auto_field_and_unordered_when_inspecting_ledger_meta():
    assert CreditTransaction._meta.pk.get_internal_type() == "BigAutoField"
    assert not CreditTransaction._meta.ordering


def test_note_is_nullable_with_max_length_255_when_inspecting_field():
    note = CreditTransaction._meta.get_field("note")
    assert note.max_length == 255
    assert note.null is True


# --- assert_ledger_reconciles --------------------------------------------------


def _reconcile_fixture(consumed: int) -> ShopCreditBalance:
    balance = ShopCreditBalanceFactory(allocated_credits=10)
    CreditTransactionFactory(shop_credit_balance=balance, status=Status.RESERVED, credits_delta=-1)
    CreditTransactionFactory(shop_credit_balance=balance, status=Status.COMMITTED, credits_delta=-2)
    CreditTransactionFactory(shop_credit_balance=balance, status=Status.REFUNDED, credits_delta=-5)
    ShopCreditBalance.objects.filter(pk=balance.pk).update(
        consumed_credits=consumed, updated_at=timezone.now()
    )
    return balance


def test_reconcile_passes_when_consumed_matches_live_consumption_rows():
    assert_ledger_reconciles(_reconcile_fixture(consumed=3))


def test_reconcile_raises_when_consumed_differs_from_live_consumption_rows():
    with pytest.raises(AssertionError, match="does not reconcile"):
        assert_ledger_reconciles(_reconcile_fixture(consumed=4))
