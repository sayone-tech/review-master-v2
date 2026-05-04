"""Phase 11 — ReviewViewSet API tests including REVW-14 query-count gate."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffAccessScope
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/reviews/"


@pytest.fixture
def org_admin_client():
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, org


def test_list_reviews_accessible_to_org_admin(org_admin_client) -> None:
    client, _, org = org_admin_client
    ReviewFactory.create_batch(3, organisation=org)
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert "results" in resp.data
    assert resp.data["total_count"] == 3


def test_list_reviews_filters_by_rating(org_admin_client) -> None:
    client, _, org = org_admin_client
    ReviewFactory.create_batch(2, organisation=org, star_rating=5)
    ReviewFactory.create_batch(3, organisation=org, star_rating=3)
    resp = client.get(LIST_URL, {"rating": 5})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 2


def test_list_reviews_filters_by_shop_and_is_replied(org_admin_client) -> None:
    client, _, org = org_admin_client
    s1 = ShopFactory(organisation=org)
    s2 = ShopFactory(organisation=org)
    ReviewFactory(organisation=org, shop=s1, is_replied=True)
    ReviewFactory(organisation=org, shop=s1, is_replied=False)
    ReviewFactory(organisation=org, shop=s2, is_replied=True)
    resp = client.get(LIST_URL, {"shop": s1.pk, "is_replied": "true"})
    assert resp.status_code == 200
    assert resp.data["total_count"] == 1


def test_list_reviews_filters_by_date_range(org_admin_client) -> None:
    client, _, org = org_admin_client
    now = timezone.now()
    ReviewFactory(organisation=org, review_create_time=now - timedelta(days=10))
    ReviewFactory(organisation=org, review_create_time=now - timedelta(days=2))
    resp = client.get(
        LIST_URL,
        {
            "from_date": (now - timedelta(days=5)).date().isoformat(),
            "to_date": now.date().isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.data["total_count"] == 1


def test_list_reviews_default_ordering_newest_first(org_admin_client) -> None:
    client, _, org = org_admin_client
    older = ReviewFactory(organisation=org, review_create_time=timezone.now() - timedelta(days=5))
    newer = ReviewFactory(organisation=org, review_create_time=timezone.now())
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.data["results"]]
    assert ids == [newer.pk, older.pk]


def test_list_reviews_page_size_param(org_admin_client) -> None:
    client, _, org = org_admin_client
    ReviewFactory.create_batch(8, organisation=org)
    resp = client.get(LIST_URL, {"page_size": 3})
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 3
    assert resp.data["total_count"] == 8


def test_staff_user_sees_only_accessible_shops_reviews() -> None:
    org = OrganisationFactory()
    s1 = ShopFactory(organisation=org)
    s2 = ShopFactory(organisation=org)
    ReviewFactory.create_batch(2, organisation=org, shop=s1)
    ReviewFactory.create_batch(2, organisation=org, shop=s2)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1)
    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    assert resp.data["total_count"] == 2


def test_reviews_list_query_count_org_admin(org_admin_client) -> None:
    """REVW-14: <=5 SQL queries regardless of page size."""
    client, _, org = org_admin_client
    ReviewFactory.create_batch(50, organisation=org)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(LIST_URL, {"page_size": 25})
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 25
    assert len(ctx.captured_queries) <= 5, [q["sql"] for q in ctx.captured_queries]


def test_reviews_list_query_count_staff_admin() -> None:
    """REVW-14 + Staff scope: <=5 queries (allows the StaffAccessScope subquery)."""
    org = OrganisationFactory()
    s1 = ShopFactory(organisation=org)
    ReviewFactory.create_batch(40, organisation=org, shop=s1)
    staff = StaffAdminFactory(organisation=org)
    StaffAccessScope.objects.create(user=staff, scope_type=StaffAccessScope.ScopeType.SHOP, shop=s1)
    client = APIClient()
    client.force_authenticate(user=staff)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(LIST_URL, {"page_size": 25})
    assert resp.status_code == 200
    assert len(ctx.captured_queries) <= 5, [q["sql"] for q in ctx.captured_queries]
