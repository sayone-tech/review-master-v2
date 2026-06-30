"""Phase 11 — Selector tests (list_reviews, get_accessible_shop_ids).

Phase 26 (TMGT-07/D-01): also covers list_canonical_tags_for_org search filter.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import StaffAdminFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.reviews.selectors.canonical_tags import list_canonical_tags_for_org
from apps.reviews.selectors.reviews import (
    get_accessible_shop_ids,
    list_reviews,
)
from apps.reviews.tests.factories import OrgCanonicalTagFactory, ReviewFactory
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


# ---------------------------------------------------------------------------
# Phase 26 — list_canonical_tags_for_org search filter (TMGT-07/D-01)
# ---------------------------------------------------------------------------


def test_list_canonical_tags_search_returns_matching_label() -> None:
    """Substring search on label is case-insensitive and org-scoped (D-01)."""
    org = OrganisationFactory()
    tag_match = OrgCanonicalTagFactory(organisation=org, label="Food Quality")
    OrgCanonicalTagFactory(organisation=org, label="Service Speed")
    qs = list_canonical_tags_for_org(organisation_id=org.pk, search="food")
    ids = list(qs.values_list("id", flat=True))
    assert tag_match.pk in ids
    assert len(ids) == 1


def test_list_canonical_tags_search_is_case_insensitive() -> None:
    """Case-insensitive: searching 'FOOD' matches 'Food Quality' (D-01)."""
    org = OrganisationFactory()
    tag = OrgCanonicalTagFactory(organisation=org, label="Food Quality")
    qs = list_canonical_tags_for_org(organisation_id=org.pk, search="FOOD")
    ids = list(qs.values_list("id", flat=True))
    assert tag.pk in ids


def test_list_canonical_tags_search_cross_org_isolation() -> None:
    """A tag in another org with a matching label is NOT returned (T-26-01)."""
    org_a = OrganisationFactory()
    org_b = OrganisationFactory()
    OrgCanonicalTagFactory(organisation=org_a, label="Food Quality")
    tag_b = OrgCanonicalTagFactory(organisation=org_b, label="Food Quality")
    qs = list_canonical_tags_for_org(organisation_id=org_a.pk, search="food")
    ids = list(qs.values_list("id", flat=True))
    assert tag_b.pk not in ids


def test_list_canonical_tags_empty_search_returns_all_org_rows() -> None:
    """Empty search returns all rows in the same order as without search."""
    org = OrganisationFactory()
    OrgCanonicalTagFactory(organisation=org, label="Ambiance", review_count=5)
    OrgCanonicalTagFactory(organisation=org, label="Food Quality", review_count=10)
    qs_with = list_canonical_tags_for_org(organisation_id=org.pk, search="")
    qs_without = list_canonical_tags_for_org(organisation_id=org.pk)
    assert list(qs_with.values_list("id", flat=True)) == list(
        qs_without.values_list("id", flat=True)
    )


def test_list_canonical_tags_query_count_without_search() -> None:
    """Paginated response issues ≤2 queries (1 COUNT + 1 SELECT) without search (§6.9)."""
    org = OrganisationFactory()
    OrgCanonicalTagFactory.create_batch(5, organisation=org)
    with CaptureQueriesContext(connection) as ctx:
        qs = list_canonical_tags_for_org(organisation_id=org.pk)
        count = qs.count()
        list(qs)
    assert len(ctx.captured_queries) <= 2, f"Expected ≤2 queries, got {len(ctx.captured_queries)}"
    assert count == 5


def test_list_canonical_tags_query_count_with_search() -> None:
    """Paginated response issues ≤2 queries (1 COUNT + 1 SELECT) with ?search=foo (§6.9/D-01)."""
    org = OrganisationFactory()
    OrgCanonicalTagFactory.create_batch(5, organisation=org)
    OrgCanonicalTagFactory(organisation=org, label="Food Quality")
    with CaptureQueriesContext(connection) as ctx:
        qs = list_canonical_tags_for_org(organisation_id=org.pk, search="food")
        count = qs.count()
        list(qs)
    assert len(ctx.captured_queries) <= 2, f"Expected ≤2 queries, got {len(ctx.captured_queries)}"
    assert count == 1
