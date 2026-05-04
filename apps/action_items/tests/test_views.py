"""Phase 13 plan 04 — ActionItemViewSet API tests including ACTN-12 query-count gate."""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from django.urls.exceptions import Resolver404
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory
from apps.action_items.models import ActionItem, ActionItemNote
from apps.action_items.tests.factories import ActionItemFactory
from apps.common.models import AuditLog
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/action-items/"


def _detail_url(pk: int) -> str:
    return f"/api/v1/action-items/{pk}/"


@pytest.fixture
def org_admin_setup():
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, org


@pytest.fixture
def staff_setup():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop
    )
    client = APIClient()
    client.force_authenticate(user=staff)
    return client, staff, org, shop


def test_list_returns_org_admin_all_items(org_admin_setup) -> None:
    client, _, org = org_admin_setup
    s1 = ShopFactory(organisation=org)
    ActionItemFactory(organisation=org, shop=s1, scope=ActionItem.Scope.SHOP)
    ActionItemFactory(organisation=org, shop=s1, scope=ActionItem.Scope.SHOP)
    ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 3


def test_list_staff_excludes_brand_and_inaccessible_shops(staff_setup) -> None:
    client, _staff, org, accessible_shop = staff_setup
    other_shop = ShopFactory(organisation=org)
    ActionItemFactory(organisation=org, shop=accessible_shop, scope=ActionItem.Scope.SHOP)
    ActionItemFactory(organisation=org, shop=other_shop, scope=ActionItem.Scope.SHOP)
    ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1


def test_staff_cannot_retrieve_brand_item_returns_403(staff_setup) -> None:
    client, _staff, org, _shop = staff_setup
    brand_item = ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
    resp = client.get(_detail_url(brand_item.pk))
    assert resp.status_code in (403, 404)
    # Layer 1 (selector) hides BRAND items from Staff entirely → 404 expected
    # in current implementation; Layer 2 (BrandScopeGuard) is the belt for
    # any case where the item somehow resolves. Both are valid blocks.


def test_org_admin_can_create_manual_item(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    payload = {
        "title": "Fix the broken sign at the front",
        "scope": ActionItem.Scope.SHOP,
        "shop": shop.pk,
        "priority": ActionItem.Priority.HIGH,
    }
    resp = client.post(LIST_URL, payload, format="json")
    assert resp.status_code == 201, resp.data
    item = ActionItem.objects.get(pk=resp.data["id"])
    assert item.source == ActionItem.Source.MANUAL
    assert item.priority == ActionItem.Priority.HIGH
    assert AuditLog.objects.filter(
        entity_type="action_item",
        entity_id=str(item.pk),
        action="action_item.created",
    ).exists()


def test_create_with_initial_note_creates_note_row(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    payload = {
        "title": "Replace ceiling tile",
        "scope": ActionItem.Scope.SHOP,
        "shop": shop.pk,
        "initial_note": "Saw it sagging this morning",
    }
    resp = client.post(LIST_URL, payload, format="json")
    assert resp.status_code == 201
    item_pk = resp.data["id"]
    assert ActionItemNote.objects.filter(
        action_item_id=item_pk, body="Saw it sagging this morning"
    ).exists()


def test_create_shop_scope_without_shop_fails_400(org_admin_setup) -> None:
    client, _user, _org = org_admin_setup
    payload = {
        "title": "A title that is long enough",
        "scope": ActionItem.Scope.SHOP,
    }
    resp = client.post(LIST_URL, payload, format="json")
    assert resp.status_code == 400
    assert "shop" in resp.data


def test_partial_update_cannot_change_scope_or_shop(org_admin_setup) -> None:
    """ACTN-07: PATCH silently ignores scope/shop fields (not declared on update serializer)."""
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    item = ActionItemFactory(organisation=org, shop=shop, scope=ActionItem.Scope.SHOP)
    payload = {
        "scope": ActionItem.Scope.BRAND,
        "shop": None,
        "title": "New title for this item",
    }
    resp = client.patch(_detail_url(item.pk), payload, format="json")
    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.scope == ActionItem.Scope.SHOP
    assert item.shop_id == shop.pk
    assert item.title == "New title for this item"


def test_transition_status_endpoint_writes_audit_log(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    item = ActionItemFactory(
        organisation=org,
        shop=shop,
        scope=ActionItem.Scope.SHOP,
        status=ActionItem.Status.TODO,
    )
    resp = client.post(
        f"{_detail_url(item.pk)}transition-status/",
        {"status": ActionItem.Status.COMPLETE},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    item.refresh_from_db()
    assert item.status == ActionItem.Status.COMPLETE
    assert AuditLog.objects.filter(
        entity_type="action_item",
        entity_id=str(item.pk),
        action="action_item.status_changed",
    ).exists()


def test_add_note_endpoint_creates_note_and_audit(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    item = ActionItemFactory(organisation=org, shop=shop, scope=ActionItem.Scope.SHOP)
    resp = client.post(
        f"{_detail_url(item.pk)}add-note/",
        {"body": "hello world note"},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert ActionItemNote.objects.filter(action_item=item, body="hello world note").exists()
    assert AuditLog.objects.filter(
        entity_type="action_item",
        entity_id=str(item.pk),
        action="action_item.note_added",
    ).exists()


def test_list_query_count_org_admin_le_5(org_admin_setup) -> None:
    """ACTN-12: <=5 SQL queries on list endpoint regardless of result size."""
    client, _user, org = org_admin_setup
    shops = [ShopFactory(organisation=org) for _ in range(3)]
    for i in range(20):
        ActionItemFactory(
            organisation=org,
            shop=shops[i % 3],
            scope=ActionItem.Scope.SHOP,
        )
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(LIST_URL, {"page_size": 20})
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20
    assert len(ctx.captured_queries) <= 5, [q["sql"] for q in ctx.captured_queries]


def test_list_query_count_staff_le_5(staff_setup) -> None:
    """ACTN-12 + Staff scope: <=5 queries with the StaffAccessScope subquery."""
    client, staff, org, accessible_shop = staff_setup
    extra_shop = ShopFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=extra_shop
    )
    for i in range(20):
        ActionItemFactory(
            organisation=org,
            shop=accessible_shop if i % 2 == 0 else extra_shop,
            scope=ActionItem.Scope.SHOP,
        )
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(LIST_URL, {"page_size": 20})
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5, [q["sql"] for q in ctx.captured_queries]


def test_no_patch_or_delete_endpoint_for_notes(org_admin_setup) -> None:
    """ACTN-10: notes are append-only — no per-note edit/delete URL exists."""
    _client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    item = ActionItemFactory(organisation=org, shop=shop, scope=ActionItem.Scope.SHOP)
    note_url = f"/api/v1/action-items/{item.pk}/notes/1/"
    with pytest.raises(Resolver404):
        resolve(note_url)
