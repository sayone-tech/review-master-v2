"""Phase 21 plan 01 — Selector + serializer unit tests for AuditLog viewer.

Covers:
  * list_audit_logs_for_org — entity filter (D-01), org isolation (D-02).
  * list_audit_logs_for_staff — two-step scope (D-03): excludes brand-scope
    action items and reviews in inaccessible shops.
  * AuditLogReadSerializer — omits before_data (D-10), includes actor_name
    (D-11), handles system (actor=None) rows.
  * N+1 prevention — select_related('actor') keeps query count fixed.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import StaffAccessScope, User
from apps.accounts.tests.factories import StaffAccessScopeFactory, UserFactory
from apps.action_items.models import ActionItem
from apps.action_items.tests.factories import ActionItemFactory
from apps.common.selectors.audit_logs import (
    list_audit_logs_for_org,
    list_audit_logs_for_staff,
)
from apps.common.serializers import AuditLogReadSerializer
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import AuditLogFactory, ReviewFactory
from apps.shops.tests.factories import ShopFactory


@pytest.mark.django_db
def test_list_audit_logs_for_org_includes_reply_actions():
    org = OrganisationFactory()
    for action in ("reply_posted", "reply_deleted", "reply_failed"):
        AuditLogFactory(organisation=org, entity_type="review", action=action)
    AuditLogFactory(
        organisation=org,
        entity_type="shop_sync",
        action="sync_triggered",
    )
    rows = list(list_audit_logs_for_org(organisation_id=org.id))
    actions = sorted(r.action for r in rows)
    assert actions == ["reply_deleted", "reply_failed", "reply_posted"]


@pytest.mark.django_db
def test_list_audit_logs_for_org_includes_action_item_events():
    org = OrganisationFactory()
    AuditLogFactory(
        organisation=org,
        entity_type="action_item",
        action="action_item.status_changed",
    )
    rows = list(list_audit_logs_for_org(organisation_id=org.id))
    assert len(rows) == 1
    assert rows[0].entity_type == "action_item"


@pytest.mark.django_db
def test_list_audit_logs_for_org_excludes_other_orgs():
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    AuditLogFactory(organisation=org_a, entity_type="review", action="reply_posted")
    AuditLogFactory(organisation=org_b, entity_type="review", action="reply_posted")
    rows = list(list_audit_logs_for_org(organisation_id=org_a.id))
    assert len(rows) == 1
    assert rows[0].organisation_id == org_a.id


@pytest.mark.django_db
def test_list_audit_logs_for_staff_excludes_brand_scope_items():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    staff = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    StaffAccessScopeFactory(
        user=staff,
        scope_type=StaffAccessScope.ScopeType.SHOP,
        region=None,
        shop=shop,
    )
    brand_item = ActionItemFactory(organisation=org, shop=shop, scope=ActionItem.Scope.BRAND)
    shop_item = ActionItemFactory(organisation=org, shop=shop, scope=ActionItem.Scope.SHOP)
    AuditLogFactory(
        organisation=org,
        entity_type="action_item",
        entity_id=str(brand_item.pk),
        action="action_item.status_changed",
    )
    AuditLogFactory(
        organisation=org,
        entity_type="action_item",
        entity_id=str(shop_item.pk),
        action="action_item.status_changed",
    )
    rows = list(list_audit_logs_for_staff(organisation_id=org.id, user=staff))
    entity_ids = {r.entity_id for r in rows}
    assert entity_ids == {str(shop_item.pk)}


@pytest.mark.django_db
def test_list_audit_logs_for_staff_excludes_inaccessible_shop_reviews():
    org = OrganisationFactory()
    shop_a = ShopFactory(organisation=org)
    shop_b = ShopFactory(organisation=org)
    staff = UserFactory(role=User.Role.STAFF_ADMIN, organisation=org)
    StaffAccessScopeFactory(
        user=staff,
        scope_type=StaffAccessScope.ScopeType.SHOP,
        region=None,
        shop=shop_a,
    )
    review_a = ReviewFactory(organisation=org, shop=shop_a)
    review_b = ReviewFactory(organisation=org, shop=shop_b)
    AuditLogFactory(
        organisation=org,
        entity_type="review",
        entity_id=str(review_a.pk),
        action="reply_posted",
    )
    AuditLogFactory(
        organisation=org,
        entity_type="review",
        entity_id=str(review_b.pk),
        action="reply_posted",
    )
    rows = list(list_audit_logs_for_staff(organisation_id=org.id, user=staff))
    entity_ids = {r.entity_id for r in rows}
    assert entity_ids == {str(review_a.pk)}


@pytest.mark.django_db
def test_serializer_includes_actor_name_excludes_before_data():
    org = OrganisationFactory()
    actor = UserFactory(role=User.Role.ORG_ADMIN, organisation=org, full_name="Alice Admin")
    log = AuditLogFactory(
        organisation=org,
        actor=actor,
        entity_type="review",
        action="reply_posted",
        before_data={"x": 1},
        after_data={"reply_text": "ok"},
    )
    data = AuditLogReadSerializer(log).data
    assert data["actor_name"] == "Alice Admin"
    assert data["actor_id"] == actor.pk
    assert "before_data" not in data
    assert data["after_data"] == {"reply_text": "ok"}


@pytest.mark.django_db
def test_serializer_system_actor_name_is_none():
    org = OrganisationFactory()
    log = AuditLogFactory(organisation=org, actor=None, entity_type="review", action="reply_posted")
    data = AuditLogReadSerializer(log).data
    assert data["actor_name"] is None
    assert data["actor_id"] is None


@pytest.mark.django_db
def test_list_audit_logs_for_org_no_n_plus_one():
    org = OrganisationFactory()
    actors = [
        UserFactory(role=User.Role.ORG_ADMIN, organisation=org, email=f"a{i}@x.com")
        for i in range(5)
    ]
    for actor in actors:
        AuditLogFactory(organisation=org, actor=actor, entity_type="review", action="reply_posted")
    qs = list_audit_logs_for_org(organisation_id=org.id)
    with CaptureQueriesContext(connection) as ctx:
        # Materialise the queryset and serialise each row — including actor.
        rows = list(qs)
        for r in rows:
            _ = r.actor.full_name if r.actor else None
    assert len(rows) == 5
    # select_related('actor') means: 1 query for AuditLog (joined with User).
    assert len(ctx.captured_queries) <= 3, [q["sql"] for q in ctx.captured_queries]
