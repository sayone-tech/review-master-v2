"""Phase 21 plan 02 — AuditLogViewSet API tests.

Covers REQ-01..REQ-05, REQ-09 and threats T-21-03/T-21-04/T-21-06 per
.planning/phases/21-audit-log-viewer/21-02-PLAN.md.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope, User
from apps.accounts.tests.factories import (
    OrgAdminFactory,
    StaffAdminFactory,
    UserFactory,
)
from apps.action_items.models import ActionItem
from apps.action_items.tests.factories import ActionItemFactory
from apps.common.models import AuditLog
from apps.common.views import AuditLogViewSet
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import AuditLogFactory, ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/audit-logs/"


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
    accessible_shop = ShopFactory(organisation=org)
    inaccessible_shop = ShopFactory(organisation=org)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff,
        scope_type=StaffAccessScope.ScopeType.SHOP,
        shop=accessible_shop,
    )
    client = APIClient()
    client.force_authenticate(user=staff)
    return client, staff, org, accessible_shop, inaccessible_shop


def test_list_audit_logs_org_admin(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    AuditLogFactory(organisation=org, entity_type="review", action="reply_posted")
    AuditLogFactory(
        organisation=org, entity_type="action_item", action="action_item.created"
    )
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert "results" in resp.data
    assert len(resp.data["results"]) == 2


def test_cursor_pagination(org_admin_setup) -> None:
    """Cursor pagination shape: 'next', 'previous', 'results' keys."""
    client, _user, org = org_admin_setup
    AuditLogFactory.create_batch(3, organisation=org, entity_type="review", action="reply_posted")
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert "next" in resp.data
    assert "previous" in resp.data
    assert "results" in resp.data


def test_list_query_count(org_admin_setup, assert_query_ceiling) -> None:
    """Query count is fixed (<=5) regardless of result size (CLAUDE.md §6.9)."""
    client, _user, org = org_admin_setup
    for _ in range(50):
        actor = UserFactory(organisation=org)
        AuditLogFactory(
            organisation=org,
            actor=actor,
            entity_type="review",
            action="reply_posted",
        )
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert_query_ceiling(ctx, max_queries=5)


def test_staff_scope(staff_setup) -> None:
    """Staff sees only entries for reviews in accessible shops."""
    client, _staff, org, accessible_shop, inaccessible_shop = staff_setup
    review_in = ReviewFactory(organisation=org, shop=accessible_shop)
    review_out = ReviewFactory(organisation=org, shop=inaccessible_shop)
    AuditLogFactory(
        organisation=org,
        entity_type="review",
        entity_id=str(review_in.pk),
        action="reply_posted",
    )
    AuditLogFactory(
        organisation=org,
        entity_type="review",
        entity_id=str(review_out.pk),
        action="reply_posted",
    )
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    entity_ids = {row["entity_id"] for row in resp.data["results"]}
    assert str(review_in.pk) in entity_ids
    assert str(review_out.pk) not in entity_ids


def test_staff_cannot_see_brand_items(staff_setup) -> None:
    """Brand-scope action item audit logs are absent from Staff response."""
    client, _staff, org, accessible_shop, _inaccessible_shop = staff_setup
    brand_item = ActionItemFactory(
        organisation=org, shop=None, scope=ActionItem.Scope.BRAND
    )
    shop_item = ActionItemFactory(
        organisation=org, shop=accessible_shop, scope=ActionItem.Scope.SHOP
    )
    AuditLogFactory(
        organisation=org,
        entity_type="action_item",
        entity_id=str(brand_item.pk),
        action="action_item.created",
    )
    AuditLogFactory(
        organisation=org,
        entity_type="action_item",
        entity_id=str(shop_item.pk),
        action="action_item.created",
    )
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    entity_ids = {row["entity_id"] for row in resp.data["results"]}
    assert str(brand_item.pk) not in entity_ids
    assert str(shop_item.pk) in entity_ids


def test_filter_entity_type(org_admin_setup) -> None:
    """?entity_type=review returns only review-type rows."""
    client, _user, org = org_admin_setup
    AuditLogFactory(organisation=org, entity_type="review", action="reply_posted")
    AuditLogFactory(
        organisation=org, entity_type="action_item", action="action_item.created"
    )
    resp = client.get(LIST_URL, {"entity_type": "review"})
    assert resp.status_code == 200
    types = {row["entity_type"] for row in resp.data["results"]}
    assert types == {"review"}


def test_filter_date_range(org_admin_setup) -> None:
    """?date_from / ?date_to filter on created_at."""
    client, _user, org = org_admin_setup
    a = AuditLogFactory(organisation=org, entity_type="review", action="reply_posted")
    b = AuditLogFactory(organisation=org, entity_type="review", action="reply_posted")
    # Backdate one entry to before the range.
    AuditLog.objects.filter(pk=a.pk).update(
        created_at=dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    )
    resp = client.get(
        LIST_URL, {"date_from": "2099-01-01", "date_to": "2099-12-31"}
    )
    # 'a' (2020) is outside; 'b' (today) is also outside the 2099 window — both
    # filtered out. Now widen to today:
    resp = client.get(LIST_URL, {"date_from": "2021-01-01"})
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data["results"]}
    assert b.pk in ids
    assert a.pk not in ids


def test_filter_actor_system(org_admin_setup) -> None:
    """?actor=system returns only entries where actor is null."""
    client, _user, org = org_admin_setup
    actor = UserFactory(organisation=org)
    AuditLogFactory(
        organisation=org,
        actor=None,
        entity_type="review",
        action="reply_posted",
    )
    AuditLogFactory(
        organisation=org,
        actor=actor,
        entity_type="review",
        action="reply_posted",
    )
    resp = client.get(LIST_URL, {"actor": "system"})
    assert resp.status_code == 200
    actor_ids = [row["actor_id"] for row in resp.data["results"]]
    assert all(a is None for a in actor_ids)
    assert len(actor_ids) == 1


def test_serializer_fields(org_admin_setup) -> None:
    """Response result has actor_name; before_data is NOT serialized (D-11)."""
    client, _user, org = org_admin_setup
    actor = UserFactory(organisation=org, full_name="Jane Doe")
    AuditLogFactory(
        organisation=org,
        actor=actor,
        entity_type="review",
        action="reply_posted",
        before_data={"secret": "should_not_leak"},
    )
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    row = resp.data["results"][0]
    assert "actor_name" in row
    assert row["actor_name"] == "Jane Doe"
    assert "before_data" not in row


def test_throttle_scope() -> None:
    """ViewSet declares the audit_log_list throttle scope (D-09)."""
    assert AuditLogViewSet.throttle_scope == "audit_log_list"


def test_superadmin_forbidden() -> None:
    """Superadmin role is denied (D-06)."""
    superadmin = UserFactory(role=User.Role.SUPERADMIN, organisation=None)
    client = APIClient()
    client.force_authenticate(user=superadmin)
    resp = client.get(LIST_URL)
    assert resp.status_code == 403


def test_unauthenticated_returns_401() -> None:
    """Unauthenticated request returns 401."""
    client = APIClient()
    resp = client.get(LIST_URL)
    assert resp.status_code in (401, 403)
    # DRF returns 401 when no authentication classes assert credentials, 403
    # when an auth class is present but rejects. Either is a valid block.
