"""Ledger append-only guards and the status CAS (CRED-03, D-05, D-06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.credits.exceptions import AppendOnlyViolation, InvalidStatusTransition
from apps.credits.models import CreditTransaction
from apps.credits.services.ledger import transition_status
from apps.credits.tests.factories import CreditTransactionFactory, ShopCreditBalanceFactory

pytestmark = pytest.mark.django_db

Status = CreditTransaction.Status


def _stored_status(tx: CreditTransaction) -> str:
    return CreditTransaction.objects.values_list("status", flat=True).get(pk=tx.pk)


# --- append-only guards (D-05) -------------------------------------------------


def test_queryset_update_raises_when_called_on_ledger_rows():
    tx = CreditTransactionFactory()
    with pytest.raises(AppendOnlyViolation):
        CreditTransaction.objects.filter(pk=tx.pk).update(status=Status.COMMITTED)
    assert _stored_status(tx) == Status.RESERVED


def test_queryset_delete_raises_when_called_on_ledger_rows():
    tx = CreditTransactionFactory()
    with pytest.raises(AppendOnlyViolation):
        CreditTransaction.objects.filter(pk=tx.pk).delete()
    assert CreditTransaction.objects.filter(pk=tx.pk).exists()


def test_bulk_update_raises_when_called_on_ledger_rows():
    tx = CreditTransactionFactory()
    tx.status = Status.COMMITTED
    # bulk_update opens atomic(savepoint=False), so isolate it in our own savepoint.
    with pytest.raises(AppendOnlyViolation), transaction.atomic():
        CreditTransaction.objects.bulk_update([tx], ["status"])
    assert _stored_status(tx) == Status.RESERVED


def test_instance_delete_raises_when_called_on_ledger_row():
    tx = CreditTransactionFactory()
    with pytest.raises(AppendOnlyViolation):
        tx.delete()
    assert CreditTransaction.objects.filter(pk=tx.pk).exists()


def test_save_raises_when_no_update_fields_on_existing_row():
    tx = CreditTransactionFactory()
    tx.credits_delta = -9
    with pytest.raises(AppendOnlyViolation):
        tx.save()
    assert CreditTransaction.objects.values_list("credits_delta", flat=True).get(pk=tx.pk) == -1


def test_save_raises_when_update_fields_is_not_status_only():
    tx = CreditTransactionFactory()
    tx.credits_delta = -9
    with pytest.raises(AppendOnlyViolation):
        tx.save(update_fields=["credits_delta"])
    tx.status = Status.COMMITTED
    tx.note = "x"
    with pytest.raises(AppendOnlyViolation):
        tx.save(update_fields=["status", "note"])
    assert _stored_status(tx) == Status.RESERVED


def test_bulk_create_raises_when_update_conflicts_requested():
    # WR-02: bulk_create(update_conflicts=True) is an upsert that rewrites committed rows.
    tx = CreditTransactionFactory()
    clone = CreditTransaction(
        pk=tx.pk,
        shop_credit_balance=tx.shop_credit_balance,
        shop=tx.shop,
        organisation=tx.organisation,
        transaction_type=CreditTransaction.Type.CONSUMPTION,
        status=Status.RESERVED,
        credits_delta=-7,
        created_at=timezone.now(),
    )
    with pytest.raises(AppendOnlyViolation), transaction.atomic():
        CreditTransaction.objects.bulk_create(
            [clone],
            update_conflicts=True,
            unique_fields=["id"],
            update_fields=["credits_delta"],
        )
    tx.refresh_from_db()
    assert tx.credits_delta == -1


def test_bulk_create_inserts_rows_when_update_conflicts_not_requested():
    balance = ShopCreditBalanceFactory()
    rows = CreditTransaction.objects.bulk_create(
        [
            CreditTransaction(
                shop_credit_balance=balance,
                shop=balance.shop,
                organisation=balance.organisation,
                transaction_type=CreditTransaction.Type.CONSUMPTION,
                status=Status.RESERVED,
                credits_delta=-1,
            )
            for _ in range(2)
        ],
        update_conflicts=False,
    )
    assert len(rows) == 2
    assert CreditTransaction.objects.filter(shop_credit_balance=balance).count() == 2


def test_save_raises_integrity_error_when_new_instance_reuses_existing_pk():
    # WR-01: an in-memory instance (adding=True) carrying an existing pk must never
    # fall through to Django's UPDATE-then-INSERT; the insert is forced and collides.
    tx = CreditTransactionFactory()
    clone = CreditTransaction(
        pk=tx.pk,
        shop_credit_balance=tx.shop_credit_balance,
        shop=tx.shop,
        organisation=tx.organisation,
        transaction_type=CreditTransaction.Type.CONSUMPTION,
        status=Status.COMMITTED,
        credits_delta=-7,
        created_at=timezone.now(),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        clone.save()
    tx.refresh_from_db()
    assert tx.credits_delta == -1
    assert tx.status == Status.RESERVED


def test_create_and_bulk_create_insert_rows_when_ledger_is_append_only():
    balance = ShopCreditBalanceFactory()
    created = CreditTransactionFactory(shop_credit_balance=balance)
    rows = CreditTransaction.objects.bulk_create(
        [
            CreditTransaction(
                shop_credit_balance=balance,
                shop=balance.shop,
                organisation=balance.organisation,
                transaction_type=CreditTransaction.Type.CONSUMPTION,
                status=Status.RESERVED,
                credits_delta=-1,
            )
            for _ in range(3)
        ]
    )
    assert created.pk is not None
    assert len(rows) == 3
    assert CreditTransaction.objects.filter(shop_credit_balance=balance).count() == 4


# --- transition_status (D-06) --------------------------------------------------


def test_transition_returns_true_then_false_when_same_commit_repeated():
    tx = CreditTransactionFactory()
    kwargs = {
        "transaction_id": tx.pk,
        "from_status": Status.RESERVED,
        "to_status": Status.COMMITTED,
    }
    assert transition_status(**kwargs) is True
    assert transition_status(**kwargs) is False
    assert _stored_status(tx) == Status.COMMITTED


def test_transition_returns_true_when_reserved_row_is_refunded():
    tx = CreditTransactionFactory()
    assert (
        transition_status(
            transaction_id=tx.pk, from_status=Status.RESERVED, to_status=Status.REFUNDED
        )
        is True
    )
    assert _stored_status(tx) == Status.REFUNDED


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (Status.COMMITTED, Status.REFUNDED),
        (Status.REFUNDED, Status.COMMITTED),
        (Status.RESERVED, Status.RESERVED),
    ],
)
def test_transition_raises_when_pair_is_not_allowed(from_status, to_status):
    tx = CreditTransactionFactory()
    with pytest.raises(InvalidStatusTransition):
        transition_status(transaction_id=tx.pk, from_status=from_status, to_status=to_status)
    assert _stored_status(tx) == Status.RESERVED


def test_transition_returns_false_when_transaction_does_not_exist():
    assert (
        transition_status(
            transaction_id=987654321, from_status=Status.RESERVED, to_status=Status.COMMITTED
        )
        is False
    )


def test_refund_after_commit_returns_false_and_keeps_committed_when_already_settled():
    tx = CreditTransactionFactory()
    assert transition_status(
        transaction_id=tx.pk, from_status=Status.RESERVED, to_status=Status.COMMITTED
    )
    assert (
        transition_status(
            transaction_id=tx.pk, from_status=Status.RESERVED, to_status=Status.REFUNDED
        )
        is False
    )
    assert _stored_status(tx) == Status.COMMITTED


# --- instance.save(update_fields=["status"]) goes through the same CAS --------


def test_save_status_only_succeeds_when_row_is_reserved():
    tx = CreditTransactionFactory()
    tx.status = Status.COMMITTED
    tx.save(update_fields=["status"])
    assert _stored_status(tx) == Status.COMMITTED


def test_save_status_only_raises_when_row_is_already_committed():
    tx = CreditTransactionFactory()
    transition_status(transaction_id=tx.pk, from_status=Status.RESERVED, to_status=Status.COMMITTED)
    tx.refresh_from_db()
    tx.status = Status.REFUNDED
    with pytest.raises(InvalidStatusTransition):
        tx.save(update_fields=["status"])
    assert _stored_status(tx) == Status.COMMITTED


def test_save_status_only_raises_when_target_is_not_allowed():
    tx = CreditTransactionFactory()
    tx.status = Status.RESERVED
    with pytest.raises(InvalidStatusTransition):
        tx.save(update_fields=["status"])
    assert _stored_status(tx) == Status.RESERVED


def test_save_status_only_raises_when_instance_is_stale():
    tx = CreditTransactionFactory()
    # Row settled behind the in-memory instance's back (it still believes RESERVED).
    transition_status(transaction_id=tx.pk, from_status=Status.RESERVED, to_status=Status.REFUNDED)
    tx.status = Status.COMMITTED
    with pytest.raises(InvalidStatusTransition):
        tx.save(update_fields=["status"])
    assert _stored_status(tx) == Status.REFUNDED


# --- the CAS escape hatch has exactly the sanctioned callers (D-05) -----------


def test_cas_status_is_called_only_from_ledger_and_model_when_scanning_apps():
    allowed = {
        "apps/credits/managers.py",
        "apps/credits/models.py",
        "apps/credits/services/ledger.py",
    }
    root = Path(__file__).resolve().parents[3]
    found = set()
    for path in (root / "apps").rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if "/tests/" in rel or "/migrations/" in rel:
            continue
        if "cas_status(" in path.read_text(encoding="utf-8"):
            found.add(rel)
    assert found == allowed
