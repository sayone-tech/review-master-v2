"""Phase 11 — Selector tests (list_reviews, get_accessible_shop_ids)."""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import StaffAdminFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.reviews.selectors.reviews import (
    get_accessible_shop_ids,
    list_reviews,
)
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


def test_list_reviews_scoped_by_organisation() -> None:
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    r_a = ReviewFactory(organisation=org_a)
    r_b = ReviewFactory(organisation=org_b)
    qs = list_reviews(organisation_id=org_a.pk)
    ids = list(qs.values_list("id", flat=True))
    assert r_a.pk in ids
    assert r_b.pk not in ids


def test_list_reviews_excludes_soft_deleted() -> None:
    org = OrganisationFactory()
    r1 = ReviewFactory(organisation=org)
    ReviewFactory(organisation=org, deleted_at=timezone.now())
    qs = list_reviews(organisation_id=org.pk)
    assert qs.count() == 1
    assert qs.first() == r1


def test_get_accessible_shop_ids_includes_shop_and_region_scopes() -> None:
    org = OrganisationFactory()
    region = RegionFactory(organisation=org)
    shop_in_region = ShopFactory(organisation=org, region=region)
    shop_direct = ShopFactory(organisation=org)
    ShopFactory(organisation=org)  # not accessible
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=shop_direct
    )
    StaffAccessScope.objects.create(
        user=staff, scope_type=StaffAccessScope.ScopeType.REGION, region=region
    )
    ids = get_accessible_shop_ids(user_id=staff.pk)
    assert shop_direct.pk in ids
    assert shop_in_region.pk in ids
    assert len(ids) == 2


def test_list_reviews_for_staff_filters_by_accessible_shops() -> None:
    org = OrganisationFactory()
    s1 = ShopFactory(organisation=org)
    s2 = ShopFactory(organisation=org)
    r_in_scope = ReviewFactory(organisation=org, shop=s1)
    ReviewFactory(organisation=org, shop=s2)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1)
    qs = list_reviews(organisation_id=org.pk, user=staff)
    ids = list(qs.values_list("id", flat=True))
    assert ids == [r_in_scope.pk]
