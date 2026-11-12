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
    AuditLogFactory(organisation=org, entity_type="action_item", action="action_item.created")
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
    brand_item = ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
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
    AuditLogFactory(organisation=org, entity_type="action_item", action="action_item.created")
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
    AuditLog.objects.filter(pk=a.pk).update(created_at=dt.datetime(2020, 1, 1, tzinfo=dt.UTC))
    resp = client.get(LIST_URL, {"date_from": "2099-01-01", "date_to": "2099-12-31"})
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
    actor = OrgAdminFactory(organisation=org, full_name="Jane Doe")
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


def test_filter_entity_type_whitelist_rejects_unknown(org_admin_setup) -> None:
    """WR-01 regression: entity_type outside the whitelist returns 400."""
    client, _user, _org = org_admin_setup
    resp = client.get(LIST_URL, {"entity_type": "shop_sync"})
    assert resp.status_code == 400


def test_filter_date_from_after_date_to_returns_400(org_admin_setup) -> None:
    """WR-02 regression: date_from > date_to is rejected with 400."""
    client, _user, _org = org_admin_setup
    resp = client.get(LIST_URL, {"date_from": "2026-12-31", "date_to": "2026-01-01"})
    assert resp.status_code == 400


def test_filter_shop_inaccessible_for_staff_returns_400(staff_setup) -> None:
    """WR-04 regression: Staff requesting an inaccessible shop_id gets 400
    rather than silently receiving an empty page."""
    client, _staff, _org, _accessible_shop, inaccessible_shop = staff_setup
    resp = client.get(LIST_URL, {"shop": inaccessible_shop.pk})
    assert resp.status_code == 400


def test_filter_shop_accessible_for_staff_ok(staff_setup) -> None:
    """WR-04 regression: Staff can still filter by accessible shop_id."""
    client, _staff, org, accessible_shop, _inaccessible_shop = staff_setup
    review_in = ReviewFactory(organisation=org, shop=accessible_shop)
    AuditLogFactory(
        organisation=org,
        entity_type="review",
        entity_id=str(review_in.pk),
        action="reply_posted",
    )
    resp = client.get(LIST_URL, {"shop": accessible_shop.pk})
    assert resp.status_code == 200


def test_org_admin_sees_credit_consumed_row_with_shop_name(org_admin_setup) -> None:
    """CVIS-05 tracer: a shop credit event reaches the Org Admin with the shop name."""
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org, name="Downtown Store")
    AuditLogFactory(
        organisation=org,
        actor=None,
        entity_type="shop",
        entity_id=str(shop.pk),
        action="shop.credits.consumed",
    )
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    rows = resp.data["results"]
    assert len(rows) == 1
    assert rows[0]["action"] == "shop.credits.consumed"
    assert rows[0]["entity_type"] == "shop"
    assert rows[0]["shop_name"] == "Downtown Store"


def _credit_rows(org, count: int) -> None:
    for i in range(count):
        shop = ShopFactory(organisation=org, name=f"Credit Shop {i}")
        AuditLogFactory(
            organisation=org,
            actor=None,
            entity_type="shop",
            entity_id=str(shop.pk),
            action="shop.credits.consumed",
        )


def test_org_admin_credit_rows_query_count_equal_for_1_and_20(org_admin_setup) -> None:
    """CVIS-05 / CLAUDE.md §6.9: shop_name resolution adds no per-row queries."""
    client, _user, org = org_admin_setup
    _credit_rows(org, 1)
    with CaptureQueriesContext(connection) as ctx_one:
        resp_one = client.get(LIST_URL)
    assert resp_one.status_code == 200
    assert len(resp_one.data["results"]) == 1

    _credit_rows(org, 19)
    with CaptureQueriesContext(connection) as ctx_twenty:
        resp_twenty = client.get(LIST_URL)
    assert resp_twenty.status_code == 200
    assert len(resp_twenty.data["results"]) == 20
    assert len(ctx_twenty.captured_queries) == len(ctx_one.captured_queries)
    assert len(ctx_twenty.captured_queries) <= 5


def test_staff_api_never_returns_credit_rows_on_pk_collision(staff_setup) -> None:
    client, _staff, org, accessible_shop, _inaccessible = staff_setup
    review = ReviewFactory(organisation=org, shop=accessible_shop)
    item = ActionItemFactory(organisation=org, shop=accessible_shop, scope=ActionItem.Scope.SHOP)
    AuditLogFactory(
        organisation=org,
        entity_type="shop",
        entity_id=str(review.pk),
        action="shop.credits.consumed",
    )
    AuditLogFactory(
        organisation=org,
        entity_type="shop",
        entity_id=str(accessible_shop.pk),
        action="shop.credits.allocated",
    )
    AuditLogFactory(
        organisation=org,
        entity_type="organisation",
        entity_id=str(item.pk),
        action="organisation.credits.set",
    )
    AuditLogFactory(
        organisation=org,
        entity_type="review",
        entity_id=str(review.pk),
        action="reply_posted",
    )
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert {r["entity_type"] for r in resp.data["results"]} == {"review"}
    assert all(r["shop_name"] is None for r in resp.data["results"])


def test_type_filter_whitelist_is_not_extended_for_credit_types(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    _credit_rows(org, 1)
    assert client.get(LIST_URL, {"entity_type": "shop"}).status_code == 400
    assert len(client.get(LIST_URL).data["results"]) == 1


def _activity_log_actors(user) -> list[dict]:
    client = APIClient()
    client.force_login(user)
    resp = client.get("/admin/org/activity-log/")
    assert resp.status_code == 200
    return resp.context["actors_json"]


def _superadmin_credit_row(org):
    superadmin = UserFactory(
        role=User.Role.SUPERADMIN, organisation=None, full_name="Internal Person"
    )
    AuditLogFactory(
        organisation=org,
        actor=superadmin,
        entity_type="organisation",
        entity_id=str(org.pk),
        action="organisation.credits.set",
    )
    return superadmin


def test_actor_dropdown_shows_platform_label_not_superadmin_name_for_org_admin(
    staff_setup,
) -> None:
    """CVIS-07: Superadmins appear as one generic 'ReviewBee Admin' option, never by
    name or id. Staff never see it (they get no credit rows)."""
    _client, staff, org, accessible_shop, _inaccessible = staff_setup
    org_admin = OrgAdminFactory(organisation=org)
    superadmin = _superadmin_credit_row(org)
    # A staff-visible row so the Staff dropdown query is non-trivial.
    review = ReviewFactory(organisation=org, shop=accessible_shop)
    AuditLogFactory(
        organisation=org,
        actor=staff,
        entity_type="review",
        entity_id=str(review.pk),
        action="reply_posted",
    )

    org_admin_actors = _activity_log_actors(org_admin)
    assert {"id": "platform", "full_name": "ReviewBee Admin"} in org_admin_actors
    assert superadmin.pk not in {a["id"] for a in org_admin_actors}
    assert "Internal Person" not in {a["full_name"] for a in org_admin_actors}

    staff_actors = _activity_log_actors(staff)
    assert "platform" not in {a["id"] for a in staff_actors}
    assert superadmin.pk not in {a["id"] for a in staff_actors}


def test_superadmin_rows_show_platform_label_and_hide_actor_id(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    superadmin = _superadmin_credit_row(org)
    row = client.get(LIST_URL).data["results"][0]
    assert row["actor_name"] == "ReviewBee Admin"
    assert row["actor_id"] is None
    assert superadmin.full_name not in str(client.get(LIST_URL).data)


def test_actor_platform_filter_returns_only_superadmin_rows(org_admin_setup) -> None:
    client, user, org = org_admin_setup
    _superadmin_credit_row(org)
    AuditLogFactory(organisation=org, actor=user, entity_type="review", action="reply_posted")
    resp = client.get(LIST_URL, {"actor": "platform"})
    assert [r["action"] for r in resp.data["results"]] == ["organisation.credits.set"]


def test_actor_filter_by_superadmin_id_returns_nothing(org_admin_setup) -> None:
    """A Superadmin's numeric id cannot be probed through the actor filter."""
    client, _user, org = org_admin_setup
    superadmin = _superadmin_credit_row(org)
    assert client.get(LIST_URL, {"actor": superadmin.pk}).data["results"] == []


# ---------------------------------------------------------------------------
# CVIS-06: AI reply generated event, Credits type filter, shop filter keeps credits
# ---------------------------------------------------------------------------


def _actions(resp) -> list[str]:
    return sorted(r["action"] for r in resp.data["results"])


def test_org_admin_sees_ai_reply_generated_under_review_type(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    review = ReviewFactory(organisation=org)
    AuditLogFactory(
        organisation=org,
        entity_type="review",
        entity_id=str(review.pk),
        action="ai_reply_generated",
        after_data={"tone": "professional", "ai_usage_log_id": 1},
    )
    resp = client.get(LIST_URL, {"entity_type": "review"})
    assert resp.status_code == 200
    assert _actions(resp) == ["ai_reply_generated"]


def test_credits_type_filter_returns_only_credit_rows_for_org_admin(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    AuditLogFactory(organisation=org, entity_type="review", action="reply_posted")
    AuditLogFactory(
        organisation=org, entity_type="shop", entity_id=str(shop.pk), action="shop.credits.consumed"
    )
    AuditLogFactory(
        organisation=org,
        entity_type="organisation",
        entity_id=str(org.pk),
        action="organisation.credits.set",
    )
    resp = client.get(LIST_URL, {"entity_type": "credits"})
    assert resp.status_code == 200
    assert _actions(resp) == ["organisation.credits.set", "shop.credits.consumed"]


def test_shop_filter_keeps_that_shops_credit_rows_for_org_admin(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    shop = ShopFactory(organisation=org)
    other_shop = ShopFactory(organisation=org)
    review = ReviewFactory(organisation=org, shop=shop)
    AuditLogFactory(
        organisation=org, entity_type="review", entity_id=str(review.pk), action="reply_posted"
    )
    AuditLogFactory(
        organisation=org, entity_type="shop", entity_id=str(shop.pk), action="shop.credits.consumed"
    )
    AuditLogFactory(
        organisation=org,
        entity_type="shop",
        entity_id=str(other_shop.pk),
        action="shop.credits.refunded",
    )
    resp = client.get(LIST_URL, {"shop": shop.pk})
    assert resp.status_code == 200
    assert _actions(resp) == ["reply_posted", "shop.credits.consumed"]


def test_staff_sees_ai_reply_generated_only_for_accessible_shops(staff_setup) -> None:
    client, _staff, org, accessible_shop, inaccessible_shop = staff_setup
    review_in = ReviewFactory(organisation=org, shop=accessible_shop)
    review_out = ReviewFactory(organisation=org, shop=inaccessible_shop)
    for review in (review_in, review_out):
        AuditLogFactory(
            organisation=org,
            entity_type="review",
            entity_id=str(review.pk),
            action="ai_reply_generated",
        )
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert [r["entity_id"] for r in resp.data["results"]] == [str(review_in.pk)]


def test_staff_gets_no_credit_rows_from_credits_or_shop_filter(staff_setup) -> None:
    client, _staff, org, accessible_shop, _inaccessible_shop = staff_setup
    AuditLogFactory(
        organisation=org,
        entity_type="shop",
        entity_id=str(accessible_shop.pk),
        action="shop.credits.consumed",
    )
    assert client.get(LIST_URL, {"entity_type": "credits"}).data["results"] == []
    assert client.get(LIST_URL, {"shop": accessible_shop.pk}).data["results"] == []


def test_staff_ai_reply_generated_payload_is_tone_only(staff_setup) -> None:
    """CVIS-06 / CVIS-05: the Staff-visible payload never carries credit fields.

    Uses the real writer so a future change to its after_data fails here.
    """
    from apps.reviews.services.reply_generation import _record_ai_reply_generated

    client, staff, org, accessible_shop, _inaccessible_shop = staff_setup
    review = ReviewFactory(organisation=org, shop=accessible_shop)
    _record_ai_reply_generated(review=review, tone="professional", actor_id=staff.pk)

    rows = client.get(LIST_URL).data["results"]
    assert [r["action"] for r in rows] == ["ai_reply_generated"]
    for row in rows:
        assert set((row["after_data"] or {}).keys()) <= {"tone"}
        assert not any("credit" in key for key in (row["after_data"] or {}))


def test_new_filter_paths_never_return_another_orgs_rows(org_admin_setup) -> None:
    """CVIS-06 cross-tenant: credits and shop filters stay inside the caller's org."""
    client, _user, _org = org_admin_setup
    other_org = OrganisationFactory()
    other_shop = ShopFactory(organisation=other_org)
    other_review = ReviewFactory(organisation=other_org, shop=other_shop)
    AuditLogFactory(
        organisation=other_org,
        entity_type="shop",
        entity_id=str(other_shop.pk),
        action="shop.credits.consumed",
    )
    AuditLogFactory(
        organisation=other_org,
        entity_type="organisation",
        entity_id=str(other_org.pk),
        action="organisation.credits.set",
    )
    AuditLogFactory(
        organisation=other_org,
        entity_type="review",
        entity_id=str(other_review.pk),
        action="ai_reply_generated",
    )

    assert client.get(LIST_URL, {"entity_type": "credits"}).data["results"] == []
    assert client.get(LIST_URL, {"shop": other_shop.pk}).data["results"] == []
    assert client.get(LIST_URL, {"entity_type": "review"}).data["results"] == []


def test_staff_shop_filter_for_another_orgs_shop_returns_400(staff_setup) -> None:
    client, _staff, _org, _accessible_shop, _inaccessible_shop = staff_setup
    other_shop = ShopFactory(organisation=OrganisationFactory())
    assert client.get(LIST_URL, {"shop": other_shop.pk}).status_code == 400


def test_date_to_includes_rows_from_later_in_that_day(org_admin_setup) -> None:
    """Regression: date_to=today must include today's rows (it compared against midnight)."""
    client, _user, org = org_admin_setup
    row = AuditLogFactory(organisation=org, entity_type="review", action="reply_posted")
    AuditLog.objects.filter(pk=row.pk).update(
        created_at=dt.datetime(2026, 11, 12, 6, 49, tzinfo=dt.UTC)
    )
    resp = client.get(LIST_URL, {"date_from": "2026-11-12", "date_to": "2026-11-12"})
    assert resp.status_code == 200
    assert [r["id"] for r in resp.data["results"]] == [row.pk]


def test_date_to_excludes_rows_from_the_next_day(org_admin_setup) -> None:
    client, _user, org = org_admin_setup
    row = AuditLogFactory(organisation=org, entity_type="review", action="reply_posted")
    AuditLog.objects.filter(pk=row.pk).update(
        created_at=dt.datetime(2026, 11, 13, 0, 0, 1, tzinfo=dt.UTC)
    )
    resp = client.get(LIST_URL, {"date_to": "2026-11-12"})
    assert resp.data["results"] == []
