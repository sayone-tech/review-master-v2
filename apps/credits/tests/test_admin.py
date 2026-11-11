"""Credit admins are read-only investigation surfaces (D-05, CRED-03)."""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.credits.models import CreditTransaction, ShopCreditBalance
from apps.credits.tests.factories import CreditTransactionFactory, ShopCreditBalanceFactory

pytestmark = pytest.mark.django_db

MODELS = ["shopcreditbalance", "credittransaction"]


@pytest.fixture
def admin_client(client):
    client.force_login(UserFactory(is_staff=True, is_superuser=True))
    return client


def _make_row(model_name: str):
    if model_name == "shopcreditbalance":
        return ShopCreditBalanceFactory()
    return CreditTransactionFactory()


def _url(model_name: str, view: str, *args):
    return reverse(f"admin:credits_{model_name}_{view}", args=args)


@pytest.mark.parametrize("model_name", MODELS)
def test_changelist_and_view_page_return_200_when_superuser(admin_client, model_name):
    row = _make_row(model_name)
    assert admin_client.get(_url(model_name, "changelist")).status_code == 200
    assert admin_client.get(_url(model_name, "change", row.pk)).status_code == 200


@pytest.mark.parametrize("model_name", MODELS)
def test_add_returns_403_when_superuser(admin_client, model_name):
    assert admin_client.get(_url(model_name, "add")).status_code == 403


@pytest.mark.parametrize("model_name", MODELS)
def test_change_post_returns_403_and_row_unchanged_when_superuser(admin_client, model_name):
    row = _make_row(model_name)
    response = admin_client.post(_url(model_name, "change", row.pk), {"credits_delta": -99})
    assert response.status_code == 403
    if model_name == "credittransaction":
        assert CreditTransaction.objects.get(pk=row.pk).credits_delta == -1
    else:
        assert ShopCreditBalance.objects.get(pk=row.pk).allocated_credits == 10


@pytest.mark.parametrize("model_name", MODELS)
def test_delete_returns_403_when_superuser(admin_client, model_name):
    row = _make_row(model_name)
    assert admin_client.get(_url(model_name, "delete", row.pk)).status_code == 403
    assert admin_client.post(_url(model_name, "delete", row.pk), {"post": "yes"}).status_code == 403


def _changelist_queries(client, model_name: str) -> int:
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(_url(model_name, "changelist")).status_code == 200
    return len(ctx.captured_queries)


@pytest.mark.parametrize("model_name", MODELS)
def test_changelist_query_count_is_constant_when_row_count_grows(admin_client, model_name):
    for _ in range(2):
        _make_row(model_name)
    small = _changelist_queries(admin_client, model_name)
    for _ in range(8):
        _make_row(model_name)
    large = _changelist_queries(admin_client, model_name)
    assert small == large
