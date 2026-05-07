"""Fixtures for apps.dashboard tests."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory
from apps.dashboard.filters import DashboardFilterParams
from apps.organisations.tests.factories import OrganisationFactory
from apps.regions.tests.factories import RegionFactory
from apps.reviews.models import Review
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory


@pytest.fixture
def org_admin_with_shops(db):
    org = OrganisationFactory()
    user = OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)
    shop1 = ShopFactory(organisation=org)
    shop2 = ShopFactory(organisation=org)
    return {"user": user, "org": org, "shops": [shop1, shop2]}


@pytest.fixture
def org(db):
    return OrganisationFactory()


@pytest.fixture
def region(db, org):
    return RegionFactory(organisation=org)


@pytest.fixture
def org_admin(db, org):
    return OrgAdminFactory(organisation=org, role=User.Role.ORG_ADMIN)


@pytest.fixture
def accessible_shops(db, org, region):
    """3 shops belonging to the same org and region."""
    return [ShopFactory(organisation=org, region=region) for _ in range(3)]


@pytest.fixture
def single_shop(db, org, region):
    return ShopFactory(organisation=org, region=region)


@pytest.fixture
def single_shop_params(db, org, single_shop):
    """DashboardFilterParams scoped to a single shop (Staff-style)."""
    today = timezone.now().date()
    return DashboardFilterParams(
        region_id=None,
        shop_id=None,
        date_from=today - timedelta(days=30),
        date_to=today,
        accessible_shop_ids=(single_shop.id,),
    )


@pytest.fixture
def multi_shop_params(db, org, accessible_shops):
    """DashboardFilterParams scoped to multiple shops."""
    today = timezone.now().date()
    return DashboardFilterParams(
        region_id=None,
        shop_id=None,
        date_from=today - timedelta(days=30),
        date_to=today,
        accessible_shop_ids=tuple(s.id for s in accessible_shops),
    )


def make_review(
    *,
    shop,
    star_rating: int = 5,
    sentiment: str = "",
    enrichment_status: str = Review.EnrichmentStatus.PENDING,
    days_ago: int = 5,
) -> Review:
    """Helper factory wrapper for creating reviews in tests."""
    create_time = timezone.now() - timedelta(days=days_ago)
    return ReviewFactory(
        organisation=shop.organisation,
        shop=shop,
        star_rating=star_rating,
        sentiment=sentiment,
        enrichment_status=enrichment_status,
        review_create_time=create_time,
        review_update_time=create_time,
    )
