"""Phase 13 plan 03 — Tests for ActionItem selectors and BrandScopeGuard."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import StaffAccessScope, User
from apps.accounts.tests.factories import (
    OrgAdminFactory,
    StaffAdminFactory,
    UserFactory,
)
from apps.action_items.models import ActionItem
from apps.action_items.permissions import BrandScopeGuard
from apps.action_items.selectors.items import list_action_items
from apps.action_items.tests.factories import ActionItemFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory


@pytest.mark.django_db
def test_org_admin_sees_all_items():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    ActionItemFactory.create_batch(2, organisation=org, shop=shop, scope=ActionItem.Scope.SHOP)
    ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
    admin = OrgAdminFactory(organisation=org)
    qs = list_action_items(organisation_id=org.pk, user=admin)
    assert qs.count() == 3


@pytest.mark.django_db
def test_staff_sees_only_shop_scope_in_accessible_shops():
    org = OrganisationFactory()
    accessible_shop = ShopFactory(organisation=org)
    inaccessible_shop = ShopFactory(organisation=org)

    visible = ActionItemFactory(organisation=org, shop=accessible_shop, scope=ActionItem.Scope.SHOP)
    ActionItemFactory(organisation=org, shop=inaccessible_shop, scope=ActionItem.Scope.SHOP)
    ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)

    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff,
        scope_type=StaffAccessScope.ScopeType.SHOP,
        shop=accessible_shop,
    )
    qs = list_action_items(organisation_id=org.pk, user=staff)
    pks = list(qs.values_list("pk", flat=True))
    assert pks == [visible.pk]


@pytest.mark.django_db
def test_staff_cannot_see_brand_items():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop
    )
    qs = list_action_items(organisation_id=org.pk, user=staff)
    assert qs.count() == 0


@pytest.mark.django_db
def test_superadmin_returns_none():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    ActionItemFactory(organisation=org, shop=shop, scope=ActionItem.Scope.SHOP)
    superadmin = UserFactory(role=User.Role.SUPERADMIN, organisation=None)
    qs = list_action_items(organisation_id=org.pk, user=superadmin)
    assert qs.count() == 0


@pytest.mark.django_db
def test_select_related_no_n_plus_one():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    assignee = UserFactory(organisation=org)
    review = ReviewFactory(organisation=org, shop=shop)
    for _ in range(5):
        ActionItemFactory(
            organisation=org,
            shop=shop,
            scope=ActionItem.Scope.SHOP,
            assignee=assignee,
            source_review=review,
        )
    admin = OrgAdminFactory(organisation=org)
    qs = list_action_items(organisation_id=org.pk, user=admin)
    with CaptureQueriesContext(connection) as ctx:
        for item in qs:
            _ = item.shop.name if item.shop else None
            _ = item.assignee.email if item.assignee else None
            _ = item.source_review.pk if item.source_review else None
    # One main query is sufficient because select_related joined shop, assignee,
    # source_review, source_review__shop. Allow a tiny budget for safety.
    assert len(ctx.captured_queries) <= 3


@pytest.mark.django_db
def test_brand_scope_guard_blocks_staff_brand_item():
    org = OrganisationFactory()
    staff = StaffAdminFactory(organisation=org)
    brand_item = ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
    shop_item = ActionItemFactory(
        organisation=org, shop=ShopFactory(organisation=org), scope=ActionItem.Scope.SHOP
    )
    guard = BrandScopeGuard()
    request = SimpleNamespace(user=staff)
    assert guard.has_object_permission(request, None, brand_item) is False
    assert guard.has_object_permission(request, None, shop_item) is True


@pytest.mark.django_db
def test_list_hides_merged_duplicates():
    """Phase 18 (D-10): items with canonical_id set must not appear in the list."""
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    primary = ActionItemFactory(
        organisation=org, shop=shop, scope=ActionItem.Scope.SHOP, source=ActionItem.Source.AI
    )
    dup = ActionItemFactory(
        organisation=org, shop=shop, scope=ActionItem.Scope.SHOP, source=ActionItem.Source.AI
    )
    dup.canonical = primary
    dup.save(update_fields=["canonical"])
    admin = OrgAdminFactory(organisation=org)
    qs = list_action_items(organisation_id=org.pk, user=admin)
    ids = set(qs.values_list("pk", flat=True))
    assert primary.pk in ids
    assert dup.pk not in ids


@pytest.mark.django_db
def test_list_annotates_duplicate_count():
    """Phase 18 (D-11): primary rows expose duplicate_count == #merged duplicates."""
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    primary = ActionItemFactory(
        organisation=org, shop=shop, scope=ActionItem.Scope.SHOP, source=ActionItem.Source.AI
    )
    for _ in range(2):
        d = ActionItemFactory(
            organisation=org, shop=shop, scope=ActionItem.Scope.SHOP, source=ActionItem.Source.AI
        )
        d.canonical = primary
        d.save(update_fields=["canonical"])
    admin = OrgAdminFactory(organisation=org)
    qs = list_action_items(organisation_id=org.pk, user=admin)
    found = next(item for item in qs if item.pk == primary.pk)
    assert found.duplicate_count == 2


@pytest.mark.django_db
def test_list_query_count_with_duplicates():
    """Phase 18: list query count is bounded regardless of merge density."""
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    for _ in range(5):
        primary = ActionItemFactory(
            organisation=org, shop=shop, scope=ActionItem.Scope.SHOP, source=ActionItem.Source.AI
        )
        for _ in range(2):
            d = ActionItemFactory(
                organisation=org,
                shop=shop,
                scope=ActionItem.Scope.SHOP,
                source=ActionItem.Source.AI,
            )
            d.canonical = primary
            d.save(update_fields=["canonical"])
    admin = OrgAdminFactory(organisation=org)
    qs = list_action_items(organisation_id=org.pk, user=admin)
    with CaptureQueriesContext(connection) as ctx:
        items = list(qs)
        for item in items:
            _ = item.duplicate_count
    assert len(ctx.captured_queries) <= 6


@pytest.mark.django_db
def test_brand_scope_guard_allows_org_admin():
    org = OrganisationFactory()
    admin = OrgAdminFactory(organisation=org)
    brand_item = ActionItemFactory(organisation=org, shop=None, scope=ActionItem.Scope.BRAND)
    shop_item = ActionItemFactory(
        organisation=org, shop=ShopFactory(organisation=org), scope=ActionItem.Scope.SHOP
    )
    guard = BrandScopeGuard()
    request = SimpleNamespace(user=admin)
    assert guard.has_object_permission(request, None, brand_item) is True
    assert guard.has_object_permission(request, None, shop_item) is True
