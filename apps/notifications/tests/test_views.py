"""Phase 13 plan 05 — NotificationViewSet API tests.

Covers NOTF-01 (bell list), NOTF-03 (mark-read / mark-all-read), NOTF-04
(unread count), and the bell endpoint's <=3 SQL query budget gate.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.tests.factories import OrgAdminFactory
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

BELL_URL = "/api/v1/notifications/bell/"
MARK_ALL_URL = "/api/v1/notifications/mark-all-read/"


def _read_url(pk: int) -> str:
    return f"/api/v1/notifications/{pk}/read/"


@pytest.fixture
def setup():
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, org


def test_bell_returns_unread_count_and_items(setup) -> None:
    client, user, org = setup
    NotificationFactory.create_batch(3, recipient=user, organisation=org, is_read=False)
    NotificationFactory.create_batch(2, recipient=user, organisation=org, is_read=True)
    resp = client.get(BELL_URL)
    assert resp.status_code == 200
    assert resp.data["unread_count"] == 3
    assert len(resp.data["items"]) == 3
    # Newest-first: items[0] should be the most recently created unread.
    ids_returned = [item["id"] for item in resp.data["items"]]
    expected = list(
        Notification.objects.filter(recipient=user, is_read=False)
        .order_by("-created_at")
        .values_list("id", flat=True)
    )
    assert ids_returned == expected


def test_bell_caps_items_at_10(setup) -> None:
    client, user, org = setup
    NotificationFactory.create_batch(15, recipient=user, organisation=org, is_read=False)
    resp = client.get(BELL_URL)
    assert resp.status_code == 200
    assert resp.data["unread_count"] == 15
    assert len(resp.data["items"]) == 10


def test_bell_excludes_other_users(setup) -> None:
    client, _user, org = setup
    other = OrgAdminFactory(organisation=org)
    NotificationFactory(recipient=other, organisation=org, is_read=False)
    resp = client.get(BELL_URL)
    assert resp.status_code == 200
    assert resp.data["unread_count"] == 0
    assert resp.data["items"] == []


def test_mark_read_sets_is_read_true(setup) -> None:
    client, user, org = setup
    n = NotificationFactory(recipient=user, organisation=org, is_read=False)
    resp = client.post(_read_url(n.pk))
    assert resp.status_code == 200
    n.refresh_from_db()
    assert n.is_read is True


def test_mark_read_idempotent(setup) -> None:
    client, user, org = setup
    n = NotificationFactory(recipient=user, organisation=org, is_read=False)
    resp1 = client.post(_read_url(n.pk))
    resp2 = client.post(_read_url(n.pk))
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    n.refresh_from_db()
    assert n.is_read is True


def test_mark_read_returns_404_for_other_user_notification(setup) -> None:
    client, _, org = setup
    other = OrgAdminFactory(organisation=org)
    n = NotificationFactory(recipient=other, organisation=org, is_read=False)
    resp = client.post(_read_url(n.pk))
    # get_queryset filters by recipient — other-user notification is invisible.
    assert resp.status_code == 404
    n.refresh_from_db()
    assert n.is_read is False  # never modified


def test_mark_all_read_marks_all_unread_for_user(setup) -> None:
    client, user, org = setup
    NotificationFactory.create_batch(5, recipient=user, organisation=org, is_read=False)
    NotificationFactory.create_batch(2, recipient=user, organisation=org, is_read=True)
    # Notification belonging to a different user must NOT be touched.
    other = OrgAdminFactory(organisation=org)
    other_unread = NotificationFactory(recipient=other, organisation=org, is_read=False)
    resp = client.post(MARK_ALL_URL)
    assert resp.status_code == 200
    assert Notification.objects.filter(recipient=user, is_read=False).count() == 0
    assert Notification.objects.filter(recipient=user, is_read=True).count() == 7
    other_unread.refresh_from_db()
    assert other_unread.is_read is False


def test_bell_query_count_le_3(setup) -> None:
    """Hot-path budget — bell endpoint must stay within 3 SQL queries on a
    populated user. Auth (1) + count (1) + select-with-select_related (1)."""
    client, user, org = setup
    shop = ShopFactory(organisation=org)
    NotificationFactory.create_batch(15, recipient=user, organisation=org, is_read=False, shop=shop)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(BELL_URL)
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 3, [q["sql"] for q in ctx.captured_queries]
